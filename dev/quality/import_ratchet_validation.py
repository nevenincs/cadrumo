"""Import ratchet validation."""

from __future__ import annotations

from datetime import date
from typing import cast

from .import_health_models import RatchetEntry


def _ratchet_text_fields(entry: dict[str, object]) -> dict[str, str] | str:
    """Ratchet text fields."""
    required_text = (
        "fingerprint",
        "source_module",
        "target_module",
        "import_form",
        "lexical_scope",
        "contract",
        "owner",
        "reason",
        "capability",
        "created_on",
        "expires_on",
        "status",
    )
    text_fields: dict[str, str] = {}
    for key in required_text:
        value = entry.get(key)
        if not isinstance(value, str) or not value.strip():
            return "required text field is missing"
        text_fields[key] = value
    return text_fields


def _ratchet_imported_symbols(entry: dict[str, object]) -> list[str] | str:
    """Ratchet imported symbols."""
    imported_symbols_raw = entry.get("imported_symbols")
    if not isinstance(imported_symbols_raw, list):
        return "imported_symbols must be a string list"
    imported_symbols: list[str] = []
    for symbol in cast("list[object]", imported_symbols_raw):
        if not isinstance(symbol, str):
            return "imported_symbols must be a string list"
        imported_symbols.append(symbol)
    return imported_symbols


def _ratchet_date_refusal(text_fields: dict[str, str]) -> str | None:
    """Ratchet date refusal."""
    try:
        created = date.fromisoformat(text_fields["created_on"])
        expires = date.fromisoformat(text_fields["expires_on"])
    except ValueError:
        return "created_on and expires_on must be ISO dates"
    if expires < created:
        return "expires_on precedes created_on"
    return None


def validate_ratchet_entry(entry: dict[str, object]) -> str | RatchetEntry:
    """Validate one approved occurrence and its stable fingerprint."""
    text_fields = _ratchet_text_fields(entry)
    if isinstance(text_fields, str):
        return text_fields

    imported_symbols = _ratchet_imported_symbols(entry)
    if isinstance(imported_symbols, str):
        return imported_symbols

    multiplicity = entry.get("multiplicity")
    if not isinstance(multiplicity, int) or multiplicity <= 0:
        return "multiplicity must be a positive integer"
    import_form = text_fields["import_form"]
    if import_form not in {"static", "local", "type_checking", "dynamic"}:
        return "unknown import_form"
    status = text_fields["status"]
    if status not in {"active", "retired"}:
        return "status must be active or retired"
    date_refusal = _ratchet_date_refusal(text_fields)
    if date_refusal is not None:
        return date_refusal
    from .import_occurrences import import_occurrence_fingerprint

    expected = import_occurrence_fingerprint(
        source_module=text_fields["source_module"],
        target_module=text_fields["target_module"],
        imported_symbols=tuple(imported_symbols),
        import_form=import_form,
        lexical_scope=text_fields["lexical_scope"],
        contract=text_fields["contract"],
    )
    if text_fields["fingerprint"] != expected:
        return "fingerprint does not match normalized occurrence identity"
    return {
        "fingerprint": text_fields["fingerprint"],
        "source_module": text_fields["source_module"],
        "target_module": text_fields["target_module"],
        "import_form": import_form,
        "imported_symbols": imported_symbols,
        "lexical_scope": text_fields["lexical_scope"],
        "contract": text_fields["contract"],
        "owner": text_fields["owner"],
        "reason": text_fields["reason"],
        "capability": text_fields["capability"],
        "multiplicity": multiplicity,
        "created_on": text_fields["created_on"],
        "expires_on": text_fields["expires_on"],
        "status": status,
    }
