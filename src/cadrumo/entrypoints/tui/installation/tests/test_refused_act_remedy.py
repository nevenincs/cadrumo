"""A refused act is shown through the refusal it served: its sentence and the verdict naming its ways out."""

from __future__ import annotations

from uuid import uuid4

import pytest

from cadrumo_client.contracts.installation_requests import InstallationAct, InstallationRefused

from .....application.operations.error_detail import (
    OperationErrorContextEntryV1,
    OperationErrorDetailKind,
    OperationErrorDetailV1,
)
from .....application.operator_actions.models import PreconditionVerdict
from .....application.operator_actions.preconditions import (
    no_action_precondition_verdict,
    profile_setup_incomplete_verdict,
)
from .....core.external_constants import OutputLanguage
from .....core.i18n.render import tr
from .....core.operator_action_enums import ActionEvidenceProvenance, NoRecoveryOutcome
from ..acts import offered_act
from ..door import ActRefused
from ..rendering import ActPresentation, present_outcome

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_CODE = "REFUSED_AUTH_CERTIFICATE_SOURCE_NOT_FOUND"
_SERVED = "The certificate this profile names is not where it was."


def _refused_with(verdict: PreconditionVerdict | None) -> ActPresentation:
    refusal = InstallationRefused(
        request_id=uuid4(),
        runtime_boot_id=uuid4(),
        connection_id=uuid4(),
        act=InstallationAct.REPAIR_PROFILE,
        detail=OperationErrorDetailV1(
            kind=OperationErrorDetailKind.REGISTERED_ERROR,
            error_code=_CODE,
            message_key=None,
            context=(OperationErrorContextEntryV1(key="source", value="primary"),),
            precondition_verdict_json=None if verdict is None else verdict.model_dump_json(),
            refusal_words=_SERVED,
            refusal_words_language=OutputLanguage.EN,
        ),
    )
    return present_outcome(ActRefused(refusal), offered_act(InstallationAct.REPAIR_PROFILE).contract)


def test_a_refused_act_carries_its_served_sentence_and_the_verdict_naming_its_way_out() -> None:
    shown = _refused_with(profile_setup_incomplete_verdict(modelo="303", missing_required_field_count=1))

    assert shown.tone == "error"
    assert shown.status == tr("tui.installation.status.refused", code=_CODE)
    assert shown.refusal is not None
    assert shown.refusal.sentence == _SERVED
    assert shown.refusal.verdict is not None
    assert shown.refusal.verdict.action_id == "operator.profile.complete_setup"
    assert not any("aeat " in line or "operator." in line for line in shown.lines)


def test_a_refusal_with_no_way_out_keeps_its_sentence_and_offers_no_action() -> None:
    no_action = no_action_precondition_verdict(
        condition_id="storage.root.unreadable",
        facts={"readable": False},
        provenance=ActionEvidenceProvenance.PERSISTED_STATE,
        outcome=NoRecoveryOutcome.OPERATOR_DECISION,
    )

    closed = _refused_with(no_action).refusal
    bare = _refused_with(None).refusal

    assert closed is not None
    assert closed.sentence == _SERVED
    assert closed.verdict is not None
    assert closed.verdict.action_id is None
    assert closed.verdict.no_recovery_outcome is NoRecoveryOutcome.OPERATOR_DECISION
    assert bare is not None
    assert bare.sentence == _SERVED
    assert bare.verdict is None


def test_the_recorded_context_stays_beside_the_refusal() -> None:
    assert _refused_with(None).lines == ("source  primary",)
