from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import shutil
import os
from extractor import extract_text_from_pdf, analyze_syllabus
import json

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "Syllabus Analyzer API is running!"}

@app.post("/upload/")
async def upload_syllabus(file: UploadFile = File(...)):
    """
    Receives a PDF file, saves it temporarily, extracts text, 
    and returns the structured JSON data.
    """
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

        return {"filename": file.filename, "events": data}
    
    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    
    finally:
        if os.path.exists(temp_filename):
            os.remove(temp_filename)
   
