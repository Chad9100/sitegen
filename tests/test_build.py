import os
import xml.etree.ElementTree as ET

import pytest

from sitegen.builder import BuildError, build, safe_join
from sitegen.cli import main
from sitegen.render import fill

ATOM = "{http://www.w3.org/2005/Atom}"
SM = "{http://www.sitemaps.org/schemas/sitemap/0.9}"


def post(folder, name, title="T", date="2026-01-01", tags="", extra="", body="Hello"):
    lines = ["---", f"title: {title}", f"date: {date}"]
    if tags:
        lines.append(f"tags: [{tags}]")
    if extra:
        lines.append(extra)
    lines += ["---", body]
    (folder / name).write_text("\n".join(lines), encoding="utf-8")


@pytest.fixture
def site(tmp_path):
    (tmp_path / "sitegen.toml").write_text(
        'title = "Test Site"\nbase_url = "https://example.test/"\nposts_per_page = 2\n')
    return tmp_path


def read(path):
    return path.read_text(encoding="utf-8")


def test_basic_build(site):
    post(site, "a.md", title="Alpha", body="Some **bold** text")
    out = build(site)
    assert out == site / "public"
    page = read(out / "posts" / "alpha" / "index.html")
    assert "<strong>bold</strong>" in page and "<h1>Alpha</h1>" in page
    assert (out / "index.html").exists()


def test_drafts_skipped_by_default(site):
    post(site, "a.md", title="Secret", extra="draft: true")
    post(site, "b.md", title="Public")
    out = build(site)
    assert not (out / "posts" / "secret").exists()
    assert "Secret" not in read(out / "index.html")
    assert "Secret" not in read(out / "atom.xml")


def test_drafts_included_with_flag(site):
    post(site, "a.md", title="Secret", extra="draft: true")
    out = build(site, drafts=True)
    assert (out / "posts" / "secret" / "index.html").exists()


def test_index_newest_first(site):
    post(site, "a.md", title="Old", date="2025-01-01")
    post(site, "b.md", title="New", date="2026-06-01")
    html = read(build(site) / "index.html")
    assert html.index("New") < html.index("Old")


def test_pagination(site):
    for i in range(5):
        post(site, f"p{i}.md", title=f"Post{i}", date=f"2026-01-0{i + 1}")
    out = build(site)
    p1, p2, p3 = (read(out / "index.html"), read(out / "page/2/index.html"),
                  read(out / "page/3/index.html"))
    assert "Post4" in p1 and "Post3" in p1 and "Post2" not in p1
    assert "Post2" in p2 and "Post1" in p2
    assert "Post0" in p3 and "Post4" not in p3
    assert 'rel="next"' in p1 and 'rel="prev"' not in p1
    assert 'rel="prev"' in p3 and 'rel="next"' not in p3
    assert not (out / "page/4").exists()


def test_single_page_has_no_pager(site):
    post(site, "a.md")
    assert 'class="pager"' not in read(build(site) / "index.html")


def test_empty_site_builds(site):
    out = build(site)
    assert (out / "index.html").exists()
    assert ET.parse(out / "atom.xml").getroot().tag == ATOM + "feed"


def test_tag_pages(site):
    post(site, "a.md", title="Alpha", tags="python, Web Dev")
    post(site, "b.md", title="Beta", tags="python")
    out = build(site)
    py = read(out / "tags" / "python" / "index.html")
    assert "Alpha" in py and "Beta" in py
    web = read(out / "tags" / "web-dev" / "index.html")
    assert "Alpha" in web and "Beta" not in web
    assert "/tags/python/" in read(out / "posts" / "alpha" / "index.html")


def test_tag_pages_paginate(site):
    for i in range(3):
        post(site, f"p{i}.md", title=f"P{i}", date=f"2026-01-0{i + 1}", tags="x")
    assert (build(site) / "tags/x/page/2/index.html").exists()


def test_draft_only_tag_has_no_page(site):
    post(site, "a.md", tags="hidden", extra="draft: true")
    assert not (build(site) / "tags" / "hidden").exists()


def test_atom_feed_is_valid_xml(site):
    post(site, "a.md", title="Fish & Chips <3", tags="food", body="Tasty & <b>hot</b>")
    root = ET.parse(build(site) / "atom.xml").getroot()
    assert root.tag == ATOM + "feed"
    assert root.find(ATOM + "title").text == "Test Site"
    entries = root.findall(ATOM + "entry")
    assert len(entries) == 1
    e = entries[0]
    assert e.find(ATOM + "title").text == "Fish & Chips <3"
    assert e.find(ATOM + "id").text == "https://example.test/posts/fish-chips-3/"
    assert e.find(ATOM + "updated").text == "2026-01-01T00:00:00Z"
    assert e.find(ATOM + "category").get("term") == "food"


def test_atom_limited_to_20_entries(site):
    for i in range(25):
        post(site, f"p{i}.md", title=f"P{i}", date=f"2026-01-{i + 1:02d}")
    root = ET.parse(build(site) / "atom.xml").getroot()
    assert len(root.findall(ATOM + "entry")) == 20


def test_sitemap(site):
    post(site, "a.md", title="Alpha", tags="t")
    root = ET.parse(build(site) / "sitemap.xml").getroot()
    locs = [u.find(SM + "loc").text for u in root.findall(SM + "url")]
    assert "https://example.test/" in locs
    assert "https://example.test/posts/alpha/" in locs
    assert "https://example.test/tags/t/" in locs


def test_title_is_html_escaped(site):
    post(site, "a.md", title="<script>alert(1)</script>", tags="<b>x</b>")
    out = build(site)
    for f in (out / "index.html", *out.glob("posts/*/index.html"), *out.glob("tags/*/index.html")):
        text = read(f)
        assert "<script>alert(1)</script>" not in text
        assert "<b>x</b>" not in text
    assert "&lt;script&gt;" in read(out / "index.html")


