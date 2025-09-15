# Dictation App Architecture

## System Overview

The dictation application follows a modular, event-driven architecture designed for reliability, performance, and maintainability. The system operates as a background service with minimal resource usage, activated by global hotkeys.

## Core Architecture

### High-Level Components

```
┌─────────────────────────────────────────────────────────────┐
│                    Dictation Application                    │
├─────────────────────────────────────────────────────────────┤
│  Global Hotkey Manager  │  Streaming Audio │  Streaming Whisper│
│  - Key Detection        │  - Continuous Cap │  - Real-time Proc │
│  - Toggle Logic         │  - Chunk Processing│  - Model Loading │
│  - Focus Management     │  - Silence Detect │  - Lang Detection│
├─────────────────────────────────────────────────────────────┤
│  Configuration Manager  │  Text Output     │  System Service │
│  - Settings Storage     │  - Cursor Insert │  - Auto-start   │
│  - Model Management     │  - Real-time Typing│  - Background   │
│  - User Preferences     │  - Auto-terminate│  - Monitoring   │
└─────────────────────────────────────────────────────────────┘
```

## Component Details

### 1. Global Hotkey Manager
**Purpose**: Handle system-wide hotkey detection and toggle functionality

**Responsibilities**:
- Monitor Copilot key globally across all applications
- Implement double-tap detection with precise timing
- Toggle dictation mode on/off with same hotkey
- Manage focus and prevent conflicts
- Trigger dictation mode activation/deactivation

**Key Classes**:
- `HotkeyManager`: Main hotkey detection and management
- `DoubleTapDetector`: Timing logic for double-tap recognition
- `ToggleManager`: Start/stop dictation mode management
- `FocusManager`: Handle application focus and context switching

### 2. Streaming Audio Pipeline
**Purpose**: Continuous audio capture and real-time processing for speech recognition

**Responsibilities**:
- Continuous audio capture from system microphone
- Real-time audio chunking (2-3 second segments)
- Convert audio formats for Whisper compatibility
- Implement silence detection for auto-termination
- Manage audio buffers and temporary files securely

**Key Classes**:
- `StreamingAudioCapture`: Continuous FFmpeg-based audio input
- `AudioChunker`: Real-time audio segmentation
- `SilenceDetector`: Detect speech end for auto-termination
- `AudioProcessor`: Format conversion and preprocessing
- `AudioValidator`: Quality checks and validation
- `BufferManager`: Audio buffer and temporary file handling

### 3. Streaming Whisper Engine
**Purpose**: Real-time speech-to-text conversion with continuous processing

**Responsibilities**:
- Load and manage Whisper models for streaming
- Process audio chunks in real-time (2-3 second segments)
- Detect language (English/Polish) automatically
- Provide streaming text output with minimal latency
- Handle concurrent processing of multiple chunks

**Key Classes**:
- `StreamingWhisperEngine`: Real-time speech-to-text processing
- `ModelManager`: Model loading and caching
- `LanguageDetector`: Automatic language identification
- `ChunkProcessor`: Individual audio chunk processing
- `StreamingQueue`: Real-time processing queue management

### 4. Configuration Manager
**Purpose**: Handle all application settings and preferences

**Responsibilities**:
- Store and retrieve user settings
- Manage model downloads and updates
- Handle audio device configuration
- Provide default values and validation

**Key Classes**:
- `ConfigManager`: Main configuration handling
- `ModelConfig`: Whisper model configuration
- `AudioConfig`: Audio device and quality settings
- `UserPreferences`: User-specific settings

### 5. Real-time Text Output Handler
**Purpose**: Manage real-time text output and insertion

**Responsibilities**:
- Insert text at current cursor position in active application
- Send text to system clipboard
- Save text to files
- Handle real-time text streaming
- Manage text formatting and punctuation
- Auto-termination after silence timeout

**Key Classes**:
- `RealtimeTextManager`: Main real-time output coordination
- `CursorTextInserter`: Insert text at cursor position
- `ClipboardHandler`: System clipboard integration
- `FileOutputHandler`: Text file management
- `AutoTerminator`: Silence-based auto-termination

### 6. System Service
**Purpose**: Integrate with system for auto-start and background operation

**Responsibilities**:
- Register as system service for auto-start
- Run in background with minimal resource usage
- Handle system integration and permissions
- Provide monitoring and health checks

**Key Classes**:
- `SystemService`: Main service management
- `StartupManager`: Auto-start configuration
- `ResourceMonitor`: System resource tracking
- `HealthChecker`: Service health validation

## Data Flow

### 1. Activation Flow
```
User Double-tap Copilot Key
         ↓
HotkeyManager detects activation
         ↓
StreamingAudioCapture starts continuous recording
         ↓
AudioChunker creates 2-3 second chunks
         ↓
StreamingWhisperEngine processes chunks in real-time
         ↓
LanguageDetector identifies language
         ↓
RealtimeTextManager inserts text at cursor
         ↓
SilenceDetector monitors for auto-termination
```

