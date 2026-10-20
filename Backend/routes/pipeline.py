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


