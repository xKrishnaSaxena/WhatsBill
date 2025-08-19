import os
from datetime import datetime,timedelta,timezone
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException,Request
from pydantic import BaseModel
from typing import List, Optional, Dict
# from langchain_openai import ChatOpenAI
# from langchain_openai import OpenAIEmbeddings
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_milvus import Milvus
from pymilvus import connections
from fastapi.middleware.cors import CORSMiddleware
from uuid import uuid4
from fastapi.responses import StreamingResponse, JSONResponse
import requests
from twilio.rest import Client
import re
import logging
import asyncio

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

API_BASE_URL = "http://localhost:8001/v1/api"
TWILIO_ACCOUNT_SID=os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN=os.getenv("TWILIO_AUTH_TOKEN")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    raise ValueError("GOOGLE_API_KEY not found in environment variables.")
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5000","http://0.0.0.0:5000","http://localhost:4200","http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


embedding = GoogleGenerativeAIEmbeddings(model="models/embedding-001", google_api_key=GOOGLE_API_KEY)
connections.connect(host='localhost', port='19530')
vector_store = Milvus(embedding_function=embedding, collection_name="gemini_rag_collection") # <-- Use new collection name
llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash", google_api_key=GOOGLE_API_KEY, temperature=0.9)


class Message(BaseModel):
    role: str
    content: str

class State(BaseModel):
    messages: List[Message]
    conversation_state: Optional[Dict] = {}


@app.post("/chat/")
async def chat(state: State,request: Request):
    try:
        phone_number=request.headers.get("phone-number")
        if not phone_number:
            raise HTTPException(status_code=400, detail="Phone number header is missing")
       
        phone_number = str(re.sub(r"[^\d]", "", phone_number))

        phone_number="+"+phone_number
        tone = "Friendly"
        user_message = state.messages[-1].content.strip().lower()
        conversation_state = state.conversation_state or {}
      

        now=datetime.now(timezone.utc)

        # last_interaction=conversation_state.get('last_interaction')
       
        # if last_interaction and now - datetime.fromisoformat(last_interaction) > timedelta(minutes=10):
        #     del conversation_state['invoice_creation']
        #     return {
        #         "messages": state.messages + [{
        #             "role": "assistant",
        #             "content": "The invoice creation session has timed out due to inactivity. Please start again if you wish to continue."
        #         }],
        #         "conversation_state": conversation_state
        #     }
        # print("pp")
        # conversation_state['last_interaction'] = now.isoformat()
        # print("pp22")

        response = user_intent(user_message)
        intent = response.get("intent", "no")
        if intent == "reminder":
            response = await handle_reminder(state, user_message, phone_number)
        elif conversation_state.get('invoice_creation') is None:
            if intent == "yes":
                conversation_state['invoice_creation'] = {'step': 'start', 'data': {}}
                response = await handle_invoice_creation(state, conversation_state,phone_number)
            else:
                return await handle_rag(state, tone)
        else:
            response = await handle_invoice_creation(state, conversation_state,phone_number)
        return response
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def user_intent(query):
    if "invoice" in query.lower():
        return {"intent": "yes"}
    elif "remind me" in query.lower():
        return {"intent": "reminder"}
    return {"intent": "no"}

async def handle_reminder(state: State, user_message: str, phone_number: str) -> dict:
    try:
        reminder_time, reminder_message = parse_reminder(user_message)
        if not reminder_time or not reminder_message:
            return {"messages": state.messages + [{"role": "assistant", "content": "I couldn't understand your reminder. Could you specify the time and message more clearly?"}]}
        confirmation_message = {
            "role": "assistant",
            "content": f"Reminder set for {reminder_time.strftime('%A, %B %d, %Y at %I:%M %p')} with the message: '{reminder_message}'."
        }
        state.messages.append(confirmation_message)

        asyncio.create_task(schedule_reminder(phone_number, reminder_time, reminder_message, state))

        return {"messages": state.messages, "conversation_state": state.conversation_state}


    except Exception as e:
        print(f"Error in handle_reminder: {e}")
        return {"messages": state.messages + [{"role": "assistant", "content": "Something went wrong while setting the reminder. Please try again."}]}
