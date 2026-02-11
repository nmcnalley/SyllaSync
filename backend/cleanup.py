from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import os

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

def delete_syllasync_events():
    service = get_calendar_service()
    
    print("🔍 Searching for SyllaSync events...")
    
    # Fetch events
    events_result = service.events().list(
        calendarId='primary', 
        singleEvents=True,
        orderBy='startTime'
    ).execute()
    
    events = events_result.get('items', [])
    to_delete = []

    # Identify events to delete based on our specific format
    for event in events:
        description = event.get('description', '')
        summary = event.get('summary', '')

        # CRITERIA: 
        # 1. Description contains "Weight:" OR "SyllaSync"
        # 2. Summary starts with "[" (e.g. [ECE 447])
        if ("Weight:" in description or "SyllaSync" in description) and summary.startswith("["):
            to_delete.append(event)

    if not to_delete:
        print("🎉 No events found matching the SyllaSync format.")
        return

    print(f"⚠️ Found {len(to_delete)} events that look like they belong to SyllaSync.")
    print("Here are the first 3:")
    for e in to_delete[:3]:
        print(f" - {e['summary']} ({e['start'].get('date')})")

    confirm = input("\n🔴 Delete ALL these events? (yes/no): ")
    
    if confirm.lower() == 'yes':
        batch = service.new_batch_http_request()
        callback = lambda request_id, response, exception: print(".", end="", flush=True)
        
        print("Deleting", end="")
        for event in to_delete:
            batch.add(service.events().delete(calendarId='primary', eventId=event['id']), callback=callback)
        
        batch.execute()
        print("\n✨ Done! Cleanup complete.")
    else:
        print("Operation cancelled.")

if __name__ == "__main__":
    delete_syllasync_events()