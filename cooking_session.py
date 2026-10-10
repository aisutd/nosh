"""In-memory, bounded conversation about one approved recipe."""
import httpx
import ollama

from llm.nosh_generation import (
    classify_request, judge_passed, OUT_OF_SCOPE, UNSUPPORTED_PREFERENCES,
    INSUFFICIENT_CONTEXT,
)
from llm.recipe_chat import answer_question, judge_answer
from retrieval.nosh_retrieval import format_recipes_for_llm, normalize_ingredients

MODEL_ERRORS = (ConnectionError, ollama.ResponseError, httpx.RequestError)


class CookingSession:
    """Call start() once, then ask(). Only approved answers enter history.

    Sessions are local to this object and are not persisted between processes.
    A new start clears the old recipe, including when the new request fails.
    """
    def __init__(self):
        self._context = None
        self._history = []

    def start(self, ingredients, *, user_query='', top_k=5, max_time=None, collection=None):
        from nosh_pipeline import run_nosh
        self._context = None
        self._history = []
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

    def ask(self, question):
        if not isinstance(question, str):
            raise ValueError('question must be a string')
        if self._context is None:
            return {'status': 'no_recipe', 'message': 'Start with an approved recipe first.'}
        if not question.strip():
            return {'status': 'insufficient_input', 'message': 'Ask a question about the current recipe.'}
        if len(question) > 4000:
            return {'status': 'insufficient_input', 'message': 'Please keep your question under 4,000 characters.'}
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
            if decision['status'] == 'insufficient_context':
                return {'status': 'insufficient_context', 'message': INSUFFICIENT_CONTEXT}
            if decision['status'] == 'change_requested':
                return {'status': 'change_requested', 'message': 'This chat explains the current recipe. Start a new recipe request to change ingredients or cooking methods.'}
            answer = decision['answer'].strip()
            if len(answer) > 4000 or not judge_passed(judge_answer(self._context, question, self._history, answer)):
                return {'status': 'failed_validation', 'message': 'I could not verify that answer against the recipe. Please rephrase your question.'}
        except MODEL_ERRORS:
            return {'status': 'model_error', 'message': 'Could not reach the local models. Check Ollama and try again.'}
        self._history.extend([{'role': 'user', 'content': question},
                              {'role': 'assistant', 'content': answer}])
        self._history = self._history[-12:]
        return {'status': 'ok', 'answer': answer}


def chat_loop(session):
    print('\nAsk about this recipe. Type quit or exit to finish.')
    while True:
        try:
            question = input('You: ').strip()
            if question.lower() in {'quit', 'exit'}:
                break
            result = session.ask(question)
            print('NOSH:', result.get('answer', result.get('message')))
        except (EOFError, KeyboardInterrupt):
            print('\nCooking chat ended.')
            break
