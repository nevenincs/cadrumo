"""The CLI file-import bridge binds receipt and facts to its authenticated profile."""

from __future__ import annotations

from typing import Any, cast
from uuid import UUID

import pytest
import typer

from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.runtime.contracts import RuntimeRefusalCode
from cadrumo.application.user_profile.censal_file_import_operation import (
    CENSAL_FILE_IMPORT_OPERATION_DEFINITION_ID,
    CensalFileImportFact,
    CensalFileImportOperationRequest,
    CensalFileImportOperationResult,
    CensalFileImportProvenance,
)
from cadrumo.core.external_constants import PROVENANCE_SOURCE_CENSO_ARTEFACT
from cadrumo.core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from cadrumo.domain.user_profile.values import UserProfileFact
from cadrumo.entrypoints.cli.config import runtime_censal_file_import
from cadrumo.entrypoints.cli.errors import CliRefusedBoundaryError
from cadrumo.entrypoints.cli.registered_operation_contracts import RegisteredOperationCompletion

_PROFILE_ID = UUID("aa000000-0000-4000-8000-0000000000aa")
_FOREIGN_PROFILE_ID = UUID("bb000000-0000-4000-8000-0000000000bb")
_OPERATION_ID = "f" * 64
_FACTS = (
    UserProfileFact(
        path="contact.fiscal_address",
        value="Calle Mayor 1, Madrid",
        source=PROVENANCE_SOURCE_CENSO_ARTEFACT,
    ),
    UserProfileFact(
        path="activities.description",
        value="Consultoría",
        source=PROVENANCE_SOURCE_CENSO_ARTEFACT,
    ),
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


class _BoundClient:
    profile_id = _PROFILE_ID
    session_id = UUID("cc000000-0000-4000-8000-0000000000cc")
    frontend = OperationFrontendProjection.CLI


def _install_bridge(
    monkeypatch: pytest.MonkeyPatch,
    *,
    profile_id: UUID = _PROFILE_ID,
    effect: OperationEffect = OperationEffect.UPDATED,
) -> tuple[_BoundClient, dict[str, Any], CensalFileImportOperationResult]:
    client = _BoundClient()
    projection = CensalFileImportOperationResult(
        profile_id=profile_id,
        fact_paths=tuple(fact.path for fact in _FACTS),
    )
    captured: dict[str, Any] = {}
    monkeypatch.setattr(runtime_censal_file_import, "bound_profile_client", lambda _ctx: client)

    def run_registered_operation(received_client: object, payload: object, **options: object):
        captured.update(client=received_client, payload=payload, options=options)
        return RegisteredOperationCompletion(
            operation_id=_OPERATION_ID,
            projection=projection,
            effect=effect,
            terminal_condition=OperationTerminalCondition.SUCCEEDED,
        )

    monkeypatch.setattr(runtime_censal_file_import, "run_registered_operation", run_registered_operation)
    return client, captured, projection


def test_file_import_bridge_submits_typed_facts_and_exact_profile_subject(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, captured, projection = _install_bridge(monkeypatch)

    receipt = runtime_censal_file_import.import_censal_file_facts(cast(typer.Context, object()), _FACTS)

    assert receipt is projection
    assert captured["client"] is client
    request = captured["payload"]
    assert isinstance(request, CensalFileImportOperationRequest)
    assert request.profile_id == client.profile_id
    assert request.facts == tuple(
        CensalFileImportFact(
            path=fact.path,
            value=cast(str, fact.value),
            source=CensalFileImportProvenance(fact.source),
        )
        for fact in _FACTS
    )
    assert captured["options"] == {
        "definition_id": CENSAL_FILE_IMPORT_OPERATION_DEFINITION_ID,
        "subject_ref": profile_operation_subject(str(client.profile_id)),
        "result_type": CensalFileImportOperationResult,
        "request_version": 1,
        "result_version": 1,
        "timeout": 60,
    }


@pytest.mark.parametrize(
    ("projection_profile_id", "effect"),
    [
        (_FOREIGN_PROFILE_ID, OperationEffect.UPDATED),
        (_PROFILE_ID, OperationEffect.NONE),
    ],
)
def test_file_import_bridge_refuses_mismatched_profile_or_effect(
    monkeypatch: pytest.MonkeyPatch,
    projection_profile_id: UUID,
    effect: OperationEffect,
) -> None:
    _client, _captured, _projection = _install_bridge(
        monkeypatch,
        profile_id=projection_profile_id,
        effect=effect,
    )

    with pytest.raises(CliRefusedBoundaryError) as refused:
        runtime_censal_file_import.import_censal_file_facts(cast(typer.Context, object()), _FACTS)

    assert refused.value.context == {
        "operation_id": _OPERATION_ID,
        "reason": RuntimeRefusalCode.INVALID_FRAME.value,
        "effect": effect.value,
        "terminal_condition": OperationTerminalCondition.SUCCEEDED.value,
    }
