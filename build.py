#!/usr/bin/env python3
"""Builds index.html from template.html and projects.json, and draws the
favicons and the link preview image into assets/.

To add a project, add an entry to projects.json and run:

    python3 build.py

Fields: id, name, ja (Japanese name, optional), jaStyle ("sans" or "serif"),
kind (a few words, e.g. "Habit and goal tracker"), description (a sentence
or two), platforms (list), status ("released", "in-progress" or "planned"),
url and releases (optional links), icon (path under assets/, optional),
schemaType and category (for search engines; see schema.org).

The images need rsvg-convert and ImageMagick (magick); without them only the
page is rebuilt. The preview image uses Cormorant, so have it installed (or
point FONTCONFIG_FILE at a config that has it).
"""
import datetime
import html
import json
import os
import random
import shutil
import subprocess
from urllib.parse import urlparse

ROOT = os.path.dirname(os.path.abspath(__file__))
STATUS = {'released': 'Out now', 'in-progress': 'Being built', 'planned': 'Planned'}
NUMBERS = ['no', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten']


# --- Drawings -----------------------------------------------------------------

def feather(fill, notch='#0D1424'):
    """One feather pointing up, quill at the bottom, on a 120 x 370 box."""
    return (
        f'<path fill="{fill}" d="M60,40 C92,90 104,200 84,292 C78,315 68,330 60,335 '
        'C52,330 42,315 36,292 C16,200 28,90 60,40 Z"/>'
        '<path d="M60,150 L97,182 M60,214 L25,240 M60,258 L90,282 M60,112 L34,132" '
        f'stroke="{notch}" stroke-opacity="0.55" stroke-width="3" stroke-linecap="round" fill="none"/>'
        '<path d="M60,70 Q61,220 60,366" stroke="#7F8A9B" stroke-width="2.5" stroke-linecap="round" fill="none"/>'
    )


def _leaf(length, half_width):
    L, W = length, half_width
    return (f'M0,0 C{L*0.25:.1f},{-W:.1f} {L*0.75:.1f},{-W*1.05:.1f} {L:.1f},0 '
            f'C{L*0.75:.1f},{W*0.95:.1f} {L*0.25:.1f},{W*0.9:.1f} 0,0 Z')


def _bezier(p0, p1, p2, t):
    return tuple((1 - t) ** 2 * a + 2 * (1 - t) * t * b + t * t * c for a, b, c in zip(p0, p1, p2))


def wing(prefix):
    """A wing on a 1000 x 640 box: long flight feathers hanging from the arm,
    with two rows of shorter covering feathers over them."""
    defs = (
        f'<defs>'
        f'<linearGradient id="{prefix}1" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#D3DDEC"/><stop offset="1" stop-color="#4C5B75"/></linearGradient>'
        f'<linearGradient id="{prefix}2" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#E6ECF5"/><stop offset="1" stop-color="#7D8DA6"/></linearGradient>'
        f'<linearGradient id="{prefix}3" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#F2F5FA"/><stop offset="1" stop-color="#A6B4C8"/></linearGradient>'
        f'</defs>'
    )
    shoulder, bend, tip = (40, 420), (120, 0), (520, 40)
    layers = [  # count, shortest and longest, width, angle at shoulder and tip, fill, part of the arm
        (26, (150, 430), 0.16, (120, 8), f'url(#{prefix}1)', (0.0, 1.0)),
        (20, (80, 200), 0.21, (112, 22), f'url(#{prefix}2)', (0.02, 0.92)),
        (18, (50, 110), 0.2, (80, 20), f'url(#{prefix}3)', (0.0, 0.8)),
    ]
    out = []
    for count, (short, long_), width, (a0, a1), fill, (t0, t1) in layers:
        for i in reversed(range(count)):
            u = i / (count - 1)
            x, y = _bezier(shoulder, bend, tip, t0 + (t1 - t0) * u)
            length = short + (long_ - short) * u ** 1.4
            angle = a0 + (a1 - a0) * u
            out.append(f'<path transform="translate({x:.1f} {y:.1f}) rotate({angle:.1f})" '
                       f'd="{_leaf(length, length * width)}" fill="{fill}" '
                       'stroke="#0D1424" stroke-opacity="0.55" stroke-width="1.2"/>')
    return defs + f'<g transform="translate(60 40) scale(0.95)">{"".join(out)}</g>'


# The mark: a small wing, on a 32 x 32 box.
MARK = ('<path fill="currentColor" d="M3 26 C4 14 12 5 29 3 C26 7 22 9 18 10 C22 10 25 10 27 11 '
        'C24 14 20 15 16 15.5 C19 16 22 16.5 24 18 C21 20 17 20.5 13 20.5 C15 21.5 17 22.5 19 24.5 '
        'C14 25.5 8 25.5 3 26 Z"/>')


def star_dots(width, height, count, seed):
    rng = random.Random(seed)
    dots = []
    for _ in range(count):
        x, y = rng.uniform(0, width), rng.uniform(0, height)
        r = rng.choice([0.6, 0.7, 0.8, 1.0, 1.0, 1.3, 1.7])
        o = rng.uniform(0.25, 0.85)
        dots.append(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="{r}" fill="#DCE4F0" opacity="{o:.2f}"/>')
    return ''.join(dots)


def falling(count=9, seed=4):
    """Feathers that drift down the page. Positions are fixed by the seed, so
    every build gives the same page."""
    rng = random.Random(seed)
    spans = []
    for i in range(count):
        x = (i + rng.uniform(0.1, 0.9)) / count * 100
        style = (f'--x:{x:.1f}%;--y:{rng.uniform(5, 90):.0f}%;--w:{rng.choice([18, 22, 26, 30, 36])}px;'
                 f'--d:{rng.uniform(16, 30):.1f}s;--delay:{-rng.uniform(0, 30):.1f}s;'
                 f'--o:{rng.uniform(0.4, 0.75):.2f};--r:{rng.uniform(-40, 40):.0f}deg')
        spans.append(f'    <span style="{style}"><svg viewBox="0 0 120 370"><use href="#feather"/></svg></span>')
    return '\n'.join(spans)


# --- Text ---------------------------------------------------------------------

def a_or_an(phrase):
    return ('an ' if phrase[:1].lower() in 'aeiou' else 'a ') + phrase


def join_words(parts):
    return parts[0] if len(parts) == 1 else ', '.join(parts[:-1]) + ' and ' + parts[-1]


def summary(projects):
    return join_words([f"{p['name']}, {a_or_an(p['kind'][0].lower() + p['kind'][1:])}" for p in projects])


def word(n):
    return NUMBERS[n] if n < len(NUMBERS) else str(n)


def count_text(projects):
    released = sum(p['status'] == 'released' for p in projects)
    coming = sum(p['status'] in ('in-progress', 'planned') for p in projects)
    text = f'{word(released).capitalize()} out so far.' if released else "Nothing's out yet."
    if coming:
        text += f' {word(coming).capitalize()} on the way.'
    return text


def count_short(projects):
    parts = []
    for status, label in [('released', 'released'), ('in-progress', 'in progress'), ('planned', 'planned')]:
        n = sum(p['status'] == status for p in projects)
        if n:
            parts.append(f'{n} {label}')
    return ' · '.join(parts)


# --- Page ---------------------------------------------------------------------

def row(index, p):
    e = html.escape
    ja = f' <span class="ja-{e(p.get("jaStyle", "sans"))}" lang="ja">{e(p["ja"])}</span>' if p.get('ja') else ''
    icon = (f'<img src="{e(p["icon"])}" alt="" width="64" height="64" loading="lazy">'
            if p.get('icon') else '<span></span>')
    side = [f'<span class="status {e(p["status"])}">{STATUS[p["status"]]}</span>',
            f'<span class="meta">{e(" · ".join(p.get("platforms", [])))}</span>']
    if p.get('url'):
        side.append(f'<a href="{e(p["url"])}">{e(urlparse(p["url"]).netloc)}</a>')
    if p.get('releases'):
        side.append(f'<a href="{e(p["releases"])}">Releases</a>')
    return f'''        <li class="project" id="{e(p["id"])}">
          <span class="num">{index:02d}</span>
          {icon}
          <div class="head">
            <h3>{e(p["name"])}{ja}</h3>
            <p class="kind">{e(p["kind"])}</p>
          </div>
          <div class="body"><p>{e(p["description"])}</p></div>
          <div class="side">{''.join(side)}</div>
          <span class="tip" aria-hidden="true"><svg viewBox="0 0 120 370"><use href="#feather"/></svg>{'<i></i>' * 6}</span>
        </li>'''


def jsonld(projects):
    parts = []
    for p in projects:
        item = {'@type': p.get('schemaType', 'SoftwareApplication'), 'name': p['name']}
        if p.get('ja'):
            item['alternateName'] = p['ja']
        if p.get('url'):
            item['url'] = p['url']
        if p.get('platforms'):
            item['operatingSystem'] = ', '.join(p['platforms'])
        if p.get('category'):
            item['applicationCategory'] = p['category']
        item['description'] = p['description']
        parts.append(item)
    data = {
        '@context': 'https://schema.org',
        '@type': 'WebSite',
        'name': 'Noint',
        'url': 'https://nointdev.xyz/',
        'author': {'@type': 'Person', 'name': 'Noint', 'url': 'https://github.com/NointApostle'},
        'hasPart': parts,
    }
    return '\n'.join('  ' + line for line in json.dumps(data, ensure_ascii=False, indent=2).splitlines())


def build_page(projects):
    page = open(os.path.join(ROOT, 'template.html'), encoding='utf-8').read()
    values = {
        'PROJECT_SUMMARY': html.escape(summary(projects)),
        'PROJECT_NAMES': html.escape(join_words([p['name'] for p in projects])),
        'JSONLD': jsonld(projects),
        'FEATHER': feather('url(#feather-fill)'),
        'STARS': ('<svg viewBox="0 0 1000 1000" preserveAspectRatio="xMidYMid slice">'
                  + star_dots(1000, 1000, 110, 9) + '</svg>'),
        'FALLING': falling(),
        'MARK': MARK,
        'WING': wing('wg'),
        'COUNT_TEXT': html.escape(count_text(projects)),
        'COUNT_SHORT': html.escape(count_short(projects)),
        'PROJECT_ROWS': '\n'.join(row(i + 1, p) for i, p in enumerate(projects)),
        'YEAR': str(datetime.date.today().year),
    }
    for key, value in values.items():
        page = page.replace('{{' + key + '}}', value)
    assert '{{' not in page, 'a placeholder in template.html was not filled in'
    open(os.path.join(ROOT, 'index.html'), 'w', encoding='utf-8').write(page)


# --- Images -------------------------------------------------------------------

def render(svg_text, path, width, height):
    tmp = path + '.svg'
    open(tmp, 'w', encoding='utf-8').write(svg_text)
    subprocess.run(['rsvg-convert', '-w', str(width), '-h', str(height), tmp, '-o', path], check=True)
    subprocess.run(['magick', path, '-strip', '-define', 'png:compression-level=9', path], check=True)
    os.remove(tmp)


def build_images():
    assets = os.path.join(ROOT, 'assets')
    # Favicon: the wing in silver-white on night blue.
    icon = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">'
            '<rect width="32" height="32" rx="7" fill="#0D1424"/>'
            f'<g transform="translate(3.5 3.5) scale(0.78)" color="#EEF1F5">{MARK}</g></svg>')
    open(os.path.join(assets, 'favicon.svg'), 'w', encoding='utf-8').write(icon)
    render(icon, os.path.join(assets, 'favicon.png'), 48, 48)
    render(icon, os.path.join(assets, 'apple-touch-icon.png'), 180, 180)

    # Preview image: the name under the wing, in the night sky, with a few feathers falling.
    fall = ''.join(
        f'<g transform="translate({x} {y}) rotate({r}) scale({s})" opacity="{o}">{feather("url(#ff)")}</g>'
        for x, y, r, s, o in [(120, 420, -30, 0.2, 0.6), (1060, 440, 25, 0.24, 0.65),
                              (230, 60, -15, 0.15, 0.5), (820, 520, 40, 0.17, 0.5), (60, 140, 20, 0.13, 0.4)]
    )
    og = f'''<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630" viewBox="0 0 1200 630">
  <defs>
    <linearGradient id="sky" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#070A12"/><stop offset="0.6" stop-color="#0D1424"/><stop offset="1" stop-color="#070A12"/></linearGradient>
    <radialGradient id="glow" cx="0.42" cy="0.5" r="0.5"><stop offset="0" stop-color="#5888E6" stop-opacity="0.32"/><stop offset="1" stop-color="#5888E6" stop-opacity="0"/></radialGradient>
    <linearGradient id="name" x1="0" y1="0" x2="0.3" y2="1"><stop offset="0.1" stop-color="#FFFFFF"/><stop offset="0.6" stop-color="#AEB8C6"/><stop offset="1" stop-color="#7F8A9B"/></linearGradient>
    <filter id="shade" x="-20%" y="-20%" width="140%" height="160%"><feDropShadow dx="0" dy="6" stdDeviation="18" flood-color="#070A12" flood-opacity="0.85"/></filter>
    <linearGradient id="ff" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#EEF1F5"/><stop offset="1" stop-color="#7F8A9B"/></linearGradient>
  </defs>
  <rect width="1200" height="630" fill="url(#sky)"/>
  {star_dots(1200, 630, 90, 3)}
  <rect width="1200" height="630" fill="url(#glow)"/>
  <g transform="translate(470 -150) scale(0.9)" opacity="0.45">{wing('og')}</g>
  {fall}
  <text x="600" y="380" text-anchor="middle" font-family="Cormorant" font-weight="500" font-size="230" fill="url(#name)" filter="url(#shade)">Noint</text>
  <text x="600" y="470" text-anchor="middle" font-family="IBM Plex Sans" font-size="30" letter-spacing="3" fill="#8FB4EC">nointdev.xyz</text>
</svg>'''
    render(og, os.path.join(assets, 'og-image.png'), 1200, 630)


if __name__ == '__main__':
    projects = json.load(open(os.path.join(ROOT, 'projects.json'), encoding='utf-8'))
    for p in projects:
        assert p['status'] in STATUS, f"{p['name']}: status must be one of {', '.join(STATUS)}"
    build_page(projects)
    if shutil.which('rsvg-convert') and shutil.which('magick'):
        build_images()
    print(f'Built index.html with {len(projects)} projects.')
