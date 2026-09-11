"""Generic schedule-attestation mechanics for registry-selected declarations."""

from __future__ import annotations

from collections.abc import Mapping

from ...domain.calculations.registry.authority import bundled_authority
from ...domain.calculations.registry.queries import RegistryQueryService
from ...domain.calculations.registry.schema import ModeloRevision


# fact-relocation: M111 schedule and applicability are consumed through RegistryQueryService
def _registry_no_retenciones_periods(
    revision: ModeloRevision | None = None,
    *,
    modelo: str | None = None,
    filing_year: int | None = None,
    period_token: str | None = None,
) -> frozenset[tuple[int, str]]:
    """Resolve a declared filing period through the generic registry query."""
    del revision
    if modelo is None or filing_year is None or period_token is None:
        return frozenset()
    report = RegistryQueryService(bundled_authority()).describe_modelo(modelo, period=period_token)
    if report.period != period_token:
        return frozenset()
    return frozenset({(filing_year, period_token)})


def parse_m111_no_retenciones_periods(
    raw: str | None,
    *,
    modelo: str | None = None,
    filing_year: int | None = None,
    period_token: str | None = None,
    revision: ModeloRevision | None = None,
) -> frozenset[tuple[int, str]]:
    """Resolve schedule-attestation periods through registry authority."""
    del raw
    return _registry_no_retenciones_periods(
        revision,
        modelo=modelo,
        filing_year=filing_year,
        period_token=period_token,
    )


def m111_no_retenciones_periods_from_profile_values(
    values: Mapping[str, str] | None,
    *,
    modelo: str | None = None,
    filing_year: int | None = None,
    period_token: str | None = None,
    revision: ModeloRevision | None = None,
) -> frozenset[tuple[int, str]]:
    """Resolve schedule-attestation periods through registry authority."""
    del values
    return _registry_no_retenciones_periods(
        revision,
        modelo=modelo,
        filing_year=filing_year,
        period_token=period_token,
    )


def m111_no_retenciones_periods_for_bucket(
    bucket_id: str,
    *,
    filing_year: int | None = None,
    period_token: str | None = None,
    revision: ModeloRevision | None = None,
) -> frozenset[tuple[int, str]]:
    """Resolve a bucket's declared periods through registry authority."""
    return _registry_no_retenciones_periods(
        revision,
        modelo=bucket_id,
        filing_year=filing_year,
        period_token=period_token,
    )


def is_m111_no_retenciones_period(
    *,
    source_modelo: str,
    filing_year: int,
    period_token: str,
    attested_periods: frozenset[tuple[int, str]],
) -> bool:
    """Resolve whether a source period is covered by registry schedule data."""
    del attested_periods
    return (filing_year, period_token) in _registry_no_retenciones_periods(
        modelo=source_modelo,
        filing_year=filing_year,
        period_token=period_token,
    )


__all__ = [
    "is_m111_no_retenciones_period",
    "m111_no_retenciones_periods_for_bucket",
    "m111_no_retenciones_periods_from_profile_values",
    "parse_m111_no_retenciones_periods",
]
