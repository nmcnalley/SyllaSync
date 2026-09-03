from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import google.genai
import json
import os
import io
import pypdf
from datetime import datetime, timedelta
from dotenv import load_dotenv
from google.oauth2.credentials import Credentials

# --- BULLETPROOF .ENV LOADING ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.join(BASE_DIR, ".env")
load_dotenv(ENV_PATH)

# Google Calendar & Sheets Imports
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

app = FastAPI()

origins = [
    "http://localhost:5173", # Keep this so you can still test on your computer
    "https://syllasync-six.vercel.app" # <-- ADD YOUR EXACT VERCEL URL HERE (No slash at the end!)
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- CONFIGURATION ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    print(f"❌ ERROR: Still cannot find the API key! I looked exactly here: {ENV_PATH}")
else:
    print("✅ API Key loaded successfully!")

genai.configure(api_key=GEMINI_API_KEY)

# --- UPDATED SCOPES: Now includes both Calendar AND Sheets ---
SCOPES = [
    'https://www.googleapis.com/auth/calendar',
    'https://www.googleapis.com/auth/spreadsheets'
]

def extract_syllabus_data(text_content):
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
    3. Convert all dates to YYYY-MM-DD. If year is missing, infer 2026.
    4. If a date is "TBA" or not found, return empty string "".
    
    Syllabus Text:
    {text_content[:15000]}
    """
    
    try:
        response = model.generate_content(prompt)
        cleaned_text = response.text.strip()
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
        content = await file.read()
        pdf_file = io.BytesIO(content)
        
        reader = pypdf.PdfReader(pdf_file)
        text_content = ""
        for page in reader.pages:
            text_content += page.extract_text() + "\n"
            
        print(f"Extracted {len(text_content)} characters from {file.filename}")

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
    user_token = payload.get("token") # <-- 1. Get the token from React
    
    if not user_token:
        raise HTTPException(status_code=401, detail="No Google token provided")
        
    # <-- 2. Build credentials DIRECTLY from the token! Goodbye token.json!
    creds = Credentials(token=user_token) 
    service = build('calendar', 'v3', credentials=creds)
    
    # --- FIND OR CREATE DEDICATED CALENDAR ---
    calendar_summary = "SyllaSync Schedule"
    target_calendar_id = None
    
    calendar_list = service.calendarList().list().execute()
    for calendar_list_entry in calendar_list.get('items', []):
        if calendar_list_entry['summary'] == calendar_summary:
            target_calendar_id = calendar_list_entry['id']
            break
            
    if not target_calendar_id:
        calendar_body = {
            'summary': calendar_summary,
            'description': 'Classes and assignments imported from SyllaSync'
        }
        created_calendar = service.calendars().insert(body=calendar_body).execute()
        target_calendar_id = created_calendar['id']

    created_count = 0
    keywords = ["exam", "midterm", "final", "test", "quiz"]

    for event in events:
        if not event.get('date'): continue 

        body = {
            'summary': f"[{event.get('course')}] {event.get('title')}",
            'description': f"Weight: {event.get('weight')}",
            'start': {'date': event.get('date')},
            'end': {'date': event.get('date')},
            'colorId': event.get('colorId', '9')
        }
        
        try:
            service.events().insert(calendarId=target_calendar_id, body=body).execute()
            created_count += 1

            if add_reminders:
                is_exam = any(k in event.get('title', '').lower() for k in keywords)
                if is_exam:
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
                        service.events().insert(calendarId=target_calendar_id, body=rem_body).execute()
                        created_count += 1
        except Exception as e:
            print(f"Skipping event {event.get('title')}: {e}")
            continue

    return {"message": f"Synced {created_count} events to the '{calendar_summary}' Calendar!"}

# --- NEW SHEETS ENDPOINT ---
@app.post("/export_sheets")
async def export_sheets(payload: dict):
    events = payload.get("events", [])
    user_token = payload.get("token") # <-- 1. Get the token from React
    
    if not events:
        raise HTTPException(status_code=400, detail="No events provided")
    if not user_token:
        raise HTTPException(status_code=401, detail="No Google token provided")

    # <-- 2. Build credentials directly from the token!
    creds = Credentials(token=user_token)
    service = build('sheets', 'v4', credentials=creds)

    # 1. Create a new blank spreadsheet
    spreadsheet_body = {
        'properties': {
            'title': f'SyllaSync Semester Dashboard ({datetime.now().strftime("%B %Y")})'
        }
    }
    spreadsheet = service.spreadsheets().create(body=spreadsheet_body, fields='spreadsheetId,spreadsheetUrl').execute()
    sheet_id = spreadsheet.get('spreadsheetId')
    sheet_url = spreadsheet.get('spreadsheetUrl')

    # 2. Prepare the data
    values = [["Class", "Task", "Due Date", "Status", "Weight"]]
    unique_classes = list(set())

    for ev in events:
        course_name = ev.get("course", "")
        if course_name:
            unique_classes.append(course_name)
            
        date_str = ev.get("date") if ev.get("date") else "TBA"
        values.append([
            course_name,
            ev.get("title", ""),
            date_str,
            "Not Started",
            ev.get("weight", "")
        ])
        
    unique_classes = list(set(unique_classes))

    # 3. Write data to the sheet
    num_rows = len(values)
    range_name = f'Sheet1!A1:E{num_rows}'
    body = {'values': values}
    service.spreadsheets().values().update(
        spreadsheetId=sheet_id, range=range_name,
        valueInputOption='USER_ENTERED', body=body).execute()

    # 4. FORMATTING UPGRADE
    requests = []

    # --- A. Header Formatting ---
    requests.append({
        "repeatCell": {
            "range": {"sheetId": 0, "startRowIndex": 0, "endRowIndex": 1},
            "cell": {
                "userEnteredFormat": {
                    "backgroundColor": {"red": 0.3, "green": 0.2, "blue": 0.4},
                    "textFormat": {"foregroundColor": {"red": 1.0, "green": 1.0, "blue": 1.0}, "bold": True},
                    "horizontalAlignment": "CENTER"
                }
            },
            "fields": "userEnteredFormat(backgroundColor,textFormat,horizontalAlignment)"
        }
    })

    # --- B. Center Alignment ---
    for col_range in [{"start": 0, "end": 1}, {"start": 2, "end": 5}]: 
        requests.append({
            "repeatCell": {
                "range": {"sheetId": 0, "startRowIndex": 1, "endRowIndex": num_rows, "startColumnIndex": col_range["start"], "endColumnIndex": col_range["end"]},
                "cell": {
                    "userEnteredFormat": {"horizontalAlignment": "CENTER", "verticalAlignment": "MIDDLE"}
                },
                "fields": "userEnteredFormat(horizontalAlignment, verticalAlignment)"
            }
        })

    # --- C. Date Formatting ---
    requests.append({
        "repeatCell": {
            "range": {"sheetId": 0, "startRowIndex": 1, "endRowIndex": num_rows, "startColumnIndex": 2, "endColumnIndex": 3},
            "cell": {
                "userEnteredFormat": {
                    "numberFormat": {"type": "DATE", "pattern": "mmm d"}
                }
            },
            "fields": "userEnteredFormat.numberFormat"
        }
    })

    # --- D. Borders ---
    requests.append({
        "updateBorders": {
            "range": {"sheetId": 0, "startRowIndex": 0, "endRowIndex": num_rows, "startColumnIndex": 0, "endColumnIndex": 5},
            "innerHorizontal": {"style": "SOLID", "width": 1, "color": {"red": 0.8, "green": 0.8, "blue": 0.8}},
            "innerVertical": {"style": "SOLID", "width": 1, "color": {"red": 0.8, "green": 0.8, "blue": 0.8}},
            "top": {"style": "SOLID", "width": 1}, "bottom": {"style": "SOLID", "width": 1},
            "left": {"style": "SOLID", "width": 1}, "right": {"style": "SOLID", "width": 1}
        }
    })

    # --- E. Status Dropdowns ---
    requests.append({
        "setDataValidation": {
            "range": {"sheetId": 0, "startRowIndex": 1, "endRowIndex": num_rows, "startColumnIndex": 3, "endColumnIndex": 4},
            "rule": {
                "condition": {
                    "type": "ONE_OF_LIST",
                    "values": [{"userEnteredValue": "Not Started"}, {"userEnteredValue": "In Progress"}, {"userEnteredValue": "Done"}, {"userEnteredValue": "Quiz"}, {"userEnteredValue": "Exam"}]
                },
                "showCustomUi": True, "strict": True
            }
        }
    })

    # --- F. Status Color Pills ---
    status_colors = [
        ("Done", {"red": 0.2, "green": 0.6, "blue": 0.3}, {"red": 1.0, "green": 1.0, "blue": 1.0}),
        ("In Progress", {"red": 0.98, "green": 0.73, "blue": 0.0}, {"red": 0.0, "green": 0.0, "blue": 0.0}),
        ("Not Started", {"red": 0.9, "green": 0.9, "blue": 0.9}, {"red": 0.3, "green": 0.3, "blue": 0.3}),
        ("Quiz", {"red": 0.75, "green": 0.65, "blue": 0.90}, {"red": 1.0, "green": 1.0, "blue": 1.0}),
        ("Exam", {"red": 0.35, "green": 0.15, "blue": 0.50}, {"red": 1.0, "green": 1.0, "blue": 1.0}) 
    ]
    for status, bg_color, text_color in status_colors:
        requests.append({
            "addConditionalFormatRule": {
                "rule": {
                    "ranges": [{"sheetId": 0, "startRowIndex": 1, "endRowIndex": num_rows, "startColumnIndex": 3, "endColumnIndex": 4}],
                    "booleanRule": {
                        "condition": {"type": "TEXT_EQ", "values": [{"userEnteredValue": status}]},
                        "format": {"backgroundColor": bg_color, "textFormat": {"foregroundColor": text_color, "bold": True}}
                    }
                }, "index": 0
            }
        })

    # --- G. Auto-Color Classes ---
    pastel_palette = [
        {"red": 0.8, "green": 0.9, "blue": 1.0},
        {"red": 1.0, "green": 0.8, "blue": 0.8},
        {"red": 0.8, "green": 1.0, "blue": 0.8},
        {"red": 1.0, "green": 0.9, "blue": 0.7},
        {"red": 0.9, "green": 0.8, "blue": 1.0} 
    ]
    
    for i, class_name in enumerate(unique_classes):
        color = pastel_palette[i % len(pastel_palette)]
        requests.append({
            "addConditionalFormatRule": {
                "rule": {
                    "ranges": [{"sheetId": 0, "startRowIndex": 1, "endRowIndex": num_rows, "startColumnIndex": 0, "endColumnIndex": 1}],
                    "booleanRule": {
                        "condition": {"type": "TEXT_EQ", "values": [{"userEnteredValue": class_name}]},
                        "format": {"backgroundColor": color, "textFormat": {"bold": True}}
                    }
                }, "index": 0
            }
        })

    service.spreadsheets().batchUpdate(spreadsheetId=sheet_id, body={'requests': requests}).execute()

    return {"message": "Spreadsheet created successfully!", "url": sheet_url}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
