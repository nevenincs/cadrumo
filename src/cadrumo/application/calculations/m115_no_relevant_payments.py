"""Modelo 115 explicit no-relevant-payment attestations.

An empty Modelo 115 observation window is not evidence of a zero return.  The
operator may instead persist a period-scoped attestation that no payment subject
to urban-rent withholding occurred.  Only that explicit fact permits the
calculation path to materialise the model's canonical zero values.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Final

from ...core.period import Period, PeriodError
from ..user_profile.profile_read_ports import ProfilePathValuesReadPort

M115_NO_RELEVANT_PAYMENT_PROFILE_PATH: Final = "withholding.modelo_115_no_relevant_payment_periods"
"""Profile fact carrying comma-separated ``YYYY:PERIOD`` Modelo 115 attestations."""

_TOKEN_RE: Final = re.compile(r"^(?P<year>\d{4}):(?P<period>[A-Z0-9]+)$")


def parse_m115_no_relevant_payment_periods(raw: str | None) -> frozenset[tuple[int, str]]:
    """Parse explicit Modelo 115 no-relevant-payment period keys.

    Invalid tokens attest nothing.  This is deliberately fail-closed: malformed
    profile input leaves the normal missing-observation refusal in force.
    """
    if raw is None:
        return frozenset[tuple[int, str]]()
    periods: set[tuple[int, str]] = set()
    for token in re.split(r"[,;\s]+", raw.strip().upper()):
        match = _TOKEN_RE.fullmatch(token) if token else None
        if match is None:
            continue
        try:
            period = Period.from_year_and_code(int(match.group("year")), match.group("period"))
        except (PeriodError, ValueError):
            continue
        if not period.registry_token.endswith("T"):
            continue
        periods.add((period.filing_year, period.registry_token))
    return frozenset(periods)


def m115_no_relevant_payment_periods_from_profile_values(
    values: Mapping[str, str] | None,
) -> frozenset[tuple[int, str]]:
    """Return explicit attested periods from a profile projection."""
    if values is None:
        return frozenset[tuple[int, str]]()
    return parse_m115_no_relevant_payment_periods(values.get(M115_NO_RELEVANT_PAYMENT_PROFILE_PATH))


def m115_no_relevant_payment_periods_for_bucket(
    bucket_id: str,
    *,
    profile_path_values_reader: ProfilePathValuesReadPort,
) -> frozenset[tuple[int, str]]:
    """Load explicit Modelo 115 no-relevant-payment facts for one bucket."""
    return m115_no_relevant_payment_periods_from_profile_values(
        profile_path_values_reader.load_path_values(bucket_id=bucket_id),
    )


def is_m115_no_relevant_payment_period(
    *,
    filing_year: int,
    period_token: str,
    attested_periods: frozenset[tuple[int, str]],
) -> bool:
    """Whether the selected scheduled Modelo 115 period is explicitly attested."""
    return (filing_year, period_token) in attested_periods


__all__ = [
    "M115_NO_RELEVANT_PAYMENT_PROFILE_PATH",
    "is_m115_no_relevant_payment_period",
    "m115_no_relevant_payment_periods_for_bucket",
    "m115_no_relevant_payment_periods_from_profile_values",
    "parse_m115_no_relevant_payment_periods",
]