def test_site_title_is_escaped(tmp_path):
    (tmp_path / "sitegen.toml").write_text('title = "A <i>b</i> & c"\n')
    text = read(build(tmp_path) / "index.html")
    assert "<i>b</i>" not in text and "&lt;i&gt;" in text


def test_hostile_slug_stays_inside_public(site):
    post(site, "a.md", title="Evil", extra="slug: ../../../escaped")
    post(site, "b.md", title="Evil2", extra="slug: /etc/passwd")
    post(site, "c.md", title="Evil3", extra="slug: ..\\..\\x")
    out = build(site)
    assert not (site.parent / "escaped").exists()
    assert (out / "posts" / "escaped" / "index.html").exists()
    assert (out / "posts" / "etc-passwd" / "index.html").exists()
    for f in out.rglob("*"):
        assert out.resolve() in f.resolve().parents or f.resolve() == out.resolve()


def test_hostile_tag_stays_inside_public(site):
    post(site, "a.md", tags="../../evil")
    out = build(site)
    assert (out / "tags" / "evil" / "index.html").exists()
    assert not (site.parent / "evil").exists()


def test_duplicate_slugs_are_disambiguated(site):
    post(site, "a.md", title="Same")
    post(site, "b.md", title="Same")
    out = build(site)
    assert (out / "posts" / "same").is_dir() and (out / "posts" / "same-2").is_dir()


def test_safe_join_rejects_escape(tmp_path):
    with pytest.raises(BuildError):
        safe_join(tmp_path, "..", "x")
    assert safe_join(tmp_path, "a", "b").parent.parent == tmp_path.resolve()


def test_static_assets_copied(site):
    (site / "static" / "img").mkdir(parents=True)
    (site / "static" / "img" / "logo.txt").write_text("logo")
    out = build(site)
    assert read(out / "static" / "img" / "logo.txt") == "logo"


def test_static_symlink_escape_not_copied(site, tmp_path_factory):
    secret = tmp_path_factory.mktemp("outside") / "secret.txt"
    secret.write_text("TOP SECRET")
    (site / "static").mkdir()
    try:
        os.symlink(secret, site / "static" / "leak.txt")
    except (OSError, NotImplementedError):
        pytest.skip("symlinks unavailable")
    out = build(site)
    assert not (out / "static" / "leak.txt").exists()


def test_missing_date_is_error(site):
    (site / "a.md").write_text("---\ntitle: X\n---\nbody")
    with pytest.raises(BuildError, match="date"):
        build(site)


def test_bad_front_matter_names_file(site):
    (site / "broken.md").write_text("---\ntitle: X\n")
    with pytest.raises(BuildError, match="broken.md"):
        build(site)


def test_unknown_theme_rejected(tmp_path):
    (tmp_path / "sitegen.toml").write_text('theme = "neon"\n')
    with pytest.raises(BuildError, match="theme"):
        build(tmp_path)


@pytest.mark.parametrize("val", ["0", "-1", '"x"', "true"])
def test_bad_posts_per_page(tmp_path, val):
    (tmp_path / "sitegen.toml").write_text(f"posts_per_page = {val}\n")
    with pytest.raises(BuildError):
        build(tmp_path)


def test_dark_theme(tmp_path):
    (tmp_path / "sitegen.toml").write_text('theme = "dark"\n')
    assert "#16181d" in read(build(tmp_path) / "index.html")


def test_default_light_theme(tmp_path):
    assert "background:#fff" in read(build(tmp_path) / "index.html")


def test_markdown_fenced_code_and_tables(site):
    post(site, "a.md", title="Code", body="```py\nx = 1\n```\n\n| a | b |\n|---|---|\n| 1 | 2 |\n")
    page = read(build(site) / "posts" / "code" / "index.html")
    assert "<pre><code" in page and "<table>" in page


def test_template_override(site):
    (site / "templates").mkdir()
    (site / "templates" / "post.html").write_text("<div id='custom'>{{ title }}|{{ nope }}</div>")
    post(site, "a.md", title="Mine")
    page = read(build(site) / "posts" / "mine" / "index.html")
    assert "<div id='custom'>Mine|</div>" in page


def test_template_values_not_reexpanded():
    assert fill("{{ a }}", {"a": "{{ b }}", "b": "BAD"}) == "{{ b }}"


def test_public_rebuilt_clean_and_public_not_scanned(site):
    post(site, "a.md", title="Alpha")
    out = build(site)
    (out / "stale.txt").write_text("x")
    (out / "junk.md").write_text("---\ntitle: J\ndate: 2026-01-01\n---\n")
    out = build(site)
    assert not (out / "stale.txt").exists()
    assert not (out / "posts" / "j").exists()


def test_cli_init_and_build(tmp_path, capsys):
    target = tmp_path / "blog"
    assert main(["init", str(target)]) == 0
    assert len(list((target / "posts").glob("*.md"))) == 2
    assert main(["build", str(target)]) == 0
    assert (target / "public" / "posts" / "herb-garden" / "index.html").exists()


def test_cli_init_does_not_overwrite(tmp_path):
    main(["init", str(tmp_path)])
    cfg = tmp_path / "sitegen.toml"
    cfg.write_text('title = "Mine"\n')
    main(["init", str(tmp_path)])
    assert cfg.read_text() == 'title = "Mine"\n'


def test_cli_build_error_returns_1(tmp_path, capsys):
    (tmp_path / "a.md").write_text("---\ntitle: x\n---\n")
    assert main(["build", str(tmp_path)]) == 1
    assert "error:" in capsys.readouterr().err
