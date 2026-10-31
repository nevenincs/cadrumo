"""A recorded claim goes stale on a revision only when a fact its charge rests on changed.

The figure of a claim rests on the basis, the service date and the election.  The documents
that evidence the acquisition and the declared date and activity move no figure, so a correction
that changes only them leaves every claim current.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from decimal import Decimal

import pytest

from cadrumo.application.actividad_asset.activity_asset_read_models import ActivityAssetClaimStaleReason
from cadrumo.application.actividad_asset.operations import ActivityAssetOperations
from cadrumo.core.tipos_actividad import TipoActividad
from cadrumo.domain.renta.actividad_asset.election import DirectEstimationRegime
from cadrumo.domain.renta.actividad_asset.lifecycle import (
    AcquisitionLineageReference,
    AcquisitionShape,
    ActivityAssetRevision,
)
from cadrumo.domain.renta.actividad_asset.register_records import ActivityAssetDescriptorFacts

from .ledger_support import MemoryLedger
from .operations_support import ACQUISITION, build_forecast, build_revision
from .register_support import MemoryRepository, memory_register_authority

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_ASSET = "laptop-1"


def _restated(revision: ActivityAssetRevision, **changes: object) -> ActivityAssetRevision:
    facts = {name: getattr(revision, name) for name in type(revision).model_fields}
    facts.update(
        revision_number=revision.revision_number + 1,
        supersedes_revision_id=revision.revision_id,
        **changes,
    )
    return ActivityAssetRevision(**facts)


def _outside_the_ledger() -> ActivityAssetRevision:
    """Build the element acquired outside the ledger, the shape that declares its own date and activity."""
    base = build_revision()
    facts = {name: getattr(base, name) for name in type(base).model_fields}
    facts.update(
        acquisition=AcquisitionLineageReference(invoice_evidence_id="document-1"),
        acquisition_shape=AcquisitionShape.ACQUIRED_OUTSIDE_LEDGER,
        declared_acquisition_date=date(2024, 12, 1),
        declared_activity=next(iter(TipoActividad)),
    )
    return ActivityAssetRevision(**facts)


def _lineage(first: ActivityAssetRevision, **changes: object) -> AcquisitionLineageReference:
    return first.acquisition.model_copy(update=changes)


_Changes = Callable[[ActivityAssetRevision], dict[str, object]]

_NEUTRAL_OUTSIDE_THE_LEDGER: dict[str, _Changes] = {
    "invoice_evidence_id": lambda first: {"acquisition": _lineage(first, invoice_evidence_id="document-2")},
    "declared_acquisition_date": lambda first: {"declared_acquisition_date": date(2024, 11, 20)},
    "declared_activity": lambda first: {"declared_activity": tuple(TipoActividad)[1]},
}

_NEUTRAL_ON_THE_LEDGER: dict[str, _Changes] = {
    "invoice_evidence_id": lambda first: {"acquisition": _lineage(first, invoice_evidence_id="invoice-2")},
    "evidence_fingerprint": lambda first: {"acquisition": _lineage(first, evidence_fingerprint="c" * 64)},
}

_SENSITIVE: dict[str, _Changes] = {
    "basis": lambda first: {"basis": build_revision(basis="1000").basis},
    "in_service_date": lambda first: {"in_service_date": date(2025, 2, 1)},
    "amortization": lambda first: {"amortization": build_revision(class_key="maquinaria").amortization},
}


def _stale_reasons(
    operations: ActivityAssetOperations,
    claim_id: str,
) -> tuple[ActivityAssetClaimStaleReason | None, ActivityAssetClaimStaleReason | None]:
    plan = next(claim for row in operations.plan(_ASSET) for claim in row.claims if claim.claim_id == claim_id)
    timeline = next(
        event.claim for event in operations.timeline(_ASSET) if event.claim is not None and event.record_id == claim_id
    )
    return plan.stale_reason, timeline.stale_reason


def _claimed_then_corrected(first: ActivityAssetRevision, changes: _Changes) -> tuple[ActivityAssetOperations, str]:
    operations = ActivityAssetOperations(
        repository=MemoryRepository(),
        ledger=MemoryLedger(ACQUISITION),
        forecast_operation=build_forecast,
        taxpayer_modality=lambda: DirectEstimationRegime.SIMPLIFIED,
        register_authority=memory_register_authority(),
    )
    operations.create(first, ActivityAssetDescriptorFacts(name="Laptop"))
    claim_id = operations.record_claim(
        operations.forecast(asset_id=_ASSET, covered_from=date(2025, 1, 1), covered_until=date(2026, 1, 1)),
        creating_operation="test.claim",
    ).claim.claim_id
    operations.correct(_restated(first, **changes(first)), origin="test.correct")
    return operations, claim_id


@pytest.mark.parametrize("field", sorted(_NEUTRAL_OUTSIDE_THE_LEDGER))
def test_a_correction_of_a_fact_no_charge_rests_on_leaves_the_claim_current_outside_the_ledger(field: str) -> None:
    operations, claim_id = _claimed_then_corrected(_outside_the_ledger(), _NEUTRAL_OUTSIDE_THE_LEDGER[field])

    assert _stale_reasons(operations, claim_id) == (None, None)


@pytest.mark.parametrize("field", sorted(_NEUTRAL_ON_THE_LEDGER))
def test_a_correction_of_a_fact_no_charge_rests_on_leaves_the_claim_current_on_the_ledger(field: str) -> None:
    operations, claim_id = _claimed_then_corrected(build_revision(), _NEUTRAL_ON_THE_LEDGER[field])

    assert _stale_reasons(operations, claim_id) == (None, None)


@pytest.mark.parametrize("field", sorted(_SENSITIVE))
def test_a_correction_of_a_fact_a_charge_rests_on_marks_the_claim_stale_on_both_reads(field: str) -> None:
    operations, claim_id = _claimed_then_corrected(build_revision(), _SENSITIVE[field])

    assert _stale_reasons(operations, claim_id) == (
        ActivityAssetClaimStaleReason.REVISION_CHANGED,
        ActivityAssetClaimStaleReason.REVISION_CHANGED,
    )


def test_the_next_figure_is_unchanged_by_a_neutral_correction() -> None:
    operations, _ = _claimed_then_corrected(build_revision(), _NEUTRAL_ON_THE_LEDGER["invoice_evidence_id"])

    charge = operations.forecast(asset_id=_ASSET, covered_from=date(2026, 1, 1), covered_until=date(2027, 1, 1))

    assert charge.amount == Decimal("520.00")
