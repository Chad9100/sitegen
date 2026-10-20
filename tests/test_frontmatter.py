import pytest

from sitegen.frontmatter import FrontMatterError, parse, slugify


def test_basic_fields():
    meta, body = parse("---\ntitle: Hi\ndate: 2026-03-04\ntags: [a, b]\ndraft: true\nslug: x\n---\nBody")
    assert meta.title == "Hi"
    assert meta.date.year == 2026 and meta.date.month == 3 and meta.date.day == 4
    assert meta.tags == ["a", "b"]
    assert meta.draft is True
    assert meta.slug == "x"
    assert body.strip() == "Body"


def test_no_front_matter():
    meta, body = parse("Just text\n")
    assert meta.title == "" and meta.date is None
    assert body == "Just text\n"


def test_quoted_values_and_colon_in_title():
    meta, _ = parse('---\ntitle: "Rust: a tour"\n---\n')
    assert meta.title == "Rust: a tour"


def test_single_quotes():
    meta, _ = parse("---\ntitle: 'Hello'\n---\n")
    assert meta.title == "Hello"


def test_tags_without_brackets_and_quotes():
    meta, _ = parse("---\ntags: \"x\", 'y' , z\n---\n")
    assert meta.tags == ["x", "y", "z"]


def test_tags_empty_and_duplicates():
    assert parse("---\ntags: []\n---\n")[0].tags == []
    assert parse("---\ntags: [a, a, b]\n---\n")[0].tags == ["a", "b"]


def test_unbalanced_tags():
    with pytest.raises(FrontMatterError):
        parse("---\ntags: [a, b\n---\n")


def test_unclosed_front_matter():
    with pytest.raises(FrontMatterError):
        parse("---\ntitle: x\nno end")


def test_line_without_colon():
    with pytest.raises(FrontMatterError):
        parse("---\njust words\n---\n")


def test_bad_date():
    with pytest.raises(FrontMatterError):
        parse("---\ndate: 2026-13-45\n---\n")


def test_datetime_with_timezone_converted_to_utc():
    meta, _ = parse("---\ndate: 2026-05-01T23:30:00+02:00\n---\n")
    assert meta.date.hour == 21


def test_bad_draft_value():
    with pytest.raises(FrontMatterError):
        parse("---\ndraft: maybe\n---\n")


def test_draft_false_and_yes():
    assert parse("---\ndraft: false\n---\n")[0].draft is False
    assert parse("---\ndraft: yes\n---\n")[0].draft is True


def test_comments_blank_lines_and_extra_keys():
    meta, _ = parse("---\n# note\n\nauthor: Sam\n---\n")
    assert meta.extra == {"author": "Sam"}


def test_crlf_line_endings():
    meta, body = parse("---\r\ntitle: Win\r\n---\r\nText\r\n")
    assert meta.title == "Win" and body.strip() == "Text"


def test_bom_is_ignored():
    meta, _ = parse("﻿---\ntitle: B\n---\n")
    assert meta.title == "B"


def test_horizontal_rule_in_body_not_confused():
    meta, body = parse("---\ntitle: T\n---\nA\n\n---\n\nB")
    assert "---" in body and meta.title == "T"


@pytest.mark.parametrize("raw,expected", [
    ("Hello, World!", "hello-world"),
    ("  spaced   out  ", "spaced-out"),
    ("Café Münch", "cafe-munch"),
    ("../../etc/passwd", "etc-passwd"),
    ("a/b\\c", "a-b-c"),
    ("..", "post"),
    ("", "post"),
    ("日本語", "post"),
])
def test_slugify(raw, expected):
    assert slugify(raw) == expected
