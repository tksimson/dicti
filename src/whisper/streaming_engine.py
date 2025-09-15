"""
Streaming Whisper engine for real-time speech-to-text processing.
"""

import whisper
import threading
import queue
import time
import tempfile
import os
from typing import Optional, Callable, Dict, Any
import logging
import numpy as np
import io

logger = logging.getLogger(__name__)


class StreamingWhisperEngine:
    """Real-time speech-to-text processing using Whisper with streaming chunks."""
    
    def __init__(self, 
                 model_size: str = "base",
                 language: Optional[str] = None,
                 chunk_duration: float = 2.5,
                 sample_rate: int = 16000):
        """
        Initialize streaming Whisper engine.
        
        Args:
            model_size: Whisper model size (tiny, base, small, medium, large)
            language: Language code (en, pl) or None for auto-detection
            chunk_duration: Duration of audio chunks in seconds
            sample_rate: Audio sample rate in Hz
        """
        self.model_size = model_size
        self.language = language
        self.chunk_duration = chunk_duration
        self.sample_rate = sample_rate
        
        self.model: Optional[whisper.Whisper] = None
        self.is_processing = False
        
        # Processing queue and thread
        self.audio_queue = queue.Queue()
        self.processing_thread: Optional[threading.Thread] = None
        
        # Callbacks
        self.on_text_result: Optional[Callable[[str, str], None]] = None  # (text, language)
        self.on_error: Optional[Callable[[Exception], None]] = None
        
        # Language detection
        self.detected_language = language or "en"
        self.language_confidence = 0.0
        
    def initialize(self) -> bool:
        """Initialize Whisper model."""
        try:
            logger.info(f"Loading Whisper model: {self.model_size}")
            import whisper
            # Use the correct Whisper API
            self.model = whisper.load_model(self.model_size)
            logger.info("Whisper model loaded successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to load Whisper model: {e}")
            if self.on_error:
                self.on_error(e)
            return False
    
    def start_processing(self) -> bool:
        """Start processing audio chunks."""
        if not self.model:
            logger.error("Model not initialized")
            return False
            
        if self.is_processing:
            logger.warning("Already processing")
            return False
            
        try:
            self.is_processing = True
            self.processing_thread = threading.Thread(target=self._process_audio_chunks, daemon=True)
            self.processing_thread.start()
            logger.info("Started Whisper processing")
            return True
        except Exception as e:
            logger.error(f"Failed to start processing: {e}")
            self.is_processing = False
            return False
    
    def stop_processing(self):
        """Stop processing audio chunks."""
        if not self.is_processing:
            return
            
        self.is_processing = False
        
        if self.processing_thread and self.processing_thread.is_alive():
            self.processing_thread.join(timeout=2.0)
            
        logger.info("Stopped Whisper processing")
    
    def process_audio_chunk(self, audio_data: bytes):
        """Add audio chunk to processing queue."""
        if not self.is_processing:
            return
            
        try:
            self.audio_queue.put(audio_data, timeout=0.1)
        except queue.Full:
            logger.warning("Audio queue full, dropping chunk")
    
    def _process_audio_chunks(self):
        """Internal method to process audio chunks from queue."""
        while self.is_processing:
            try:
                # Get audio chunk from queue
                audio_data = self.audio_queue.get(timeout=0.1)
                
                # Process the audio chunk
                self._process_single_chunk(audio_data)
                
                self.audio_queue.task_done()
                
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Error processing audio chunk: {e}")
                if self.on_error:
                    self.on_error(e)
    
    def _process_single_chunk(self, audio_data: bytes):
        """Process a single audio chunk."""
        try:
            # Convert bytes to numpy array
            audio_array = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0
            
            # Check if audio has sufficient content
            if np.max(np.abs(audio_array)) < 0.01:  # Very quiet audio
                return
            
            # Transcribe with Whisper
            result = self.model.transcribe(
                audio_array,
                language=self.language,
                fp16=False,  # Use fp32 for better compatibility
                verbose=False
            )
            
            # Extract text and language
            text = result["text"].strip()
            detected_lang = result.get("language", self.detected_language)
            
            if text:
                # Update language detection
                self._update_language_detection(detected_lang)
                
                # Send result to callback
                if self.on_text_result:
                    self.on_text_result(text, self.detected_language)
                
                logger.debug(f"Transcribed: '{text}' (lang: {self.detected_language})")
            
        except Exception as e:
            logger.error(f"Error processing audio chunk: {e}")
            if self.on_error:
                self.on_error(e)
    
    def _update_language_detection(self, detected_lang: str):
        """Update language detection with confidence."""
        if detected_lang != self.detected_language:
            # Simple language switching logic
            # In a more sophisticated implementation, we could use confidence scores
            if detected_lang in ["en", "pl"]:  # Only switch between supported languages
                self.detected_language = detected_lang
                logger.info(f"Language switched to: {detected_lang}")
    
    def set_text_result_callback(self, callback: Callable[[str, str], None]):
        """Set callback for when text results are ready."""
        self.on_text_result = callback
    
    def set_error_callback(self, callback: Callable[[Exception], None]):
        """Set callback for when errors occur."""
        self.on_error = callback
    
    def get_supported_languages(self) -> list:
        """Get list of supported languages."""
        return ["en", "pl"]  # English and Polish for this implementation
    
    def set_language(self, language: str):
        """Set specific language for transcription."""
        if language in self.get_supported_languages():
            self.language = language
            self.detected_language = language
            logger.info(f"Language set to: {language}")
        else:
            logger.warning(f"Unsupported language: {language}")
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get information about the loaded model."""
        if not self.model:
            return {}
            
        return {
            "model_size": self.model_size,
            "language": self.language,
            "detected_language": self.detected_language,
            "sample_rate": self.sample_rate,
            "chunk_duration": self.chunk_duration
        }
