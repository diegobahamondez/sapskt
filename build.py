#!/usr/bin/env python3
"""Generate presskit.html from presskit.md.

Single source of truth is presskit.md. Run this after editing it:

    python3 build.py

Standard library only, so it runs anywhere python3 does.

Parsing rules (a deliberately small subset of Markdown):
  ## Title      starts a section
  ### Title     starts a subsection
  - item        bullet
  key: value    key/value pair (split on the first colon only)
  a | b | c     pipe-delimited row
  <!-- ... -->  ignored
  TODO...       author reminder: always stripped from the output

A section left with no real content after stripping TODOs is omitted from the
page entirely, and reappears on its own once real content is added.
"""

import html
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "presskit.md"
OUTPUT = ROOT / "presskit.html"

# Instagram glyph, inlined so it needs no network request and inherits the
# surrounding text colour via currentColor.
IG_ICON = (
    '<svg class="ig-icon" viewBox="0 0 24 24" width="1em" height="1em" fill="none" '
    'stroke="currentColor" stroke-width="2" stroke-linecap="round" '
    'stroke-linejoin="round" aria-hidden="true" focusable="false">'
    '<rect x="2" y="2" width="20" height="20" rx="5.5"/>'
    '<circle cx="12" cy="12" r="4.4"/>'
    '<circle cx="17.6" cy="6.4" r="1.1" fill="currentColor" stroke="none"/>'
    "</svg>"
)


WIDGET = (
    "https://w.soundcloud.com/player/?url=https%3A%2F%2Fapi.soundcloud.com"
    "%2Ftracks%2F{tid}&color=%23{color}&visual={visual}&show_artwork=true"
    "&hide_related=true&show_comments=false&show_user=true"
    "&show_reposts=false&show_teaser=false"
)


# --------------------------------------------------------------------------
# parsing
# --------------------------------------------------------------------------

def is_todo(line):
    """True for author reminders, with or without a bullet marker.

    Must strip the leading "- " first: otherwise "- TODO: confirm decks"
    reads as real rider content and ships to promoters.
    """
    s = line.strip()
    if s.startswith("- "):
        s = s[2:].strip()
    return s.upper().startswith("TODO")


def strip_comments(text):
    return re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)


def parse(text):
    """Split the document into {section title: [lines]}, preserving order."""
    sections, title, buf = {}, None, []
    for raw in strip_comments(text).splitlines():
        line = raw.rstrip()
        if line.startswith("## "):
            if title is not None:
                sections[title] = buf
            title, buf = line[3:].strip(), []
        elif title is not None:
            buf.append(line)
    if title is not None:
        sections[title] = buf
    return sections


def content_lines(lines):
    """Real content only: no blanks, no TODO reminders."""
    return [l for l in lines if l.strip() and not is_todo(l)]


def kv(lines):
    out = {}
    for line in content_lines(lines):
        if ":" in line:
            k, v = line.split(":", 1)
            out[k.strip()] = v.strip()
    return out


def bullets(lines):
    return [l.strip()[2:].strip() for l in content_lines(lines) if l.strip().startswith("- ")]


def rows(lines, width):
    out = []
    for line in content_lines(lines):
        if "|" not in line:
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) >= width:
            out.append(parts[:width])
    return out


def paragraphs(lines):
    """Blank-line separated prose. TODO lines are dropped, blanks preserved."""
    kept = [l for l in lines if not is_todo(l)]
    out, buf = [], []
    for line in kept:
        if line.strip():
            buf.append(line.strip())
        elif buf:
            out.append(" ".join(buf))
            buf = []
    if buf:
        out.append(" ".join(buf))
    return out


def subsections(lines):
    """Split a section on '### ' headings."""
    out, title, buf = {}, None, []
    for line in lines:
        if line.startswith("### "):
            if title is not None:
                out[title] = buf
            title, buf = line[4:].strip(), []
        elif title is not None:
            buf.append(line)
    if title is not None:
        out[title] = buf
    return {k: v for k, v in out.items() if bullets(v)}


def embed_url(url):
    """Normalise a YouTube/Vimeo link to its embeddable form.

    Lets the source file hold the URL as copied from the address bar.
    Anything unrecognised is passed through untouched.
    """
    url = url.strip()
    m = re.search(r"(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/)([\w-]{11})", url)
    if m:
        return f"https://www.youtube.com/embed/{m.group(1)}"
    m = re.search(r"vimeo\.com/(?:video/)?(\d+)", url)
    if m:
        return f"https://player.vimeo.com/video/{m.group(1)}"
    return url


# --------------------------------------------------------------------------
# rendering
# --------------------------------------------------------------------------

def e(s):
    return html.escape(str(s), quote=True)


