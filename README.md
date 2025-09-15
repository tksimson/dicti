# Dicti - Linux Live Dictation

A real-time speech-to-text dictation application built with Whisper and FFmpeg, designed for continuous listening and typing as you speak on Linux systems.

## Features

- **Real-time Streaming**: Continuous listening and typing as you speak
- **Auto Language Detection**: Automatically distinguish between English and Polish
- **Global Hotkey**: Double-tap Copilot key for instant activation/deactivation
- **Smart Termination**: Auto-stop after 60 seconds of silence or manual double-tap
- **Offline Operation**: No internet dependency for core functionality
- **Lightweight**: Minimal system resource usage

## Quick Start

### Prerequisites

- Python 3.13+
- FFmpeg installed
- Microphone access
- For full functionality: root privileges (for global hotkeys)

### Installation

1. Clone or download this repository
2. Create and activate virtual environment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

3. Install system dependencies (for clipboard support):
   ```bash
   sudo apt-get install xclip
   ```

### Usage

#### Demo Mode (No Root Required)
```bash
python3 demo.py
```

#### Full Application (Requires Root for Hotkeys)
```bash
sudo python3 main.py --model base --verbose
```

#### Command Line Options
```bash
python3 main.py --help
```

- `--model`: Whisper model size (tiny, base, small, medium, large)
- `--language`: Language code (en, pl) or auto-detect
- `--hotkey`: Global hotkey for activation
- `--verbose`: Enable verbose logging

## How It Works

1. **Activation**: Double-tap the Copilot key (or configured hotkey)
2. **Listening**: App continuously captures audio in 2-3 second chunks
3. **Processing**: Whisper processes each chunk in real-time
4. **Output**: Text appears at cursor position as you speak
5. **Termination**: Auto-stops after 60 seconds of silence or double-tap

## Architecture

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

## Components

- **StreamingAudioCapture**: Continuous FFmpeg-based audio input
- **StreamingWhisperEngine**: Real-time speech-to-text processing
- **HotkeyManager**: Global hotkey detection and toggle
- **TextOutputHandler**: Real-time text insertion at cursor
- **DictationApp**: Main application coordinator

## Performance

- **Activation Time**: < 500ms from hotkey to recording start
- **Streaming Latency**: < 1 second from speech to text appearance
- **Memory Usage**: < 1GB RAM during operation
- **CPU Usage**: < 50% on modern multi-core systems

## Troubleshooting

### Audio Issues
- Ensure microphone is working: `arecord -l`
- Check PulseAudio: `pulseaudio --check`

### Hotkey Issues
- Requires root privileges on Linux
- Alternative: Use `--hotkey` option to change key

### Clipboard Issues
- Install xclip: `sudo apt-get install xclip`
- Or install xsel: `sudo apt-get install xsel`

### Whisper Model Issues
- Models are downloaded automatically on first use
- Tiny model (~72MB) is fastest for testing
- Base model (~140MB) provides better accuracy

## Development

### Project Structure
```
dictation/
├── src/
│   ├── audio/          # Audio capture and processing
│   ├── whisper/        # Speech-to-text engine
│   ├── hotkey/         # Global hotkey handling
│   ├── config/         # Configuration management
│   ├── ui/             # User interface components
│   └── utils/          # Utility functions
├── models/             # Whisper model storage
├── config/             # Configuration files
├── scripts/            # Setup and utility scripts
├── tests/              # Test suite
└── docs/               # Documentation
```

### Testing
```bash
# Run basic tests
python3 test_simple.py

# Run component demo
python3 demo.py

# Run full app test
sudo python3 main.py --model tiny --verbose
```

## License

This project is for personal use. Please respect OpenAI's Whisper model license terms.

## Contributing

This is a personal project, but suggestions and improvements are welcome!

## Future Enhancements

- Additional language support
- Custom model fine-tuning
- Voice command integration
- Advanced punctuation and formatting
- Plugin system for extensions
