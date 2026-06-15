# Spec 0001: Text insertion architecture

- **Status:** ACCEPTED, v1 IMPLEMENTED (2026-06-15). `src/dicti/insert.py` (backends +
  detection), config (`insert_backend`, `paste_keys`, `preserve_clipboard`), `wl-clipboard`
  for Wayland, `wtype` backend for wlroots, clipboard save/restore. Tests in
  `tests/test_insert.py`. Not yet validated on real Wayland/wlroots hardware. v1.1 = IBus
  (spec 0002).
- **Date:** 2026-06-15
- **Supersedes:** the ad-hoc insertion logic in `daemon.py` (`_type_text` / `_paste_via_clipboard`)
- **Related:** [0002 IBus engine](0002-ibus-engine.md)

## Problem

Dicti must insert transcribed text into whatever window has focus, including **non-ASCII**
text (Polish ąęóśżźćń, other languages, accents), **reliably**, across the Linux desktop
matrix: display servers (X11, Wayland) and compositors (GNOME/Mutter, KDE/KWin,
wlroots/Sway/Hyprland). This is the single hardest portability problem in the project and the
main reason good Linux dictation tools are scarce. A wrong choice here is not cosmetic: an
earlier attempt (xdotool) **froze the X server and required a hard reboot**.

## Constraints (from two independent research passes, 2025)

No keystroke-injection tool types arbitrary Unicode everywhere:

| Method | Unicode | Works on | Notes |
|--------|---------|----------|-------|
| ydotool (uinput) | ASCII only | X11 + Wayland + TTY (all) | layout-blind; drops Polish; default 12-20ms key delay = latency |
| dotool (uinput) | layout chars only | X11 + Wayland + TTY | aborts on unmapped glyph; no arbitrary Unicode |
| xdotool (XTEST) | yes | **X11 only** | keymap-remap storm **froze our machine**; disqualified |
| wtype (virtual-kbd) | yes | **wlroots only** | GNOME Mutter & KDE KWin refuse `virtual-keyboard-v1` |
| libei portal | layout-dependent | GNOME 46+, KDE 6 | skips unmapped chars + triggers permission prompts |
| **clipboard-paste** | **full UTF-8** | **everywhere** | only universal Unicode path; see caveats below |
| **IBus IME (`commit_text`)** | **full UTF-8** | **GNOME/KDE/wlroots/X11 (if IBus runs)** | proper path for dictation; see risks |

Clipboard-paste caveats: paste shortcut varies by app (Ctrl+V vs Ctrl+Shift+V); integrated
terminals (Zed/VSCode panes) are indistinguishable from their editor by window class; Wayland
clipboard is async (needs ~100ms before restore) and non-persistent; pasting clobbers /
pollutes the user's clipboard and history.

IBus risks: IBus must be running (default on GNOME, common on KDE, **not** on wlroots); the
dicti engine must be the **active input method** to `commit_text`, which means it controls the
XKB layout, get the passthrough wrong and a user's normal physical typing breaks (worst for
the multilingual users dicti targets). Auto-activation via `gsettings` removes manual-config
friction but is invasive and must preserve the user's existing layout/IME. See spec 0002.

## Decision

**Insertion is a pluggable backend behind one interface, auto-selected per environment, with
a safe universal default. No backend may be able to hang the system. Clipboard is the
permanent universal floor; better backends layer on top where available.**

```
Insertion interface:  insert(text: str) -> None      # may be called per word (streaming)
                      open()/close()                 # session hooks: clipboard save/restore
```

### Backends (preference order, highest first when available)

1. **`ibus`** , commit UTF-8 via a dicti IBus engine. Best UX: atomic, layout-free, no
   paste-shortcut, no clobber, no prompts. **v1.1, prototype-gated** (spec 0002).
2. **`wtype`** , native Unicode typing on wlroots (Sway/Hyprland). Near-perfect there, cheap
   to add (clean backend, same interface). Auto-used when the compositor supports it.
3. **`clipboard`** , the universal default and permanent fallback. Copy via `wl-copy`
   (Wayland) or `xclip` (X11); paste via a shortcut chosen from the focused window; clipboard
   saved and restored; async-safe delay.
4. **`ydotool`** , ASCII fast-path used *within* the clipboard backend: ASCII pieces typed
   directly (universal, no paste-shortcut issue), only non-ASCII pieces go through clipboard.

xdotool is **excluded** (X11-only, froze the machine). dotool/libei excluded for Unicode.

### Default behaviour (v1)

- Detect session (`XDG_SESSION_TYPE`, `WAYLAND_DISPLAY`) and pick the clipboard tool
  (`xclip` on X11, `wl-copy`/`wl-paste` on Wayland).
- ASCII text -> ydotool `type` (fast, universal; key-delay tuned to avoid dropped keys).
- Non-ASCII text -> clipboard backend:
  - **save** the user's current clipboard (mime-aware where possible);
  - copy the text, **paste** (Ctrl+Shift+V if the focused window is a terminal, else Ctrl+V;
    X11 detects via `xprop` WM_CLASS, Wayland uses the configured default), settle ~100ms;
  - **restore** the saved clipboard (default), unless `preserve_clipboard = false`.
- Config: `insert_backend` (auto|clipboard|wtype|ydotool|ibus), `paste_keys`
  (auto|ctrl+v|ctrl+shift+v), `preserve_clipboard` (default true).

## Resolved decisions (interview, 2026-06-15)

1. **Launch scope:** X11 + Wayland (GNOME/KDE) for v1, **plus wlroots via the `wtype`
   backend** (confirmed a clean addition, not a separate architecture).
2. **IBus:** clipboard now (it is the permanent fallback, not throwaway); IBus is the
   immediate fast-follow (v1.1), **gated by a prototype** that proves zero-config
   auto-activation and transparent passthrough (spec 0002). Promote to default on GNOME/KDE
   only if proven.
3. **Clipboard etiquette:** save/restore the user's clipboard by default; `preserve_clipboard`
   config to opt into leaving the transcript on it.
4. **Audience:** general Linux users, multilingual (PL/EN core), developer-friendly. Default
   paste = Ctrl+V with terminal detection. Priorities, in order: reliable > good (not yet
   perfect) > a cool, polished look and feel before going public.

## Rollout

- **v1 (launch floor):** backend abstraction; clipboard default + ydotool ASCII; X11 and
  Wayland (GNOME/KDE) via `wl-clipboard`; clipboard save/restore; smart/overridable paste
  keys; `wtype` backend auto-used on wlroots. Honest support claim in README.
- **v1.1:** `ibus` engine backend per spec 0002 (prototype first); becomes default on
  GNOME/KDE if the prototype passes its acceptance bar.

## Done when

- One insertion interface; backends selected by capability detection; config overrides.
- Verified on X11/GNOME and Wayland/GNOME; non-ASCII correct in editors and terminals.
- No insertion path can hang the compositor (hard requirement).
- README states supported environments truthfully.
