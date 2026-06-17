# IBus engine spike (REJECTED)

`dicti_ibus.py` is a throwaway spike for the IBus insertion path (see
[`specs/0002-ibus-engine.md`](../../specs/0002-ibus-engine.md)). It is **not used** by the
app and is kept only as the record of what was tried.

Result (2026-06-17): rejected. With the engine active, the user's Polish XKB layout broke
(physical typing lost diacritics), and `commit_text` produced garbage in Zed's terminal,
the very surface IBus was meant to fix, because Zed's terminal does not implement standard
text input. IBus gave no advantage over the clipboard backend in standard apps and could not
reach the non-standard terminal. Do not revive without a fundamentally different approach to
preserving the user's keyboard layout.
