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

import calendar
import html
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "presskit.md"

# Each mode renders its own page, so a link sent to a booker is exactly the kit
# they should see - no JavaScript, and nothing of the other mode in the source.
MODES = ("techno", "reggaeton")
PAGES = {"techno": "presskit.html", "reggaeton": "presskit-reggaeton.html"}
LABELS = {"techno": "Techno", "reggaeton": "Reggaeton"}

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


def resolve(doc, title, mode):
    """A section's mode-specific version if it exists, else the shared one.

    Write a section once and it applies to both kits; add "## Title [mode]"
    only for the parts that genuinely differ.
    """
    return doc.get(f"{title} [{mode}]", doc.get(title, []))


def merged_kv(doc, title, mode):
    """Key/value sections merge rather than replace.

    A mode override that only sets `hook` must not silently drop the booking
    email and everything else defined in the shared block.
    """
    out = kv(doc.get(title, []))
    out.update(kv(doc.get(f"{title} [{mode}]", [])))
    return out


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


def music_rows(lines):
    """Parse: title | track id | label | player style | link... | link...

    Each trailing field is an optional "text > url" pair, so a release can
    carry as many links as it needs without changing the row format.
    """
    out = []
    for line in content_lines(lines):
        if "|" not in line:
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) < 4:
            continue
        links = []
        for extra in parts[4:]:
            if ">" in extra:
                text, url = extra.split(">", 1)
                links.append((text.strip(), url.strip()))
        out.append((parts[0], parts[1], parts[2], parts[3], links))
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


MONTHS = {m.lower(): i for i, m in enumerate(calendar.month_abbr) if m}


def parse_when(text):
    """Parse a show date to the last moment it still counts as upcoming.

    Returns a date, or None when the text is not a single parseable date
    (a range like "2022-23", say). None means past: only something clearly
    in the future should be allowed to claim it is upcoming.
    """
    s = text.strip()
    m = re.match(r"^(\d{1,2})\s+([A-Za-z]{3,})\.?\s+(\d{4})$", s)
    if m:
        mon = MONTHS.get(m.group(2)[:3].lower())
        if mon:
            try:
                return date(int(m.group(3)), mon, int(m.group(1)))
            except ValueError:
                return None
    m = re.match(r"^([A-Za-z]{3,})\.?\s+(\d{4})$", s)
    if m:
        mon = MONTHS.get(m.group(1)[:3].lower())
        if mon:
            # Month precision: still upcoming until the whole month has gone.
            y = int(m.group(2))
            return date(y, mon, calendar.monthrange(y, mon)[1])
    return None


def split_shows(entries, today):
    """Split rows into (upcoming, past), each sorted and tagged with an ISO date.

    Upcoming runs soonest-first, past runs most-recent-first. Rows with no
    parseable date sort to the bottom of the past list, keeping source order.
    """
    tagged = []
    for when, venue, city in entries:
        d = parse_when(when)
        tagged.append((when, venue, city, d.isoformat() if d else "", d))
    upcoming = [t for t in tagged if t[4] and t[4] >= today]
    past = [t for t in tagged if not (t[4] and t[4] >= today)]
    upcoming.sort(key=lambda t: t[4])
    past.sort(key=lambda t: t[4] or date.min, reverse=True)
    return ([t[:4] for t in upcoming], [t[:4] for t in past])


