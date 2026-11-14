"""Read text from stdin aloud with Supertonic 3, for `dicti --speak-toggle`.

    echo "Dzień dobry" | python -m dicti.tts_worker

Runs in the parakeet venv (sherpa-onnx + numpy, install/03b and 03c) so dicti itself stays
stdlib. Voice and speed come from the panel menu (speak.settings()). One sentence at a time
is synthesized, each in its own language, and piped straight into pw-play: speech starts
after the first sentence, and nothing is written to disk. The text arrives on stdin, never
argv, which other users can read in ps.
"""

from __future__ import annotations

import os
import queue
import signal
import subprocess
import sys
import threading
from pathlib import Path

from dicti import memo
from dicti import speak as speak_mod

STEPS = 8         # flow-matching steps: 6 starts ~0.5s sooner but sounds audibly worse
PAUSE_SEC = 0.12  # between sentences, tuned by ear
THREADS = 4


def load_tts(model: Path):
    import sherpa_onnx

    if not (model / "vocoder.onnx").exists():
        raise FileNotFoundError(f"no voice model in {model}, run install/03c-install-tts.sh")
    return sherpa_onnx.OfflineTts(sherpa_onnx.OfflineTtsConfig(
        model=sherpa_onnx.OfflineTtsModelConfig(
            supertonic=sherpa_onnx.OfflineTtsSupertonicModelConfig(
                duration_predictor=str(model / "duration_predictor.onnx"),
                text_encoder=str(model / "text_encoder.onnx"),
                vector_estimator=str(model / "vector_estimator.onnx"),
                vocoder=str(model / "vocoder.onnx"),
                tts_json=str(model / "tts.json"),
                unicode_indexer=str(model / "unicode_indexer.bin"),
                voice_style=str(model / "voice.bin")),
            num_threads=THREADS)))


def speak(text: str) -> int:
    import numpy as np
    import sherpa_onnx

    chosen = speak_mod.settings()
    sid = speak_mod.VOICES[chosen["voice"]]
    rate = speak_mod.SPEEDS[chosen["speed"]]
    tts = load_tts(speak_mod.MODEL_DIR)
    pause = np.zeros(int(PAUSE_SEC * tts.sample_rate), np.float32).tobytes()
    player = subprocess.Popen(
        ["pw-play", "--raw", f"--rate={tts.sample_rate}", "--channels=1", "--format=f32", "-"],
        stdin=subprocess.PIPE)
    # The pipe holds well under a second of audio, so writing from this thread would stall
    # synthesis and leave a gap before every sentence. A feeder thread plays while the next
    # sentence is synthesized.
    chunks: queue.Queue[bytes | None] = queue.Queue()
    feeder = threading.Thread(target=_feed, args=(player, chunks), daemon=True)
    feeder.start()
    for i, sentence in enumerate(speak_mod.sentences(text)):
        if player.poll() is not None:  # pw-play gone (the stop key) = stop synthesizing
            break
        lang = speak_mod.language(sentence)
        cfg = sherpa_onnx.GenerationConfig()
        cfg.sid = sid
        cfg.speed = speak_mod.BASE_SPEED[lang] * rate
        cfg.num_steps = STEPS
        cfg.extra["lang"] = lang
        audio = tts.generate(sentence, cfg)
        chunks.put(np.asarray(audio.samples, np.float32).tobytes() + pause)
        if i == 0:  # first sound: the icon moves from preparing to speaking
            speak_mod.phase_path().write_text("SPEAKING\n")
            memo._poke_indicator()
    chunks.put(None)
    feeder.join()
    return player.wait()


def _feed(player: subprocess.Popen, chunks: queue.Queue) -> None:
    try:
        while (chunk := chunks.get()) is not None:
            player.stdin.write(chunk)
        player.stdin.close()
    except BrokenPipeError:  # stopped mid-sentence
        pass


def main() -> int:
    signal.signal(signal.SIGINT, lambda *_: sys.exit(0))  # the stop key, quietly
    text = sys.stdin.read().strip()
    try:
        return speak(text) if text else 0
    except Exception as e:  # stderr goes nowhere when run from the hotkey: say it
        memo._notify("Could not read aloud", str(e)[:200] or type(e).__name__)
        return 1
    finally:
        _cleanup()


def _cleanup() -> None:
    """Speech ended: drop the phase file, and the pidfile if it is still ours (a new
    speak may already have replaced it), so the icon goes idle now, not on the next poll."""
    speak_mod.phase_path().unlink(missing_ok=True)
    pid_path = speak_mod._pid_path()
    try:
        if pid_path.read_text().strip() == str(os.getpid()):
            pid_path.unlink()
    except OSError:
        pass
    memo._poke_indicator()


if __name__ == "__main__":
    sys.exit(main())
