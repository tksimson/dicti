# Dictation App Specification

## Overview
A lightweight, offline dictation application built on Whisper and FFmpeg, designed for reliable speech-to-text conversion with automatic language detection for English and Polish.

## Core Requirements

### Technical Stack
- **Speech Recognition**: OpenAI Whisper (offline)
- **Audio Processing**: FFmpeg
- **Runtime Environment**: Python 3.13 virtual environment
- **Platform**: Debian 13 (Linux)
- **Language Support**: English and Polish (pre-downloaded models)

### Key Features
1. **Offline Operation**: No internet dependency for core functionality
2. **Real-time Streaming**: Continuous listening and typing as you speak
3. **Auto Language Detection**: Automatically distinguish between English and Polish
4. **Hotkey Activation**: Double-tap of Copilot key for instant activation/deactivation
5. **Smart Termination**: Auto-stop after 60 seconds of silence or manual double-tap
6. **Auto-start**: Launch automatically on system startup
7. **Lightweight**: Minimal system resource usage
8. **Reliable**: Robust error handling and recovery

### User Experience
- **Instant Activation**: Double-tap Copilot key → immediate continuous dictation mode
- **Real-time Typing**: Text appears as you speak, no waiting for processing
- **Continuous Listening**: Stays active until manually stopped or auto-termination
- **Smart Termination**: Auto-stops after 60 seconds of silence or double-tap to stop
- **Visual Feedback**: Clear indication of listening/processing/stopped states
- **Text Output**: Real-time text insertion at cursor position
- **Language Switching**: Automatic detection with manual override option
- **Error Handling**: Graceful degradation and user-friendly error messages

## Technical Architecture

### Core Components
1. **Audio Capture Module**: FFmpeg-based continuous audio input handling
2. **Streaming Whisper Engine**: Real-time speech-to-text processing with language detection
3. **Hotkey Manager**: Global hotkey detection, activation, and deactivation
4. **Language Detection**: Automatic English/Polish identification
5. **Text Output Handler**: Real-time text insertion at cursor position
6. **Silence Detection**: Auto-termination after 60 seconds of silence
7. **Configuration Manager**: Settings and model management
8. **Auto-start Service**: System integration for startup launch

### Model Strategy
- **Base Model**: Whisper base model for balanced performance/speed
- **Language Models**: Pre-downloaded English and Polish language packs
- **Model Caching**: Local storage with integrity verification
- **Fallback Strategy**: Graceful degradation if models unavailable

### Performance Targets
- **Activation Time**: < 500ms from hotkey to recording start
- **Streaming Latency**: < 1 second from speech to text appearance
- **Processing Chunks**: 2-3 second audio chunks for optimal balance
- **Memory Usage**: < 1GB RAM during operation
- **CPU Usage**: < 50% on modern multi-core systems
- **Storage**: < 2GB for models and dependencies
- **Silence Detection**: < 2 seconds to detect speech end

## System Integration

### Startup Integration
- **Desktop Entry**: Systemd user service for auto-start
- **Environment Setup**: Automatic virtual environment activation
- **Dependency Check**: Startup validation of required components
- **Background Service**: Minimal resource daemon mode

### Hotkey Implementation
- **Global Hotkey**: System-wide Copilot key detection
- **Double-tap Logic**: Precise timing detection (300-800ms window)
- **Toggle Functionality**: Double-tap to start/stop dictation
- **Focus Management**: Works across all applications
- **Conflict Avoidance**: Graceful handling of existing hotkey usage

## Configuration

### User Settings
- **Language Preferences**: Default language and detection sensitivity
- **Audio Settings**: Input device, sample rate, quality
- **Hotkey Customization**: Alternative key combinations
- **Silence Timeout**: Auto-termination delay (default 60 seconds)
- **Streaming Settings**: Chunk size, processing interval
- **Output Options**: Text destination (cursor position, clipboard, file)
- **Performance Tuning**: Model selection and processing parameters

### System Requirements
- **Python**: 3.13+
- **FFmpeg**: Latest stable version
- **Audio**: ALSA/PulseAudio support
- **Storage**: 2GB free space for models
- **RAM**: 4GB+ recommended
- **CPU**: Multi-core processor recommended

## Security & Privacy
- **Local Processing**: All audio processing happens locally
- **No Network**: No data transmission during operation
- **Temporary Files**: Secure cleanup of audio buffers
- **User Control**: Full control over data and processing

## Error Handling
- **Audio Issues**: Microphone access, device selection
- **Model Loading**: Graceful fallback and recovery
- **System Integration**: Hotkey conflicts, startup failures
- **Performance**: Resource monitoring and optimization
- **User Feedback**: Clear error messages and recovery suggestions

## Future Extensibility
- **Additional Languages**: Framework for adding more languages
- **Custom Models**: Support for fine-tuned models
- **API Integration**: Optional cloud services for enhanced accuracy
- **Plugin System**: Modular architecture for extensions
- **Advanced Features**: Punctuation, formatting, voice commands
