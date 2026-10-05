"""Validate rendered legal rows without inferring or merging authored authority."""

from __future__ import annotations

from pathlib import Path
from typing import Final, cast

from .legal_catalogue_fields import _validate_authored_text, _validate_boe_permalink
from .legal_reference_models import LegalProvisionRecord, LegalReferenceError
from .legal_reference_routing import legal_document_slug

_RENDERED_TEXT_FIELDS: Final[tuple[str, ...]] = (
    "legal_id",
    "kind",
    "document_id",
    "corpus_ref",
    "permalink",
    "authority",
    "evidence_tier",
    "article",
    "section",
    "review_status",
    "reviewed_by",
    "notes",
)


def _validate_records(records: tuple[object, ...]) -> None:
    seen_ids: set[str] = set()
    page_slugs: dict[str, str] = {}
    for candidate in records:
        _validate_rendered_record(candidate, seen_ids, page_slugs)


def _validate_rendered_record(candidate: object, seen_ids: set[str], page_slugs: dict[str, str]) -> None:
    if not isinstance(candidate, LegalProvisionRecord):
        raise LegalReferenceError("legal reference records must be LegalProvisionRecord values")
    record = candidate
    _validate_record_text(record)
    _validate_record_window(record)
    if record.legal_id in seen_ids:
        raise LegalReferenceError(f"duplicate legal provision id {record.legal_id!r}; refusing to merge rows")
    seen_ids.add(record.legal_id)
    slug = legal_document_slug(record.document_id)
    previous_document = page_slugs.get(slug)
    if previous_document is not None and previous_document != record.document_id:
        raise LegalReferenceError(
            f"document ids {previous_document!r} and {record.document_id!r} collide at page slug {slug!r}",
        )
    page_slugs[slug] = record.document_id


def _validate_record_text(record: LegalProvisionRecord) -> None:
    for field in _RENDERED_TEXT_FIELDS:
        value = cast(object, getattr(record, field))
        if value is None:
            continue
        if not isinstance(value, str):
            raise LegalReferenceError(
                f"legal entry {record.legal_id!r} field {field!r} must be a string",
            )
        _validate_authored_text(value, path=Path("<rendered records>"), legal_id=record.legal_id, field=field)
    required_value = cast(object, record.required_text)
    if not isinstance(required_value, tuple):
        raise LegalReferenceError(f"legal entry {record.legal_id!r} field 'required_text' must be a string tuple")
    required_items = cast(tuple[object, ...], required_value)
    if not all(isinstance(item, str) for item in required_items):
        raise LegalReferenceError(f"legal entry {record.legal_id!r} field 'required_text' must be a string tuple")
    for item in (item for item in required_items if isinstance(item, str)):
        _validate_authored_text(
            item,
            path=Path("<rendered records>"),
            legal_id=record.legal_id,
            field="required_text",
        )
    _validate_boe_permalink(
        record.permalink,
        path=Path("<rendered records>"),
        legal_id=record.legal_id,
    )


def _validate_record_window(record: LegalProvisionRecord) -> None:
    if (
        record.effective_from is not None
        and record.effective_to is not None
        and record.effective_to < record.effective_from
    ):
        raise LegalReferenceError(
            f"legal entry {record.legal_id!r} declares an effectivity window that closes before "
            f"it opens: effective_from {record.effective_from.isoformat()} is later than "
            f"effective_to {record.effective_to.isoformat()}; the rendered in-force sentence "
            "would assert a span no reader can act on",
        )
