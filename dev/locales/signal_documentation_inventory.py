"""Documentation inventory for the authoritative locale audit."""

from __future__ import annotations

import html
import re
from collections import Counter
from collections.abc import Mapping
from pathlib import Path

from .signal_contracts import DocumentationEchoDictionaries
from .signal_document_prose import embedded_document_language_prose, visible_document_prose
from .signal_documentation_counts import docs_extraction_finding, documentation_counts
from .signal_documentation_templates import inventory_documentation_manifest
from .signal_echo_classification import load_platform_identity_terms
from .signal_tokens import filtered_translation_text


def observed_documentation_catalogue_files(
    catalogue_files: set[tuple[str, str]] | None, catalogue_messages: Mapping[tuple[str, str], Mapping[str, bool]]
) -> set[tuple[str, str]]:
    """Observed documentation catalogue files."""
    catalogue_files = catalogue_files or {
        (locale, catalogue) for (catalogue, _message_id), states in catalogue_messages.items() for locale in states
    }
    return catalogue_files


def catalogue_in_localization_scope(catalogue: str, docs_root: Path, pages: set[str]) -> bool:
    """Keep authored or orphan user catalogues, excluding English-only sources.

    Existing sources follow the canonical page selector, including generated
    files outside excluded directories. Missing sources remain orphan candidates
    unless their whole top-level tree is outside the translation authority.
    """
    from dev.docs.i18n import is_localized_documentation_tree

    relative = Path(catalogue)
    if not is_localized_documentation_tree(relative):
        return False
    possible_sources = tuple(relative.with_suffix(suffix) for suffix in (".md", ".rst"))
    return any(path.as_posix() in pages for path in possible_sources) or not any(
        (docs_root / path).is_file() for path in possible_sources
    )


def inventory_generated_document_sources(
    docs_root: Path,
    repository: Path,
    counts: Counter[str],
    findings: list[dict[str, object]],
    spelling_values: dict[str, dict[str, str]] | None,
) -> None:
    """Inventory generated document sources."""
    generated_roots = (docs_root / "cli", docs_root / "_generated")
    generated_pages = sorted(
        path
        for root in generated_roots
        for path in (root.rglob("*") if root.is_dir() else ())
        if path.is_file() and path.suffix in {".md", ".rst"}
    )
    counts["docs_generated_english_only_pages"] = len(generated_pages)
    for path in generated_pages:
        inventory_generated_document_file(path, repository, counts, findings, spelling_values)


def inventory_documentation_catalogue_files(
    pages: list[str],
    catalogue_files: set[tuple[str, str]],
    counts: Counter[str],
    findings: list[dict[str, object]],
) -> None:
    """Inventory documentation catalogue files."""
    from dev.docs.i18n import TARGET_LANGUAGES

    for locale in TARGET_LANGUAGES:
        counts[f"docs_catalogue_files_expected_{locale}"] = len(pages)
    counts["docs_catalogue_files_expected"] = len(pages) * len(TARGET_LANGUAGES)
    expected_catalogues = {
        (locale, Path(page).with_suffix(".po").as_posix()) for locale in TARGET_LANGUAGES for page in pages
    }
    present_catalogues = catalogue_files & expected_catalogues
    counts["docs_catalogue_files_read"] = len(present_catalogues)
    for locale in TARGET_LANGUAGES:
        counts[f"docs_catalogue_files_read_{locale}"] = sum(
            1 for candidate_locale, _catalogue in present_catalogues if candidate_locale == locale
        )
    missing_catalogues = expected_catalogues - catalogue_files
    counts["docs_missing_catalogue_files"] = len(missing_catalogues)
    for locale, catalogue in sorted(missing_catalogues):
        findings.append(
            {
                "classification": "blocking",
                "kind": "docs_catalogue_missing",
                "domain": "docs",
                "path": f"docs/locales/{locale}/LC_MESSAGES/{catalogue}",
                "locale": locale,
                "next_action": "run python -m dev.docs.i18n, then translate the new catalogue",
            }
        )
    orphan_catalogues = catalogue_files - expected_catalogues
    counts["docs_orphan_catalogue_files"] = len(orphan_catalogues)
    for locale, catalogue in sorted(orphan_catalogues):
        findings.append(
            {
                "classification": "blocking",
                "kind": "docs_orphan_catalogue",
                "domain": "docs",
                "path": f"docs/locales/{locale}/LC_MESSAGES/{catalogue}",
                "locale": locale,
                "next_action": "run python -m dev.docs.i18n to prune the orphan catalogue",
            }
        )


