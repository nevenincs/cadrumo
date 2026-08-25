"""Shared validators and typed period wire alias for live payload schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from pydantic import AfterValidator

from ...core import Period
from ...core.errors import CoreValidationError
from ...core.time import validate_utc_aware


def _is_a_registry_period_token(value: str) -> str:
    """Return ``value`` when it is a bare registry period code, else refuse.

    The justificante wire carries the bare token (``"1T"``, ``"0A"``) rather
    than a structured :class:`~core.Period`, so the JSON contract stays a
    string -- but a string is not a free-form label. Parsing it back through
    the canonical period grammar is what stops ``period='bogus'`` from being
    emitted as a capture's filing period.
    """
    Period.from_year_and_code(2000, value)
    return value


JustificantePeriodToken = Annotated[str, AfterValidator(_is_a_registry_period_token)]
"""A bare registry period code, validated through the canonical period grammar."""

# ---------------------------------------------------------------------------
# Shared nested models (not direct CommandSpec schema targets)
# ---------------------------------------------------------------------------


def _canonical_borrador_period(value: str) -> str:
    """Validate and normalise the canonical string transport for a filing period."""
    return str(Period.from_string(value))


def _canonical_borrador_utc_timestamp(value: str) -> str:
    """Require an ISO-8601 UTC timestamp while retaining its JSON string form."""
    try:
        timestamp = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("must be an ISO-8601 timestamp") from exc
    try:
        validate_utc_aware(timestamp)
    except CoreValidationError as exc:
        raise ValueError("must be a UTC timestamp") from exc
    return value


__all__ = ["JustificantePeriodToken"]
