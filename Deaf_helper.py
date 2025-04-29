"""
DeafHelper.py - A real-time assistive app for deaf and hard-of-hearing users.
Features:
- Real-time text extraction from camera feed using OpenCV and Tesseract.
- Real-time speech-to-text using Google Speech API.
- Displays extracted text on screen and saves to notes.
- Production-ready with logging, error handling, and configuration.

Dependencies:
- pip install kivy opencv-python speechrecognition pyaudio pytesseract gTTS pygame requests
- Install Tesseract OCR and add to PATH.
- Ensure internet access for Google Speech API.
- Download Tesseract language data for Amharic (amh) and English (eng).

Setup:
- Create a config.json file with settings (see below).
- Run: python DeafHelper.py

Config (config.json):
{
  "camera_index": 0,
  "language": "am-ET",
  "notes_file": "notes.txt",
  "tts_enabled": false
}
"""
import os
import json
import logging
import threading
import time
from datetime import datetime
import cv2
import numpy as np
import speech_recognition as sr
import pygame
import pytesseract
from gtts import gTTS
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.spinner import Spinner
from kivy.uix.image import Image
from kivy.graphics.texture import Texture
from kivy.clock import Clock

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("deaf_helper.log"), logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Load configuration
CONFIG_FILE = "config.json"
DEFAULT_CONFIG = {
    "camera_index": 0,
    "language": "am-ET",
    "notes_file": "notes.txt",
    "tts_enabled": False
}