### 2. Continuous Processing Flow
```
Audio Chunk (2-3 seconds)
         ↓
SilenceDetector checks for speech
         ↓
If speech detected:
  - ChunkProcessor processes audio
  - LanguageDetector identifies language
  - TextInserter adds text to cursor
  - Reset silence timer
         ↓
If silence > 60 seconds:
  - AutoTerminator stops dictation
         ↓
If user double-tap:
  - ToggleManager stops dictation
```

### 3. Startup Flow
```
System Boot
         ↓
Systemd starts dictation service
         ↓
SystemService initializes components
         ↓
ModelManager loads Whisper models
         ↓
HotkeyManager registers global hotkey
         ↓
Application ready for activation
```

## Technology Stack

### Core Dependencies
- **Python 3.13**: Runtime environment
- **OpenAI Whisper**: Speech-to-text engine
- **FFmpeg**: Audio capture and processing
- **pynput**: Global hotkey detection
- **pyperclip**: Clipboard integration
- **pydub**: Audio processing and chunking
- **keyboard**: Advanced keyboard input simulation

### System Integration
- **Systemd**: Service management and auto-start
- **ALSA/PulseAudio**: Audio system integration
- **X11/Wayland**: Display system integration
- **Desktop Entry**: Application registration

### Development Tools
- **pytest**: Testing framework
- **black**: Code formatting
- **mypy**: Type checking
- **pre-commit**: Code quality hooks

## Performance Considerations

### Memory Management
- **Model Loading**: Lazy loading of Whisper models
- **Audio Buffering**: Efficient circular buffer implementation
- **Chunk Management**: Real-time audio chunk processing
- **Garbage Collection**: Explicit cleanup of temporary files
- **Resource Monitoring**: Continuous memory usage tracking

### Processing Optimization
- **Streaming Processing**: Real-time audio chunk processing
- **Async Processing**: Non-blocking audio and text processing
- **Model Caching**: Persistent model storage
- **Concurrent Processing**: Multiple chunks processed simultaneously
- **Resource Pooling**: Reuse of processing resources

### System Integration
- **Minimal Footprint**: Low resource usage when idle
- **Fast Activation**: Sub-500ms hotkey response
- **Efficient Processing**: Optimized audio-to-text pipeline
- **Graceful Degradation**: Fallback options for failures

## Security & Privacy

### Data Protection
- **Local Processing**: All audio processing happens locally
- **No Network**: No data transmission during operation
- **Temporary Files**: Secure cleanup of audio buffers
- **User Control**: Full control over data and processing

### System Security
- **Minimal Permissions**: Only required system access
- **Sandboxing**: Isolated processing environment
- **Input Validation**: Secure handling of all inputs
- **Error Handling**: No sensitive data in error messages

## Error Handling Strategy

### Component-Level Errors
- **Audio Issues**: Microphone access, device selection
- **Model Loading**: Graceful fallback and recovery
- **Hotkey Conflicts**: Alternative activation methods
- **Processing Failures**: Retry logic and user feedback

### System-Level Errors
- **Service Startup**: Dependency validation and recovery
- **Resource Exhaustion**: Monitoring and cleanup
- **Permission Issues**: User guidance and resolution
- **Hardware Failures**: Graceful degradation

## Monitoring & Logging

### Application Monitoring
- **Performance Metrics**: Processing time, memory usage
- **Error Tracking**: Failure rates and types
- **User Activity**: Usage patterns and preferences
- **System Health**: Resource availability and status

### Logging Strategy
- **Structured Logging**: JSON format for easy parsing
- **Log Levels**: DEBUG, INFO, WARNING, ERROR, CRITICAL
- **Rotation**: Automatic log file rotation
- **Privacy**: No sensitive data in logs

## Future Extensibility

### Plugin Architecture
- **Modular Design**: Easy addition of new components
- **Interface Standards**: Consistent APIs for extensions
- **Configuration**: Plugin-specific settings
- **Dependency Management**: Isolated plugin dependencies

### Feature Extensions
- **Additional Languages**: Framework for new language support
- **Custom Models**: Support for fine-tuned models
- **Advanced Features**: Punctuation, formatting, voice commands
- **API Integration**: Optional cloud services

## Deployment Architecture

### Installation Structure
```
/opt/dictation/           # Application files
├── bin/                  # Executables
├── lib/                  # Python modules
├── models/               # Whisper models
├── config/               # Configuration files
└── logs/                 # Log files

~/.config/dictation/      # User configuration
├── settings.json         # User preferences
├── models/               # User-specific models
└── logs/                 # User logs

~/.local/share/dictation/ # User data
├── cache/                # Cached data
└── temp/                 # Temporary files
```

### Service Integration
- **Systemd User Service**: `~/.config/systemd/user/dictation.service`
- **Desktop Entry**: `~/.local/share/applications/dictation.desktop`
- **Autostart**: Automatic service activation
- **Environment**: Proper PATH and environment setup
