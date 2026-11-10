# Repairing incomplete recipe imports

Run these commands from `Backend` with the project virtual environment active.
The importer reads publisher Recipe JSON-LD, including grouped ingredients and
nested instruction sections. It never asks an LLM to invent missing amounts.

Preview a source already present in the dataset:

```sh
python -m rag.source_import --url "RECIPE_SOURCE_URL"
```

Review the ingredient lines and steps in the output. To persist the import:

```sh
python -m rag.source_import --url "RECIPE_SOURCE_URL" --apply
python -m rag.build_embeddings
```

Restart the backend after indexing to clear its cached keyword index. Search again
to refresh existing recommendation cards. Saved recipes use the same stable source
URL ID and their cooking view uses the rebuilt index.

`--url` may be repeated for multiple recipes. Imports are explicit, not an automatic
crawl of the entire dataset. Failed pages are reported as `unverified` and make the
command exit nonzero; successful imports can still be applied in the same batch.
Missing, ambiguous or unsupported structured data never replaces an existing record.

## Sites that block automated downloads

If a publisher returns 403, open the original URL in your browser and save its HTML.
Use that saved page as input; it must contain the publisher's Recipe JSON-LD:

```sh
python -m rag.source_import --url "RECIPE_SOURCE_URL" --html "/path/to/saved-page.html"
python -m rag.source_import --url "RECIPE_SOURCE_URL" --html "/path/to/saved-page.html" --apply
python -m rag.build_embeddings
```

The page title must match the dataset recipe title. Review mismatches rather than
forcing an import from a possibly different recipe.

Successful imports are stored in `data/processed/source_repairs.json`, keyed by URL.
Commit that file to share repaired data. The cleaned CSV stays untouched by this
command; preprocessing and indexing both apply the saved repairs. Re-running
`python -m rag.preprocess` therefore will not restore the old truncated ingredients.
The report confirms that structured fields were imported, not that every publisher
record is complete or correct. Existing cooking validation remains in place.

## Batch repair and sharing corrections

From the top-level `Backend`, with the project environment active, preview a small
batch first (this writes a report but does not change saved repairs):

```sh
python -m rag.repair_all --limit 5
```

Import every unique source URL and persist each successful repair immediately:

```sh
python -m rag.repair_all --apply
```

Requests are sequential with a two-second delay between requests. Expect a large
batch to take a while. Ctrl+C safely stops it; rerun the same command to skip saved
repairs and retry remaining/failed sources. `--limit N` bounds the number of source
requests. `--refresh` explicitly re-fetches previously repaired sources too.
Failed refreshes preserve existing repairs. Do not run concurrent repair writers.

Review `data/processed/source_repair_report.json` for per-recipe outcomes and
failure reasons. `complete` means the dataset was traversed, not that all sources
were verified. Failed sources produce exit code 1; successful repairs still save.
The report is replaced each run, while corrections accumulate in
`data/processed/source_repairs.json`. Blocked pages can use the saved-HTML workflow
above. Title conflicts and unsupported source data need manual review; imports
cannot guarantee the publisher's own information is correct.

After reviewing the corrections:

```sh
python -m rag.build_embeddings
```

Restart the backend and reopen recipes. Commit `Backend/data/processed/source_repairs.json`
along with the batch command, tests, and documentation. The report is local review
output, not required for teammates. Teammates pull the changes, rebuild their own
index using the same command, and restart their backend. Do not commit the generated
Chroma index. Previewing alone does not produce shareable corrections.
