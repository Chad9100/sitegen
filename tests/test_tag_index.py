import xml.etree.ElementTree as ET

from sitegen.builder import build

SM = "{http://www.sitemaps.org/schemas/sitemap/0.9}"


def post(folder, name, title, tags="", extra=""):
    lines = ["---", f"title: {title}", "date: 2026-01-01"]
    if tags:
        lines.append(f"tags: [{tags}]")
    if extra:
        lines.append(extra)
    lines += ["---", "Hello"]
    (folder / name).write_text("\n".join(lines), encoding="utf-8")


def read(path):
    return path.read_text(encoding="utf-8")


def test_lists_every_tag_with_counts_most_used_first(tmp_path):
    post(tmp_path, "a.md", "A", tags="python, web")
    post(tmp_path, "b.md", "B", tags="python, web")
    post(tmp_path, "c.md", "C", tags="python, art")
    page = read(build(tmp_path) / "tags" / "index.html")
    assert "<h1>Tags</h1>" in page and "<title>Tags</title>" in page
    py = page.index('href="../tags/python/">#python</a> <span class="meta">3 posts</span>')
    web = page.index('href="../tags/web/">#web</a> <span class="meta">2 posts</span>')
    art = page.index('href="../tags/art/">#art</a> <span class="meta">1 post</span>')
    assert py < web < art


def test_ties_sorted_by_name_case_insensitively(tmp_path):
    post(tmp_path, "a.md", "A", tags="zeta, Beta, alpha")
    page = read(build(tmp_path) / "tags" / "index.html")
    assert page.index("#alpha") < page.index("#Beta") < page.index("#zeta")


def test_tag_names_escaped(tmp_path):
    post(tmp_path, "a.md", "A", tags="<b>x</b>")
    page = read(build(tmp_path) / "tags" / "index.html")
    assert "<b>x</b>" not in page and "#&lt;b&gt;x&lt;/b&gt;" in page


def test_drafts_not_counted(tmp_path):
    post(tmp_path, "a.md", "A", tags="shared")
    post(tmp_path, "b.md", "B", tags="shared, secret", extra="draft: true")
    page = read(build(tmp_path) / "tags" / "index.html")
    assert "1 post<" in page and "secret" not in page
    assert "2 posts" in read(build(tmp_path, drafts=True) / "tags" / "index.html")


def test_no_tags_no_index_and_not_in_sitemap(tmp_path):
    post(tmp_path, "a.md", "A")
    out = build(tmp_path)
    assert not (out / "tags").exists()
    locs = [e.text for e in ET.parse(out / "sitemap.xml").iter(f"{SM}loc")]
    assert not any("/tags/" in loc for loc in locs)


def test_in_sitemap_and_linked_from_tag_pages(tmp_path):
    (tmp_path / "sitegen.toml").write_text(
        'base_url = "https://example.test"\nposts_per_page = 1\n')
    post(tmp_path, "a.md", "A", tags="t")
    post(tmp_path, "b.md", "B", tags="t")
    out = build(tmp_path)
    locs = [e.text for e in ET.parse(out / "sitemap.xml").iter(f"{SM}loc")]
    assert "https://example.test/tags/" in locs
    assert '<a href="../../tags/">All tags</a>' in read(out / "tags/t/index.html")
    assert '<a href="../../../../tags/">All tags</a>' in read(out / "tags/t/page/2/index.html")
    assert "All tags" not in read(out / "index.html")
