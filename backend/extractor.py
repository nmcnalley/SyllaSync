import google.generativeai as genai
import os
import time
from dotenv import load_dotenv
import fitz  # PyMuPDF
from google.api_core.exceptions import ResourceExhausted

load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

generation_config = {
    "temperature": 1,
    "top_p": 0.95,
    "top_k": 64,
    "max_output_tokens": 8192,
    "response_mime_type": "application/json",
}

model = genai.GenerativeModel(
    model_name="gemini-1.5-flash", # Updated to the standard naming convention
    generation_config=generation_config
)

def extract_text_from_pdf(pdf_path):
    try:
        doc = fitz.open(pdf_path)
        text = ""
        for page in doc:
            text += page.get_text()
        return text
    except Exception as e:
        print(f"Error extracting text from PDF: {e}")
        raise

def analyze_syllabus(text):
    prompt = """
    Analyze this syllabus text. Extract two things:
    1. The Course Code (e.g., "CMPUT 301", "ECE 447", "MATH 100"). 
       - Strictly extract ONLY the code (Department + Number). 
       - Do NOT include the full course title.
       - If multiple codes are found, pick the main one.
       - If no code is found, use "Unknown Course".

    2. A list of all important dates (assignments, exams, quizzes, projects).

    Return ONLY valid JSON in this format:
    {
        "course": "CMPUT 301", 
        "events": [
            {"title": "Assignment 1", "date": "YYYY-MM-DD", "weight": "10%"},
            {"title": "Midterm", "date": "YYYY-MM-DD", "weight": "20%"}
        ]
    }
    
    Rules:
    - Convert all dates to YYYY-MM-DD format.
    - If a specific date is not found, use "TBD".
    - Do not include reading weeks or holidays, only graded items.
    """
    
    max_retries = 4
    base_delay = 10 # Base wait time in seconds

    for attempt in range(max_retries):
        try:
            response = model.generate_content([prompt, text])
            return response.text
            
        except ResourceExhausted as e:
            if attempt == max_retries - 1:
                print("Max retries reached. Upload failed due to rate limits.")
                raise e
            
            # Exponential backoff calculates the delay: 10s, 20s, 40s
            sleep_time = base_delay * (2 ** attempt)
            print(f"Rate limit (429) hit. Pausing for {sleep_time} seconds before attempt {attempt + 2}...")
            time.sleep(sleep_time)
            
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            raise
