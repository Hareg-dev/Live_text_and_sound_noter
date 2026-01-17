import pytest
import requests
import base64
import json
import time
import subprocess
import signal
import os
from pathlib import Path

API_BASE = "http://localhost:8000"

@pytest.fixture(scope="session")
def api_server():
    """Start API server for testing."""
    # Start server
    process = subprocess.Popen(
        ["python", "api.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    
    # Wait for server to start
    time.sleep(3)
    
    # Check if server is running
    try:
        response = requests.get(f"{API_BASE}/health", timeout=5)
        assert response.status_code == 200
    except:
        process.terminate()
        pytest.fail("API server failed to start")
    
    yield process
    
    # Cleanup
    process.terminate()
    process.wait()

def test_health_endpoint(api_server):
    """Test health check endpoint."""
    response = requests.get(f"{API_BASE}/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "timestamp" in data
    assert "config" in data

def test_config_endpoints(api_server):
    """Test configuration endpoints."""
    # Get config
    response = requests.get(f"{API_BASE}/config")
    assert response.status_code == 200
    config = response.json()
    assert "language" in config
    assert "notes_file" in config
    
    # Update config
    update_data = {"language": "en-US", "tts_enabled": True}
    response = requests.put(f"{API_BASE}/config", json=update_data)
    assert response.status_code == 200
    assert response.json()["config"]["language"] == "en-US"

def test_ocr_base64(api_server):
    """Test OCR with base64 image."""
    # Create simple test image
    import cv2
    import numpy as np
    
    img = np.ones((100, 300, 3), dtype=np.uint8) * 255
    cv2.putText(img, "TEST", (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 0), 2)
    
    # Encode to base64
    _, buffer = cv2.imencode('.png', img)
    img_base64 = base64.b64encode(buffer).decode('utf-8')
    
    # Test OCR
    response = requests.post(f"{API_BASE}/ocr/base64", json={"image": img_base64})
    assert response.status_code == 200
    data = response.json()
    assert "text" in data
    assert "language" in data

def test_tts_generation(api_server):
    """Test TTS generation."""
    data = {"text": "Hello test", "language": "en-US"}
    response = requests.post(f"{API_BASE}/tts/generate", json=data)
    assert response.status_code == 200
    assert response.headers["content-type"] == "audio/mpeg"

def test_notes_endpoints(api_server):
    """Test notes management."""
    # Get notes
    response = requests.get(f"{API_BASE}/notes")
    assert response.status_code == 200
    data = response.json()
    assert "notes" in data
    
    # Clear notes
    response = requests.delete(f"{API_BASE}/notes")
    assert response.status_code == 200
    assert "message" in response.json()

def test_invalid_requests(api_server):
    """Test error handling."""
    # Invalid OCR data
    response = requests.post(f"{API_BASE}/ocr/base64", json={"image": "invalid"})
    assert response.status_code == 400
    
    # Empty TTS text
    response = requests.post(f"{API_BASE}/tts/generate", json={"text": ""})
    assert response.status_code == 400