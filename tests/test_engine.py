#!/usr/bin/env python3
"""Unit tests for engine selection (Parakeet default, Whisper optional).

  - stream interval and window follow the engine unless the config sets them
  - requests go to parakeet-server, except translate and engine="whisper"
  - parakeet-server pulls the WAV out of the same multipart form whisper-server accepts

Pure stdlib (no numpy, no sherpa-onnx, no server). Run with: python3 tests/test_engine.py
"""

import os
import sys
import tempfile

import _fake_requests

_tmp = tempfile.mkdtemp()
os.environ["XDG_RUNTIME_DIR"] = _tmp
os.environ["XDG_CONFIG_HOME"] = _tmp
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from dicti.config import Config, _config_path  # noqa: E402
from dicti.daemon import Daemon  # noqa: E402
from dicti.parakeet_server import BadRequest, wav_from_multipart  # noqa: E402


def _load(text):
    # Another test module may have repointed XDG_CONFIG_HOME, so ask config where it reads.
    path = _config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    try:
        return Config.load()
    finally:
        path.unlink()


def test_parakeet_is_the_default_with_fast_streaming():
    cfg = Config()
    assert cfg.engine == "parakeet"
    assert (cfg.stream_interval_sec, cfg.max_context_sec) == (0.5, 12.0)


def test_whisper_keeps_its_own_streaming_defaults():
    cfg = _load('engine = "whisper"\n')
    assert (cfg.stream_interval_sec, cfg.max_context_sec) == (2.0, 60.0)


def test_explicit_streaming_settings_win_over_engine_defaults():
    cfg = _load('stream_interval_sec = 1.5\nmax_context_sec = 45.0\n')
    assert cfg.engine == "parakeet"
    assert (cfg.stream_interval_sec, cfg.max_context_sec) == (1.5, 45.0)


def test_unknown_engine_falls_back_to_parakeet():
    assert Config(engine="vosk").engine == "parakeet"


def _sent_urls(cfg, translate):
    urls = []
    _fake_requests._req.post = lambda url, **kw: urls.append(url) or _fake_requests._Resp("")
    try:
        d = Daemon(cfg)
        d.translate = translate
        d._transcribe_pcm(b"\0\0" * 1600)
    finally:
        _fake_requests._req.post = _fake_requests._default_post
    return urls


def test_requests_go_to_parakeet_but_translate_goes_to_whisper():
    cfg = Config()
    assert _sent_urls(cfg, translate=False) == [cfg.parakeet_url]
    assert _sent_urls(cfg, translate=True) == [cfg.whisper_url]
    whisper = Config(engine="whisper")
    assert _sent_urls(whisper, translate=False) == [whisper.whisper_url]


def _form(*parts):
    body = b""
    for name, payload in parts:
        body += (b"--XB\r\nContent-Disposition: form-data; name=\"" + name.encode()
                 + b"\"; filename=\"a.wav\"\r\nContent-Type: audio/wav\r\n\r\n"
                 + payload + b"\r\n")
    return "multipart/form-data; boundary=XB", body + b"--XB--\r\n"


def test_server_extracts_the_file_field_byte_exact():
    wav = bytes(range(256)) * 4  # binary, includes CR/LF and boundary-like bytes
    assert wav_from_multipart(*_form(("language", b"auto"), ("file", wav))) == wav


def test_server_rejects_forms_without_audio():
    for content_type, body in (_form(("language", b"auto")), ("application/json", b"{}")):
        try:
            wav_from_multipart(content_type, body)
        except BadRequest:
            continue
        raise AssertionError(f"accepted {content_type!r} without a file field")


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items())
             if k.startswith("test_") and callable(v)]
    for t in tests:
        t()
        print(f"ok  {t.__name__}")
    print(f"\n{len(tests)} engine tests passed")
