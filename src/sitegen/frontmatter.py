"""Hand-rolled front matter parser (simple ``key: value`` lines)."""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime, timezone


class FrontMatterError(ValueError):
    """Raised when front matter is malformed."""


@dataclass
class Meta:
    title: str = ""
    date: datetime | None = None
    tags: list[str] = field(default_factory=list)
    draft: bool = False
    slug: str = ""
    extra: dict[str, str] = field(default_factory=dict)


def slugify(text: str, fallback: str = "post") -> str:
    """Turn arbitrary text into a safe single path segment [a-z0-9-]."""
    norm = unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", norm.lower()).strip("-")
    return slug or fallback


def _unquote(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def parse_tags(value: str) -> list[str]:
    value = value.strip()
    if value.startswith("[") and value.endswith("]"):
        value = value[1:-1]
    elif value.startswith("[") or value.endswith("]"):
        raise FrontMatterError(f"unbalanced brackets in tags: {value!r}")
    tags: list[str] = []
    for part in value.split(","):
        tag = _unquote(part)
        if tag and tag not in tags:
            tags.append(tag)
    return tags


def parse_bool(value: str) -> bool:
    v = _unquote(value).lower()
    if v in ("true", "yes", "on", "1"):
        return True
    if v in ("false", "no", "off", "0", ""):
        return False
    raise FrontMatterError(f"invalid boolean for draft: {value!r}")


def parse_date(value: str) -> datetime:
    v = _unquote(value)
    try:
        if len(v) == 10:
            d = date.fromisoformat(v)
            return datetime(d.year, d.month, d.day, tzinfo=timezone.utc)
        dt = datetime.fromisoformat(v.replace("Z", "+00:00"))
    except ValueError:
        raise FrontMatterError(f"invalid date: {value!r} (use YYYY-MM-DD)") from None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def split_front_matter(text: str) -> tuple[str, str]:
    """Return (front_matter_block, body). Block is '' when absent."""
    text = text.lstrip("﻿").replace("\r\n", "\n").replace("\r", "\n")
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        return "", text
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            return "\n".join(lines[1:i]), "\n".join(lines[i + 1:])
    raise FrontMatterError("front matter is not closed with '---'")


def parse(text: str) -> tuple[Meta, str]:
    block, body = split_front_matter(text)
    meta = Meta()
    for raw in block.split("\n"):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            raise FrontMatterError(f"expected 'key: value', got {line!r}")
        key, _, value = line.partition(":")
        key = key.strip().lower()
        if key == "title":
            meta.title = _unquote(value)
        elif key == "date":
            meta.date = parse_date(value)
        elif key == "tags":
            meta.tags = parse_tags(value)
        elif key == "draft":
            meta.draft = parse_bool(value)
        elif key == "slug":
            meta.slug = _unquote(value)
        else:
            meta.extra[key] = _unquote(value)
    return meta, body
