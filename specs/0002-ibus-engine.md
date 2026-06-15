# Spec 0002: IBus input-method engine (premium insertion path)

- **Status:** DRAFT (prototype-gated; not started)
- **Date:** 2026-06-15
- **Depends on:** [0001 Text insertion](0001-text-insertion.md)

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
