#!/usr/bin/env python3
"""
Zero-dependency static site generator for a security-research blog.

Usage:
    python3 build.py            # build into ./docs
    python3 build.py --serve    # build, then serve ./docs at http://localhost:8000

Write posts as Markdown files in ./posts with a small front-matter header:

    ---
    title: Heap overflow in libfoo 1.2
    date: 2026-07-11
    tags: [pwn, cve, heap]
    summary: One-line teaser shown in listings.
    draft: false
    ---

    # Your markdown here
"""
import os, re, sys, shutil, html, json, datetime, http.server, socketserver
import urllib.request, urllib.error
from config import SITE, CVES

ROOT   = os.path.dirname(os.path.abspath(__file__))
POSTS  = os.path.join(ROOT, "posts")
ASSETS = os.path.join(ROOT, "assets")
OUT    = os.path.join(ROOT, "docs")


# ---------------------------------------------------------------------------
# Minimal Markdown -> HTML  (headings, code fences, lists, quotes, tables,
# rules, links, images, inline code/bold/italic). Good enough for writeups.
# ---------------------------------------------------------------------------
def esc(s):
    return html.escape(s, quote=False)


def inline(text):
    # Protect inline code spans first.
    codes = []
    def stash(m):
        codes.append(m.group(1))
        return f"\x00{len(codes)-1}\x00"
    text = re.sub(r"`([^`]+)`", stash, text)

    text = esc(text)
    # images  ![alt](src)
    text = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)",
                  r'<img src="\2" alt="\1" loading="lazy">', text)
    # links  [text](href)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)",
                  r'<a href="\2">\1</a>', text)
    # bold / italic
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", text)
    # restore code spans (escaped)
    text = re.sub(r"\x00(\d+)\x00",
                  lambda m: f"<code>{esc(codes[int(m.group(1))])}</code>", text)
    return text


