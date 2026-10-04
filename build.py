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
page is rebuilt. The preview image uses Cormorant and IBM Plex Sans, so have
them installed (or point FONTCONFIG_FILE at a config that has them).
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

# A feather pointing up, quill at the bottom, on a 120 x 370 box. Specks
# drift off the tip: it's coming apart, like an apostle's feathers do.
def feather(specks=True):
    out = [
        '<defs><linearGradient id="fg" x1="0" y1="0" x2="1" y2="1">'
        '<stop offset="0" stop-color="var(--silver-hi)"/><stop offset="1" stop-color="var(--silver-lo)"/>'
        '</linearGradient></defs>',
        '<path fill="url(#fg)" d="M60,40 C92,90 104,200 84,292 C78,315 68,330 60,335 '
        'C52,330 42,315 36,292 C16,200 28,90 60,40 Z"/>',
        # Splits in the vane.
        '<path d="M60,150 L97,182 M60,214 L25,240 M60,258 L90,282 M60,112 L34,132" '
        'stroke="var(--bg)" stroke-width="3" stroke-linecap="round" fill="none"/>',
        '<path d="M60,70 Q61,220 60,366" stroke="var(--silver-lo)" stroke-width="2.5" stroke-linecap="round" fill="none"/>',
    ]
    if specks:
        for x, y, r in [(66, 30, 3), (74, 18, 2.4), (58, 14, 2), (83, 8, 1.6), (70, 4, 1.4), (90, 22, 1.2), (50, 26, 1.6)]:
            out.append(f'<circle cx="{x}" cy="{y}" r="{r}" fill="var(--silver)"/>')
    return ''.join(out).replace('id="fg"', 'id="FGID"')

# The mark: a wing (the apostles' winged helmet), on a 32 x 32 box.
WING = ('<path fill="currentColor" d="M3 26 C4 14 12 5 29 3 C26 7 22 9 18 10 C22 10 25 10 27 11 '
        'C24 14 20 15 16 15.5 C19 16 22 16.5 24 18 C21 20 17 20.5 13 20.5 C15 21.5 17 22.5 19 24.5 '
        'C14 25.5 8 25.5 3 26 Z"/>')


def a_or_an(phrase):
    return ('an ' if phrase[:1].lower() in 'aeiou' else 'a ') + phrase


def summary(projects):
    parts = [f"{p['name']}, {a_or_an(p['kind'][0].lower() + p['kind'][1:])}" for p in projects]
    if len(parts) <= 1:
        return ''.join(parts)
    return ', '.join(parts[:-1]) + ' and ' + parts[-1]


def number_word(n):
    return NUMBERS[n] if n < len(NUMBERS) else str(n)


def count_text(projects):
    released = sum(p['status'] == 'released' for p in projects)
    building = sum(p['status'] == 'in-progress' for p in projects)
    first = {0: 'Nothing is out yet.', 1: 'One is out so far.'}.get(
        released, f'{number_word(released).capitalize()} are out so far.')
    if building:
        first += f" {number_word(building).capitalize()} {'is' if building == 1 else 'are'} being built."
    return first + " New ones go on the list below when they're ready."


def count_short(projects):
    released = sum(p['status'] == 'released' for p in projects)
    building = sum(p['status'] == 'in-progress' for p in projects)
    planned = sum(p['status'] == 'planned' for p in projects)
    parts = [f'{released} released'] if released else []
    if building:
        parts.append(f'{building} in progress')
    if planned:
        parts.append(f'{planned} planned')
    return ' · '.join(parts)


def row(index, p):
    e = html.escape
    ja = ''
    if p.get('ja'):
        ja = f' <span class="ja-{e(p.get("jaStyle", "sans"))}" lang="ja">{e(p["ja"])}</span>'
    icon = (f'<img src="{e(p["icon"])}" alt="" width="64" height="64" loading="lazy">'
            if p.get('icon') else '<span></span>')
    side = [f'<span class="status {e(p["status"])}">{STATUS[p["status"]]}</span>',
            f'<span class="meta">{e(" · ".join(p.get("platforms", [])))}</span>']
    if p.get('url'):
        side.append(f'<a href="{e(p["url"])}">{e(urlparse(p["url"]).netloc)}</a>')
    if p.get('releases'):
        side.append(f'<a href="{e(p["releases"])}">Releases</a>')
    specks = '<i></i>' * 6
    small = feather(specks=False).replace('FGID', f'fg-{e(p["id"])}').replace('url(#fg)', f'url(#fg-{e(p["id"])})')
    return f'''        <li class="project" id="{e(p["id"])}">
          <span class="num">{index:02d}</span>
          {icon}
          <div class="head">
            <h3>{e(p["name"])}{ja}</h3>
            <p class="kind">{e(p["kind"])}</p>
          </div>
          <div class="body"><p>{e(p["description"])}</p></div>
          <div class="side">{''.join(side)}</div>
          <span class="tip" aria-hidden="true"><svg viewBox="0 0 120 370">{small}</svg>{specks}</span>
        </li>'''


