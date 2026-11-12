"""A prior-domiciliation election refused for its baseline opens the door of its cause."""

from __future__ import annotations

import pytest

from ....core.operator_action_enums import NoRecoveryOutcome
from ....domain.calculations.registry.tests.authored_editions import newest_authored_edition
from ...cli_exception_preconditions import nested_terminal_precondition_verdict
from ...operator_actions.models import PreconditionVerdict
from ..declaration_refusal_failures import (
    prior_domiciliation_baseline_unevidenced_refusal,
    prior_domiciliation_refusal,
)
from ..declaration_refusal_profiles import DeclarationRefusalCause

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_UNIT = "cd" * 32


def _verdict(error: BaseException) -> PreconditionVerdict:
    verdict = nested_terminal_precondition_verdict(error)
    assert verdict is not None
    return verdict


def _outcome(verdict: PreconditionVerdict) -> NoRecoveryOutcome:
    assert verdict.action is None
    assert verdict.no_recovery_outcome is not None
    return verdict.no_recovery_outcome


def _bound(verdict: PreconditionVerdict) -> dict[str, str]:
    return {item.argument_name: str(item.value) for item in verdict.argument_bindings if item.value is not None}


def test_a_baseline_without_evidence_opens_the_import_bound_to_the_unit() -> None:
    error = prior_domiciliation_baseline_unevidenced_refusal(
        "baseline is not evidenced", work_unit_id=_UNIT, baseline_filing_record_id="record"
    )

    verdict = _verdict(error)
    assert verdict.action is not None
    assert verdict.action.action_id == "operator.modelo.filing_record.import"
    assert _bound(verdict)["work_unit_id"] == _UNIT


def test_an_uncaptured_baseline_observation_opens_the_filed_capture_for_its_declaration() -> None:
    error = prior_domiciliation_refusal(
        DeclarationRefusalCause.ELECTION_OBSERVATION,
        "no official observation",
        action_arguments={"modelos": "303", "period": "1T", "year": newest_authored_edition("303")},
    )

    verdict = _verdict(error)
    assert verdict.action is not None
    assert verdict.action.action_id == "operator.live.filed.pull"
    assert _bound(verdict) == {"modelos": "303", "period": "1T", "year": str(newest_authored_edition("303"))}


@pytest.mark.parametrize(
    ("cause", "outcome"),
    [
        (DeclarationRefusalCause.ELECTION_HEADER_VALUE, NoRecoveryOutcome.OPERATOR_DECISION),
        (DeclarationRefusalCause.ELECTION_TYPE, NoRecoveryOutcome.TERMINAL),
        (DeclarationRefusalCause.ELECTION_MARKER_LAYOUT, NoRecoveryOutcome.TERMINAL),
    ],
)
def test_an_election_refusal_no_action_repairs_names_no_command(
    cause: DeclarationRefusalCause, outcome: NoRecoveryOutcome
) -> None:
    assert _outcome(_verdict(prior_domiciliation_refusal(cause, "refused"))) is outcome