def markdown(md):
    lines = md.split("\n")
    out, i, n = [], 0, len(lines)

    def close_list(stack):
        while stack:
            out.append("</ul>" if stack.pop() == "ul" else "</ol>")

    list_stack = []
    while i < n:
        line = lines[i]

        # fenced code block
        m = re.match(r"^```(\w+)?\s*$", line)
        if m:
            close_list(list_stack)
            lang = m.group(1) or "text"
            buf = []
            i += 1
            while i < n and not re.match(r"^```\s*$", lines[i]):
                buf.append(lines[i]); i += 1
            i += 1
            code = esc("\n".join(buf))
            out.append(
                f'<div class="code"><div class="code__bar">'
                f'<span class="code__lang">{esc(lang)}</span>'
                f'<button class="code__copy" type="button">copy</button></div>'
                f'<pre><code class="language-{esc(lang)}">{code}</code></pre></div>')
            continue

        # blank line
        if line.strip() == "":
            close_list(list_stack)
            i += 1
            continue

        # heading
        m = re.match(r"^(#{1,6})\s+(.*)$", line)
        if m:
            close_list(list_stack)
            lvl = len(m.group(1))
            txt = inline(m.group(2).strip())
            slug = re.sub(r"[^a-z0-9]+", "-", m.group(2).strip().lower()).strip("-")
            out.append(f'<h{lvl} id="{slug}">{txt}</h{lvl}>')
            i += 1
            continue

        # standalone image/video -> <figure> with caption from alt text
        # (greedy alt so brackets like [::1] inside the caption are allowed)
        m = re.match(r"^!\[(.*)\]\(([^)]+)\)\s*$", line)
        if m:
            close_list(list_stack)
            alt, src = m.group(1), m.group(2)
            cap = f'<figcaption>{inline(alt)}</figcaption>' if alt.strip() else ""
            if src.lower().split("?")[0].endswith((".webm", ".mp4", ".mov", ".ogg")):
                media = (f'<video src="{esc(src)}" controls preload="metadata" '
                         f'playsinline></video>')
            else:
                media = f'<img src="{esc(src)}" alt="{esc(alt)}" loading="lazy">'
            out.append(f'<figure>{media}{cap}</figure>')
            i += 1
            continue

        # horizontal rule
        if re.match(r"^(\*{3,}|-{3,}|_{3,})\s*$", line):
            close_list(list_stack)
            out.append("<hr>")
            i += 1
            continue

        # blockquote
        if line.startswith(">"):
            close_list(list_stack)
            buf = []
            while i < n and lines[i].startswith(">"):
                buf.append(lines[i][1:].lstrip()); i += 1
            out.append(f"<blockquote>{inline(' '.join(buf))}</blockquote>")
            continue

        # table  | a | b |
        if line.strip().startswith("|") and i + 1 < n and re.match(r"^\s*\|[\s:|-]+\|\s*$", lines[i+1]):
            header = [c.strip() for c in line.strip().strip("|").split("|")]
            i += 2
            rows = []
            while i < n and lines[i].strip().startswith("|"):
                rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
                i += 1
            th = "".join(f"<th>{inline(c)}</th>" for c in header)
            trs = "".join("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>" for r in rows)
            out.append(f"<div class='tablewrap'><table><thead><tr>{th}</tr></thead><tbody>{trs}</tbody></table></div>")
            continue

        # lists
        m = re.match(r"^(\s*)([-*+]|\d+\.)\s+(.*)$", line)
        if m:
            ordered = bool(re.match(r"\d+\.", m.group(2)))
            want = "ol" if ordered else "ul"
            if not list_stack or list_stack[-1] != want:
                close_list(list_stack)
                out.append(f"<{want}>")
                list_stack.append(want)
            buf = [m.group(3)]
            i += 1
            # soft-wrapped continuation lines belong to the same <li>
            while i < n and lines[i].strip() and not re.match(
                    r"^(#{1,6}\s|```|>|\s*([-*+]|\d+\.)\s|\||(\*{3,}|-{3,}|_{3,})\s*$)",
                    lines[i]):
                buf.append(lines[i].strip())
                i += 1
            out.append(f"<li>{inline(' '.join(buf))}</li>")
            continue

        # paragraph (accumulate until blank)
        close_list(list_stack)
        buf = [line]
        i += 1
        while i < n and lines[i].strip() and not re.match(r"^(#{1,6}\s|```|>|\s*([-*+]|\d+\.)\s|\||(\*{3,}|-{3,}|_{3,})\s*$)", lines[i]):
            buf.append(lines[i]); i += 1
        out.append(f"<p>{inline(' '.join(buf))}</p>")

    close_list(list_stack)
    return "\n".join(out)


# ---------------------------------------------------------------------------
# Post loading + front matter
# ---------------------------------------------------------------------------
def parse_post(path):
    raw = open(path, encoding="utf-8").read()
    meta, body = {}, raw
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", raw, re.S)
    if m:
        body = m.group(2)
        for ln in m.group(1).split("\n"):
            if ":" not in ln:
                continue
            k, v = ln.split(":", 1)
            k, v = k.strip(), v.strip()
            if v.startswith("[") and v.endswith("]"):
                v = [x.strip() for x in v[1:-1].split(",") if x.strip()]
            meta[k] = v
    slug = os.path.splitext(os.path.basename(path))[0]
    slug = re.sub(r"^\d{4}-\d{2}-\d{2}-", "", slug)
    meta.setdefault("title", slug)
    meta.setdefault("date", "1970-01-01")
    meta.setdefault("tags", [])
    meta.setdefault("summary", "")
    if isinstance(meta["tags"], str):
        meta["tags"] = [meta["tags"]] if meta["tags"] else []
    meta["slug"] = slug
    meta["draft"] = str(meta.get("draft", "false")).lower() == "true"
    meta["html"] = markdown(body)
    words = len(re.findall(r"\w+", body))
    meta["read"] = max(1, round(words / 200))
    return meta


def load_posts():
    posts = []
    if os.path.isdir(POSTS):
        for f in os.listdir(POSTS):
            if f.endswith(".md"):
                p = parse_post(os.path.join(POSTS, f))
                if not p["draft"]:
                    posts.append(p)
    posts.sort(key=lambda p: p["date"], reverse=True)
    return posts


# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------
def render(tpl, **kw):
    for k, v in kw.items():
        tpl = tpl.replace("{{%s}}" % k, str(v))
    return tpl


def nav(active, depth=0):
    up = "../" * depth
    items = [("~", up + "index.html", "home"),
             ("research", up + "research/index.html", "research"),
             ("cves", up + "cves.html", "cves"),
             ("projects", up + "projects.html", "projects"),
             ("about", up + "about.html", "about")]
    links = ""
    for label, href, key in items:
        cls = "nav__link is-active" if key == active else "nav__link"
        links += f'<a class="{cls}" href="{href}">{label}</a>'
    return links


def socials_html(depth=0):
    up = "../" * depth
    out = ""
    for s in SITE["socials"]:
        href = s["url"]
        if href.startswith("/"):
            href = up + href.lstrip("/")
        out += f'<a href="{href}" rel="me noopener">{esc(s["label"])}</a>'
    return out


PAGE = """<!doctype html>
<html lang="en" data-theme="dark">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{title}}</title>
<meta name="description" content="{{desc}}">
<link rel="stylesheet" href="{{up}}assets/style.css">
<link rel="preconnect" href="https://cdnjs.cloudflare.com">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/base16/black-metal-bathory.min.css">
</head>
<body class="{{bodyclass}}">
<div class="scanlines" aria-hidden="true"></div>
<header class="site">
  <a class="brand" href="{{up}}index.html"><span class="brand__mark"></span>{{handle}}<span class="accent">.</span></a>
  <nav class="nav">{{nav}}</nav>
</header>
<main class="wrap">
{{body}}
</main>
<footer class="site-foot">
  <div class="foot__socials">{{socials}}</div>
  <div class="foot__meta">// built static, no trackers &middot; <span id="clock"></span></div>
</footer>
<script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/highlight.min.js"></script>
<script src="{{up}}assets/main.js"></script>
</body>
</html>"""


def page(title, desc, body, active, depth=0, bodyclass=""):
    return render(PAGE,
        title=esc(title), desc=esc(desc), up="../" * depth,
        nav=nav(active, depth), socials=socials_html(depth),
        handle=esc(SITE["handle"]), body=body, bodyclass=bodyclass)


def post_card(p, depth):
    up = "../" * depth
    tags = "".join(f'<span class="tag">{esc(t)}</span>' for t in p["tags"])
    return f"""<a class="card" href="{up}research/{p['slug']}.html">
  <div class="card__date">{esc(p['date'])} <span class="dot">&bull;</span> {p['read']} min</div>
  <h3 class="card__title">{esc(p['title'])}</h3>
  <p class="card__sum">{esc(p['summary'])}</p>
  <div class="card__tags">{tags}</div>
</a>"""


