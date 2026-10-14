"""In-memory, bounded conversation about one approved recipe."""
import re

import httpx
import ollama

from llm.nosh_generation import (
    classify_request, judge_passed, OUT_OF_SCOPE, UNSUPPORTED_PREFERENCES,
    INSUFFICIENT_CONTEXT, OUT_OF_SCOPE_PATTERN,
)
from llm.recipe_chat import answer_question, judge_answer
from retrieval.nosh_retrieval import format_recipes_for_llm, normalize_ingredients

MODEL_ERRORS = (ConnectionError, ollama.ResponseError, httpx.RequestError)


class CookingSession:
    """Call start() once, then ask(). Accepted advice and verified facts enter history.

    Sessions are local to this object and are not persisted between processes.
    A new start clears the old recipe, including when the new request fails.
    """
    def __init__(self):
        self._context = None
        self._history = []
        self._step_index = 0

    def start(self, ingredients, *, user_query='', top_k=5, max_time=None, collection=None):
        from nosh_pipeline import run_nosh
        self._context = None
        self._history = []
        self._step_index = 0
        try:
            result = run_nosh(ingredients, user_query=user_query, top_k=top_k,
                              max_time=max_time, collection=collection)
        except MODEL_ERRORS:
            return {'status': 'model_error', 'recipe': None, 'recipes': [],
                    'message': 'Could not reach the local models. Check Ollama and try again.'}
        if result['status'] == 'ok':
            self._context = {
                'approved_recipe': result['recipe'],
                'source_context': format_recipes_for_llm(result['recipes'], top_k=1),
                'available_ingredients': normalize_ingredients(ingredients) + ['water', 'salt', 'pepper'],
                'original_request': user_query, 'max_total_minutes': max_time,
            }
        return result

    def _remember(self, question, answer):
        self._history.extend([{'role': 'user', 'content': question},
                              {'role': 'assistant', 'content': answer}])
        self._history = self._history[-12:]
        return {'status': 'ok', 'answer': answer}

    def _navigate(self, question):
        # Match entire commands: mixed requests still go through scope checks.
        text = re.sub(r"[?!.,'’]", '', question.lower()).strip()
        text = re.sub(r"\s+", ' ', text)
        if re.fullmatch(r"(?:(?:ok|okay) )?(?:thanks|thank you|thansk+s*(?: yous?)?|thanks yous?)(?: so much)?", text):
            return self._remember(question, "You're welcome! Say 'next' when you're ready to continue.")
        if re.fullmatch(r"(?:hi|hello|hey)(?: nosh| there)?", text):
            return self._remember(question, "Hi! I can help with this recipe. Ask a cooking question, or say next when you're ready.")
        if text in {'left or right', 'right or left', 'which one', 'what do you mean'}:
            return {'status': 'insufficient_input', 'message': 'Which part of the recipe do you mean? Tell me what you are trying to do.'}
        actions = {
            'next': r"(?:(?:ok|okay|and) )?(?:next(?: step)?|(?:whats|what is) (?:the )?next(?: step)?(?: after that)?|what next)",
            'back': r"(?:back|go back|previous(?: step)?)",
            'repeat': r"(?:repeat(?: (?:that|the step|this step))?|current step|(?:whats|what is) (?:the )?current step)",
            'start': r"(?:start|start cooking|start over|first step|(?:whats|what is) (?:the )?first step)",
        }
        action = next((name for name, pattern in actions.items() if re.fullmatch(pattern, text)), None)
        specific = re.fullmatch(r"(?:go to |repeat )?step (\d+)", text)
        if action is None and specific is None:
            return None
        steps = re.findall(r"^\d+\. (.+)$", self._context.get('approved_recipe', '').split('Steps:', 1)[-1], re.M)
        if not steps:
            return {'status': 'insufficient_context', 'message': 'I could not find numbered steps in this recipe.'}
        if specific:
            index = int(specific[1]) - 1
            if not 0 <= index < len(steps):
                return {'status': 'insufficient_input', 'message': f'This recipe has {len(steps)} steps. Choose a step from 1 to {len(steps)}.'}
            self._step_index = index
        elif action == 'next':
            if self._step_index >= len(steps) - 1:
                return self._remember(question, 'That was the last step in this recipe. Say repeat to hear it again, or start over.')
            self._step_index += 1
        elif action == 'back':
            self._step_index = max(0, self._step_index - 1)
        elif action == 'start':
            self._step_index = 0
        return self._remember(question, f'Step {self._step_index + 1}: {steps[self._step_index]}')

    def ask(self, question, *, show_drafts=False):
        if not isinstance(question, str):
            raise ValueError('question must be a string')
        if self._context is None:
            return {'status': 'no_recipe', 'message': 'Start with an approved recipe first.'}
        if not question.strip():
            return {'status': 'insufficient_input', 'message': 'Ask a question about the current recipe.'}
        if len(question) > 4000:
            return {'status': 'insufficient_input', 'message': 'Please keep your question under 4,000 characters.'}
        navigation = self._navigate(question)
        if navigation is not None:
            return navigation
        self._context['current_step_number'] = self._step_index + 1
        try:
            scope = classify_request(self._context['available_ingredients'], question,
                                     conversation_context={**self._context, 'history': self._history})
            if scope['status'] != 'in_scope':
                messages = {'out_of_scope': OUT_OF_SCOPE,
                            'unsupported_preferences': UNSUPPORTED_PREFERENCES,
                            'insufficient_input': 'Ask a question about the current recipe.',
                            'guardrail_error': 'Could not validate request scope. Please try again.'}
                return {'status': scope['status'], 'message': messages[scope['status']]}
            decision = answer_question(self._context, question, self._history)
            if decision is None:
                return {'status': 'failed_validation', 'message': 'Could not validate an answer. Please rephrase your question.'}
            if decision['status'] in {'out_of_scope', 'unsupported_preferences'}:
                return {'status': decision['status'], 'message': OUT_OF_SCOPE if decision['status'] == 'out_of_scope' else UNSUPPORTED_PREFERENCES}
            if decision['status'] == 'insufficient_input':
                return {'status': 'insufficient_input', 'message': 'Which part of the recipe do you mean? Tell me what you are trying to do.'}
            if decision['status'] == 'insufficient_context':
                return {'status': 'insufficient_context', 'message': INSUFFICIENT_CONTEXT}
            if decision['status'] == 'change_requested':
                return {'status': 'change_requested', 'message': 'This chat explains the current recipe. Start a new recipe request to change ingredients or cooking methods.'}
            answer = decision['answer'].strip()
            if OUT_OF_SCOPE_PATTERN.search(answer):
                return {'status': 'out_of_scope', 'message': OUT_OF_SCOPE}
            kind = decision.get('kind', 'recipe_fact')
            # Do not rely on the answerer's label for explicit quantity/time questions.
            if kind != 'suggestion' and (re.search(
                    r"\b(?:how (?:many|much|long)|temperature|degrees?|minutes?|hours?)\b", question, re.I)
                    or re.search(r"\d", answer)):
                kind = 'recipe_fact'
            verdict = None
            if len(answer) > 4000:
                result = {'status': 'failed_validation', 'message': 'The answer was too long. Please ask a shorter question.'}
            else:
                # The source-grounding judge applies to recipe facts, not general advice.
                if kind == 'recipe_fact':
                    verdict = judge_answer(self._context, question, self._history, answer)
                if kind == 'recipe_fact' and not judge_passed(verdict):
                    result = {'status': 'failed_validation', 'message': 'I could not verify those details against the saved recipe.'}
                else:
                    result = self._remember(question, answer)
                    result['answer_kind'] = kind
                    result['validation'] = 'source_checked' if kind == 'recipe_fact' else 'general_advice'
            if show_drafts:
                result['diagnostics'] = {'draft': decision['answer'], 'answer_kind': kind,
                                         'judge_verdict': verdict,
                                         'judge_used': verdict is not None}
            return result

        except MODEL_ERRORS:
            return {'status': 'model_error', 'message': 'Could not reach the local models. Check Ollama and try again.'}


def chat_loop(session, *, show_drafts=False):
    print('\nCooking starts at step 1. Say next when you finish a step, back, repeat, or step 2 to navigate. Ask questions anytime. Type quit or exit to finish.')
    while True:
        try:
            question = input('You: ').strip()
            if question.lower() in {'quit', 'exit'}:
                print('\nCooking chat ended.')
                break
            result = session.ask(question, show_drafts=True) if show_drafts else session.ask(question)
            if show_drafts and result.get("diagnostics"):
                import json
                print("Draft diagnostics (not an approved recipe):", json.dumps(result["diagnostics"], indent=2))
            print('NOSH:', result.get('answer', result.get('message')))
        except (EOFError, KeyboardInterrupt):
            print('\nCooking chat ended.')
            break
