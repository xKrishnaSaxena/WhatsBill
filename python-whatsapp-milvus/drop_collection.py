from pymilvus import utility, connections

# Connect to Milvus
connections.connect("default", host="localhost", port="19530")

collection_name = "whatsapp_collection"

if utility.has_collection(collection_name):
    utility.drop_collection(collection_name)
    print(f"Collection '{collection_name}' dropped successfully.")
else:
    print(f"Collection '{collection_name}' does not exist.")