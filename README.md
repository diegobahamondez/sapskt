# SAPSKT - DJ Webpage

Repository for the official page of **SAPSKT** (DJ & Music Producer).

## Folder structure
- `/assets`: Images, photos and other media resources.
- `index.html`: Main page.
- `style.css`: Visual styles for the page.

## Sections
- **Hero**: profile photo, name and in-page navigation.
- **Music**: embedded SoundCloud players.
  - Mixset: [smile when you dance](https://soundcloud.com/sapskt/smile-when-you-dance)
  - Track: [Fake Dichotomy](https://soundcloud.com/sapskt/fake-dichotomy)
- **Gallery**: photos of live sessions, visuals and vinyl.

### Adding a new track
The players use the official SoundCloud widget pointing at the track's numeric
ID, not at the permalink. To get the ID for a new track:

```bash
curl -s "https://soundcloud.com/oembed?format=json&url=<TRACK_URL>"
```

The `html` field in the response contains the `src` with the ID
(`api.soundcloud.com/tracks/<ID>`). Copy an existing
`<article class="player-card">` block in `index.html` and swap in that ID.

## Deploying to GitHub Pages
This site is ready to be hosted on GitHub Pages.

To preview it locally:

```bash
python3 -m http.server 8000
# open http://localhost:8000
```

## Press kit

`presskit.html` is the promoter-facing page — the link to send to bookers. It is
**generated**, not hand-written.

All of its copy lives in [`presskit.md`](presskit.md), which is the single source
of truth. To change the press kit:

```bash
# 1. edit the text
$EDITOR presskit.md

# 2. regenerate the page
python3 build.py
```

`build.py` uses only the Python standard library, so there is nothing to install.

Two conventions worth knowing:

- A section whose only content is `TODO` is **omitted** from the built page, and
  reappears by itself once you add real content. This is how the "Selected shows"
  section stays hidden until there are shows to list.
- Lines starting with `TODO` are **always stripped** from the output, including
  bullets inside the tech rider. They are reminders for you, never shown to
  promoters. `build.py` prints the outstanding ones after each build.

Do not edit `presskit.html` by hand; the next build overwrites it. The generated
file is committed so GitHub Pages can serve it with no build step of its own.
