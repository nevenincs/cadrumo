"""Real-behaviour tests for the local reader's role resolution, probe and status projection.

The runtime is a real loopback endpoint speaking the ``/api/version``,
``/api/tags`` and ``/api/ps`` wire shapes, or a real closed port.
"""

from __future__ import annotations

import json
from collections.abc import Generator
from contextlib import contextmanager
from http import HTTPStatus
from pathlib import Path
from typing import ClassVar, override

import pytest

from ...core.component_records import component_records_root
from ...core.config import load_settings, override_settings
from ...core.config_runtime_fields import LOCAL_AI_CHAT_URL
from ...core.hardware import AcceleratorKind, ContentionCause
from ...core.model_catalogue import ModelRole, default_model_runtime_id, model_candidate
from ...tests.loopback_llm import SilentLoopbackHandler, read_json_body, serving_loopback, write_json_response
from ..local_reader import (
    EXTRACTION_READER_ROLES,
    probe_local_reader,
    read_local_reader_status,
    role_model_targets,
    select_role_model,
)
from ..provisioning import (
    AcceleratorDevice,
    AcceleratorReading,
    HardwareProfile,
    SystemMemoryReading,
    probe_hardware_profile,
)
from ..provisioning_contracts import (
    LOCAL_AI_PROVISION_ACTION_ID,
    ProvisioningPreconditionCondition,
)
from ..provisioning_runtime import InstalledModel, assess_model_load_contention, runtime_model_names_match
from .role_model_support import configured_role_model

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_CLOSED_ENDPOINT = "http://127.0.0.1:1/api/chat"
_VISION = default_model_runtime_id(ModelRole.VISION_TRANSCRIPTION)
_TEXT = default_model_runtime_id(ModelRole.TEXT_EXTRACTION)
_MAPPING = default_model_runtime_id(ModelRole.COLUMN_ROLE_MAPPING)


class _Runtime(SilentLoopbackHandler):
    installed: ClassVar[list[str]] = []
    residents: ClassVar[list[str]] = []
    digests: ClassVar[dict[str, str]] = {}

    @override
    def do_GET(self) -> None:
        if self.path == "/api/version":
            write_json_response(self, {"version": "0.9.0"}, status=HTTPStatus.OK)
        elif self.path == "/api/tags":
            rows = [
                {"name": n, "size": 1, **({"digest": self.digests[n]} if n in self.digests else {})}
                for n in self.installed
            ]
            write_json_response(self, {"models": rows}, status=HTTPStatus.OK)
        elif self.path == "/api/ps":
            rows = [{"name": n, "size": 1, "size_vram": 1} for n in self.residents]
            write_json_response(self, {"models": rows}, status=HTTPStatus.OK)
        else:
            self.send_error(HTTPStatus.NOT_FOUND)

    @override
    def do_POST(self) -> None:
        # The readiness check's one-token generate; its content is irrelevant.
        read_json_body(self)
        if self.path != "/api/generate":
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        write_json_response(self, {"done": True}, status=HTTPStatus.OK)


@contextmanager
def _runtime(
    *, installed: list[str], residents: list[str] | None = None, digests: dict[str, str] | None = None
) -> Generator[str]:
    _Runtime.installed = installed
    _Runtime.residents = residents or []
    _Runtime.digests = digests or {}
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
        ("qwen3", "qwen3:1.7b", False),
        ("qwen3:latest", "qwen3:latest", True),
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
    assert status.precondition_verdict.action is not None
    assert status.precondition_verdict.action.action_id == LOCAL_AI_PROVISION_ACTION_ID


def test_probe_is_per_role_so_one_missing_model_does_not_close_the_other() -> None:
    """A missing vision model must not stop text reads, and vice versa."""
    with _runtime(installed=[_TEXT]):
        text = probe_local_reader(ModelRole.TEXT_EXTRACTION)
        vision = probe_local_reader(ModelRole.VISION_TRANSCRIPTION)
    assert text.available is True
    assert vision.available is False
    assert vision.precondition_verdict is not None
    assert vision.precondition_verdict.failed_condition_id == ProvisioningPreconditionCondition.ROLE_MODEL_INSTALLED
    assert vision.precondition_verdict.action is not None
    assert vision.precondition_verdict.action.action_id == LOCAL_AI_PROVISION_ACTION_ID


