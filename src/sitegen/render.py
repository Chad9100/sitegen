"""Markdown rendering and simple ``{{ var }}`` templating."""
from __future__ import annotations

import re

import markdown

try:  # optional extra: pip install "sitegen[highlight]"
    import pygments  # noqa: F401
    HAVE_PYGMENTS = True
except ImportError:  # pragma: no cover - depends on the environment
    HAVE_PYGMENTS = False

_VAR = re.compile(r"\{\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}\}")

# CSS class of the <div> Pygments wraps around each highlighted code block.
HIGHLIGHT_CLASS = "codehilite"
# Pygments style used for each built-in theme unless `highlight_style` is set.
DEFAULT_STYLES = {"light": "default", "dark": "monokai"}


def render_markdown(text: str, highlight: bool = False) -> str:
    """Render Markdown; with ``highlight`` (needs Pygments) code blocks are
    tokenized into ``<span>`` elements styled by :func:`highlight_css`."""
    if not highlight:
        return markdown.markdown(text, extensions=["fenced_code", "tables"])
    return markdown.markdown(
        text, extensions=["fenced_code", "tables", "codehilite"],
        extension_configs={"codehilite": {
            # Never guess: a block without a language stays plain text.
            "guess_lang": False, "css_class": HIGHLIGHT_CLASS}})


def highlight_styles() -> list[str]:
    from pygments.styles import get_all_styles
    return sorted(get_all_styles())


def highlight_css(style: str) -> str:
    """Stylesheet for highlighted code blocks in the given Pygments style."""
    from pygments.formatters import HtmlFormatter
    css = HtmlFormatter(style=style).get_style_defs(f".{HIGHLIGHT_CLASS}")
    # Let the style's background show through the theme's own <pre> colour.
    return css + f"\n.{HIGHLIGHT_CLASS} pre{{background:transparent}}\n"


def fill(template: str, values: dict[str, str]) -> str:
    """Single-pass substitution; unknown variables become empty.

    Values are inserted verbatim (callers escape them) and are never
    re-scanned, so substituted content cannot inject further variables.
    """
    return _VAR.sub(lambda m: str(values.get(m.group(1), "")), template)