import json
def parse_reminder(user_message: str):
    try:
        prompt = (
            f"User query will be in natural language, and you should correctly extract the reminder time and message."
            f" Extract the reminder time and message from the following text: '{user_message}'."
            f" Provide the output in JSON format with the keys 'reminder_time' and 'reminder_message'."
            f" If the query contains relative terms like 'today,' 'tomorrow,' or 'day after tomorrow,' "
            f"calculate the exact date based on the current date (assume today is {datetime.now().strftime('%Y-%m-%d')}) "
            f"and include the time provided by the user. If the query specifies a specific date, ensure it is converted to this format: <YYYY-MM-DD HH:MM:SS>."
            f" If no time is mentioned, default to '09:00:00' on the calculated date. "
            f" If the user query is not related to datetime or a reminder, return an empty JSON object: {{}}."
        )
        response = llm.invoke(prompt)
        
        cleaned_response = response.content.strip().replace("```json", "").replace("```", "").strip()
        
        parsed_json = json.loads(cleaned_response)

        reminder_time_str = parsed_json.get('reminder_time', '').strip()
        reminder_message = parsed_json.get('reminder_message', '').strip()
        if reminder_time_str:
            reminder_time = datetime.strptime(reminder_time_str, "%Y-%m-%d %H:%M:%S")
            return reminder_time, reminder_message
        else:
            return None, None

    except Exception as e:
        print(f"Error in parse_reminder: {e}")
    return None, None

def send_twilio_reminder(phone_number: str, reminder_message: str):
    """Synchronous function to send a Twilio message."""
    try:
        account_sid = os.getenv("TWILIO_ACCOUNT_SID")
        auth_token = os.getenv("TWILIO_AUTH_TOKEN")
        client = Client(account_sid, auth_token)
        message = client.messages.create(
            from_='whatsapp:+14155238886',
            to=f"whatsapp:+{phone_number}",
            body=f"Reminder: {reminder_message}"
        )
        print(f"Reminder sent to {phone_number}: {message.sid}")
        return True
    except Exception as e:
        print(f"Error sending Twilio message: {e}")
        return False

async def schedule_reminder(phone_number: str, reminder_time: datetime, reminder_message: str, state: State):
    try:
        now = datetime.now()
        delay = (reminder_time - now).total_seconds()
        print(f"Scheduling reminder in {delay} seconds.")
        if delay > 0:
            await asyncio.sleep(delay)
        
        # Run the blocking Twilio function in a thread
        success = await asyncio.to_thread(send_twilio_reminder, phone_number, reminder_message)

        if success:
            reminder_notification = {
                "role": "assistant",
                "content": f"Reminder sent: {reminder_message}"
            }
            # Note: Modifying state like this from a background task can be tricky.
            # For a production app, you might want a more robust way to notify the user.
            state.messages.append(reminder_notification)
            
    except Exception as e:
        print(f"Error in schedule_reminder: {e}")



