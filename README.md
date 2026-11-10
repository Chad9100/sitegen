# sitegen

sitegen turns a folder of Markdown files with simple front matter into a static blog. It writes a `public/` folder with an index (newest first, paginated), one page per post, per-tag pages, standalone pages such as About and Contact, an Atom feed, a sitemap and your static assets.

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

`init` creates `sitegen.toml`, two example posts and an About page. Add `--drafts` to `build` or `serve` to include drafts.

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
then typing an impossible date and fixing it):

```
$ sitegen serve myblog --port 8765
Serving myblog\public at http://localhost:8765/ (Ctrl+C to stop)
Watching myblog for changes (--no-watch to turn off)
Rebuilt in 0.06s (1 changed: posts/2026-11-09-notes-on-sourdough.md)
Build failed after change to posts/2026-11-09-notes-on-sourdough.md:
posts/2026-11-09-notes-on-sourdough.md:3: invalid date: '2026-11-31' (day is out of range for month)
     3 | date: 2026-11-31
  (still serving the last good build)
Rebuilt in 0.02s (1 changed: posts/2026-11-09-notes-on-sourdough.md)
```

### Standalone pages (About, Contact)

Every `.md` file directly inside a top-level `pages/` folder becomes a page at
`/<file-name>/` (so `pages/about.md` is `/about/`). Pages need no `date`, never appear
in the post list, tag pages or the Atom feed, but are in the sitemap and linked from
the header of every page (the current one marked `aria-current="page"`). Front matter:

- `title`: the page heading and nav label (defaults to the file name).
- `slug`: optional URL override, sanitized like post slugs.
- `order`: whole number; nav links sort by `order` (default 0), then title.
- `nav: false`: build the page but leave it out of the header (e.g. an imprint).
- `draft: true`: skipped unless `--drafts`.

Real output, after adding `pages/contact.md` (`order: 1`) and `pages/imprint.md`
(`nav: false`) to a site made with `sitegen init pagesdemo`:

```
$ sitegen build pagesdemo
Built site into pagesdemo\public
$ ls pagesdemo/public
about
atom.xml
contact
imprint
index.html
posts
sitemap.xml
tags
$ grep '<nav' pagesdemo/public/index.html pagesdemo/public/contact/index.html
pagesdemo/public/index.html:<nav class="pages"><a href="./about/">About</a> <a href="./contact/">Contact</a></nav></header>
pagesdemo/public/contact/index.html:<nav class="pages"><a href="../about/">About</a> <a href="../contact/" aria-current="page">Contact</a></nav></header>
```

A page may not take over sitegen's own folders (`posts`, `tags`, `page`, `static`),
and two pages may not share a slug:

```
$ sitegen build pagesdemo       # with slug: tags in pages/tag-list.md
error: pages/tag-list.md:3: page slug 'tags' would replace sitegen's own /tags/ folder; rename the file or set another 'slug:'
```

### Tag index

Every build with at least one tag also writes `public/tags/index.html`: all tags with
their post counts, most used first (ties in alphabetical order). Each tag page links
back to it with an "All tags" link, and it is listed in `sitemap.xml`. Drafts are not
counted unless you build with `--drafts`. Real output from a demo site (`sitegen init`
plus four `sitegen new` posts, built with `--drafts`):

```
$ sitegen build . --drafts
Built site into public
$ grep -A8 '<ul class="posts">' public/tags/index.html
<ul class="posts">
<li><a class="tag" href="../tags/food/">#food</a> <span class="meta">3 posts</span></li>
<li><a class="tag" href="../tags/baking/">#baking</a> <span class="meta">2 posts</span></li>
<li><a class="tag" href="../tags/notes/">#notes</a> <span class="meta">2 posts</span></li>
<li><a class="tag" href="../tags/garden/">#garden</a> <span class="meta">1 post</span></li>
<li><a class="tag" href="../tags/intro/">#intro</a> <span class="meta">1 post</span></li>
<li><a class="tag" href="../tags/python/">#python</a> <span class="meta">1 post</span></li>
</ul>
$ grep pager public/tags/food/index.html
<nav class="pager"><a href="../../tags/">All tags</a></nav>
```

It uses the `list.html` template (`heading` is "Tags", `pager` is empty).

### When something is wrong

Errors name the file (relative to the site folder) and line as `file:line:`, the
form most editors and terminals can jump to, and quote the offending line. That
covers front matter (bad dates, `draft` values, unbalanced tag brackets, a line
without `key: value`, front matter that is never closed), files that are not UTF-8
(with the column of the bad byte), and `sitegen.toml` (TOML syntax errors, an unknown
theme, a bad `posts_per_page`). A missing `date` suggests the likely typo. Real output:

```
$ sitegen build myblog
error: posts/sourdough.md:3: invalid date: '2026-11-31' (day is out of range for month)
     3 | date: 2026-11-31

$ sitegen build myblog          # after mistyping the key as `dat:`
error: posts/sourdough.md:3: missing 'date' in front matter; did you mean 'date' instead of 'dat'?

$ sitegen build myblog          # with theme = "solarized" in sitegen.toml
error: sitegen.toml:3: unknown theme 'solarized'; choose one of: light, dark
     3 | theme = "solarized"
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

Layout: posts are Markdown anywhere in the site folder (except `public/`, `templates/`, `static/`, `pages/`, hidden folders); pages are `pages/*.md`. Files in `static/` are copied to `public/static/`.

Custom templates: put `base.html`, `list.html`, `post.html` and/or `page.html` in a local `templates/` folder. They use `{{ var }}` substitution (`title`, `site_title`, `root`, `feed_url`, `css`, `content`, `nav` in base; `heading`, `items`, `pager` in list; `title`, `date`, `reading_time`, `summary`, `tags`, `body` in post; `title`, `body` in page). Unknown variables render empty.

## Development

```
python -m venv .venv
.venv/Scripts/activate        # or: source .venv/bin/activate
pip install -e ".[dev]"
pytest -q
```

MIT licensed. See [ROADMAP.md](ROADMAP.md).
