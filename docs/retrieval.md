# Retrieval and generation guide

Run all commands from the repository root.

## Semantic recipe retrieval

The retrieval pipeline reads `data/processed/cleaned_recipes.csv`, embeds each recipe chunk
with `all-MiniLM-L6-v2`, persists it in ChromaDB, and returns the top-k nearest
recipes by cosine distance. It runs locally without Ollama or an API key.

### Setup and build

From the repository root (tested with Python 3.13):

```bash
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m rag.build_embeddings
```

The first build downloads the embedding model if it is not cached. Subsequent
offline runs can use `HF_HUB_OFFLINE=1`. The cleaned CSV is already committed, so
running the Kaggle preprocessing script is not required.

The default database is `data/chroma_db`, resolved relative to the source file,
not the terminal's working directory. Ingestion and retrieval share the model
configuration in `rag/store.py`. The builder keeps full source chunks,
ingredients, directions, URLs, and original time strings; it also adds numeric
`total_time_minutes` when parsing is possible. Unknown times remain unknown.

There are 1,090 source rows and 961 unique recipe URLs. Stable URL-based IDs
remove duplicates. Rebuilding updates records and removes stale records from
this collection to match the supplied CSV. Do not share this collection with
other datasets. The database is ignored by Git; each teammate builds it locally.

An index created by the original script has a different schema. To preserve it,
build the new index elsewhere and pass the same location to retrieval:

```bash
python -m rag.build_embeddings --db-path data/chroma_db_v2
python -m retrieval.nosh_retrieval "lemon salmon" --db-path data/chroma_db_v2 --top-k 5
```

### Get top-k recipes

```bash
python -m retrieval.nosh_retrieval "Bake salmon with lemon in a foil packet" --top-k 5
python -m retrieval.nosh_retrieval "a fruit breakfast drink" --top-k 3 --max-time 15
```

```python
from retrieval.nosh_retrieval import search_recipes, format_recipes_for_llm

recipes = search_recipes("chicken with lemon and garlic", top_k=5)
for recipe in recipes:
    print(recipe["rank"], recipe["title"], recipe["similarity"], recipe["url"])

# Pass this source context to your generation module when ready.
context = format_recipes_for_llm(recipes, top_k=5)
```

Results contain `rank`, `id`, `title`, `document`, `ingredients`, `directions`,
`metadata`, `url`, `distance`, and `similarity`. Lower distance is better;
similarity is `1 - cosine_distance`, not a confidence probability. Semantic
order is preserved. A positive integer k is required; fewer than k results are
returned when the collection or filter has fewer matches. Empty matches return
`[]`. There is no calibrated relevance cutoff: unrelated queries can still
return recipes.

`max_time` means **total preparation and cooking time in minutes**. Unknown
times are excluded and the limit is never silently relaxed. Dietary filters raise a clear error because the source has no verified dietary
labels. Budget filtering is outside the project scope: the source has no prices
and the retrieval API has no budget parameter.

### Simple retrieval-to-LLM pipeline

```bash
python nosh_pipeline.py "salmon, lemon, garlic" --top-k 5
```

Ollama must be running with both `llama3.2` (scope/generation) and `gemma2`
(judge) available. The pipeline now checks scope, retrieves top-k recipes, sends
the best match as context, generates a source-preserving recipe once, and judges that response. It returns
`recipe` only when the judge passes; rejected answers are withheld. There are no
retry loops. Source title/URL, similarity, and all candidates remain available.

```python
from nosh_pipeline import run_nosh
result = run_nosh(["salmon", "lemon", "garlic"],
                  user_query="Make a baked fish dinner", top_k=5)
print(result["recipe"] if result["status"] == "ok" else result["message"])
```

```bash
python nosh_pipeline.py "salmon, lemon" --query "Make a baked fish dinner"
python nosh_pipeline.py "salmon, lemon" --query "Who won the football game?"
```

