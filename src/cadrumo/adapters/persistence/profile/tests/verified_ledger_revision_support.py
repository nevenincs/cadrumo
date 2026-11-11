"""A verified Modelo 303 revision over one ledger row, carrying either kind of ledger filing record."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from .....core.casilla_id import validated_casilla_id
from .....core.period import Period
from .....domain.calculations.registry.schema_references import RegistrySnapshotRef
from .....domain.calculations.registry.tests.registry_observations import registry_grounded_observations
from .....domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from .....domain.modelos.calculation_revision_m303_handoff import FilingInstanceEvidence
from .....domain.modelos.ledger_filing_snapshot import LedgerFilingEvidence, LedgerFilingSnapshot

_REVISION_CASILLA = validated_casilla_id("01")


def verified_303_ledger_revision(
    *,
    work_unit_id: str,
    registry_snapshot_ref: RegistrySnapshotRef,
    filing_instance_evidence: FilingInstanceEvidence,
    tx_id: str,
    period: Period,
    at: datetime,
    ledger_filing_snapshot: LedgerFilingSnapshot | None = None,
    ledger_filing_evidence: LedgerFilingEvidence | None = None,
) -> CalculationRevision:
    """Return a 2025 Modelo 303 revision verified complete at ``at`` whose one casilla is fed by the row ``tx_id``."""
    revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit_id,
        input_values_by_casilla_id={_REVISION_CASILLA: "1"},
        binding_overrides={},
        casilla_values={_REVISION_CASILLA: Decimal("1")},
        source_transaction_ids=(tx_id,),
        filing_instance_evidence=filing_instance_evidence,
        source_provenance=(),
    )
    return CalculationRevision(
        calculation_revision_id=revision_id,
        work_unit_id=work_unit_id,
        registry_snapshot_ref=registry_snapshot_ref,
        state=CalculationRevisionState.VERIFICADO_COMPLETO,
        input_values_by_casilla_id={_REVISION_CASILLA: "1"},
        binding_overrides={},
        source_transaction_ids=(tx_id,),
        casilla_values={_REVISION_CASILLA: Decimal("1")},
        observations=registry_grounded_observations(
            modelo="303",
            filing_year=2025,
            period=period.registry_token,
            casilla_values={_REVISION_CASILLA: Decimal("1")},
        ),
        created_at=at,
        updated_at=at,
        verified_at=at,
        verified_by="operator",
        ledger_filing_snapshot=ledger_filing_snapshot,
        ledger_filing_evidence=ledger_filing_evidence,
        filing_instance_evidence=filing_instance_evidence,
        source_provenance=(),
    )
