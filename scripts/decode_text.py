"""Render text as an SVG that "decodes" from random symbols, left to right.

Usage: python scripts/decode_text.py "<text>" <out.svg> [top|bottom]
The optional last argument draws a divider line at that edge.
"""
import html
import random
import sys

from profile_cards import BAR, LINE, with_font

FG, JUNK = "#e6edf3", "#%&*+<>/\\=?@$!{}[]01"


def render(text, divider="", w=810, h=76, size=28):
    adv = size * 0.6  # JetBrains Mono advance width
    x0, y = w / 2 - adv * len(text) / 2, 48
    rnd = random.Random(7)
    parts = []
    for i, c in enumerate(text):
        if c == " ":
            continue
        x, settle, frames = x0 + adv * i, 0.6 + i * 0.16, 10
        for k in range(frames):
            t0, t1 = settle * k / frames, settle * (k + 1) / frames
            parts.append(
                f'<text x="{x:.1f}" y="{y}" fill="{BAR}" opacity="0">{html.escape(rnd.choice(JUNK))}'
                f'<set attributeName="opacity" to="1" begin="{t0:.2f}s" dur="{t1 - t0:.2f}s"/></text>'
            )
        parts.append(
            f'<text x="{x:.1f}" y="{y}" fill="{FG}" opacity="0">{html.escape(c)}'
            f'<set attributeName="opacity" to="1" begin="{settle:.2f}s"/></text>'
        )
    return wrap(parts, divider, w, h, size)


def wrap(parts, divider, w, h, size):
    line_y = {"top": 0.5, "bottom": h - 1}.get(divider)
    line = f'<line x1="0" y1="{line_y}" x2="{w}" y2="{line_y}" stroke="{LINE}"/>' if line_y else ""
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">'
        f"<style>text{{font-family:Mono,monospace;font-size:{size}px}}</style>{''.join(parts)}{line}</svg>\n"
    )


if __name__ == "__main__":
    assert render("ab").count("<set") == 22, "render self-check failed"
    svg, out = render(sys.argv[1], *sys.argv[3:4]), sys.argv[2]
    with open(out, "w") as f:
        f.write(with_font(svg))