def jsonld(projects):
    parts = []
    for p in projects:
        item = {'@type': p.get('schemaType', 'SoftwareApplication'), 'name': p['name']}
        if p.get('ja'):
            item['alternateName'] = p['ja']
        if p.get('url'):
            item['url'] = p['url']
        item['operatingSystem'] = ', '.join(p.get('platforms', []))
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
    s = summary(projects)
    values = {
        'PROJECT_SUMMARY': html.escape(s),
        'PROJECT_SUMMARY_CAP': html.escape(s[:1].upper() + s[1:]),
        'JSONLD': jsonld(projects),
        'WING': WING,
        'BIG_FEATHER': feather().replace('FGID', 'fg-big').replace('url(#fg)', 'url(#fg-big)'),
        'COUNT_TEXT': html.escape(count_text(projects)),
        'COUNT_SHORT': html.escape(count_short(projects)),
        'PROJECT_ROWS': '\n'.join(row(i + 1, p) for i, p in enumerate(projects)),
        'YEAR': str(datetime.date.today().year),
    }
    for key, value in values.items():
        page = page.replace('{{' + key + '}}', value)
    assert '{{' not in page, 'a placeholder in template.html was not filled in'
    open(os.path.join(ROOT, 'index.html'), 'w', encoding='utf-8').write(page)


# Plain colours for the images, which can't use the page's CSS variables.
LIGHT = {'--bg': '#F4F5F7', '--silver-hi': '#EEF1F4', '--silver': '#B4BCC7', '--silver-lo': '#858F9C'}
DARK = {'--bg': '#0D1015', '--silver-hi': '#DCE2EA', '--silver': '#8D97A5', '--silver-lo': '#59626F'}


def with_colours(svg, colours):
    for name, value in colours.items():
        svg = svg.replace(f'var({name})', value)
    return svg


def render(svg_text, path, width, height):
    tmp = path + '.svg'
    open(tmp, 'w', encoding='utf-8').write(svg_text)
    subprocess.run(['rsvg-convert', '-w', str(width), '-h', str(height), tmp, '-o', path], check=True)
    subprocess.run(['magick', path, '-strip', '-define', 'png:compression-level=9', path], check=True)
    os.remove(tmp)


def build_images():
    assets = os.path.join(ROOT, 'assets')
    # Favicon: the wing in silver-white on night blue, so it reads on light and dark tabs.
    icon = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">'
            f'<rect width="32" height="32" rx="7" fill="#141820"/>'
            f'<g transform="translate(3.5 3.5) scale(0.78)" color="#E7EAEF">{WING}</g></svg>')
    open(os.path.join(assets, 'favicon.svg'), 'w', encoding='utf-8').write(icon)
    render(icon, os.path.join(assets, 'favicon.png'), 48, 48)
    render(icon, os.path.join(assets, 'apple-touch-icon.png'), 180, 180)

    big = with_colours(feather().replace('FGID', 'fg').replace('url(#fg)', 'url(#fg)'), DARK)
    og = f'''<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630" viewBox="0 0 1200 630">
  <rect width="1200" height="630" fill="#0D1015"/>
  <g transform="translate(960 40) rotate(28 60 185) scale(1.45)">{big}</g>
  <g transform="translate(100 60) scale(2.6)" color="#E7EAEF">{WING}</g>
  <text x="96" y="300" font-family="Cormorant" font-weight="600" font-size="150" fill="#E7EAEF">Noint</text>
  <text x="100" y="400" font-family="IBM Plex Sans" font-size="38" fill="#A6AEBA">Apps that work offline. No account needed.</text>
  <text x="100" y="530" font-family="IBM Plex Sans" font-size="28" fill="#8FB4EC">nointdev.xyz</text>
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
