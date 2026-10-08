"""Admit complete canonical documentation roots and the site's record-bearing search index."""

from __future__ import annotations

from pathlib import Path

from defusedxml import ElementTree

from cadrumo.core.directory_scan import scan_directory
from dev._paths import UTF_8
from dev.docs import i18n as _docs_i18n

from .docs_delivery_contracts import _REQUIRED_ROOT_ARTIFACTS, _REQUIRED_SITE_SEARCH_ARTIFACTS
from .docs_site_languages import _language_site_url, localized_languages


def _require_sitemap_locations(locations: list[str], expected_base_url: str, root_label: str) -> None:
    """Require sitemap locations."""
    if not locations:
        raise SystemExit(f"{root_label} sitemap has no URLs.")
    canonical_root = f"{expected_base_url}/"
    if canonical_root not in locations:
        raise SystemExit(f"{root_label} sitemap is missing the canonical docs root: {canonical_root}")
    unexpected = [location for location in locations if not location.startswith(f"{expected_base_url}/")]
    if unexpected:
        raise SystemExit(f"{root_label} sitemap contains a non-canonical URL: " + unexpected[0])


def _validate_apex(html_root: Path) -> None:
    """Require the apex entry, its error page, a sitemap index and the one search bundle."""
    required = ("index.html", "404.html", "sitemap.xml", *_REQUIRED_SITE_SEARCH_ARTIFACTS)
    missing = [name for name in required if not (html_root / name).is_file()]
    if missing:
        raise SystemExit(f"The apex is not deployable; missing: {', '.join(missing)}")
    try:
        sitemap = ElementTree.parse(html_root / "sitemap.xml")
    except ElementTree.ParseError as exc:
        raise SystemExit("The apex sitemap index is not valid XML.") from exc
    listed = {(element.text or "").strip() for element in sitemap.iter() if element.tag.endswith("loc")}
    expected = {f"{_language_site_url(language)}/sitemap.xml" for language in localized_languages()}
    if listed != expected:
        raise SystemExit(f"The apex sitemap index lists {sorted(listed)}, not every language root's sitemap.")


def _require_artifacts_present(html_root: Path, *, root_label: str) -> None:
    """Require every artifact in :data:`_REQUIRED_ROOT_ARTIFACTS` at ``html_root``.

    Shared by every published root, English included: the same page, error page
    and sitemap are mandatory on each of them, because each root's pages are
    its own. The search bundle is the site's, not a root's, and is required at
    the apex by :func:`_validate_apex`.
    """
    missing = [artifact for artifact in _REQUIRED_ROOT_ARTIFACTS if not (html_root / artifact).is_file()]
    if missing:
        joined = ", ".join(missing)
        raise SystemExit(f"{root_label} is not deployable; required artifacts are missing: {joined}")


def _require_valid_sitemap(html_root: Path, *, expected_base_url: str, root_label: str) -> None:
    """Require a valid, canonically-rooted ``sitemap.xml`` at ``html_root``.

    ``expected_base_url`` is the root's OWN canonical URL (the English site's
    ``CANONICAL_DOCS_BASE_URL``, or a localized root's ``/<language>``
    sub-root via :func:`_language_site_url`) -- shared logic parameterized by
    the caller's expected root, since a localized root's sitemap is correctly
    rooted at its own language sub-path, not the English canonical root.
    """
    try:
        sitemap = ElementTree.parse(html_root / "sitemap.xml")
    except OSError as exc:
        raise SystemExit(
            f"{root_label} did not produce a sitemap at {html_root / 'sitemap.xml'}; "
            "set CADRUMO_DOCS_BASE_URL so the build writes one.",
        ) from exc
    except ElementTree.ParseError as exc:
        raise SystemExit(f"{root_label} sitemap is not valid XML.") from exc
    locations = [(element.text or "").strip() for element in sitemap.iter() if element.tag.endswith("loc")]
    _require_sitemap_locations(locations, expected_base_url, root_label)