def cve_card(cve):
    record_url = f"https://www.cve.org/CVERecord?id={cve['id']}"
    return f"""<article class="card cve">
  <div class="card__date">{esc(cve['date'])}</div>
  <h3 class="card__title">{esc(cve['id'])}</h3>
  <p class="card__sum">{esc(cve['summary'])}</p>
  <a class="cve__link" href="{record_url}" rel="noopener" target="_blank">Show publication <span aria-hidden="true">&rarr;</span></a>
</article>"""


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------
def build_index(posts):
    links = ""
    for s in SITE["socials"]:
        href = s["url"] if not s["url"].startswith("/") else s["url"].lstrip("/")
        links += f'<a class="hero__link" href="{href}" rel="me noopener">{esc(s["label"])}</a>'

    # stats strip (all truthful / computed)
    latest_date = posts[0]["date"] if posts else "n/a"
    n_tags = len({t for p in posts for t in p["tags"]})
    stats = [
        (str(len(posts)), "writeup" if len(posts) == 1 else "writeups"),
        (str(n_tags), "topic" if n_tags == 1 else "topics"),
        (latest_date, "last updated"),
    ]
    stats_html = "".join(
        f'<div class="stat"><span class="stat__num">{esc(v)}</span><span class="stat__lbl">{esc(l)}</span></div>'
        for v, l in stats)

    # featured (latest) + the rest
    featured_html = featured_card(posts[0], 0) if posts else \
        '<p class="muted">No posts yet. Add one in ./posts and rebuild.</p>'
    rest = "".join(post_card(p, 0) for p in posts[1:4])
    rest_block = f'<div class="cards">{rest}</div>' if rest else ""
    cves_preview = "".join(cve_card(cve) for cve in CVES[:3])

    body = f"""
<section class="hero">
  <div class="hero__eyebrow">vulnerability research &amp; disclosure</div>
  <h1 class="hero__title">{esc(SITE['handle'])}<span class="accent">.</span></h1>
  <p class="hero__sub">{esc(SITE['tagline'])}</p>
  <p class="hero__who"><b>{esc(SITE['author'])}</b> &middot; {esc(SITE['role'])}</p>
  <div class="hero__actions">
    <a class="btn" href="research/index.html">Read the research &rarr;</a>
    <div class="hero__links">{links}</div>
  </div>
</section>
<div class="stats">{stats_html}</div>
<section class="section">
  <div class="section__head"><h2># latest writeup</h2><a class="more" href="research/index.html">all research &rarr;</a></div>
  {featured_html}
  {rest_block}
</section>
<section class="section">
  <div class="section__head"><h2># CVEs</h2><a class="more" href="cves.html">all CVEs &rarr;</a></div>
  <div class="cards">{cves_preview}</div>
</section>
"""
    write("index.html", page(SITE["title"], SITE["description"], body, "home", 0, "is-home"))


def featured_card(p, depth):
    up = "../" * depth
    tags = "".join(f'<span class="tag">{esc(t)}</span>' for t in p["tags"])
    return f"""<a class="featured" href="{up}research/{p['slug']}.html">
  <div class="featured__body">
    <div class="featured__meta"><span class="featured__badge">latest</span>{esc(p['date'])} <span class="dot">&bull;</span> {p['read']} min read</div>
    <h3 class="featured__title">{esc(p['title'])}</h3>
    <p class="featured__sum">{esc(p['summary'])}</p>
    <div class="featured__tags">{tags}</div>
    <span class="featured__cta">read the writeup &rarr;</span>
  </div>
</a>"""


def build_research(posts):
    all_tags = sorted({t for p in posts for t in p["tags"]})
    filters = '<button class="filter is-active" data-tag="*">all</button>' + \
              "".join(f'<button class="filter" data-tag="{esc(t)}">{esc(t)}</button>' for t in all_tags)
    cards = ""
    for p in posts:
        data = " ".join(p["tags"])
        card = post_card(p, 1).replace('<a class="card"', f'<a class="card" data-tags="{esc(data)}"', 1)
        cards += card
    body = f"""
<div class="page-head">
  <h1># research</h1>
  <p class="muted">{len(posts)} writeups &middot; vulnerability research, exploitation, and CTF.</p>
</div>
<div class="filters">{filters}</div>
<div class="cards cards--list">{cards or '<p class="muted">No posts yet.</p>'}</div>
"""
    write("research/index.html", page("research // " + SITE["handle"], "All research writeups.", body, "research", 1))

    for p in posts:
        build_post(p)


def build_cves():
    cards = "".join(cve_card(cve) for cve in CVES)
    body = f"""
<div class="page-head">
  <h1># CVEs</h1>
  <p class="muted">{len(CVES)} disclosed vulnerabilities and advisories.</p>
</div>
<div class="cards cards--list">{cards}</div>
"""
    write("cves.html", page("CVEs // " + SITE["handle"], "Disclosed CVEs and security advisories.", body, "cves"))


