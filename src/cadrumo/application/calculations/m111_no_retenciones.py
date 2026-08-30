"""Modelo 111 no-retenciones period attestations."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Final

from ...core.modelo import Modelo
from ...core.period import Period, PeriodError

M111_NO_RETENCIONES_PROFILE_PATH: Final = "withholding.modelo_111_no_retenciones_periods"
"""Profile fact carrying comma-separated ``YYYY:PERIOD`` no-obligation M111 periods."""

_TOKEN_RE: Final = re.compile(r"^(?P<year>\d{4}):(?P<period>[A-Z0-9]+)$")


def parse_m111_no_retenciones_periods(raw: str | None) -> frozenset[tuple[int, str]]:
    """Parse profile ``YYYY:PERIOD`` tokens into validated period keys.

    Invalid tokens are ignored fail-closed: they never suppress a dependency, so
    verification still asks for the missing filing/evidence instead of silently
    treating an unclear declaration as no-obligation evidence.
    """
    if raw is None:
        return frozenset[tuple[int, str]]()
    periods: set[tuple[int, str]] = set()
    for token in re.split(r"[,;\s]+", raw.strip().upper()):
        if not token:
            continue
        match = _TOKEN_RE.fullmatch(token)
        if match is None:
            continue
        year = int(match.group("year"))
        period_token = match.group("period")
        try:
            period = Period.from_year_and_code(year, period_token)
        except (PeriodError, ValueError):
            continue
        periods.add((period.filing_year, period.registry_token))
    return frozenset(periods)


def m111_no_retenciones_periods_from_profile_values(values: Mapping[str, str] | None) -> frozenset[tuple[int, str]]:
    """Return attested M111 no-retenciones periods from a profile projection."""
    if values is None:
        return frozenset[tuple[int, str]]()
    return parse_m111_no_retenciones_periods(values.get(M111_NO_RETENCIONES_PROFILE_PATH))


def m111_no_retenciones_periods_for_bucket(bucket_id: str) -> frozenset[tuple[int, str]]:
    """Load attested M111 no-retenciones periods for ``bucket_id``.

    Missing profiles fail closed to an empty set.
    """
    from ...domain.user_profile.errors import ProfileNotFoundError
    from ..user_profile.profile_record_repository import ProfileRecordRepository
    from ..user_profile.projections import record_to_path_values

    try:
        record = ProfileRecordRepository.for_current_session(bucket_id).load(bucket_id)
    except ProfileNotFoundError:
        return frozenset[tuple[int, str]]()
    return m111_no_retenciones_periods_from_profile_values(record_to_path_values(record))


def is_m111_no_retenciones_period(
    *,
    source_modelo: str,
    filing_year: int,
    period_token: str,
    attested_periods: frozenset[tuple[int, str]],
) -> bool:
    """Return whether a source requirement is attested as no-obligation M111."""
    return source_modelo == Modelo.M111.value and (filing_year, period_token) in attested_periods


__all__ = [
    "M111_NO_RETENCIONES_PROFILE_PATH",
    "is_m111_no_retenciones_period",
    "m111_no_retenciones_periods_for_bucket",
    "m111_no_retenciones_periods_from_profile_values",
    "parse_m111_no_retenciones_periods",
]
