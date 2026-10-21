"""Image and detection JSON entry points for the hybrid RAG pipeline."""
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field
from nosh_pipeline import run_nosh
from vision.detector import detect_ingredients

router = APIRouter()


class IngredientDetection(BaseModel):
    name: str = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)


class DetectionOutput(BaseModel):
    ingredients: list[IngredientDetection]


class RecipeFromDetectionsRequest(BaseModel):
    detections: DetectionOutput
    user_query: str = ""


async def generate_from_detections(detections: DetectionOutput, user_query: str):
    ingredients = sorted({
        item.name.replace("_", " ").strip().lower()
        for item in detections.ingredients
        if item.name.replace("_", " ").strip()
    })

    if not ingredients:
        raise HTTPException(status_code=400, detail="No ingredient names were detected or provided.")

    result = await run_in_threadpool(run_nosh, ingredients, user_query=user_query)
    return {
        "detections": detections.model_dump(),
        "ingredients": ingredients,
        "result": result,
    }


@router.post("/recipes/from-detections")
async def recipes_from_detections(request: RecipeFromDetectionsRequest):
    return await generate_from_detections(request.detections, request.user_query)


MAX_IMAGE_BYTES = 10 * 1024 * 1024


@router.post("/recipes/from-image")
async def recipes_from_image(
    image: UploadFile = File(...),
    user_query: str = Form(""),
):
    """Detect ingredients in an image and generate a recipe from retrieved sources."""
    try:
        image_bytes = await image.read(MAX_IMAGE_BYTES + 1)
    finally:
        await image.close()

    if len(image_bytes) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="Image must be 10 MB or smaller.")
    if not image_bytes:
        raise HTTPException(status_code=400, detail="The uploaded image is empty.")

    try:
        output = await run_in_threadpool(detect_ingredients, image_bytes)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail="The ingredient detection model is unavailable.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return await generate_from_detections(DetectionOutput.model_validate(output), user_query)




class GenerateRecipeRequest(BaseModel):
    ingredients: list[str] = Field(min_length=1)
    user_query: str = ""


@router.post("/recipes/generate")
async def generate_recipe_from_pantry(request: GenerateRecipeRequest):
    """Use the reviewed pantry, including manual corrections, for RAG."""
    ingredients = sorted({
        name.replace("_", " ").strip().lower()
        for name in request.ingredients
        if name.replace("_", " ").strip()
    })
    if not ingredients:
        raise HTTPException(status_code=400, detail="Add at least one ingredient.")
    try:
        result = await run_in_threadpool(run_nosh, ingredients, user_query=request.user_query)
    except Exception as exc:
        import logging
        logging.getLogger(__name__).exception("Recipe generation failed")
        raise HTTPException(
            status_code=503,
            detail="Recipe generation is unavailable. Check that Ollama is running and the recipe index is built.",
        ) from exc
    return {"ingredients": ingredients, "result": result}


@router.post("/recipes/options")
async def recipe_options(request: GenerateRecipeRequest):
    try:
        result = await run_in_threadpool(
            run_nosh, request.ingredients, user_query=request.user_query, retrieve_only=True, top_k=15,
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Recipe search is unavailable. Check Ollama and the recipe index.") from exc
    cards = [{
        "id": "rag:" + recipe["id"], "title": recipe["title"],
        "ingredients": recipe.get("ingredients", ""), "source_url": recipe["url"],
        "image": recipe.get("metadata", {}).get("img_src"),
        "total_time": recipe.get("metadata", {}).get("total_time"),
    } for recipe in result["recipes"]]
    return {"status": result["status"], "message": result["message"], "recipes": cards}


class SelectedRecipeRequest(GenerateRecipeRequest):
    recipe_id: str = Field(min_length=1)


@router.post("/recipes/generate-selected")
async def generate_selected(request: SelectedRecipeRequest):
    try:
        result = await run_in_threadpool(
            run_nosh, request.ingredients, user_query=request.user_query,
            selected_recipe_id=request.recipe_id.removeprefix("rag:"),
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Recipe generation is unavailable. Check Ollama and the recipe index.") from exc
    return {"result": result}
