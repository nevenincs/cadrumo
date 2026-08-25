"""Project the registry legal catalogue into typed docs search records.

The generated legal-reference renderer owns page slugs, provision anchors, and
site-relative targets. This module supplies those rendered targets to the
search-record seam while carrying the authored catalogue fields, including the
BOE permalink, as typed record metadata. It does not invent a search
destination or a translated legal description.
"""

from __future__ import annotations

from pathlib import Path

from cadrumo.core.external_constants import OutputLanguage

from ..._paths import REPO_ROOT
from ..legal_reference import (
    LegalProvisionRecord,
    LegalReferenceError,
    load_legal_provisions,
    render_legal_reference,
)
from ._search_record import LegalSearchRecord

__all__ = ["LegalSearchRecord", "legal_target_record_id", "project_legal_search_records"]

_REPO_ROOT = REPO_ROOT
_LEGAL_RECORD_ID_PREFIX = "legal:"


def legal_target_record_id(legal_id: str) -> str:
    """Return the search-record id for a legal-catalogue provision."""
    return f"{_LEGAL_RECORD_ID_PREFIX}{legal_id}"


def project_legal_search_records(repo_root: Path | None = None) -> tuple[LegalSearchRecord, ...]:
    """Project every authored legal provision onto its generated target.

    ``render_legal_reference`` is passed the same loaded catalogue rows used
    for projection, so the returned target inventory is the renderer's own
    page/anchor authority rather than a second URL convention. BOE permalinks
    remain provenance and are never returned as ``target`` values.
    """
    root = repo_root if repo_root is not None else _REPO_ROOT
    records = load_legal_provisions(root)
    reference = render_legal_reference(root, records)
    projected: list[LegalSearchRecord] = []
    for record in records:
        target = reference.targets.get(record.legal_id)
        if target is None:
            raise LegalReferenceError(
                f"legal provision {record.legal_id!r} has no generated legal-reference target",
            )
        projected.append(
            LegalSearchRecord(
                record_id=legal_target_record_id(record.legal_id),
                title=record.legal_id,
                descriptions={OutputLanguage.ES: _description(record)},
                target=target,
                legal_id=record.legal_id,
                legal_kind=record.kind,
                document_id=record.document_id,
                corpus_ref=record.corpus_ref,
                permalink=record.permalink,
                authority=record.authority,
                evidence_tier=record.evidence_tier,
                article=record.article,
                section=record.section,
                published_at=record.published_at,
                effective_from=record.effective_from,
                effective_to=record.effective_to,
                consolidated_as_of=record.consolidated_as_of,
                review_status=record.review_status,
                reviewed_at=record.reviewed_at,
                reviewed_by=record.reviewed_by,
                notes=record.notes,
                required_text=record.required_text,
                search_aliases=_search_aliases(record),
            ),
        )
    return tuple(projected)


def _description(record: LegalProvisionRecord) -> str:
    """Return authored legal text, falling back only to the authored id."""
    if record.notes:
        return record.notes
    if record.required_text:
        return "; ".join(record.required_text)
    return record.legal_id


def _search_aliases(record: LegalProvisionRecord) -> tuple[str, ...]:
    """Collect authored catalogue forms without synthesising vocabulary."""
    candidates = (
        record.document_id,
        record.kind,
        record.corpus_ref,
        record.article,
        record.section,
        *record.required_text,
    )
    seen: set[str] = {record.legal_id}
    aliases: list[str] = []
    for value in candidates:
        if value and value not in seen:
            seen.add(value)
            aliases.append(value)
    return tuple(aliases)
