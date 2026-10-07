"""Saved review values must never be replaced with live or inferred amounts."""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import pytest

from ....core.casilla_id import CasillaId
from ....core.period import Period
from ....domain.calculations.registry.bindings import CasillaObservation, CasillaObservationValueKind
from ....domain.calculations.registry.schema_references import RegistrySnapshotRef
from ....domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from ....domain.modelos.calculation_revision_operator_layer import CalculationOperatorLayer
from ....domain.modelos.ledger_filing_snapshot import (
    LedgerEvidenceRow,
    LedgerFilingEvidence,
    LedgerFilingSnapshot,
    LedgerRowFingerprint,
)
from ....domain.modelos.work_unit import WorkUnit, derive_work_unit_id
from ..review_snapshot import CalculationReviewSelection, EvidenceDisposition, ReviewSourceKind, ReviewStatus
from ..review_snapshot_loader import build_calculation_review_snapshot

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _saved(
    *, manual: bool = False, operator_layer: CalculationOperatorLayer | None = None, computed: bool = False
) -> tuple[CalculationReviewSelection, CalculationRevision, WorkUnit]:
    profile_id = UUID("5aa00000-0000-4000-8000-0000000000aa")
    instant = datetime(2026, 3, 10, 12, tzinfo=UTC)
    period = Period.from_year_and_code(2026, "1T")
    unit = WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=str(profile_id), modelo="303", filing_year=2026, period=period, revision_id="test-revision"
        ),
        bucket_id=str(profile_id),
        modelo="303",
        filing_year=2026,
        period=period,
        revision_id="test-revision",
        name="Saved synthetic example",
        created_at=instant,
        updated_at=instant,
    )
    casilla: CasillaId = "01"
    values = {casilla: Decimal("123.4500")}
    inputs = {casilla: "123.4500"} if manual else {}
    revision_id = derive_calculation_revision_id(
        work_unit_id=unit.work_unit_id,
        input_values_by_casilla_id=inputs,
        binding_overrides={},
        casilla_values=values,
        filing_instance_evidence=None,
        source_provenance=(),
        operator_layer=operator_layer,
    )
    reference = RegistrySnapshotRef(modelo="303", revision_id="test-revision", modelo_year=2026, period="1T")
    revision = CalculationRevision(
        calculation_revision_id=revision_id,
        work_unit_id=unit.work_unit_id,
        registry_snapshot_ref=reference,
        state=CalculationRevisionState.BORRADOR,
        input_values_by_casilla_id=inputs,
        operator_layer=operator_layer,
        casilla_values=values,
        observations=(
            CasillaObservation(
                casilla_id=casilla,
                value=values[casilla],
                formula_id="test-formula" if computed else None,
                legal_refs=("test-law",),
                source_refs=("test-source",),
            ),
        ),
        created_at=instant,
        updated_at=instant,
        filing_instance_evidence=None,
        source_provenance=(),
    )
    selection = CalculationReviewSelection(
        profile_id=profile_id,
        work_unit_id=unit.work_unit_id,
        calculation_revision_id=revision_id,
        modelo="303",
        filing_year=2026,
        period="1T",
        registry_snapshot_ref=reference,
        authority_generation="e" * 64,
        registry_digest="f" * 64,
    )
    return selection, revision, unit


def test_saved_decimal_is_preserved_without_inventing_attribution() -> None:
    selection, revision, unit = _saved()
    snapshot = build_calculation_review_snapshot(selection=selection, revision=revision, work_unit=unit)
    assert str(snapshot.amounts[0].value) == "123.4500"
    assert snapshot.amounts[0].currency is None
    assert snapshot.amounts[0].legal_refs == ("test-law",)
    assert snapshot.contributions[0].kind is ReviewSourceKind.UNAVAILABLE
    assert snapshot.status is ReviewStatus.INCOMPLETE
    assert not snapshot.ledger_rows


def test_legacy_revision_wire_has_no_rendering_capsule_and_retains_identity() -> None:
    _, revision, _ = _saved()
    wire = revision.model_dump_json(context={"secure_calculation_revision": True})
    assert '"rendering_snapshot"' not in wire
    restored = CalculationRevision.model_validate_json(wire, context={"secure_calculation_revision": True})
    assert restored.rendering_snapshot is None
    assert restored.calculation_revision_id == revision.calculation_revision_id


def test_legacy_text_observation_is_in_digest_bound_review_without_current_template() -> None:
    selection, revision, unit = _saved()
    text = CasillaObservation(
        casilla_id="decl.periodo",
        value="1T",
        value_kind=CasillaObservationValueKind.TEXT,
        legal_refs=("test-law",),
        source_refs=("test-source",),
    )
    revision = revision.model_copy(update={"observations": (*revision.observations, text)})
    snapshot = build_calculation_review_snapshot(selection=selection, revision=revision, work_unit=unit)
    assert snapshot.saved_form is None
    assert snapshot.text_values[0].value == "1T"
    assert snapshot.text_values[0].casilla_id == "decl.periodo"


def test_exact_manual_input_is_distinguished_from_unknown_provenance() -> None:
    selection, revision, unit = _saved(
        manual=True, operator_layer=CalculationOperatorLayer(decimal_casilla_inputs={"01": "123.45"})
    )
    snapshot = build_calculation_review_snapshot(selection=selection, revision=revision, work_unit=unit)
    assert snapshot.contributions[0].kind is ReviewSourceKind.MANUAL_INPUT