def documentation_source_inventory(
    repository: Path,
    catalogue_messages: Mapping[tuple[str, str], Mapping[str, bool]],
    *,
    catalogue_files: set[tuple[str, str]] | None = None,
    catalogue_obsolete: Mapping[tuple[str, str], set[str]] | None = None,
    catalogue_translations: Mapping[tuple[str, str], Mapping[str, tuple[str, ...]]] | None = None,
    spelling_values: dict[str, dict[str, str]] | None = None,
) -> tuple[dict[str, object], list[dict[str, object]]]:
    """Validate cached source extraction and compare it with every PO.

    The committed catalogues are not a source authority: a newly authored
    paragraph is absent from every PO until gettext extraction is rerun.  This
    audit therefore consumes the same page selector and the digest manifest
    written by the canonical Sphinx gettext extractor. English source messages
    are enrolled from a digest-proven POT, alongside translated PO values.
    """
    from dev.docs.i18n import (
        pot_root,
        user_scope_source_pages,
    )

    counts = Counter[str]()
    findings: list[dict[str, object]] = []
    source_echo_samples: list[dict[str, object]] = []
    invariant_echo_samples: list[dict[str, object]] = []
    near_echo_samples: list[dict[str, object]] = []
    echo_cache = DocumentationEchoDictionaries()
    platform_identity_terms = load_platform_identity_terms(repository)
    if catalogue_obsolete is None:
        catalogue_obsolete: dict[tuple[str, str], set[str]] = {}
    if catalogue_translations is None:
        catalogue_translations: dict[tuple[str, str], Mapping[str, tuple[str, ...]]] = {}
    catalogue_files = observed_documentation_catalogue_files(catalogue_files, catalogue_messages)
    docs_root = repository / "docs"
    try:
        pages = user_scope_source_pages(docs_root)
    except Exception as exc:  # The page authority is an audit boundary.
        counts["docs_extraction_failures"] += 1
        findings.append(docs_extraction_finding(docs_root, exc))
        return documentation_counts(counts), findings
    scope_pages = set(pages)
    catalogue_files = {
        (locale, catalogue)
        for locale, catalogue in catalogue_files
        if catalogue_in_localization_scope(catalogue, docs_root, scope_pages)
    }
    for (locale, catalogue), identities in catalogue_obsolete.items():
        if catalogue_in_localization_scope(catalogue, docs_root, scope_pages):
            counts["docs_catalogue_messages_obsolete"] += len(identities)
            counts[f"docs_catalogue_messages_obsolete_{locale}"] += len(identities)
    counts["docs_source_pages"] = len(pages)
    if not pages:
        counts["docs_extraction_failures"] += 1
        findings.append(
            {
                "classification": "blocking",
                "kind": "docs_source_surface_empty",
                "domain": "docs",
                "path": docs_root.as_posix(),
                "next_action": "restore user-scope page discovery, then rerun check-locales",
            }
        )
        return documentation_counts(counts), findings
    inventory_generated_document_sources(docs_root, repository, counts, findings, spelling_values)
    extracted = pot_root(docs_root)
    inventory_documentation_catalogue_files(pages, catalogue_files, counts, findings)
    try:
        inventory_documentation_manifest(
            extracted,
            pages,
            repository,
            docs_root,
            counts,
            findings,
            catalogue_messages,
            catalogue_obsolete,
            catalogue_translations,
            spelling_values,
            echo_cache,
            platform_identity_terms,
            source_echo_samples,
            invariant_echo_samples,
            near_echo_samples,
        )
    except Exception as exc:  # Manifest and filesystem failures must fail closed.
        counts["docs_extraction_failures"] += 1
        findings.append(docs_extraction_finding(docs_root, exc))
    return documentation_counts(
        counts,
        source_echo_samples=source_echo_samples,
        invariant_echo_samples=invariant_echo_samples,
        near_echo_samples=near_echo_samples,
    ), findings


def inventory_generated_document_file(
    path: Path,
    repository: Path,
    counts: Counter[str],
    findings: list[dict[str, object]],
    spelling_values: dict[str, dict[str, str]] | None,
) -> None:
    """Inventory generated document file."""
    try:
        prose = visible_document_prose(path)
    except Exception as exc:  # Parsing is part of the measured docs surface.
        counts["docs_generated_source_failures"] += 1
        findings.append(
            {
                "classification": "blocking",
                "kind": "docs_generated_source_unreadable",
                "domain": "docs",
                "path": path.relative_to(repository).as_posix(),
                "error_type": type(exc).__name__,
                "detail": str(exc),
                "next_action": "repair the generated user document, then rerun check-locales",
            }
        )
        return
    counts["docs_generated_spellchecked_pages"] += 1
    embedded = embedded_document_language_prose(path) + _legal_note_untagged_prose(path)
    counts["docs_generated_prose_cells"] += len(prose) + len(embedded)
    if spelling_values is not None:
        relative = path.relative_to(repository).as_posix()
        for line, text in prose:
            spelling_values.setdefault("en", {})[f"parallel:{relative}:line[{line}]"] = text
        for line, language, text in embedded:
            spelling_values.setdefault(language, {})[f"parallel:{relative}:line[{line}]:lang[{language}]"] = text


_LEGAL_NOTE_BODY = re.compile(
    r"<!--cadrumo-legal-note-->(?P<body>.*?)</p></dd>",
    re.DOTALL,
)
_LEGAL_NOTE_LANGUAGE_SPAN = re.compile(
    r'<span\b[^>]*\blang\s*=\s*["\'][A-Za-z]{2}(?:-[^"\']*)?["\'][^>]*>.*?</span>',
    re.DOTALL | re.IGNORECASE,
)
_HTML_TAG = re.compile(r"</?[^>]+>")


def _legal_note_untagged_prose(path: Path) -> tuple[tuple[int, str, str], ...]:
    """Keep untagged mixed-note text in the English spelling inventory.

    The exact Spanish quote spans are separately read by
    :func:`embedded_document_language_prose`. The generated legal-note raw
    block is invisible to the RST prose parser, so inventory its remaining
    text explicitly instead of exempting the whole note.
    """
    source = path.read_text(encoding="utf-8")
    found: list[tuple[int, str, str]] = []
    for match in _LEGAL_NOTE_BODY.finditer(source):
        untagged = _LEGAL_NOTE_LANGUAGE_SPAN.sub(" ", match.group("body"))
        visible = _HTML_TAG.sub(" ", untagged)
        text = filtered_translation_text(html.unescape(visible))[0].strip()
        if text:
            line = source.count("\n", 0, match.start()) + 1
            found.append((line, "en", text))
    return tuple(found)
