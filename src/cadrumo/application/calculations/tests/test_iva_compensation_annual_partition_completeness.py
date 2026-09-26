"""Completeness evidence tests for the Modelo 390 annual compensation partition."""

from __future__ import annotations

from datetime import UTC, datetime
from functools import cache
from typing import override

import pytest

from ....core.aggregation import BindingSourceKind
from ....core.period import Period
from ....domain.calculations.registry.authority import bundled_indexed_authority
from ....domain.calculations.registry.bindings import RegistryModeloObservation
from ....domain.calculations.registry.schema import RegistrySnapshot
from ....domain.calculations.registry.tests.published_authority import published_snapshot
from ...aggregation.source_mesh import CalculationSourceContext
from ...modelo.tests.advisory_diagnostic_repositories import EmptyObservationRepository
from ..iva_compensation_annual_partition import (
    IvaCompensationAnnualPartitionSourceResolver,
    _annual_source_evidence_diagnostics,
)
from ..observations_repository import ObservationEnvelopePayload

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]


class _StaleObservationRepository(EmptyObservationRepository):
    """Observation port returning one stale M303 envelope for carry admission."""

    def __init__(self, payload: ObservationEnvelopePayload, period: Period) -> None:
        self._payload = payload
        self._period = period

    @override
    def load_observation(self, modelo: str, period: Period) -> ObservationEnvelopePayload | None:
        if modelo == str(self._payload.observation.modelo) and period == self._period:
            return self._payload
        return None


@cache
def _snapshot() -> RegistrySnapshot:
    return published_snapshot("390", filing_year=2025, period="0A")


def test_missing_required_m303_periods_emit_a_typed_annual_source_evidence_failure() -> None:
    snapshot = _snapshot()
    with bundled_indexed_authority().operation() as authority_operation:
        resolution = IvaCompensationAnnualPartitionSourceResolver(
            repository=EmptyObservationRepository(),
            registry_snapshot=snapshot,
            operation=authority_operation,
        ).resolve(
            CalculationSourceContext(
                bucket_id="annual-partition-completeness",
                modelo="390",
                filing_year=2025,
                period=Period.from_year_and_code(2025, "0A"),
                revision=snapshot.revision,
            ),
        )

    annual_diagnostics = tuple(
        diagnostic
        for diagnostic in resolution.diagnostics
        if diagnostic.reason == "iva_compensation_annual_source_evidence_failure"
    )
    assert annual_diagnostics
    assert {diagnostic.binding_source for diagnostic in annual_diagnostics} == {
        BindingSourceKind.IVA_COMPENSATION_ANNUAL_PARTITION
    }
    assert {diagnostic.binding_id for diagnostic in annual_diagnostics} == set(resolution.unresolved_binding_ids)


def test_annual_evidence_diagnostics_name_only_the_actual_unresolved_binding() -> None:
    snapshot = _snapshot()
    requirement_binding_ids = tuple(
        binding.id
        for binding in snapshot.revision.bindings
        if binding.source is BindingSourceKind.IVA_COMPENSATION_ANNUAL_PARTITION
    )
    unresolved_binding_id, resolved_binding_id = requirement_binding_ids

    diagnostics = _annual_source_evidence_diagnostics(
        binding_ids=(unresolved_binding_id,),
        resolver_id="iva_compensation_annual_partition",
    )

    assert [diagnostic.binding_id for diagnostic in diagnostics] == [unresolved_binding_id]
    assert resolved_binding_id not in {diagnostic.binding_id for diagnostic in diagnostics}


def test_stale_m303_source_is_refused_during_carry_admission_and_leaves_bindings_unresolved() -> None:
    stale_observation = ObservationEnvelopePayload.model_validate(
        {
            "observation": RegistryModeloObservation(modelo="303", filing_year=2025, period="1T"),
            "captured_at": datetime(2026, 1, 1, tzinfo=UTC),
            "source_kind": "app_filing",
            "stamped_revision_id": "stale-revision",
        },
        context={"canonical_m303_ingress_candidate": True},
    )
    snapshot = _snapshot()
    with bundled_indexed_authority().operation() as authority_operation:
        resolution = IvaCompensationAnnualPartitionSourceResolver(
            repository=_StaleObservationRepository(stale_observation, Period.from_year_and_code(2025, "1T")),
            registry_snapshot=snapshot,
            operation=authority_operation,
        ).resolve(
            CalculationSourceContext(
                bucket_id="annual-partition-completeness",
                modelo="390",
                filing_year=2025,
                period=Period.from_year_and_code(2025, "0A"),
                revision=snapshot.revision,
            ),
        )

    assert not resolution.binding_values
    annual_diagnostics = tuple(
        diagnostic
        for diagnostic in resolution.diagnostics
        if diagnostic.reason == "iva_compensation_annual_source_evidence_failure"
    )
    assert {diagnostic.binding_id for diagnostic in annual_diagnostics} == set(resolution.unresolved_binding_ids)
