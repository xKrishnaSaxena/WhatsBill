# WhatsBill

WhatsBill is a WhatsApp-based invoice creation bot powered by Twilio, FastAPI, MongoDB, and Google Gemini AI. It allows users to generate professional invoices through natural language conversations on WhatsApp, including service selection, address input, tax calculations, and PDF generation. The system supports reminders, audio transcription (for voice notes), and vector search for contextual responses.

## Screenshots
![Invoice Creation Flow 1](https://github.com/user-attachments/assets/9e10083b-2013-4dc9-8eb2-e50f5bd1fffb) 
![Invoice Creation Flow 2](https://github.com/user-attachments/assets/5b263c44-36db-41e5-a010-7c5abf4cb3b2)
![Generated PDF Example](https://github.com/user-attachments/files/22052610/invoice_ac3d079588f74f2d9bc80330e437fcd5.pdf)

## Table of Contents
- [Features](#features)
- [Architecture](#architecture)
- [Technologies Used](#technologies-used)
- [Setup Instructions](#setup-instructions)
- [Usage](#usage)
- [Screenshots](#screenshots)
- [Contributing](#contributing)
- [License](#license)

## Features
- **Conversational Invoice Creation**: Step-by-step guided process via WhatsApp to select companies, services, quantities, addresses, and advertisements.
- **PDF Invoice Generation**: Automatically generates and sends downloadable PDF invoices with details like subtotal, CGST/SGST taxes, and company branding.
- **Reminder System**: Set timed reminders (e.g., "remind me in 2 hours") and receive WhatsApp notifications.
- **Audio Transcription**: Handles voice messages by transcribing them using Google Gemini AI for seamless input.
- **AI-Powered Responses**: Uses Gemini for embeddings, intent detection, and natural language processing.
- **Data Management**: Fetches and updates companies, clients, services, and advertisements from a MongoDB backend.
- **Session Management**: Maintains conversation state for multi-step interactions, with timeouts for inactivity.
- **Tone Customization**: Responses can be tuned (e.g., Friendly, Formal) – currently set to Friendly by default.

## Architecture
The project consists of three main components:
1. **Twilio Webhook (Flask App)**: Handles incoming WhatsApp messages, processes audio, embeds content with Gemini, stores in Milvus for vector search, and forwards to the FastAPI backend.
2. **FastAPI Backend (Chat Logic)**: Manages conversation state, intent detection, invoice creation logic, and integrations with MongoDB. It uses Gemini for AI tasks like parsing reminders and generating responses.
3. **Mock API (FastAPI for Data)**: Simulates database operations for companies, clients, services, advertisements, and PDF generation using ReportLab.

Key Flows:
- User sends message → Twilio webhook → Embed & store in Milvus → Forward to FastAPI → Process intent (e.g., create invoice) → Respond via Twilio.
- Invoice PDF: Generated on confirmation and streamed back as an attachment.

## Technologies Used
- **Backend**: FastAPI (for chat logic and mock API), Flask (for Twilio webhook)
- **Messaging**: Twilio (WhatsApp integration)
- **AI/ML**: Google Gemini (embeddings, transcription, intent detection via generative AI)
- **Database**: MongoDB (for storing companies, clients, etc.), Milvus (vector database for embeddings)
- **PDF Generation**: ReportLab
- **Audio Processing**: PyDub (for format conversion)
- **Other**: Pydantic (models), Requests (API calls), Asyncio (for scheduling)

## Setup Instructions

### Prerequisites
- Python 3.10+
- MongoDB instance (local or cloud)
- Twilio account with WhatsApp sandbox
- Google API Key (for Gemini)
- Milvus instance (standalone or Docker)

### Environment Variables
Create a `.env` file with:
```
TWILIO_ACCOUNT_SID=your_twilio_sid
TWILIO_AUTH_TOKEN=your_twilio_token
GOOGLE_API_KEY=your_google_api_key
FASTAPI_URL=http://localhost:8000/chat/
MILVUS_HOST=localhost
MILVUS_PORT=19530
```

### Installation
1. Clone the repo:
   ```
   git clone https://github.com/yourusername/WhatsBill.git
   cd WhatsBill
   ```

2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
   (Create `requirements.txt` with: fastapi, uvicorn, flask, twilio, google-generativeai, pymilvus, pydub, requests, python-dotenv, etc.)

3. Start Milvus (if using Docker):
   ```
   docker run -d -p 19530:19530 milvusdb/milvus:latest
   ```

4. Run the apps:
   - Mock API (port 8001): `uvicorn mock_api:app --host 0.0.0.0 --port 8001 --reload`
   - Chat Backend (port 8000): `uvicorn main:app --host 0.0.0.0 --port 8000 --reload`
   - Twilio Webhook (port 5000): `python webhook.py`

5. Configure Twilio: Set your WhatsApp sandbox webhook to `https://your-domain/webhook` (use ngrok for local testing: `ngrok http 5000`).

6. Seed MongoDB: Insert sample data for companies, clients, services, and ads (use the provided mock data in `database.py`).

## Usage
1. Join Twilio's WhatsApp sandbox by sending "join <code>" to +14155238886.
2. Start a conversation: Send "create invoice" to begin the process.
3. Follow prompts: Select company, service, quantity, addresses, etc.
4. Confirm: Receive a PDF invoice link.
5. Set reminders: e.g., "Remind me in 2 hours to pay bill."
6. Send voice notes: The bot transcribes and processes them.
