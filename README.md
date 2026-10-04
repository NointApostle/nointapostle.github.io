# nointdev.xyz

Noint's home page: a short intro and the list of apps, each linking to its own site on a subdomain (kizamu.nointdev.xyz, itogatari.nointdev.xyz).

The look borrows from Noint, the ninth apostle in *Arifureta*, without using the show's art: silver on solid night blue, a wing for the mark, and a feather on each row that comes apart into specks on hover. Projects are numbered, like the apostles.

## Adding a project

1. Put its icon in `assets/` (a square PNG, 256 px is plenty).
2. Add an entry to `projects.json`. `status` is `released`, `in-progress` or `planned`; `url` and `releases` are optional, so a planned project can go in before it has a site.
3. Run `python3 build.py`. It rewrites `index.html` and redraws the favicons and the link preview image.

Edit `template.html` and `projects.json`, not `index.html`.

## Hosting

GitHub Pages, with `CNAME` set to `nointdev.xyz`. The domain's DNS needs these records:

| Type | Name | Value |
|---|---|---|
| A | `@` | `185.199.108.153` |
| A | `@` | `185.199.109.153` |
| A | `@` | `185.199.110.153` |
| A | `@` | `185.199.111.153` |
| CNAME | `www` | `nointapostle.github.io` |
| CNAME | `kizamu` | `nointapostle.github.io` |
| CNAME | `itogatari` | `nointapostle.github.io` |