class DeafHelperApp(App):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.recognizer = sr.Recognizer()
        self.language = DEFAULT_CONFIG["language"]
        self.notes_file = DEFAULT_CONFIG["notes_file"]
        self.tts_enabled = DEFAULT_CONFIG["tts_enabled"]
        self.camera = None
        self.audio_thread = None
        self.running = False
        self.load_config()
        self.check_dependencies()

    def load_config(self):
        """Load configuration from JSON file."""
        try:
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, "r") as f:
                    config = json.load(f)
                self.language = config.get("language", DEFAULT_CONFIG["language"])
                self.notes_file = config.get("notes_file", DEFAULT_CONFIG["notes_file"])
                self.tts_enabled = config.get("tts_enabled", DEFAULT_CONFIG["tts_enabled"])
                self.camera_index = config.get("camera_index", DEFAULT_CONFIG["camera_index"])
                logger.info("Configuration loaded: %s", config)
            else:
                with open(CONFIG_FILE, "w") as f:
                    json.dump(DEFAULT_CONFIG, f, indent=4)
                logger.info("Default configuration created")
        except Exception as e:
            logger.error("Config load error: %s", str(e))
            self.result_label.text = f"Config Error: {str(e)}"

    def check_dependencies(self):
        """Verify required dependencies."""
        required_modules = ["cv2", "speech_recognition", "pyaudio", "pytesseract", "gTTS", "pygame"]
        for module in required_modules:
            try:
                __import__(module)
            except ImportError:
                logger.error("Missing dependency: %s", module)
                self.result_label.text = f"Error: Please install {module}."

    def build(self):
        """Initialize the Kivy UI."""
        self.running = True
        self.layout = BoxLayout(orientation="vertical", padding=20, spacing=15)

        # Language selection
        self.language_spinner = Spinner(
            text="Amharic",
            values=("Amharic", "English"),
            size_hint=(1, 0.1),
            font_size=24
        )
        self.language_spinner.bind(text=self.set_language)

        # Camera feed display
        self.camera_image = Image(size_hint=(1, 0.4))
        self.start_camera()

        # Result display
        self.result_label = TextInput(
            size_hint=(1, 0.4),
            readonly=True,
            font_size=24,
            multiline=True,
            background_color=(0.1, 0.1, 0.1, 1),
            foreground_color=(1, 1, 1, 1)
        )

        # Control buttons
        self.audio_btn = Button(
            text="Start Audio", on_press=self.toggle_audio, size_hint=(0.5, 0.1), font_size=24
        )
        self.exit_btn = Button(
            text=" Exit", on_press=self.stop_app, size_hint=(0.5, 0.1), font_size=24
        )

        # Add widgets
        self.layout.add_widget(self.language_spinner)
        self.layout.add_widget(self.camera_image)
        self.layout.add_widget(self.result_label)
        self.layout.add_widget(self.audio_btn)
        self.layout.add_widget(self.exit_btn)

        # Schedule camera update
        Clock.schedule_interval(self.update_camera, 1.0 / 30.0)

        # Start audio thread if enabled
        self.start_audio_thread()

        return self.layout

    def set_language(self, spinner, text):
        """Set the application language."""
        self.language = "am-ET" if text == "Amharic" else "en-US"
        logger.info("Language changed to %s", self.language)

    def start_camera(self):
        """Initialize the camera."""
        try:
            self.camera = cv2.VideoCapture(self.camera_index)
            if not self.camera.isOpened():
                raise ValueError("Camera not available")
            logger.info("Camera initialized on index %d", self.camera_index)
        except Exception as e:
            logger.error("Camera init error: %s", str(e))
            self.result_label.text = f"Camera Error: {str(e)}"

    def update_camera(self, dt):
        """Update camera feed and extract text."""
        if not self.running or not self.camera:
            return
        try:
            ret, frame = self.camera.read()
            if not ret:
                logger.warning("Failed to capture frame")
                return

            # Extract text from frame
            lang_code = "amh" if self.language == "am-ET" else "eng"
            text = pytesseract.image_to_string(frame, lang=lang_code).strip()
            if text:
                self.save_note("Camera", text)
                self.result_label.text = f"Camera Text:\n{text}\n\n{self.result_label.text[:200]}"

            # Update Kivy image
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w = frame.shape[:2]
            texture = Texture.create(size=(w, h), colorfmt='rgb')
            texture.blit_buffer(frame.flatten(), colorfmt='rgb', bufferfmt='ubyte')
            self.camera_image.texture = texture
        except Exception as e:
            logger.error("Camera update error: %s", str(e))
            self.result_label.text = f"Camera Error: {str(e)}"

    def start_audio_thread(self):
        """Start audio processing in a separate thread."""
        self.audio_thread = threading.Thread(target=self.audio_loop, daemon=True)
        self.audio_thread.start()

    def toggle_audio(self, instance):
        """Toggle audio processing."""
        if self.audio_btn.text == " Start Audio":
            self.audio_btn.text = " Stop Audio"
            self.running = True
        else:
            self.audio_btn.text = " Start Audio"
            self.running = False

    def audio_loop(self):
        """Real-time audio processing loop."""
        while True:
            if not self.running:
                time.sleep(0.1)
                continue
            try:
                with sr.Microphone() as source:
                    self.recognizer.adjust_for_ambient_noise(source)
                    audio = self.recognizer.listen(source, timeout=5, phrase_time_limit=5)
                text = self.recognizer.recognize_google(audio, language=self.language)
                if text:
                    self.save_note("Audio", text)
                    self.result_label.text = f"Audio Text:\n{text}\n\n{self.result_label.text[:200]}"
                    if self.tts_enabled:
                        self.play_tts(text)
                logger.info("Audio recognition successful: %s", text)
            except sr.UnknownValueError:
                logger.debug("Audio not understood")
            except sr.RequestError as e:
                logger.error("Audio API error: %s", str(e))
                self.result_label.text = f"Audio Error: {str(e)}"
            except Exception as e:
                logger.error("Audio loop error: %s", str(e))
                self.result_label.text = f"Audio Error: {str(e)}"

    def play_tts(self, text):
        """Play text-to-speech if enabled."""
        try:
            tts = gTTS(text=text, lang="am" if self.language == "am-ET" else "en")
            audio_file = f"tts_{int(time.time())}.mp3"
            tts.save(audio_file)
            pygame.mixer.init()
            pygame.mixer.music.load(audio_file)
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                pygame.time.Clock().tick(10)
            pygame.mixer.quit()
            if os.path.exists(audio_file):
                os.remove(audio_file)
        except Exception as e:
            logger.error("TTS error: %s", str(e))

    def save_note(self, source, text):
        """Save extracted text to notes file."""
        try:
            with open(self.notes_file, "a", encoding="utf-8") as f:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                f.write(f"[{timestamp}] {source}: {text}\n")
            logger.info("Note saved from %s: %s", source, text[:50])
        except Exception as e:
            logger.error("Note save error: %s", str(e))
            self.result_label.text = f"Note Save Error: {str(e)}"

    def stop_app(self, instance):
        """Cleanly exit the application."""
        self.running = False
        if self.camera:
            self.camera.release()
        logger.info("Application stopped")
        App.get_running_app().stop()

if __name__ == "__main__":
    DeafHelperApp().run()