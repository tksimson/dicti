#!/usr/bin/env python3
"""
Basic test script for dictation app components.
"""

import sys
import time
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from audio.streaming_capture import StreamingAudioCapture
from whisper.streaming_engine import StreamingWhisperEngine
from hotkey.hotkey_manager import HotkeyManager
from ui.text_output import TextOutputHandler

def test_audio_capture():
    """Test audio capture functionality."""
    print("Testing audio capture...")
    
    capture = StreamingAudioCapture()
    
    if not capture.is_available():
        print("❌ Audio capture not available")
        return False
    
    print("✅ Audio capture available")
    
    # Test device listing
    devices = capture.get_audio_devices()
    print(f"Available audio devices: {len(devices)}")
    
    return True

def test_whisper_engine():
    """Test Whisper engine functionality."""
    print("Testing Whisper engine...")
    
    engine = StreamingWhisperEngine(model_size="tiny")  # Use tiny for faster testing
    
    if not engine.initialize():
        print("❌ Whisper engine initialization failed")
        return False
    
    print("✅ Whisper engine initialized")
    
    # Test model info
    info = engine.get_model_info()
    print(f"Model info: {info}")
    
    return True

def test_hotkey_manager():
    """Test hotkey manager functionality."""
    print("Testing hotkey manager...")
    
    manager = HotkeyManager()
    
    if not manager.is_available():
        print("❌ Hotkey manager not available")
        return False
    
    print("✅ Hotkey manager available")
    
    # Test available keys
    keys = manager.get_available_keys()
    print(f"Available keys: {keys}")
    
    return True

def test_text_output():
    """Test text output functionality."""
    print("Testing text output...")
    
    output = TextOutputHandler()
    
    if not output.is_available():
        print("❌ Text output not available")
        return False
    
    print("✅ Text output available")
    
    # Test text output
    output.start_output()
    output.output_text("Test text output")
    output.stop_output()
    
    print("✅ Text output test completed")
    
    return True

def main():
    """Run all tests."""
    print("Running basic component tests...\n")
    
    tests = [
        test_audio_capture,
        test_whisper_engine,
        test_hotkey_manager,
        test_text_output
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            if test():
                passed += 1
            print()
        except Exception as e:
            print(f"❌ Test failed with error: {e}\n")
    
    print(f"Tests completed: {passed}/{total} passed")
    
    if passed == total:
        print("🎉 All tests passed! The app should work.")
    else:
        print("⚠️  Some tests failed. Check the output above.")

if __name__ == "__main__":
    main()