def tone_prompt(context, user_query, tone):
    if tone == "Formal":
        prompt = f"""
        Primary_tone: {tone}
        Context: {context}

                Question: {user_query}

        Instructions:
        1. Provide a professional, courteous response that fully addresses the question within the context.
        2. Use complete sentences and avoid contractions.
        3. If the question is not related to the context, respond with a polite phrase such as, "I'm sorry, but I don't have information on that matter."

        Answer:
        """
    elif tone == "Friendly":
        prompt = f"""
        Primary_tone: Friendly
        Context: {context}

        Question: {user_query}

        Instructions:
        1. Write a response in a warm, conversational tone, as if you're chatting with a friend.
        2. Use expressive language and engage with the user personally. Feel free to use emojis like 😊 or phrases like "Hey there!" to make it relatable.
        3. Add a touch of encouragement or positivity to the response. For instance, say "You're doing great!" or "I'm here to help!"
        4. If you don’t know the answer, be transparent but assure them of your willingness to assist further.
        5. Use light humor or relatable metaphors when appropriate to make the response enjoyable.

        Answer:
        """
    elif tone == "Concise/Direct":
        prompt = f"""
        Primary_tone: {tone}
        Context: {context}

        Question: {user_query}

        Instructions:
        1. Provide a brief, straight-to-the-point answer. Avoid extra detail unless essential to the question.
        2. Use minimal language to address the question effectively.
        3. If unrelated, simply reply, "I'm sorry, that's outside the current context."

        Answer:
        """

    elif tone == "Playful/Humorous":
        prompt = f"""
        Primary_tone: Playful/Humorous
        Context: {context}

        Question: {user_query}

        Instructions:
        1. Respond in a light-hearted, playful way, using emojis where appropriate 😊 and friendly humor.
        2. Keep the tone fun and casual, and feel free to include a little wit or a joke if it fits naturally!
        3. If the question doesn’t relate, say something like, "Oops! Looks like I don’t have the scoop on that! 🙈 But feel free to ask me anything else!"
        
        """
    elif tone == "Flirty":
        prompt = f"""
        Primary_tone: Flirty
        Context: {context}
        Question: {user_query}

        Instructions:
        1. Respond with a fun, charming tone that’s subtly flirtatious, using light-hearted compliments and playful language. 
        2. Feel free to add emojis like 😉 or 😏 to keep things casual and inviting.
        3. Keep it friendly and light; if the question isn’t relevant to the context, reply with something like, "Hmm, I’m not sure about that, but I’d love to help you with something else! 😉"

        Answer:
        """

    return prompt

def fetch_invoice_pdf_from_api(invoice_id: str, api_url: str,phone_number:str) -> str:
   
    os.makedirs("invoicesnew", exist_ok=True)

    filename = f"invoice_{invoice_id}_{uuid4().hex}_{datetime.now().strftime('%Y%m%d%H%M%S')}.pdf"
    pdf_path = os.path.join("invoicesnew", filename)

    endpoint = f"{api_url}/invoices/{invoice_id}/generate-invoice/informal"

    response = requests.get(endpoint, stream=True,headers={"phone-number": phone_number})
    
    if response.status_code == 200:
        with open(pdf_path, "wb") as pdf_file:
            for chunk in response.iter_content(chunk_size=8192):
                pdf_file.write(chunk)
        return pdf_path
    else:

        raise Exception(f"Failed to fetch the invoice PDF. Status code: {response.status_code}, Response: {response.text}")

# In main.py

def fetch_companies(phone_number):
    logger.info("Attempting to fetch companies...")
    try:
        response = requests.get(f"{API_BASE_URL}/companies", headers={"phone-number": phone_number})
        response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)
        companies = response.json().get("content", [])
        logger.info(f"Successfully fetched {len(companies)} companies.")
        return companies
    except requests.RequestException as e:
        logger.error(f"Error fetching companies: {e}", exc_info=True)
        if e.response is not None:
            logger.error(f"Response status: {e.response.status_code}, body: {e.response.text}")
        return []

def fetch_clients(phone_number):
    logger.info("Attempting to fetch clients...")
    try:
        response = requests.get(f"{API_BASE_URL}/clients", headers={"phone-number": phone_number})
        response.raise_for_status()
        clients = response.json().get("content", [])
        logger.info(f"Successfully fetched {len(clients)} clients.")
        return clients
    except requests.RequestException as e:
        logger.error(f"Error fetching clients: {e}", exc_info=True)
        if e.response is not None:
            logger.error(f"Response status: {e.response.status_code}, body: {e.response.text}")
        return []

