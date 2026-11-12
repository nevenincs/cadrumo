"""The TUI correction door reads the current filing's correction and submits it, both bound to one session.

The door reads the work unit's current filing, then the correction it offers,
through profile-subject reads in the session's profile, and accepts the
answers only when they name the same profile, work unit and filing. The
correction is submitted under the work unit's subject; a lost start keeps its
outcome unknown.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID, uuid4

import pytest

from cadrumo.application.modelo.amendment_context_operation import (
    MODELO_WORK_AMENDMENT_CONTEXT_OPERATION_DEFINITION_ID,
    ModeloWorkAmendmentContextRequest,
)
from cadrumo.application.modelo.metadata_read_operation import (
    MODELO_WORK_METADATA_OPERATION_DEFINITION_ID,
    ModeloWorkMetadataRequest,
)
from cadrumo.application.modelo.operation_shared import MODELO_WORK_AMEND_OPERATION_DEFINITION_ID
from cadrumo.application.modelo.work_amend_contracts import ModeloWorkAmendOverride, ModeloWorkAmendRequest
from cadrumo.core.external_constants import OutputLanguage
from cadrumo.core.operations import OperationEffect, OperationFrontendProjection, profile_operation_subject
from cadrumo.domain.modelos.filing_record import FilingDeclarationKind
from cadrumo.entrypoints.tui.modelo.lifecycle import ModeloLifecycleActionUnavailableError, ModeloWorkspaceLifecycleDoor
from cadrumo_client.contracts.contracts import RefusalCode, RefusalError
from cadrumo_client.transport.frontend_client import FrontendClient

from .....frontend.tui.modelo import runtime_lifecycle

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_WORK_UNIT_ID = "b" * 64
_FILING_RECORD_ID = "f" * 64
_OPERATION_ID = "a" * 64


def _client() -> SimpleNamespace:
    return SimpleNamespace(frontend=OperationFrontendProjection.TUI, profile_id=uuid4(), session_id=uuid4())


def _door(client: SimpleNamespace) -> ModeloWorkspaceLifecycleDoor:
    return runtime_lifecycle.compose_runtime_modelo_lifecycle_door(
        cast(FrontendClient, client),
        cast(Any, SimpleNamespace(work_unit_id=_WORK_UNIT_ID)),
        calculation_revision_id=None,
        verification_report_id=None,
        asks_modelo_390=False,
    )


def _reads(
    profile_id: UUID,
    *,
    current_filing: str | None = _FILING_RECORD_ID,
    unit_profile: UUID | None = None,
    context_work_unit: str = _WORK_UNIT_ID,
    context_filing: str = _FILING_RECORD_ID,
) -> tuple[dict[str, object], list[dict[str, Any]]]:
    """Answers for the metadata and correction reads, and the list of reads they were asked."""
    correction = SimpleNamespace(filed=SimpleNamespace(filing_record_id=context_filing), language=OutputLanguage.EN)
    answers: dict[str, object] = {
        MODELO_WORK_METADATA_OPERATION_DEFINITION_ID: SimpleNamespace(
            profile_id=unit_profile or profile_id,
            unit=SimpleNamespace(
                bucket_id=str(unit_profile or profile_id),
                work_unit_id=_WORK_UNIT_ID,
                current_filing_record_id=current_filing,
            ),
        ),
        MODELO_WORK_AMENDMENT_CONTEXT_OPERATION_DEFINITION_ID: SimpleNamespace(
            profile_id=profile_id,
            unit=SimpleNamespace(work_unit_id=context_work_unit),
            record=SimpleNamespace(filing_record_id=context_filing),
            correction=correction,
        ),
    }
    return answers, []


def _bind_reads(monkeypatch: pytest.MonkeyPatch, answers: dict[str, object], asked: list[dict[str, Any]]) -> None:
    async def read_operation(client: object, **kwargs: Any) -> object:
        del client
        asked.append(kwargs)
        return answers[kwargs["definition_id"]]

    monkeypatch.setattr(runtime_lifecycle, "read_operation", read_operation)


def test_the_correction_is_read_for_the_current_filing_in_the_session_profile(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client()
    answers, asked = _reads(client.profile_id)
    _bind_reads(monkeypatch, answers, asked)

    correction = asyncio.run(_door(client).amendment_context(OutputLanguage.EN))

    assert correction is cast(Any, answers[MODELO_WORK_AMENDMENT_CONTEXT_OPERATION_DEFINITION_ID]).correction
    subject = profile_operation_subject(str(client.profile_id))
    metadata, context = asked
    assert metadata["definition_id"] == MODELO_WORK_METADATA_OPERATION_DEFINITION_ID
    assert metadata["subject_ref"] == subject
    assert metadata["session_id"] == client.session_id
    assert metadata["payload"] == ModeloWorkMetadataRequest(profile_id=client.profile_id, work_unit_id=_WORK_UNIT_ID)
    assert context["definition_id"] == MODELO_WORK_AMENDMENT_CONTEXT_OPERATION_DEFINITION_ID
    assert context["subject_ref"] == subject
    assert context["payload"] == ModeloWorkAmendmentContextRequest(
        profile_id=client.profile_id, filing_record_id=_FILING_RECORD_ID, output_language=OutputLanguage.EN
    )


def test_a_declaration_without_a_current_filing_offers_no_correction(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client()
    answers, asked = _reads(client.profile_id, current_filing=None)
    _bind_reads(monkeypatch, answers, asked)

    with pytest.raises(ModeloLifecycleActionUnavailableError) as raised:
        asyncio.run(_door(client).amendment_context(OutputLanguage.EN))

    assert raised.value.translated_message == "workspace.modelo.correction.unavailable"
    assert len(asked) == 1


@pytest.mark.parametrize(
    "mismatch",
    [
        {"unit_profile": UUID("5aa00000-0000-4000-8000-0000000000aa")},
        {"context_work_unit": "c" * 64},
        {"context_filing": "e" * 64},
    ],
)
def test_an_answer_naming_another_profile_unit_or_filing_is_refused(
    monkeypatch: pytest.MonkeyPatch, mismatch: dict[str, Any]
) -> None:
    client = _client()
    answers, asked = _reads(client.profile_id, **mismatch)
    _bind_reads(monkeypatch, answers, asked)

    with pytest.raises(RefusalError) as raised:
        asyncio.run(_door(client).amendment_context(OutputLanguage.EN))

    assert raised.value.reason is RefusalCode.INVALID_FRAME


class _StartLost:
    operation_id = _OPERATION_ID

    async def start(self) -> None:
        raise RefusalError(RefusalCode.CONNECTION_CLOSED)


def test_a_correction_is_submitted_under_the_work_unit_and_a_lost_start_stays_unknown() -> None:
    requests: list[Any] = []

    async def submit(request: Any) -> _StartLost:
        requests.append(request)
        return _StartLost()

    door = ModeloWorkspaceLifecycleDoor(work_unit_id=_WORK_UNIT_ID, submit_operation=cast(Any, submit))
    override = ModeloWorkAmendOverride(casilla_id="07", value="1250.5")

    with pytest.raises(ModeloLifecycleActionUnavailableError) as raised:
        asyncio.run(
            door.amend(
                filing_record_id=_FILING_RECORD_ID,
                amendment_kind=FilingDeclarationKind.COMPLEMENTARIA,
                overrides=(override,),
                reason="A figure was left out.",
                m303_rectificativa_motive=None,
            )
        )

    assert raised.value.context == {"operation_id": _OPERATION_ID, "effect": OperationEffect.UNKNOWN.value}
    (request,) = requests
    assert request.definition_id == MODELO_WORK_AMEND_OPERATION_DEFINITION_ID
    assert request.subject_ref == _WORK_UNIT_ID
    payload = request.payload
    assert isinstance(payload, ModeloWorkAmendRequest)
    assert payload.baseline.from_filing_record_id == _FILING_RECORD_ID
    assert payload.amendment_kind is FilingDeclarationKind.COMPLEMENTARIA
    assert payload.overrides == (override,)
    assert payload.reason == "A figure was left out."
    assert payload.m303_rectificativa_motive is None


def test_a_door_without_the_correction_read_refuses_rather_than_guessing() -> None:
    door = ModeloWorkspaceLifecycleDoor(work_unit_id=_WORK_UNIT_ID, submit_operation=cast(Any, None))

    with pytest.raises(ModeloLifecycleActionUnavailableError) as raised:
        asyncio.run(door.amendment_context(OutputLanguage.EN))

    assert raised.value.translated_message == "workspace.modelo.correction.unavailable"
