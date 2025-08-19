from pymilvus import connections

def connect_milvus(host='localhost', port='19530'):
    connections.connect(
        alias="default",
        host=host,
        port=port
    )
    print(f"Connected to Milvus at {host}:{port}")

if __name__ == "__main__":
    connect_milvus()