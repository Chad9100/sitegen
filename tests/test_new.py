from datetime import date
from pathlib import Path

import pytest

from sitegen import frontmatter
from sitegen.builder import build
from sitegen.cli import main


def posts_in(folder: Path) -> list[str]:
    return sorted(p.name for p in (folder / "posts").glob("*.md"))


def test_creates_a_dated_draft_stub(tmp_path, capsys):
    assert main(["new", "Notes on sourdough", "-C", str(tmp_path), "--date", "2026-11-09"]) == 0
    assert posts_in(tmp_path) == ["2026-11-09-notes-on-sourdough.md"]

    meta, body = frontmatter.parse((tmp_path / "posts" / posts_in(tmp_path)[0]).read_text("utf-8"))
    assert meta.title == "Notes on sourdough"
    assert meta.date.date() == date(2026, 11, 9)
    assert meta.draft is True
    assert meta.tags == []
    assert "Write your post here." in body
    assert "--drafts" in capsys.readouterr().out


def test_defaults_to_today(tmp_path):
    assert main(["new", "Today", "-C", str(tmp_path)]) == 0
    assert posts_in(tmp_path) == [f"{date.today().isoformat()}-today.md"]


def test_tags_and_no_draft(tmp_path):
    assert main(["new", "Garden update", "-C", str(tmp_path), "--date", "2026-11-09",
                 "--tags", "garden, notes", "--no-draft"]) == 0
    meta, _ = frontmatter.parse((tmp_path / "posts" / "2026-11-09-garden-update.md")
                                .read_text("utf-8"))
    assert meta.tags == ["garden", "notes"]
    assert meta.draft is False


@pytest.mark.parametrize("title", [
    "Re: why colons: matter",
    "Tips #1 and #2",
    'She said "hello"',
    "  extra   spaces\nand a newline  ",
])
def test_awkward_titles_round_trip(tmp_path, title):
    assert main(["new", title, "-C", str(tmp_path), "--date", "2026-11-09"]) == 0
    [name] = posts_in(tmp_path)
    meta, _ = frontmatter.parse((tmp_path / "posts" / name).read_text("utf-8"))
    assert meta.title == " ".join(title.split())


def test_never_overwrites(tmp_path, capsys):
    args = ["new", "Same title", "-C", str(tmp_path), "--date", "2026-11-09"]
    assert main(args) == 0
    target = tmp_path / "posts" / "2026-11-09-same-title.md"
    target.write_text("my real writing", encoding="utf-8")
    assert main(args) == 1
    assert target.read_text("utf-8") == "my real writing"
    assert "already exists" in capsys.readouterr().err


@pytest.mark.parametrize("extra, message", [
    (["--date", "2026-13-40"], "error:"),
    (["--tags", "[unbalanced"], "unbalanced"),
])
def test_bad_input_is_rejected(tmp_path, capsys, extra, message):
    assert main(["new", "Title", "-C", str(tmp_path), *extra]) == 1
    assert message in capsys.readouterr().err
    assert not (tmp_path / "posts").exists()


def test_empty_title_and_missing_folder(tmp_path, capsys):
    assert main(["new", "   ", "-C", str(tmp_path)]) == 1
    assert main(["new", "Title", "-C", str(tmp_path / "nope")]) == 1
    err = capsys.readouterr().err
    assert "empty" in err and "no such folder" in err


def test_stub_builds_only_with_drafts_until_published(tmp_path):
    assert main(["init", str(tmp_path)]) == 0
    assert main(["new", "Fresh post", "-C", str(tmp_path), "--date", "2026-11-09"]) == 0

    out = build(tmp_path)
    assert not (out / "posts" / "fresh-post").exists()

    out = build(tmp_path, drafts=True)
    assert (out / "posts" / "fresh-post" / "index.html").exists()
