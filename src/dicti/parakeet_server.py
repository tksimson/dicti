"""Local Parakeet TDT v3 speech-to-text server, a drop-in for whisper-server's /inference.

Speaks the subset of whisper-server's API dicti uses: POST a multipart form with a 16 kHz
mono s16 WAV in `file`, get back {"text": ...}. Other form fields (language, translate) are
ignored: Parakeet detects the language itself and cannot translate, so the daemon sends
translate requests to whisper-server instead.

Runs in its own venv (sherpa-onnx + numpy, see install/03b-install-parakeet.sh) so the
daemon stays stdlib + requests. Binds to localhost only; one request at a time, like
whisper-server, which also keeps CPU use bounded.
"""

from __future__ import annotations

import argparse
import io
import json
import logging
import time
import wave
from email.parser import BytesParser
from email.policy import HTTP
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

log = logging.getLogger("parakeet")

SAMPLE_RATE = 16000
MAX_BODY_BYTES = 160 * 1024 * 1024  # > one hour of 16 kHz s16 audio (dicti's max_record_sec)


class BadRequest(ValueError):
    pass


def wav_from_multipart(content_type: str, body: bytes) -> bytes:
    """Return the bytes of the `file` part of a multipart/form-data body. Raises BadRequest."""
    if not content_type.startswith("multipart/form-data"):
        raise BadRequest("expected multipart/form-data")
    msg = BytesParser(policy=HTTP).parsebytes(
        b"Content-Type: " + content_type.encode() + b"\r\n\r\n" + body)
    for part in msg.iter_parts():
        if part.get_param("name", header="content-disposition") == "file":
            return part.get_payload(decode=True)
    raise BadRequest("no 'file' field")


def pcm_from_wav(data: bytes):
    """Decode a 16 kHz mono 16-bit WAV to float32 samples in [-1, 1]. Raises BadRequest."""
    import numpy as np

    try:
        with wave.open(io.BytesIO(data)) as w:
            if (w.getframerate(), w.getnchannels(), w.getsampwidth()) != (SAMPLE_RATE, 1, 2):
                raise BadRequest("need 16 kHz mono 16-bit WAV")
            frames = w.readframes(w.getnframes())
    except (wave.Error, EOFError) as e:
        raise BadRequest(f"bad WAV: {e}") from e
    return np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0


def load_recognizer(model_dir: Path, threads: int):
    import sherpa_onnx

    return sherpa_onnx.OfflineRecognizer.from_transducer(
        encoder=str(model_dir / "encoder.int8.onnx"),
        decoder=str(model_dir / "decoder.int8.onnx"),
        joiner=str(model_dir / "joiner.int8.onnx"),
        tokens=str(model_dir / "tokens.txt"),
        model_type="nemo_transducer",
        num_threads=threads,
    )


def make_handler(recognizer, path: str):
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            if self.path != path:
                return self._reply(404, {"error": "not found"})
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= MAX_BODY_BYTES:
                    raise BadRequest("missing or oversized body")
                body = self.rfile.read(length)
                samples = pcm_from_wav(wav_from_multipart(
                    self.headers.get("Content-Type", ""), body))
            except BadRequest as e:
                return self._reply(400, {"error": str(e)})
            t0 = time.monotonic()
            stream = recognizer.create_stream()
            stream.accept_waveform(SAMPLE_RATE, samples)
            recognizer.decode_stream(stream)
            text = stream.result.text.strip()
            log.info("%.1fs audio in %.2fs", len(samples) / SAMPLE_RATE, time.monotonic() - t0)
            self._reply(200, {"text": text})

        def do_GET(self):
            self._reply(200, {"status": "ok"})  # health probe, like whisper-server's GET /

        def _reply(self, code: int, payload: dict) -> None:
            data = json.dumps(payload, ensure_ascii=False).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, fmt, *args):
            pass  # per-request access lines are noise; inference timing is logged instead

    return Handler


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--model-dir", type=Path, required=True)
    ap.add_argument("--port", type=int, default=8179)
    ap.add_argument("--threads", type=int, default=8)
    ap.add_argument("--inference-path", default="/inference")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    t0 = time.monotonic()
    recognizer = load_recognizer(args.model_dir, args.threads)
    log.info("Loaded %s in %.1fs", args.model_dir, time.monotonic() - t0)
    server = HTTPServer(("127.0.0.1", args.port), make_handler(recognizer, args.inference_path))
    log.info("Listening on 127.0.0.1:%d%s", args.port, args.inference_path)
    server.serve_forever()


if __name__ == "__main__":
    main()
