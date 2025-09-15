# Changelog

All notable changes to Dicti - Linux Live Dictation will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2024-09-15

### Added
- Initial release of Dicti - Linux Live Dictation
- Real-time streaming audio capture using FFmpeg
- Whisper-based speech-to-text processing with auto language detection
- Global hotkey support for activation/deactivation (requires root)
- Continuous listening with 2-3 second audio chunks
- Auto-termination after 60 seconds of silence
- Support for English and Polish languages
- Real-time text insertion at cursor position
- Clipboard integration for text output
- Modular architecture with clean separation of concerns
- Comprehensive error handling and logging
- Demo mode for testing without root privileges
- Command-line interface with multiple options
- Virtual environment setup and dependency management

### Features
- **Streaming Audio Capture**: Continuous microphone input with silence detection
- **Streaming Whisper Engine**: Real-time speech processing with language detection
- **Global Hotkey Manager**: Double-tap activation with configurable keys
- **Text Output Handler**: Real-time text insertion and clipboard support
- **Main Application**: Coordinated component management

### Technical Details
- Python 3.13+ support
- FFmpeg for audio processing
- OpenAI Whisper for speech recognition
- NumPy for audio analysis
- Cross-platform keyboard input simulation
- Modular, event-driven architecture

### Known Limitations
- Global hotkeys require root privileges on Linux
- Clipboard support requires xclip or xsel installation
- Whisper models downloaded on first use (72MB+ for tiny model)
- Audio device detection limited to PulseAudio systems