The second request should return exactly `not something I can search about`
without searching Chroma. Common unrelated-topic/instruction-override patterns are rejected directly, with
a model scope check for other wording. Dietary/allergy/nutrition/budget terms trigger
an unsupported-preference response because this corpus cannot verify them. These
conservative text checks are backed by the model scope check;
they are not full metadata filtering and can over-reject benign mentions.

Empty inputs and no matches skip generation. Insufficient source context produces
an explicit response instead of an invented recipe. Both generation and judge
prompts treat retrieved text and requests as untrusted data. The judge checks
source grounding, available ingredients, request constraints, unsupported claims,
and formatting. Both use Recipe Name, Changes and Steps as the three sections.
Python checks formatting first. Judge output must be valid JSON with an explicit
PASS, a nonempty explanation, and no violations; malformed/contradictory decisions
fail closed. The old substring-based PASS check is no longer used.

Pass free-form requests through `user_query`; `max_time` is still a numeric total-
time filter. `max_attempts`, `dietary`, and `budget` are not pipeline arguments.
The pipeline applies strict ingredient-presence filtering before generation. A judge PASS is a
model assessment, not a guarantee of correctness, dietary safety, or immunity to
prompt injection. Dietary metadata filtering still needs work. Budget filtering is excluded from
the current scope; price requests remain unsupported so the model does not invent costs.

### Guardrail and judge checks

```bash
python -m unittest discover -s tests -v
python -m evaluation.evaluate_guardrails
```

Unit tests mock the model responses to verify scope routing, strict verdict
parsing, formatting, rejected-output suppression, and data passed to each model.
The live evaluation uses your local models for cooking/non-cooking requests,
instruction overrides, unsupported preferences, grounded/ungrounded answers,
and one generation-to-judge example. Results are saved in
`evaluation/results/guardrail_results.json`; the initial run is retained separately for
comparison. These are development cases, not a comprehensive robustness benchmark.

### Tests and retrieval quality

```bash
python -m unittest discover -s tests -v
python -m evaluation.evaluate_retrieval
```

The integration suite builds a temporary Chroma database with the real embedding
model and tests semantic ranking, persistence, duplicate handling, rebuilds,
time filtering, empty results, validation, source context, and the generation
handoff. Scope, generation, and judging are mocked in the handoff test.

The evaluation searches the full index using 12 fixed development queries.
See [quality results](../evaluation/results/retrieval_results.md),
[full ranked results](../evaluation/results/retrieval_results.json), and
[expected recipes](../evaluation/cases/retrieval_cases.json). This is a small development
benchmark, not a held-out estimate of general accuracy. Full chunks can exceed
the embedding model's token limit, so later directions may not affect ranking;
the full text is still retained for generation. The current corpus is heavily
fruit-focused.

