import os
import json
import logging
import asyncio
import tempfile
import base64
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any
import cv2
import numpy as np
import speech_recognition as sr
import pytesseract
from gtts import gTTS
from fastapi import FastAPI, HTTPException, UploadFile, File, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
import uvicorn

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
CONFIG_FILE = "config.json"
DEFAULT_CONFIG = {
    "camera_index": 0,
    "language": "am-ET",
    "notes_file": "notes.txt",
    "tts_enabled": False
}

app = FastAPI(title="Deaf Helper API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global variables
recognizer = sr.Recognizer()
config = DEFAULT_CONFIG.copy()

# Pydantic models
class TextRequest(BaseModel):
    text: str
    language: Optional[str] = "en-US"

class ConfigUpdate(BaseModel):
    camera_index: Optional[int] = None
    language: Optional[str] = None
    notes_file: Optional[str] = None
    tts_enabled: Optional[bool] = None

class NoteResponse(BaseModel):
    timestamp: str
    source: str
    text: str

def load_config():
    """Load configuration from JSON file."""
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                config.update(json.load(f))
        else:
            save_config()
        logger.info("Configuration loaded")
    except Exception as e:
        logger.error(f"Config load error: {e}")

def save_config():
    """Save configuration to JSON file."""
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4)
        logger.info("Configuration saved")
    except Exception as e:
        logger.error(f"Config save error: {e}")

def save_note(source: str, text: str):
    """Save note to file."""
    try:
        notes_path = Path(config["notes_file"])
        notes_path.parent.mkdir(exist_ok=True)
        
        with open(config["notes_file"], "a", encoding="utf-8") as f:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            clean_text = text.replace('\n', ' ').strip()
            f.write(f"[{timestamp}] {source}: {clean_text}\n")
        
        logger.info(f"Note saved from {source}")
    except Exception as e:
        logger.error(f"Save note error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save note: {e}")

@app.on_event("startup")
async def startup_event():
    """Initialize application on startup."""
    load_config()
    logger.info("Deaf Helper API started")

@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "Deaf Helper API", "version": "1.0.0"}

@app.get("/config")
async def get_config():
    """Get current configuration."""
    return config

@app.put("/config")
async def update_config(config_update: ConfigUpdate):
    """Update configuration."""
    try:
        if config_update.camera_index is not None:
            config["camera_index"] = config_update.camera_index
        if config_update.language is not None:
            config["language"] = config_update.language
        if config_update.notes_file is not None:
            config["notes_file"] = config_update.notes_file
        if config_update.tts_enabled is not None:
            config["tts_enabled"] = config_update.tts_enabled
        
        save_config()
        return {"message": "Configuration updated", "config": config}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update config: {e}")

