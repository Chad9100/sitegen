"""Reading time and post summaries."""
from __future__ import annotations

import html
import re

WORDS_PER_MINUTE = 200
SUMMARY_LIMIT = 200

# Block-level tags separate words; inline ones (<em>, <strong>, <a>, <code>)
# must vanish without a space, or "<strong>here</strong>." reads "here .".
_BLOCK_TAG = re.compile(
    r"</?(?:p|div|br|hr|li|ul|ol|h[1-6]|pre|blockquote|table|thead|tbody|tr|td|th)\b[^>]*>",
    re.IGNORECASE)
_TAG = re.compile(r"<[^>]+>")
_FIRST_PARA = re.compile(r"<p>(.*?)</p>", re.DOTALL)
# Hugo/Jekyll-style marker: everything above it is the post's excerpt.
MORE = re.compile(r"<!--\s*more\s*-->", re.IGNORECASE)


def plain_text(body_html: str) -> str:
    """Visible text of rendered HTML, with whitespace collapsed."""
    spaced = _BLOCK_TAG.sub(" ", body_html)
    return " ".join(html.unescape(_TAG.sub("", spaced)).split())


def reading_minutes(body_html: str, wpm: int = WORDS_PER_MINUTE) -> int:
    """Estimated minutes to read, rounded, never less than 1."""
    words = len(plain_text(body_html).split())
    return max(1, round(words / wpm))


def truncate(text: str, limit: int = SUMMARY_LIMIT) -> str:
    """Cut at the last word boundary before `limit`, adding an ellipsis."""
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0] if " " in text[:limit] else text[:limit]
    return cut.rstrip(" ,.;:") + "…"


def summarize(body_html: str, before_more_html: str | None = None,
              override: str | None = None) -> str:
    """Pick a post's summary as plain text.

    Order: an explicit `summary:` from front matter, then the part above a
    `<!--more-->` marker (kept whole: the author chose it), then the first
    paragraph, then the start of the body, both truncated.
    """
    if override and override.strip():
        return " ".join(override.split())
    if before_more_html is not None:
        text = plain_text(before_more_html)
        if text:
            return text
    para = _FIRST_PARA.search(body_html)
    text = plain_text(para.group(1)) if para else ""
    return truncate(text or plain_text(body_html))
