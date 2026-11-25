"""The comparison, resolution, solicitud, election, row and reducción refusals open the door of their cause.

Each refusal is raised by the owning code where its trigger needs no stored
profile, or built by the owning factory where it needs one, and read through
the reader the operation error detail uses.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from ....core.operator_action_enums import NoRecoveryOutcome
from ....domain.calculations.registry.tests.authored_editions import newest_authored_edition
from ....domain.calculations.registry.tests.published_authority import PublishedGovernedFactSource
from ....domain.modelos.dt12_reduccion import compute_dt12_reduccion_plan_pensiones
from ....domain.modelos.errors import PensionReduccionError
from ....domain.modelos.modelo_fact_context import ModeloFactResolutionContext
from ....domain.modelos.row_models import Modelo210AgrupacionRentaRowsError, validate_m210_agrupacion_renta_rows
from ....domain.modelos.sal_reserva_especial import compute_sal_reserva_especial_dotacion
from ...cli_exception_preconditions import nested_terminal_precondition_verdict
from ...filing.producer_snapshot_m360 import Modelo360SolicitudRegister
from ...operator_actions.models import PreconditionVerdict
from ..credit_resolution import stored_resolution_for
from ..credit_resolution_repository import CreditResolutionRefusedError, credit_resolution_refusal
from ..declaration_refusal_profiles import DeclarationRefusalCause
from ..m360_solicitud_operation import (
    Modelo360SolicitudRefusedError,
    Modelo360SolicitudRequest,
    apply_solicitud_request,
)
from ..taxation_comparison import TaxationComparisonRefusal, taxation_comparison_refusal

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_UNIT = "cd" * 32
_CONTEXT = ModeloFactResolutionContext(
    authority=PublishedGovernedFactSource(),
    filing_period=date.today(),
    devengo_date=date.today(),
)


def _verdict(error: BaseException) -> PreconditionVerdict:
    verdict = nested_terminal_precondition_verdict(error)
    assert verdict is not None
    return verdict


def _bound(verdict: PreconditionVerdict) -> dict[str, str]:
    return {item.argument_name: str(item.value) for item in verdict.argument_bindings if item.value is not None}


def _outcome(verdict: PreconditionVerdict) -> NoRecoveryOutcome:
    assert verdict.action is None
    assert verdict.no_recovery_outcome is not None
    return verdict.no_recovery_outcome


def test_an_uncalculated_comparison_opens_the_calculation_bound_to_its_unit() -> None:
    verdict = _verdict(taxation_comparison_refusal(TaxationComparisonRefusal.NOT_CALCULATED, work_unit_id=_UNIT))

    assert verdict.action is not None
    assert verdict.action.action_id == "operator.modelo.work.calculate"
    assert _bound(verdict) == {"work_unit_id": _UNIT}


def test_an_unstated_spouse_opens_the_profile_edit_leaving_the_profile_to_the_operator() -> None:
    verdict = _verdict(taxation_comparison_refusal(TaxationComparisonRefusal.SPOUSE_UNSTATED))

    assert verdict.action is not None
    assert verdict.action.action_id == "operator.profile.edit"
    assert set(verdict.missing_argument_names) == {"profile_name"}


@pytest.mark.parametrize(
    ("refusal", "outcome"),
    [
        (TaxationComparisonRefusal.NOT_DECLARED, NoRecoveryOutcome.TERMINAL),
        (TaxationComparisonRefusal.REVISION_OUTDATED, NoRecoveryOutcome.OPERATOR_DECISION),
        (TaxationComparisonRefusal.NO_FAMILY_UNIT, NoRecoveryOutcome.OPERATOR_DECISION),
        (TaxationComparisonRefusal.UNRESOLVED_BOXES, NoRecoveryOutcome.OPERATOR_DECISION),
    ],
)
def test_a_comparison_refusal_no_action_repairs_names_no_command(
    refusal: TaxationComparisonRefusal, outcome: NoRecoveryOutcome
) -> None:
    assert _outcome(_verdict(taxation_comparison_refusal(refusal))) is outcome


def test_a_finding_the_operator_named_wrongly_is_the_operators_decision() -> None:
    with pytest.raises(CreditResolutionRefusedError) as raised:
        stored_resolution_for((), "abc")

    assert _outcome(_verdict(raised.value)) is NoRecoveryOutcome.OPERATOR_DECISION


def test_a_calculation_that_moved_on_opens_the_status_of_its_unit() -> None:
    error = credit_resolution_refusal(
        "calculation_not_current", DeclarationRefusalCause.CREDIT_CALCULATION, work_unit_id=_UNIT
    )

    verdict = _verdict(error)
    assert verdict.action is not None
    assert verdict.action.action_id == "operator.modelo.work.status"
    assert _bound(verdict) == {"work_unit_id": _UNIT}


def test_a_finding_without_its_disagreement_is_terminal() -> None:
    error = credit_resolution_refusal("unknown_finding", DeclarationRefusalCause.CREDIT_FINDING_READABLE)

    assert _outcome(_verdict(error)) is NoRecoveryOutcome.TERMINAL


class _RemovalRepository:
    def load(self) -> Modelo360SolicitudRegister:
        return Modelo360SolicitudRegister()

    def declare(self, entry: object) -> Modelo360SolicitudRegister:
        return pytest.fail("a refused removal declares nothing")

    def remove(self, period: object) -> Modelo360SolicitudRegister:
        return pytest.fail("a refused removal removes nothing")


def test_removing_an_undeclared_solicitud_is_the_operators_decision() -> None:
    request = Modelo360SolicitudRequest(profile_id=uuid4(), action="remove", filing_year=newest_authored_edition("360"))

    with pytest.raises(Modelo360SolicitudRefusedError) as raised:
        apply_solicitud_request(request, repository=_RemovalRepository(), own_accounts=lambda: pytest.fail("unread"))

    assert _outcome(_verdict(raised.value)) is NoRecoveryOutcome.OPERATOR_DECISION


def test_a_grouped_renta_set_the_rules_refuse_is_the_operators_decision() -> None:
    with pytest.raises(Modelo210AgrupacionRentaRowsError) as raised:
        validate_m210_agrupacion_renta_rows((), effective_date=date.today())

    assert _outcome(_verdict(raised.value)) is NoRecoveryOutcome.OPERATOR_DECISION


def test_a_rescate_the_reduccion_refuses_is_the_operators_decision() -> None:
    with pytest.raises(PensionReduccionError) as raised:
        compute_dt12_reduccion_plan_pensiones(
            gross_rescate=Decimal(1),
            aportaciones_pre_2007=Decimal(0),
            aportaciones_totales=Decimal(0),
            context=_CONTEXT,
        )

    assert _outcome(_verdict(raised.value)) is NoRecoveryOutcome.OPERATOR_DECISION


def test_a_reserva_dotation_the_rules_refuse_is_the_operators_decision() -> None:
    with pytest.raises(PensionReduccionError) as raised:
        compute_sal_reserva_especial_dotacion(
            beneficio_neto=Decimal(1), reserva_dotada=Decimal(0), capital_social=Decimal(0), context=_CONTEXT
        )

    assert _outcome(_verdict(raised.value)) is NoRecoveryOutcome.OPERATOR_DECISION
