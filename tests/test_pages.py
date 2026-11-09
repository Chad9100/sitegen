import xml.etree.ElementTree as ET

import pytest

from sitegen.builder import BuildError, build
from sitegen.cli import main

SM = "{http://www.sitemaps.org/schemas/sitemap/0.9}"


@pytest.fixture
def site(tmp_path):
    (tmp_path / "sitegen.toml").write_text(
        'title = "Test Site"\nbase_url = "https://example.test"\n', encoding="utf-8")
    (tmp_path / "posts").mkdir()
    (tmp_path / "posts" / "p.md").write_text(
        "---\ntitle: A post\ndate: 2026-01-01\n---\nPost body", encoding="utf-8")
    (tmp_path / "pages").mkdir()
    return tmp_path


def page(site, name, front="", body="Page body"):
    (site / "pages" / name).write_text(f"---\n{front}---\n{body}", encoding="utf-8")


def read(path):
    return path.read_text(encoding="utf-8")


def test_page_gets_its_own_url_without_a_date(site):
    page(site, "about.md", "title: About me\n", "Hi, I **write** things.")
    out = build(site)
    html = read(out / "about" / "index.html")
    assert "<h1>About me</h1>" in html
    assert "<strong>write</strong>" in html
    assert "min read" not in html  # pages have no post metadata
    assert '<title>About me</title>' in html


def test_pages_stay_out_of_posts_lists_feed(site):
    page(site, "about.md", "title: About\n")
    out = build(site)
    assert not (out / "posts" / "about").exists()
    assert "posts/about" not in read(out / "index.html")
    assert "About" not in read(out / "atom.xml")


def test_pages_are_in_sitemap(site):
    page(site, "contact.md", "title: Contact\n")
    out = build(site)
    locs = [e.text for e in ET.parse(out / "sitemap.xml").getroot().iter(f"{SM}loc")]
    assert "https://example.test/contact/" in locs


def test_header_nav_on_every_page_with_relative_links(site):
    page(site, "about.md", "title: About\n")
    out = build(site)
    assert '<a href="./about/">About</a>' in read(out / "index.html")
    assert '<a href="../../about/">About</a>' in read(out / "posts" / "a-post" / "index.html")
    about = read(out / "about" / "index.html")
    assert '<a href="../about/" aria-current="page">About</a>' in about


def test_nav_order_then_title_and_nav_false(site):
    page(site, "zeta.md", "title: Zeta\n")
    page(site, "alpha.md", "title: Alpha\n")
    page(site, "contact.md", "title: Contact\norder: -1\n")
    page(site, "imprint.md", "title: Imprint\nnav: false\n")
    out = build(site)
    html = read(out / "index.html")
    nav = html[html.index('<nav class="pages">'):html.index("</nav>")]
    assert nav.index("Contact") < nav.index("Alpha") < nav.index("Zeta")
    assert "Imprint" not in nav
    assert (out / "imprint" / "index.html").exists()  # still built, just unlisted


def test_slug_from_filename_or_front_matter(site):
    page(site, "Contact Us.md", "title: Get in touch\n")
    page(site, "x.md", "title: X\nslug: ../../Evil Path\n")
    out = build(site)
    assert (out / "contact-us" / "index.html").exists()
    assert (out / "evil-path" / "index.html").exists()


def test_draft_page_only_with_drafts(site):
    page(site, "wip.md", "title: WIP\ndraft: true\n")
    assert not (build(site) / "wip").exists()
    out = build(site, drafts=True)
    assert (out / "wip" / "index.html").exists()
    assert "WIP" in read(out / "index.html")


def test_no_pages_means_no_nav(site):
    out = build(site)
    assert '<nav class="pages">' not in read(out / "index.html")


def test_nested_files_under_pages_are_ignored(site):
    (site / "pages" / "drafts").mkdir()
    page(site, "drafts/old.md", "title: Old\n")
    out = build(site)
    assert not (out / "old").exists()
    assert not (out / "posts" / "old").exists()


def test_reserved_slug_is_an_error(site):
    page(site, "tags.md", "title: Tags\n")
    with pytest.raises(BuildError, match=r"pages/tags\.md: page slug 'tags'"):
        build(site)


def test_duplicate_slug_names_both_files(site):
    page(site, "about.md", "title: About\n")
    page(site, "me.md", "title: Me\nslug: about\n")
    with pytest.raises(BuildError) as e:
        build(site)
    assert "pages/me.md:3:" in str(e.value)
    assert "already used by pages/about.md" in str(e.value)


@pytest.mark.parametrize("front, message", [
    ("order: first\n", "pages/a.md:2: order must be a whole number, got 'first'"),
    ("nav: maybe\n", "pages/a.md:2: nav must be true or false, got 'maybe'"),
])
def test_bad_order_or_nav(site, front, message):
    page(site, "a.md", front)
    with pytest.raises(BuildError) as e:
        build(site)
    assert str(e.value) == message


def test_custom_page_template(site):
    (site / "templates").mkdir()
    (site / "templates" / "page.html").write_text(
        '<section class="custom">{{ title }}|{{ body }}</section>', encoding="utf-8")
    page(site, "about.md", "title: About\n", "text")
    html = read(build(site) / "about" / "index.html")
    assert '<section class="custom">About|<p>text</p></section>' in html


def test_init_scaffolds_an_about_page(tmp_path):
    assert main(["init", str(tmp_path)]) == 0
    assert (tmp_path / "pages" / "about.md").is_file()
    assert main(["build", str(tmp_path)]) == 0
    assert '<a href="./about/">About</a>' in read(tmp_path / "public" / "index.html")
