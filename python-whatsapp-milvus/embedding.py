import google.generativeai as genai
import os
from dotenv import load_dotenv

load_dotenv()

# Configure the Google AI SDK with your API key
api_key = os.getenv("GOOGLE_API_KEY")
if not api_key:
    raise ValueError("GOOGLE_API_KEY not found in environment variables.")
genai.configure(api_key=api_key)

def get_embedding(text, model="models/embedding-001"):
    """
    Generates embeddings for the given text using a Google Gemini model.
    """
    try:
        # Use the Gemini embedding model
        result = genai.embed_content(
            model=model,
            content=text,
            task_type="RETRIEVAL_DOCUMENT" # Use "retrieval_query" for queries
        )
        return result['embedding']
    except Exception as e:
        print(f"Error generating Gemini embedding: {e}")
        return None

if __name__ == "__main__":
    sample_text = "Hello, how can I assist you today?"
    embedding = get_embedding(sample_text)
    if embedding:
        print(f"Embedding generated successfully. Dimension: {len(embedding)}")
        # print(embedding) # Uncomment to see the full vector