def test_a_role_the_catalogue_cannot_serve_offers_no_setup() -> None:
    """Setup cannot change the hardware, so the refusal names no action."""
    with _runtime(installed=[_TEXT]), override_settings(cadrumo_llm_ollama_num_ctx=1_000_000):
        status = probe_local_reader(ModelRole.SUPPLY_NATURE_PROPOSAL)
    assert status.available is False
    assert status.precondition_verdict is not None
    assert status.precondition_verdict.failed_condition_id == ProvisioningPreconditionCondition.SELECTED_MODEL_AVAILABLE
    assert status.precondition_verdict.action is None


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


def test_installed_reader_models_are_extraction_ready() -> None:
    with _runtime(installed=[_TEXT]):
        partial = read_local_reader_status(roles=EXTRACTION_READER_ROLES, assess_load=False)
    with _runtime(installed=[_TEXT, _VISION], residents=[_TEXT]):
        unverified = read_local_reader_status(roles=EXTRACTION_READER_ROLES, assess_load=False)

    assert partial.host.reachable is True
    assert partial.extraction_ready is False
    partial_rows = {row.role: row for row in partial.roles}
    assert partial_rows[ModelRole.VISION_TRANSCRIPTION].failed_condition_id == (
        ProvisioningPreconditionCondition.ROLE_MODEL_INSTALLED
    )
    assert unverified.extraction_ready is True
    rows = {row.role: row for row in unverified.roles}
    assert rows[ModelRole.TEXT_EXTRACTION].ready is True
    assert rows[ModelRole.TEXT_EXTRACTION].resident is True
    assert rows[ModelRole.VISION_TRANSCRIPTION].ready is True
    assert rows[ModelRole.VISION_TRANSCRIPTION].resident is False
    assert rows[ModelRole.VISION_TRANSCRIPTION].installed is True


# ---------------------------------------------------------------------------
# the order of the probe's judgement, and the local AI located from its record
# ---------------------------------------------------------------------------

_LOCAL_AI_RECORD = Path(__file__).parents[2] / "core" / "tests" / "_component_records" / "local_ai.json"
_GIB = 1024**3


def _computer(*, total: int, free: int) -> HardwareProfile:
    """A computer measured with no accelerator, ``total`` memory installed and ``free`` of it free now."""
    return probe_hardware_profile(
        memory=SystemMemoryReading(total_bytes=total, free_bytes=free),
        accelerator=AcceleratorReading(kind=AcceleratorKind.NONE),
    )


