import os
import json
import logging
import threading
import time
from datetime import datetime
import tempfile
import atexit
from pathlib import Path
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
from kivy.logger import Logger

def setup_logging():
    """Setup logging with proper error handling."""
    try:
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(levelname)s - %(message)s",
            handlers=[
                logging.FileHandler(log_dir / "deaf_helper.log"),
                logging.StreamHandler()
            ]
        )
    except Exception as e:
        print(f"Logging setup failed: {e}")
        logging.basicConfig(level=logging.INFO)
    return logging.getLogger(__name__)

logger = setup_logging()

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
        self.camera_index = DEFAULT_CONFIG["camera_index"]
        self.camera = None
        self.audio_thread = None
        self.camera_thread = None
        self.running = False
        self.audio_running = False
        self.camera_running = False
        self.result_label = None
        self.audio_btn = None
        self.lock = threading.Lock()
        self.temp_files = []
        atexit.register(self.cleanup)
        
        try:
            self.load_config()
            self.check_dependencies()
        except Exception as e:
            logger.error(f"Initialization error: {e}")

    def load_config(self):
        """Load configuration from JSON file."""
        try:
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    config = json.load(f)
                self.language = config.get("language", DEFAULT_CONFIG["language"])
                self.notes_file = config.get("notes_file", DEFAULT_CONFIG["notes_file"])
                self.tts_enabled = config.get("tts_enabled", DEFAULT_CONFIG["tts_enabled"])
                self.camera_index = config.get("camera_index", DEFAULT_CONFIG["camera_index"])
                logger.info("Configuration loaded successfully")
            else:
                with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                    json.dump(DEFAULT_CONFIG, f, indent=4)
                logger.info("Default configuration created")
        except Exception as e:
            logger.error(f"Config load error: {e}")
            # Use defaults if config fails
            self.language = DEFAULT_CONFIG["language"]
            self.notes_file = DEFAULT_CONFIG["notes_file"]
            self.tts_enabled = DEFAULT_CONFIG["tts_enabled"]
            self.camera_index = DEFAULT_CONFIG["camera_index"]

    def check_dependencies(self):
        """Verify required dependencies."""
        missing_deps = []
        required_modules = ["cv2", "speech_recognition", "pyaudio", "pytesseract", "gtts", "pygame"]
        
        for module in required_modules:
            try:
                __import__(module)
            except ImportError:
                missing_deps.append(module)
                logger.error(f"Missing dependency: {module}")
        
        if missing_deps:
            error_msg = f"Missing dependencies: {', '.join(missing_deps)}"
            logger.error(error_msg)
            raise ImportError(error_msg)

    def build(self):
        """Initialize the Kivy UI."""
        try:
            self.layout = BoxLayout(orientation="vertical", padding=20, spacing=15)

            # Language selection
            self.language_spinner = Spinner(
                text="Amharic" if self.language == "am-ET" else "English",
                values=("Amharic", "English"),
                size_hint=(1, 0.1),
                font_size=24
            )
            self.language_spinner.bind(text=self.set_language)

            # Camera feed display
            self.camera_image = Image(size_hint=(1, 0.4))

            # Result display
            self.result_label = TextInput(
                size_hint=(1, 0.4),
                readonly=True,
                font_size=18,
                multiline=True,
                background_color=(0.1, 0.1, 0.1, 1),
                foreground_color=(1, 1, 1, 1),
                text="Application started. Click buttons to begin."
            )

            # Control buttons
            button_layout = BoxLayout(orientation="horizontal", size_hint=(1, 0.1), spacing=10)
            
            self.audio_btn = Button(
                text="Start Audio", on_press=self.toggle_audio, font_size=20
            )
            
            self.camera_btn = Button(
                text="Start Camera", on_press=self.toggle_camera, font_size=20
            )
            
            self.exit_btn = Button(
                text="Exit", on_press=self.stop_app, font_size=20
            )

            button_layout.add_widget(self.audio_btn)
            button_layout.add_widget(self.camera_btn)
            button_layout.add_widget(self.exit_btn)

            # Add widgets
            self.layout.add_widget(self.language_spinner)
            self.layout.add_widget(self.camera_image)
            self.layout.add_widget(self.result_label)
            self.layout.add_widget(button_layout)

            return self.layout
        except Exception as e:
            logger.error(f"UI build error: {e}")
            raise

    def set_language(self, spinner, text):
        """Set the application language."""
        self.language = "am-ET" if text == "Amharic" else "en-US"
        logger.info("Language changed to %s", self.language)

    def start_camera(self):
        """Initialize the camera."""
        try:
            if self.camera:
                self.camera.release()
            
            self.camera = cv2.VideoCapture(self.camera_index)
            if not self.camera.isOpened():
                raise ValueError(f"Camera {self.camera_index} not available")
            
            # Set camera properties for better performance
            self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            self.camera.set(cv2.CAP_PROP_FPS, 15)
            
            logger.info(f"Camera initialized on index {self.camera_index}")
            return True
        except Exception as e:
            logger.error(f"Camera init error: {e}")
            if self.result_label:
                Clock.schedule_once(lambda dt: setattr(self.result_label, 'text', f"Camera Error: {e}"), 0)
            return False
    
    def toggle_camera(self, instance):
        """Toggle camera processing."""
        if self.camera_btn.text == "Start Camera":
            if self.start_camera():
                self.camera_running = True
                self.camera_btn.text = "Stop Camera"
                Clock.schedule_interval(self.update_camera, 1.0 / 15.0)
                self.update_status("Camera started")
        else:
            self.camera_running = False
            self.camera_btn.text = "Start Camera"
            Clock.unschedule(self.update_camera)
            if self.camera:
                self.camera.release()
                self.camera = None
            self.update_status("Camera stopped")

    def update_camera(self, dt):
        """Update camera feed and extract text."""
        if not self.camera_running or not self.camera:
            return False
        
        try:
            ret, frame = self.camera.read()
            if not ret:
                logger.warning("Failed to capture frame")
                return True

            # Update Kivy image first (faster)
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w = frame_rgb.shape[:2]
            texture = Texture.create(size=(w, h), colorfmt='rgb')
            texture.blit_buffer(frame_rgb.flatten(), colorfmt='rgb', bufferfmt='ubyte')
            texture.flip_vertical()
            self.camera_image.texture = texture

            # Extract text every 5th frame to improve performance
            if hasattr(self, '_frame_count'):
                self._frame_count += 1
            else:
                self._frame_count = 0
                
            if self._frame_count % 5 == 0:
                threading.Thread(target=self._extract_text_async, args=(frame.copy(),), daemon=True).start()
            
            return True
        except Exception as e:
            logger.error(f"Camera update error: {e}")
            self.update_status(f"Camera Error: {e}")
            return False
    
    def _extract_text_async(self, frame):
        """Extract text from frame asynchronously."""
        try:
            lang_code = "amh" if self.language == "am-ET" else "eng"
            text = pytesseract.image_to_string(frame, lang=lang_code).strip()
            if text and len(text) > 3:  # Filter out noise
                self.save_note("Camera", text)
                Clock.schedule_once(lambda dt: self.update_result(f"Camera: {text}"), 0)
        except Exception as e:
            logger.error(f"Text extraction error: {e}")

    def start_audio_thread(self):
        """Start audio processing in a separate thread."""
        if not self.audio_thread or not self.audio_thread.is_alive():
            self.audio_thread = threading.Thread(target=self.audio_loop, daemon=True)
            self.audio_thread.start()
            logger.info("Audio thread started")

    def toggle_audio(self, instance):
        """Toggle audio processing."""
        if self.audio_btn.text == "Start Audio":
            self.audio_running = True
            self.audio_btn.text = "Stop Audio"
            self.start_audio_thread()
            self.update_status("Audio started")
        else:
            self.audio_running = False
            self.audio_btn.text = "Start Audio"
            self.update_status("Audio stopped")

    def audio_loop(self):
        """Real-time audio processing loop."""
        try:
            with sr.Microphone() as source:
                self.recognizer.adjust_for_ambient_noise(source, duration=1)
                logger.info("Audio calibration complete")
        except Exception as e:
            logger.error(f"Microphone setup error: {e}")
            Clock.schedule_once(lambda dt: self.update_status(f"Microphone Error: {e}"), 0)
            return
        
        while self.audio_running:
            try:
                with sr.Microphone() as source:
                    audio = self.recognizer.listen(source, timeout=1, phrase_time_limit=3)
                
                text = self.recognizer.recognize_google(audio, language=self.language)
                if text and len(text.strip()) > 2:
                    self.save_note("Audio", text)
                    Clock.schedule_once(lambda dt: self.update_result(f"Audio: {text}"), 0)
                    
                    if self.tts_enabled:
                        threading.Thread(target=self.play_tts, args=(text,), daemon=True).start()
                    
                    logger.info(f"Audio recognized: {text[:50]}...")
                    
            except sr.WaitTimeoutError:
                continue
            except sr.UnknownValueError:
                continue
            except sr.RequestError as e:
                logger.error(f"Audio API error: {e}")
                Clock.schedule_once(lambda dt: self.update_status(f"Audio API Error: {e}"), 0)
                time.sleep(5)  # Wait before retrying
            except Exception as e:
                logger.error(f"Audio loop error: {e}")
                Clock.schedule_once(lambda dt: self.update_status(f"Audio Error: {e}"), 0)
                time.sleep(1)

    def play_tts(self, text):
        """Play text-to-speech if enabled."""
        if not self.tts_enabled or len(text.strip()) < 3:
            return
            
        temp_file = None
        try:
            # Use temporary file for better cleanup
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                temp_file = f.name
                self.temp_files.append(temp_file)
            
            tts_lang = "am" if self.language == "am-ET" else "en"
            tts = gTTS(text=text[:200], lang=tts_lang, slow=False)  # Limit text length
            tts.save(temp_file)
            
            # Initialize pygame mixer if not already done
            if not pygame.mixer.get_init():
                pygame.mixer.init(frequency=22050, size=-16, channels=2, buffer=512)
            
            pygame.mixer.music.load(temp_file)
            pygame.mixer.music.play()
            
            # Don't block - let it play in background
            logger.info("TTS playback started")
            
        except Exception as e:
            logger.error(f"TTS error: {e}")
        finally:
            # Clean up temp file after a delay
            if temp_file:
                threading.Timer(10.0, self._cleanup_temp_file, args=(temp_file,)).start()
    
    def _cleanup_temp_file(self, filepath):
        """Clean up temporary file."""
        try:
            if os.path.exists(filepath):
                os.remove(filepath)
            if filepath in self.temp_files:
                self.temp_files.remove(filepath)
        except Exception as e:
            logger.error(f"Temp file cleanup error: {e}")

    def save_note(self, source, text):
        """Save extracted text to notes file with thread safety."""
        if not text or len(text.strip()) < 3:
            return
            
        try:
            with self.lock:
                # Ensure notes directory exists
                notes_path = Path(self.notes_file)
                notes_path.parent.mkdir(exist_ok=True)
                
                with open(self.notes_file, "a", encoding="utf-8") as f:
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    clean_text = text.replace('\n', ' ').strip()
                    f.write(f"[{timestamp}] {source}: {clean_text}\n")
                    f.flush()  # Ensure immediate write
                
                logger.info(f"Note saved from {source}: {clean_text[:50]}...")
        except Exception as e:
            logger.error(f"Save note error: {e}")
    
    def update_status(self, message):
        """Update status message safely."""
        if self.result_label:
            current_text = self.result_label.text
            self.result_label.text = f"Status: {message}\n{current_text[:500]}"
    
    def update_result(self, message):
        """Update result display safely."""
        if self.result_label:
            current_text = self.result_label.text
            self.result_label.text = f"{message}\n{current_text[:800]}"
    
    def stop_app(self, instance):
        """Properly stop the application."""
        logger.info("Stopping application...")
        self.cleanup()
        self.stop()
    
    def cleanup(self):
        """Clean up resources."""
        try:
            self.audio_running = False
            self.camera_running = False
            
            if self.camera:
                self.camera.release()
                self.camera = None
            
            if pygame.mixer.get_init():
                pygame.mixer.quit()
            
            # Clean up temp files
            for temp_file in self.temp_files[:]:
                try:
                    if os.path.exists(temp_file):
                        os.remove(temp_file)
                    self.temp_files.remove(temp_file)
                except Exception as e:
                    logger.error(f"Cleanup temp file error: {e}")
            
            logger.info("Cleanup completed")
        except Exception as e:
            logger.error(f"Cleanup error: {e}")
    
    def on_stop(self):
        """Called when app is closing."""
        self.cleanup()
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

if __name__ == "__main__":
    try:
        app = DeafHelperApp()
        app.run()
    except KeyboardInterrupt:
        logger.info("Application interrupted by user")
    except Exception as e:
        logger.error(f"Application error: {e}")
        print(f"Fatal error: {e}")