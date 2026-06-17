# Spec 0002: IBus input-method engine (premium insertion path)

- **Status:** REJECTED (spike 2026-06-17, failed both gate requirements)
- **Date:** 2026-06-15
- **Depends on:** [0001 Text insertion](0001-text-insertion.md)

## Spike result (2026-06-17): REJECTED

A minimal passthrough engine was built (`prototype/ibus/dicti_ibus.py`: `layout="default"`,
`do_process_key_event` -> False, a unix-socket `commit_text` bridge) and tested live on the
target GNOME + Polish setup. Both hard requirements failed:

1. **Transparency failed.** With the engine active, physical *ASCII* typing worked but the
   user's **Polish layout broke** (no diacritics). `layout="default"` inherited the primary
   (US) layout rather than following the user's active `pl` source; an active IBus engine
   owns the layout and a passthrough does not reach the secondary XKB layout. This is exactly
   the multilingual-typing breakage the gate existed to prevent.
2. **It did not solve the target problem.** `commit_text` injected correctly into GNOME Text
   Editor (a standard GTK app) but produced **garbage in Zed's terminal** (`wklejone?^V^[e`).
   Zed's terminal does not implement the standard text-input protocol, the *same* root cause
   that made clipboard Ctrl+V fail there. IBus gives no advantage over clipboard in standard
   apps and still cannot reach Zed's non-standard terminal.

**Conclusion:** the integrated-terminal gap (Zed/VS Code custom terminals) is not an
insertion-method problem dicti can fix from outside; those surfaces reject external text
injection by any method. Stay on the clipboard backend (spec 0001). For such terminals the
practical lever is `paste_keys = "ctrl+shift+v"` (worth testing: Zed's terminal likely
accepts Ctrl+Shift+V as paste even though it rejects Ctrl+V), or dictate into a standard app.
The prototype is kept under `prototype/ibus/` as the record of this spike; do not revive IBus
without a fundamentally different transparency approach.

---

(original design below, kept for the record)

## Why

Clipboard-paste (spec 0001) is reliable and universal but has irreducible rough edges: the
paste shortcut varies by app, integrated terminals (Zed/VSCode panes) can't be targeted, and
it touches the user's clipboard. The proper fix for a dictation tool is a custom **IBus input
method engine** that `commit_text`s the transcribed UTF-8 directly into the focused
application's input buffer: atomic, layout-independent, no paste shortcut, no clipboard, no
permission prompts. It works on GNOME/Mutter, KDE/KWin, wlroots, and X11 wherever IBus runs.

## Hard requirements (the gate)

This path ships **only if a prototype proves both**:

1. **Zero manual configuration.** The installer registers the engine (component XML) and
   activates it for the user automatically (e.g. via `gsettings set
   org.gnome.desktop.input-sources sources ...`), preserving the user's existing sources/
   layout. The user never opens Settings or "adds an input source" by hand.
2. **Transparent passthrough.** With the dicti engine active, normal physical typing is
   **identical** to before, including the user's real XKB layout, dead keys, and compose.
   This is the make-or-break risk: an active IBus engine controls the layout, and breaking a
   Polish user's physical ł/ą would be unacceptable. Must be validated on a non-US layout.

If either fails, abandon IBus and stay on clipboard (spec 0001). Do not ship a half-working
input method.

## Sketch (to validate in the spike)

- A small IBus engine (Python via `gi.repository.IBus`) that:
  - returns `False` from `process_key_event` for every key (pure passthrough) while
    correctly inheriting the user's layout;
  - listens on a socket / D-Bus for the dicti daemon and calls `commit_text` on its current
    input context when dictation arrives.
- The daemon's `ibus` insertion backend talks to the engine instead of typing/pasting.
- Install/activate/uninstall scripts; clean removal restores the user's input sources.

## Acceptance

- Dictated Polish + English insert correctly into GNOME Text Editor, a terminal, and an IDE's
  integrated terminal, with no paste shortcut and no clipboard change.
- Physical typing on a Polish layout is unchanged with the engine active.
- Fresh install activates it with no manual step; uninstall fully reverts.
- Falls back to clipboard (spec 0001) when IBus is absent (e.g. stock wlroots).

## Open questions

- Best transparent-passthrough technique that preserves arbitrary XKB layouts.
- KDE/Fcitx5 parity (Fcitx5 is common on KDE; may need a second engine or a shared core).
- How invasive is auto-activation across distros/desktops; how to revert cleanly.
