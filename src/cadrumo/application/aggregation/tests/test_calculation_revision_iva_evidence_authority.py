"""IVA evidence duties resolve from the filing frame and fail closed on a stale reference."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from ....core.modelo import Modelo
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from ..evidence_advisory import calculation_revision_claims_ledger_iva

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]


@pytest.mark.parametrize(
    ("modelo", "stale_reference", "requires_iva_evidence"),
    [(Modelo("130"), False, False), (Modelo("303"), False, True), (Modelo("130"), True, True)],
    ids=["irpf-without-iva-duty", "iva-duty", "stale-irpf-reference-fails-closed"],
)
def test_revision_iva_evidence_duty_uses_the_resolved_filing_frame(
    operation: PinnedAuthorityOperation,
    modelo: Modelo,
    stale_reference: bool,
    requires_iva_evidence: bool,
) -> None:
    snapshot = operation.snapshot(modelo, filing_year=2026, period="1T")
    reference = snapshot.snapshot_ref
    if stale_reference:
        reference = reference.model_copy(update={"revision_id": "different-stored-revision"})
    now = datetime(2026, 4, 16, tzinfo=UTC)
    revision = CalculationRevision(
        calculation_revision_id=derive_calculation_revision_id(
            work_unit_id="a" * 64,
            input_values_by_casilla_id={},
            binding_overrides={},
            casilla_values={},
            source_provenance=(),
            filing_instance_evidence=None,
        ),
        work_unit_id="a" * 64,
        registry_snapshot_ref=reference,
        state=CalculationRevisionState.BORRADOR,
        source_provenance=(),
        filing_instance_evidence=None,
        created_at=now,
        updated_at=now,
    )
    assert calculation_revision_claims_ledger_iva(revision, operation=operation) is requires_iva_evidence
