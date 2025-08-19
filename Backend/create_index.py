from pymilvus import Collection, connections, utility
import os
from dotenv import load_dotenv

load_dotenv()

def create_index():
    connections.connect(
        alias="default",
        host=os.getenv("MILVUS_HOST", "localhost"),
        port=os.getenv("MILVUS_PORT", "19530")
    )

    collection_name = "collection_102"

   
    if not utility.has_collection(collection_name):
        print(f"Collection '{collection_name}' does not exist. Please create it first.")
        return

    collection = Collection(name=collection_name)


    existing_indexes = collection.indexes


    if any(idx.index_name == "embedding_index" for idx in existing_indexes):
        print("Index 'embedding_index' already exists.")
        return

    index_params = {
        "index_type": "IVF_FLAT",
        "metric_type": "L2",
        "params": {"nlist": 128}
    }

    try:
       
        collection.create_index(field_name="embedding", index_params=index_params, index_name="embedding_index")
        print("Index 'embedding_index' created successfully.")
    except Exception as e:
        print(f"Failed to create index: {e}")

if __name__ == "__main__":
    create_index()
