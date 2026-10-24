"""Render the profile README cards (contributions per year, stats, languages) as SVG.

Usage: GITHUB_TOKEN=... python scripts/profile_cards.py <user> <out_dir>
"""
import base64
import html
import json
import os
import re
import sys
import urllib.parse
import urllib.request

BG, LINE, MUTED, TEXT, TITLE, BAR = "#0d1117", "#2e343b", "#8b949e", "#c9d1d9", "#58a6ff", "#40c463"
STYLE = (
    "<style>text{font-family:Mono,ui-monospace,Menlo,Consolas,monospace}"
    f".t{{fill:{TITLE};font-size:16px;font-weight:600}}.s{{fill:{MUTED};font-size:13px}}"
    f".v{{fill:{TEXT};font-size:13px;font-weight:600}}.c{{fill:{MUTED};font-size:12px}}</style>"
)


def frame(w, h, title, body, right=""):
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">{STYLE}'
        f'<rect x="0.5" y="0.5" width="{w - 1}" height="{h - 1}" rx="5" fill="{BG}" stroke="{LINE}"/>'
        f'<text x="20" y="34" class="t">{title}</text>'
        f'<text x="{w - 20}" y="34" class="s" text-anchor="end">{right}</text>{body}</svg>\n'
    )


def with_font(svg):
    """Embed JetBrains Mono, subset by Google Fonts to the glyphs this SVG uses."""
    chars = "".join(sorted(set(html.unescape("".join(re.findall(r">([^<>]+)<", svg))))))
    url = "https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@500&text=" + urllib.parse.quote(chars)
    get = lambda u: urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "curl"}), timeout=30).read()
    font_url = re.search(r"url\(([^)]+)\)", get(url).decode()).group(1)
    face = "@font-face{font-family:Mono;src:url(data:font/ttf;base64,%s)}" % base64.b64encode(get(font_url)).decode()
    return svg.replace("<style>", "<style>" + face, 1)


