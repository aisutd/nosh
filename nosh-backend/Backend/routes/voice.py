"""Browser transcripts use the same RAG and grounded Q&A as desktop cooking.

State is supplied per turn, never stored in process globals or shared across users.
Recipe text supplied by the browser is untrusted context, not an approval record.
"""
from security import get_optional_user
from personalization import memory_context

import logging
import re
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

router = APIRouter(prefix="/voice", tags=["voice"])


class VoiceTurn(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    ingredients: list[Annotated[str, Field(max_length=200)]] = Field(default_factory=list, max_length=100)
    recipe: str = Field(default="", max_length=30000)
    step: int = Field(default=-1, ge=-1, le=500)


def recipe_steps(recipe):
    """Only numbered directions after a steps/instructions heading are navigable."""
    section = re.split(r"(?im)^\s*(?:#+\s*)?(?:\*\*)?(?:steps|instructions|directions|method)(?:\*\*)?\s*:?\s*$", recipe)
    if len(section) < 2:
        return []
    steps = []
    for line in section[1].splitlines():
        match = re.match(r"^\s*(?:\*\*)?(?:Step\s+)?\d+[.):]\s*(.+)", line, re.I)
        if match:
            steps.append(match.group(1).strip())
        elif steps and line.strip() and not line.lstrip().startswith(('#', '**')):
            steps[-1] += ' ' + line.strip()
        elif steps and line.strip():
            break
    return steps


def handle_turn(turn, personalization=None):
    command = turn.message.lower().strip().rstrip('.!?')
    steps = recipe_steps(turn.recipe)
    step = min(turn.step, len(steps) - 1)
    navigation = command in {'next', 'next step', 'continue', 'repeat', 'repeat step', 'previous', 'previous step', 'back', 'start cooking', 'current step'}
    target = re.fullmatch(r'(?:go to )?step (\d+)', command)
    if navigation or target:
        if not steps:
            return {'answer': 'Choose a recipe with numbered instructions first.', 'step': -1}
        if target:
            desired = int(target[1]) - 1
        elif command in {'next', 'next step', 'continue'}:
            desired = step + 1
        elif command in {'previous', 'previous step', 'back'}:
            desired = max(0, step - 1)
        elif command == 'start cooking':
            desired = 0
        else:
            desired = max(0, step)
        if not 0 <= desired < len(steps):
            return {'answer': f'This recipe has {len(steps)} steps. You are at step {step + 1}.', 'step': step}
        return {'answer': f'Step {desired + 1}. {steps[desired]}', 'step': desired}
    if command in {'what can i cook', 'generate recipe', 'find a recipe', 'make a recipe'}:
        if not any(item.strip() for item in turn.ingredients):
            return {'answer': 'Add ingredients to your pantry first.', 'step': step}
        from nosh_pipeline import run_nosh
        result = run_nosh(turn.ingredients, user_query='', personalization=personalization)
        generated = result.get('recipe') if result.get('status') == 'ok' else None
        return {'answer': generated or result['message'], 'recipe': generated or turn.recipe, 'step': -1 if generated else step}
    if not turn.recipe:
        return {'answer': 'Add pantry ingredients and say “What can I cook?”, or open a recipe to ask cooking questions.', 'step': step}
    from llm.recipe_chat import answer_question, judge_answer
    from llm.nosh_generation import judge_passed
    context = {'approved_recipe': turn.recipe, 'source_context': turn.recipe, 'available_ingredients': turn.ingredients, 'personalization': personalization or {}}
    decision = answer_question(context, turn.message, [])
    if decision and (decision['status'] != 'answered' or judge_passed(judge_answer(context, turn.message, [], decision['answer']))):
        return {'answer': decision['answer'], 'step': step}
    return {'answer': 'I could not verify an answer from this recipe. Please try a more specific cooking question.', 'step': step}


@router.post('/turn')
async def voice_turn(turn: VoiceTurn, current_user: dict | None = Depends(get_optional_user)):
    if not turn.message.strip():
        raise HTTPException(400, 'Say or type a cooking question.')
    try:
        return await run_in_threadpool(handle_turn, turn, memory_context(current_user))
    except Exception as exc:
        logging.getLogger(__name__).exception('Voice turn failed')
        raise HTTPException(503, 'NOSH could not respond. Check the recipe service and try again.') from exc
