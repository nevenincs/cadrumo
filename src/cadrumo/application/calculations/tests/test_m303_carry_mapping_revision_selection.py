"""Modelo 303 carry mapping resolves for the revision selected at each filing scope."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date

import pytest

from ....core.filing_producer_key import FilingProducerKey
from ....domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from ....domain.calculations.registry.errors import GovernedFactNotApplicableError
from ....domain.calculations.registry.export import resolve_export_layout
from ....domain.calculations.registry.facts.resolution import MappingFactQuery, ResolvedMappingFact
from ....domain.calculations.registry.schema_base import DateAxis
from ....domain.calculations.registry.schema_references import TemporalProjectionDirection
from ....domain.calculations.registry.tests.published_authority import PublishedGovernedFactSource
from ....domain.period import period_end_date
from ..m303_carry_ingress import m303_declaration_type_header_key

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_SUPPORT = PublishedGovernedFactSource().supported_filing_years()


@pytest.fixture
def authority_operation() -> Iterator[PinnedAuthorityOperation]:
    with bundled_indexed_authority().operation() as operation:
        yield operation


# Exercise every historical branch and the 2026 shared-end-date boundary.
@pytest.mark.parametrize("period", ("1T", "2T", "3T", "4T", "01", "02", "03", "08", "09", "12"))
@pytest.mark.parametrize("filing_year", _SUPPORT.years)
def test_carry_mapping_matches_the_selected_modelo_303_revision(
    authority_operation: PinnedAuthorityOperation,
    filing_year: int,
    period: str,
) -> None:
    header_key = m303_declaration_type_header_key(
        filing_year=filing_year,
        period=period,
        operation=authority_operation,
    )

    snapshot = authority_operation.snapshot("303", filing_year=filing_year, period=period)
    layout = resolve_export_layout(snapshot)
    disposition_fields = tuple(
        field
        for field in layout.fields_by_id.values()
        if field.producer_key is FilingProducerKey.FILING_RESULT_DISPOSITION
    )
    assert disposition_fields, "the export must expose the same official header that carry ingestion requires"
    assert all(
        field.producer_key is not None and field.producer_key.value == header_key for field in disposition_fields
    )
    assert header_key == FilingProducerKey.FILING_RESULT_DISPOSITION.value


@pytest.mark.parametrize(
    ("period", "revision_id", "variant_id"),
    (
        ("1T", "2026-hasta-01-y-1t", "modelo-303-carry-disposition-verification-mapping:2026-hasta-01-y-1t"),
        ("03", "2026-y-siguientes", "modelo-303-carry-disposition-verification-mapping:2026"),
    ),
)
def test_shared_end_date_retains_the_exact_monthly_or_quarterly_mapping(
    authority_operation: PinnedAuthorityOperation,
    period: str,
    revision_id: str,
    variant_id: str,
) -> None:
    effective_date = period_end_date(2026, period)
    assert effective_date == period_end_date(2026, "1T") == period_end_date(2026, "03")
    revision = authority_operation.revision_for_context("303", filing_year=2026, period=period, on=effective_date)
    resolved = authority_operation.resolve_governed_fact(
        MappingFactQuery(
            fact_id="modelo-303-carry-disposition-verification-mapping",
            date_axis=DateAxis.FILING_PERIOD,
            effective_date=effective_date,
            filing_year=2026,
            period=period,
        ),
    )

    assert isinstance(resolved, ResolvedMappingFact)
    entries = {entry.key: entry.value for entry in resolved.payload.entries}
    assert str(revision.id) == entries["revision"] == revision_id
    assert str(resolved.variant_id) == variant_id
    assert resolved.effective_date == effective_date
    assert resolved.authority_digest == authority_operation.pin().logical_generation
    assert (
        m303_declaration_type_header_key(
            filing_year=2026,
            period=period,
            operation=authority_operation,
        )
        == FilingProducerKey.FILING_RESULT_DISPOSITION.value
    )


@pytest.mark.parametrize("period", (None, "0A"), ids=("date-only", "unsupported-annual"))
def test_carry_mapping_refuses_an_absent_or_unsupported_period_coordinate(
    authority_operation: PinnedAuthorityOperation,
    period: str | None,
) -> None:
    with pytest.raises(GovernedFactNotApplicableError):
        authority_operation.resolve_governed_fact(
            MappingFactQuery(
                fact_id="modelo-303-carry-disposition-verification-mapping",
                date_axis=DateAxis.FILING_PERIOD,
                effective_date=period_end_date(2026, "4T"),
                filing_year=2026 if period is not None else None,
                period=period,
            ),
        )


@pytest.mark.parametrize("period", ("01", "1T"))
def test_future_periods_use_late_mapping_after_the_2026_override(
    authority_operation: PinnedAuthorityOperation,
    period: str,
) -> None:
    filing_year = 2027
    support = authority_operation.supported_filing_years()
    effective_date = period_end_date(filing_year, period)
    assert filing_year > support.horizon
    assert support.admits_filing_year(filing_year)

    revision = authority_operation.revision_for_context(
        "303", filing_year=filing_year, period=period, on=effective_date
    )
    resolved = authority_operation.resolve_governed_fact(
        MappingFactQuery(
            fact_id="modelo-303-carry-disposition-verification-mapping",
            date_axis=DateAxis.FILING_PERIOD,
            effective_date=effective_date,
            filing_year=filing_year,
            period=period,
        ),
    )

    assert isinstance(resolved, ResolvedMappingFact)
    entries = {entry.key: entry.value for entry in resolved.payload.entries}
    assert str(revision.id) == entries["revision"] == "2026-y-siguientes"
    assert str(resolved.variant_id) == "modelo-303-carry-disposition-verification-mapping:2026"
    assert period in revision.period_selector.periods_for_year(filing_year)
    assert period not in revision.period_selector.periods_for_year(2026)
    assert revision.valid_to is None
    assert resolved.effective_date == effective_date
    assert resolved.authority_digest == authority_operation.pin().logical_generation
    assert resolved.projection_direction is TemporalProjectionDirection.FORWARD
    assert resolved.projected_from_date == date(support.horizon, 12, 31)
    assert (
        m303_declaration_type_header_key(
            filing_year=filing_year,
            period=period,
            operation=authority_operation,
        )
        == FilingProducerKey.FILING_RESULT_DISPOSITION.value
    )
