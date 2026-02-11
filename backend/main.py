from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import google.generativeai as genai
import json
import os
import io
import pypdf
from datetime import datetime, timedelta

# Google Calendar Imports
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- CONFIGURATION ---
# Updated with your specific key
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=GEMINI_API_KEY)

SCOPES = ['https://www.googleapis.com/auth/calendar']

def get_calendar_service():
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    return build('calendar', 'v3', credentials=creds)

def extract_syllabus_data(text_content):
    # UPDATED MODEL: Using gemini-1.5-flash as requested
    model = genai.GenerativeModel("gemini-flash-latest")
    
    prompt = f"""
    You are a strict data extractor. Extract the course schedule from this syllabus.
    
    Return ONLY valid JSON. Structure:
    {{
        "course_name": "Course Code",
        "events": [
            {{ "title": "Exam 1", "date": "YYYY-MM-DD", "weight": "20%" }}
        ]
    }}
    
    Rules:
    1. For "course_name", extract ONLY the Course Code (e.g. "CMPUT 301", "MATH 100"). Do NOT include the full name like "Introduction to...".
    2. If the course code is not found, use a short 2-3 word summary.
    3. Convert all dates to YYYY-MM-DD. If year is missing, infer 2025.
    4. If a date is "TBA" or not found, return empty string "".
    
    Syllabus Text:
    {text_content[:15000]}
    """
    
    try:
        response = model.generate_content(prompt)
        cleaned_text = response.text.strip()
        # Remove markdown formatting if Gemini adds it
        if cleaned_text.startswith("```"):
            cleaned_text = cleaned_text.split("```")[1]
            if cleaned_text.startswith("json"):
                cleaned_text = cleaned_text[4:]
        
        return json.loads(cleaned_text)
    except Exception as e:
        print(f"AI Extraction Error: {e}")
        return {"course_name": "Error Parsing", "events": []}

@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    try:
        # Read the uploaded file into memory
        content = await file.read()
        pdf_file = io.BytesIO(content)
        
        # Extract text using PyPDF
        reader = pypdf.PdfReader(pdf_file)
        text_content = ""
        for page in reader.pages:
            text_content += page.extract_text() + "\n"
            
        print(f"Extracted {len(text_content)} characters from {file.filename}")

        # Send to AI
        data = extract_syllabus_data(text_content)
        
        return {
            "course": data.get("course_name", "Unnamed Course"),
            "events": data.get("events", [])
        }
    except Exception as e:
        print(f"Upload Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/create_events")
async def create_events(payload: dict):
    events = payload.get("events", [])
    add_reminders = payload.get("addReminders", False)
    service = get_calendar_service()
    
    created_count = 0
    keywords = ["exam", "midterm", "final", "test", "quiz"]

    for event in events:
        if not event.get('date'): continue # Skip empty dates

        # Main Event
        body = {
            'summary': f"[{event.get('course')}] {event.get('title')}",
            'description': f"Weight: {event.get('weight')}",
            'start': {'date': event.get('date')},
            'end': {'date': event.get('date')},
            'colorId': event.get('colorId', '9')
        }
        service.events().insert(calendarId='primary', body=body).execute()
        created_count += 1

        # Reminders
        if add_reminders:
            is_exam = any(k in event.get('title', '').lower() for k in keywords)
            if is_exam:
                try:
                    event_dt = datetime.strptime(event.get('date'), "%Y-%m-%d")
                    for days in [5, 2]:
                        rem_date = (event_dt - timedelta(days=days)).strftime("%Y-%m-%d")
                        rem_body = {
                            'summary': f"🔔 Study: {event.get('title')} ({days} days away)",
                            'start': {'date': rem_date},
                            'end': {'date': rem_date},
                            'colorId': "8",
                            'transparency': 'transparent'
                        }
                        service.events().insert(calendarId='primary', body=rem_body).execute()
                        created_count += 1
                except ValueError:
                    continue

    return {"message": f"Synced {created_count} events!"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)