def shows_html(entries):
    """Render a date/venue/city list. Shared by Upcoming and Selected shows."""
    out = '      <ul class="pk-shows">\n'
    for when, venue, city, iso in entries:
        attr = f' data-date="{iso}"' if iso else ""
        out += (
            f"        <li{attr}>"
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


def render(doc, mode):
    meta = merged_kv(doc, "Meta", mode)
    socials = merged_kv(doc, "Socials", mode)
    music = music_rows(resolve(doc, "Music", mode))
    bio_short = paragraphs(resolve(doc, "Bio short", mode))
    bio_full = paragraphs(resolve(doc, "Bio full", mode))
    video = content_lines(resolve(doc, "Live video", mode))
    upcoming, shows = split_shows(rows(resolve(doc, "Shows", mode), 3), date.today())
    rider = subsections(resolve(doc, "Tech rider", mode))
    photos = rows(resolve(doc, "Press photos", mode), 2)

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

    other = "reggaeton" if mode == "techno" else "techno"

    fonts = "family=Space+Grotesk:wght@300..700&family=Space+Mono:wght@400;700"
    if mode == "reggaeton":
        # Loaded only where it is used, so the techno page pays nothing for it.
        fonts += "&family=Orbitron:wght@700;900"

    toggle = mode_toggle(mode, PAGES, 4)

    # -- head -------------------------------------------------------------
    out.append(f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{e(name)} | {e(LABELS[mode])} Press Kit</title>
  <meta name="description" content="{e(hook)}">
  <meta property="og:title" content="{e(name)} — {e(LABELS[mode])} Press Kit">
  <meta property="og:description" content="{e(hook)}">
  <meta property="og:type" content="profile">
  <meta property="og:image" content="assets/profile.jpeg">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?{fonts}&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="style.css">
</head>
<body class="presskit mode-{mode}">
  <div class="bg-overlay"></div>

  <div class="pk-bar">
    <a class="pk-bar-back" href="{HOME[mode]}">&#8592; Site</a>
    <a class="pk-bar-name" href="{HOME[mode]}">{e(name)}</a>
{toggle}
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
        for i, (title, tid, label, style, links) in enumerate(music):
            visual = "true" if style.lower() == "visual" else "false"
            height = 400 if visual == "true" else 166
            src = WIDGET.format(tid=e(tid), color=colors[i % len(colors)], visual=visual)
            cls = " pk-player--visual" if visual == "true" else ""
            # Also carries the URLs into print, where the embeds are dropped.
            credits = ""
            if links:
                joined = ' <span class="dot">&middot;</span> '.join(
                    f'<a href="{e(url)}" target="_blank" rel="noopener">{e(text)}</a>'
                    for text, url in links
                )
                credits = f'        <p class="pk-player-credit">{joined}</p>\n'
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
{credits}      </article>
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
    <p><a href="{HOME[mode]}">Back to site</a></p>
  </footer>
  <script src="shows.js" defer></script>
</body>
</html>
""")

    return "".join(out), rendered, skipped


SCRIPT = """/* Shows are split into upcoming and past at build time, which is correct on
   the day of the deploy. This re-checks in the browser so every page stays
   right on later visits without a rebuild. Progressive enhancement: with the
   script blocked, the build-time split still stands. */
(function () {
  var upSec = document.getElementById('upcoming');
  if (!upSec) return;
  var upList = upSec.querySelector('.pk-shows');
  if (!upList) return;
  var pastSec = document.getElementById('shows');
  var pastList = pastSec ? pastSec.querySelector('.pk-shows') : null;

  var today = new Date();
  today.setHours(0, 0, 0, 0);

  var stale = [];
  Array.prototype.forEach.call(upList.children, function (li) {
    var iso = li.getAttribute('data-date');
    if (!iso) return;
    var p = iso.split('-');
    if (new Date(+p[0], +p[1] - 1, +p[2]) < today) stale.push(li);
  });

  if (stale.length && pastList) {
    stale.forEach(function (li) { pastList.appendChild(li); });
    var items = Array.prototype.slice.call(pastList.children);
    items.sort(function (a, b) {
      var da = a.getAttribute('data-date'), db = b.getAttribute('data-date');
      if (!da && !db) return 0;
      if (!da) return 1;
      if (!db) return -1;
      return db.localeCompare(da);
    });
    items.forEach(function (li) { pastList.appendChild(li); });
  }

  if (!upList.children.length) upSec.hidden = true;

  /* Section numbers are baked in at build time, so renumber whatever is still
     visible rather than leaving a gap. Both page types are covered: the press
     kit uses .pk-section/.pk-num, the homepage .site-section/.section-num. */
  var n = 0;
  Array.prototype.forEach.call(
    document.querySelectorAll('.pk-section, .site-section'), function (sec) {
      if (sec.hidden) return;
      var num = sec.querySelector('.pk-num, .section-num');
      if (!num) return;
      n += 1;
      num.textContent = n < 10 ? '0' + n : String(n);
    });
})();
"""


SHOWS_JS = ROOT / "shows.js"

# The homepage exists in both modes too, so the choice follows the visitor
# across the whole site rather than living only inside the press kit.
HOME = {"techno": "index.html", "reggaeton": "index-reggaeton.html"}


def mode_toggle(mode, pages, indent):
    """The Techno / Reggaeton switch.

    `pages` decides which pair it moves between, so the homepage toggle stays
    on the homepage and the press kit toggle stays in the press kit.
    """
    other = "reggaeton" if mode == "techno" else "techno"
    pad = " " * indent
    return (
        f'{pad}<div class="pk-modes" role="group" aria-label="Version">\n'
        f'{pad}  <span class="pk-mode is-active" aria-current="true">{e(LABELS[mode])}</span>\n'
        f'{pad}  <a class="pk-mode" href="{pages[other]}">{e(LABELS[other])}</a>\n'
        f"{pad}</div>"
    )


def render_index(doc, mode):
    """The homepage, generated from the same source as the press kit."""
    meta = merged_kv(doc, "Meta", mode)
    socials = merged_kv(doc, "Socials", mode)
    music = music_rows(resolve(doc, "Music", mode))
    upcoming, past = split_shows(rows(resolve(doc, "Shows", mode), 3), date.today())

    name = meta.get("name", "Artist")
    genres = meta.get("genres", "")
    city = meta.get("city", "").split(",")[0].strip()
    subtitle = " &middot; ".join(x for x in (genres, city) if x)

    fonts = "family=Space+Grotesk:wght@300..700&family=Space+Mono:wght@400;700"
    if mode == "reggaeton":
        fonts += "&family=Orbitron:wght@700;900"

    toggle = mode_toggle(mode, HOME, 6)
    soundcloud = socials.get("SoundCloud", "https://soundcloud.com")

    out = [f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{e(name)} | {e(genres)}</title>
  <meta name="description" content="{e(meta.get('hook', ''))}">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?{fonts}&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="style.css">
</head>
<body class="mode-{mode}">
  <div class="bg-overlay"></div>

  <main id="app">
    <header class="hero">
      <div class="profile-container">
        <img src="assets/profile.jpeg" alt="{e(name)} portrait" class="profile-img">
      </div>
      <h1 class="title">{e(name)}</h1>
      <p class="subtitle">{subtitle}</p>
{toggle}
      <nav class="hero-nav">
        <a href="#music">Listen</a>
        <a href="#shows">Shows</a>
        <a href="{PAGES[mode]}">Press Kit</a>
        <a href="{e(soundcloud)}" target="_blank" rel="noopener">SoundCloud</a>
      </nav>
    </header>

"""]

    n = 1
    if music:
        body = ""
        for title, tid, label, style, links in music:
            visual = "true" if style.lower() == "visual" else "false"
            height = 400 if visual == "true" else 166
            src = WIDGET.format(tid=e(tid), color="ff3b00", visual=visual)
            cls = " player-frame--visual" if visual == "true" else ""
            credit = ""
            if links:
                joined = ' <span class="dot">&middot;</span> '.join(
                    f'<a href="{e(url)}" target="_blank" rel="noopener">{e(text)}</a>'
                    for text, url in links
                )
                credit = f'        <p class="player-credit">{joined}</p>\n'
            body += f"""      <article class="player-card">
        <div class="player-meta">
          <span class="player-tag">{e(label)}</span>
          <h3 class="player-title">{e(title)}</h3>
        </div>
        <div class="player-frame{cls}">
          <iframe title="{e(name)} — {e(title)} on SoundCloud" width="100%" height="{height}"
            scrolling="no" frameborder="no" loading="lazy" allow="autoplay; encrypted-media"
            src="{src}"></iframe>
        </div>
{credit}      </article>
"""
        out.append(f"""    <section class="music-section site-section" id="music">
      <h2 class="section-title"><span class="section-num">{n:02d}</span> Listen</h2>
{body}    </section>

""")
        n += 1

    for sid, heading, entries in (("upcoming", "Upcoming", upcoming),
                                  ("shows", "Shows", past)):
        if not entries:
            continue
        out.append(f"""    <section class="shows-section site-section" id="{sid}">
      <h2 class="section-title"><span class="section-num">{n:02d}</span> {heading}</h2>
{shows_html(entries)}    </section>

""")
        n += 1

    out.append(f"""  </main>

  <footer>
    <p>&copy; 2026 {e(name)}</p>
  </footer>

  <script src="shows.js" defer></script>
</body>
</html>
""")
    return "".join(out)


def main():
    if not SOURCE.exists():
        sys.exit(f"error: {SOURCE.name} not found")

    text = SOURCE.read_text(encoding="utf-8")
    doc = parse(text)

    for mode in MODES:
        page, rendered, skipped = render(doc, mode)
        target = ROOT / PAGES[mode]
        target.write_text(page, encoding="utf-8")
        print(f"built {target.name}  [{mode}]")
        print(f"  sections rendered : {', '.join(rendered)}")
        print(f"  sections skipped  : {', '.join(skipped) if skipped else 'none'}")

    for mode in MODES:
        home = ROOT / HOME[mode]
        home.write_text(render_index(doc, mode), encoding="utf-8")
        print(f"built {home.name}  [{mode} homepage]")

    SHOWS_JS.write_text(SCRIPT, encoding="utf-8")
    print(f"built {SHOWS_JS.name}  [shared by all pages]")

    overrides = sorted(k for k in doc if "[" in k)
    print(f"\nmode overrides: {', '.join(overrides) if overrides else 'none'}")

    todos = [l.strip() for l in text.splitlines() if is_todo(l)]
    print(f"TODOs remaining: {len(todos)}")
    for t in todos:
        print(f"  - {t}")


if __name__ == "__main__":
    main()