def build_post(p):
    tags = "".join(f'<span class="tag">{esc(t)}</span>' for t in p["tags"])
    body = f"""
<article class="post">
  <a class="back" href="index.html">&larr; ./research</a>
  <header class="post__head">
    <div class="post__meta">{esc(p['date'])} <span class="dot">&bull;</span> {p['read']} min read</div>
    <h1 class="post__title">{esc(p['title'])}</h1>
    <div class="post__tags">{tags}</div>
  </header>
  <div class="prose">
{p['html']}
  </div>
</article>
"""
    write(f"research/{p['slug']}.html",
          page(p["title"] + " // " + SITE["handle"], p["summary"] or SITE["description"],
               body, "research", 1))


# dot colors for the language indicator (GitHub-ish)
LANG_COLORS = {"Python": "#3572A5", "Java": "#b07219", "Go": "#00ADD8",
               "JavaScript": "#f1e05a", "TypeScript": "#3178c6", "C": "#555555",
               "Rust": "#dea584", "Ruby": "#701516", "Shell": "#89e051"}

def fetch_github_repos(user, limit=6):
    """Fetch public non-fork repos sorted by stars. Raises on any failure (no fallback)."""
    url = f"https://api.github.com/users/{user}/repos?per_page=100&sort=updated"
    req = urllib.request.Request(url, headers={
        "User-Agent": f"{user}-site-build",
        "Accept": "application/vnd.github+json",
    })
    try:
        with urllib.request.urlopen(req, timeout=12) as r:
            data = json.load(r)
    except Exception as e:
        raise SystemExit(f"[x] GitHub fetch failed for '{user}': {e}\n"
                         f"    (check your connection; projects are live, there is no snapshot.)")
    if not isinstance(data, list):
        msg = data.get("message") if isinstance(data, dict) else data
        raise SystemExit(f"[x] GitHub API error for '{user}': {msg}")
    repos = [x for x in data if not x.get("fork") and not x.get("archived")]
    repos.sort(key=lambda x: (x["stargazers_count"], x["forks_count"]), reverse=True)
    out = []
    for x in repos[:limit]:
        out.append({
            "name":  x["name"],
            "lang":  x.get("language") or "",
            "stars": x["stargazers_count"],
            "forks": x["forks_count"],
            "desc":  x.get("description") or "",
            "tags":  (x.get("topics") or [])[:3],
            "url":   x["html_url"],
        })
    return out


def build_projects():
    projects = fetch_github_repos(SITE.get("github_user", SITE["handle"]))
    print(f"[+] projects: {len(projects)} repos (live from github)")
    star = ('<svg viewBox="0 0 16 16" width="13" height="13" aria-hidden="true"><path fill="currentColor" '
            'd="M8 .25a.75.75 0 0 1 .673.418l1.882 3.815 4.21.612a.75.75 0 0 1 .416 1.279l-3.046 2.97.719 4.192a.75.75 0 0 1-1.088.791L8 12.347l-3.766 1.98a.75.75 0 0 1-1.088-.79l.72-4.194L.818 6.374a.75.75 0 0 1 .416-1.28l4.21-.611L7.327.668A.75.75 0 0 1 8 .25Z"/></svg>')
    fork = ('<svg viewBox="0 0 16 16" width="13" height="13" aria-hidden="true"><path fill="currentColor" '
            'd="M5 5.372v.878c0 .414.336.75.75.75h4.5a.75.75 0 0 0 .75-.75v-.878a2.25 2.25 0 1 1 1.5 0v.878a2.25 2.25 0 0 1-2.25 2.25h-1.5v2.128a2.251 2.251 0 1 1-1.5 0V8.5h-1.5A2.25 2.25 0 0 1 3.5 6.25v-.878a2.25 2.25 0 1 1 1.5 0ZM5 3.25a.75.75 0 1 0-1.5 0 .75.75 0 0 0 1.5 0Zm6.75.75a.75.75 0 1 0 0-1.5.75.75 0 0 0 0 1.5Zm-3 8.75a.75.75 0 1 0-1.5 0 .75.75 0 0 0 1.5 0Z"/></svg>')
    cards = ""
    for pr in projects:
        tags = "".join(f'<span class="tag">{esc(t)}</span>' for t in pr["tags"])
        color = LANG_COLORS.get(pr["lang"], "#8b98a5")
        lang = (f'<span class="project__lang"><span class="project__dot" style="background:{color}">'
                f'</span>{esc(pr["lang"])}</span>') if pr["lang"] else ""
        cards += f"""<a class="card project" href="{esc(pr['url'])}" rel="noopener" target="_blank" data-repo="{esc(pr['name'])}">
  <div class="project__top">
    <h3 class="card__title">{esc(pr['name'])}</h3>
    {lang}
  </div>
  <p class="card__sum">{esc(pr['desc'])}</p>
  <div class="card__tags">{tags}</div>
  <div class="project__stats">
    <span class="project__stat" data-stat="stars">{star} <span class="project__n">{pr['stars']}</span></span>
    <span class="project__stat" data-stat="forks">{fork} <span class="project__n">{pr['forks']}</span></span>
    <span class="project__view">view on github &rarr;</span>
  </div>
</a>"""
    body = f"""
<div class="page-head"><h1># projects</h1><p class="muted">Open-source security tooling &middot; live star &amp; fork counts from GitHub.</p></div>
<div class="cards" data-gh-user="{esc(SITE.get('github_user', SITE['handle']))}">{cards}</div>
"""
    write("projects.html", page("projects // " + SITE["handle"], "Open-source security tools and projects.", body, "projects"))


