"""Live Ollama regression cases for recipe chat; run from the repository root."""
import json
import argparse
from pathlib import Path
from cooking_session import CookingSession
from llm.nosh_generation import OUT_OF_SCOPE, evaluate_generation, judge_passed, generate_recipe


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--generation-only", action="store_true")
    args = parser.parse_args()
    # Fixed approved recipe isolates follow-up behavior from initial generation.
    context = {
        'approved_recipe': 'Recipe Name: Lemonade\nChanges:\n- none\nSteps:\n1. Juice 6 lemons.\n2. Mix the juice with 1 cup sugar and 6 cups water.\n3. Chill and serve.',
        'source_context': 'Old-Fashioned Lemonade. Ingredients: 6 lemons, 1 cup white sugar, 6 cups water. Directions: Juice lemons. Mix juice, sugar, and water. Chill and serve.',
        'available_ingredients': ['lemon', 'sugar', 'water', 'salt', 'pepper'],
        'original_request': 'Make lemonade', 'max_total_minutes': None,
    }
    session = CookingSession()
    session._context = context
    cases = [
        ('How should i juice this lemon?', 'ok'),
        ('how can i juice this lemon?', 'ok'),
        ('whos the president of the united states', 'out_of_scope'),
        ('Who is the best person ever?', 'out_of_scope'),
        ('Am I able to juice this lemon with a fork?', 'ok'),
        ('How much sugar does this recipe use?', 'ok'),
        ('What exact temperature should I chill it to?', 'insufficient_context'),
        ('Replace the sugar with honey.', 'change_requested'),
    ]
    results = []
    for question, expected in ([] if args.generation_only else cases):
        reply = session.ask(question)
        passed = reply['status'] == expected
        if expected == 'out_of_scope':
            passed = passed and reply['message'] == OUT_OF_SCOPE
        result = {'question': question, 'expected_status': expected, 'reply': reply, 'passed': passed}
        results.append(result)
        print(json.dumps(result), flush=True)
    bad = 'Recipe Name: Lemonade\nChanges:\n- 6 lemons omitted\n- 6 lemons replaced with 1 lemon\nSteps:\n1. Juice 1 lemon.'
    verdict = evaluate_generation('lemon, sugar', context['source_context'], bad)
    results.append({'case': 'contradictory_changes', 'verdict': verdict, 'passed': not judge_passed(verdict)})
    answer = generate_recipe('lemon, sugar', context['source_context'], user_query='Make lemonade')
    verdict = evaluate_generation('lemon, sugar', context['source_context'], answer, user_query='Make lemonade')
    results.append({'case': 'initial_generation', 'answer': answer, 'verdict': verdict,
                    'passed': judge_passed(verdict) and '6' in answer and '1 lemon' not in answer})
    output = Path('evaluation/results/chat_generation_results.json' if args.generation_only else 'evaluation/results/chat_results.json')
    output.write_text(json.dumps({'description': 'Live development checks; status success is not independent answer-quality proof.',
                                  'results': results}, indent=2) + '\n')
    print(f"{sum(r['passed'] for r in results)}/{len(results)} checks passed. Saved {output}", flush=True)


if __name__ == '__main__':
    main()
