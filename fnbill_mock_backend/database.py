import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = "fnbill_mock"

client = MongoClient(MONGO_URI)
db = client[DB_NAME]

def get_db():
    return db