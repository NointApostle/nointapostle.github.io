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


# The mark: a small wing, on a 32 x 32 box.
MARK = ('<path fill="currentColor" d="M3 26 C4 14 12 5 29 3 C26 7 22 9 18 10 C22 10 25 10 27 11 '
        'C24 14 20 15 16 15.5 C19 16 22 16.5 24 18 C21 20 17 20.5 13 20.5 C15 21.5 17 22.5 19 24.5 '
        'C14 25.5 8 25.5 3 26 Z"/>')


# --- Text ---------------------------------------------------------------------

def a_or_an(phrase):
    return ('an ' if phrase[:1].lower() in 'aeiou' else 'a ') + phrase


def join_words(parts):
    return parts[0] if len(parts) == 1 else ', '.join(parts[:-1]) + ' and ' + parts[-1]


def summary(projects):
    return join_words([f"{p['name']}, {a_or_an(p['kind'][0].lower() + p['kind'][1:])}" for p in projects])


def word(n):
    return NUMBERS[n] if n < len(NUMBERS) else str(n)


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
        'MARK': MARK,
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

    # Preview image: the mark and the name on solid night blue.
    og = f'''<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630" viewBox="0 0 1200 630">
  <defs>
    <linearGradient id="name" x1="0" y1="0" x2="0.3" y2="1"><stop offset="0.1" stop-color="#FFFFFF"/><stop offset="0.6" stop-color="#AEB8C6"/><stop offset="1" stop-color="#7F8A9B"/></linearGradient>
  </defs>
  <rect width="1200" height="630" fill="#070A12"/>
  <g transform="translate(552 118) scale(3)" color="#EEF1F5">{MARK}</g>
  <text x="600" y="400" text-anchor="middle" font-family="Cormorant" font-weight="500" font-size="200" fill="url(#name)">Noint</text>
  <text x="600" y="482" text-anchor="middle" font-family="IBM Plex Sans" font-size="28" letter-spacing="3" fill="#8FB4EC">nointdev.xyz</text>
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
