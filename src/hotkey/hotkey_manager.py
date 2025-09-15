"""
Global hotkey manager for dictation activation/deactivation.
"""

import keyboard
import threading
import time
from typing import Optional, Callable
import logging

logger = logging.getLogger(__name__)


class HotkeyManager:
    """Global hotkey detection and management for dictation toggle."""
    
    def __init__(self, 
                 hotkey: str = "copilot",
                 double_tap_window: float = 0.8):
        """
        Initialize hotkey manager.
        
        Args:
            hotkey: Key to monitor (e.g., "copilot", "ctrl+alt+d")
            double_tap_window: Time window for double-tap detection in seconds
        """
        self.hotkey = hotkey
        self.double_tap_window = double_tap_window
        
        self.is_listening = False
        self.last_tap_time = 0.0
        self.tap_count = 0
        
        # Callbacks
        self.on_activation: Optional[Callable[[], None]] = None
        self.on_deactivation: Optional[Callable[[], None]] = None
        
        # Threading
        self.listener_thread: Optional[threading.Thread] = None
        
    def start_listening(self) -> bool:
        """Start listening for hotkey presses."""
        if self.is_listening:
            logger.warning("Already listening for hotkeys")
            return False
            
        try:
            self.is_listening = True
            self.listener_thread = threading.Thread(target=self._listen_for_hotkeys, daemon=True)
            self.listener_thread.start()
            logger.info(f"Started listening for hotkey: {self.hotkey}")
            return True
        except Exception as e:
            logger.error(f"Failed to start hotkey listening: {e}")
            self.is_listening = False
            return False
    
    def stop_listening(self):
        """Stop listening for hotkey presses."""
        if not self.is_listening:
            return
            
        self.is_listening = False
        
        if self.listener_thread and self.listener_thread.is_alive():
            self.listener_thread.join(timeout=1.0)
            
        logger.info("Stopped listening for hotkeys")
    
    def _listen_for_hotkeys(self):
        """Internal method to listen for hotkey presses."""
        try:
            # Register hotkey callback
            keyboard.on_press_key(self.hotkey, self._on_hotkey_press)
            
            # Keep the thread alive
            while self.is_listening:
                time.sleep(0.1)
                
        except Exception as e:
            logger.error(f"Error in hotkey listening: {e}")
        finally:
            # Clean up
            try:
                keyboard.unhook_all()
            except:
                pass
    
    def _on_hotkey_press(self, event):
        """Handle hotkey press event."""
        if not self.is_listening:
            return
            
        current_time = time.time()
        
        # Check if this is within the double-tap window
        if current_time - self.last_tap_time <= self.double_tap_window:
            self.tap_count += 1
        else:
            self.tap_count = 1
        
        self.last_tap_time = current_time
        
        # Check for double-tap
        if self.tap_count == 2:
            logger.info("Double-tap detected, toggling dictation")
            self._toggle_dictation()
            self.tap_count = 0  # Reset after action
    
    def _toggle_dictation(self):
        """Toggle dictation on/off."""
        # This is a simple toggle - in a real implementation,
        # you'd track the current state and call appropriate callbacks
        if self.on_activation:
            self.on_activation()
        elif self.on_deactivation:
            self.on_deactivation()
    
    def set_activation_callback(self, callback: Callable[[], None]):
        """Set callback for dictation activation."""
        self.on_activation = callback
    
    def set_deactivation_callback(self, callback: Callable[[], None]):
        """Set callback for dictation deactivation."""
        self.on_deactivation = callback
    
    def is_available(self) -> bool:
        """Check if hotkey detection is available."""
        try:
            # Test if we can register a hotkey
            keyboard.on_press_key("test", lambda x: None)
            keyboard.unhook_all()
            return True
        except Exception as e:
            logger.warning(f"Hotkey detection not available: {e}")
            return False
    
    def get_available_keys(self) -> list:
        """Get list of available keys for hotkey detection."""
        # Common keys that work well for global hotkeys
        return [
            "copilot",
            "ctrl+alt+d",
            "ctrl+alt+space",
            "ctrl+shift+d",
            "alt+space",
            "f12"
        ]
    
    def set_hotkey(self, new_hotkey: str) -> bool:
        """Change the hotkey combination."""
        if self.is_listening:
            logger.warning("Cannot change hotkey while listening")
            return False
            
        try:
            # Test if the new hotkey is valid
            keyboard.on_press_key(new_hotkey, lambda x: None)
            keyboard.unhook_all()
            
            self.hotkey = new_hotkey
            logger.info(f"Hotkey changed to: {new_hotkey}")
            return True
        except Exception as e:
            logger.error(f"Invalid hotkey: {new_hotkey}, error: {e}")
            return False
