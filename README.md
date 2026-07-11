# weirdmachine64 - security research site

A fast, zero-dependency static site for publishing security research, hosted on
GitHub Pages. Posts are written in Markdown and built into static HTML by a single
Python script - no Node, no Ruby, no build servers.

```
config.py                     # site identity: handle, title, socials, accent color
build.py                      # the generator (Markdown -> docs/)  + a tiny dev server
posts/                        # your writeups, as Markdown with front matter
assets/                       # style.css, main.js, img/  (copied into docs/ on build)
docs/                         # GENERATED output, gitignored, built by CI on every push
.github/workflows/deploy.yml  # builds and deploys docs/ to GitHub Pages
```

## Write a post

Create `posts/YYYY-MM-DD-my-slug.md`:

```markdown
---
title: My vulnerability writeup
date: 2026-07-11
tags: [web, oauth, bug-bounty]
summary: One-line teaser shown in listings and meta description.
draft: false
---

# Your markdown here

Standalone images become captioned figures - the alt text is the caption:

![This caption shows under the image.](../assets/img/my-screenshot.png)
```

Put images in `assets/img/`. Reference them from a post as `../assets/img/NAME`.

## Build & preview

```bash
python3 build.py            # build into ./docs
python3 build.py --serve    # build, then serve at http://localhost:8000
```

## Deploy to GitHub Pages

The site is built and deployed by `.github/workflows/deploy.yml` on every push
to `main`. Nothing to build locally before pushing; `docs/` is gitignored.

1. Create the repo and push (one time):

   ```bash
   gh auth login
   gh repo create weirdmachine64.github.io --public --source=. --remote=origin --push
   ```

   > Naming the repo `<username>.github.io` serves it at the root domain.
   > Any other name serves it at `https://<username>.github.io/<repo>/`.

2. In the repo: **Settings → Pages → Build and deployment →**
   **Source: GitHub Actions.** (The workflow will show up as an available option
   once it's pushed.)

3. After every change: `git add -A && git commit -m "update" && git push`
   Actions builds the site and deploys it automatically, live within a minute or two.
   Check progress under the repo's **Actions** tab.

To preview locally before pushing: `python3 build.py --serve` (serves the same
output at `http://localhost:8000`, gitignored so it never gets committed).

## Customize

- **Identity / socials:** edit `config.py`.
- **Accent color & theme:** `--accent` and friends at the top of `assets/style.css`.
- **Projects list:** the `build_projects()` function in `build.py`.
- **About page:** the `build_about()` function in `build.py`.
