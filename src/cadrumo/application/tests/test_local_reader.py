"""Real-behaviour tests for the local reader's role resolution, probe and status projection.

The runtime is a real loopback endpoint speaking the ``/api/version``,
``/api/tags`` and ``/api/ps`` wire shapes, or a real closed port.
"""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from http import HTTPStatus
from typing import ClassVar, override

import pytest

from ...core.config import override_settings
from ...core.model_catalogue import ModelRole, default_model_runtime_id
from ...tests.loopback_llm import SilentLoopbackHandler, serving_loopback, write_json_response
from ..local_reader import (
    EXTRACTION_READER_ROLES,
    configured_role_model,
    probe_local_reader,
    read_local_reader_status,
    role_model_targets,
    runtime_model_names_match,
)
from ..provisioning_contracts import ProvisioningPreconditionCondition
from ..provisioning_runtime import InstalledModel

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_CLOSED_ENDPOINT = "http://127.0.0.1:1/api/chat"
_VISION = default_model_runtime_id(ModelRole.VISION_TRANSCRIPTION)
_TEXT = default_model_runtime_id(ModelRole.TEXT_EXTRACTION)
_MAPPING = default_model_runtime_id(ModelRole.COLUMN_ROLE_MAPPING)


class _Runtime(SilentLoopbackHandler):
    installed: ClassVar[list[str]] = []
    residents: ClassVar[list[str]] = []

    @override
    def do_GET(self) -> None:
        if self.path == "/api/version":
            write_json_response(self, {"version": "0.9.0"}, status=HTTPStatus.OK)
        elif self.path == "/api/tags":
            write_json_response(
                self, {"models": [{"name": n, "size": 1} for n in self.installed]}, status=HTTPStatus.OK
            )
        elif self.path == "/api/ps":
            rows = [{"name": n, "size": 1, "size_vram": 1} for n in self.residents]
            write_json_response(self, {"models": rows}, status=HTTPStatus.OK)
        else:
            self.send_error(HTTPStatus.NOT_FOUND)


@contextmanager
def _runtime(*, installed: list[str], residents: list[str] | None = None) -> Generator[str]:
    _Runtime.installed = installed
    _Runtime.residents = residents or []
    with (
        serving_loopback(_Runtime, path="/api/chat") as chat_url,
        override_settings(
            cadrumo_llm_ollama_chat_url=chat_url,
            cadrumo_llm_ollama_vision_model=_VISION,
            cadrumo_llm_ollama_text_model=_TEXT,
            cadrumo_llm_ollama_mapping_model=_MAPPING,
        ),
    ):
        yield chat_url


@pytest.mark.parametrize(
    ("left", "right", "same"),
    [
        ("qwen3:1.7b", "qwen3:1.7b", True),
        ("qwen3", "qwen3:latest", True),
        ("qwen3:1.7b", "qwen3:8b", False),
        ("qwen3:1.7b", "qwen3-vl:2b", False),
    ],
)
def test_model_names_match_on_the_full_tag(left: str, right: str, same: bool) -> None:
    assert runtime_model_names_match(left, right) is same


def test_each_role_reads_its_own_setting() -> None:
    with override_settings(
        cadrumo_llm_ollama_vision_model="vision-x:1b",
        cadrumo_llm_ollama_text_model="text-x:1b",
        cadrumo_llm_ollama_mapping_model="map-x:1b",
    ):
        assert configured_role_model(ModelRole.VISION_TRANSCRIPTION) == "vision-x:1b"
        assert configured_role_model(ModelRole.TEXT_EXTRACTION) == "text-x:1b"
        assert configured_role_model(ModelRole.COLUMN_ROLE_MAPPING) == "map-x:1b"


def test_roles_sharing_a_model_yield_one_target() -> None:
    with override_settings(
        cadrumo_llm_ollama_vision_model=_VISION,
        cadrumo_llm_ollama_text_model=_TEXT,
        cadrumo_llm_ollama_mapping_model=_MAPPING,
    ):
        targets = role_model_targets()
    models = [target.model for target in targets]
    assert len(models) == len(set(models))
    assert {role for target in targets for role in target.roles} == set(ModelRole)
    assert all(target.requirement_bytes for target in targets)


