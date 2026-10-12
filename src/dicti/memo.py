"""
dicti audio memos: record the microphone straight to an mp3, no transcription.

    dicti -mp3 NAME       record to ./NAME.mp3 in the current directory; Enter or Ctrl+C stops
    dicti --memo-toggle   hotkey: first press starts, second press stops and asks where to save

Audio is encoded live (pw-record | ffmpeg), so nothing grows in RAM beyond the mp3 itself
(~50 MB/hour). The hotkey's working file sits in $XDG_RUNTIME_DIR (private to the user) until
it is saved; files are created 0600.
"""

from __future__ import annotations

import os
import shlex
import shutil
import signal
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from dicti.config import _config_path

USAGE = """usage: dicti -mp3 NAME       record to ./NAME.mp3 (Enter or Ctrl+C stops)
       dicti --memo-toggle   start / stop-and-save a recording (bind to a key)"""

STOP_WAIT_SEC = 10  # how long a stop waits for ffmpeg to finish the file


def _runtime_dir() -> Path:
    xdg = os.environ.get("XDG_RUNTIME_DIR")
    if not xdg:
        raise SystemExit("XDG_RUNTIME_DIR not set, run dicti inside your desktop session")
    return Path(xdg)


def _pid_path() -> Path:
    return _runtime_dir() / "dicti-memo.pid"


def _work_path() -> Path:
    return _runtime_dir() / "dicti-memo.mp3"


def _last_dir_path() -> Path:
    return _config_path().parent / "memo-last-dir"


def _pipeline(out: Path) -> list[str]:
    # pw-record writes a non-WAV container to a pipe, so hand ffmpeg raw PCM instead.
    return ["sh", "-c",
            "pw-record --raw --rate=48000 --channels=1 --format=s16 - | "
            "ffmpeg -hide_banner -nostdin -nostats -loglevel fatal -y "
            "-f s16le -ar 48000 -ac 1 -i - -codec:a libmp3lame -q:a 2 " + shlex.quote(str(out))]


def _start(out: Path, detach: bool = False) -> subprocess.Popen:
    # Own session, so one SIGINT to the group stops pw-record and lets ffmpeg close the file.
    # Detached (hotkey) recordings outlive their launcher: a write to its closed stdout or
    # stderr would kill ffmpeg with SIGPIPE mid-recording.
    out_fd = subprocess.DEVNULL if detach else None
    return subprocess.Popen(_pipeline(out), start_new_session=True,
                            stdin=out_fd, stdout=out_fd, stderr=out_fd)


def _notify(summary: str, body: str = "") -> None:
    try:
        subprocess.run(["notify-send", "-a", "dicti", summary, body], timeout=5, check=False)
    except (OSError, subprocess.TimeoutExpired):
        pass


def target_path(name: str, cwd: Path) -> Path:
    """Where `dicti -mp3 NAME` writes. Leading dashes are dropped (`-mp3 -notes` works),
    `.mp3` is added when missing, relative names land in the current directory."""
    name = name.lstrip("-")
    if not name:
        raise ValueError("empty file name")
    path = Path(name).expanduser()
    if path.suffix.lower() != ".mp3":
        path = path.with_name(path.name + ".mp3")
    return path if path.is_absolute() else cwd / path


def save_dir() -> Path:
    """The save dialog's starting folder: the last one used, else the Desktop, else home."""
    try:
        last = Path(_last_dir_path().read_text().strip())
        if last.is_dir():
            return last
    except OSError:
        pass
    try:
        desktop = subprocess.run(["xdg-user-dir", "DESKTOP"], capture_output=True,
                                 text=True, timeout=5).stdout.strip()
        if desktop and Path(desktop).is_dir():
            return Path(desktop)
    except (OSError, subprocess.TimeoutExpired):
        pass
    return Path.home()


def running_pid() -> int | None:
    """PID of the hotkey recording in progress, or None. Checks the process is really ours,
    so a stale pidfile whose PID was reused never gets signalled."""
    try:
        pid = int(_pid_path().read_text().strip())
        if b"pw-record" in Path(f"/proc/{pid}/cmdline").read_bytes():
            return pid
    except (OSError, ValueError):
        pass
    return None


def _stop_group(pid: int) -> None:
    try:
        os.killpg(pid, signal.SIGINT)
    except ProcessLookupError:
        return
    deadline = time.monotonic() + STOP_WAIT_SEC
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return
        time.sleep(0.1)


def record_to_file(name: str) -> int:
    try:
        out = target_path(name, Path.cwd())
    except ValueError as e:
        print(f"dicti: {e}", file=sys.stderr)
        return 2
    if out.exists():
        print(f"dicti: {out} already exists", file=sys.stderr)
        return 1
    proc = _start(out)
    time.sleep(0.3)
    if proc.poll() is not None:
        print("dicti: recording failed to start (microphone? pw-record, ffmpeg?)", file=sys.stderr)
        return 1
    print(f"Recording to {out}. Enter = stop.")
    try:
        input()
    except (KeyboardInterrupt, EOFError):
        pass
    _stop_group(proc.pid)
    proc.wait()
    if not out.exists() or out.stat().st_size == 0:
        print("dicti: nothing was recorded", file=sys.stderr)
        return 1
    print(f"Saved {out}")
    return 0


def memo_toggle() -> int:
    pid = running_pid()
    if pid is None:
        work = _work_path()
        work.unlink(missing_ok=True)
        proc = _start(work, detach=True)
        _pid_path().write_text(f"{proc.pid}\n")
        _notify("Recording mp3", "Press Copilot again to stop and save")
        return 0

    _stop_group(pid)
    _pid_path().unlink(missing_ok=True)
    work = _work_path()
    if not work.exists() or work.stat().st_size == 0:
        work.unlink(missing_ok=True)
        _notify("Nothing recorded")
        return 1

    start = save_dir()
    default = start / datetime.now().strftime("dicti-%Y-%m-%d-%H%M.mp3")
    try:
        r = subprocess.run(["zenity", "--file-selection", "--save", "--confirm-overwrite",
                            "--title=Save recording", f"--filename={default}"],
                           capture_output=True, text=True, check=False)
        if r.returncode == 1:  # cancelled = the user chose not to keep it
            work.unlink(missing_ok=True)
            _notify("Recording discarded")
            return 0
        dest = Path(r.stdout.strip()) if r.returncode == 0 and r.stdout.strip() else default
    except OSError:  # no zenity: never lose the recording, save it to the default name
        dest = default
    if dest.suffix.lower() != ".mp3":
        dest = dest.with_name(dest.name + ".mp3")
    shutil.move(work, dest)
    try:
        _last_dir_path().parent.mkdir(parents=True, exist_ok=True)
        _last_dir_path().write_text(f"{dest.parent}\n")
    except OSError:
        pass
    _notify("Recording saved", str(dest))
    return 0


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    os.umask(0o077)  # recordings are readable by their owner only
    if args == ["--memo-toggle"]:
        return memo_toggle()
    if len(args) == 2 and args[0] in ("-mp3", "--mp3"):
        return record_to_file(args[1])
    print(USAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
