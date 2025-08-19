# seed_database.py

import pymongo
from bson.objectid import ObjectId
import os

# --- Configuration ---
# It's recommended to use an environment variable for the URI in a real application
MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = "fnbill_mock"

# --- Dummy Data Generation ---

# Generate consistent ObjectIds for cross-referencing
default_company_id = ObjectId()
company1_id = ObjectId()
company2_id = ObjectId()
company3_id = ObjectId()

client1_id = ObjectId()
client2_id = ObjectId()
client3_id = ObjectId()
client4_id = ObjectId()

ad1_id = ObjectId()
ad2_id = ObjectId()
ad3_id = ObjectId()
ad4_id = ObjectId()

# The first company is treated as "default" by the chat logic
companies_data = [
    {
        "_id": default_company_id,
        "name": "General Services Inc.",
        "main_address": {"street_address": "1 Global Ave", "city": "Metropolis", "state": "General State", "zip": "00000"}
    },
    {
        "_id": company1_id,
        "name": "Creative Solutions LLC",
        "main_address": {"street_address": "123 Innovation Dr", "city": "Techville", "state": "CA", "zip": "90210"}
    },
    {
        "_id": company2_id,
        "name": "Marketing Gurus Co.",
        "main_address": {"street_address": "456 Market St", "city": "AdCity", "state": "NY", "zip": "10001"}
    },
    {
        "_id": company3_id,
        "name": "Innovatech Solutions",
        "main_address": {"street_address": "789 Silicon Rd", "city": "Palo Alto", "state": "CA", "zip": "94301"}
    }
]

clients_data = [
    {
        "_id": client1_id,
        "name": "John Doe Corp",
        "address_list": [
            {"street_address": "789 Client Rd", "city": "Customer City", "state": "TX", "zip": "75001"},
            {"street_address": "101 Business Blvd", "city": "Worktown", "state": "TX", "zip": "75002"}
        ]
    },
    {
        "_id": client2_id,
        "name": "Jane Smith Enterprises",
        "address_list": [
            {"street_address": "212 Partner Pl", "city": "Collaboration Creek", "state": "FL", "zip": "33101"}
        ]
    },
    {
        "_id": client3_id,
        "name": "Global Goods Ltd.",
        "address_list": [
            {"street_address": "55 Merchant Way", "city": "London", "state": "N/A", "zip": "EC1A 1AA"},
            {"street_address": "8 International Sq", "city": "Tokyo", "state": "N/A", "zip": "100-0005"}
        ]
    },
     {
        "_id": client4_id,
        "name": "Local Bistro",
        "address_list": [
            {"street_address": "15 Main Street", "city": "Hometown", "state": "IL", "zip": "60601"}
        ]
    }
]

advertisements_data = [
    {"_id": ad1_id, "name": "Summer Sale Banner", "file": "summer_sale.jpg"},
    {"_id": ad2_id, "name": "New Product Launch Ad", "file": "new_product.png"},
    {"_id": ad3_id, "name": "Holiday Special Video", "file": "holiday_promo.mp4"},
    {"_id": ad4_id, "name": "Brand Awareness Print", "file": "brand_awareness.pdf"}
]

services_data = [
    # Services for the "default" company
    {"_id": ObjectId(), "name": "Standard Consultation", "price": 100.00, "company_id": default_company_id},
    {"_id": ObjectId(), "name": "Basic Support Package", "price": 50.00, "company_id": default_company_id},
    
    # Services for Creative Solutions LLC
    {"_id": ObjectId(), "name": "Web Design Package", "price": 1500.00, "company_id": company1_id},
    {"_id": ObjectId(), "name": "Graphic Design Logo", "price": 450.00, "company_id": company1_id},
    {"_id": ObjectId(), "name": "Full Branding Package", "price": 2500.00, "company_id": company1_id},
    
    # Services for Marketing Gurus Co.
    {"_id": ObjectId(), "name": "Social Media Campaign", "price": 2000.00, "company_id": company2_id},
    {"_id": ObjectId(), "name": "SEO Audit", "price": 750.00, "company_id": company2_id},

    # Services for Innovatech Solutions
    {"_id": ObjectId(), "name": "Cloud Migration Service", "price": 5000.00, "company_id": company3_id},
    {"_id": ObjectId(), "name": "Cybersecurity Audit", "price": 3200.00, "company_id": company3_id},
    {"_id": ObjectId(), "name": "Enterprise Software License", "price": 1200.00, "company_id": company3_id},
]

def seed_database():
    """Connects to MongoDB, clears old data, and inserts new dummy data."""
    try:
        client = pymongo.MongoClient(MONGO_URI)
        db = client[DB_NAME]
        print(f"✅ Connected to MongoDB database: '{DB_NAME}'")

        collections = {
            "companies": companies_data,
            "clients": clients_data,
            "advertisements": advertisements_data,
            "services": services_data,
            "invoices": [] # Start with an empty invoice collection
        }

        for name, data in collections.items():
            collection = db[name]
            collection.drop()
            print(f"🗑️ Dropped collection: {name}")
            if data:
                collection.insert_many(data)
                print(f"🌱 Seeded {len(data)} documents into {name}")
            else:
                print(f"텅텅 Created empty collection: {name}") # Korean for empty :)
        
        print("\n✨ Database seeding completed successfully! ✨")
        client.close()
    except pymongo.errors.ConnectionFailure as e:
        print(f"❌ Error: Could not connect to MongoDB. Please check your connection string and network access.\n{e}")
    except Exception as e:
        print(f"❌ An unexpected error occurred: {e}")

if __name__ == "__main__":
    seed_database()