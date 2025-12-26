#!/bin/bash

# Deaf Helper Setup Script
echo "Setting up Deaf Helper Application..."

# Check Python version
python_version=$(python3 --version 2>&1 | grep -Po '(?<=Python )\d+\.\d+')
if [[ $(echo "$python_version >= 3.8" | bc -l) -eq 0 ]]; then
    echo "Error: Python 3.8+ required. Current version: $python_version"
    exit 1
fi

# Install system dependencies
echo "Installing system dependencies..."
if command -v apt-get &> /dev/null; then
    sudo apt-get update
    sudo apt-get install -y tesseract-ocr tesseract-ocr-amh portaudio19-dev python3-dev
elif command -v yum &> /dev/null; then
    sudo yum install -y tesseract tesseract-langpack-amh portaudio-devel python3-devel
elif command -v brew &> /dev/null; then
    brew install tesseract tesseract-lang portaudio
fi

# Create virtual environment
echo "Creating virtual environment..."
python3 -m venv deaf_helper_env
source deaf_helper_env/bin/activate

# Install Python dependencies
echo "Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Create directories
mkdir -p logs

echo "Setup complete!"
echo "To run the application:"
echo "1. Activate virtual environment: source deaf_helper_env/bin/activate"
echo "2. Run GUI application: python Deaf_helper.py"
echo "3. Run API server: python api.py (or uvicorn api:app --reload)"
echo "4. API documentation: http://localhost:8000/docs"