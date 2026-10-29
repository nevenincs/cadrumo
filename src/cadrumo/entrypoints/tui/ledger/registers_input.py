"""Typed register input parsing and reviewed-request wording."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from typing import cast

from pydantic import BaseModel

from ....application.operations.public_scalar import PublicDecimal
from ....core.decimal.grammar import try_parse_canonical_decimal
from ....core.i18n.render import tr
from ....core.parsing.dates import require_iso8601_date


def blank_to_none(raw: str) -> str | None:
    """A blank field is not part of the request."""
    stripped = raw.strip()
    return stripped or None


def _field_name(field_key: str) -> str:
    return tr(field_key)


def require_text(raw: str, *, field_key: str) -> str:
    """A required text field, refused on screen when left blank."""
    value = blank_to_none(raw)
    if value is None:
        raise ValueError(tr("tui.ledger.registers.required", field=_field_name(field_key)))
    return value


def parse_public_decimal(raw: str, *, field_key: str, signed: bool = True) -> PublicDecimal:
    """Parse a typed amount in the canonical grammar; ambiguous separators are refused, never guessed."""
    parsed = try_parse_canonical_decimal(raw, signed=signed, max_fraction_digits=2)
    if parsed is None:
        raise ValueError(tr("tui.ledger.registers.invalid_decimal", field=_field_name(field_key), value=raw.strip()))
    return PublicDecimal(decimal=str(parsed))


def parse_optional_public_decimal(raw: str, *, field_key: str, signed: bool = True) -> PublicDecimal | None:
    """Parse an optional amount; a blank field is absent rather than zero."""
    if blank_to_none(raw) is None:
        return None
    return parse_public_decimal(raw, field_key=field_key, signed=signed)


def parse_date(raw: str, *, field_key: str) -> date:
    """Parse a typed calendar date in the extended ISO form."""
    try:
        return require_iso8601_date(raw.strip())
    except ValueError:
        raise ValueError(
            tr("tui.ledger.registers.invalid_date", field=_field_name(field_key), value=raw.strip())
        ) from None


def parse_whole_number(raw: str, *, field_key: str) -> int:
    """Parse a typed year or count as a whole number."""
    stripped = raw.strip()
    if not stripped.isascii() or not stripped.isdigit():
        raise ValueError(tr("tui.ledger.registers.invalid_number", field=_field_name(field_key), value=stripped))
    return int(stripped)


def parse_optional_whole_number(raw: str, *, field_key: str) -> int | None:
    """Parse an optional whole number; a blank field is absent."""
    if blank_to_none(raw) is None:
        return None
    return parse_whole_number(raw, field_key=field_key)


def decimal_text(value: PublicDecimal | None) -> str:
    """Show an operation's decimal exactly as it reported it, or a dash when it reported none."""
    return "-" if value is None else value.decimal


def _summary_value(value: object) -> str | None:
    if value is None or value == ():
        return None
    if isinstance(value, PublicDecimal):
        return value.decimal
    if isinstance(value, bool):
        return tr("tui.ledger.registers.yes" if value else "tui.ledger.registers.no")
    if isinstance(value, BaseModel):
        return tr("tui.ledger.registers.attached")
    if isinstance(value, tuple):
        return ", ".join(str(item) for item in cast("tuple[object, ...]", value))
    return str(value)


def request_summary(request: BaseModel, *, field_keys: Mapping[str, str]) -> str:
    """List every field the reviewed request carries, named in the operator's language."""
    lines: list[str] = []
    for name in type(request).model_fields:
        if name == "profile_id":
            continue
        text = _summary_value(getattr(request, name))
        if text is not None:
            lines.append(f"{tr(field_keys[name])}: {text}")
    return "\n".join(lines)
