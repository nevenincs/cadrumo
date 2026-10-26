"""Render and publish legal-reference pages from the authoritative catalogue."""

from __future__ import annotations

import os
from pathlib import Path

from cadrumo.core.directory_scan import scan_directory
from cadrumo.core.external_constants import OutputLanguage
from cadrumo.core.link_safety import is_link_like
from dev._paths import UTF_8

from .build import docs_build_language
from .legal_catalogue import load_legal_provisions
from .legal_page_rendering import _render_document_page, _render_index
from .legal_record_validation import _validate_records
from .legal_reference_models import LegalPage, LegalProvisionRecord, LegalReferenceError, LegalReferenceResult
from .legal_reference_routing import LEGAL_REFERENCE_DIR


def render_legal_reference(
    repo_root: Path,
    records: tuple[LegalProvisionRecord, ...] | None = None,
    language: OutputLanguage | None = None,
) -> LegalReferenceResult:
    """Render the legal reference in memory and return its inventories.

    ``language`` selects the page chrome. It defaults to the language this docs
    root is being built for, so a Spanish root writes Spanish headings and
    labels around the Spanish legal text it may not translate.
    """
    resolved_language = language if language is not None else docs_build_language(os.environ)
    resolved = records if records is not None else load_legal_provisions(repo_root)
    ordered = tuple(
        sorted(
            resolved,
            key=lambda record: (
                record.document_id,
                record.article or "",
                record.section or "",
                record.legal_id,
            ),
        ),
    )
    _validate_records(ordered)

    grouped: dict[str, list[LegalProvisionRecord]] = {}
    for record in ordered:
        grouped.setdefault(record.document_id, []).append(record)
    pages = tuple(
        _render_document_page(document_id, tuple(grouped[document_id]), resolved_language)
        for document_id in sorted(grouped)
    )
    return _reference_result(pages)


def generate_legal_reference(
    docs_root: Path,
    *,
    repo_root: Path | None = None,
    language: OutputLanguage | None = None,
) -> LegalReferenceResult:
    """Materialise legal pages from the authoritative repo into ``docs_root``.

    ``docs_root`` may be an isolated copy used by a localized build, so the
    source repository must be independently selectable. The default retains
    the historical adjacent-root behavior for direct callers.
    """
    resolved_language = language if language is not None else docs_build_language(os.environ)
    docs_root = docs_root.resolve()
    source_root = (repo_root if repo_root is not None else docs_root.parent).resolve()
    result = render_legal_reference(source_root, language=language)
    out_dir = _validated_output_dir(docs_root)
    output_paths = [out_dir / "index.rst"]
    for page in result.pages:
        page_path = docs_root / Path(page.output_relpath)
        if page_path.parent != out_dir or page_path.suffix != ".rst":
            raise LegalReferenceError(f"generated legal page escaped the validated output directory: {page_path}")
        output_paths.append(page_path)
    if len(set(output_paths)) != len(output_paths):
        raise LegalReferenceError("generated legal output paths collide")
    _remove_generated_rst(out_dir, frozenset(output_paths))
    _write_if_changed(output_paths[0], _render_index(result.pages, resolved_language))
    for page, path in zip(result.pages, output_paths[1:], strict=True):
        _write_if_changed(path, page.rst)
    return result


def _validated_output_dir(docs_root: Path) -> Path:
    """Return the exact legal output directory, refusing symlinked or broad paths."""
    relative = Path(LEGAL_REFERENCE_DIR)
    if relative.parts != ("_generated", "legal"):
        raise LegalReferenceError(f"unexpected legal output path constant: {LEGAL_REFERENCE_DIR!r}")
    generated_dir = docs_root / "_generated"
    out_dir = docs_root / relative
    if out_dir.parent != generated_dir or out_dir.name != "legal":
        raise LegalReferenceError(f"unexpected legal output directory: {out_dir}")
    if not docs_root.is_dir() or is_link_like(docs_root):
        raise LegalReferenceError(f"docs root is not a real directory: {docs_root}")
    if is_link_like(generated_dir) or not generated_dir.is_dir():
        raise LegalReferenceError(f"generated docs directory is not a real directory: {generated_dir}")
    if is_link_like(out_dir):
        raise LegalReferenceError(f"legal output directory is not the exact real directory: {out_dir}")
    if out_dir.exists():
        _validate_existing_output_dir(out_dir)
    else:
        out_dir.mkdir()
    return out_dir


def _remove_generated_rst(out_dir: Path, keep: frozenset[Path]) -> None:
    """Remove direct generated RST files this render no longer produces.

    Pruning is why the sweep exists: a legal document dropped from the
    catalogue must not leave its page behind for Sphinx to read. Only the
    pages absent from ``keep`` are unlinked, so a page this render still owns
    keeps its inode and its mtime, and :func:`_write_if_changed` can then leave
    it untouched when its bytes are unchanged. Deleting every page first made
    that comparison vacuous -- all 141 were recreated with fresh mtimes on
    every build, so Sphinx re-read and re-wrote the whole legal tree even when
    the catalogue had not moved.
    """
    for path in scan_directory(out_dir, require_root=True):
        if path.suffix != ".rst":
            continue
        if path.is_symlink() or not path.is_file() or path.parent != out_dir:
            raise LegalReferenceError(f"refusing to remove unsafe generated legal path: {path}")
        if path in keep:
            continue
        path.unlink()


def _write_if_changed(path: Path, rst: str) -> None:
    """Write generated RST with LF endings only when its bytes changed."""
    if not (path.is_file() and path.read_bytes() == rst.encode(UTF_8)):
        path.write_text(rst, encoding=UTF_8, newline="\n")


def _reference_result(pages: tuple[LegalPage, ...]) -> LegalReferenceResult:
    targets = {legal_id: target for page in pages for legal_id, target in page.targets.items()}
    anchors = {legal_id: anchor for page in pages for legal_id, anchor in page.anchor_by_id.items()}
    grounding_count = sum(len(page.grounding_by_id) for page in pages)
    return LegalReferenceResult(
        pages=pages,
        index_relpath=f"{LEGAL_REFERENCE_DIR}/index.rst",
        page_count=len(pages),
        provision_count=sum(len(page.targets) for page in pages),
        grounding_count=grounding_count,
        targets=targets,
        anchors=anchors,
    )


def _validate_existing_output_dir(out_dir: Path) -> None:
    if is_link_like(out_dir) or not out_dir.is_dir() or out_dir.resolve() != out_dir:
        raise LegalReferenceError(f"legal output directory is not the exact real directory: {out_dir}")
