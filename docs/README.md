# docs

How dicti works, and design handoffs. The project keeps three kinds of writing separate:

- **`docs/`** (here) , how things work and handoff notes.
- **`specs/`** , design *decisions* (the "why"), numbered and self-contained.
- **`ROADMAP.md` / `CHANGELOG.md`** (repo root) , the timeline and per-version history.
- **`README.md`** (repo root) , user-facing overview, install, configuration.

## In this folder

- [`v0.3-streaming.md`](v0.3-streaming.md) , live streaming dictation: design + handoff.
  Growing-window re-transcription (full context = batch quality), the stabilise-across-passes
  filter (append-only), and onset-tuned server-side VAD. Also the starting point for the v0.4
  word-level work.

## Specs (in [`../specs/`](../specs/))

- [`0001-text-insertion.md`](../specs/0001-text-insertion.md) , insertion architecture
  (pluggable backends; clipboard floor; why not xdotool/wtype/ydotool alone). ACCEPTED.
- [`0002-ibus-engine.md`](../specs/0002-ibus-engine.md) , the IBus premium insertion path,
  prototype-gated on zero-config + transparent passthrough. DRAFT.
