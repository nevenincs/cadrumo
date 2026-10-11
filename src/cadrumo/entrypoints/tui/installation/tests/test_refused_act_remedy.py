"""A refused act names the command that remedies it, when its verdict names an action that resolves to one."""

from __future__ import annotations

from uuid import uuid4

import pytest

from .....application.operations.error_detail import OperationErrorDetailKind, OperationErrorDetailV1
from .....application.operator_actions.models import PreconditionVerdict
from .....application.operator_actions.preconditions import (
    no_action_precondition_verdict,
    profile_setup_incomplete_verdict,
)
from .....application.runtime.installation_requests import InstallationAct, RuntimeInstallationRefused
from .....core.errors.error_codes import resolve_error_message
from .....core.errors.hierarchy import RecordedRegisteredError
from .....core.i18n.render import tr
from .....core.operator_action_enums import ActionEvidenceProvenance, NoRecoveryOutcome
from ..acts import offered_act
from ..door import ActRefused
from ..rendering import ActPresentation, present_outcome

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_CODE = "REFUSED_AUTH_CERTIFICATE_SOURCE_NOT_FOUND"


def _refused_with(verdict: PreconditionVerdict | None) -> ActPresentation:
    refusal = RuntimeInstallationRefused(
        request_id=uuid4(),
        runtime_boot_id=uuid4(),
        connection_id=uuid4(),
        act=InstallationAct.REPAIR_PROFILE,
        detail=OperationErrorDetailV1(
            kind=OperationErrorDetailKind.REGISTERED_ERROR,
            error_code=_CODE,
            message_key=None,
            context=(),
            precondition_verdict_json=None if verdict is None else verdict.model_dump_json(),
        ),
    )
    return present_outcome(ActRefused(refusal), offered_act(InstallationAct.REPAIR_PROFILE).contract)


def test_a_refused_act_names_the_remedy_command_as_its_last_line() -> None:
    shown = _refused_with(profile_setup_incomplete_verdict(modelo="303", missing_required_field_count=1))

    assert shown.tone == "error"
    assert shown.status == tr("tui.installation.status.refused", code=_CODE)
    assert shown.lines == (
        resolve_error_message(RecordedRegisteredError(_CODE, context={})),
        tr("tui.installation.result.remedy", action="operator.profile.complete_setup"),
        tr("tui.operations.stopped.remedy_command", command="aeat config profile complete-setup"),
    )


def test_a_refusal_whose_verdict_names_no_action_is_shown_as_it_was() -> None:
    no_action = no_action_precondition_verdict(
        condition_id="storage.root.unreadable",
        facts={"readable": False},
        provenance=ActionEvidenceProvenance.PERSISTED_STATE,
        outcome=NoRecoveryOutcome.OPERATOR_DECISION,
    )
    explanation = (resolve_error_message(RecordedRegisteredError(_CODE, context={})),)

    assert _refused_with(no_action).lines == explanation
    assert _refused_with(None).lines == explanation
