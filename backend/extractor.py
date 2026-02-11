import os
import json
from dotenv import load_dotenv
from google import genai
from google.genai import types
from pypdf import PdfReader

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=api_key)

def extract_text_from_pdf(pdf_path):
    try:
        reader = PdfReader(pdf_path)
        text = ""
        for page in reader.pages:
            text += page.extract_text() + "\n"
        return text 
    except Exception as e:
        return f"Error reading PDF: {e}"
    
def analyze_syllabus(text):
    prompt = """
    You are a helpful assistant for university students.
    Read the following syllabus text and extract all important dates, assignments, exams, and holidays.
    
    Return the data in this exact JSON format:
    [
        {"title": "Assignment 1", "date": "2023-10-15", "weight": "10%", "type": "assignment"},
        {"title": "Midterm Exam", "date": "2023-11-02", "weight": "30%", "type": "exam"}
    ]
    
    If a date is not specific (like "Week 5"), make your best guess or use "TBD".
    If there is no year, assume the current academic year.
    Do not include any other text, just the JSON.
    """

    try:
        response = client.models.generate_content(
            model="gemini-flash-latest",
            contents=prompt + "\n\nSYLLABUS TEXT:\n" + text,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
            )
        )
        return response.text
    except Exception as e:
        return f"Error connecting to Gemini: {e}"

if __name__ == "__main__":
    pdf_path = "samples/syllabus.pdf"
    if not os.path.exists(pdf_path):
        print(f"PDF file not found: {pdf_path}")
        print("Please place a syllabus PDF in the 'samples' folder and name it 'syllabus.pdf'")  
    else:
        print(f"Reading PDF: {pdf_path}")
        raw_text = extract_text_from_pdf(pdf_path)
        
        if len(raw_text) < 50:
            print("PDF seems empty or text extraction failed. Please check the PDF file.")
        else:
            print("Extracting important information from syllabus...")
            structered_data = analyze_syllabus(raw_text)
            print("Extracted Information:")
            print(structered_data)

            with open("samples/output.json", "w") as f:
                f.write(structered_data)
                print("Structured data saved to samples/output.json")