def test_an_operator_set_model_is_honoured_as_the_target() -> None:
    with override_settings(cadrumo_llm_ollama_text_model="qwen2.5:3b"):
        (target,) = role_model_targets((ModelRole.TEXT_EXTRACTION,))
    assert target.model == "qwen2.5:3b"
    assert target.selection_verdict is None


def test_a_role_whose_selection_refuses_is_its_own_target_with_the_verdict() -> None:
    with override_settings(
        cadrumo_llm_ollama_num_ctx=1_000_000,
        cadrumo_llm_ollama_text_model=_TEXT,
    ):
        (target,) = role_model_targets((ModelRole.TEXT_EXTRACTION,))
    assert target.model is None
    assert target.selection_verdict is not None
    assert target.selection_verdict.failed_condition_id == ProvisioningPreconditionCondition.SELECTED_MODEL_AVAILABLE


def test_probe_refuses_an_unreachable_runtime() -> None:
    with override_settings(cadrumo_llm_ollama_chat_url=_CLOSED_ENDPOINT):
        status = probe_local_reader(ModelRole.TEXT_EXTRACTION)
    assert status.available is False
    assert status.service == "local-reader:text_extraction"
    assert status.precondition_verdict is not None
    assert status.precondition_verdict.failed_condition_id == ProvisioningPreconditionCondition.RUNTIME_REACHABLE


def test_probe_is_per_role_so_one_missing_model_does_not_close_the_other() -> None:
    """A missing vision model must not stop text reads, and vice versa."""
    with _runtime(installed=[_TEXT]):
        text = probe_local_reader(ModelRole.TEXT_EXTRACTION)
        vision = probe_local_reader(ModelRole.VISION_TRANSCRIPTION)
    assert text.available is True
    assert vision.available is False
    assert vision.precondition_verdict is not None
    assert vision.precondition_verdict.failed_condition_id == ProvisioningPreconditionCondition.ROLE_MODEL_INSTALLED


def test_a_different_size_of_the_same_family_does_not_satisfy_the_probe() -> None:
    inventory = (InstalledModel(name="qwen3:8b", size_bytes=1),)
    with override_settings(cadrumo_llm_ollama_text_model="qwen3:1.7b"):
        status = probe_local_reader(ModelRole.TEXT_EXTRACTION, installed=inventory)
    assert status.available is False


def test_status_of_an_unreachable_runtime_reports_unknowns_not_absences() -> None:
    with override_settings(cadrumo_llm_ollama_chat_url=_CLOSED_ENDPOINT):
        status = read_local_reader_status(which=lambda _name: None)
    assert status.host.reachable is False
    assert status.extraction_ready is False
    assert all(row.installed is None and row.resident is None for row in status.roles)
    assert all(row.failed_condition_id == ProvisioningPreconditionCondition.RUNTIME_REACHABLE for row in status.roles)


def test_status_is_extraction_ready_only_when_both_reader_models_are_installed() -> None:
    with _runtime(installed=[_TEXT]):
        partial = read_local_reader_status(roles=EXTRACTION_READER_ROLES, assess_load=False)
    with _runtime(installed=[_TEXT, _VISION], residents=[_TEXT]):
        complete = read_local_reader_status(roles=EXTRACTION_READER_ROLES, assess_load=False)

    assert partial.host.reachable is True
    assert partial.extraction_ready is False
    assert {row.role: row.ready for row in partial.roles} == {
        ModelRole.TEXT_EXTRACTION: True,
        ModelRole.VISION_TRANSCRIPTION: False,
    }
    assert complete.extraction_ready is True
    rows = {row.role: row for row in complete.roles}
    assert rows[ModelRole.TEXT_EXTRACTION].resident is True
    assert rows[ModelRole.VISION_TRANSCRIPTION].resident is False
    assert rows[ModelRole.VISION_TRANSCRIPTION].installed is True
