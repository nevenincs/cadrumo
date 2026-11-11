"""An inventory purchase with no standing ledger entry refuses checking, filing and export with the claim command as its door.

The findings come from the production inventory resolver over a real ledger, persist
as the revision's notes the way a calculation persists them, and the application's
own gate decides each action. The refusal and the calculation's own note both name
the inventory command that states which ledger entry books a purchase, or that none
does, and never decide that for the filer.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from cadrumo.application.aggregation.source_mesh import CalculationSourceDiagnostic
from cadrumo.application.aggregation.tests.test_inventory_book_claims import (
    YEAR,
    _claiming,  # pyright: ignore[reportPrivateUsage]
    _expense_row,  # pyright: ignore[reportPrivateUsage]
    _resolve,  # pyright: ignore[reportPrivateUsage]
)
from cadrumo.application.aggregation.tests.test_inventory_source import inventory_ledger

from ....core.errors.error_codes import get_registered_error_code
from ....core.operator_action_enums import ActionArgumentStatus, ActionConditionality
from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from ....domain.modelos.calculation_revision_sources import CalculationSourceIssue
from ....domain.modelos.work_unit import WorkUnit, derive_work_unit_id
from ...operator_actions.catalogue import lookup_action
from ..bucket_unrouted_source_issues import unrouted_source_issues
from ..calculation_note_gate import (
    ModeloCalculationBlockedError,
    blocking_calculation_issues,
    require_work_unit_calculation_unblocked,
)
from ..calculation_notes import note_record_verdict
from ..calculation_screen import calculation_screen_stamp
from ..inventory_purchase_claim_gate import ModeloInventoryPurchaseLedgerRowError
from ..printed_boxes import snapshot_printed_boxes
from .work_form_fixture import form_snapshot

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_BUCKET = "0de41ce4-0000-4000-8000-000000000811"
_CLOCK = datetime(1980, 5, 21, 10, 0, tzinfo=UTC)
_ACTIONS = {"verify": "modelo.work.verify", "file": "modelo.work.file", "export": "modelo.export"}
_DOOR = "operator.ledger.inventory.movement.claim"


def _diagnostics(amount: str, *, claiming: bool) -> tuple[CalculationSourceDiagnostic, ...]:
    """What the inventory resolver says about one purchase and the ledger entry beside it."""
    row = _expense_row(base=amount)
    ledger = inventory_ledger("comercio")
    if claiming:
        ledger = _claiming(ledger, row.transaction_id)
    return _resolve(ledger, row).diagnostics


def _work_unit(operation: PinnedAuthorityOperation) -> WorkUnit:
    snapshot = form_snapshot(operation, "100", YEAR, "0A")
    period = Period.from_year_and_code(YEAR, "0A")
    return WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=_BUCKET, modelo="100", filing_year=YEAR, period=period, revision_id=snapshot.revision.id
        ),
        bucket_id=_BUCKET,
        modelo="100",
        filing_year=YEAR,
        period=period,
        revision_id=snapshot.revision.id,
        name="inventory-purchase",
        created_at=_CLOCK,
        updated_at=_CLOCK,
    )


def _issues(
    operation: PinnedAuthorityOperation, diagnostics: tuple[CalculationSourceDiagnostic, ...]
) -> tuple[CalculationSourceIssue, ...]:
    snapshot = form_snapshot(operation, "100", YEAR, "0A")
    return unrouted_source_issues(diagnostics, snapshot_printed_boxes(operation, snapshot))


def _revision(operation: PinnedAuthorityOperation, issues: tuple[CalculationSourceIssue, ...]) -> CalculationRevision:
    snapshot = form_snapshot(operation, "100", YEAR, "0A")
    work_unit = _work_unit(operation)
    stamp = calculation_screen_stamp(snapshot, operation=operation)
    return CalculationRevision(
        calculation_revision_id=derive_calculation_revision_id(
            work_unit_id=work_unit.work_unit_id,
            input_values_by_casilla_id={},
            binding_overrides={},
            casilla_values={},
            source_issues=issues,
            filing_instance_evidence=None,
            source_provenance=(),
            screen_stamp=stamp,
        ),
        work_unit_id=work_unit.work_unit_id,
        registry_snapshot_ref=snapshot.snapshot_ref,
        state=CalculationRevisionState.BORRADOR,
        casilla_values={},
        observations=(),
        created_at=_CLOCK,
        updated_at=_CLOCK,
        filing_instance_evidence=None,
        source_provenance=(),
        source_issues=issues,
        screen_stamp=stamp,
    )


def _gate(operation: PinnedAuthorityOperation, revision: CalculationRevision, action: str) -> None:
    require_work_unit_calculation_unblocked(
        work_unit=_work_unit(operation), revision=revision, action=action, operation=operation
    )


@pytest.mark.parametrize(
    ("amount", "claiming", "scenario"),
    [("100.00", False, "unstated"), ("100.01", True, "claim_refused")],
)
def test_a_purchase_without_a_standing_ledger_entry_refuses_every_action_with_the_claim_command(
    operation: PinnedAuthorityOperation, amount: str, claiming: bool, scenario: str
) -> None:
    revision = _revision(operation, _issues(operation, _diagnostics(amount, claiming=claiming)))

    assert [issue.reason for issue in blocking_calculation_issues(revision)] == ["source_domain_not_ready"]
    for action, leaf in _ACTIONS.items():
        with pytest.raises(ModeloInventoryPurchaseLedgerRowError) as refused:
            _gate(operation, revision, action)

        error = refused.value
        assert get_registered_error_code(error).code == "REFUSED_MODELO_INVENTORY_PURCHASE_LEDGER_ROW"
        assert not isinstance(error, ModeloCalculationBlockedError)
        assert error.context is not None
        assert (error.context["year"], error.context["count"]) == (str(YEAR), "1")
        failure = error.precondition_failure
        assert failure is not None
        assert failure.subject_leaf_key == leaf
        assert failure.scenario_id == f"{leaf}.inventory_purchase_ledger_row.{scenario}"
        verdict = failure.verdict
        assert verdict.action is not None
        assert verdict.action.action_id == _DOOR
        assert verdict.conditionality is ActionConditionality.REQUIRES_ARGUMENTS
        assert verdict.missing_argument_names == ("actividad_id", "correction_id", "ledger_row", "movement_id")
        year = next(binding for binding in verdict.argument_bindings if binding.argument_name == "year")
        assert (year.status, year.value) == (ActionArgumentStatus.RESOLVED, YEAR)


@pytest.mark.usefixtures("operation")
def test_the_calculation_names_the_same_door_on_the_note_it_shows() -> None:
    (diagnostic,) = _diagnostics("100.00", claiming=False)

    verdict = note_record_verdict(diagnostic)

    assert verdict is not None
    assert verdict.action is not None
    assert verdict.action.action_id == _DOOR
    assert verdict.failed_condition_id == "modelo.work.calculate.inventory_purchase_ledger_row.stands"


def test_the_door_is_the_inventory_claim_command() -> None:
    assert lookup_action(_DOOR).target_command_key == "ledger.inventory.movement.claim"


def test_a_standing_claim_raises_no_note_and_no_refusal(operation: PinnedAuthorityOperation) -> None:
    row = _expense_row(base="100.00")
    diagnostics = _resolve(_claiming(inventory_ledger("comercio"), row.transaction_id), row).diagnostics

    revision = _revision(operation, _issues(operation, diagnostics))

    assert diagnostics == ()
    for action in _ACTIONS:
        _gate(operation, revision, action)
