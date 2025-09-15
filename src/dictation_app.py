"""
Main dictation application that coordinates all components.
"""

import logging
import time
import threading
from typing import Optional
from src.audio.streaming_capture import StreamingAudioCapture
from src.whisper.streaming_engine import StreamingWhisperEngine
from src.hotkey.hotkey_manager import HotkeyManager
from src.ui.text_output import TextOutputHandler

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DictationApp:
    """Main dictation application with real-time streaming capabilities."""
    
    def __init__(self, 
                 model_size: str = "base",
                 language: Optional[str] = None,
                 hotkey: str = "copilot"):
        """
        Initialize dictation application.
        
        Args:
            model_size: Whisper model size
            language: Language code or None for auto-detection
            hotkey: Global hotkey for activation
        """
        self.model_size = model_size
        self.language = language
        self.hotkey = hotkey
        
        # Application state
        self.is_running = False
        self.is_dictating = False
        
        # Initialize components
        self.audio_capture = StreamingAudioCapture()
        self.whisper_engine = StreamingWhisperEngine(
            model_size=model_size,
            language=language
        )
        self.hotkey_manager = HotkeyManager(hotkey=hotkey)
        self.text_output = TextOutputHandler()
        
        # Setup component callbacks
        self._setup_callbacks()
        
        logger.info("Dictation app initialized")
    
    def _setup_callbacks(self):
        """Setup callbacks between components."""
        # Audio capture callbacks
        self.audio_capture.set_audio_chunk_callback(self._on_audio_chunk)
        self.audio_capture.set_silence_detected_callback(self._on_silence_detected)
        
        # Whisper engine callbacks
        self.whisper_engine.set_text_result_callback(self._on_text_result)
        self.whisper_engine.set_error_callback(self._on_whisper_error)
        
        # Hotkey manager callbacks
        self.hotkey_manager.set_activation_callback(self._on_hotkey_activation)
        self.hotkey_manager.set_deactivation_callback(self._on_hotkey_deactivation)
        
        # Text output callbacks
        self.text_output.set_text_output_callback(self._on_text_output)
        self.text_output.set_error_callback(self._on_text_output_error)
    
    def start(self) -> bool:
        """Start the dictation application."""
        if self.is_running:
            logger.warning("Application already running")
            return False
        
        try:
            logger.info("Starting dictation application...")
            
            # Initialize Whisper model
            if not self.whisper_engine.initialize():
                logger.error("Failed to initialize Whisper engine")
                return False
            
            # Start hotkey listening
            if not self.hotkey_manager.start_listening():
                logger.error("Failed to start hotkey listening")
                return False
            
            self.is_running = True
            logger.info("Dictation application started successfully")
            logger.info(f"Press {self.hotkey} twice quickly to start/stop dictation")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to start application: {e}")
            self.is_running = False
            return False
    
    def stop(self):
        """Stop the dictation application."""
        if not self.is_running:
            return
        
        logger.info("Stopping dictation application...")
        
        # Stop dictation if active
        if self.is_dictating:
            self._stop_dictation()
        
        # Stop all components
        self.hotkey_manager.stop_listening()
        self.whisper_engine.stop_processing()
        self.audio_capture.stop_recording()
        self.text_output.stop_output()
        
        self.is_running = False
        logger.info("Dictation application stopped")
    
    def _on_hotkey_activation(self):
        """Handle hotkey activation (start dictation)."""
        if not self.is_running or self.is_dictating:
            return
        
        logger.info("Starting dictation...")
        self._start_dictation()
    
    def _on_hotkey_deactivation(self):
        """Handle hotkey deactivation (stop dictation)."""
        if not self.is_running or not self.is_dictating:
            return
        
        logger.info("Stopping dictation...")
        self._stop_dictation()
    
    def _start_dictation(self):
        """Start dictation mode."""
        try:
            # Start text output
            if not self.text_output.start_output():
                logger.error("Failed to start text output")
                return
            
            # Start Whisper processing
            if not self.whisper_engine.start_processing():
                logger.error("Failed to start Whisper processing")
                return
            
            # Start audio capture
            if not self.audio_capture.start_recording():
                logger.error("Failed to start audio capture")
                return
            
            self.is_dictating = True
            logger.info("Dictation started - speak now!")
            
        except Exception as e:
            logger.error(f"Failed to start dictation: {e}")
            self._stop_dictation()
    
    def _stop_dictation(self):
        """Stop dictation mode."""
        try:
            # Stop audio capture
            self.audio_capture.stop_recording()
            
            # Stop Whisper processing
            self.whisper_engine.stop_processing()
            
            # Stop text output
            self.text_output.stop_output()
            
            self.is_dictating = False
            logger.info("Dictation stopped")
            
        except Exception as e:
            logger.error(f"Error stopping dictation: {e}")
    
    def _on_audio_chunk(self, audio_data: bytes):
        """Handle audio chunk from capture."""
        if self.is_dictating:
            self.whisper_engine.process_audio_chunk(audio_data)
    
    def _on_silence_detected(self):
        """Handle silence timeout."""
        logger.info("Silence detected, stopping dictation")
        self._stop_dictation()
    
    def _on_text_result(self, text: str, language: str):
        """Handle text result from Whisper."""
        if self.is_dictating:
            self.text_output.output_text(text, language)
    
    def _on_whisper_error(self, error: Exception):
        """Handle Whisper engine error."""
        logger.error(f"Whisper error: {error}")
        self._stop_dictation()
    
    def _on_text_output(self, text: str):
        """Handle text output."""
        logger.debug(f"Text output: {text}")
    
    def _on_text_output_error(self, error: Exception):
        """Handle text output error."""
        logger.error(f"Text output error: {error}")
    
    def get_status(self) -> dict:
        """Get application status."""
        return {
            "is_running": self.is_running,
            "is_dictating": self.is_dictating,
            "model_size": self.model_size,
            "language": self.language,
            "hotkey": self.hotkey,
            "audio_available": self.audio_capture.is_available(),
            "hotkey_available": self.hotkey_manager.is_available(),
            "text_output_available": self.text_output.is_available()
        }
    
    def set_language(self, language: str):
        """Set language for transcription."""
        self.whisper_engine.set_language(language)
        self.language = language
        logger.info(f"Language set to: {language}")
    
    def set_hotkey(self, hotkey: str):
        """Change global hotkey."""
        if self.hotkey_manager.set_hotkey(hotkey):
            self.hotkey = hotkey
            logger.info(f"Hotkey changed to: {hotkey}")
        else:
            logger.error(f"Failed to change hotkey to: {hotkey}")
    
    def run_interactive(self):
        """Run application in interactive mode."""
        if not self.start():
            logger.error("Failed to start application")
            return
        
        try:
            logger.info("Application running. Press Ctrl+C to exit.")
            while self.is_running:
                time.sleep(0.1)
        except KeyboardInterrupt:
            logger.info("Received interrupt signal")
        finally:
            self.stop()
