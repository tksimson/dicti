"""
Streaming audio capture using FFmpeg for real-time dictation.
"""

import ffmpeg
import threading
import queue
import time
import tempfile
import os
from typing import Optional, Callable, Generator
import numpy as np
import logging

logger = logging.getLogger(__name__)


class StreamingAudioCapture:
    """Continuous audio capture with real-time chunking for streaming dictation."""
    
    def __init__(self, 
                 sample_rate: int = 16000,
                 chunk_duration: float = 2.5,
                 silence_threshold: float = 0.01,
                 silence_timeout: float = 60.0):
        """
        Initialize streaming audio capture.
        
        Args:
            sample_rate: Audio sample rate in Hz
            chunk_duration: Duration of each audio chunk in seconds
            silence_threshold: Threshold for silence detection (0.0-1.0)
            silence_timeout: Timeout for auto-stop after silence in seconds
        """
        self.sample_rate = sample_rate
        self.chunk_duration = chunk_duration
        self.silence_threshold = silence_threshold
        self.silence_timeout = silence_timeout
        
        self.is_recording = False
        self.audio_queue = queue.Queue()
        self.silence_timer = 0.0
        self.last_audio_time = time.time()
        
        self.recording_thread: Optional[threading.Thread] = None
        self.chunk_thread: Optional[threading.Thread] = None
        
        # Callbacks
        self.on_audio_chunk: Optional[Callable[[bytes], None]] = None
        self.on_silence_detected: Optional[Callable[[], None]] = None
        
    def start_recording(self) -> bool:
        """Start continuous audio recording."""
        if self.is_recording:
            logger.warning("Already recording")
            return False
            
        try:
            self.is_recording = True
            self.silence_timer = 0.0
            self.last_audio_time = time.time()
            
            # Start recording thread
            self.recording_thread = threading.Thread(target=self._record_audio, daemon=True)
            self.recording_thread.start()
            
            # Start chunk processing thread
            self.chunk_thread = threading.Thread(target=self._process_chunks, daemon=True)
            self.chunk_thread.start()
            
            logger.info("Started streaming audio capture")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start recording: {e}")
            self.is_recording = False
            return False
    
    def stop_recording(self):
        """Stop continuous audio recording."""
        if not self.is_recording:
            return
            
        self.is_recording = False
        
        # Wait for threads to finish
        if self.recording_thread and self.recording_thread.is_alive():
            self.recording_thread.join(timeout=1.0)
        if self.chunk_thread and self.chunk_thread.is_alive():
            self.chunk_thread.join(timeout=1.0)
            
        logger.info("Stopped streaming audio capture")
    
    def _record_audio(self):
        """Internal method to record audio using FFmpeg."""
        try:
            # Create FFmpeg input stream for microphone
            input_stream = ffmpeg.input(
                'default',  # Use default audio input
                f='pulse',  # PulseAudio format
                ar=self.sample_rate,
                ac=1,  # Mono
                t=None  # No time limit
            )
            
            # Create output stream to raw audio data
            output_stream = ffmpeg.output(
                input_stream,
                'pipe:',
                f='s16le',  # 16-bit signed little-endian
                acodec='pcm_s16le'
            )
            
            # Start FFmpeg process
            process = ffmpeg.run_async(output_stream, pipe_stdout=True, pipe_stderr=True)
            
            # Read audio data in chunks
            chunk_size = int(self.sample_rate * self.chunk_duration * 2)  # 2 bytes per sample
            
            while self.is_recording:
                try:
                    audio_data = process.stdout.read(chunk_size)
                    if not audio_data:
                        break
                        
                    # Put audio data in queue for processing
                    self.audio_queue.put(audio_data)
                    self.last_audio_time = time.time()
                    
                except Exception as e:
                    logger.error(f"Error reading audio data: {e}")
                    break
            
            # Clean up
            process.terminate()
            process.wait()
            
        except Exception as e:
            logger.error(f"Error in audio recording: {e}")
    
    def _process_chunks(self):
        """Internal method to process audio chunks and detect silence."""
        while self.is_recording:
            try:
                # Get audio chunk from queue with timeout
                audio_data = self.audio_queue.get(timeout=0.1)
                
                # Convert to numpy array for analysis
                audio_array = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0
                
                # Check for silence
                if self._is_silence(audio_array):
                    self.silence_timer += self.chunk_duration
                    
                    # Check for silence timeout
                    if self.silence_timer >= self.silence_timeout:
                        logger.info("Silence timeout reached, stopping recording")
                        if self.on_silence_detected:
                            self.on_silence_detected()
                        break
                else:
                    # Reset silence timer
                    self.silence_timer = 0.0
                    
                    # Send audio chunk to callback
                    if self.on_audio_chunk:
                        self.on_audio_chunk(audio_data)
                
                self.audio_queue.task_done()
                
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Error processing audio chunk: {e}")
    
    def _is_silence(self, audio_array: np.ndarray) -> bool:
        """Check if audio array is silence based on volume threshold."""
        try:
            # Calculate RMS (Root Mean Square) volume
            rms = np.sqrt(np.mean(audio_array ** 2))
            
            # Check if RMS is below threshold
            return rms < self.silence_threshold
            
        except Exception as e:
            logger.error(f"Error checking silence: {e}")
            return False
    
    def set_audio_chunk_callback(self, callback: Callable[[bytes], None]):
        """Set callback for when audio chunks are ready."""
        self.on_audio_chunk = callback
    
    def set_silence_detected_callback(self, callback: Callable[[], None]):
        """Set callback for when silence timeout is reached."""
        self.on_silence_detected = callback
    
    def get_audio_devices(self) -> list:
        """Get list of available audio input devices."""
        try:
            # Use FFmpeg to list audio devices
            probe = ffmpeg.probe('default', f='pulse')
            devices = []
            
            for stream in probe.get('streams', []):
                if stream.get('codec_type') == 'audio':
                    devices.append({
                        'name': stream.get('tags', {}).get('device.description', 'Unknown'),
                        'index': stream.get('index', 0)
                    })
            
            return devices
            
        except Exception as e:
            logger.error(f"Error getting audio devices: {e}")
            return []
    
    def is_available(self) -> bool:
        """Check if audio capture is available."""
        try:
            # Test if we can access audio input
            test_input = ffmpeg.input('default', f='pulse', t=0.1)
            test_output = ffmpeg.output(test_input, 'pipe:', f='null')
            ffmpeg.run(test_output, capture_stdout=True, capture_stderr=True)
            return True
        except Exception:
            return False