def _require_search_index(site_root: Path, *, root_label: str) -> None:
    """Refuse a site whose Pagefind index is empty OR carries no records.

    Read once, at the apex: the site has ONE index and every language's pages
    load it, so one reading is the whole site's verdict rather than one root's.
    It was four readings while there were four indexes; the check itself did not
    change, only how many indexes there are to read.

    Two distinct failures, both fatal, checked in order. An index with no
    substantive chunks means the pass produced nothing. An index with chunks but
    no injected records is the shape that shipped for weeks: the deploy
    environment selected the pages-only contract, the build wrote 75 rendered
    pages and not one concept, casilla, or CLI record, and every check in front
    of it stayed green because a pages-only index is full of non-empty chunks.
    Non-emptiness cannot separate the two, so it is kept AND supplemented.

    The record read is :func:`~dev.docs.pagefind_index.injected_record_kinds_in_index`
    -- the same artefact scan the CI parity gate performs, in one place so the
    publish preflight and the gate cannot drift apart.
    """
    from dev.docs.pagefind_index import DECIDED_INJECTED_RECORD_KINDS, injected_record_kinds_in_index

    index_chunks = [
        chunk
        for chunk in scan_directory(site_root / "pagefind" / "index", pattern="*.pf_index", recursive=True)
        if chunk.stat().st_size > 0
    ]
    if not index_chunks:
        raise SystemExit(f"{root_label} Pagefind index has no substantive generated index data.")

    present = injected_record_kinds_in_index(site_root)
    missing = sorted(DECIDED_INJECTED_RECORD_KINDS - present)
    if missing:
        raise SystemExit(
            f"{root_label} Pagefind index carries no records of kind(s) {', '.join(missing)} "
            f"(found: {', '.join(sorted(present)) or 'none'}). The index holds rendered pages only, "
            "so a reader could not search that surface at all. This is a pages-only index: confirm the "
            "site index pass ran with the record-injecting contract (CADRUMO_DOCS_PAGEFIND_MODE=full), "
            f"then rebuild before publishing. Index read at {site_root / 'pagefind'}.",
        )


def _validate_language_entry(html_root: Path) -> None:
    """Require the apex entry to exist and to reach every published root.

    This is the REACHABILITY half of what the apex owes, and only that half: it
    exists and no root is unreachable from it. A language built, uploaded and
    then absent from the entry is invisible to every reader who does not
    already know its URL, and nothing else in the pipeline would notice.

    The apex's own artifact set -- its error page, its sitemap index and the
    site's one Pagefind bundle -- is required by :func:`_validate_apex`, not
    here. Neither check is the other's substitute: an entry that reaches every
    root proves nothing about what those roots contain.
    """
    entry = html_root / "index.html"
    if not entry.is_file():
        raise SystemExit(f"Language entry missing at {entry}; refusing to publish.")
    body = entry.read_text(encoding=UTF_8)
    unreachable = [language for language in localized_languages() if f'"{language}"' not in body]
    if unreachable:
        raise SystemExit(
            f"Language entry does not route to {', '.join(unreachable)}; refusing to publish "
            "a root that cannot reach every built language.",
        )
    if _docs_i18n.DEFAULT_SITE_LANGUAGE not in body:
        raise SystemExit(
            f"Language entry declares no {_docs_i18n.DEFAULT_SITE_LANGUAGE!r} fallback; a reader with no "
            "stated preference would reach nothing.",
        )


def _validate_language_roots(html_root: Path) -> None:
    """Require every published site root to carry the complete required-artifact set.

    The same artifacts mandatory for the English root -- the rendered page, the
    404 error page and a canonically-rooted sitemap -- are mandatory for every
    localized root too, not only its index page. These are checked per root
    because a root's pages are its own; the search index is checked once, at the
    apex, because the site has one.
    """
    for language in localized_languages():
        root = html_root / language
        label = f"Localized site root {language!r}"
        _require_artifacts_present(root, root_label=label)
        _require_valid_sitemap(root, expected_base_url=_language_site_url(language), root_label=label)


def _validate_built_site(html_root: Path) -> None:
    """Run every validation a publish runs against the built tree before uploading.

    Every language root must carry its complete artifact set, and the site must
    carry a record-bearing search index, before a byte moves: a publish that
    cannot succeed would otherwise write to the live destination first.
    """
    _validate_apex(html_root)
    _validate_language_entry(html_root)
    _validate_language_roots(html_root)
    _require_search_index(html_root, root_label="The documentation site")