def gql(query, token):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query}).encode(),
        headers={"Authorization": f"bearer {token}", "User-Agent": "profile-cards"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        body = json.load(r)
    if "errors" in body:
        raise SystemExit(body["errors"])
    return body["data"]["user"]


def fetch_years(user, token):
    years = gql(f'{{user(login:"{user}"){{contributionsCollection{{contributionYears}}}}}}', token)
    years = sorted(years["contributionsCollection"]["contributionYears"])
    parts = " ".join(
        f'y{y}: contributionsCollection(from:"{y}-01-01T00:00:00Z", to:"{y}-12-31T23:59:59Z")'
        "{contributionCalendar{totalContributions}}"
        for y in years
    )
    data = gql(f'{{user(login:"{user}"){{{parts}}}}}', token)
    return [(y, data[f"y{y}"]["contributionCalendar"]["totalContributions"]) for y in years]


def fetch_profile(user, token):
    # shortcut: first 100 owned repos only, fine until the account has more than that
    return gql(
        f'{{user(login:"{user}"){{'
        "pullRequests{totalCount} issues{totalCount}"
        " contributionsCollection{totalCommitContributions}"
        " repositories(first:100, ownerAffiliations:OWNER, isFork:false, privacy:PUBLIC){totalCount nodes{"
        "stargazerCount languages(first:10){edges{size node{name color}}}}}}}",
        token,
    )


def render_years(counts, w=810, h=220):
    total = sum(c for _, c in counts)
    top = max((c for _, c in counts), default=0) or 1
    x0, y0, plot_h = 30, 180, 115  # baseline y and max bar height
    slot = (w - 2 * x0) / max(len(counts), 1)
    bw = min(36, slot * 0.6)
    bars = []
    for i, (year, c) in enumerate(counts):
        bh = max(2, c / top * plot_h)
        cx = x0 + slot * i + slot / 2
        bars.append(
            f'<rect x="{cx - bw / 2:.1f}" y="{y0 - bh:.1f}" width="{bw:.1f}" height="{bh:.1f}" rx="3" fill="{BAR}"/>'
            f'<text x="{cx:.1f}" y="{y0 - bh - 6:.1f}" class="c" text-anchor="middle">{c:,}</text>'
            f'<text x="{cx:.1f}" y="{y0 + 18}" class="c" text-anchor="middle">{year}</text>'
        )
    body = f'<line x1="{x0}" y1="{y0}" x2="{w - x0}" y2="{y0}" stroke="{LINE}"/>' + "".join(bars)
    return frame(w, h, "Contributions over the years", body, f"{total:,} total")


def render_stats(p, w=400, h=150):
    repos = p["repositories"]
    rows = [
        ("Commits (last year)", p["contributionsCollection"]["totalCommitContributions"]),
        ("Pull requests", p["pullRequests"]["totalCount"]),
        ("Issues", p["issues"]["totalCount"]),
        ("Public repos", repos["totalCount"]),
        ("Stars earned", sum(r["stargazerCount"] for r in repos["nodes"])),
    ]
    body = "".join(
        f'<text x="20" y="{62 + i * 18}" class="s">{k}</text>'
        f'<text x="{w - 20}" y="{62 + i * 18}" class="v" text-anchor="end">{v:,}</text>'
        for i, (k, v) in enumerate(rows)
    )
    return frame(w, h, "GitHub stats", body)


def render_langs(p, w=400, h=150, n=6):
    sizes, colors = {}, {}
    for repo in p["repositories"]["nodes"]:
        for e in repo["languages"]["edges"]:
            name = e["node"]["name"]
            sizes[name] = sizes.get(name, 0) + e["size"]
            colors[name] = e["node"]["color"] or MUTED
    top = sorted(sizes.items(), key=lambda kv: -kv[1])[:n]
    total = sum(s for _, s in top) or 1
    bar_w, x, segs, legend = w - 40, 20.0, [], []
    for i, (name, s) in enumerate(top):
        seg = s / total * bar_w
        segs.append(f'<rect x="{x:.1f}" y="50" width="{seg:.1f}" height="8" fill="{colors[name]}"/>')
        x += seg
        lx, ly = 20 + (i % 2) * (bar_w / 2), 84 + (i // 2) * 20
        legend.append(
            f'<circle cx="{lx + 5}" cy="{ly - 4}" r="5" fill="{colors[name]}"/>'
            f'<text x="{lx + 16}" y="{ly}" class="s">{name} {s / total * 100:.1f}%</text>'
        )
    clip = f'<clipPath id="r"><rect x="20" y="50" width="{bar_w}" height="8" rx="4"/></clipPath>'
    return frame(w, h, "Most used languages", f'{clip}<g clip-path="url(#r)">{"".join(segs)}</g>{"".join(legend)}')


if __name__ == "__main__":
    fake = {
        "pullRequests": {"totalCount": 2}, "issues": {"totalCount": 1},
        "contributionsCollection": {"totalCommitContributions": 5},
        "repositories": {"totalCount": 1, "nodes": [{"stargazerCount": 3, "languages": {"edges": [
            {"size": 75, "node": {"name": "TypeScript", "color": "#3178c6"}},
            {"size": 25, "node": {"name": "Python", "color": None}}]}}]},
    }
    assert "10 total" in render_years([(2023, 10), (2024, 0)]), "years self-check failed"
    assert ">3<" in render_stats(fake), "stats self-check failed"
    assert "TypeScript 75.0%" in render_langs(fake), "langs self-check failed"

    user, out = sys.argv[1], sys.argv[2]
    token = os.environ["GITHUB_TOKEN"]
    os.makedirs(out, exist_ok=True)
    profile = fetch_profile(user, token)
    cards = {
        "contributions-years.svg": render_years(fetch_years(user, token)),
        "stats.svg": render_stats(profile),
        "languages.svg": render_langs(profile),
    }
    for name, svg in cards.items():
        with open(os.path.join(out, name), "w") as f:
            f.write(with_font(svg))
