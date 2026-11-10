import xml.etree.ElementTree as ET

from sitegen.builder import build

A = "{http://www.w3.org/2005/Atom}"
SM = "{http://www.sitemaps.org/schemas/sitemap/0.9}"


def post(folder, name, title, date, tags="", extra=""):
    lines = ["---", f"title: {title}", f"date: {date}"]
    if tags:
        lines.append(f"tags: [{tags}]")
    if extra:
        lines.append(extra)
    lines += ["---", f"Body of {title}"]
    (folder / name).write_text("\n".join(lines), encoding="utf-8")


def site(folder, extra=""):
    (folder / "sitegen.toml").write_text(
        f'title = "Blog"\nbase_url = "https://example.test"\n{extra}', encoding="utf-8")


def entries(feed):
    return [e.find(f"{A}title").text for e in feed.iter(f"{A}entry")]


def test_one_feed_per_tag_with_only_its_posts_newest_first(tmp_path):
    site(tmp_path)
    post(tmp_path, "a.md", "Old python", "2026-01-01", "python")
    post(tmp_path, "b.md", "Art piece", "2026-01-02", "art")
    post(tmp_path, "c.md", "New python", "2026-01-03", "python, art")
    out = build(tmp_path)
    py = ET.parse(out / "tags/python/atom.xml").getroot()
    art = ET.parse(out / "tags/art/atom.xml").getroot()
    assert entries(py) == ["New python", "Old python"]
    assert entries(art) == ["New python", "Art piece"]
    assert len(entries(ET.parse(out / "atom.xml").getroot())) == 3


def test_feed_metadata_points_at_the_tag(tmp_path):
    site(tmp_path)
    post(tmp_path, "a.md", "Old", "2026-01-01", "Web Dev")
    post(tmp_path, "b.md", "New", "2026-02-05", "Web Dev")
    feed = ET.parse(build(tmp_path) / "tags/web-dev/atom.xml").getroot()
    assert feed.find(f"{A}title").text == "Blog: #Web Dev"
    assert feed.find(f"{A}id").text == "https://example.test/tags/web-dev/"
    links = {l.get("rel", "alternate"): l.get("href") for l in feed.findall(f"{A}link")}
    assert links == {"alternate": "https://example.test/tags/web-dev/",
                     "self": "https://example.test/tags/web-dev/atom.xml"}
    assert feed.find(f"{A}updated").text == "2026-02-05T00:00:00Z"
    entry = feed.find(f"{A}entry")
    assert entry.find(f"{A}id").text == "https://example.test/posts/new/"
    assert entry.find(f"{A}category").get("term") == "Web Dev"


def test_main_feed_links_unchanged(tmp_path):
    site(tmp_path)
    post(tmp_path, "a.md", "A", "2026-01-01", "t")
    feed = ET.parse(build(tmp_path) / "atom.xml").getroot()
    assert feed.find(f"{A}id").text == "https://example.test/"
    hrefs = [l.get("href") for l in feed.findall(f"{A}link")]
    assert hrefs == ["https://example.test/", "https://example.test/atom.xml"]


def test_tag_pages_advertise_and_link_their_feed(tmp_path):
    site(tmp_path, "posts_per_page = 1\n")
    post(tmp_path, "a.md", "A", "2026-01-01", "t")
    post(tmp_path, "b.md", "B", "2026-01-02", "t")
    out = build(tmp_path)
    first = (out / "tags/t/index.html").read_text(encoding="utf-8")
    second = (out / "tags/t/page/2/index.html").read_text(encoding="utf-8")
    assert 'type="application/atom+xml" href="../../tags/t/atom.xml"' in first
    assert '<a class="feed" href="../../tags/t/atom.xml">Atom feed</a>' in first
    assert 'type="application/atom+xml" href="../../../../tags/t/atom.xml"' in second
    home = (out / "index.html").read_text(encoding="utf-8")
    assert 'type="application/atom+xml" href="./atom.xml"' in home
    assert 'class="feed"' not in home
    tags = (out / "tags/index.html").read_text(encoding="utf-8")
    assert 'href="../atom.xml"' in tags


def test_drafts_left_out_unless_requested(tmp_path):
    site(tmp_path)
    post(tmp_path, "a.md", "Public", "2026-01-01", "t")
    post(tmp_path, "b.md", "Secret", "2026-01-02", "t, hidden", extra="draft: true")
    out = build(tmp_path)
    assert entries(ET.parse(out / "tags/t/atom.xml").getroot()) == ["Public"]
    assert not (out / "tags/hidden").exists()
    out = build(tmp_path, drafts=True)
    assert entries(ET.parse(out / "tags/t/atom.xml").getroot()) == ["Secret", "Public"]


def test_tag_feed_capped_at_twenty_and_not_in_sitemap(tmp_path):
    site(tmp_path)
    for n in range(1, 26):
        post(tmp_path, f"p{n:02}.md", f"Post {n:02}", f"2026-01-{n:02}", "many")
    out = build(tmp_path)
    titles = entries(ET.parse(out / "tags/many/atom.xml").getroot())
    assert len(titles) == 20 and titles[0] == "Post 25" and titles[-1] == "Post 06"
    locs = [e.text for e in ET.parse(out / "sitemap.xml").iter(f"{SM}loc")]
    assert not any(loc.endswith("atom.xml") for loc in locs)


def test_titles_with_markup_are_xml_safe(tmp_path):
    site(tmp_path)
    post(tmp_path, "a.md", "A", "2026-01-01", "<b>&x</b>")
    out = build(tmp_path)
    feeds = list((out / "tags").glob("*/atom.xml"))
    assert len(feeds) == 1
    feed = ET.parse(feeds[0]).getroot()
    assert feed.find(f"{A}title").text == "Blog: #<b>&x</b>"
