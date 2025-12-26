# Deaf Helper Application

A production-ready accessibility application that helps deaf users by providing real-time text extraction from camera feeds and speech-to-text conversion.

## Features

- **Real-time OCR**: Extract text from camera feed using Tesseract
- **Speech Recognition**: Convert speech to text using Google Speech Recognition
- **Text-to-Speech**: Optional TTS playback with gTTS
- **Multi-language Support**: Amharic and English
- **Note Taking**: Automatic saving of all extracted text with timestamps
- **Thread-safe Operations**: Proper resource management and cleanup

## System Requirements

- Python 3.8+
- Camera (webcam)
- Microphone
- Tesseract OCR engine
- PortAudio (for microphone access)

## Installation

### Quick Setup (Linux/macOS)
```bash
chmod +x setup.sh
./setup.sh
```

### Manual Installation

1. **Install system dependencies:**

   **Ubuntu/Debian:**
   ```bash
   sudo apt-get update
   sudo apt-get install tesseract-ocr tesseract-ocr-amh portaudio19-dev python3-dev
   ```

   **CentOS/RHEL:**
   ```bash
   sudo yum install tesseract tesseract-langpack-amh portaudio-devel python3-devel
   ```

   **macOS:**
   ```bash
   brew install tesseract tesseract-lang portaudio
   ```

2. **Create virtual environment:**
   ```bash
   python3 -m venv deaf_helper_env
   source deaf_helper_env/bin/activate
   ```

3. **Install Python dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

## Usage

### GUI Application

1. **Activate virtual environment:**
   ```bash
   source deaf_helper_env/bin/activate
   ```

2. **Run the GUI application:**
   ```bash
   python Deaf_helper.py
   ```

3. **Using the interface:**
   - Select language (Amharic/English)
   - Click "Start Camera" to begin text extraction from video
   - Click "Start Audio" to begin speech recognition
   - All extracted text is automatically saved to `notes.txt`

### API Server

1. **Start the API server:**
   ```bash
   python api.py
   # or
   uvicorn api:app --reload --host 0.0.0.0 --port 8000
   ```

2. **API Documentation:**
   - Interactive docs: http://localhost:8000/docs
   - OpenAPI spec: http://localhost:8000/openapi.json

3. **API Endpoints:**
   - `GET /` - Root endpoint
   - `GET /config` - Get configuration
   - `PUT /config` - Update configuration
   - `POST /ocr/image` - Extract text from uploaded image
   - `POST /ocr/base64` - Extract text from base64 image
   - `POST /speech/recognize` - Recognize speech from audio file
   - `POST /tts/generate` - Generate text-to-speech audio
   - `GET /notes` - Get recent notes
   - `DELETE /notes` - Clear all notes
   - `GET /health` - Health check

## Configuration

Edit `config.json` to customize settings:

```json
{
    "camera_index": 0,
    "language": "am-ET",
    "notes_file": "notes.txt",
    "tts_enabled": false
}
```

## Production Deployment

### Key Improvements Made:

1. **Thread Safety**: Added locks and proper thread management
2. **Resource Management**: Proper cleanup of camera, audio, and temporary files
3. **Error Handling**: Comprehensive exception handling with logging
4. **Performance**: Optimized camera processing and text extraction
5. **Memory Management**: Efficient texture handling and temp file cleanup
6. **Logging**: Structured logging with file rotation
7. **Configuration**: Robust config loading with fallbacks
8. **Dependencies**: Proper dependency checking and validation

### Security Considerations:

- Input validation for all user inputs
- Secure temporary file handling
- Proper resource cleanup to prevent memory leaks
- Error messages don't expose sensitive information

## Troubleshooting

### Common Issues:

1. **Camera not working**: Check camera permissions and index in config
2. **Audio not recognized**: Verify microphone permissions and internet connection
3. **Missing dependencies**: Run setup script or install manually
4. **Performance issues**: Reduce camera resolution or frame rate

### Logs:

Check `logs/deaf_helper.log` for detailed error information.

## License

This project is provided as-is for accessibility purposes.