# Site configuration. Edit these values, then run:  python3 build.py
SITE = {
    "handle":      "weirdmachine64",        # your alias / wordmark
    "github_user": "weirdmachine64",        # used to fetch live project stats
    "title":       "weirdmachine64 // security research",
    "tagline":     "Security research, tooling, and writeups.",
    "description": "Security research, vulnerability writeups, and responsible disclosure by Mohamed Benchikh.",
    "role":        "Security researcher & bug bounty hunter",
    "url":         "https://weirdmachine64.github.io",   # change to your Pages URL / custom domain
    "author":      "Mohamed Benchikh",
    "email":       "mohamed.benchikh@proton.me",
    "accent":      "#00ff9c",               # neon accent color
    "google_site_verification": "Uhe-cpELHH2BKTaGaA9xyeLpRJhJESF9YD346fsV_uw",  # Search Console (URL prefix property)
    "socials": [
        {"label": "github",   "url": "https://github.com/weirdmachine64"},
        {"label": "linkedin", "url": "https://www.linkedin.com/in/mohamedbenchikh/"},
        {"label": "rss",      "url": "/feed.xml"},
    ],
}

# Disclosed CVEs shown on the dedicated CVEs page and homepage preview.
CVES = [
    {
        "id": "CVE-2025-66413",
        "date": "Mar 11, 2026",
        "summary": "Git for Windows is the Windows port of Git. Prior to 2.53.0(2), it is possible to obtain a user's NTLM hash by tricking them into cloning from a malicious server.",
    },
    {
        "id": "CVE-2023-39137",
        "date": "Aug 30, 2023",
        "summary": "An issue in Archive v3.3.7 allows attackers to spoof zip filenames which can lead to inconsistent filename parsing.",
    },
    {
        "id": "CVE-2023-39135",
        "date": "Aug 30, 2023",
        "summary": "An issue in Zip Swift v2.1.2 allows attackers to execute a path traversal attack via a crafted zip entry.",
    },
    {
        "id": "CVE-2023-39138",
        "date": "Aug 30, 2023",
        "summary": "An issue in ZIPFoundation v0.9.16 allows attackers to execute a path traversal via extracting a crafted zip file.",
    },
    {
        "id": "CVE-2023-39136",
        "date": "Aug 30, 2023",
        "summary": "An unhandled edge case in the component _sanitizedPath of ZipArchive v2.5.4 allows attackers to cause a Denial of Service (DoS) via a crafted zip file.",
    },
    {
        "id": "CVE-2023-39139",
        "date": "Aug 30, 2023",
        "summary": "An issue in Archive v3.3.7 allows attackers to execute a path traversal via extracting a crafted zip file.",
    },
]
