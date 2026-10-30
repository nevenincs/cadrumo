"""The verify-time drift gate compares the register state a draft consumed with the register now.

Hand-worked: a draft that recorded claim ``C1`` and fingerprint ``F1`` is current
while the register yields exactly ``{C1}`` and ``{F1}``, and stale as soon as
either set differs, whether by an addition, a supersession or a changed schedule.
The revision, its provenance rows and the gate are the real ones.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from cadrumo.core.aggregation import BindingSourceKind, CalculationSourceLineageRole
from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.tests.published_authority import published_snapshot
from cadrumo.domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from cadrumo.domain.modelos.calculation_revision_sources import ActivityAssetConsumption, CalculationSourceRef
from cadrumo.domain.modelos.codes import ModeloCode
from cadrumo.domain.modelos.verification_report import ModeloVerificationFinding
from cadrumo.domain.modelos.work_unit import WorkUnit, derive_work_unit_id
from cadrumo.domain.transactions.models import TransactionCatalogue

from ...aggregation.ledger_membership import LedgerSourceMembership
from .._ledger_drift_gate import ledger_drift_findings

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_BUCKET = "28282828-2828-4828-8828-282828282828"
_AT = datetime(2026, 4, 20, 12, 0, tzinfo=UTC)
_KEY = "application.modelo.findings.activity_asset_register_drift"
_C1, _C2 = "1" * 64, "2" * 64
_F1, _F2 = "a" * 64, "b" * 64


class _Transactions:
    """The ledger side is not under test: no row contributes, so the anchor is absent."""

    def load(self) -> TransactionCatalogue:
        return TransactionCatalogue()


def _provenance(*source_refs: str) -> tuple[CalculationSourceRef, ...]:
    return tuple(
        CalculationSourceRef(
            resolver_id="ledger_renta_gastos_pago_fraccionado_aggregation",
            resolved_binding_source=BindingSourceKind.LEDGER_RENTA_GASTOS_PAGO_FRACCIONADO_AGGREGATION,
            contributor_source_kind="activity_asset",
            contributor_binding_source=None,
            lineage_role=CalculationSourceLineageRole.PRIMARY,
            source_ref=source_ref,
            parent_source_ref=None,
        )
        for source_ref in source_refs
    )


def _draft(*source_refs: str) -> tuple[WorkUnit, CalculationRevision]:
    snapshot = published_snapshot("130", filing_year=2025, period="1T")
    period = Period.from_year_and_code(2025, "1T")
    work_unit = WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=_BUCKET,
            modelo="130",
            filing_year=2025,
            period=period,
            revision_id=snapshot.revision.id,
        ),
        bucket_id=_BUCKET,
        modelo=ModeloCode("130"),
        filing_year=2025,
        period=period,
        revision_id=snapshot.revision.id,
        name="130-2025-1T",
        created_at=_AT,
        updated_at=_AT,
    )
    provenance = _provenance(*source_refs)
    revision = CalculationRevision(
        calculation_revision_id=derive_calculation_revision_id(
            work_unit_id=work_unit.work_unit_id,
            input_values_by_casilla_id={},
            binding_overrides={},
            casilla_values={},
            filing_instance_evidence=None,
            source_provenance=provenance,
        ),
        work_unit_id=work_unit.work_unit_id,
        registry_snapshot_ref=snapshot.snapshot_ref,
        state=CalculationRevisionState.BORRADOR,
        input_values_by_casilla_id={},
        binding_overrides={},
        casilla_values={},
        observations=(),
        created_at=_AT,
        updated_at=_AT,
        filing_instance_evidence=None,
        source_provenance=provenance,
    )
    return work_unit, revision


def _gate(draft: tuple[WorkUnit, CalculationRevision], *current_refs: str) -> list[ModeloVerificationFinding]:
    work_unit, revision = draft
    return ledger_drift_findings(
        target=revision,
        work_unit=work_unit,
        transaction_repository=_Transactions(),
        current_membership=LedgerSourceMembership(
            activity_asset_consumption=ActivityAssetConsumption.from_source_refs(current_refs),
        ),
    )


def _facts(findings: list[ModeloVerificationFinding]) -> tuple[object, object, object]:
    (finding,) = findings
    assert finding.message_locale_key == _KEY
    facts = finding.message_facts
    return facts["claims_added"], facts["claims_removed"], facts["schedules_changed"]


def test_the_revision_records_the_claims_and_schedules_it_consumed() -> None:
    _, revision = _draft(
        f"activity-asset-claim:{_C2}",
        f"activity-asset-claim:{_C1}",
        f"activity-asset-schedule:{_F1}",
        "transaction:" + "9" * 64,
    )

    assert revision.activity_asset_consumption.claim_ids == (_C1, _C2)
    assert revision.activity_asset_consumption.schedule_fingerprints == (_F1,)


def test_an_identical_re_read_leaves_the_draft_current() -> None:
    refs = (f"activity-asset-claim:{_C1}", f"activity-asset-schedule:{_F1}")

    assert _gate(_draft(*refs), *reversed(refs)) == []


def test_a_claim_recorded_after_calculation_makes_the_draft_stale() -> None:
    draft = _draft(f"activity-asset-claim:{_C1}")

    assert _facts(_gate(draft, f"activity-asset-claim:{_C1}", f"activity-asset-claim:{_C2}")) == (1, 0, 0)


def test_a_claim_first_recorded_on_a_draft_that_consumed_none_makes_it_stale() -> None:
    assert _facts(_gate(_draft(), f"activity-asset-claim:{_C1}")) == (1, 0, 0)


def test_superseding_a_consumed_claim_makes_the_draft_stale() -> None:
    draft = _draft(f"activity-asset-claim:{_C1}")

    assert _facts(_gate(draft, f"activity-asset-claim:{_C2}")) == (1, 1, 0)


def test_a_changed_schedule_fingerprint_makes_the_draft_stale() -> None:
    draft = _draft(f"activity-asset-schedule:{_F1}")

    assert _facts(_gate(draft, f"activity-asset-schedule:{_F2}")) == (0, 0, 1)


def test_unrelated_provenance_neither_hides_nor_causes_drift() -> None:
    draft = _draft(f"activity-asset-claim:{_C1}", "transaction:" + "9" * 64)

    assert _gate(draft, f"activity-asset-claim:{_C1}", "invoice:" + "8" * 64) == []
