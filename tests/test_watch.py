import os
import threading

import pytest

from sitegen.builder import build
from sitegen.cli import make_parser
from sitegen.watch import Watcher, describe, diff, snapshot

POST = "---\ntitle: {title}\ndate: 2026-01-01\n---\nHello\n"


@pytest.fixture
def site(tmp_path):
    (tmp_path / "sitegen.toml").write_text('title = "Watched"\n', encoding="utf-8")
    (tmp_path / "posts").mkdir()
    (tmp_path / "posts" / "a.md").write_text(POST.format(title="First"), encoding="utf-8")
    build(tmp_path)
    return tmp_path


def touch_later(path, text):
    """Rewrite a file and push its mtime forward, so coarse clocks can't hide the edit."""
    path.write_text(text, encoding="utf-8")
    st = path.stat()
    os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns + 2_000_000_000))


def make(site, **kw):
    log = []
    w = Watcher(site, lambda: build(site), log=log.append, **kw)
    return w, log


def index(site):
    return (site / "public" / "index.html").read_text(encoding="utf-8")


def test_snapshot_covers_sources_and_skips_output_and_hidden(site):
    (site / "templates").mkdir()
    (site / "templates" / "base.html").write_text("x", encoding="utf-8")
    (site / "static").mkdir()
    (site / "static" / "logo.svg").write_text("<svg/>", encoding="utf-8")
    (site / ".git").mkdir()
    (site / ".git" / "HEAD").write_text("ref", encoding="utf-8")
    (site / "posts" / "a.md~").write_text("backup", encoding="utf-8")
    keys = set(snapshot(site))
    assert {"sitegen.toml", "posts/a.md", "templates/base.html", "static/logo.svg"} <= keys
    assert not any(k.startswith(("public/", ".git/")) for k in keys)
    assert "posts/a.md~" not in keys


def test_diff_reports_added_removed_and_modified():
    old = {"a.md": (1, 10), "b.md": (1, 10), "c.md": (1, 10)}
    new = {"a.md": (1, 10), "b.md": (2, 11), "d.md": (1, 1)}
    assert diff(old, new) == ["b.md", "c.md", "d.md"]
    assert diff(old, dict(old)) == []


def test_describe_truncates_long_lists():
    assert describe(["a"]) == "a"
    assert describe(["a", "b", "c", "d", "e"]) == "a, b, c and 2 more"


def test_no_change_means_no_rebuild(site):
    calls = []
    w = Watcher(site, lambda: calls.append(1), log=lambda m: None)
    assert w.check() is None
    assert calls == []


def test_editing_a_post_rebuilds(site):
    w, log = make(site)
    touch_later(site / "posts" / "a.md", POST.format(title="Renamed"))
    assert w.check() is True
    assert "Renamed" in index(site)
    assert "posts/a.md" in log[-1] and log[-1].startswith("Rebuilt in")
    assert w.check() is None  # settled: nothing more to do


def test_new_post_and_config_change_rebuild(site):
    w, log = make(site)
    (site / "posts" / "b.md").write_text(POST.format(title="Second"), encoding="utf-8")
    touch_later(site / "sitegen.toml", 'title = "Retitled"\n')
    assert w.check() is True
    html = index(site)
    assert "Second" in html and "Retitled" in html
    assert "2 changed" in log[-1]


def test_deleting_a_post_rebuilds(site):
    (site / "posts" / "b.md").write_text(POST.format(title="Doomed"), encoding="utf-8")
    build(site)
    w, _ = make(site)
    (site / "posts" / "b.md").unlink()
    assert w.check() is True
    assert "Doomed" not in index(site)


def test_build_output_does_not_trigger_rebuilds(site):
    w, _ = make(site)
    touch_later(site / "posts" / "a.md", POST.format(title="Again"))
    assert w.check() is True
    # The rebuild rewrote public/; that must not count as a change.
    assert w.check() is None


def test_broken_post_keeps_last_good_build_and_recovers(site):
    w, log = make(site)
    good = index(site)
    touch_later(site / "posts" / "a.md", "---\ntitle: No date\n---\nOops\n")
    assert w.check() is False
    assert "a.md" in log[-1] and "missing 'date'" in log[-1]
    assert "still serving the last good build" in log[-1]
    assert index(site) == good  # public/ untouched
    assert w.check() is None  # the same error isn't reported on every poll

    touch_later(site / "posts" / "a.md", POST.format(title="Fixed"))
    assert w.check() is True
    assert "Fixed" in index(site)


def test_background_thread_rebuilds_and_stops(site):
    rebuilt = threading.Event()
    w = Watcher(site, lambda: (build(site), rebuilt.set()), interval=0.05,
                log=lambda m: None)
    w.start()
    try:
        touch_later(site / "posts" / "a.md", POST.format(title="Threaded"))
        assert rebuilt.wait(5)
    finally:
        w.stop()
    assert "Threaded" in index(site)
    assert not w._thread.is_alive()


def test_serve_watches_by_default_with_opt_out():
    p = make_parser()
    args = p.parse_args(["serve", "site"])
    assert args.watch is True and args.interval == 0.5
    args = p.parse_args(["serve", "site", "--no-watch", "--interval", "2"])
    assert args.watch is False and args.interval == 2.0


@pytest.mark.parametrize("bad", ["0", "-1", "soon"])
def test_interval_must_be_positive_number(bad, capsys):
    with pytest.raises(SystemExit):
        make_parser().parse_args(["serve", "--interval", bad])
    assert "--interval" in capsys.readouterr().err


def test_build_has_no_watch_flag():
    with pytest.raises(SystemExit):
        make_parser().parse_args(["build", "--no-watch"])
