"""A Modelo 720 re-declaration reads each year's obligation blocks at that year's end, never at the run date."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from ....core.casilla_id import validated_casilla_id
from ....core.time.clock import frozen_clock
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.bindings import CasillaObservation, RegistryModeloObservation
from ....domain.calculations.registry.facts.resolution import GovernedFactQuery, ResolvedGovernedFact
from ....domain.calculations.registry.governed_fact_scope import validating_governed_facts
from ....domain.calculations.registry.schema_references import TemporalSupportEnvelope
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ..foreign_asset_redeclaration import modelo_720_redeclaration_advisory_findings

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_CUENTAS_VALORACION = validated_casilla_id("cuentas.valoracion")


class _DateRecordingSource:
    """Delegate every governed-fact read to the pinned operation, keeping the date each one asked for."""

    def __init__(self, inner: PinnedAuthorityOperation) -> None:
        self._inner = inner
        self.asked: list[date] = []

    def resolve_governed_fact(self, query: GovernedFactQuery) -> ResolvedGovernedFact:
        self.asked.append(query.effective_date)
        return self._inner.resolve_governed_fact(query)

    def supported_filing_years(self) -> TemporalSupportEnvelope:
        return self._inner.supported_filing_years()


def _cuentas_observation(filing_year: int, valuation_eur: Decimal | None) -> RegistryModeloObservation:
    observations = (
        ()
        if valuation_eur is None
        else (
            CasillaObservation(
                casilla_id=_CUENTAS_VALORACION,
                value=valuation_eur,
                legal_refs=("ley-58-2003:da-18",),
                source_refs=("aeat-modelo-720-procedure",),
            ),
        )
    )
    return RegistryModeloObservation(modelo="720", filing_year=filing_year, period="0A", observations=observations)


def test_each_year_s_obligation_blocks_are_read_at_its_own_year_end_whatever_the_run_date(
    operation: PinnedAuthorityOperation,
) -> None:
    current_year = filing_year_envelope().horizon
    prior_year = current_year - 1
    recorder = _DateRecordingSource(operation)
    run_date_outside_the_envelope = datetime(filing_year_envelope().floor - 3, 6, 15, 12, tzinfo=UTC)

    with frozen_clock(run_date_outside_the_envelope), validating_governed_facts(recorder):
        findings = modelo_720_redeclaration_advisory_findings(
            prior_observation=_cuentas_observation(prior_year, Decimal("60000.00")),
            current_observation=_cuentas_observation(current_year, Decimal("100000.00")),
            current_declaration_observation=_cuentas_observation(current_year, None),
            operation=operation,
        )

    assert len(findings) == 1
    assert findings[0].message_facts["group_code"] == "cuentas"
    assert recorder.asked
    assert set(recorder.asked) == {date(prior_year, 12, 31), date(current_year, 12, 31)}
