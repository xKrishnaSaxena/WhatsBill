from fastapi import FastAPI, HTTPException, Header
from fastapi.responses import StreamingResponse
from typing import List, Dict, Optional
from database import get_db
from models import Company, Client, Advertisement, Service, Invoice
from bson import ObjectId
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
import io
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import Table, TableStyle
from datetime import datetime

app = FastAPI(title="fnBill Mock API")
db = get_db()

# A helper to serialize MongoDB documents
def serialize_doc(doc):
    doc["id"] = str(doc["_id"])
    # Convert any other ObjectIds
    for key, value in doc.items():
        if isinstance(value, ObjectId):
            doc[key] = str(value)
    del doc["_id"]
    return doc

@app.get("/v1/api/companies", response_model=Dict[str, List[Company]])
async def fetch_companies(phone_number: Optional[str] = Header(None)):
    companies = [doc for doc in db.companies.find()]
    return {"content": companies}

@app.get("/v1/api/clients", response_model=Dict[str, List[Client]])
async def fetch_clients(phone_number: Optional[str] = Header(None)):
    clients = [doc for doc in db.clients.find()]
    return {"content": clients}

@app.get("/v1/api/advertisements", response_model=Dict[str, List[Advertisement]])
async def fetch_advertisements(phone_number: Optional[str] = Header(None)):
    advertisements = [doc for doc in db.advertisements.find()]
    return {"content": advertisements}

@app.get("/v1/api/services/company/{company_id}", response_model=Dict[str, List[Service]])
async def fetch_services(company_id: str, phone_number: Optional[str] = Header(None)):
    # Find the "default" company (hardcoded as the first one for this mock)
    default_company = db.companies.find_one()
    if not default_company:
        raise HTTPException(status_code=404, detail="Default company not found")
    print(default_company)
    default_company_id = default_company['_id']
    print(default_company_id)
    # Fetch services for the specified company
    services1 = list(db.services.find({"company_id": ObjectId(company_id)}))
    print(services1)
    # Fetch services for the default company, avoiding duplicates
    services2 = []
    if ObjectId(company_id) != default_company_id:
        services2 = list(db.services.find({"company_id": default_company_id}))

    all_services = services1 + services2
    return {"content": all_services}

@app.post("/v1/api/invoices")
async def create_invoice(phone_number: Optional[str] = Header(None)):
    new_invoice = db.invoices.insert_one({})
    return {"content": {"id": str(new_invoice.inserted_id)}}

@app.patch("/v1/api/invoices/{invoice_id}/company/{company_id}")
async def update_invoice_company(invoice_id: str, company_id: str, phone_number: Optional[str] = Header(None)):
    db.invoices.update_one({"_id": ObjectId(invoice_id)}, {"$set": {"company_id": ObjectId(company_id)}})
    return {"status": "success"}

@app.patch("/v1/api/invoices/{invoice_id}/advertisement/{advertisement_id}")
async def update_invoice_advertisement(invoice_id: str, advertisement_id: str, phone_number: Optional[str] = Header(None)):
    db.invoices.update_one({"_id": ObjectId(invoice_id)}, {"$set": {"advertisement_id": ObjectId(advertisement_id)}})
    return {"status": "success"}

@app.patch("/v1/api/invoices/{invoice_id}/service/{service_id}")
async def update_invoice_service(invoice_id: str, service_id: str, body: Dict, phone_number: Optional[str] = Header(None)):
    quantity = body.get("content", {}).get("quantity", 1)
    db.invoices.update_one(
        {"_id": ObjectId(invoice_id)},
        {"$push": {"services": {"service_id": ObjectId(service_id), "quantity": quantity}}}
    )
    return {"status": "success"}

@app.patch("/v1/api/invoices/{invoice_id}")
async def update_invoice_details(invoice_id: str, body: Dict, phone_number: Optional[str] = Header(None)):
    update_data = body.get("content", {})
    state = body.get("state")
    
    update_payload = {}
    if "billing_address" in update_data:
        update_payload["billing_address"] = update_data["billing_address"]
    if "shipping_address" in update_data:
        update_payload["shipping_address"] = update_data["shipping_address"]
    if state is not None:
        update_payload["state"] = state
        
    db.invoices.update_one({"_id": ObjectId(invoice_id)}, {"$set": update_payload})
    return {"status": "success"}

