"""Modelo 115 explicit no-relevant-payment attestations.

An empty Modelo 115 observation window is not evidence of a zero return.  The
operator may instead persist a period-scoped attestation that no payment subject
to urban-rent withholding occurred.  Only that explicit fact permits the
calculation path to materialise the model's canonical zero values.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Final

from ...core.period import Period
from ..user_profile.profile_read_ports import ProfilePathValuesReadPort
from .attested_period_tokens import parse_attested_period_keys

M115_NO_RELEVANT_PAYMENT_PROFILE_PATH: Final = "withholding.modelo_115_no_relevant_payment_periods"
"""Profile fact carrying comma-separated ``YYYY:PERIOD`` Modelo 115 attestations."""


def _is_quarterly_period(period: Period) -> bool:
    return period.registry_token.endswith("T")


def m115_no_relevant_payment_periods_from_profile_values(
    values: Mapping[str, str] | None,
) -> frozenset[tuple[int, str]]:
    """Return explicit attested periods from a profile projection."""
    if values is None:
        return frozenset[tuple[int, str]]()
    # Invalid tokens attest nothing: malformed profile input leaves the normal
    # missing-observation refusal in force.
    return parse_attested_period_keys(
        values.get(M115_NO_RELEVANT_PAYMENT_PROFILE_PATH),
        accepts=_is_quarterly_period,
    )


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
]
