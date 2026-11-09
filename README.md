# sitegen

sitegen turns a folder of Markdown files with simple front matter into a static blog. It writes a `public/` folder with an index (newest first, paginated), one page per post, per-tag pages, an Atom feed, a sitemap and your static assets.

## Who it is for

People who want a small, readable blog generator with one runtime dependency and no templating language to learn.

## Built with

Python 3.11+, the [`markdown`](https://pypi.org/project/Markdown/) package (fenced code and tables extensions), and the standard library (`tomllib`, `http.server`, `xml.etree`). Front matter is parsed by hand; there is no PyYAML or Jinja.

## Install

```
pip install git+https://github.com/Chad9100/sitegen.git
```

## Quick start

```
sitegen init myblog
sitegen new "Notes on sourdough" -C myblog --tags food,notes
sitegen serve myblog --drafts   # http://localhost:8000/
sitegen build myblog
```

`init` creates `sitegen.toml` and two example posts. Add `--drafts` to `build` or `serve` to include drafts.

### Writing a new post

`sitegen new "Title"` creates `posts/YYYY-MM-DD-title.md` with the front matter filled
in. It's a draft by default, so a half-written post never gets published by accident:
preview it with `serve --drafts`, then delete the `draft: true` line when it's ready.
Options: `-C FOLDER` (site folder, default current), `--tags a,b`, `--date YYYY-MM-DD`
(default today) and `--no-draft`. It never overwrites an existing file.

### Live rebuilds while you write

`sitegen serve` rebuilds the site whenever a post, `sitegen.toml`, a template or a
file in `static/` is added, changed or deleted (it checks every 0.5s; change that with
`--interval SECONDS`, or turn it off with `--no-watch`). Reload the browser to see the
result. If a change breaks the build, the error is printed and the last good build
keeps being served until you fix it. A real session (adding a post with `sitegen new`,
then breaking and fixing its `date:` line):

```
$ sitegen serve myblog --port 8765
Serving myblog\public at http://localhost:8765/ (Ctrl+C to stop)
Watching myblog for changes (--no-watch to turn off)
Rebuilt in 0.02s (1 changed: posts/2026-11-09-notes-on-sourdough.md)
127.0.0.1 - - [09/Nov/2026 16:22:53] "GET / HTTP/1.1" 200 -
Build failed after change to posts/2026-11-09-notes-on-sourdough.md: 2026-11-09-notes-on-sourdough.md: missing 'date' in front matter
  (still serving the last good build)
127.0.0.1 - - [09/Nov/2026 16:22:54] "GET / HTTP/1.1" 200 -
Rebuilt in 0.02s (1 changed: posts/2026-11-09-notes-on-sourdough.md)
```

## Config reference (`sitegen.toml`)

| Key | Default | Meaning |
|---|---|---|
| `title` | `My Site` | Site title (HTML-escaped) |
| `base_url` | `http://localhost:8000` | Absolute URL used in the feed and sitemap |
| `theme` | `light` | `light` or `dark` |
| `posts_per_page` | `5` | Posts per index/tag page (positive integer) |

## Front matter reference

```
---
title: My post
date: 2026-03-04
tags: [python, notes]
draft: false
slug: my-post
summary: A one-line teaser for lists and the feed
---
```

- `title`: defaults to the file name.
- `date`: required, `YYYY-MM-DD` (or ISO date-time).
- `tags`: `[a, b]` or `a, b`.
- `draft`: `true`/`false`; drafts are skipped unless `--drafts`.
- `slug`: optional; always sanitized to `[a-z0-9-]`, so output cannot leave `public/`.
- `summary`: optional; the teaser shown under the post's title in lists and used in
  the Atom feed. Without it, everything above a `<!--more-->` line in the post is used
  as the summary. Without that either, the first paragraph is used, cut at a word
  boundary after about 200 characters.

Lists and post pages also show an estimated reading time ("3 min read", at about 200
words per minute, never less than 1).

Layout: Markdown anywhere in the site folder (except `public/`, `templates/`, `static/`, hidden folders). Files in `static/` are copied to `public/static/`.

Custom templates: put `base.html`, `list.html` and/or `post.html` in a local `templates/` folder. They use `{{ var }}` substitution (`title`, `site_title`, `root`, `feed_url`, `css`, `content` in base; `heading`, `items`, `pager` in list; `title`, `date`, `reading_time`, `summary`, `tags`, `body` in post). Unknown variables render empty.

## Development

```
python -m venv .venv
.venv/Scripts/activate        # or: source .venv/bin/activate
pip install -e ".[dev]"
pytest -q
```

MIT licensed. See [ROADMAP.md](ROADMAP.md).