@app.patch("/v1/api/invoices/{invoice_id}/taxes")
async def update_invoice_taxes(invoice_id: str, body: Dict, phone_number: Optional[str] = Header(None)):
    tax_data = body.get("content", {})
    db.invoices.update_one({"_id": ObjectId(invoice_id)}, {"$push": {"taxes": tax_data}})
    return {"status": "success"}

@app.get("/v1/api/invoices/{invoice_id}/generate-invoice/informal")
async def generate_invoice_pdf(invoice_id: str, phone_number: Optional[str] = Header(None)):
    """
    Generates a detailed and beautifully formatted PDF for the given invoice ID.
    """
    # 1. Fetch all necessary data from the database
    invoice_data = db.invoices.find_one({"_id": ObjectId(invoice_id)})
    if not invoice_data:
        raise HTTPException(status_code=404, detail="Invoice not found")

    # Fetch company details
    company_id = invoice_data.get("company_id")
    company_data = db.companies.find_one({"_id": ObjectId(company_id)}) if company_id else {}
    if not company_data:
        raise HTTPException(status_code=404, detail="Company details not found for this invoice")
        
    # Note: Client Name is not stored in the invoice document in the current flow.
    # We will proceed using the stored billing/shipping addresses.

    # Fetch service details and calculate subtotal
    services_in_invoice = []
    subtotal = 0
    if "services" in invoice_data:
        for item in invoice_data["services"]:
            service_doc = db.services.find_one({"_id": ObjectId(item["service_id"])})
            if service_doc:
                quantity = item.get("quantity", 1)
                price = service_doc.get("price", 0)
                amount = quantity * price
                subtotal += amount
                services_in_invoice.append({
                    "name": service_doc.get("name", "N/A"),
                    "quantity": quantity,
                    "price": f"₹{price:,.2f}",
                    "amount": f"₹{amount:,.2f}"
                })

    # 2. Setup the PDF document
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter

    # Helper function for address formatting
    def format_address(address_dict):
        if not isinstance(address_dict, dict):
            return ["Address not available"]
        # Filter out empty or None values before joining
        parts = [
            address_dict.get("street_address"),
            f"{address_dict.get('city', '')}, {address_dict.get('state', '')} {address_dict.get('zip', '')}".strip(", "),
            address_dict.get("country")
        ]
        return [part for part in parts if part]

    # 3. Start drawing the invoice content
    
    # --- Header ---
    p.setFont("Helvetica-Bold", 24)
    p.setFillColor(colors.darkblue)
    p.drawString(0.75 * inch, height - 1 * inch, "INVOICE")

    company_name = company_data.get("name", "Company Name Not Found")
    company_address_lines = format_address(company_data.get("main_address", {}))
    
    p.setFont("Helvetica-Bold", 12)
    p.setFillColor(colors.black)
    p.drawRightString(width - 0.75 * inch, height - 1 * inch, company_name)
    p.setFont("Helvetica", 10)
    
    y_pos = height - 1.2 * inch
    for line in company_address_lines:
        p.drawRightString(width - 0.75 * inch, y_pos, line)
        y_pos -= 0.18 * inch

    # --- Invoice Details & Addresses ---
    p.setStrokeColor(colors.grey)
    p.line(0.75 * inch, height - 1.8 * inch, width - 0.75 * inch, height - 1.8 * inch)

    y_pos_addr = height - 2.1 * inch
    
    # Bill To Address
    p.setFont("Helvetica-Bold", 10)
    p.drawString(0.75 * inch, y_pos_addr, "BILL TO")
    p.setFont("Helvetica", 10)
    billing_address_lines = format_address(invoice_data.get("billing_address", {}))
    y_pos_bill = y_pos_addr - 0.2 * inch
    for line in billing_address_lines:
        p.drawString(0.75 * inch, y_pos_bill, line)
        y_pos_bill -= 0.18 * inch

    # Shipping To Address (if different)
    shipping_address = invoice_data.get("shipping_address")
    billing_address = invoice_data.get("billing_address")
    if shipping_address != billing_address:
        p.setFont("Helvetica-Bold", 10)
        p.drawString(3.0 * inch, y_pos_addr, "SHIP TO")
        p.setFont("Helvetica", 10)
        shipping_address_lines = format_address(shipping_address)
        y_pos_ship = y_pos_addr - 0.2 * inch
        for line in shipping_address_lines:
            p.drawString(3.0 * inch, y_pos_ship, line)
            y_pos_ship -= 0.18 * inch
    
    # Invoice Number and Date
    invoice_date = ObjectId(invoice_id).generation_time.strftime("%B %d, %Y")
    p.drawRightString(width - 0.75 * inch, y_pos_addr, f"Invoice #: {invoice_id}")
    p.drawRightString(width - 0.75 * inch, y_pos_addr - 0.2 * inch, f"Date: {invoice_date}")

    # --- Services/Items Table ---
    table_y_start = y_pos_bill - 0.5 * inch
    
    table_header = [["ITEM DESCRIPTION", "QTY", "RATE", "AMOUNT"]]
    table_data = [[s["name"], s["quantity"], s["price"], s["amount"]] for s in services_in_invoice]
    
    full_table_data = table_header + table_data
    
    item_table = Table(full_table_data, colWidths=[3.5 * inch, 0.75 * inch, 1.25 * inch, 1.5 * inch])
    item_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('ALIGN', (0, 1), (0, -1), 'LEFT'), # Align item description to the left
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0,1), (0,-1), 10),
        ('RIGHTPADDING', (-1,1), (-1,-1), 10),
        ('ALIGN', (-1,1), (-1,-1), 'RIGHT'), # Align amount to the right
        ('ALIGN', (-2,1), (-2,-1), 'RIGHT'), # Align rate to the right
    ]))

    w, h = item_table.wrapOn(p, width, height)
    item_table.drawOn(p, 0.75 * inch, table_y_start - h)
    
    # --- Totals Section ---
    y_pos_totals = table_y_start - h - 0.4 * inch
    total_due = subtotal
    
    p.drawRightString(width - 2.5 * inch, y_pos_totals, "Subtotal:")
    p.drawRightString(width - 0.75 * inch, y_pos_totals, f"₹{subtotal:,.2f}")
    y_pos_totals -= 0.25 * inch

    if "taxes" in invoice_data:
        for tax in invoice_data["taxes"]:
            tax_name = tax.get("name", "Tax")
            tax_percentage = tax.get("percentage", 0)
            tax_amount = subtotal * (tax_percentage / 100)
            total_due += tax_amount
            p.drawRightString(width - 2.5 * inch, y_pos_totals, f"{tax_name} ({tax_percentage}%):")
            p.drawRightString(width - 0.75 * inch, y_pos_totals, f"₹{tax_amount:,.2f}")
            y_pos_totals -= 0.25 * inch

    p.setLineWidth(2)
    p.line(width - 3.0 * inch, y_pos_totals, width - 0.75 * inch, y_pos_totals)
    y_pos_totals -= 0.1 * inch

    p.setFont("Helvetica-Bold", 12)
    p.drawRightString(width - 2.5 * inch, y_pos_totals - 0.2 * inch, "TOTAL DUE:")
    p.drawRightString(width - 0.75 * inch, y_pos_totals - 0.2 * inch, f"₹{total_due:,.2f}")

    # --- Footer ---
    p.setFont("Helvetica-Oblique", 9)
    p.setFillColor(colors.grey)
    p.drawCentredString(width / 2.0, 0.75 * inch, "Thank you for your business!")

    # 4. Save the PDF and return
    p.showPage()
    p.save()
    buffer.seek(0)

    return StreamingResponse(buffer, media_type="application/pdf", headers={
        "Content-Disposition": f"attachment; filename=invoice_{invoice_id}.pdf"
    })

if __name__ == "__main__":
    import uvicorn
    # Use port 8001 to avoid conflict with the chat app at 8000
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=True)