def shows_html(entries):
    """Render a date/venue/city list. Shared by Upcoming and Selected shows."""
    out = '      <ul class="pk-shows">\n'
    for when, venue, city in entries:
        out += (
            "        <li>"
            f'<span class="pk-show-year">{e(when)}</span>'
            f'<span class="pk-show-venue">{e(venue)}</span>'
            f'<span class="pk-show-city">{e(city)}</span></li>\n'
        )
    return out + "      </ul>\n"


def section(sid, heading, body, num):
    """Render one section. `num` is its position among the sections that were
    actually rendered, so hiding an empty section does not leave a gap in the
    numbering."""
    return (
        f'    <section class="pk-section" id="{sid}">\n'
        f'      <h2 class="pk-heading"><span class="pk-num">{num:02d}</span> {e(heading)}</h2>\n'
        f"{body}"
        f"    </section>\n"
    )


def render(doc):
    meta = kv(doc.get("Meta", []))
    socials = kv(doc.get("Socials", []))
    music = rows(doc.get("Music", []), 4)
    bio_short = paragraphs(doc.get("Bio short", []))
    bio_full = paragraphs(doc.get("Bio full", []))
    video = content_lines(doc.get("Live video", []))
    upcoming = rows(doc.get("Upcoming", []), 3)
    shows = rows(doc.get("Selected shows", []), 3)
    rider = subsections(doc.get("Tech rider", []))
    photos = rows(doc.get("Press photos", []), 2)

    name = meta.get("name", "Artist")
    hook = meta.get("hook", "")
    email = meta.get("booking_email", "")
    facts = [meta.get(k, "") for k in ("genres", "city")]
    facts = [f for f in facts if f]
    barmeta = " · ".join(facts)

    rendered, skipped = [], []
    out = []

    counter = {"n": 0}

    def emit(sid, heading, body):
        counter["n"] += 1
        return section(sid, heading, body, counter["n"])

    # -- head -------------------------------------------------------------
    out.append(f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{e(name)} | Press Kit</title>
  <meta name="description" content="{e(hook)}">
  <meta property="og:title" content="{e(name)} — Press Kit">
  <meta property="og:description" content="{e(hook)}">
  <meta property="og:type" content="profile">
  <meta property="og:image" content="assets/profile.jpeg">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@300..700&family=Space+Mono:wght@400;700&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="style.css">
</head>
<body class="presskit">
  <div class="bg-overlay"></div>

  <div class="pk-bar">
    <a class="pk-bar-back" href="index.html">&#8592; Site</a>
    <a class="pk-bar-name" href="index.html">{e(name)}</a>
    <span class="pk-bar-meta">{e(barmeta)}</span>
    <a class="pk-bar-cta" href="mailto:{e(email)}">Book</a>
  </div>

  <main class="pk">
""")

    # -- hero -------------------------------------------------------------
    origin = meta.get("origin", "")
    chips = "".join(
        f'          <li>{e(f)}</li>\n'
        for f in (meta.get("genres", ""), meta.get("city", ""),
                  f"from {origin}" if origin else "")
        if f
    )
    out.append(f"""    <header class="pk-hero">
      <div class="pk-hero-photo">
        <img src="assets/profile.jpeg" alt="{e(name)} portrait" width="320" height="320">
      </div>
      <div class="pk-hero-text">
        <p class="pk-eyebrow">Press Kit</p>
        <h1 class="pk-name">{e(name)}</h1>
        <p class="pk-hook">{e(hook)}</p>
        <ul class="pk-chips">
{chips}        </ul>
        <div class="pk-cta">
          <a class="pk-btn pk-btn--primary" href="mailto:{e(email)}">Booking enquiry</a>
          <a class="pk-btn" href="#listen">Listen</a>
        </div>
      </div>
    </header>

""")
    rendered.append("hero")

    # -- listen -----------------------------------------------------------
    if music:
        colors = ["ff3b00"]
        body = ""
        for i, (title, tid, label, style) in enumerate(music):
            visual = "true" if style.lower() == "visual" else "false"
            height = 400 if visual == "true" else 166
            src = WIDGET.format(tid=e(tid), color=colors[i % len(colors)], visual=visual)
            cls = " pk-player--visual" if visual == "true" else ""
            body += f"""      <article class="pk-player{cls}">
        <div class="pk-player-meta">
          <span class="pk-tag">{e(label)}</span>
          <h3 class="pk-player-title">{e(title)}</h3>
        </div>
        <div class="pk-frame">
          <iframe title="{e(name)} — {e(title)} on SoundCloud" width="100%" height="{height}"
            scrolling="no" frameborder="no" loading="lazy" allow="autoplay; encrypted-media"
            src="{src}"></iframe>
        </div>
      </article>
"""
        out.append(emit("listen", "Listen", body))
        rendered.append("listen")
    else:
        skipped.append("listen")

    # -- bio --------------------------------------------------------------
    if bio_short:
        body = "".join(f'      <p class="pk-lead">{e(p)}</p>\n' for p in bio_short)
        if bio_full:
            inner = "".join(f"          <p>{e(p)}</p>\n" for p in bio_full)
            body += (
                '      <details class="pk-details">\n'
                "        <summary>Read the full biography</summary>\n"
                '        <div class="pk-details-body">\n'
                f"{inner}"
                "        </div>\n"
                "      </details>\n"
            )
        out.append(emit("bio", "Biography", body))
        rendered.append("bio")
    else:
        skipped.append("bio")

    # -- live video -------------------------------------------------------
    if video:
        url = embed_url(video[0])
        body = f"""      <div class="pk-frame pk-frame--video">
        <iframe title="{e(name)} live" src="{e(url)}" loading="lazy"
          allow="accelerometer; clipboard-write; encrypted-media; picture-in-picture"
          allowfullscreen frameborder="no"></iframe>
      </div>
"""
        out.append(emit("live", "Live", body))
        rendered.append("live")
    else:
        skipped.append("live")

    # -- upcoming ---------------------------------------------------------
    if upcoming:
        out.append(emit("upcoming", "Upcoming", shows_html(upcoming)))
        rendered.append("upcoming")
    else:
        skipped.append("upcoming")

    # -- shows ------------------------------------------------------------
    if shows:
        out.append(emit("shows", "Selected shows", shows_html(shows)))
        rendered.append("shows")
    else:
        skipped.append("shows")

    # -- press photos -----------------------------------------------------
    if photos:
        body = '      <div class="pk-photos">\n'
        for src, caption in photos:
            body += f"""        <figure class="pk-photo">
          <a href="{e(src)}" download><img src="{e(src)}" alt="{e(caption)}" loading="lazy"></a>
          <figcaption>{e(caption)}</figcaption>
        </figure>
"""
        body += "      </div>\n"
        credit = meta.get("photo_credit", "")
        handle = meta.get("photo_credit_instagram", "").lstrip("@")
        if credit:
            if handle:
                who = (
                    f"{e(credit)} "
                    f'(<a class="pk-credit" href="https://instagram.com/{e(handle)}" '
                    f'target="_blank" rel="noopener">{IG_ICON}@{e(handle)}</a>)'
                )
            else:
                who = e(credit)
            body += (
                f'      <p class="pk-note">Photos by {who}. '
                "Please credit on all published material. Click any image to download.</p>\n"
            )
        out.append(emit("photos", "Press photos", body))
        rendered.append("photos")
    else:
        skipped.append("photos")

    # -- tech rider -------------------------------------------------------
    if rider:
        body = '      <div class="pk-rider">\n'
        for sub, lines in rider.items():
            items = "".join(f"            <li>{e(b)}</li>\n" for b in bullets(lines))
            body += f"""        <div class="pk-rider-block">
          <h3>{e(sub)}</h3>
          <ul>
{items}          </ul>
        </div>
"""
        body += "      </div>\n"
        out.append(emit("rider", "Tech rider", body))
        rendered.append("rider")
    else:
        skipped.append("rider")

    # -- booking ----------------------------------------------------------
    links = "".join(
        f'          <li><a href="{e(url)}" target="_blank" rel="noopener">{e(label)}</a></li>\n'
        for label, url in socials.items()
    )
    body = f"""      <div class="pk-booking">
        <div class="pk-booking-primary">
          <p class="pk-note">Booking &amp; enquiries</p>
          <a class="pk-email" href="mailto:{e(email)}">{e(email)}</a>
        </div>
        <ul class="pk-links">
{links}        </ul>
      </div>
"""
    out.append(emit("booking", "Booking", body))
    rendered.append("booking")

    out.append(f"""  </main>

  <footer class="pk-footer">
    <p>&copy; 2026 {e(name)}. All rights reserved.</p>
    <p><a href="index.html">Back to site</a></p>
  </footer>
</body>
</html>
""")

    return "".join(out), rendered, skipped


def main():
    if not SOURCE.exists():
        sys.exit(f"error: {SOURCE.name} not found")

    text = SOURCE.read_text(encoding="utf-8")
    doc = parse(text)
    page, rendered, skipped = render(doc)
    OUTPUT.write_text(page, encoding="utf-8")

    todos = [l.strip() for l in text.splitlines() if is_todo(l)]
    print(f"built {OUTPUT.name} from {SOURCE.name}")
    print(f"  sections rendered : {', '.join(rendered)}")
    print(f"  sections skipped  : {', '.join(skipped) if skipped else 'none'}")
    print(f"  TODOs remaining   : {len(todos)}")
    for t in todos:
        print(f"    - {t}")


if __name__ == "__main__":
    main()
