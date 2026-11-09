"""Rebuild-on-change for `sitegen serve`: poll the site folder's files.

Polling (rather than OS file events) keeps sitegen dependency-free and behaves
the same on Windows, macOS and Linux. A snapshot is a map of every watched file
to its (mtime, size); comparing two snapshots tells us what changed.
"""
from __future__ import annotations

import os
import threading
import time
from pathlib import Path
from typing import Callable

from .builder import BuildError

# public/ is the build output: watching it would rebuild forever.
IGNORED_DIRS = {"public", "node_modules", "__pycache__"}

Snapshot = dict[str, tuple[int, int]]


def snapshot(folder: Path) -> Snapshot:
    """Every file that can affect the build: posts, sitegen.toml, templates, static."""
    snap: Snapshot = {}
    for dirpath, dirnames, filenames in os.walk(folder):
        # Prune in place so os.walk never descends into ignored folders.
        dirnames[:] = sorted(d for d in dirnames
                             if d not in IGNORED_DIRS and not d.startswith("."))
        for name in filenames:
            if name.startswith(".") or name.endswith(("~", ".swp", ".tmp")):
                continue  # editor backup and swap files
            p = Path(dirpath) / name
            try:
                st = p.stat()
            except OSError:
                continue  # deleted between listing and stat
            snap[p.relative_to(folder).as_posix()] = (st.st_mtime_ns, st.st_size)
    return snap


def diff(old: Snapshot, new: Snapshot) -> list[str]:
    """Relative paths added, removed or modified between two snapshots, sorted."""
    return sorted(k for k in old.keys() | new.keys() if old.get(k) != new.get(k))


def describe(changed: list[str], limit: int = 3) -> str:
    shown = ", ".join(changed[:limit])
    more = len(changed) - limit
    return shown + (f" and {more} more" if more > 0 else "")


class Watcher:
    """Rebuild the site when its sources change; never stop on a build error.

    A failed build is reported and the last good `public/` keeps being served,
    because sitegen loads and checks every post before it touches `public/`.
    """

    def __init__(self, folder: Path, rebuild: Callable[[], object],
                 interval: float = 0.5, log: Callable[[str], None] = print):
        self.folder = Path(folder)
        self.rebuild = rebuild
        self.interval = interval
        self.log = log
        self.last = snapshot(self.folder)
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def check(self) -> bool | None:
        """Poll once. None if nothing changed, else whether the rebuild succeeded."""
        current = snapshot(self.folder)
        changed = diff(self.last, current)
        if not changed:
            return None
        # Remember this state even if the build fails, so a broken post is
        # reported once rather than on every poll until it is fixed.
        self.last = current
        start = time.perf_counter()
        try:
            self.rebuild()
        except BuildError as e:
            self.log(f"Build failed after change to {describe(changed)}: {e}\n"
                     "  (still serving the last good build)")
            return False
        except OSError as e:
            # e.g. Windows refusing to delete a file in public/ that the server
            # has open at that moment. Keep watching; the next save retries.
            self.log(f"Build failed after change to {describe(changed)}: {e}\n"
                     "  (save again to retry)")
            return False
        self.log(f"Rebuilt in {time.perf_counter() - start:.2f}s "
                 f"({len(changed)} changed: {describe(changed)})")
        return True

    def run(self) -> None:
        while not self._stop.wait(self.interval):
            self.check()

    def start(self) -> None:
        self._thread = threading.Thread(target=self.run, name="sitegen-watch", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join()
