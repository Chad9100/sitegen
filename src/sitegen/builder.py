"""Site building: config, post loading, page generation."""
from __future__ import annotations

import difflib
import html
import re
import shutil
import tomllib
from dataclasses import dataclass
from pathlib import Path

from . import feed, frontmatter
from .excerpt import MORE, reading_minutes, summarize
from .frontmatter import FrontMatterError, slugify
from .render import fill, render_markdown
from .themes import THEMES, load_templates

SKIP_DIRS = {"public", "templates", "static", "node_modules"}
# Top-level folder for standalone pages (About, Contact): not posts.
PAGES_DIR = "pages"
# Top-level output paths a page slug must not take over.
RESERVED_SLUGS = {"posts", "tags", "page", "static"}


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
    minutes: int = 1


@dataclass
class Page:
    """A standalone page: no date, not in lists or the feed, linked from the header."""
    title: str
    slug: str
    body_html: str
    source: Path
    order: int = 0
    nav: bool = True


def esc(s: object) -> str:
    return html.escape(str(s), quote=True)


def located(where: str, message: str, line: int | None = None,
            text: str | None = None) -> str:
    """Format an error as ``file:line: message`` plus the offending line.

    The ``file:line:`` prefix is the form editors and terminals can jump to.
    """
    head = f"{where}:{line}: {message}" if line else f"{where}: {message}"
    if line and text is not None:
        head += f"\n  {line:>4} | {text.rstrip()}"
    return head


def _key_line(text: str, key: str) -> tuple[int | None, str | None]:
    """Line number and text of the top-level ``key = ...`` in a TOML file."""
    for n, raw in enumerate(text.splitlines(), start=1):
        if raw.lstrip().startswith("["):
            break  # past the top-level table
        if re.match(rf"\s*{re.escape(key)}\s*=", raw):
            return n, raw
    return None, None


def load_config(folder: Path) -> Config:
    cfg = Config()
    f = folder / "sitegen.toml"
    if not f.is_file():
        return cfg
    text = f.read_text(encoding="utf-8")
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as e:
        m = re.search(r"\(at line (\d+), column \d+\)", str(e))
        line = int(m.group(1)) if m else None
        lines = text.splitlines()
        src = lines[line - 1] if line and line <= len(lines) else None
        raise BuildError(located("sitegen.toml", f"invalid TOML: {e}", line, src)) from None

    def bad(key: str, message: str) -> BuildError:
        return BuildError(located("sitegen.toml", message, *_key_line(text, key)))

    if "title" in data:
        cfg.title = str(data["title"])
    if "base_url" in data:
        cfg.base_url = str(data["base_url"]).rstrip("/")
    if "theme" in data:
        cfg.theme = str(data["theme"])
    if "posts_per_page" in data:
        ppp = data["posts_per_page"]
        if isinstance(ppp, bool) or not isinstance(ppp, int) or ppp < 1:
            raise bad("posts_per_page",
                      f"posts_per_page must be a positive integer, got {ppp!r}")
        cfg.posts_per_page = ppp
    if cfg.theme not in THEMES:
        raise bad("theme", f"unknown theme {cfg.theme!r}; choose one of: {', '.join(THEMES)}")
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
        if len(rel) > 1 and rel[0] == PAGES_DIR:
            continue
        out.append(p)
    return out


def read_source(folder: Path, src: Path) -> tuple[frontmatter.Meta, str]:
    where = src.relative_to(folder).as_posix()
    try:
        return frontmatter.parse(src.read_text(encoding="utf-8"))
    except FrontMatterError as e:
        raise BuildError(located(where, str(e), e.line, e.text)) from None
    except UnicodeDecodeError as e:
        raise BuildError(decode_error(where, src, e)) from None


def load_pages(folder: Path, drafts: bool = False) -> list[Page]:
    """Load ``pages/*.md`` (top level only), ordered for the header nav."""
    pages_dir = folder / PAGES_DIR
    if not pages_dir.is_dir() or pages_dir.is_symlink():
        return []
    pages: list[Page] = []
    owner: dict[str, str] = {}
    for src in sorted(pages_dir.glob("*.md")):
        if src.is_symlink() or not src.is_file():
            continue
        where = src.relative_to(folder).as_posix()
        meta, body = read_source(folder, src)
        if meta.draft and not drafts:
            continue
        title = meta.title or src.stem
        slug = slugify(meta.slug or src.stem, "page")
        if slug in RESERVED_SLUGS:
            raise BuildError(located(
                where, f"page slug {slug!r} would replace sitegen's own /{slug}/ "
                       "folder; rename the file or set another 'slug:'",
                meta.lines.get("slug")))
        if slug in owner:
            raise BuildError(located(
                where, f"page slug {slug!r} is already used by {owner[slug]}; "
                       "set a different 'slug:' in one of them", meta.lines.get("slug")))
        owner[slug] = where
        order, nav = 0, True
        if "order" in meta.extra:
            raw = meta.extra["order"]
            try:
                order = int(raw)
            except ValueError:
                raise BuildError(located(where, f"order must be a whole number, got {raw!r}",
                                         meta.lines.get("order"))) from None
        if "nav" in meta.extra:
            try:
                nav = frontmatter.parse_bool(meta.extra["nav"])
            except FrontMatterError:
                raise BuildError(located(
                    where, f"nav must be true or false, got {meta.extra['nav']!r}",
                    meta.lines.get("nav"))) from None
        pages.append(Page(title, slug, render_markdown(body), src, order, nav))
    pages.sort(key=lambda p: (p.order, p.title.lower(), p.slug))
    return pages


