"""Shared index settings: ingestion and queries must use the same model."""
from functools import lru_cache
from pathlib import Path

RAG_DIR = Path(__file__).resolve().parent
PROJECT_DIR = RAG_DIR.parent
DATA_DIR = PROJECT_DIR / "data"
DEFAULT_DB_PATH = DATA_DIR / "chroma_db"
DEFAULT_CSV_PATH = DATA_DIR / "processed" / "cleaned_recipes.csv"
COLLECTION_NAME = "recipes"
MODEL_NAME = "all-MiniLM-L6-v2"
SCHEMA_VERSION = 2


@lru_cache(maxsize=1)
def embedding_function():
    from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
    return SentenceTransformerEmbeddingFunction(
        model_name=MODEL_NAME, device="cpu", normalize_embeddings=True
    )


def client_for(path=DEFAULT_DB_PATH):
    import chromadb
    return chromadb.PersistentClient(path=str(Path(path).expanduser().resolve()))


def validate_collection(collection):
    metadata = collection.metadata or {}
    if (metadata.get("schema_version") != SCHEMA_VERSION
            or metadata.get("embedding_model") != MODEL_NAME
            or metadata.get("hnsw:space") != "cosine"):
        raise ValueError(
            "This collection uses an older or incompatible index. Build into a new "
            "database with `python -m rag.build_embeddings --db-path PATH`, "
            "then use that same --db-path for retrieval."
        )
