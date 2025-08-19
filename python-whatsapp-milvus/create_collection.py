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

    collection_name = "whatsapp_collection"

    if utility.has_collection(collection_name):
        print(f"Collection '{collection_name}' already exists.")
    else:
        fields = [
            FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
            FieldSchema(name="from_number", dtype=DataType.VARCHAR, max_length=100),
            FieldSchema(name="body", dtype=DataType.VARCHAR, max_length=65535), # Increased length for safety
            FieldSchema(name="timestamp", dtype=DataType.VARCHAR, max_length=100),
            # --- IMPORTANT: Dimension changed to 768 for Gemini embeddings ---
            FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=768)
        ]

        schema = CollectionSchema(fields, description="WhatsApp Messages with Gemini Embeddings")
        collection = Collection(name=collection_name, schema=schema)
        print(f"Collection '{collection_name}' created successfully.")

if __name__ == "__main__":
    create_collection()