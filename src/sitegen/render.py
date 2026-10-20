"""Markdown rendering and simple ``{{ var }}`` templating."""
from __future__ import annotations

import re

import markdown

_VAR = re.compile(r"\{\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}\}")


def render_markdown(text: str) -> str:
    return markdown.markdown(text, extensions=["fenced_code", "tables"])


def fill(template: str, values: dict[str, str]) -> str:
    """Single-pass substitution; unknown variables become empty.

    Values are inserted verbatim (callers escape them) and are never
    re-scanned, so substituted content cannot inject further variables.
    """
    return _VAR.sub(lambda m: str(values.get(m.group(1), "")), template)
