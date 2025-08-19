from pymilvus import Collection, CollectionSchema, FieldSchema, DataType, connections, utility
from pymilvus.orm.index import Index
import os
from dotenv import load_dotenv

load_dotenv()

def create_collection():
    
    connections.connect(
        alias="default",
        host=os.getenv("MILVUS_HOST", "localhost"),
        port=os.getenv("MILVUS_PORT", "19530")
    )

    collection_name = "rag_collection4"

    if utility.has_collection(collection_name):
        print(f"Collection '{collection_name}' already exists.")
    else:
        fields = [
            FieldSchema(
                name="text",
                dtype=DataType.VARCHAR,
                max_length=65535, 
                description="Text field"
            ),
            FieldSchema(
                name="pk",
                dtype=DataType.INT64,
                is_primary=True,
                auto_id=True,
                description="Primary key"
            ),
            FieldSchema(
                name="vector",
                dtype=DataType.FLOAT_VECTOR,
                dim=1536,
                description="Vector embeddings"
            )
        ]

        schema = CollectionSchema(
            fields=fields,
            description="Collection for RAG-related data"
        )

        collection = Collection(name=collection_name, schema=schema)
        print(f"Collection '{collection_name}' created successfully.")

        index_params = {
            "metric_type": "L2", 
            "index_type": "IVF_FLAT",  
            "params": {"nlist": 128}  
        }
        index = Index(collection, field_name="vector", index_params=index_params)
        print(f"Index created successfully for collection '{collection_name}'.")

if __name__ == "__main__":
    create_collection()





