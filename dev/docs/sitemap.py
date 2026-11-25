"""Write the canonical deployment sitemap for documentation builds."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from cadrumo.core.directory_scan import scan_directory

_UTF_8 = "utf-8"

_SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"

#: Top-level built pages that carry no canonical human content (Sphinx
#: builder-owned orphans); excluded from the deployment sitemap.
_SITEMAP_EXCLUDED_PAGES = frozenset({"search.html", "genindex.html", "py-modindex.html", "404.html"})

#: Top-level directories of generated / infrastructure surfaces that never
#: belong in the human sitemap (API autodoc, viewcode, assets, sources).
_SITEMAP_EXCLUDED_ROOTS = frozenset({"api", "_modules", "_static", "_sources"})


def _sitemap_page_url(base_url: str, rel_posix: str) -> str:
    """Map a built page's relative path to its canonical deployment URL.

    ``index.html`` pages canonicalise to their directory root (the site root
    for the top-level index), matching how the served site addresses them; any
    other page keeps its ``.html`` path.
    """
    if rel_posix == "index.html":
        suffix = ""
    elif rel_posix.endswith("/index.html"):
        suffix = rel_posix[: -len("index.html")]
    else:
        suffix = rel_posix
    return f"{base_url}/{suffix}"


def _sitemap_urls(html_root: Path, base_url: str) -> list[str]:
    """Return the deterministic canonical human-page URL set for the sitemap."""
    urls: set[str] = set()
    for page in scan_directory(html_root, pattern="*.html", recursive=True):
        rel = page.relative_to(html_root)
        parts = rel.parts
        if parts[0] in _SITEMAP_EXCLUDED_ROOTS:
            continue
        if len(parts) == 1 and rel.name in _SITEMAP_EXCLUDED_PAGES:
            continue
        urls.add(_sitemap_page_url(base_url, rel.as_posix()))
    return sorted(urls)


def write_deployment_sitemap(html_root: Path, base_url: str) -> Path:
    """Write a deterministic, canonical-human-page ``sitemap.xml`` for deployment.

    Walks the built HTML tree, filters to canonical human pages (excluding the
    generated ``api``/``_modules`` trees, the ``_static``/``_sources`` asset
    roots, and the builder-owned ``search``/``genindex``/``py-modindex``/``404``
    orphans), canonicalises ``index.html`` pages to their directory roots,
    sorts the URLs lexicographically, and emits the sitemaps.org urlset with no
    ``lastmod`` stamps. Stdlib-only and side-effect-deterministic so the deploy
    validator's exact canonical-root and canonical-prefix checks hold.

    Args:
        html_root: The built Sphinx HTML output directory.
        base_url: The canonical docs base URL (trailing slash tolerated).

    Returns:
        The path to the written ``sitemap.xml``.
    """
    base = base_url.rstrip("/")
    ET.register_namespace("", _SITEMAP_NS)
    urlset = ET.Element(f"{{{_SITEMAP_NS}}}urlset")
    for url in _sitemap_urls(html_root, base):
        entry = ET.SubElement(urlset, f"{{{_SITEMAP_NS}}}url")
        ET.SubElement(entry, f"{{{_SITEMAP_NS}}}loc").text = url
    tree = ET.ElementTree(urlset)
    ET.indent(tree)
    sitemap_path = html_root / "sitemap.xml"
    tree.write(sitemap_path, encoding=_UTF_8, xml_declaration=True)
    return sitemap_path