def fetch_advertisements(phone_number):
    logger.info("Attempting to fetch advertisements...")
    try:
        response = requests.get(f"{API_BASE_URL}/advertisements", headers={"phone-number": phone_number})
        response.raise_for_status()
        advertisements = response.json().get("content", [])
        logger.info(f"Successfully fetched {len(advertisements)} advertisements.")
        return advertisements
    except requests.RequestException as e:
        logger.error(f"Error fetching advertisements: {e}", exc_info=True)
        if e.response is not None:
            logger.error(f"Response status: {e.response.status_code}, body: {e.response.text}")
        return []

def fetch_services(company_id, phone_number):
    logger.info(f"Attempting to fetch services for company_id: {company_id}")
    try:
        print("REACHED HERE")
        companies = fetch_companies(phone_number)
    
        # --- FIX: Check if companies list is empty to prevent IndexError ---
        if not companies:
            logger.warning("No companies found, cannot determine default company. Returning no services.")
            return []
        
        default_company_id = companies[0]['_id']
        print("REACHED SERVICE FETCHING")
        # Fetch services for the default company
        response2 = requests.get(f"{API_BASE_URL}/services/company/{default_company_id}", headers={"phone-number": phone_number})
        print(response2)
        response2.raise_for_status()
        services2 = response2.json().get("content", [])
        print(services2)
        for service in services2:
            service['name'] = f"{service['name']} (default)"
        
        if company_id == default_company_id:
            logger.info(f"Fetched {len(services2)} default services.")
            return services2

        # Fetch services for the selected company if it's not the default one
        response1 = requests.get(f"{API_BASE_URL}/services/company/{company_id}", headers={"phone-number": phone_number})
        response1.raise_for_status()
        services1 = response1.json().get("content", [])
        
        all_services = services1 + services2
        logger.info(f"Successfully fetched {len(all_services)} total services.")
        return all_services

    except requests.RequestException as e:
        logger.error(f"Error during API call in fetch_services: {e}", exc_info=True)
        if e.response is not None:
            logger.error(f"Response status: {e.response.status_code}, body: {e.response.text}")
        return []
    # --- FIX: Explicitly catch the potential IndexError ---
    except IndexError as e:
        logger.error(f"IndexError in fetch_services, this should not happen with the new check: {e}", exc_info=True)
        return []


def create_invoice(phone_number):
    try:
        response = requests.post(f"{API_BASE_URL}/invoices", headers={"phone-number": phone_number})
        response.raise_for_status()
        content=response.json().get("content")
        invoice_id=content.get("invoice_id") or content.get("id")
        if not invoice_id:
            print("Invoice creation response missing invoice_id or id:", response.json())
            return None
        return invoice_id
    except requests.RequestException as e:
        print(f"Error generating invoice: {e} , Response: {getattr(e,'response',None)}")
        return None

def update_invoice_company(invoice_id, company_id,phone_number):
    try:
        response = requests.patch(f"{API_BASE_URL}/invoices/{invoice_id}/company/{company_id}", headers={"phone-number": phone_number})
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"Error updating invoice with company: {e}")

def update_invoice_advertisement(invoice_id, advertisement_id,phone_number):
    try:
        response = requests.patch(f"{API_BASE_URL}/invoices/{invoice_id}/advertisement/{advertisement_id}", headers={"phone-number": phone_number})
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"Error updating invoice with advertisement: {e}")

def update_invoice_service(invoice_id, service_id, quantity,phone_number):
    try:
        response = requests.patch(
            f"{API_BASE_URL}/invoices/{invoice_id}/service/{service_id}", 
            headers={"phone-number": phone_number},
            json={"content": {"quantity": quantity}}
        )
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"Error updating invoice with service: {e}")

def update_invoice_address(invoice_id, billing_address, shipping_address,phone_number):
    try:
        response = requests.patch(
            f"{API_BASE_URL}/invoices/{invoice_id}", 
            headers={"phone-number": phone_number},
            json={"content": {"billing_address": billing_address, "shipping_address": shipping_address},"state":0}
        )
        response.raise_for_status()
        
    except requests.RequestException as e:
        print(f"Error updating invoice address: {e}")

