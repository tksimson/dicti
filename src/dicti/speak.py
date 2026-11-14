"""dicti speak: read the highlighted text aloud, offline.

    dicti --speak-toggle         hotkey: first press reads the highlighted text, second stops
    dicti --speak-voice F1       pick the voice (F1 F3 M1 M4), the panel menu calls this
    dicti --speak-speed faster   slower | normal | faster

The text comes from the primary selection (whatever is highlighted, in any app). Each
sentence is spoken in Polish or English, picked from the sentence itself. Synthesis runs in
the parakeet venv (dicti.tts_worker, Supertonic 3 from install/03c-install-tts.sh) and plays
straight to the speakers; the text travels on a pipe, never argv or disk.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

from dicti import memo
from dicti.config import _config_path

VENV_PYTHON = Path.home() / "opt/parakeet/venv/bin/python3"
MODEL_DIR = Path.home() / "opt/parakeet/tts/supertonic-3"
SRC_DIR = Path(__file__).resolve().parent.parent
MARKER = "dicti.tts_worker"  # in the worker's cmdline, so a reused PID is never signalled

# Supertonic's preset voices, by speaker id: F1..F5 = 0..4, M1..M5 = 5..9. These four were
# picked by ear for Polish and English.
VOICES = {"F1": 0, "F3": 2, "M1": 5, "M4": 8}
# The model speaks slowly at 1.0; these rates were tuned by ear. Polish takes faster.
BASE_SPEED = {"pl": 1.3, "en": 1.15}
SPEEDS = {"slower": 0.85, "normal": 1.0, "faster": 1.15}
DEFAULTS = {"voice": "F1", "speed": "normal"}

PL_LETTERS = set("ąćęłńóśźżĄĆĘŁŃÓŚŹŻ")
PL_WORDS = {"nie", "się", "jest", "że", "na", "jak", "czy", "dla", "oraz", "ale", "tak",
            "jestem", "bardzo", "tylko", "też", "być", "może", "już", "przez", "od"}
SELECTION_CMDS = (["wl-paste", "--primary", "--no-newline"],
                  ["xclip", "-o", "-selection", "primary"])


def _pid_path() -> Path:
    return memo._runtime_dir() / "dicti-speak.pid"


def phase_path() -> Path:
    """Holds SPEAKING once the first sound plays; absent while the voice is getting ready."""
    return memo._runtime_dir() / "dicti-speak.phase"


def settings_path() -> Path:
    return _config_path().parent / "speak.json"


def settings() -> dict[str, str]:
    """The chosen voice and speed; anything missing or unknown falls back to the default."""
    try:
        saved = json.loads(settings_path().read_text())
    except (OSError, ValueError):
        saved = {}
    if not isinstance(saved, dict):
        saved = {}
    return {"voice": saved.get("voice") if saved.get("voice") in VOICES else DEFAULTS["voice"],
            "speed": saved.get("speed") if saved.get("speed") in SPEEDS else DEFAULTS["speed"]}


def save_setting(key: str, value: str) -> int:
    allowed = {"voice": VOICES, "speed": SPEEDS}[key]
    if value not in allowed:
        print(f"dicti: {key} must be one of {', '.join(allowed)}")
        return 2
    current = settings()
    current[key] = value
    settings_path().parent.mkdir(parents=True, exist_ok=True)
    settings_path().write_text(json.dumps(current) + "\n")
    return 0


def running_pid() -> int | None:
    return memo._running_pid(_pid_path(), MARKER)


def phase() -> str | None:
    """PREPARING or SPEAKING while dicti reads aloud, else None. The live pid is the only
    test of running, so a killed worker's leftover files never stick the icon."""
    if running_pid() is None:
        return None
    try:
        return "SPEAKING" if phase_path().read_text().strip() == "SPEAKING" else "PREPARING"
    except OSError:
        return "PREPARING"


def stop() -> None:
    pid = running_pid()
    if pid is not None:
        memo._stop_group(pid)
    _pid_path().unlink(missing_ok=True)
    phase_path().unlink(missing_ok=True)
    memo._poke_indicator()


def language(text: str) -> str:
    """'pl' when the text has Polish letters or reads as Polish, else 'en'."""
    if PL_LETTERS & set(text):
        return "pl"
    words = re.findall(r"\w+", text.lower())
    hits = sum(w in PL_WORDS for w in words)
    return "pl" if hits >= 2 or (words and hits / len(words) > 0.1) else "en"


def sentences(text: str) -> list[str]:
    """Split at sentence ends and line breaks: the model takes one sentence per call, and
    speech starts as soon as the first one is ready."""
    parts = re.split(r"(?<=[.!?…])\s+|\n\s*", text)
    return [p.strip() for p in parts if p and p.strip()]


def selection() -> str:
    """The highlighted text, or '' when nothing is highlighted or no tool can read it."""
    for cmd in SELECTION_CMDS:
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=3, check=False)
        except (OSError, subprocess.TimeoutExpired):
            continue
        if r.returncode == 0:
            return r.stdout.strip()
    return ""


def _mic_busy() -> bool:
    """Dictation or an mp3 memo is recording: speaking now would land in the microphone."""
    try:
        state = (memo._runtime_dir() / "dictation.state").read_text().strip()
    except OSError:
        state = ""
    return state == "LISTENING" or memo.running_pid() is not None


def _start(text: str) -> subprocess.Popen:
    # Own session, so the stop key's SIGINT reaches pw-play too. Detached: the hotkey
    # launcher exits right away, so its closed stdout must not SIGPIPE the worker.
    proc = subprocess.Popen(
        [str(VENV_PYTHON), "-m", MARKER],
        env={**os.environ, "PYTHONPATH": str(SRC_DIR)},
        start_new_session=True, stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    proc.stdin.write(text.encode())
    proc.stdin.close()
    return proc


def speak_toggle() -> int:
    if running_pid() is not None:
        stop()
        return 0
    if _mic_busy():
        memo._notify("Not speaking", "dicti is recording, the microphone would hear it",
                     transient=True)
        return 1
    text = selection()
    if not text:
        memo._notify("Nothing highlighted", "Highlight some text, then press AltGr+Copilot",
                     transient=True)
        return 1
    if not (MODEL_DIR / "vocoder.onnx").exists() or not VENV_PYTHON.exists():
        memo._notify("Voice not installed", "Run install/03c-install-tts.sh", transient=True)
        return 1
    phase_path().unlink(missing_ok=True)
    proc = _start(text)
    _pid_path().write_text(f"{proc.pid}\n")
    memo._poke_indicator()
    return 0
