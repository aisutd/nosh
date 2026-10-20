"""Index the team's cleaned recipe CSV. Run: python -m rag.build_embeddings."""
import argparse
import csv
import hashlib
import json
import re
from pathlib import Path

from rag.store import (
    COLLECTION_NAME, DEFAULT_CSV_PATH, DEFAULT_DB_PATH, MODEL_NAME,
    SCHEMA_VERSION, client_for, embedding_function, validate_collection,
)


def parse_minutes(value):
    """Return total minutes, or None for unknown/unrecognized durations."""
    value = str(value or "").strip().lower()
    pattern = r"(\d+(?:\.\d+)?)\s*(days?|hrs?|hours?|mins?|minutes?)\b"
    matches = list(re.finditer(pattern, value))
    if not matches or re.sub(r"[\s,]+", "", re.sub(pattern, "", value)):
        return None
    return sum(float(m[1]) * (1440 if m[2].startswith("day") else
                             60 if m[2].startswith(("hr", "hour")) else 1)
               for m in matches)


def load_records(csv_path):
    records = {}
    row_count = 0
    with Path(csv_path).open(encoding="utf-8", newline="") as source:
        reader = csv.DictReader(source)
        required = {"recipe_name", "ingredients", "directions", "url"}
        if not required.issubset(reader.fieldnames or []):
            raise ValueError(f"CSV must contain {sorted(required)}")
        for row_count, row in enumerate(reader, 1):
            if not all((row.get(key) or "").strip() for key in required):
                raise ValueError(f"Missing required recipe value in data row {row_count}")
            url = row["url"].strip()
            rid = hashlib.sha256(url.encode()).hexdigest()
            if rid in records:
                continue
            document = row.get("chunk") or (
                f"Recipe: {row['recipe_name']}\nIngredients: {row['ingredients']}\n"
                f"Directions: {row['directions']}"
            )
            metadata = {key: value.strip() for key, value in row.items()
                        if key != "chunk" and value and value.strip()}
            metadata["title"] = row["recipe_name"].strip()
            minutes = parse_minutes(row.get("total_time"))
            if minutes is not None:
                metadata["total_time_minutes"] = minutes
            records[rid] = (document, metadata)
    if not records:
        raise ValueError("The CSV contains no recipes")
    return records, row_count


def build_index(csv_path=DEFAULT_CSV_PATH, db_path=DEFAULT_DB_PATH,
                name=COLLECTION_NAME, batch_size=64):
    if batch_size < 1:
        raise ValueError("batch_size must be positive")
    records, row_count = load_records(csv_path)
    client = client_for(db_path)
    from chromadb.errors import NotFoundError
    try:
        existing = client.get_collection(name=name, embedding_function=None)
    except NotFoundError:
        collection = client.create_collection(
            name=name, embedding_function=embedding_function(),
            metadata={"hnsw:space": "cosine", "embedding_model": MODEL_NAME,
                      "schema_version": SCHEMA_VERSION},
        )
    else:
        validate_collection(existing)
        collection = client.get_collection(name=name, embedding_function=embedding_function())
    ids = list(records)
    batch_size = min(batch_size, client.get_max_batch_size())
    for start in range(0, len(ids), batch_size):
        batch = ids[start:start + batch_size]
        collection.upsert(ids=batch, documents=[records[i][0] for i in batch],
                          metadatas=[records[i][1] for i in batch])
        print(f"Indexed {min(start + batch_size, len(ids))}/{len(ids)}", flush=True)
    # The CSV is the source of truth. Remove stale rows only after successful upserts.
    stale = sorted(set(collection.get(include=[])["ids"]) - set(ids))
    for start in range(0, len(stale), batch_size):
        collection.delete(ids=stale[start:start + batch_size])
    return {"csv_rows": row_count, "unique_recipes": collection.count(),
            "duplicates_removed": row_count - len(records), "model": MODEL_NAME,
            "collection": name, "db_path": str(Path(db_path).resolve())}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV_PATH)
    parser.add_argument("--db-path", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--collection", default=COLLECTION_NAME)
    args = parser.parse_args()
    print(json.dumps(build_index(args.csv, args.db_path, args.collection), indent=2))


if __name__ == "__main__":
    main()
