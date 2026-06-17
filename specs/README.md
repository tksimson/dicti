# Specs

Design specs for dicti. Each spec is a numbered, self-contained document that states a
problem, the constraints, the decision, and the rollout. Specs are the durable "why";
`docs/` holds how-it-works and handoffs; `ROADMAP.md` holds the timeline.

Convention:
- `NNNN-short-title.md`, zero-padded, allocated in order.
- Status one of: `DRAFT`, `ACCEPTED`, `IN PROGRESS`, `SHIPPED`, `SUPERSEDED`.
- Keep decisions and open questions explicit. When a spec is superseded, link forward.

| # | Title | Status |
|---|-------|--------|
| [0001](0001-text-insertion.md) | Text insertion architecture | v1 SHIPPED |
| [0002](0002-ibus-engine.md) | IBus input-method engine (premium path) | REJECTED (spike failed) |
