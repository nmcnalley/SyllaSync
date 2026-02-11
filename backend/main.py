from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
import shutil
import os
from extractor import extract_text_from_pdf, analyze_syllabus
import json

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

SCOPES = ['https://www.googleapis.com/auth/calendar']

def get_calendar_service():
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expured and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    return build('calendar', 'v3', credentials=creds)

class Event(BaseModel):
    title: str
    date: str
    weight: str = ""

@app.get("/")
def read_root():
    return {"message": "SyllaSync API is running!"}

@app.post("/upload/")
async def upload_syllabus(file: UploadFile = File(...)):
    temp_filename = f"temp_{file.filename}"

    try:
        with open(temp_filename, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        text = extract_text_from_pdf(temp_filename)

        if len(text) < 50:
            raise HTTPException(status_code=400, detail="Extracted text is too short. Please upload a valid syllabus PDF.") 
        
        json_string = analyze_syllabus(text)
        clean_json = json_string.replace("'''json", "").replace("'''", "").strip()
        data = json.loads(clean_json)

        return {"events": data}
    
    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    
    finally:
        if os.path.exists(temp_filename):
            os.remove(temp_filename)
   
@app.post("/create_events")
async def create_calendar_events(events: List[Event]):
    try:
        service = get_calendar_service()
        created_count = 0
        
        for event in events:
            if event.date.upper() == "TBD":
                continue
            calendar_event = {
                'summary': f"{event.title} ({event.weight})",
                'description': f"Added by SyllaSync. Weight: {event.weight}",
                'start': {
                    'date': event.date,
                    'timeZone': 'America/Edmonton',
                },
                'end': {
                    'date': event.date,
                    'timeZone': 'America/Edmonton',
                },
            }

            service.events().insert(calendarId='primary', body=calendar_event).execute()
            created_count += 1
            print(f"Created: {event.title}")
        return {"message": f"Successfully created {created_count} events."}
    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))