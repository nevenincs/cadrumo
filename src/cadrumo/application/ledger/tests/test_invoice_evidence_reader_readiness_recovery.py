"""The reader readiness rows name the setup action the reader probe named, and only that one.

The status is measured by the real local reader status reader against a real
loopback runtime that speaks the ``/api/version``, ``/api/tags`` and
``/api/ps`` wire shapes, or against a real closed port, and is then projected
by the readiness operation's own projection. A row offers setup only when the
probe's verdict names it: a missing model or an unanswering runtime does, and a
role this computer cannot run or a fitness verdict does not.
"""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from http import HTTPStatus
from typing import ClassVar, override
from uuid import UUID

import pytest

from ....core.config import override_settings
from ....core.model_catalogue import ModelRole, default_model_runtime_id
from ....tests.loopback_llm import SilentLoopbackHandler, serving_loopback, write_json_response
from ...local_reader import RoleFitnessState, probe_local_reader, read_local_reader_status
from ...provisioning_contracts import LOCAL_AI_PROVISION_ACTION_ID, ProvisioningPreconditionCondition
from ..invoice_evidence_readiness_operation import LedgerEvidenceReaderReadinessProjection, ReaderRoleProjectionV1

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE = UUID("5c11a0e7-3b2d-4c6e-8f1a-2b3c4d5e6f70")
_CLOSED_ENDPOINT = "http://127.0.0.1:1/api/chat"
_VISION = default_model_runtime_id(ModelRole.VISION_TRANSCRIPTION)
_TEXT = default_model_runtime_id(ModelRole.TEXT_EXTRACTION)
_MAPPING = default_model_runtime_id(ModelRole.COLUMN_ROLE_MAPPING)


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
        override_settings(
            cadrumo_llm_ollama_chat_url=chat_url,
            cadrumo_llm_ollama_vision_model=_VISION,
            cadrumo_llm_ollama_text_model=_TEXT,
            cadrumo_llm_ollama_mapping_model=_MAPPING,
        ),
    ):
        yield


def _rows() -> dict[str, ReaderRoleProjectionV1]:
    projection = LedgerEvidenceReaderReadinessProjection.from_status(_PROFILE, read_local_reader_status())
    return {row.role: row for row in projection.roles}


def test_a_missing_model_offers_the_local_ai_setup_and_an_unverified_one_offers_none() -> None:
    with _runtime_holding(_TEXT):
        rows = _rows()

    vision = rows[ModelRole.VISION_TRANSCRIPTION.value]
    assert vision.installed is False and vision.ready is False
    assert vision.failed_condition_id == ProvisioningPreconditionCondition.ROLE_MODEL_INSTALLED.value
    assert vision.recovery_action_id == LOCAL_AI_PROVISION_ACTION_ID
    text = rows[ModelRole.TEXT_EXTRACTION.value]
    assert text.installed is True
    assert text.fitness is RoleFitnessState.NOT_VERIFIED
    assert text.failed_condition_id == ProvisioningPreconditionCondition.ROLE_MODEL_FITNESS_VERIFIED.value
    assert text.recovery_action_id is None, "a fitness verdict is not repaired by setting the local AI up"


def test_an_unanswering_runtime_offers_the_local_ai_setup_on_every_role() -> None:
    with override_settings(cadrumo_llm_ollama_chat_url=_CLOSED_ENDPOINT):
        rows = _rows()
        refusal = probe_local_reader(ModelRole.TEXT_EXTRACTION).precondition_verdict

    assert refusal is not None and refusal.action is not None
    assert refusal.action.action_id == LOCAL_AI_PROVISION_ACTION_ID
    assert set(rows) == {role.value for role in ModelRole}
    for row in rows.values():
        assert row.installed is None and not row.ready
        assert row.failed_condition_id == ProvisioningPreconditionCondition.RUNTIME_REACHABLE.value
        assert row.recovery_action_id == refusal.action.action_id


def test_a_role_this_computer_cannot_run_offers_no_setup() -> None:
    with _runtime_holding(_TEXT, _VISION), override_settings(cadrumo_llm_ollama_num_ctx=1_000_000):
        rows = _rows()

    supply = rows[ModelRole.SUPPLY_NATURE_PROPOSAL.value]
    assert supply.ready is False
    assert supply.failed_condition_id == ProvisioningPreconditionCondition.SELECTED_MODEL_AVAILABLE.value
    assert supply.recovery_action_id is None
    assert rows[ModelRole.VISION_TRANSCRIPTION.value].recovery_action_id is None, "a ready role offers nothing"
