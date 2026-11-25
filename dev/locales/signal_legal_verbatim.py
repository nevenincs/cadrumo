"""Verify source-backed legal wording before excluding it from spelling."""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Mapping
from html import escape
from pathlib import Path
from typing import TYPE_CHECKING

from dev.paths import UTF_8

from .signal_tokens import filtered_translation_text

if TYPE_CHECKING:
    from dev.docs.legal_reference_models import LegalProvisionRecord


def verified_legal_wording_prose(
    path: Path,
    repository: Path,
    records_for_audit: Callable[[], Mapping[str, LegalProvisionRecord]] | None = None,
) -> dict[int, str]:
    """Retain unverified wording from authenticated generated quote blocks.

    A marker is not authority: its row, placement, rendered text and exact
    anchored corpus proof are independently checked against the catalogue.
    """
    lines = path.read_text(encoding=UTF_8).splitlines()
    markers = [
        (index, line) for index, line in enumerate(lines) if line.lstrip().startswith(".. cadrumo-legal-verbatim")
    ]
    if not markers:
        return {}
    if path.suffix != ".rst" or path.parts[-3:-1] != ("_generated", "legal"):
        raise ValueError("legal verbatim markers are only valid on generated legal pages")
    from dev.docs.legal_catalogue import read_legal_provisions

    records = (
        records_for_audit()
        if records_for_audit is not None
        else {record.legal_id: record for record in read_legal_provisions(repository)}
    )
    result: dict[int, str] = {}
    seen: set[str] = set()
    for index, marker in markers:
        record, indices = _verified_wording_marker(marker, path, repository, records, seen)
        _require_wording_anchor(lines, index, record)
        _require_wording_block(lines, index, record)
        result[index + 7] = _unchecked_wording(record, indices)
    return result


_LEGAL_VERBATIM_PREFIX = ".. cadrumo-legal-verbatim: "


def _verified_wording_marker(
    marker: str,
    path: Path,
    repository: Path,
    records: Mapping[str, LegalProvisionRecord],
    seen: set[str],
) -> tuple[LegalProvisionRecord, tuple[int, ...]]:
    """Resolve marker identity and recheck the authoritative corpus proof."""
    from dev.docs.legal_page_rendering import verified_legal_wording_indices
    from dev.docs.legal_reference_routing import legal_page_relpath

    legal_id = _wording_marker_id(marker, records, seen)
    record = records[legal_id]
    if path.relative_to(repository / "docs") != legal_page_relpath(record.document_id):
        raise ValueError("legal verbatim marker names a different document")
    indices = verified_legal_wording_indices(record, repository)
    expected = _LEGAL_VERBATIM_PREFIX + json.dumps({"legal_id": legal_id, "verified": indices}, ensure_ascii=False)
    if not indices or marker != expected:
        raise ValueError("legal verbatim marker lacks current anchored source proof")
    return record, indices


def _wording_marker_id(marker: str, records: Mapping[str, LegalProvisionRecord], seen: set[str]) -> str:
    """Read one declared row identity, refusing malformed or duplicate markers."""
    if not marker.startswith(_LEGAL_VERBATIM_PREFIX):
        raise ValueError("malformed legal verbatim marker")
    try:
        payload = json.loads(marker[len(_LEGAL_VERBATIM_PREFIX) :])
    except json.JSONDecodeError as exc:
        raise ValueError("malformed legal verbatim marker") from exc
    if not isinstance(payload, dict) or set(payload) != {"legal_id", "verified"}:
        raise ValueError("invalid legal verbatim marker")
    legal_id = payload["legal_id"]
    if not isinstance(legal_id, str) or legal_id not in records or legal_id in seen:
        raise ValueError("unknown or repeated legal verbatim marker")
    seen.add(legal_id)
    return legal_id


def _require_wording_anchor(lines: list[str], index: int, record: LegalProvisionRecord) -> None:
    """Bind the marker to the provision immediately preceding it."""
    from dev.docs.legal_reference_routing import legal_provision_anchor

    anchor = legal_provision_anchor(
        record.legal_id,
        article=record.article,
        section=record.section,
        corpus_ref=record.corpus_ref,
        permalink=record.permalink,
    )
    preceding = [line for line in lines[:index] if re.fullmatch(r'   <span id="[^"]+"></span>', line)]
    if anchor is None or not preceding or preceding[-1] != f'   <span id="{anchor}"></span>':
        raise ValueError("legal verbatim marker does not follow its provision anchor")


def _require_wording_block(lines: list[str], index: int, record: LegalProvisionRecord) -> None:
    """Refuse a marker whose following block differs from the authored row."""
    quotes = "".join(f"<p>{escape(item.rstrip())}</p>" for item in record.required_text)
    expected_blockquote = f'     <blockquote lang="es">{quotes}</blockquote>'
    if (
        index + 7 >= len(lines)
        or lines[index + 1 : index + 5] != ["", ".. raw:: html", "", '   <div class="cadrumo-legal-wording">']
        or not re.fullmatch(r'     <p class="cadrumo-legal-wording-label" lang="[^"]+">.*</p>', lines[index + 5])
        or lines[index + 6] != expected_blockquote
        or lines[index + 7] != "   </div>"
    ):
        raise ValueError("legal verbatim marker does not match its rendered wording")


def _unchecked_wording(record: LegalProvisionRecord, indices: tuple[int, ...]) -> str:
    """Keep every phrase that did not receive exact source proof."""
    remaining = "".join(
        f"<p>{escape(item.rstrip())}</p>" for offset, item in enumerate(record.required_text) if offset not in indices
    )
    return filtered_translation_text(remaining)[0]
