"""Atom feed and sitemap generation."""
from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import datetime, timezone

ATOM = "http://www.w3.org/2005/Atom"
SITEMAP = "http://www.sitemaps.org/schemas/sitemap/0.9"


def _rfc3339(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _tostring(root: ET.Element) -> str:
    ET.indent(root)
    return '<?xml version="1.0" encoding="utf-8"?>\n' + ET.tostring(root, encoding="unicode") + "\n"


def build_atom(site_title: str, base_url: str, posts: list[dict], limit: int = 20) -> str:
    """posts: dicts with title, url (absolute), date, summary, tags (newest first)."""
    ET.register_namespace("", ATOM)
    feed = ET.Element(f"{{{ATOM}}}feed")
    ET.SubElement(feed, f"{{{ATOM}}}title").text = site_title
    ET.SubElement(feed, f"{{{ATOM}}}id").text = base_url + "/"
    ET.SubElement(feed, f"{{{ATOM}}}link", href=base_url + "/")
    ET.SubElement(feed, f"{{{ATOM}}}link", href=base_url + "/atom.xml", rel="self")
    latest = posts[0]["date"] if posts else datetime(1970, 1, 1, tzinfo=timezone.utc)
    ET.SubElement(feed, f"{{{ATOM}}}updated").text = _rfc3339(latest)
    for p in posts[:limit]:
        e = ET.SubElement(feed, f"{{{ATOM}}}entry")
        ET.SubElement(e, f"{{{ATOM}}}title").text = p["title"]
        ET.SubElement(e, f"{{{ATOM}}}id").text = p["url"]
        ET.SubElement(e, f"{{{ATOM}}}link", href=p["url"])
        ET.SubElement(e, f"{{{ATOM}}}updated").text = _rfc3339(p["date"])
        ET.SubElement(e, f"{{{ATOM}}}summary").text = p["summary"]
        for t in p["tags"]:
            ET.SubElement(e, f"{{{ATOM}}}category", term=t)
    return _tostring(feed)


def build_sitemap(entries: list[tuple[str, datetime | None]]) -> str:
    ET.register_namespace("", SITEMAP)
    root = ET.Element(f"{{{SITEMAP}}}urlset")
    for loc, lastmod in entries:
        u = ET.SubElement(root, f"{{{SITEMAP}}}url")
        ET.SubElement(u, f"{{{SITEMAP}}}loc").text = loc
        if lastmod:
            ET.SubElement(u, f"{{{SITEMAP}}}lastmod").text = lastmod.strftime("%Y-%m-%d")
    return _tostring(root)