def build_about():
    body = f"""
<div class="page-head"><h1># about</h1></div>
<div class="prose about">
  <p>I'm <strong>{esc(SITE['author'])}</strong>, a security researcher and bug bounty
     hunter. I like taking apart the systems people rely on and finding the subtle
     bugs others miss. This site is where I publish my writeups and disclosed findings.</p>
  <h2>what I do</h2>
  <ul>
    <li>Vulnerability research &amp; discovery</li>
    <li>Exploitation &amp; proof-of-concept development</li>
    <li>Responsible disclosure &amp; bug bounty</li>
    <li>Reverse engineering</li>
  </ul>
  <h2>contact</h2>
  <p>Reach me at <a href="mailto:{esc(SITE['email'])}">{esc(SITE['email'])}</a>.</p>
</div>
"""
    write("about.html", page("about // " + SITE["handle"], "About " + SITE["author"], body, "about"))


def build_feed(posts):
    now = datetime.datetime.now(datetime.UTC).strftime("%a, %d %b %Y %H:%M:%S GMT")
    items = ""
    for p in posts[:20]:
        link = f"{SITE['url'].rstrip('/')}/research/{p['slug']}.html"
        items += f"""<item><title>{esc(p['title'])}</title><link>{link}</link>
<guid>{link}</guid><description>{esc(p['summary'])}</description></item>"""
    feed = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
<title>{esc(SITE['title'])}</title><link>{SITE['url']}</link>
<description>{esc(SITE['description'])}</description><lastBuildDate>{now}</lastBuildDate>
{items}
</channel></rss>"""
    write("feed.xml", feed)


# ---------------------------------------------------------------------------
def write(rel, content):
    path = os.path.join(OUT, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path, "w", encoding="utf-8").write(content)


def main():
    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    os.makedirs(OUT)
    shutil.copytree(ASSETS, os.path.join(OUT, "assets"))
    # .nojekyll so GitHub Pages serves files as-is
    open(os.path.join(OUT, ".nojekyll"), "w").close()

    posts = load_posts()
    build_index(posts)
    build_research(posts)
    build_cves()
    build_projects()
    build_about()
    build_feed(posts)
    print(f"[+] built {len(posts)} posts -> {OUT}")

    if "--serve" in sys.argv:
        os.chdir(OUT)
        port = 8000
        with http.server.HTTPServer(("", port), http.server.SimpleHTTPRequestHandler) as httpd:
            print(f"[+] serving http://localhost:{port}  (ctrl-c to stop)")
            httpd.serve_forever()


if __name__ == "__main__":
    main()