Chroma API references: [querying collections](https://docs.trychroma.com/docs/querying-collections/query-and-get)
and [Python client](https://docs.trychroma.com/reference/python).

### Inspect a rejected answer

Add `--debug` to print retrieved recipe titles and the judge verdict to stderr:

```bash
python nosh_pipeline.py "pork" --query "Tell me something I can make" --debug
```

Only listed ingredients plus water, salt and pepper are considered available.
Recipes missing required ingredients are excluded before generation.
The judge can still reject a generated answer for other violations. Debug output never exposes a
rejected generated answer as an approved recipe. With the model already cached,
`HF_HUB_OFFLINE=1` can be set for offline embedding loading.


### Available-ingredient filtering

The main pipeline automatically filters using the supplied ingredient list.
For direct retrieval, opt in with `available_ingredients` or `--ingredients`:

```bash
python -m retrieval.nosh_retrieval "a refreshing drink" --ingredients "lemon, sugar" --top-k 5
```

```python
recipes = search_recipes("a refreshing drink", available_ingredients=["lemon", "sugar"])
```

Filtering reads existing ingredient metadata, so no index rebuild is required.
The shared parser in `retrieval/ingredients.py` removes common quantities, units,
and preparation notes, normalizes simple plurals and a small explicit alias list,
and requires every parsed ingredient to be available. Water, salt, and black pepper
are assumed available; oil and butter are not. An empty list allows only pantry
recipes; omitting the argument leaves direct semantic search unfiltered.

The current 961-recipe index is small enough to query all candidates satisfying
any time filter, apply ingredient filtering, and take the top-k survivors in
semantic order. This avoids missing matches below an initial top-k cutoff, but
will need a more scalable approach for a much larger corpus. No matches returns
an empty list, and the pipeline skips generation.

This checks presence, not quantities, dietary safety, or substitutions. Specific
forms remain distinct (e.g. milk versus coconut milk). Unknown fragments and
optional ingredients are conservatively retained as requirements; missing metadata
is excluded. The CSV flattens ingredient entries and preparation notes into one
string, so unusual descriptions may cause false negatives. Structured ingredient
lists and a broader reviewed vocabulary are future improvements. Semantic results
still have no relevance cutoff: an ingredient-compatible recipe may not satisfy
an unrelated cooking request, which the generation/judge stages must assess.

### Conversational recipe questions

Start an in-memory cooking chat after a recipe passes validation:

```bash
python nosh_pipeline.py "lemon, sugar" --query "Make lemonade" --chat
```

Ask questions such as "What is the first step?", "How much sugar does the source
use?", and "What comes after that?". Type `quit` or `exit` to finish. Ctrl-C and
end-of-input also close the chat. A failed initial recipe does not open a chat.
Ollama must have both `llama3.2` and `gemma2` available.

```python
from cooking_session import CookingSession

session = CookingSession()
result = session.start(["lemon", "sugar"], user_query="Make lemonade")
if result["status"] == "ok":
    reply = session.ask("What is the first step?")
    print(reply["answer"] if reply["status"] == "ok" else reply["message"])
```

Each session retains the approved recipe, source context, original ingredient list
and constraints, and the last six approved question/answer pairs. Follow-ups do
not retrieve another recipe. Scope classification receives conversation context so
short references can be understood. Ordinary cooking-technique explanations (such as juicing a lemon with a fork)
may use general cooking knowledge, identified as general advice. Recipe-specific
amounts, temperatures, and timings still require source support. A dedicated
short-answer judge checks answers before they are returned or saved; the full-recipe format is not required.
Unrelated questions use `not something I can search about`. Missing source facts
produce an insufficient-information response. Failed or malformed judgments withhold
the candidate answer, and model connection failures leave the session available
for retry. Histories are isolated by session and disappear when the process ends.
Calling `start()` again clears the prior recipe and history even if the new request
fails. `run_nosh()` remains the independent, single-request API.

This version explains a fixed recipe, including tools and techniques for its steps.
Substitutions, changes to cooking methods such as baking versus frying, scaling,
and new recipe requests are refused with instructions to start a new request;
they do not modify the current recipe. Voice integration is not included. Scope
and grounding checks use models and remain fallible. Automated chat tests mock
model responses; they establish routing, context, and rejection behavior, not
real-model answer accuracy.


Reproduce live chat regression cases with `python -m evaluation.evaluate_chat`.
This uses local Ollama models with a fixed lemonade recipe to isolate conversational
behavior. It saves answers and status checks to `evaluation/results/chat_results.json`;
inspect the answers as well as the status totals. Initial generation is separate.
Ingredient names indicate presence, not a count of one. Generation preserves source
quantities unless scaling is requested, and deterministic validation rejects listing
the same ingredient as both omitted and replaced.


After ingredient filtering, initial generation presents the matching source recipe
with its original quantities and `Changes: - none`; it does not silently adapt or
scale it. The chat allows general technique guidance while keeping recipe-specific
facts grounded. A live lemonade regression run passed all eight conversational
cases plus the contradictory-change check; a separate generation check preserved
six lemons, one cup sugar, and six cups water. These are small development checks,
not a guarantee for every recipe or phrasing. See `chat_results.json` and
`chat_generation_results.json` in `evaluation/results/`.
