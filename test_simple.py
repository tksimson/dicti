#!/usr/bin/env python3
"""
Simple test script for dictation app - focuses on core functionality.
"""

import sys
import time
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

def test_whisper_import():
    """Test Whisper import and basic functionality."""
    print("Testing Whisper import...")
    
    try:
        import whisper
        print("✅ Whisper imported successfully")
        
        # Test loading a tiny model (fastest)
        print("Loading tiny model...")
        model = whisper.load_model("tiny")
        print("✅ Tiny model loaded successfully")
        
        return True
    except Exception as e:
        print(f"❌ Whisper test failed: {e}")
        return False

def test_audio_capture():
    """Test audio capture without full initialization."""
    print("Testing audio capture...")
    
    try:
        from audio.streaming_capture import StreamingAudioCapture
        capture = StreamingAudioCapture()
        
        if capture.is_available():
            print("✅ Audio capture available")
            return True
        else:
            print("❌ Audio capture not available")
            return False
    except Exception as e:
        print(f"❌ Audio capture test failed: {e}")
        return False

def test_basic_functionality():
    """Test basic app functionality."""
    print("Testing basic app functionality...")
    
    try:
        from dictation_app import DictationApp
        
        # Create app with tiny model for testing
        app = DictationApp(model_size="tiny")
        
        # Check status
        status = app.get_status()
        print(f"App status: {status}")
        
        print("✅ Basic app functionality works")
        return True
    except Exception as e:
        print(f"❌ Basic functionality test failed: {e}")
        return False

def main():
    """Run simple tests."""
    print("Running simple component tests...\n")
    
    tests = [
        test_whisper_import,
        test_audio_capture,
        test_basic_functionality
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
        print("🎉 All core tests passed! The app should work.")
        print("\nTo run the full app:")
        print("  python3 main.py --model tiny --verbose")
    else:
        print("⚠️  Some tests failed. Check the output above.")

if __name__ == "__main__":
    main()