def update_state(invoice_id,phone_number):
    try:
        response = requests.patch(
            f"{API_BASE_URL}/invoices/{invoice_id}", 
            headers={"phone-number": phone_number},
            json={"content": {"state":0}}
        )
        response.raise_for_status()
        
    except requests.RequestException as e:
        print(f"Error updating invoice address: {e}")

def update_invoice_taxes_cgst(invoice_id, cgst,phone_number):
    try:
        response = requests.patch(
            f"{API_BASE_URL}/invoices/{invoice_id}/taxes", 
            headers={"phone-number": phone_number},
            json={"content": {"name": "CGST", "percentage": cgst}}
        )
        response.raise_for_status()
        
    except requests.RequestException as e:
        print(f"Error updating invoice taxes: {e}")

def update_invoice_taxes_sgst(invoice_id, sgst,phone_number):
    try:
        response = requests.patch(
            f"{API_BASE_URL}/invoices/{invoice_id}/taxes", 
            headers={"phone-number": phone_number},
            json={"content": {"name": "SGST", "percentage": sgst}}
        )
        response.raise_for_status()
        
    except requests.RequestException as e:
        print(f"Error updating invoice taxes: {e}")

def add_human_touch(response):
    response = response.replace("I am", "I'm").replace("do not", "don't")
    response += " 😊" if not response.endswith("!") else " 😉"
    return response


async def handle_rag(state: State,tone:str) -> dict:
    user_query = state.messages[-1].content
    retrieved_docs = await asyncio.to_thread(
        vector_store.similarity_search, user_query
    )
    context = "\n\n".join([doc.page_content for doc in retrieved_docs])    
    tone = "Formal"
    prompt = tone_prompt(context, user_query, tone)
    response = await llm.ainvoke(prompt)
    response_content = response.content
    response_content = add_human_touch(response_content)
    ai_message = {"role": "assistant", "content": response_content}
    new_messages = state.messages + [ai_message]
    return {"messages": new_messages, "conversation_state": state.conversation_state}

