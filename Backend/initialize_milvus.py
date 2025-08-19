import os
from dotenv import load_dotenv
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_milvus import Milvus
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain.docstore.document import Document
from pymilvus import connections
import getpass # Import getpass for securely entering API key

load_dotenv()

# Securely get the API key if not set in the environment
if "GOOGLE_API_KEY" not in os.environ:
    os.environ["GOOGLE_API_KEY"] = getpass.getpass("Enter your Google API key: ")

def load_documents(file_path):
    with open(file_path, 'r') as file:
        content = file.read()
    return content

file_path = 'fnmoney.txt'
document_text = load_documents(file_path)

docs = [Document(page_content=document_text)]

# Correctly initialize the Google embedding model
embedding = GoogleGenerativeAIEmbeddings(model="models/embedding-001")

text_splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(chunk_size=500, chunk_overlap=0)
split_docs = text_splitter.split_documents(docs)

connections.connect(host='localhost', port='19530')

# Use the new collection name
vector_store = Milvus.from_documents(
    documents=split_docs,
    collection_name="gemini_rag_collection", # <-- IMPORTANT: Use the new collection name
    embedding=embedding,
)

print("Documents have been successfully embedded and stored in Milvus.")