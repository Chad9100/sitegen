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