@app.post("/ocr/image")
async def extract_text_from_image(file: UploadFile = File(...)):
    """Extract text from uploaded image."""
    try:
        # Read image
        contents = await file.read()
        nparr = np.frombuffer(contents, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if image is None:
            raise HTTPException(status_code=400, detail="Invalid image format")
        
        # Extract text
        lang_code = "amh" if config["language"] == "am-ET" else "eng"
        text = pytesseract.image_to_string(image, lang=lang_code).strip()
        
        if text:
            save_note("OCR", text)
        
        return {"text": text, "language": config["language"]}
    except Exception as e:
        logger.error(f"OCR error: {e}")
        raise HTTPException(status_code=500, detail=f"OCR failed: {e}")

@app.post("/ocr/base64")
async def extract_text_from_base64(data: dict):
    """Extract text from base64 encoded image."""
    try:
        # Decode base64 image
        image_data = base64.b64decode(data["image"])
        nparr = np.frombuffer(image_data, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if image is None:
            raise HTTPException(status_code=400, detail="Invalid image data")
        
        # Extract text
        lang_code = "amh" if config["language"] == "am-ET" else "eng"
        text = pytesseract.image_to_string(image, lang=lang_code).strip()
        
        if text:
            save_note("OCR", text)
        
        return {"text": text, "language": config["language"]}
    except Exception as e:
        logger.error(f"OCR error: {e}")
        raise HTTPException(status_code=500, detail=f"OCR failed: {e}")

@app.post("/speech/recognize")
async def recognize_speech(file: UploadFile = File(...)):
    """Recognize speech from audio file."""
    try:
        # Save uploaded file temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_file:
            contents = await file.read()
            temp_file.write(contents)
            temp_path = temp_file.name
        
        try:
            # Recognize speech
            with sr.AudioFile(temp_path) as source:
                audio = recognizer.record(source)
            
            text = recognizer.recognize_google(audio, language=config["language"])
            
            if text:
                save_note("Speech", text)
            
            return {"text": text, "language": config["language"]}
        finally:
            # Clean up temp file
            if os.path.exists(temp_path):
                os.remove(temp_path)
                
    except sr.UnknownValueError:
        raise HTTPException(status_code=400, detail="Could not understand audio")
    except sr.RequestError as e:
        raise HTTPException(status_code=500, detail=f"Speech recognition error: {e}")
    except Exception as e:
        logger.error(f"Speech recognition error: {e}")
        raise HTTPException(status_code=500, detail=f"Speech recognition failed: {e}")

@app.post("/tts/generate")
async def generate_tts(request: TextRequest, background_tasks: BackgroundTasks):
    """Generate text-to-speech audio."""
    try:
        if not request.text.strip():
            raise HTTPException(status_code=400, detail="Text cannot be empty")
        
        # Create temporary file
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
        temp_path = temp_file.name
        temp_file.close()
        
        # Generate TTS
        tts_lang = "am" if request.language == "am-ET" else "en"
        tts = gTTS(text=request.text[:500], lang=tts_lang, slow=False)
        tts.save(temp_path)
        
        # Schedule cleanup
        background_tasks.add_task(cleanup_file, temp_path)
        
        return FileResponse(
            temp_path,
            media_type="audio/mpeg",
            filename="tts_audio.mp3"
        )
    except Exception as e:
        logger.error(f"TTS error: {e}")
        raise HTTPException(status_code=500, detail=f"TTS generation failed: {e}")

@app.get("/notes")
async def get_notes(limit: int = 100):
    """Get recent notes."""
    try:
        if not os.path.exists(config["notes_file"]):
            return {"notes": []}
        
        notes = []
        with open(config["notes_file"], "r", encoding="utf-8") as f:
            lines = f.readlines()
        
        # Parse last 'limit' lines
        for line in lines[-limit:]:
            line = line.strip()
            if line and line.startswith("["):
                try:
                    # Parse format: [timestamp] source: text
                    end_bracket = line.find("]")
                    timestamp = line[1:end_bracket]
                    rest = line[end_bracket + 2:]  # Skip "] "
                    colon_pos = rest.find(": ")
                    source = rest[:colon_pos]
                    text = rest[colon_pos + 2:]
                    
                    notes.append({
                        "timestamp": timestamp,
                        "source": source,
                        "text": text
                    })
                except Exception:
                    continue
        
        return {"notes": notes}
    except Exception as e:
        logger.error(f"Get notes error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get notes: {e}")

@app.delete("/notes")
async def clear_notes():
    """Clear all notes."""
    try:
        if os.path.exists(config["notes_file"]):
            os.remove(config["notes_file"])
        return {"message": "Notes cleared"}
    except Exception as e:
        logger.error(f"Clear notes error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to clear notes: {e}")

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "config": config
    }

def cleanup_file(filepath: str):
    """Clean up temporary file."""
    try:
        if os.path.exists(filepath):
            os.remove(filepath)
    except Exception as e:
        logger.error(f"File cleanup error: {e}")

if __name__ == "__main__":
    uvicorn.run(
        "api:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )