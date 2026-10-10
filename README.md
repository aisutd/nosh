# NOSH

NOSH finds recipes from your available ingredients using ChromaDB, generates a
recipe with local Ollama models, and lets you ask follow-up cooking questions.
The current pipeline accepts typed ingredients. Voice is a separate prototype.

## Setup

Tested with Python 3.13. Run these commands from the project folder:

```bash
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m rag.build_embeddings
```

The recipe CSV is included. Build the local index once; rebuild it when the data
changes. The first build downloads the embedding model.

For recipe generation and chat, install and start Ollama, then download the models:

```bash
ollama pull llama3.2
ollama pull gemma2
```

## Run

Generate a recipe and ask follow-up questions (`quit` to exit):

```bash
python nosh_pipeline.py "lemon, sugar" --query "Make lemonade" --chat
```

Leave out `--chat` for a single recipe. Add `--debug` to see retrieved titles and
the judge's decision.

Search recipes without Ollama:

```bash
python -m retrieval.nosh_retrieval "coconut rice" --ingredients "basmati rice, coconut milk"
```

The main pipeline always filters by available ingredients. Direct search only
applies ingredient filtering when `--ingredients` is supplied.

## Test

```bash
python -m unittest discover -s tests -v
python -m evaluation.evaluate_retrieval
```

Tests use real Chroma retrieval with mocked model responses. To evaluate the live
Ollama models:

```bash
python -m evaluation.evaluate_guardrails
python -m evaluation.evaluate_chat
```

Evaluation reports are saved in `evaluation/results/`. They are small development
benchmarks, not guarantees of accuracy; older reports may reflect earlier code.

## Current limits

- Ingredient filtering checks presence, not quantities. Water, salt, and pepper
  are assumed available. Some ingredient descriptions may exclude valid matches.
- `--max-time` filters total preparation and cooking time.
- Dietary and budget filtering are not implemented.
- Chat explains the current recipe; it does not change ingredients or methods.

See the [retrieval and chat guide](docs/retrieval.md) or the
[voice prototype guide](docs/voice-agent.md) for more detail.
