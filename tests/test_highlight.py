import pytest

from sitegen import render
from sitegen.builder import BuildError, build, load_config
from sitegen.cli import main

pytest.importorskip("pygments")

CODE = '```python\nx = 1  # one\n```\n'


def post(folder, name, title, body):
    (folder / name).write_text(
        f"---\ntitle: {title}\ndate: 2026-01-01\ntags: [t]\n---\n{body}", encoding="utf-8")


def config(folder, text):
    (folder / "sitegen.toml").write_text(text, encoding="utf-8")


def read(path):
    return path.read_text(encoding="utf-8")


def test_code_blocks_are_tokenized_by_pygments(tmp_path):
    post(tmp_path, "a.md", "Code", CODE)
    page = read(build(tmp_path) / "posts" / "code" / "index.html")
    assert '<div class="codehilite">' in page
    assert '<span class="n">x</span> <span class="o">=</span> <span class="mi">1</span>' in page
    assert '<span class="c1"># one</span>' in page


def test_block_without_language_is_not_guessed(tmp_path):
    post(tmp_path, "a.md", "Plain", "```\nimport os <b>\n```\n")
    page = read(build(tmp_path) / "posts" / "plain" / "index.html")
    assert "<code>import os &lt;b&gt;\n</code>" in page  # escaped, no token spans
    assert '<span class="kn">' not in page


def test_unknown_language_falls_back_to_plain_text(tmp_path):
    post(tmp_path, "a.md", "Odd", "```nosuchlang\nfoo(bar)\n```\n")
    page = read(build(tmp_path) / "posts" / "odd" / "index.html")
    assert '<div class="codehilite">' in page and "foo(bar)" in page


def test_style_css_only_on_pages_with_code(tmp_path):
    post(tmp_path, "a.md", "Code", CODE)
    post(tmp_path, "b.md", "Prose", "No code here.")
    out = build(tmp_path)
    assert ".codehilite .c1" in read(out / "posts" / "code" / "index.html")
    assert ".codehilite" not in read(out / "posts" / "prose" / "index.html")
    assert ".codehilite" not in read(out / "index.html")


def test_theme_picks_default_style_and_config_overrides_it(tmp_path):
    post(tmp_path, "a.md", "Code", CODE)
    page = tmp_path / "public" / "posts" / "code" / "index.html"
    build(tmp_path)
    assert render.highlight_css("default") in read(page)
    config(tmp_path, 'theme = "dark"\n')
    build(tmp_path)
    assert render.highlight_css("monokai") in read(page)
    config(tmp_path, 'theme = "dark"\nhighlight_style = "nord"\n')
    build(tmp_path)
    assert render.highlight_css("nord") in read(page)
    assert render.highlight_css("monokai") not in read(page)


def test_pages_are_highlighted_too(tmp_path):
    (tmp_path / "pages").mkdir()
    (tmp_path / "pages" / "usage.md").write_text("---\ntitle: Usage\n---\n" + CODE,
                                                  encoding="utf-8")
    page = read(build(tmp_path) / "usage" / "index.html")
    assert '<span class="mi">1</span>' in page and ".codehilite .mi" in page


def test_highlight_false_keeps_plain_code(tmp_path):
    config(tmp_path, "highlight = false\nhighlight_style = \"nord\"\n")
    post(tmp_path, "a.md", "Code", CODE)
    page = read(build(tmp_path) / "posts" / "code" / "index.html")
    assert '<pre><code class="language-python">x = 1  # one' in page
    assert "codehilite" not in page


def test_unknown_style_suggests_close_match(tmp_path):
    config(tmp_path, 'title = "x"\nhighlight_style = "monokia"\n')
    with pytest.raises(BuildError) as e:
        load_config(tmp_path)
    assert str(e.value).startswith(
        "sitegen.toml:2: unknown Pygments style 'monokia'; did you mean 'monokai'?")
    assert '     2 | highlight_style = "monokia"' in str(e.value)


def test_unknown_style_without_close_match_points_at_pygmentize(tmp_path):
    config(tmp_path, 'highlight_style = "zzzzqqqq"\n')
    with pytest.raises(BuildError, match="pygmentize -L styles"):
        load_config(tmp_path)


@pytest.mark.parametrize("line, message", [
    ('highlight = "yes"', "highlight must be true or false, got 'yes'"),
    ("highlight_style = 3", "highlight_style must be a Pygments style name, got 3"),
    ('highlight_style = ""', "highlight_style must be a Pygments style name, got ''"),
])
def test_bad_highlight_values(tmp_path, line, message):
    config(tmp_path, line + "\n")
    with pytest.raises(BuildError, match=f"^sitegen.toml:1: {message}"):
        load_config(tmp_path)


def test_without_pygments_build_degrades_to_plain_code(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(render, "HAVE_PYGMENTS", False)
    config(tmp_path, 'highlight_style = "not-checked-without-pygments"\n')
    post(tmp_path, "a.md", "Code", CODE)
    assert main(["build", str(tmp_path)]) == 0
    page = read(tmp_path / "public" / "posts" / "code" / "index.html")
    assert '<pre><code class="language-python">' in page and "codehilite" not in page
    err = capsys.readouterr().err
    assert "Pygments is not installed" in err and 'pip install "sitegen[highlight]"' in err


def test_without_pygments_no_note_unless_a_style_was_asked_for(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(render, "HAVE_PYGMENTS", False)
    post(tmp_path, "a.md", "Code", CODE)
    assert main(["build", str(tmp_path)]) == 0
    assert capsys.readouterr().err == ""
