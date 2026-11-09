"""Command line interface."""
from __future__ import annotations

import argparse
import functools
import http.server
import sys
from datetime import date
from pathlib import Path

from . import __version__, frontmatter
from .builder import BuildError, build
from .frontmatter import FrontMatterError, slugify
from .watch import Watcher

CONFIG = """title = "My Sitegen Blog"
base_url = "http://localhost:8000"
theme = "light"          # "light" or "dark"
posts_per_page = 5
"""

POSTS = {
    "posts/hello-world.md": """---
title: Hello, world
date: 2026-01-10
tags: [intro, notes]
---
Welcome to my new blog, built with **sitegen**.

## What to expect

- Short notes
- Small experiments

```python
print("hello")
```
""",
    "posts/garden-notes.md": """---
title: "Notes from the herb garden"
date: 2026-02-03
tags: [garden, notes]
slug: herb-garden
---
The basil is doing well; the mint is taking over.

| Herb  | Status   |
|-------|----------|
| Basil | thriving |
| Mint  | wild     |
""",
    "pages/about.md": """---
title: About
---
This blog is built with **sitegen**. Pages in `pages/` (like this one) get their
own URL and a link in the header, but never appear in the post list or the feed.
""",
}


def cmd_init(args) -> int:
    folder = Path(args.folder)
    folder.mkdir(parents=True, exist_ok=True)
    files = {"sitegen.toml": CONFIG, **POSTS}
    for rel, text in files.items():
        f = folder / rel
        if f.exists():
            print(f"skip (exists): {f}")
            continue
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding="utf-8", newline="\n")
        print(f"created {f}")
    (folder / "static").mkdir(exist_ok=True)
    print(f"Done. Next: sitegen build {folder}")
    return 0


def post_stub(title: str, day: date, tags: list[str], draft: bool) -> str:
    """Front matter plus a placeholder body for a new post."""
    lines = [
        "---",
        # Always quoted, so titles containing ':' or '#' survive the parser.
        f'title: "{title}"',
        f"date: {day.isoformat()}",
    ]
    if tags:
        lines.append(f"tags: [{', '.join(tags)}]")
    if draft:
        lines.append("draft: true")
    lines += ["---", "", "Write your post here.", ""]
    return "\n".join(lines)


def cmd_new(args) -> int:
    title = " ".join(args.title.split())  # no newlines or runs of spaces
    if not title:
        print("error: the title can't be empty", file=sys.stderr)
        return 1
    try:
        day = date.fromisoformat(args.date) if args.date else date.today()
        tags = frontmatter.parse_tags(args.tags) if args.tags else []
    except (ValueError, FrontMatterError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    folder = Path(args.folder)
    if not folder.is_dir():
        print(f"error: no such folder: {folder}", file=sys.stderr)
        return 1

    text = post_stub(title, day, tags, args.draft)
    meta, _ = frontmatter.parse(text)  # never write a stub sitegen can't read back
    if meta.title != title or meta.tags != tags:
        print(f"error: can't write front matter for title {title!r}", file=sys.stderr)
        return 1

    target = folder / "posts" / f"{day.isoformat()}-{slugify(title)}.md"
    if target.exists():
        print(f"error: {target} already exists; not overwriting it", file=sys.stderr)
        return 1
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8", newline="\n")
    print(f"created {target}")
    if args.draft:
        print("It's a draft: preview it with `sitegen serve --drafts`, then "
              "remove the `draft: true` line to publish it.")
    return 0


def cmd_build(args) -> int:
    out = build(Path(args.folder), drafts=args.drafts)
    print(f"Built site into {out}")
    return 0


def cmd_serve(args) -> int:
    folder = Path(args.folder)
    out = build(folder, drafts=args.drafts)
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(out))
    watcher = None
    if args.watch:
        watcher = Watcher(folder, lambda: build(folder, drafts=args.drafts),
                          interval=args.interval, log=lambda msg: print(msg, flush=True))
    with http.server.ThreadingHTTPServer(("127.0.0.1", args.port), handler) as srv:
        print(f"Serving {out} at http://localhost:{args.port}/ (Ctrl+C to stop)")
        if watcher:
            print(f"Watching {folder} for changes (--no-watch to turn off)")
            watcher.start()
        sys.stdout.flush()
        try:
            srv.serve_forever()
        except KeyboardInterrupt:
            print("\nStopped.")
        finally:
            if watcher:
                watcher.stop()
    return 0


def positive_float(text: str) -> float:
    try:
        value = float(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"not a number: {text!r}") from None
    if not value > 0:
        raise argparse.ArgumentTypeError("must be greater than 0")
    return value


def make_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="sitegen", description="Markdown folder to static blog.")
    p.add_argument("--version", action="version", version=f"sitegen {__version__}")
    sub = p.add_subparsers(dest="command", required=True)
    i = sub.add_parser("init", help="scaffold a new site")
    i.add_argument("folder", nargs="?", default=".")
    i.set_defaults(func=cmd_init)
    n = sub.add_parser("new", help="create a dated post stub in posts/")
    n.add_argument("title", help='post title, e.g. "Notes on sourdough"')
    n.add_argument("-C", "--folder", default=".", help="site folder (default: current)")
    n.add_argument("--tags", help="comma-separated tags, e.g. notes,garden")
    n.add_argument("--date", help="post date as YYYY-MM-DD (default: today)")
    n.add_argument("--draft", action=argparse.BooleanOptionalAction, default=True,
                   help="mark the post as a draft (default); --no-draft publishes it "
                        "on the next build")
    n.set_defaults(func=cmd_new)
    for name, fn, help_ in (("build", cmd_build, "build the site into public/"),
                            ("serve", cmd_serve, "build and serve on localhost")):
        s = sub.add_parser(name, help=help_)
        s.add_argument("folder", nargs="?", default=".")
        s.add_argument("--drafts", action="store_true", help="include draft posts")
        if name == "serve":
            s.add_argument("--port", type=int, default=8000)
            s.add_argument("--watch", action=argparse.BooleanOptionalAction, default=True,
                           help="rebuild when posts, sitegen.toml, templates or static "
                                "files change (default); --no-watch builds once")
            s.add_argument("--interval", type=positive_float, default=0.5, metavar="SECONDS",
                           help="how often to check for changes (default: 0.5)")
        s.set_defaults(func=fn)
    return p


def main(argv: list[str] | None = None) -> int:
    args = make_parser().parse_args(argv)
    try:
        return args.func(args)
    except BuildError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
