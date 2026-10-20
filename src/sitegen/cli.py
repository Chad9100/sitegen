"""Command line interface."""
from __future__ import annotations

import argparse
import functools
import http.server
import sys
from pathlib import Path

from . import __version__
from .builder import BuildError, build

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


def cmd_build(args) -> int:
    out = build(Path(args.folder), drafts=args.drafts)
    print(f"Built site into {out}")
    return 0


def cmd_serve(args) -> int:
    out = build(Path(args.folder), drafts=args.drafts)
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(out))
    with http.server.ThreadingHTTPServer(("127.0.0.1", args.port), handler) as srv:
        print(f"Serving {out} at http://localhost:{args.port}/ (Ctrl+C to stop)")
        try:
            srv.serve_forever()
        except KeyboardInterrupt:
            print("\nStopped.")
    return 0


def make_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="sitegen", description="Markdown folder to static blog.")
    p.add_argument("--version", action="version", version=f"sitegen {__version__}")
    sub = p.add_subparsers(dest="command", required=True)
    i = sub.add_parser("init", help="scaffold a new site")
    i.add_argument("folder", nargs="?", default=".")
    i.set_defaults(func=cmd_init)
    for name, fn, help_ in (("build", cmd_build, "build the site into public/"),
                            ("serve", cmd_serve, "build and serve on localhost")):
        s = sub.add_parser(name, help=help_)
        s.add_argument("folder", nargs="?", default=".")
        s.add_argument("--drafts", action="store_true", help="include draft posts")
        if name == "serve":
            s.add_argument("--port", type=int, default=8000)
        s.set_defaults(func=fn)
    return p


def main(argv: list[str] | None = None) -> int:
    args = make_parser().parse_args(argv)
    try:
        return args.func(args)
    except BuildError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
