#!/usr/bin/env python3
"""
Example client for Deaf Helper API
Demonstrates how to use the API endpoints
"""

import requests
import base64
import json

API_BASE = "http://localhost:8000"

def test_health():
    """Test health endpoint."""
    response = requests.get(f"{API_BASE}/health")
    print("Health Check:", response.json())

def test_config():
    """Test configuration endpoints."""
    # Get config
    response = requests.get(f"{API_BASE}/config")
    print("Current Config:", response.json())
    
    # Update config
    update_data = {"language": "en-US", "tts_enabled": True}
    response = requests.put(f"{API_BASE}/config", json=update_data)
    print("Config Update:", response.json())

def test_ocr_base64():
    """Test OCR with base64 image."""
    # Create a simple test image (1x1 white pixel)
    import cv2
    import numpy as np
    
    # Create test image with text
    img = np.ones((100, 300, 3), dtype=np.uint8) * 255
    cv2.putText(img, "Hello World", (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 0), 2)
    
    # Encode to base64
    _, buffer = cv2.imencode('.png', img)
    img_base64 = base64.b64encode(buffer).decode('utf-8')
    
    # Send to API
    response = requests.post(f"{API_BASE}/ocr/base64", json={"image": img_base64})
    print("OCR Result:", response.json())

def test_tts():
    """Test text-to-speech generation."""
    data = {"text": "Hello, this is a test", "language": "en-US"}
    response = requests.post(f"{API_BASE}/tts/generate", json=data)
    
    if response.status_code == 200:
        with open("test_tts.mp3", "wb") as f:
            f.write(response.content)
        print("TTS audio saved as test_tts.mp3")
    else:
        print("TTS Error:", response.text)

def test_notes():
    """Test notes endpoints."""
    # Get notes
    response = requests.get(f"{API_BASE}/notes")
    print("Notes:", response.json())

if __name__ == "__main__":
    print("Testing Deaf Helper API...")
    
    try:
        test_health()
        test_config()
        test_ocr_base64()
        test_tts()
        test_notes()
        print("All tests completed!")
    except requests.exceptions.ConnectionError:
        print("Error: API server not running. Start with: python api.py")
    except Exception as e:
        print(f"Test error: {e}")