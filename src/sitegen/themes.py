"""Built-in themes and local template overrides."""
from __future__ import annotations

from importlib import resources
from pathlib import Path

THEMES = ("light", "dark")
TEMPLATE_NAMES = ("base", "list", "post")


def _builtin(name: str) -> str:
    return resources.files("sitegen").joinpath("themes", name).read_text(encoding="utf-8")


def load_templates(theme: str, override_dir: Path | None = None) -> dict[str, str]:
    if theme not in THEMES:
        raise ValueError(f"unknown theme {theme!r}; choose one of: {', '.join(THEMES)}")
    out = {name: _builtin(f"{name}.html") for name in TEMPLATE_NAMES}
    out["css"] = _builtin(f"{theme}.css")
    if override_dir is not None and override_dir.is_dir():
        for name in TEMPLATE_NAMES:
            f = override_dir / f"{name}.html"
            if f.is_file() and not f.is_symlink():
                out[name] = f.read_text(encoding="utf-8")
    return out
