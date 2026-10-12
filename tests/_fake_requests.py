"""One fake `requests` for every test module, so no whisper-server is needed.

Shared on purpose: dicti.daemon binds `requests` once, at its first import. A
per-file fake would leave the second test file talking to the first file's fake.
"""

import sys
import types

_req = types.ModuleType("requests")


class _Resp:
    def __init__(self, text):
        self._t = text

    def raise_for_status(self):
        pass

    def json(self):
        return {"text": self._t}


def _default_post(url, files=None, data=None, timeout=None):
    return _Resp(_req.next_text)


_req.next_text = ""
_req.post = _default_post
sys.modules["requests"] = _req
