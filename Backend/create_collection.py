from pymilvus import Collection, CollectionSchema, FieldSchema, DataType, connections, utility
import os
from dotenv import load_dotenv

load_dotenv()

def create_collection():
    connections.connect(
        alias="default",
        host=os.getenv("MILVUS_HOST", "localhost"),
        port=os.getenv("MILVUS_PORT", "19530")
    )

    # Use a new name for clarity and set the correct dimension
    collection_name = "gemini_rag_collection"

    if utility.has_collection(collection_name):
        print(f"Collection '{collection_name}' already exists.")
    else:
        fields = [
            FieldSchema(name="pk", dtype=DataType.INT64, is_primary=True, auto_id=True),
            FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=65535), # Renamed for clarity with LangChain
            FieldSchema(name="vector", dtype=DataType.FLOAT_VECTOR, dim=768) # <-- IMPORTANT: Dimension changed to 768 for Gemini
        ]

        schema = CollectionSchema(fields, description="RAG collection with Gemini Embeddings", primary_field="pk")

        collection = Collection(name=collection_name, schema=schema)
        print(f"Collection '{collection_name}' created successfully.")

        # Optional: Create an index for the vector field for faster searches
        index_params = {
            "metric_type": "L2",
            "index_type": "IVF_FLAT",
            "params": {"nlist": 128}
        }
        collection.create_index(field_name="vector", index_params=index_params)
        print("Index created successfully.")


if __name__ == "__main__":
    create_collection()