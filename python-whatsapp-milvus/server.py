from flask import Flask, request, Response, url_for
from twilio.twiml.messaging_response import MessagingResponse
from pymilvus import Collection, connections
import os
from dotenv import load_dotenv
from embedding import get_embedding # <-- This now uses Gemini
import requests
from datetime import datetime, timezone
from uuid import uuid4
from twilio.rest import Client
from threading import Thread
import time
import google.generativeai as genai # <-- Import Google's SDK
from pydub import AudioSegment
from requests.auth import HTTPBasicAuth

load_dotenv()

app = Flask(__name__)

# --- Milvus Connection ---
connections.connect(
    alias="default",
    host=os.getenv("MILVUS_HOST", "localhost"),
    port=os.getenv("MILVUS_PORT", "19530")
)

# --- API Keys and Configuration ---
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY") # <-- Use Google API Key
FASTAPI_URL = os.getenv("FASTAPI_URL", "http://0.0.0.0:8000/chat/")

if not GOOGLE_API_KEY:
    raise ValueError("GOOGLE_API_KEY not found in environment variables.")

# --- Configure Gemini ---
genai.configure(api_key=GOOGLE_API_KEY)

# --- Milvus Collection ---
collection = Collection(name="whatsapp_collection")

sessions = {}
last_active = {}

def transcribe_audio_gemini(file_path):
    """
    Transcribes an audio file using a Gemini model that supports audio input.
    """
    try:
        # Use a model that can handle audio, like Gemini 1.5 Pro
        model = genai.GenerativeModel('models/gemini-1.5-pro-latest')
        
        # Upload the audio file to the Gemini API
        audio_file = genai.upload_file(path=file_path)
        
        # Ask the model to transcribe the audio
        response = model.generate_content(["Please transcribe this audio.", audio_file])
        
        # Clean up the uploaded file
        genai.delete_file(audio_file.name)
        
        return response.text
    except Exception as e:
        print(f"Error transcribing audio with Gemini: {e}")
        raise e

# --- (Other functions like send_whatsapp_message, reminder_thread, etc. remain the same) ---
def send_whatsapp_message(to_number, message):
    client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    message = client.messages.create(
        from_='whatsapp:+14155238886',
        to=to_number,
        body=message
    )
    print("Reminder sent to {} with message {}".format(to_number, message))

def reminder_thread():
    while True:
        now = datetime.now(timezone.utc)
        for number, last_time in list(last_active.items()):
            if (now - last_time).total_seconds() > 24 * 3600:
                send_whatsapp_message(number, "Haven't seen you in a while, where have you been?")
                last_active[number] = now
        time.sleep(3600)

thread = Thread(target=reminder_thread, daemon=True)
thread.start()

def process_invoice_async(to_number, media_url):
    time.sleep(20)
    client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    message = client.messages.create(
        from_='whatsapp:+14155238886',
        to=to_number,
        body="Your invoice has been generated. You can download it here:",
        media_url=[media_url]
    )
    print(f"Message sent to {to_number} with SID: {message.sid}")

def convert_to_supported_format(input_path, output_path, format="wav"):
    try:
        AudioSegment.from_file(input_path).export(output_path, format=format)
    except Exception as e:
        print(f"Error converting audio file: {e}")
        raise e

@app.route("/webhook", methods=['POST'])
def webhook():
    from_number = request.form.get('From')
    body = request.form.get('Body')
    audio_url = request.form.get('MediaUrl0')
    media_content_type = request.form.get('MediaContentType0')
    timestamp = datetime.now(timezone.utc).isoformat()
    last_active[from_number] = datetime.now(timezone.utc)
    
    try:
        if audio_url and "audio" in media_content_type:
            input_audio_path = "temp_audio.ogg"
            converted_audio_path = "temp_audio.wav"
            
            audio_response = requests.get(audio_url, auth=HTTPBasicAuth(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN))
            with open(input_audio_path, "wb") as audio_file:
                audio_file.write(audio_response.content)
            
            convert_to_supported_format(input_audio_path, converted_audio_path)
            # --- Use the new Gemini transcription function ---
            body = transcribe_audio_gemini(converted_audio_path)

        if not body: # Ensure body is not empty after potential transcription
            resp = MessagingResponse()
            resp.message("Sorry, I couldn't understand the message.")
            return Response(str(resp), mimetype='application/xml')

        embedding = get_embedding(body) # This now calls the Gemini embedding function
        if not embedding:
            resp = MessagingResponse()
            resp.message("Sorry, something went wrong while processing your message.")
            return Response(str(resp), mimetype='application/xml')
            
        entities = [[from_number], [body], [timestamp], [embedding]]
        collection.insert(entities)
        collection.flush()

    except Exception as e:
        print(f"Error processing message or inserting into Milvus: {e}")
        resp = MessagingResponse()
        resp.message("Sorry, there was an error processing your message.")
        return Response(str(resp), mimetype='application/xml')

    if from_number not in sessions:
        sessions[from_number] = {"messages": []}
    sessions[from_number]["messages"].append({"role": "user", "content": body})

    state_payload = {
        "messages": sessions[from_number]["messages"],
        "conversation_state": sessions[from_number].get("conversation_state", {})
    }
    headers = {"phone-number": from_number}

    try:
        chat_response = requests.post(FASTAPI_URL, json=state_payload, headers=headers, timeout=60)
        chat_response.raise_for_status()
        
        if "application/pdf" in chat_response.headers.get("Content-Type", ""):
            pdf_filename = f"invoice_{uuid4().hex}.pdf"
            pdf_path = os.path.join("static", pdf_filename)
            os.makedirs("static", exist_ok=True)
            with open(pdf_path, 'wb') as pdf_file:
                pdf_file.write(chat_response.content)
            
            media_url = url_for('static', filename=pdf_filename, _external=True)
            resp = MessagingResponse()
            resp.message("Processing request...")
            thread = Thread(target=process_invoice_async, args=(from_number, media_url))
            thread.start()
            return Response(str(resp), mimetype='application/xml')

        if chat_response.headers.get("Content-Type") == "application/json":
            chat_data = chat_response.json()
            sessions[from_number]["messages"] = chat_data.get("messages", sessions[from_number]["messages"])
            sessions[from_number]["conversation_state"] = chat_data.get("conversation_state", {})
            
            messages = sessions[from_number]["messages"]
            bot_response = "I'm sorry, I don't understand."
            for msg in reversed(messages):
                if msg.get("role") == "assistant":
                    bot_response = msg.get("content", bot_response)
                    break
            
            resp = MessagingResponse()
            resp.message(bot_response)
            return Response(str(resp), mimetype='application/xml')
            
        raise Exception("Invalid response from FastAPI")

    except requests.exceptions.RequestException as e:
        print(f"Error making request to FastAPI: {e}")
        bot_response = "I'm sorry, I am having trouble connecting to the server."
        resp = MessagingResponse()
        resp.message(bot_response)
        return Response(str(resp), mimetype='application/xml')

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)