def _below_every_floor() -> HardwareProfile:
    """A computer with less memory installed than any catalogued local model needs."""
    return _computer(total=_GIB, free=_GIB // 4)


@pytest.mark.parametrize("role", list(ModelRole))
def test_a_role_below_this_computers_floor_offers_nothing_even_with_no_runtime(role: ModelRole) -> None:
    """Setup cannot change the hardware, so the floor decides before reachability, for every role."""
    with override_settings(
        cadrumo_llm_ollama_chat_url=_CLOSED_ENDPOINT,
        cadrumo_llm_ollama_vision_model=_VISION,
        cadrumo_llm_ollama_text_model=_TEXT,
        cadrumo_llm_ollama_mapping_model=_MAPPING,
    ):
        status = probe_local_reader(role, hardware=_below_every_floor())
    assert status.available is False
    assert status.facts["role"] == role.value
    assert status.facts["total_memory_bytes"] == _GIB
    assert status.precondition_verdict is not None
    assert status.precondition_verdict.failed_condition_id == ProvisioningPreconditionCondition.HARDWARE_FLOOR_MET
    assert status.precondition_verdict.action is None


def _requirement(model: str) -> int:
    candidate = model_candidate(model)
    assert candidate is not None and candidate.memory_requirement_bytes is not None, model
    return candidate.memory_requirement_bytes


def test_an_installed_reader_stays_admitted_while_its_own_resident_model_holds_the_free_memory() -> None:
    """Free memory is not this computer's limit: 2 GiB free on 8 GiB installed is a busy moment, not a floor."""
    busy_moment = _computer(total=8 * _GIB, free=2 * _GIB)
    with _runtime(installed=[_VISION, _TEXT], residents=[_VISION, _TEXT]):
        settings = load_settings()
        statuses = {role: probe_local_reader(role, hardware=busy_moment) for role in EXTRACTION_READER_ROLES}
        vision = select_role_model(ModelRole.VISION_TRANSCRIPTION, settings, profile=busy_moment)
    # The control: the catalogue's headroom bar, which the probe used to judge on, does refuse here.
    assert vision.selected is False
    assert vision.precondition_verdict is not None
    assert vision.precondition_verdict.failed_condition_id == ProvisioningPreconditionCondition.SELECTED_MODEL_FITS
    for role, status in statuses.items():
        assert status.available is True, (role, status.precondition_verdict)
        assert status.facts["model"] == (_VISION if role is ModelRole.VISION_TRANSCRIPTION else _TEXT)


def test_a_model_larger_than_the_installed_memory_refuses_with_no_action_however_much_is_free() -> None:
    model = _VISION
    tight = _computer(total=_requirement(model) - 1, free=_requirement(model) - 1)
    with _runtime(installed=[_VISION, _TEXT], residents=[]):
        status = probe_local_reader(ModelRole.VISION_TRANSCRIPTION, hardware=tight)
    assert status.available is False
    assert status.facts["model"] == model
    assert status.facts["required_bytes"] == _requirement(model)
    assert status.precondition_verdict is not None
    assert status.precondition_verdict.failed_condition_id == ProvisioningPreconditionCondition.HARDWARE_FLOOR_MET
    assert status.precondition_verdict.action is None


def test_a_card_large_enough_holds_the_model_on_a_computer_with_little_memory() -> None:
    model = _VISION
    card = AcceleratorDevice(index=0, name="card", total_vram_bytes=_requirement(model), free_vram_bytes=_GIB // 4)
    small_memory_large_card = probe_hardware_profile(
        memory=SystemMemoryReading(total_bytes=_GIB, free_bytes=_GIB // 4),
        accelerator=AcceleratorReading(kind=AcceleratorKind.NVIDIA_CUDA, devices=(card,)),
    )
    small_card = card.model_copy(update={"total_vram_bytes": _requirement(model) - 1})
    small_memory_small_card = small_memory_large_card.model_copy(
        update={"accelerator": AcceleratorReading(kind=AcceleratorKind.NVIDIA_CUDA, devices=(small_card,))}
    )
    with _runtime(installed=[_VISION], residents=[_VISION]):
        held = probe_local_reader(ModelRole.VISION_TRANSCRIPTION, hardware=small_memory_large_card)
        refused = probe_local_reader(ModelRole.VISION_TRANSCRIPTION, hardware=small_memory_small_card)
    assert held.available is True
    assert refused.precondition_verdict is not None
    assert refused.precondition_verdict.failed_condition_id == ProvisioningPreconditionCondition.HARDWARE_FLOOR_MET


def test_a_busy_computer_admits_the_reader_and_the_load_reads_as_busy_memory_to_retry() -> None:
    """Another program holding the memory is contention at the load, never this computer's limit."""
    model = _VISION
    busy = _computer(total=8 * _GIB, free=_GIB)
    with _runtime(installed=[_VISION, _TEXT], residents=[]):
        settings = load_settings()
        status = probe_local_reader(ModelRole.VISION_TRANSCRIPTION, hardware=busy)
        load = assess_model_load_contention(model, _requirement(model), profile=busy, settings=settings)
    assert status.available is True, status.precondition_verdict
    assert load.admitted is False
    assert load.causes == (ContentionCause.PEER_PROCESS,)
    assert load.precondition_verdict is not None
    assert load.precondition_verdict.failed_condition_id == ProvisioningPreconditionCondition.LOAD_CAPACITY_AVAILABLE
    assert load.precondition_verdict.action is None
    freed = _computer(total=8 * _GIB, free=8 * _GIB)
    with _runtime(installed=[_VISION, _TEXT], residents=[]):
        retried = assess_model_load_contention(model, _requirement(model), profile=freed, settings=load_settings())
    assert retried.admitted is True, "the same load is admitted once the memory is free again"


def _install_local_ai(storage_root: Path, address: str) -> None:
    """Write the engine's local AI record, at ``address``, and the program and models it names."""
    record = json.loads(_LOCAL_AI_RECORD.read_text(encoding="utf-8").replace("<storage-root>", storage_root.as_posix()))
    record["location"]["facts"]["address"] = address
    records_root = component_records_root(load_settings())
    records_root.mkdir(parents=True, exist_ok=True)
    (records_root / "local_ai.json").write_text(json.dumps(record), encoding="utf-8")
    location = record["location"]
    folder = Path(location["root"])
    program = folder / location["paths"]["program"]
    program.parent.mkdir(parents=True, exist_ok=True)
    program.write_bytes(b"local AI program")
    (folder / location["paths"]["models"]).mkdir(parents=True, exist_ok=True)


def test_the_managed_local_ai_without_a_record_refuses_with_its_setup(tmp_path: Path) -> None:
    with override_settings(cadrumo_llm_ollama_chat_url=LOCAL_AI_CHAT_URL, cadrumo_llm_ollama_text_model=_TEXT):
        status = probe_local_reader(ModelRole.TEXT_EXTRACTION)
        host = read_local_reader_status(roles=(ModelRole.TEXT_EXTRACTION,), assess_load=False).host
    assert status.available is False
    assert status.facts["local_ai_located"] is False
    assert status.precondition_verdict is not None
    assert status.precondition_verdict.failed_condition_id == ProvisioningPreconditionCondition.RUNTIME_INSTALLED
    assert status.precondition_verdict.action is not None
    assert status.precondition_verdict.action.action_id == LOCAL_AI_PROVISION_ACTION_ID
    assert host.executable_located is False and host.reachable is False
    assert not (tmp_path / "components" / "receipts").exists(), "reading writes nothing"


def test_a_located_local_ai_whose_server_no_manager_runs_refuses_with_its_setup(tmp_path: Path) -> None:
    _, port = _CLOSED_ENDPOINT.removeprefix("http://").split("/")[0].split(":")
    with override_settings(cadrumo_llm_ollama_chat_url=LOCAL_AI_CHAT_URL, cadrumo_llm_ollama_text_model=_TEXT):
        _install_local_ai(tmp_path, f"127.0.0.1:{port}")
        status = probe_local_reader(ModelRole.TEXT_EXTRACTION)
    assert status.available is False
    assert status.facts["operator_endpoint"] is False
    assert _CLOSED_ENDPOINT not in status.model_dump_json(), "the verdict never publishes the address"
    assert status.precondition_verdict is not None
    assert status.precondition_verdict.failed_condition_id == ProvisioningPreconditionCondition.RUNTIME_REACHABLE
    assert status.precondition_verdict.action is not None
    assert status.precondition_verdict.action.action_id == LOCAL_AI_PROVISION_ACTION_ID


def test_the_readers_ask_the_server_at_the_address_the_record_names(tmp_path: Path) -> None:
    with _runtime(installed=[_TEXT]) as chat_url:
        address = chat_url.removeprefix("http://").removesuffix("/api/chat")
        with override_settings(cadrumo_llm_ollama_chat_url=LOCAL_AI_CHAT_URL):
            _install_local_ai(tmp_path, address)
            status = probe_local_reader(ModelRole.TEXT_EXTRACTION)
            reader = read_local_reader_status(roles=(ModelRole.TEXT_EXTRACTION,), assess_load=False)
    assert status.available is True
    assert reader.host.endpoint_url == chat_url
    assert reader.host.executable_located is True and reader.host.reachable is True
