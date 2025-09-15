#!/usr/bin/env python3
"""
Demo script for Dicti - Linux Live Dictation (works without root privileges).
"""

import sys
import time
import threading
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from audio.streaming_capture import StreamingAudioCapture
from whisper.streaming_engine import StreamingWhisperEngine
from ui.text_output import TextOutputHandler

def demo_audio_capture():
    """Demo audio capture functionality."""
    print("🎤 Audio Capture Demo")
    print("=" * 50)
    
    capture = StreamingAudioCapture()
    
    if not capture.is_available():
        print("❌ Audio capture not available")
        return False
    
    print("✅ Audio capture available")
    
    # Set up callbacks
    def on_audio_chunk(audio_data):
        print(f"📡 Received audio chunk: {len(audio_data)} bytes")
    
    def on_silence():
        print("🔇 Silence detected - stopping recording")
        capture.stop_recording()
    
    capture.set_audio_chunk_callback(on_audio_chunk)
    capture.set_silence_detected_callback(on_silence)
    
    print("Starting 5-second audio capture test...")
    print("Speak into your microphone now!")
    
    if capture.start_recording():
        time.sleep(5)  # Record for 5 seconds
        capture.stop_recording()
        print("✅ Audio capture demo completed")
        return True
    else:
        print("❌ Failed to start audio capture")
        return False

def demo_whisper_processing():
    """Demo Whisper processing functionality."""
    print("\n🤖 Whisper Processing Demo")
    print("=" * 50)
    
    engine = StreamingWhisperEngine(model_size="tiny")
    
    if not engine.initialize():
        print("❌ Whisper engine initialization failed")
        return False
    
    print("✅ Whisper engine initialized")
    
    # Set up callbacks
    def on_text_result(text, language):
        print(f"📝 Transcribed: '{text}' (lang: {language})")
    
    def on_error(error):
        print(f"❌ Whisper error: {error}")
    
    engine.set_text_result_callback(on_text_result)
    engine.set_error_callback(on_error)
    
    print("Starting Whisper processing...")
    
    if engine.start_processing():
        print("✅ Whisper processing started")
        print("Note: This demo doesn't include audio input")
        time.sleep(2)
        engine.stop_processing()
        print("✅ Whisper processing demo completed")
        return True
    else:
        print("❌ Failed to start Whisper processing")
        return False

def demo_text_output():
    """Demo text output functionality."""
    print("\n📝 Text Output Demo")
    print("=" * 50)
    
    output = TextOutputHandler(output_method="clipboard")
    
    if not output.is_available():
        print("❌ Text output not available")
        print("Note: Install xclip for clipboard support: sudo apt-get install xclip")
        return False
    
    print("✅ Text output available")
    
    if output.start_output():
        print("Testing text output...")
        output.output_text("Hello, this is a test of the dictation app!")
        output.output_text("This text should appear in your clipboard.")
        output.stop_output()
        print("✅ Text output demo completed")
        print("Check your clipboard for the test text!")
        return True
    else:
        print("❌ Failed to start text output")
        return False

def main():
    """Run all demos."""
    print("🎯 Dicti - Linux Live Dictation Demo")
    print("=" * 50)
    print("This demo tests the core components without requiring root privileges.")
    print()
    
    demos = [
        ("Audio Capture", demo_audio_capture),
        ("Whisper Processing", demo_whisper_processing),
        ("Text Output", demo_text_output)
    ]
    
    passed = 0
    total = len(demos)
    
    for name, demo_func in demos:
        try:
            if demo_func():
                passed += 1
        except Exception as e:
            print(f"❌ {name} demo failed: {e}")
        print()
    
    print("=" * 50)
    print(f"Demo completed: {passed}/{total} components working")
    
    if passed == total:
        print("🎉 All components are working!")
        print("\nTo run the full app with hotkeys:")
        print("  sudo python3 main.py --model tiny --verbose")
        print("\nNote: Hotkeys require root privileges on Linux")
    else:
        print("⚠️  Some components need attention:")
        if passed < 3:
            print("  - Install xclip for clipboard support: sudo apt-get install xclip")
        print("  - Run with sudo for hotkey support")

if __name__ == "__main__":
    main()