@pytest.mark.parametrize("operator_layer", [None, CalculationOperatorLayer()])
def test_equal_merged_input_does_not_imply_manual_authorship(operator_layer: CalculationOperatorLayer | None) -> None:
    selection, revision, unit = _saved(manual=True, operator_layer=operator_layer)
    snapshot = build_calculation_review_snapshot(selection=selection, revision=revision, work_unit=unit)
    assert revision.input_values_by_casilla_id["01"] == "123.4500"
    assert snapshot.contributions[0].kind is ReviewSourceKind.UNAVAILABLE


def test_computed_output_does_not_become_manual_when_equal_to_operator_input() -> None:
    selection, revision, unit = _saved(
        manual=True, operator_layer=CalculationOperatorLayer(decimal_casilla_inputs={"01": "123.45"}), computed=True
    )
    snapshot = build_calculation_review_snapshot(selection=selection, revision=revision, work_unit=unit)
    assert snapshot.contributions[0].kind is ReviewSourceKind.UNAVAILABLE
    assert snapshot.amounts[0].formula_reference == "test-formula"


@pytest.mark.parametrize(
    "change",
    [
        {"profile_id": UUID("6bb00000-0000-4000-8000-0000000000bb")},
        {"work_unit_id": "a" * 64},
        {"calculation_revision_id": "b" * 64},
    ],
)
def test_cross_profile_or_revision_selection_is_refused(change: dict[str, object]) -> None:
    selection, revision, unit = _saved()
    changed = selection.model_copy(update=change)
    with pytest.raises(ValueError, match="does not match"):
        build_calculation_review_snapshot(selection=changed, revision=revision, work_unit=unit)


def test_new_current_pointer_does_not_replace_selected_revision() -> None:
    selection, revision, unit = _saved()
    newer_unit = unit.model_copy(update={"current_calculation_revision_id": "d" * 64})
    snapshot = build_calculation_review_snapshot(selection=selection, revision=revision, work_unit=newer_unit)
    assert isinstance(snapshot.selection, CalculationReviewSelection)
    assert snapshot.selection.calculation_revision_id == revision.calculation_revision_id
    assert str(snapshot.amounts[0].value) == "123.4500"
    assert snapshot.calculation_lifecycle is not None
    assert snapshot.calculation_lifecycle.state is CalculationRevisionState.BORRADOR
    assert not snapshot.calculation_lifecycle.is_current_calculation
    assert not snapshot.calculation_lifecycle.is_current_filing
    assert snapshot.calculation_lifecycle.aeat_confirmation is None


def test_draft_review_captures_current_selection_without_claiming_filing() -> None:
    selection, revision, unit = _saved()
    unit = unit.model_copy(update={"current_calculation_revision_id": revision.calculation_revision_id})
    snapshot = build_calculation_review_snapshot(selection=selection, revision=revision, work_unit=unit)
    assert snapshot.schema_version == 2
    assert snapshot.calculation_lifecycle is not None
    assert snapshot.calculation_lifecycle.is_current_calculation
    assert snapshot.calculation_lifecycle.state is CalculationRevisionState.BORRADOR
    assert snapshot.calculation_lifecycle.aeat_confirmation is None
    assert snapshot.calculation_lifecycle.filing_record_id is None
    assert snapshot.status is ReviewStatus.INCOMPLETE


def _with_captured_ledger(revision: CalculationRevision) -> CalculationRevision:
    row = LedgerEvidenceRow(
        transaction_id="1" * 64,
        fingerprint="2" * 64,
        booked_date="2026-01-12",
        amount=Decimal("999.00"),
        currency="EUR",
        direction="outflow",
        business_classification="business",
        lifecycle_state="confirmed",
        attachment_ids=("original-invoice",),
        legal_refs=("test-law",),
        source_refs=("test-source",),
    )
    return revision.model_copy(
        update={
            "ledger_filing_evidence": LedgerFilingEvidence(
                snapshot_fingerprint="3" * 64, rows=(row,), captured_at=revision.created_at
            ),
            "ledger_filing_snapshot": LedgerFilingSnapshot(
                snapshot_fingerprint="3" * 64,
                rows=(LedgerRowFingerprint(transaction_id=row.transaction_id, fingerprint=row.fingerprint),),
                captured_at=revision.created_at,
            ),
        }
    )


def test_captured_rows_and_excluded_attachment_inventory_are_retained() -> None:
    selection, revision, unit = _saved()
    revision = _with_captured_ledger(revision)
    snapshot = build_calculation_review_snapshot(selection=selection, revision=revision, work_unit=unit)
    assert snapshot.ledger_rows[0].amount == Decimal("999.00")
    assert snapshot.amounts[0].value == Decimal("123.4500")
    assert snapshot.evidence[0].evidence_id == "original-invoice"
    assert snapshot.evidence[0].disposition is EvidenceDisposition.EXCLUDED
    assert snapshot.contributions[0].kind is ReviewSourceKind.UNAVAILABLE


def test_captured_row_fingerprint_mismatch_is_refused() -> None:
    selection, revision, unit = _saved()
    revision = _with_captured_ledger(revision)
    assert revision.ledger_filing_evidence is not None
    evidence = revision.ledger_filing_evidence
    altered = evidence.rows[0].model_copy(update={"fingerprint": "4" * 64})
    revision = revision.model_copy(update={"ledger_filing_evidence": evidence.model_copy(update={"rows": (altered,)})})
    with pytest.raises(ValueError, match="fingerprints"):
        build_calculation_review_snapshot(selection=selection, revision=revision, work_unit=unit)