def load_posts(folder: Path, drafts: bool = False) -> list[Post]:
    posts: list[Post] = []
    used: set[str] = set()
    for src in find_sources(folder):
        where = src.relative_to(folder).as_posix()
        meta, body = read_source(folder, src)
        if meta.draft and not drafts:
            continue
        if meta.date is None:
            raise BuildError(missing_date(where, meta))
        title = meta.title or src.stem
        base = slugify(meta.slug or title or src.stem)
        slug, n = base, 2
        while slug in used:
            slug, n = f"{base}-{n}", n + 1
        used.add(slug)
        body_html = render_markdown(body)
        parts = MORE.split(body, maxsplit=1)
        before_more = render_markdown(parts[0]) if len(parts) == 2 else None
        summary = summarize(body_html, before_more, meta.extra.get("summary"))
        posts.append(Post(title, slug, meta.date, meta.tags, body_html,
                          summary, src, reading_minutes(body_html)))
    posts.sort(key=lambda p: (p.date, p.slug), reverse=True)
    return posts


def decode_error(where: str, src: Path, e: UnicodeDecodeError) -> str:
    data = src.read_bytes()
    line = data.count(b"\n", 0, e.start) + 1
    column = e.start - (data.rfind(b"\n", 0, e.start) + 1) + 1
    return located(where, f"not valid UTF-8 (byte 0x{data[e.start]:02x} at column "
                          f"{column}); re-save the file as UTF-8", line)


def missing_date(where: str, meta: frontmatter.Meta) -> str:
    message = "missing 'date' in front matter"
    typo = difflib.get_close_matches("date", list(meta.extra), n=1, cutoff=0.6)
    if typo:
        return located(where, f"{message}; did you mean 'date' instead of '{typo[0]}'?",
                       meta.lines.get(typo[0]))
    return located(where, f"{message} (add a line like 'date: 2026-01-10' "
                          "between the '---' lines)")


class Site:
    def __init__(self, folder: Path, drafts: bool = False):
        self.folder = folder
        self.cfg = load_config(folder)
        self.tpl = load_templates(self.cfg.theme, folder / "templates")
        self.out = folder / "public"
        self.posts = load_posts(folder, drafts)
        self.pages = load_pages(folder, drafts)
        self.tags: dict[str, tuple[str, list[Post]]] = {}
        for p in self.posts:
            for t in p.tags:
                slug = slugify(t, "tag")
                self.tags.setdefault(slug, (t, []))[1].append(p)

    def page(self, title: str, content: str, depth: int, current: str = "") -> str:
        root = "../" * depth or "./"
        return fill(self.tpl["base"], {
            "title": esc(title), "site_title": esc(self.cfg.title), "root": root,
            "feed_url": root + "atom.xml", "css": self.tpl["css"], "content": content,
            "nav": self.nav(root, current),
        })

    def nav(self, root: str, current: str = "") -> str:
        """Header links to the standalone pages (those without ``nav: false``)."""
        links = [
            f'<a href="{root}{p.slug}/"'
            + (' aria-current="page"' if p.slug == current else "")
            + f">{esc(p.title)}</a>"
            for p in self.pages if p.nav]
        return f'<nav class="pages">{" ".join(links)}</nav>' if links else ""

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
                f'<span class="meta">{p.date:%Y-%m-%d} · {p.minutes} min read</span>'
                + (f'\n<p class="summary">{esc(p.summary)}</p>' if p.summary else "")
                + "</li>"
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
                "reading_time": f"{p.minutes} min read", "summary": esc(p.summary),
                "tags": self.tag_links(p.tags, root), "body": p.body_html})
            write(self.out, f"posts/{p.slug}/index.html", self.page(p.title, content, 2))
        for slug, (name, plist) in self.tags.items():
            self.paginate(f"Tagged: {name}", plist, f"tags/{slug}/")
        for pg in self.pages:
            content = fill(self.tpl["page"], {"title": esc(pg.title), "body": pg.body_html})
            write(self.out, f"{pg.slug}/index.html",
                  self.page(pg.title, content, 1, current=pg.slug))
        base = self.cfg.base_url
        feed_posts = [{"title": p.title, "url": f"{base}/posts/{p.slug}/", "date": p.date,
                       "summary": p.summary, "tags": p.tags} for p in self.posts]
        write(self.out, "atom.xml", feed.build_atom(self.cfg.title, base, feed_posts))
        entries = [(base + "/", self.posts[0].date if self.posts else None)]
        entries += [(f"{base}/posts/{p.slug}/", p.date) for p in self.posts]
        entries += [(f"{base}/{pg.slug}/", None) for pg in self.pages]
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
