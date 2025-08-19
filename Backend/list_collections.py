from pymilvus import connections, utility, Collection

# Connect to Milvus server
connections.connect("default", host="localhost", port="19530")

# List all collections
collections = utility.list_collections()

print("Collections and their schemas:")
for collection_name in collections:
    # Load the collection
    collection = Collection(name=collection_name)
    # Retrieve and print the schema
    schema = collection.schema
    print(f"\nCollection: {collection_name}")
    print(f"Schema: {schema}")
