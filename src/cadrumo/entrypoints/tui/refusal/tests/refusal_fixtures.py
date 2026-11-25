"""Real verdicts, served words and admitted registries the refusal tests share."""

from __future__ import annotations

from functools import lru_cache

from textual.screen import Screen

from .....application.operator_actions.models import (
    ActionArgumentBinding,
    ActionReference,
    AlternativeRecoveryAction,
    ConditionEvidence,
    PreconditionVerdict,
)
from .....application.operator_actions.projection import PreconditionVerdictSnapshot
from .....application.search.workbench import WorkbenchDestinationAdmission, WorkbenchDestinationAdmissionState
from .....core.external_constants import OutputLanguage
from .....core.operator_action_enums import (
    ActionArgumentSource,
    ActionArgumentStatus,
    ActionConditionality,
    ActionEvidenceProvenance,
    NoRecoveryOutcome,
)
from ....tests.production_operation_registry import production_operation_registry
from ...navigation import (
    TUI_DESTINATION_CATALOGUE,
    TuiActionCandidateV1,
    TuiDestinationAdmissionV1,
    TuiDestinationCatalogueV1,
    TuiScreenContextV1,
    TuiScreenFactoryV1,
    build_destination_catalogue,
)
from ...operations.catalogue import OperationCatalogueV1, build_operation_catalogue
from ..served import ServedWordsV1

#: Targets ``modelo.work.create``, an operation the registry publishes.
CREATE_WORK = "operator.modelo.work.create"
#: Targets ``ledger.review``, an operation the registry publishes.
REVIEW_LEDGER = "operator.ledger.review"
#: Targets ``modelo.work.attest_prior_value``, which no registered operation carries.
ATTEST_PRIOR_VALUE = "operator.modelo.work.attest_prior_value"

_CONDITION = "modelo.work.verify.cross_period_dependency.clean"


class MarkerScreen(Screen[None]):
    """A destination screen returned through the injected factory seam."""


def _marker(_context: TuiScreenContextV1) -> Screen[None]:
    return MarkerScreen()


def destinations(
    *,
    unavailable: frozenset[str] = frozenset(),
    action_candidates: tuple[TuiActionCandidateV1, ...] = (),
) -> TuiDestinationCatalogueV1:
    """Return the closed destination catalogue with every route admitted except ``unavailable``."""
    admissions: dict[str, TuiDestinationAdmissionV1 | WorkbenchDestinationAdmission] = {
        descriptor.destination: TuiDestinationAdmissionV1(
            destination=descriptor.destination,
            state=(
                WorkbenchDestinationAdmissionState.UNAVAILABLE
                if descriptor.destination in unavailable
                else WorkbenchDestinationAdmissionState.AVAILABLE
            ),
            reason_code="navigation.reason" if descriptor.destination in unavailable else None,
        )
        for descriptor in TUI_DESTINATION_CATALOGUE
    }
    factories: dict[str, TuiScreenFactoryV1] = {
        descriptor.destination: _marker
        for descriptor in TUI_DESTINATION_CATALOGUE
        if descriptor.destination not in unavailable
    }
    return build_destination_catalogue(admissions=admissions, factories=factories, action_candidates=action_candidates)


@lru_cache(maxsize=1)
def operations() -> OperationCatalogueV1:
    """Return the Operations catalogue projected from the production operation registry."""
    return build_operation_catalogue(production_operation_registry())


def words(text: str) -> ServedWordsV1:
    """Return a served English sentence."""
    return ServedWordsV1(words=text, language=OutputLanguage.EN)


def _evidence() -> ConditionEvidence:
    return ConditionEvidence(
        condition_id=_CONDITION,
        evidence_id="modelo.work.verify.cross_period_dependency",
        provenance=ActionEvidenceProvenance.DOMAIN_EVALUATION,
        values={"source_modelo": "100", "year": 7},
    )


def _resolved(name: str, value: str) -> ActionArgumentBinding:
    return ActionArgumentBinding(
        argument_name=name,
        status=ActionArgumentStatus.RESOLVED,
        value=value,
        source=ActionArgumentSource.VERDICT_CONTEXT,
        source_key=name,
    )


def attest_alternative() -> AlternativeRecoveryAction:
    """An alternative served as needing the value the operator has not given."""
    return AlternativeRecoveryAction(
        action=ActionReference(action_id=ATTEST_PRIOR_VALUE),
        argument_bindings=(
            _resolved("binding_id", "irpf.previous_year_economic_activity_net_income"),
            ActionArgumentBinding(argument_name="value", status=ActionArgumentStatus.MISSING),
        ),
        missing_argument_names=("value",),
        conditionality=ActionConditionality.REQUIRES_ARGUMENTS,
    )


def review_alternative() -> AlternativeRecoveryAction:
    """An alternative that runs as served."""
    return AlternativeRecoveryAction(
        action=ActionReference(action_id=REVIEW_LEDGER),
        conditionality=ActionConditionality.IMMEDIATE,
    )


def primary_verdict(
    action_id: str = CREATE_WORK,
    *alternatives: AlternativeRecoveryAction,
    missing_year: bool = False,
) -> PreconditionVerdictSnapshot:
    """A verdict whose primary action is ``action_id``, followed by ``alternatives`` in that order."""
    bindings = (_resolved("modelo", "100"),)
    if missing_year:
        bindings = (*bindings, ActionArgumentBinding(argument_name="year", status=ActionArgumentStatus.MISSING))
    return PreconditionVerdictSnapshot.from_verdict(
        PreconditionVerdict(
            failed_condition_id=_CONDITION,
            evidence=(_evidence(),),
            action=ActionReference(action_id=action_id),
            argument_bindings=bindings,
            missing_argument_names=("year",) if missing_year else (),
            conditionality=(
                ActionConditionality.REQUIRES_ARGUMENTS if missing_year else ActionConditionality.IMMEDIATE
            ),
            alternative_actions=alternatives,
        )
    )


def closed_verdict(outcome: NoRecoveryOutcome) -> PreconditionVerdictSnapshot:
    """A verdict that deliberately offers no way out."""
    return PreconditionVerdictSnapshot.from_verdict(
        PreconditionVerdict(
            failed_condition_id=_CONDITION,
            evidence=(_evidence(),),
            conditionality=ActionConditionality.NOT_APPLICABLE,
            no_recovery_outcome=outcome,
        )
    )


__all__ = [
    "ATTEST_PRIOR_VALUE",
    "CREATE_WORK",
    "REVIEW_LEDGER",
    "MarkerScreen",
    "attest_alternative",
    "closed_verdict",
    "destinations",
    "operations",
    "primary_verdict",
    "review_alternative",
    "words",
]
