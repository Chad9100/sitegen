"""Site building: config, post loading, page generation."""
from __future__ import annotations

import html
import re
import shutil
import tomllib
from dataclasses import dataclass
from pathlib import Path

from . import feed, frontmatter
from .frontmatter import FrontMatterError, slugify
from .render import fill, render_markdown
from .themes import THEMES, load_templates

SKIP_DIRS = {"public", "templates", "static", "node_modules"}


class BuildError(Exception):
    pass


@dataclass
class Config:
    title: str = "My Site"
    base_url: str = "http://localhost:8000"
    theme: str = "light"
    posts_per_page: int = 5


@dataclass
class Post:
    title: str
    slug: str
    date: object
    tags: list[str]
    body_html: str
    summary: str
    source: Path


def esc(s: object) -> str:
    return html.escape(str(s), quote=True)


def load_config(folder: Path) -> Config:
    cfg = Config()
    f = folder / "sitegen.toml"
    if not f.is_file():
        return cfg
    try:
        data = tomllib.loads(f.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as e:
        raise BuildError(f"invalid sitegen.toml: {e}") from None
    if "title" in data:
        cfg.title = str(data["title"])
    if "base_url" in data:
        cfg.base_url = str(data["base_url"]).rstrip("/")
    if "theme" in data:
        cfg.theme = str(data["theme"])
    if "posts_per_page" in data:
        ppp = data["posts_per_page"]
        if isinstance(ppp, bool) or not isinstance(ppp, int) or ppp < 1:
            raise BuildError("posts_per_page must be a positive integer")
        cfg.posts_per_page = ppp
    if cfg.theme not in THEMES:
        raise BuildError(f"unknown theme {cfg.theme!r}; choose one of: {', '.join(THEMES)}")
    return cfg


def safe_join(root: Path, *parts: str) -> Path:
    """Join parts under root, refusing anything that resolves outside it."""
    root_r = root.resolve()
    target = root_r.joinpath(*parts).resolve()
    if target != root_r and root_r not in target.parents:
        raise BuildError(f"refusing to write outside {root}: {'/'.join(parts)}")
    return target


def write(root: Path, rel: str, content: str) -> None:
    target = safe_join(root, *rel.split("/"))
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8", newline="\n")


def find_sources(folder: Path) -> list[Path]:
    out = []
    for p in sorted(folder.rglob("*.md")):
        rel = p.relative_to(folder).parts
        if any(part in SKIP_DIRS or part.startswith(".") for part in rel[:-1]) or p.is_symlink():
            continue
        out.append(p)
    return out


def _summary(body_html: str) -> str:
    text = html.unescape(re.sub(r"<[^>]+>", " ", body_html))
    return " ".join(text.split())[:200]


def load_posts(folder: Path, drafts: bool = False) -> list[Post]:
    posts: list[Post] = []
    used: set[str] = set()
    for src in find_sources(folder):
        try:
            meta, body = frontmatter.parse(src.read_text(encoding="utf-8"))
        except (FrontMatterError, UnicodeDecodeError) as e:
            raise BuildError(f"{src.name}: {e}") from None
        if meta.draft and not drafts:
            continue
        if meta.date is None:
            raise BuildError(f"{src.name}: missing 'date' in front matter")
        title = meta.title or src.stem
        base = slugify(meta.slug or title or src.stem)
        slug, n = base, 2
        while slug in used:
            slug, n = f"{base}-{n}", n + 1
        used.add(slug)
        body_html = render_markdown(body)
        posts.append(Post(title, slug, meta.date, meta.tags, body_html,
                          _summary(body_html), src))
    posts.sort(key=lambda p: (p.date, p.slug), reverse=True)
    return posts


class Site:
    def __init__(self, folder: Path, drafts: bool = False):
        self.folder = folder
        self.cfg = load_config(folder)
        self.tpl = load_templates(self.cfg.theme, folder / "templates")
        self.out = folder / "public"
        self.posts = load_posts(folder, drafts)
        self.tags: dict[str, tuple[str, list[Post]]] = {}
        for p in self.posts:
            for t in p.tags:
                slug = slugify(t, "tag")
                self.tags.setdefault(slug, (t, []))[1].append(p)

    def page(self, title: str, content: str, depth: int) -> str:
        root = "../" * depth or "./"
        return fill(self.tpl["base"], {
            "title": esc(title), "site_title": esc(self.cfg.title), "root": root,
            "feed_url": root + "atom.xml", "css": self.tpl["css"], "content": content,
        })

    def tag_links(self, tags: list[str], root: str) -> str:
        return " ".join(
            f'<a class="tag" href="{root}tags/{slugify(t, "tag")}/">#{esc(t)}</a>' for t in tags)

    def paginate(self, heading: str, posts: list[Post], base: str) -> None:
        per = self.cfg.posts_per_page
        pages = max(1, -(-len(posts) // per))
        base_depth = base.count("/")
        for n in range(1, pages + 1):
            depth = base_depth + (2 if n > 1 else 0)
            root = "../" * depth or "./"
            items = "\n".join(
                f'<li><a href="{root}posts/{p.slug}/">{esc(p.title)}</a> '
                f'<span class="meta">{p.date:%Y-%m-%d}</span></li>'
                for p in posts[(n - 1) * per:n * per])
            nav = []
            if n > 1:
                prev = base if n == 2 else f"{base}page/{n - 1}/"
                nav.append(f'<a rel="prev" href="{root}{prev}">Newer</a>')
            if n < pages:
                nav.append(f'<a rel="next" href="{root}{base}page/{n + 1}/">Older</a>')
            pager = f'<nav class="pager">{" | ".join(nav)}</nav>' if nav else ""
            content = fill(self.tpl["list"], {"heading": esc(heading), "items": items,
                                              "pager": pager})
            rel = f"{base}index.html" if n == 1 else f"{base}page/{n}/index.html"
            write(self.out, rel, self.page(heading, content, depth))

    def build(self) -> Path:
        if self.out.exists():
            shutil.rmtree(self.out)
        self.out.mkdir(parents=True)
        self.paginate(self.cfg.title, self.posts, "")
        for p in self.posts:
            root = "../../"
            content = fill(self.tpl["post"], {
                "title": esc(p.title), "date": f"{p.date:%Y-%m-%d}",
                "tags": self.tag_links(p.tags, root), "body": p.body_html})
            write(self.out, f"posts/{p.slug}/index.html", self.page(p.title, content, 2))
        for slug, (name, plist) in self.tags.items():
            self.paginate(f"Tagged: {name}", plist, f"tags/{slug}/")
        base = self.cfg.base_url
        feed_posts = [{"title": p.title, "url": f"{base}/posts/{p.slug}/", "date": p.date,
                       "summary": p.summary, "tags": p.tags} for p in self.posts]
        write(self.out, "atom.xml", feed.build_atom(self.cfg.title, base, feed_posts))
        entries = [(base + "/", self.posts[0].date if self.posts else None)]
        entries += [(f"{base}/posts/{p.slug}/", p.date) for p in self.posts]
        entries += [(f"{base}/tags/{s}/", None) for s in self.tags]
        write(self.out, "sitemap.xml", feed.build_sitemap(entries))
        self.copy_static()
        return self.out

    def copy_static(self) -> None:
        static = self.folder / "static"
        if not static.is_dir() or static.is_symlink():
            return
        src_root = static.resolve()
        if self.folder.resolve() not in src_root.parents:
            return
        for f in sorted(src_root.rglob("*")):
            if f.is_symlink() or not f.is_file():
                continue
            real = f.resolve()
            if src_root not in real.parents:
                continue
            rel = f.relative_to(src_root)
            dest = safe_join(self.out, "static", *rel.parts)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(real, dest)


def build(folder: Path, drafts: bool = False) -> Path:
    folder = Path(folder)
    if not folder.is_dir():
        raise BuildError(f"not a folder: {folder}")
    return Site(folder, drafts).build()
