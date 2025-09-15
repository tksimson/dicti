"""
Real-time text output handler for dictation results.
"""

import pyperclip
import keyboard
import time
from typing import Optional, Callable
import logging

logger = logging.getLogger(__name__)


class TextOutputHandler:
    """Handle real-time text output for dictation results."""
    
    def __init__(self, 
                 output_method: str = "cursor",
                 auto_punctuation: bool = True):
        """
        Initialize text output handler.
        
        Args:
            output_method: Method for text output ("cursor", "clipboard", "both")
            auto_punctuation: Whether to add automatic punctuation
        """
        self.output_method = output_method
        self.auto_punctuation = auto_punctuation
        
        # State tracking
        self.is_active = False
        self.last_text = ""
        self.text_buffer = ""
        
        # Callbacks
        self.on_text_output: Optional[Callable[[str], None]] = None
        self.on_error: Optional[Callable[[Exception], None]] = None
    
    def start_output(self) -> bool:
        """Start text output handling."""
        if self.is_active:
            logger.warning("Text output already active")
            return False
            
        try:
            self.is_active = True
            self.text_buffer = ""
            logger.info(f"Started text output: {self.output_method}")
            return True
        except Exception as e:
            logger.error(f"Failed to start text output: {e}")
            if self.on_error:
                self.on_error(e)
            return False
    
    def stop_output(self):
        """Stop text output handling."""
        if not self.is_active:
            return
            
        self.is_active = False
        logger.info("Stopped text output")
    
    def output_text(self, text: str, language: str = "en"):
        """Output text using the configured method."""
        if not self.is_active or not text.strip():
            return
            
        try:
            # Clean and process text
            processed_text = self._process_text(text, language)
            
            if not processed_text:
                return
            
            # Output based on method
            if self.output_method in ["cursor", "both"]:
                self._output_to_cursor(processed_text)
            
            if self.output_method in ["clipboard", "both"]:
                self._output_to_clipboard(processed_text)
            
            # Update state
            self.last_text = processed_text
            self.text_buffer += processed_text
            
            # Call callback
            if self.on_text_output:
                self.on_text_output(processed_text)
                
            logger.debug(f"Output text: '{processed_text}'")
            
        except Exception as e:
            logger.error(f"Error outputting text: {e}")
            if self.on_error:
                self.on_error(e)
    
    def _process_text(self, text: str, language: str) -> str:
        """Process text before output."""
        # Clean whitespace
        text = text.strip()
        
        if not text:
            return ""
        
        # Add space if needed
        if self.text_buffer and not self.text_buffer.endswith(" ") and not text.startswith(" "):
            text = " " + text
        
        # Auto-punctuation for common cases
        if self.auto_punctuation:
            text = self._add_auto_punctuation(text, language)
        
        return text
    
    def _add_auto_punctuation(self, text: str, language: str) -> str:
        """Add automatic punctuation to text."""
        # Simple auto-punctuation rules
        text = text.strip()
        
        if not text:
            return text
        
        # Don't add punctuation if it already ends with punctuation
        if text[-1] in ".!?;:":
            return text
        
        # Add period for statements (simple heuristic)
        if len(text) > 10 and not text.endswith(("?", "!", ":", ";")):
            # Check if it looks like a complete sentence
            if any(word in text.lower() for word in ["is", "are", "was", "were", "will", "can", "should"]):
                text += "."
        
        return text
    
    def _output_to_cursor(self, text: str):
        """Output text at cursor position by simulating typing."""
        try:
            # Type the text character by character
            for char in text:
                keyboard.write(char)
                time.sleep(0.01)  # Small delay for realistic typing
                
        except Exception as e:
            logger.error(f"Error typing text: {e}")
            # Fallback to clipboard if typing fails
            self._output_to_clipboard(text)
    
    def _output_to_clipboard(self, text: str):
        """Output text to clipboard."""
        try:
            pyperclip.copy(text)
            logger.debug("Text copied to clipboard")
        except Exception as e:
            logger.error(f"Error copying to clipboard: {e}")
    
    def clear_buffer(self):
        """Clear the text buffer."""
        self.text_buffer = ""
        self.last_text = ""
        logger.debug("Text buffer cleared")
    
    def get_buffer(self) -> str:
        """Get current text buffer."""
        return self.text_buffer
    
    def set_output_method(self, method: str):
        """Change output method."""
        if method in ["cursor", "clipboard", "both"]:
            self.output_method = method
            logger.info(f"Output method changed to: {method}")
        else:
            logger.warning(f"Invalid output method: {method}")
    
    def set_auto_punctuation(self, enabled: bool):
        """Enable/disable auto-punctuation."""
        self.auto_punctuation = enabled
        logger.info(f"Auto-punctuation {'enabled' if enabled else 'disabled'}")
    
    def set_text_output_callback(self, callback: Callable[[str], None]):
        """Set callback for when text is output."""
        self.on_text_output = callback
    
    def set_error_callback(self, callback: Callable[[Exception], None]):
        """Set callback for when errors occur."""
        self.on_error = callback
    
    def is_available(self) -> bool:
        """Check if text output is available."""
        try:
            # Test clipboard access
            pyperclip.copy("test")
            pyperclip.paste()
            return True
        except Exception as e:
            logger.warning(f"Text output not available: {e}")
            return False
