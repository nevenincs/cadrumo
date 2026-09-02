"""Proofs that an editor route accepts nothing before it is admitted.

The row's requirement is an ordering: the complete compatibility tuple must
match before any lexeme is accepted. These tests assert the ordering
STRUCTURALLY -- an unadmitted controller has no control object to offer -- and
then that a refused tuple leaves it in exactly that state. A test that merely
checked a boolean flag before typing would prove the intention and not the
guarantee.

See Also:
    :mod:`cadrumo.entrypoints.tui.modelo.edit.controller`
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from ......application.modelo.edit_contract import ModeloEditCompatibilityTupleV1, ModeloEditMutationFamily
from ......application.modelo.work_addressing import ModeloExactWorkUnitTarget
from ......application.modelo.workspace_models import ModeloWorkspaceExactWorkUnitTargetV1
from ......application.operations.registry import OperationSchemaIdentityV1
from ......core.external_constants import OutputLanguage
from ......core.period import Period
from ......domain.calculations.registry.authority import bundled_authority
from ......domain.calculations.registry.temporal import select_revision
from ......domain.modelos.calculation_revision import CalculationRevisionCatalogue
from ......domain.modelos.codes import ModeloCode
from ......domain.modelos.work_unit import WorkUnit, WorkUnitCatalogue, derive_work_unit_id
from ..controller import EditorRouteRefusedError, ModeloEditController

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_BUCKET_ID = "11111111-1111-4111-8111-111111111111"
_MODELO = "130"
_FILING_YEAR = 2026
_DIGEST = "a" * 64
_WRONG_DIGEST = "b" * 64


def _identity(fingerprint: str = _DIGEST) -> OperationSchemaIdentityV1:
    return OperationSchemaIdentityV1(schema_id="modelo.edit.contract", schema_version=1, schema_fingerprint=fingerprint)


def _work_unit() -> WorkUnit:
    period = Period.from_year_and_code(_FILING_YEAR, "1T")
    modelo = ModeloCode(_MODELO)
    revision_id = select_revision(bundled_authority().validate_modelo(modelo), filing_year=_FILING_YEAR, period="1T").id
    now = datetime(2026, 1, 10, tzinfo=UTC)
    return WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=_BUCKET_ID, modelo=modelo, filing_year=_FILING_YEAR, period=period, revision_id=revision_id
        ),
        bucket_id=_BUCKET_ID,
        modelo=modelo,
        filing_year=_FILING_YEAR,
        period=period,
        revision_id=revision_id,
        name=f"{_MODELO}-{_FILING_YEAR}-1T",
        created_at=now,
        updated_at=now,
    )


def _compatibility(*, current: bool) -> ModeloEditCompatibilityTupleV1:
    """Build a live tuple, or one whose schema axes are deliberately stale."""
    from ......application.modelo.edit_services import (
        modelo_edit_request_schema_identity,
        modelo_edit_result_schema_identity,
    )

    return ModeloEditCompatibilityTupleV1(
        contract_set_digest=_DIGEST,
        operation_definition_id="modelo.calculate",
        definition_contract_digest=_DIGEST,
        request_schema=modelo_edit_request_schema_identity() if current else _identity(_WRONG_DIGEST),
        result_schema=modelo_edit_result_schema_identity() if current else _identity(_WRONG_DIGEST),
        review_projection_contract_version=None,
        review_schema=None,
        workspace_refresh_target_schema=_identity(),
        financial_operand_schema=_identity(),
    )


def _admit(controller: ModeloEditController, *, current: bool) -> bool:
    work_unit = _work_unit()
    return controller.admit(
        ModeloWorkspaceExactWorkUnitTargetV1(
            target=ModeloExactWorkUnitTarget(work_unit_id=work_unit.work_unit_id, bucket_id=work_unit.bucket_id)
        ),
        mutation_family=ModeloEditMutationFamily.CALCULATE,
        bucket_id=work_unit.bucket_id,
        work_catalogue=WorkUnitCatalogue.from_work_units((work_unit,)),
        calculation_catalogue=CalculationRevisionCatalogue(),
        compatibility=_compatibility(current=current),
    )


def test_an_unadmitted_route_offers_no_control_to_type_into() -> None:
    """The ordering is structural: there is no object on which a lexeme could be offered."""
    controller = ModeloEditController.for_locale(OutputLanguage.ES)

    assert controller.is_admitted is False
    for accessor in (controller.fields, controller.rows, controller.review_gate):
        with pytest.raises(EditorRouteRefusedError, match="not been admitted"):
            accessor()


def test_a_stale_compatibility_tuple_refuses_the_route_and_names_why() -> None:
    """A tuple whose schema axes have moved cannot open an editor.

    Asserted against the CONTRACT's judgement rather than a local re-check:
    the axes are compared by `admit_modelo_edit`, and this test drives a
    genuinely stale tuple through it rather than simulating the refusal.
    """
    controller = ModeloEditController.for_locale(OutputLanguage.ES)

    admitted = _admit(controller, current=False)

    assert admitted is False
    assert controller.is_admitted is False
    assert controller.refusal_message_key, "a refused route must say why"
    with pytest.raises(EditorRouteRefusedError, match="refused"):
        controller.fields()


def test_a_current_tuple_admits_and_only_then_exposes_controls() -> None:
    """Admission is what turns a route into an editing surface."""
    controller = ModeloEditController.for_locale(OutputLanguage.ES)

    admitted = _admit(controller, current=True)

    assert admitted is True
    assert controller.is_admitted is True
    assert controller.refusal_message_key is None
    assert controller.fields().casilla_ids(), "an admitted route must expose the permitted surface"
    assert controller.rows() is not None
    assert controller.review_gate() is not None


def test_the_admitted_controls_share_one_session() -> None:
    """Fields, rows and the gate must stage into the same edit, not three.

    Three sessions would each hold part of the operator's work, and the
    review gate would summarise only its own share while the screen showed
    all of it.
    """
    controller = ModeloEditController.for_locale(OutputLanguage.ES)
    assert _admit(controller, current=True)

    fields = controller.fields()
    casilla_id = fields.casilla_ids()[0]
    fields.submit_lexeme(casilla_id, "42.00")

    gate = controller.review_gate()
    assert gate.leaving_with_unsaved_changes() is True, "the gate must see the field's staged edit"


def test_a_refresh_on_an_unchanged_tree_reports_no_drift_and_keeps_staged_work() -> None:
    """Staleness is asked of the contract's compare-and-swap, not of record equality.

    This is the control the earlier version of this test lacked. An admission
    carries its own identity and lifetime -- baseline_id, issued_at,
    expires_at -- so comparing two admission RECORDS reports "stale" even when
    nothing moved. Asking `reconfirm_modelo_edit_baseline` compares the
    coordinate axes instead, so an unchanged tree correctly reports no drift.
    """
    controller = ModeloEditController.for_locale(OutputLanguage.ES)
    assert _admit(controller, current=True)
    fields = controller.fields()
    casilla_id = fields.casilla_ids()[0]
    fields.submit_lexeme(casilla_id, "77.00")
    work_unit = _work_unit()

    drifted = controller.refresh(
        work_catalogue=WorkUnitCatalogue.from_work_units((work_unit,)),
        calculation_catalogue=CalculationRevisionCatalogue(),
    )

    assert drifted == (), f"an unchanged tree must report no drift, got {drifted}"
    assert controller.in_stale_conflict is False
    assert fields.state(casilla_id).touched is True, "a refresh must not discard staged work"


def test_a_drifted_catalogue_enters_stale_conflict_without_merging_or_patching() -> None:
    """The row forbids merge, rebase, result-ref interpretation and view patching.

    Each would produce a screen that is neither what the operator wrote nor
    what the tree holds, and would then submit that. So the proof is that
    NOTHING was rescued: the drift is named, and the operator's staged work
    is untouched and still judged against the coordinate it was admitted on.
    """
    controller = ModeloEditController.for_locale(OutputLanguage.ES)
    assert _admit(controller, current=True)
    fields = controller.fields()
    casilla_id = fields.casilla_ids()[0]
    fields.submit_lexeme(casilla_id, "77.00")

    # A genuinely different catalogue: the work unit the baseline was admitted
    # against is absent, which is drift the compare-and-swap must see.
    drifted = controller.refresh(
        work_catalogue=WorkUnitCatalogue(),
        calculation_catalogue=CalculationRevisionCatalogue(),
    )

    assert drifted, "an emptied work catalogue must be reported as drift"
    assert controller.in_stale_conflict is True
    assert fields.state(casilla_id).touched is True, "staged work must survive a stale conflict"
    assert controller.review_gate().leaving_with_unsaved_changes() is True
