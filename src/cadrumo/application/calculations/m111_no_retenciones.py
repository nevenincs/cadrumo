"""Modelo 111 no-retenciones period attestations.

AEAT instructions say no Modelo 111 is presented for a period in which no
subject rents were paid. A later fold may therefore skip such a period, but
only when the taxpayer has attested it explicitly and only for Modelo 111
sources; every other dependency keeps its full evidence requirement.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Final

from ...core.modelo import Modelo
from ...core.period import Period, PeriodError
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.errors import RegistrySnapshotError, RegistryValidationError
from ..user_profile.profile_read_ports import ProfilePathValuesReadPort

M111_NO_RETENCIONES_PROFILE_PATH: Final = "withholding.modelo_111_no_retenciones_periods"
"""Profile fact carrying comma-separated ``YYYY:PERIOD`` no-obligation Modelo 111 periods."""

_TOKEN_RE: Final = re.compile(r"^(?P<year>\d{4}):(?P<period>[A-Z0-9]+)$")


def parse_m111_no_retenciones_periods(raw: str | None) -> frozenset[tuple[int, str]]:
    """Parse profile ``YYYY:PERIOD`` tokens into validated period keys.

    Invalid tokens are ignored fail-closed: they never suppress a dependency, so
    verification still asks for the missing filing or evidence instead of
    treating an unclear declaration as no-obligation evidence.
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
        periods.add((period.filing_year, period.registry_token))
    return frozenset(periods)


def m111_no_retenciones_periods_from_profile_values(values: Mapping[str, str] | None) -> frozenset[tuple[int, str]]:
    """Return attested Modelo 111 no-retenciones periods from a profile projection."""
    if values is None:
        return frozenset[tuple[int, str]]()
    return parse_m111_no_retenciones_periods(values.get(M111_NO_RETENCIONES_PROFILE_PATH))


def m111_no_retenciones_periods_for_bucket(
    bucket_id: str,
    *,
    profile_path_values_reader: ProfilePathValuesReadPort,
) -> frozenset[tuple[int, str]]:
    """Load the attested periods for ``bucket_id``; a missing profile attests nothing."""
    return m111_no_retenciones_periods_from_profile_values(
        profile_path_values_reader.load_path_values(bucket_id=bucket_id),
    )


def _registry_declares_period(
    *,
    modelo: str,
    filing_year: int,
    period_token: str,
    operation: PinnedAuthorityOperation,
) -> bool:
    """Whether the selected revision schedules ``period_token`` for ``modelo``."""
    try:
        snapshot = operation.snapshot(modelo, filing_year=filing_year, period=period_token)
    except (RegistrySnapshotError, RegistryValidationError):
        return False
    return any(period_token in schedule.periods for schedule in snapshot.filing_schedules.values())


def is_m111_no_retenciones_period(
    *,
    source_modelo: str,
    filing_year: int,
    period_token: str,
    attested_periods: frozenset[tuple[int, str]],
    operation: PinnedAuthorityOperation,
) -> bool:
    """Return whether a source requirement is an attested no-obligation Modelo 111 period."""
    if source_modelo != Modelo("111").value or (filing_year, period_token) not in attested_periods:
        return False
    return _registry_declares_period(
        modelo=source_modelo,
        filing_year=filing_year,
        period_token=period_token,
        operation=operation,
    )


__all__ = [
    "M111_NO_RETENCIONES_PROFILE_PATH",
    "is_m111_no_retenciones_period",
    "m111_no_retenciones_periods_for_bucket",
    "m111_no_retenciones_periods_from_profile_values",
    "parse_m111_no_retenciones_periods",
]
