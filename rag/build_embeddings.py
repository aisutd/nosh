import pandas as pd
import chromadb
from chromadb.utils import embedding_functions


# Load new recipes
df = pd.read_csv("cleaned_recipes.csv")

print("Recipes loaded:", len(df))


# Create ChromaDB database
client = chromadb.PersistentClient(path="./chroma_db")


# Create embeddings using all-MiniLM-L6-v2
embed_func = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name="all-MiniLM-L6-v2"
)


# Get or create collection
collection = client.get_or_create_collection(
    name="recipes",
    embedding_function=embed_func
)


# Create unique IDs for each recipe
ids = [str(i) for i in range(len(df))]


# Recipe chunks that will be embedded
documents = df["chunk"].tolist()


# Metadata for each recipe
metadatas = []

for _, row in df.iterrows():
    metadatas.append({
        "recipe_name": str(row["recipe_name"]),
        "prep_time": str(row["prep_time"]),
        "cook_time": str(row["cook_time"]),
        "total_time": str(row["total_time"]),
        "servings": int(row["servings"]),
        "yield": str(row["yield"]),
        "rating": float(row["rating"]),
        "url": str(row["url"]),
        "cuisine_path": str(row["cuisine_path"]),
        "nutrition": str(row["nutrition"]),
        "timing": str(row["timing"]),
        "img_src": str(row["img_src"])
    })


# Add recipes to ChromaDB and ChromaDB creates embeddings
collection.upsert(
    ids=ids,
    documents=documents,
    metadatas=metadatas
)


print("Recipes stored:", collection.count())
result = collection.get(ids=["0"])
print(result)