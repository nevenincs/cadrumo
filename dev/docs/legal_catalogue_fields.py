"""Strict authored legal table fields and BOE permalink validation."""

from __future__ import annotations

import unicodedata
from datetime import date
from pathlib import Path
from typing import Final, cast
from urllib.parse import urlsplit

from cadrumo.domain.calculations.registry.schema_references import LegalReference

from .legal_reference_models import LegalProvisionRecord, LegalReferenceError

_LEGAL_TABLE_FIELDS: Final[frozenset[str]] = frozenset(
    field_name for field_name in LegalReference.model_fields if isinstance(field_name, str) and field_name != "id"
)
"""Every field a ``[legal."..."]`` table body may declare.

Derived from :class:`LegalReference` rather than hand-listed, so it is complete
by construction and cannot drift from the model it validates against. The
hand-written set it replaces had fallen two fields behind -- ``corpus_tier``
and ``forbidden_text`` -- and the first of those crashed ``dev.locales
scaffold`` tree-wide the moment a catalogue entry used it, blocking every
locale operation for reasons unrelated to locales.

``id`` is excluded because it is the TOML table KEY, not a body field: a legal
entry is written ``[legal."ley-58-2003:art-29"]`` and never carries ``id =``
inside its own table.
"""


_UNSAFE_LINK_CHARS: Final[frozenset[str]] = frozenset({"<", ">", '"', "'", "`", "\\"})


def _validate_authored_text(value: str, *, path: Path, legal_id: str, field: str) -> str:
    """Reject authored control characters before text enters generated RST."""
    if any(unicodedata.category(char).startswith("C") for char in value):
        raise LegalReferenceError(
            f"{path}: legal entry {legal_id!r} field {field!r} contains a control character",
        )
    return value


def _validate_boe_permalink(value: str, *, path: Path, legal_id: str) -> str:
    """Validate an authored BOE URL before it enters an RST link target."""
    _validate_authored_text(value, path=path, legal_id=legal_id, field="permalink")
    if any(char.isspace() for char in value) or any(char in _UNSAFE_LINK_CHARS for char in value):
        raise LegalReferenceError(
            f"{path}: legal entry {legal_id!r} field 'permalink' contains unsafe URL characters",
        )
    try:
        parsed = urlsplit(value)
    except ValueError as exc:
        raise LegalReferenceError(
            f"{path}: legal entry {legal_id!r} field 'permalink' is malformed",
        ) from exc
    if parsed.scheme != "https" or parsed.netloc != "www.boe.es" or not parsed.path.startswith("/"):
        raise LegalReferenceError(
            f"{path}: legal entry {legal_id!r} field 'permalink' must be an https://www.boe.es URL",
        )
    return value


def _required_string(body: dict[str, object], key: str, *, path: Path, legal_id: str) -> str:
    value = body.get(key)
    if not isinstance(value, str) or not value.strip():
        raise LegalReferenceError(f"{path}: legal entry {legal_id!r} requires string field {key!r}")
    return _validate_authored_text(value, path=path, legal_id=legal_id, field=key)


def _optional_string(body: dict[str, object], key: str, *, path: Path, legal_id: str) -> str | None:
    value = body.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise LegalReferenceError(f"{path}: legal entry {legal_id!r} field {key!r} must be a string")
    return _validate_authored_text(value, path=path, legal_id=legal_id, field=key)


def _optional_date(body: dict[str, object], key: str, *, path: Path, legal_id: str) -> date | None:
    value = body.get(key)
    if value is None:
        return None
    if not isinstance(value, date):
        raise LegalReferenceError(f"{path}: legal entry {legal_id!r} field {key!r} must be a TOML date")
    return value


def required_text(body: dict[str, object], *, path: Path, legal_id: str) -> tuple[str, ...]:
    value = body.get("required_text")
    if value is None:
        return ()
    if not isinstance(value, list):
        raise LegalReferenceError(f"{path}: legal entry {legal_id!r} field 'required_text' must be a string array")
    items = cast(list[object], value)
    if not all(isinstance(item, str) for item in items):
        raise LegalReferenceError(f"{path}: legal entry {legal_id!r} field 'required_text' must be a string array")
    string_items = tuple(item for item in items if isinstance(item, str))
    return tuple(
        _validate_authored_text(item, path=path, legal_id=legal_id, field="required_text") for item in string_items
    )


def _record_from_table(path: Path, legal_id: str, body: object) -> LegalProvisionRecord:
    if not isinstance(body, dict):
        raise LegalReferenceError(f"{path}: [legal.{legal_id!r}] must be a table")
    table = cast(dict[str, object], body)
    unknown_fields = set(table).difference(_LEGAL_TABLE_FIELDS)
    if unknown_fields:
        fields = ", ".join(repr(field) for field in sorted(unknown_fields))
        raise LegalReferenceError(
            f"{path}: legal entry {legal_id!r} contains unknown field(s): {fields}",
        )
    permalink = _required_string(table, "permalink", path=path, legal_id=legal_id)
    _validate_boe_permalink(permalink, path=path, legal_id=legal_id)
    return LegalProvisionRecord(
        legal_id=legal_id,
        kind=_required_string(table, "kind", path=path, legal_id=legal_id),
        document_id=_required_string(table, "document_id", path=path, legal_id=legal_id),
        corpus_ref=_required_string(table, "corpus_ref", path=path, legal_id=legal_id),
        permalink=permalink,
        authority=_optional_string(table, "authority", path=path, legal_id=legal_id),
        evidence_tier=_optional_string(table, "evidence_tier", path=path, legal_id=legal_id),
        article=_optional_string(table, "article", path=path, legal_id=legal_id),
        section=_optional_string(table, "section", path=path, legal_id=legal_id),
        published_at=_optional_date(table, "published_at", path=path, legal_id=legal_id),
        effective_from=_optional_date(table, "effective_from", path=path, legal_id=legal_id),
        effective_to=_optional_date(table, "effective_to", path=path, legal_id=legal_id),
        consolidated_as_of=_optional_date(table, "consolidated_as_of", path=path, legal_id=legal_id),
        review_status=_optional_string(table, "review_status", path=path, legal_id=legal_id),
        reviewed_at=_optional_date(table, "reviewed_at", path=path, legal_id=legal_id),
        reviewed_by=_optional_string(table, "reviewed_by", path=path, legal_id=legal_id),
        notes=_optional_string(table, "notes", path=path, legal_id=legal_id),
        required_text=required_text(table, path=path, legal_id=legal_id),
    )
