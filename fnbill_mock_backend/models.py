# models.py

from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional
from bson import ObjectId

# This helper class is essential for Pydantic to handle MongoDB's ObjectId
class PyObjectId(ObjectId):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v, *args, **kwargs):
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid ObjectId")
        return ObjectId(v)
    
    @classmethod
    def __get_pydantic_json_schema__(cls, schema, handler):
        # Update the schema to represent ObjectId as a string in OpenAPI/JSON Schema
        schema.update(type="string", example="612345678901234567890123")
        return schema

# --- Configuration for all models ---
# This config allows models to use MongoDB's '_id' field and encode ObjectId to string
model_config = ConfigDict(
    arbitrary_types_allowed=True,
    json_encoders={ObjectId: str},
    populate_by_name=True, # Allows using 'alias' field names for population
)

# --- Sub-document Models ---
class Address(BaseModel):
    street_address: str
    city: str
    state: str
    zip: str

class InvoiceServiceItem(BaseModel):
    """Represents a service line item within an invoice."""
    service_id: PyObjectId
    quantity: int

class InvoiceTaxItem(BaseModel):
    """Represents a tax line item within an invoice."""
    name: str
    percentage: float

# --- Main Document Models (for API responses and database interaction) ---
class Company(BaseModel):
    id: PyObjectId = Field(alias="_id")
    name: str
    main_address: Address
    model_config = model_config

class Client(BaseModel):
    id: PyObjectId = Field(alias="_id")
    name: str
    address_list: List[Address]
    model_config = model_config

class Advertisement(BaseModel):
    id: PyObjectId = Field(alias="_id")
    name: str
    file: str  # Stores the filename, e.g., 'summer_sale.jpg'
    model_config = model_config

class Service(BaseModel):
    id: PyObjectId = Field(alias="_id")
    name: str
    price: float
    company_id: PyObjectId
    model_config = model_config

class Invoice(BaseModel):
    id: PyObjectId = Field(alias="_id")
    # Links to other collections
    company_id: Optional[PyObjectId] = None
    client_id: Optional[PyObjectId] = None
    advertisement_id: Optional[PyObjectId] = None
    # Embedded data for the invoice itself
    services: List[InvoiceServiceItem] = []
    taxes: List[InvoiceTaxItem] = []
    billing_address: Optional[Address] = None
    shipping_address: Optional[Address] = None
    # Metadata
    state: Optional[int] = None
    model_config = model_config