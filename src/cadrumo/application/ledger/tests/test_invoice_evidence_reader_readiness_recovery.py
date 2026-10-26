"""The reader readiness rows name the setup action the judgement named, and only that one.

The status is measured by the real local reader status reader against a real
loopback runtime that speaks the ``/api/version``, ``/api/tags`` and
``/api/ps`` wire shapes, or against a real closed port, over the lanes the
person's selection resolves to, and is then projected by the readiness
operation's own projection. A row offers setup only when the judgement names
it: a missing on-host model or an unanswering program does, and a role with no
selection does not. Every model id is synthetic.
"""

from __future__ import annotations

from collections.abc import Generator, Mapping
from contextlib import contextmanager
from http import HTTPStatus
from typing import ClassVar, override
from uuid import UUID

import pytest

from cadrumo_client.contracts.model_runs import ModelRunLane, ModelRunRefusal, ModelRunRefusalCode

from ....core.config import override_settings
from ....core.model_roles import ModelRole
from ....tests.loopback_llm import SilentLoopbackHandler, serving_loopback, write_json_response
from ...local_reader import RoleLane, read_local_reader_status
from ...provisioning_contracts import LOCAL_AI_PROVISION_ACTION_ID, ProvisioningPreconditionCondition
from ..invoice_evidence_readiness_operation import LedgerEvidenceReaderReadinessProjection, ReaderRoleProjectionV1

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE = UUID("5c11a0e7-3b2d-4c6e-8f1a-2b3c4d5e6f70")
_CLOSED_ENDPOINT = "http://127.0.0.1:1/api/chat"
_VISION = "synthetic-vision:small"
_TEXT = "synthetic-text:small"


def _on_host(model: str) -> ModelRunLane:
    return ModelRunLane(
        provider_id="ollama",
        transport="api",
        model=model,
        reads_off_host=False,
        licence=None,
        size_bytes=None,
        vision=None,
        context_length=None,
    )


#: Both reader roles selected on the local lane; the other roles have no selection.
_LANES: Mapping[ModelRole, RoleLane] = {
    ModelRole.TEXT_EXTRACTION: _on_host(_TEXT),
    ModelRole.VISION_TRANSCRIPTION: _on_host(_VISION),
    ModelRole.COLUMN_ROLE_MAPPING: ModelRunRefusal(code=ModelRunRefusalCode.NO_SELECTION),
    ModelRole.SUPPLY_NATURE_PROPOSAL: ModelRunRefusal(code=ModelRunRefusalCode.NO_SELECTION),
}


class _Runtime(SilentLoopbackHandler):
    """A runtime that answers its version, inventory and residents and nothing else."""

    installed: ClassVar[tuple[str, ...]] = ()

    @override
    def do_GET(self) -> None:
        if self.path == "/api/version":
            write_json_response(self, {"version": "0.9.0"}, status=HTTPStatus.OK)
        elif self.path == "/api/tags":
            write_json_response(
                self, {"models": [{"name": name, "size": 1} for name in self.installed]}, status=HTTPStatus.OK
            )
        elif self.path == "/api/ps":
            write_json_response(self, {"models": []}, status=HTTPStatus.OK)
        else:
            self.send_error(HTTPStatus.NOT_FOUND)


@contextmanager
def _runtime_holding(*models: str) -> Generator[None]:
    _Runtime.installed = models
    with (
        serving_loopback(_Runtime, path="/api/chat") as chat_url,
        override_settings(cadrumo_llm_ollama_chat_url=chat_url),
    ):
        yield


def _rows() -> dict[str, ReaderRoleProjectionV1]:
    projection = LedgerEvidenceReaderReadinessProjection.from_status(_PROFILE, read_local_reader_status(_LANES))
    return {row.role: row for row in projection.roles}


def test_a_missing_model_offers_the_local_ai_setup_and_an_installed_one_is_ready() -> None:
    with _runtime_holding(_TEXT):
        rows = _rows()

    vision = rows[ModelRole.VISION_TRANSCRIPTION.value]
    assert vision.model == _VISION
    assert vision.installed is False and vision.ready is False
    assert vision.failed_condition_id == ProvisioningPreconditionCondition.ROLE_MODEL_INSTALLED.value
    assert vision.recovery_action_id == LOCAL_AI_PROVISION_ACTION_ID
    text = rows[ModelRole.TEXT_EXTRACTION.value]
    assert text.installed is True
    assert text.ready is True
    assert text.failed_condition_id is None
    assert text.recovery_action_id is None


def test_an_unanswering_runtime_offers_the_local_ai_setup_on_every_on_host_role() -> None:
    with override_settings(cadrumo_llm_ollama_chat_url=_CLOSED_ENDPOINT):
        rows = _rows()

    assert set(rows) == {role.value for role in ModelRole}
    for role in (ModelRole.TEXT_EXTRACTION, ModelRole.VISION_TRANSCRIPTION):
        row = rows[role.value]
        assert row.installed is None and not row.ready
        assert row.failed_condition_id == ProvisioningPreconditionCondition.RUNTIME_REACHABLE.value
        assert row.recovery_action_id == LOCAL_AI_PROVISION_ACTION_ID


def test_a_role_with_no_selection_offers_no_setup() -> None:
    with _runtime_holding(_TEXT, _VISION):
        rows = _rows()

    supply = rows[ModelRole.SUPPLY_NATURE_PROPOSAL.value]
    assert supply.ready is False
    assert supply.model is None
    assert supply.failed_condition_id == ProvisioningPreconditionCondition.SELECTED_MODEL_AVAILABLE.value
    assert supply.recovery_action_id is None
    assert rows[ModelRole.VISION_TRANSCRIPTION.value].recovery_action_id is None, "a ready role offers nothing"
