"""Error messages point at the file and line that caused them."""
import pytest

from sitegen.builder import BuildError, build, located
from sitegen.cli import main
from sitegen.frontmatter import FrontMatterError, parse


def error_of(folder) -> str:
    with pytest.raises(BuildError) as info:
        build(folder)
    return str(info.value)


def test_located_formats_file_line_and_excerpt():
    assert located("a.md", "boom") == "a.md: boom"
    assert located("a.md", "boom", 3) == "a.md:3: boom"
    assert located("a.md", "boom", 3, "date: x   ") == "a.md:3: boom\n     3 | date: x"


@pytest.mark.parametrize("text, line, excerpt", [
    ("---\ntitle: X\ndate: 2026-13-45\n---\n", 3, "date: 2026-13-45"),
    ("---\n\n# comment\ndraft: maybe\n---\n", 4, "draft: maybe"),
    ("---\ntitle: X\ntags: [a, b\n---\n", 3, "tags: [a, b"),
    ("---\ntitle: X\n  just words\n---\n", 3, "  just words"),
    ("﻿---\r\ntitle: X\r\ndate: nope\r\n---\r\n", 3, "date: nope"),
])
def test_parse_errors_carry_line_and_text(text, line, excerpt):
    with pytest.raises(FrontMatterError) as info:
        parse(text)
    assert info.value.line == line
    assert info.value.text == excerpt


def test_unclosed_front_matter_points_at_opening_line():
    with pytest.raises(FrontMatterError) as info:
        parse("---\ntitle: x\nno end")
    assert info.value.line == 1
    assert "never closed" in str(info.value)


def test_message_stays_plain_for_other_callers():
    with pytest.raises(FrontMatterError) as info:
        parse("---\ndate: 3 May 2026\n---\n")
    assert str(info.value) == "invalid date: '3 May 2026' (use YYYY-MM-DD)"


def test_impossible_day_says_why_instead_of_repeating_format():
    with pytest.raises(FrontMatterError) as info:
        parse("---\ndate: 2026-02-30\n---\n")
    msg = str(info.value)
    assert msg.startswith("invalid date: '2026-02-30' (")
    assert "YYYY-MM-DD" not in msg and "day" in msg


def test_meta_records_field_lines():
    meta, _ = parse("---\ntitle: X\n\ndate: 2026-01-01\nauthor: Sam\n---\n")
    assert meta.lines == {"title": 2, "date": 4, "author": 5}


def test_build_error_uses_relative_path_and_line(tmp_path):
    (tmp_path / "posts" / "2026").mkdir(parents=True)
    (tmp_path / "posts" / "2026" / "bad.md").write_text(
        "---\ntitle: Bad\ndate: 2026-02-30\n---\nbody", encoding="utf-8")
    msg = error_of(tmp_path)
    assert msg.startswith("posts/2026/bad.md:3: invalid date")
    assert msg.endswith("\n     3 | date: 2026-02-30")


def test_missing_date_suggests_typo_with_line(tmp_path):
    (tmp_path / "a.md").write_text("---\ntitle: X\ndat: 2026-01-01\n---\n", encoding="utf-8")
    assert error_of(tmp_path) == ("a.md:3: missing 'date' in front matter; "
                                  "did you mean 'date' instead of 'dat'?")


def test_missing_date_without_typo_gives_example(tmp_path):
    (tmp_path / "a.md").write_text("---\ntitle: X\nauthor: Sam\n---\n", encoding="utf-8")
    msg = error_of(tmp_path)
    assert msg.startswith("a.md: missing 'date'")
    assert "date: 2026-01-10" in msg


def test_invalid_utf8_reports_line_and_column(tmp_path):
    (tmp_path / "a.md").write_bytes(b"---\ntitle: X\ndate: 2026-01-01\n---\ncaf\xe9 au lait\n")
    assert error_of(tmp_path) == ("a.md:5: not valid UTF-8 (byte 0xe9 at column 4); "
                                  "re-save the file as UTF-8")


def test_toml_syntax_error_shows_line(tmp_path):
    (tmp_path / "sitegen.toml").write_text('title = "Blog"\ntheme = dark\n', encoding="utf-8")
    msg = error_of(tmp_path)
    assert msg.startswith("sitegen.toml:2: invalid TOML:")
    assert msg.endswith("\n     2 | theme = dark")


def test_bad_config_value_points_at_its_line(tmp_path):
    (tmp_path / "sitegen.toml").write_text(
        'title = "Blog"\n\n  theme = "neon"\n', encoding="utf-8")
    msg = error_of(tmp_path)
    assert msg.startswith("sitegen.toml:3: unknown theme 'neon'")
    assert msg.endswith('     3 |   theme = "neon"')


def test_bad_posts_per_page_points_at_its_line(tmp_path):
    (tmp_path / "sitegen.toml").write_text("posts_per_page = 0\n", encoding="utf-8")
    assert error_of(tmp_path) == ("sitegen.toml:1: posts_per_page must be a positive "
                                  "integer, got 0\n     1 | posts_per_page = 0")


def test_cli_prints_located_error(tmp_path, capsys):
    (tmp_path / "a.md").write_text("---\ntitle: X\ndraft: maybe\n---\n", encoding="utf-8")
    assert main(["build", str(tmp_path)]) == 1
    err = capsys.readouterr().err
    assert err == ("error: a.md:3: invalid boolean for draft: 'maybe'\n"
                   "     3 | draft: maybe\n")
