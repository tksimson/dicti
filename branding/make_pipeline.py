#!/usr/bin/env python3
"""Generate branding/dicti-pipeline.svg.

A compact 3-stage flow for the README "How it works" section. Self-contained
dark cards + brand-green accents so it reads on both light and dark GitHub
themes. Throwaway generator.
"""

GREEN = "#3c9a5e"
GREEN_DIM = "#2f7a4a"
PINK = "#e85ba6"
CARD = "#1c1c1e"
CARD_EDGE = "#34343a"
TEXT = "#e9e9ec"
MUTE = "#9a9aa2"

CARD_W = 218
CARD_H = 116
GAP = 38
PAD = 4
TOP = 26

SVG_W = PAD + 3 * CARD_W + 2 * GAP + PAD
SVG_H = TOP + CARD_H + 26

STAGES = [
    ("1", "Trigger", GREEN, [
        ("tap your key", "keyd → GNOME shortcut"),
        ("dictation daemon", "via unix socket"),
    ]),
    ("2", "Transcribe · offline", PINK, [
        ("pw-record → WAV", "PipeWire capture"),
        ("whisper.cpp", "Vulkan GPU · on-device"),
    ]),
    ("3", "Insert", GREEN, [
        ("ydotool / clipboard", "ASCII typed · Unicode pasted"),
        ("focused window", "append-only, never rewrites"),
    ]),
]


def card_x(i):
    return PAD + i * (CARD_W + GAP)


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def build():
    cy = TOP + CARD_H / 2
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{SVG_W}" '
        f'height="{SVG_H}" viewBox="0 0 {SVG_W} {SVG_H}" role="img" '
        f'aria-label="dicti pipeline: trigger, transcribe offline, insert">',
        '<defs>',
        f'<marker id="arrow" viewBox="0 0 10 10" refX="8" refY="5" '
        f'markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
        f'<path d="M0 0 L10 5 L0 10 z" fill="{GREEN}"/></marker>',
        '</defs>',
        '<style>'
        'text{font-family:Inter,-apple-system,Segoe UI,Roboto,sans-serif}'
        '.mono{font-family:ui-monospace,SFMono-Regular,Menlo,monospace}'
        '</style>',
    ]

    # arrows between cards (drawn first, behind nothing important)
    for i in range(2):
        x1 = card_x(i) + CARD_W + 6
        x2 = card_x(i + 1) - 6
        out.append(f'<line x1="{x1}" y1="{cy}" x2="{x2}" y2="{cy}" '
                  f'stroke="{GREEN}" stroke-width="2.2" '
                  f'marker-end="url(#arrow)"/>')

    for i, (num, title, accent, rows) in enumerate(STAGES):
        x = card_x(i)
        y = TOP
        out.append(f'<rect x="{x}" y="{y}" width="{CARD_W}" height="{CARD_H}" '
                  f'rx="12" fill="{CARD}" stroke="{CARD_EDGE}"/>')
        # accent tab + number badge
        out.append(f'<rect x="{x}" y="{y}" width="6" height="{CARD_H}" '
                  f'rx="3" fill="{accent}"/>')
        out.append(f'<circle cx="{x+26}" cy="{y+24}" r="10" fill="{accent}"/>')
        out.append(f'<text x="{x+26}" y="{y+28.5}" text-anchor="middle" '
                  f'font-size="12" font-weight="700" fill="#0e0e10">{num}</text>')
        out.append(f'<text x="{x+44}" y="{y+28.5}" font-size="13.5" '
                  f'font-weight="700" fill="{TEXT}">{esc(title)}</text>')
        # two rows of step / sub
        ry = y + 56
        for main, sub in rows:
            out.append(f'<text x="{x+20}" y="{ry}" class="mono" font-size="11.5" '
                      f'font-weight="600" fill="{TEXT}">{esc(main)}</text>')
            out.append(f'<text x="{x+20}" y="{ry+15}" font-size="10.5" '
                      f'fill="{MUTE}">{esc(sub)}</text>')
            ry += 38

    # caption
    out.append(f'<text x="{SVG_W/2}" y="{SVG_H-7}" text-anchor="middle" '
              f'font-size="11" fill="{MUTE}">Two user services + a GNOME '
              f'Shell extension. Nothing leaves your machine.</text>')
    out.append('</svg>')
    return "\n".join(out)


if __name__ == "__main__":
    import os
    here = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(here, "dicti-pipeline.svg")
    with open(path, "w") as fh:
        fh.write(build() + "\n")
    print("wrote", path)