async def handle_invoice_creation(state: State, conversation_state: Dict,phone_number:str) -> dict:
    step = conversation_state['invoice_creation']['step']
    data = conversation_state['invoice_creation']['data']
    logger.info(f"--- Handling Invoice Creation --- Step: {step} ---")

    if step == 'start':
        companies = fetch_companies(phone_number)
        if companies:
            companies[0]['name'] = "Do not choose a company"
            data['available_companies'] = {str(index + 1): company for index, company in enumerate(companies)}
            
            company_list = "\n".join([f"{index}. {company['name']}" for index, company in data['available_companies'].items()])
            ai_message = {
                "role": "assistant",
                "content": f"Please select a company by entering the corresponding number:\n{company_list}"
            }
            conversation_state['invoice_creation']['step'] = 'select_company'
        else:
            ai_message = {
                "role": "assistant",
                "content": "No existing companies found. Please visit fnBill website to create a company, then come back and select it from the list."
            }
            conversation_state['invoice_creation']['step'] = 'company_selection_await'
    elif step == 'select_company':
        company_id = state.messages[-1].content.strip()
        print(company_id)
        print(data['available_companies'])
        if company_id in data['available_companies']:
            company = data['available_companies'][company_id]
            print(company)
            data.update({
                'company_id': company['_id'],
                'company_name': company['name'],
                'street_address_company': company['main_address']['street_address'],
                'shipping_address_company': company['main_address'],
                'billing_address_company': company['main_address'],
                'city': company['main_address']['city'],
                'state': company['main_address']['state'],
                'zip_code': company['main_address']['zip'],
                'selected_services': [] 
            })
            print("REACHED HERE")
            services = fetch_services(data['company_id'],phone_number)
            print(services)
            if services:
                data['available_services'] = {str(index + 1): service for index, service in enumerate(services)}
                service_list = "\n".join([f"{index}. {service['name']} - ₹{service['price']}" for index, service in data['available_services'].items()])
                ai_message = {
                    "role": "assistant",
                    "content": f"Select a service by entering the corresponding number:\n{service_list}"
                }
                conversation_state['invoice_creation']['step'] = 'select_service'
            else:
                ai_message = {"role": "assistant", "content": "No services available for this company."}
        else:
            ai_message = {"role": "assistant", "content": "Invalid company ID. Try again."}
    elif step == 'select_service':
        service_id = state.messages[-1].content.strip()
        if service_id in data['available_services']:
            service = data['available_services'][service_id]
            data['current_service']={
                'service_id': service['_id'],
                'service_name': service['name'],
                'price': service['price']
            }
            ai_message = {"role": "assistant", "content": "Enter the quantity of this service:"}
            conversation_state['invoice_creation']['step'] = 'collect_quantity'
        else:
            ai_message = {"role": "assistant", "content": "Invalid service ID. Try again."}
    elif step == 'collect_quantity':
        try:
            quantity = int(state.messages[-1].content)
            current_service = data.pop('current_service')
            current_service['quantity'] = quantity
            current_service['total_price'] = quantity * current_service['price']
            data['selected_services'].append(current_service)
            ai_message = {
                "role": "assistant",
                "content": "Do you want to add more services? (yes/no)"
            }
            conversation_state['invoice_creation']['step'] = 'add_more_services'
        except ValueError:
            ai_message = {"role": "assistant", "content": "Please enter a valid quantity."}

    elif step == 'add_more_services':
        user_response = state.messages[-1].content.strip().lower()
        if user_response == 'yes':
            service_list = "\n".join([f"{index}. {service['name']} - ₹{service['price']}" for index, service in data['available_services'].items()])
            ai_message = {
                "role": "assistant",
                "content": f"Select another service by entering the corresponding number:\n{service_list}"
            }
            conversation_state['invoice_creation']['step'] ='select_service'
        elif user_response == 'no':
            total_service_amount = sum(service['total_price'] for service in data['selected_services'])
            cgst_percentage, sgst_percentage = 9, 9
            total_amount = total_service_amount * (1 + (cgst_percentage + sgst_percentage) / 100)

            data.update({
                'total_service_amount': total_service_amount,
                'total_amount': total_amount
            })

            advertisements = fetch_advertisements(phone_number)
            print(advertisements)
            if advertisements:
                data['available_advertisements'] = {str(index + 1): advertisement for index, advertisement in enumerate(advertisements)}
                advertisement_list = "\n".join([f"{index}. {advertisement['name']}" for index, advertisement in data['available_advertisements'].items()])
                print(data['available_advertisements'])
                ai_message = {
                    "role": "assistant",
                    "content": f"Select an advertisement by entering the corresponding number:\n{advertisement_list}"
                }
                conversation_state['invoice_creation']['step'] = 'select_advertisement'
            else:
                ai_message = {"role": "assistant", "content": "No advertisements available."}
    elif step == 'select_advertisement':
        advertisement_id = state.messages[-1].content.strip()
        if advertisement_id in data['available_advertisements']:
            advertisement = data['available_advertisements'][advertisement_id]
            
            data.update({
                'advertisement_id': advertisement['_id'],
                'advertisement_image': f"{API_BASE_URL}/files/{advertisement['file']}"
            })

            clients=fetch_clients(phone_number)
            if clients:
                data['available_clients'] = {str(index + 1): client for index, client in enumerate(clients)}
                client_list = "\n".join([f"{index}. {client['name']}" for index, client in data['available_clients'].items()])
                ai_message = {
                    "role": "assistant",
                    "content": f"Select a client by entering the corresponding number:\n{client_list}"
                }
                conversation_state['invoice_creation']['step'] = 'select_client'
            else:
                ai_message = {"role": "assistant", "content": "No clients available."}
        else:
            ai_message = {"role": "assistant", "content": "Invalid advertisement ID. Try again."}

    elif step == 'select_client':
        client_id = state.messages[-1].content.strip()
        if client_id in data['available_clients']:
            client = data['available_clients'][client_id]
            data.update({
                'client_id': client['_id'],
                'client_name': client['name'],
                'client_addresses': client['address_list']
            })
            if data['client_addresses']:
                address_list = "\n".join([
                    f"{index + 1}. {address['street_address']}, {address['city']}, {address['state']} - {address['zip']}"
                    for index, address in enumerate(data['client_addresses'])
                ])
                ai_message = {
                    "role": "assistant",
                    "content": f"Select a shipping address by entering the corresponding number:\n{address_list}"
                }
                conversation_state['invoice_creation']['step'] = 'select_shipping_address'
            else:
                ai_message = {"role": "assistant", "content": "No addresses available for the selected client."}

        else:
            ai_message = {"role": "assistant", "content": "Invalid client ID. Try again."}

    elif step == 'select_shipping_address':
        address_index = state.messages[-1].content.strip()
        try:
            address_index = int(address_index)-1
            shipping_address = data['client_addresses'][address_index]
            data['shipping_address'] = shipping_address
            address_list = "\n".join([
                f"{index + 1}. {address['street_address']}, {address['city']}, {address['state']} - {address['zip']}"
                for index, address in enumerate(data['client_addresses'])
            ])
            ai_message = {
                "role": "assistant",
                "content": f"Select a billing address by entering the corresponding number:\n{address_list}"
            }
            conversation_state['invoice_creation']['step'] = 'select_billing_address'
        except (ValueError, IndexError):
            ai_message = {"role": "assistant", "content": "Invalid selection. Try again."}
    elif step == 'select_billing_address':
        address_index = state.messages[-1].content.strip()
        try:
            address_index = int(address_index) - 1
            billing_address = data['client_addresses'][address_index]
            data['billing_address'] = billing_address
            ai_message = {
                "role": "assistant",
                "content": f"The total amount is ₹{data['total_amount']}. Confirm the invoice by typing 'confirm' or 'cancel' to abort."
            }
            conversation_state['invoice_creation']['step'] = 'confirm_creation'
        except (ValueError, IndexError):
            ai_message = {"role": "assistant", "content": "Invalid selection. Try again."}
    elif step == 'confirm_creation':
        user_input = state.messages[-1].content.strip().lower()
        if user_input == 'confirm':
            invoice_id = create_invoice(phone_number)
            if invoice_id:
                update_invoice_company(invoice_id, data['company_id'],phone_number)
                for service in data['selected_services']:
                    update_invoice_service(invoice_id, service['service_id'], service['quantity'], phone_number)
                update_invoice_address(invoice_id, data['billing_address'], data['shipping_address'],phone_number)
                update_invoice_advertisement(invoice_id, data['advertisement_id'],phone_number)
                update_invoice_taxes_cgst(invoice_id, 9,phone_number)
                update_invoice_taxes_sgst(invoice_id, 9,phone_number)
                update_state(invoice_id,phone_number)
                pdf_path = fetch_invoice_pdf_from_api(invoice_id, API_BASE_URL,phone_number)
                del conversation_state['invoice_creation'] 
                if os.path.exists(pdf_path):
                    print(f"PDF created successfully: {pdf_path}")
                else:
                    del conversation_state['invoice_creation'] 
                    print("PDF creation failed.")

                return StreamingResponse(open(pdf_path, "rb"), media_type="application/pdf", headers={
                        "Content-Disposition": f"attachment; filename=invoice_{uuid4().hex}.pdf"
                    })
            else:
                del conversation_state['invoice_creation'] 
                return JSONResponse(status_code=500, content={"message": "Error creating the invoice."})
        elif user_input == 'cancel':
            ai_message = {"role": "assistant", "content": "Invoice creation canceled."}
            del conversation_state['invoice_creation']
        else:
            ai_message = {"role": "assistant", "content": "Please type 'confirm' or 'cancel'."}
    new_messages = state.messages + [ai_message]
    return {"messages": new_messages, "conversation_state": conversation_state}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
