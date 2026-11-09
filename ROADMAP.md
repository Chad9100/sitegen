# Roadmap

## v0.1 (done)

- [x] Hand-parsed front matter (title, date, tags, draft, slug)
- [x] Markdown with fenced code and tables
- [x] Index with pagination, post pages, tag pages
- [x] Atom feed and sitemap
- [x] Light and dark themes, local template overrides
- [x] `init`, `build`, `serve`
- [x] Slug sanitizing and path-traversal safety

## v0.2: Authoring comfort (about 6 hours)

- [x] `sitegen new "Title"` to create a dated post stub (1h)
- [ ] Rebuild-on-change for `serve` (2h)
- [ ] Reading time and post summaries/excerpts (1h)
- [ ] Friendlier error messages with line numbers (2h)

## v0.3: Content features (about 8 hours)

- [ ] Standalone pages (About, Contact) outside the post list (2h)
- [ ] Tag index page listing all tags with counts (1h)
- [ ] Per-tag Atom feeds (2h)
- [ ] Syntax highlighting via Pygments as an optional extra (3h)

## v0.4: Templates and themes (about 8 hours)

- [ ] Partials/includes in custom templates (3h)
- [ ] Third built-in theme and a theme preview guide (2h)
- [ ] Open Graph and meta description tags (3h)

## v0.5: Performance and robustness (about 6 hours)

- [ ] Incremental builds (4h)
- [ ] Image copy checks and asset fingerprinting (2h)

## v1.0: Stable release (about 8 hours)

- [ ] Freeze config and front matter formats, document the template variables (2h)
- [ ] Publish to PyPI (2h)
- [ ] Deploy guide for GitHub Pages and static hosts (2h)
- [ ] Broader test matrix and release checklist (2h)
