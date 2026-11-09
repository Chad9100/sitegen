import xml.etree.ElementTree as ET

import pytest

from sitegen.builder import build, load_posts
from sitegen.excerpt import plain_text, reading_minutes, summarize, truncate

ATOM = "{http://www.w3.org/2005/Atom}"


def post(folder, name, front, body):
    (folder / "posts").mkdir(parents=True, exist_ok=True)
    (folder / "posts" / name).write_text(f"---\n{front}\n---\n{body}", encoding="utf-8")


def words(n):
    return " ".join(["word"] * n)


@pytest.mark.parametrize("n, minutes", [(0, 1), (10, 1), (299, 1), (300, 2), (1000, 5), (2050, 10)])
def test_reading_minutes(n, minutes):
    assert reading_minutes(f"<p>{words(n)}</p>") == minutes


def test_plain_text_strips_tags_and_entities():
    assert plain_text("<p>Fish &amp; <em>chips</em></p>\n<p>tonight</p>") == "Fish & chips tonight"


def test_inline_tags_do_not_add_spaces_before_punctuation():
    assert plain_text('<p>Read <a href="x">this</a>, <strong>now</strong>.</p>') == "Read this, now."
    assert plain_text("<p>a</p><p>b</p><ul><li>c</li><li>d</li></ul>") == "a b c d"
    assert plain_text("line<br>break") == "line break"


def test_truncate_cuts_at_a_word_boundary():
    text = "alpha beta gamma delta"
    assert truncate(text, 100) == text
    assert truncate(text, 13) == "alpha beta…"
    assert truncate("abcdefghij", 4) == "abcd…"  # one long word: hard cut
    assert truncate("one, two, three", 9) == "one…"  # no dangling comma


def test_summary_priority():
    body = "<p>First paragraph.</p><p>Second.</p>"
    assert summarize(body) == "First paragraph."
    assert summarize(body, before_more_html="<p>Intro bit.</p>") == "Intro bit."
    assert summarize(body, "<p>Intro bit.</p>", override="  Custom   one ") == "Custom one"


def test_more_excerpt_is_not_truncated():
    long_intro = f"<p>{words(80)}</p>"
    assert summarize("<p>x</p>", before_more_html=long_intro) == words(80)


def test_first_paragraph_is_truncated():
    assert summarize(f"<p>{words(80)}</p>").endswith("…")


def test_body_without_paragraphs_falls_back_to_text():
    assert summarize("<ul><li>just a list</li></ul>") == "just a list"


def test_load_posts_uses_front_matter_summary(tmp_path):
    post(tmp_path, "a.md", "title: A\ndate: 2026-11-01\nsummary: Hand-written teaser", "Body text.")
    [p] = load_posts(tmp_path)
    assert p.summary == "Hand-written teaser"


def test_load_posts_uses_more_marker(tmp_path):
    post(tmp_path, "a.md", "title: A\ndate: 2026-11-01",
         "Intro **here**.\n\n<!-- more -->\n\nThe rest of the post.")
    [p] = load_posts(tmp_path)
    assert p.summary == "Intro here."
    assert "The rest of the post." in p.body_html  # the full body still renders


def test_more_marker_is_case_insensitive(tmp_path):
    post(tmp_path, "a.md", "title: A\ndate: 2026-11-01", "Lead.\n\n<!--MORE-->\n\nRest.")
    assert load_posts(tmp_path)[0].summary == "Lead."


def test_build_shows_reading_time_and_summary(tmp_path):
    post(tmp_path, "a.md", "title: Long one\ndate: 2026-11-01",
         f"Opening line.\n\n{words(600)}")
    out = build(tmp_path)
    index = (out / "index.html").read_text(encoding="utf-8")
    assert "3 min read" in index
    assert '<p class="summary">Opening line.</p>' in index
    page = (out / "posts" / "long-one" / "index.html").read_text(encoding="utf-8")
    assert "3 min read" in page


def test_summary_is_html_escaped_in_lists(tmp_path):
    post(tmp_path, "a.md", 'title: A\ndate: 2026-11-01\nsummary: "<script>x</script> & more"', "Body.")
    index = (build(tmp_path) / "index.html").read_text(encoding="utf-8")
    assert "<script>x</script>" not in index
    assert "&lt;script&gt;x&lt;/script&gt; &amp; more" in index


def test_feed_uses_the_new_summary(tmp_path):
    post(tmp_path, "a.md", "title: A\ndate: 2026-11-01", "Teaser.\n\n<!--more-->\n\nHidden part.")
    root = ET.parse(build(tmp_path) / "atom.xml").getroot()
    [entry] = root.findall(f"{ATOM}entry")
    assert entry.find(f"{ATOM}summary").text == "Teaser."


def test_tag_pages_show_summaries_too(tmp_path):
    post(tmp_path, "a.md", "title: A\ndate: 2026-11-01\ntags: [garden]", "Basil report.")
    page = (build(tmp_path) / "tags" / "garden" / "index.html").read_text(encoding="utf-8")
    assert "Basil report." in page and "1 min read" in page
