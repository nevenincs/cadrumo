"""Select the common scalar floor when building M347 authority fixtures."""

from __future__ import annotations

from datetime import date
from typing import Final

from ..facts.resolution import ResolvedScalarFact
from ..governed_fact_scope import GovernedFactSource, require_governed_fact_authority
from ..m347_threshold import _resolve_m347_floor_fact

_M347_COUNTERPARTY_THRESHOLD_FACT_ID: Final = "m347-counterparty-declaration-threshold"


def resolve_m347_counterparty_annual_threshold(
    *,
    effective_date: date,
    authority: GovernedFactSource | None = None,
) -> ResolvedScalarFact:
    """Resolve the canonical annual counterparty threshold with provenance."""
    selected = require_governed_fact_authority(authority, subject="M347 counterparty threshold")
    return _resolve_m347_floor_fact(
        _M347_COUNTERPARTY_THRESHOLD_FACT_ID,
        effective_date=effective_date,
        authority=selected,
    )
