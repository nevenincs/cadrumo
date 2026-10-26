"""Real-behaviour tests for the local AI program probe and the per-role reader status.

Each role's lane is what the agent service resolved for the person's selection,
given here as the typed lookup answer. The runtime is a real loopback endpoint
speaking the ``/api/version``, ``/api/tags`` and ``/api/ps`` wire shapes, or a
real closed port. Every model id is synthetic.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Generator
from contextlib import contextmanager
from http import HTTPStatus
from pathlib import Path
from typing import ClassVar, override

import pytest

from cadrumo_client.contracts.model_runs import (
    ModelRunBody,
    ModelRunHeader,
    ModelRunLane,
    ModelRunOutput,
    ModelRunRefusal,
    ModelRunRefusalCode,
    ModelRunRoleSelection,
)

from ...core.component_records import component_records_root
from ...core.config import load_settings, override_settings
from ...core.config_runtime_fields import LOCAL_AI_CHAT_URL
from ...core.hardware import AcceleratorKind, ContentionCause
from ...core.model_roles import ModelRole
from ...tests.loopback_llm import SilentLoopbackHandler, serving_loopback, write_json_response
from ..local_reader import (
    EXTRACTION_READER_ROLES,
    LOCAL_AI_PROGRAM_SERVICE,
    RoleLane,
    probe_local_ai_program,
    read_local_reader_status,
    read_role_lanes,
)
from ..local_reader_report import read_local_reader_report
from ..operations.model_runs import bound_model_runs
from ..provisioning import (
    AcceleratorDevice,
    AcceleratorReading,
    HardwareProfile,
    SystemMemoryReading,
    probe_hardware_profile,
)
from ..provisioning_contracts import LOCAL_AI_PROVISION_ACTION_ID, ProvisioningPreconditionCondition
from ..provisioning_runtime import runtime_model_names_match

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_CLOSED_ENDPOINT = "http://127.0.0.1:1/api/chat"
_GIB = 1024**3
_VISION = "synthetic-vision:small"
_TEXT = "synthetic-text:small"
_LOCAL_AI_RECORD = Path(__file__).parents[2] / "core" / "tests" / "_component_records" / "local_ai.json"


def _lane(model: str, *, off_host: bool = False, size: int | None = 2 * _GIB) -> ModelRunLane:
    return ModelRunLane(
        provider_id="ollama" if not off_host else "hosted",
        transport="api",
        model=model,
        reads_off_host=off_host,
        licence=None,
        size_bytes=size,
        vision=None,
        context_length=None,
    )


def _on_host(**extra: RoleLane) -> dict[ModelRole, RoleLane]:
    lanes: dict[ModelRole, RoleLane] = {
        ModelRole.TEXT_EXTRACTION: _lane(_TEXT),
        ModelRole.VISION_TRANSCRIPTION: _lane(_VISION),
    }
    lanes.update({ModelRole(role): answer for role, answer in extra.items()})
    return lanes


def _no_selection() -> ModelRunRefusal:
    return ModelRunRefusal(code=ModelRunRefusalCode.NO_SELECTION)


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
        override_settings(cadrumo_llm_ollama_chat_url=chat_url),
    ):
        yield chat_url


def _computer(*, total: int, free: int) -> HardwareProfile:
    """A computer measured with no accelerator, ``total`` memory installed and ``free`` of it free now."""
    return probe_hardware_profile(
        memory=SystemMemoryReading(total_bytes=total, free_bytes=free),
        accelerator=AcceleratorReading(kind=AcceleratorKind.NONE),
    )


@pytest.mark.parametrize(
    ("left", "right", "same"),
    [
        ("reader:small", "reader:small", True),
        ("reader", "reader:latest", True),
        ("reader:small", "reader:large", False),
        ("reader:small", "reader-vl:small", False),
        ("reader", "reader:small", False),
    ],
)
def test_model_names_match_on_the_full_tag(left: str, right: str, same: bool) -> None:
    assert runtime_model_names_match(left, right) is same


# ---------------------------------------------------------------------------
# the program probe the doctor reports
# ---------------------------------------------------------------------------


def test_the_program_probe_refuses_an_unreachable_runtime_with_the_local_ai_setup() -> None:
    with override_settings(cadrumo_llm_ollama_chat_url=_CLOSED_ENDPOINT):
        status = probe_local_ai_program()
    assert status.service == LOCAL_AI_PROGRAM_SERVICE
    assert status.available is False
    assert status.precondition_verdict is not None
    assert status.precondition_verdict.failed_condition_id == ProvisioningPreconditionCondition.RUNTIME_REACHABLE
    assert status.precondition_verdict.action is not None
    assert status.precondition_verdict.action.action_id == LOCAL_AI_PROVISION_ACTION_ID


def test_the_program_probe_judges_no_model() -> None:
    """An answering server is the program's health, whatever it holds."""
    with _runtime(installed=[]):
        empty = probe_local_ai_program()
    with _runtime(installed=[_TEXT, _VISION]):
        held = probe_local_ai_program()
    assert empty.available is True
    assert held.available is True
    assert "model" not in empty.facts and "model" not in held.facts


# ---------------------------------------------------------------------------
# each role's selected lane
# ---------------------------------------------------------------------------


def test_a_role_with_no_selection_is_not_ready_and_offers_no_setup() -> None:
    with _runtime(installed=[_TEXT, _VISION]):
        status = read_local_reader_status(
            _on_host(vision_transcription=_no_selection()), roles=EXTRACTION_READER_ROLES, assess_load=False
        )
    rows = {row.role: row for row in status.roles}
    vision = rows[ModelRole.VISION_TRANSCRIPTION]
    assert vision.ready is False
    assert vision.model is None
    assert vision.failed_condition_id == ProvisioningPreconditionCondition.SELECTED_MODEL_AVAILABLE
    assert vision.recovery_action_id is None
    assert rows[ModelRole.TEXT_EXTRACTION].ready is True, "one role's missing selection does not close the other"
    assert status.extraction_ready is False
    assert status.text_layer_model_fill_available is True


def test_a_role_absent_from_the_lookup_reads_as_the_service_unavailable() -> None:
    with _runtime(installed=[_TEXT, _VISION]):
        status = read_local_reader_status({}, roles=(ModelRole.TEXT_EXTRACTION,), assess_load=False)
    (row,) = status.roles
    assert row.ready is False
    assert row.failed_condition_id == ProvisioningPreconditionCondition.SELECTED_MODEL_AVAILABLE


def test_off_host_lanes_need_nothing_local_and_name_no_local_model() -> None:
    lanes = _on_host(text_extraction=_lane(_TEXT, off_host=True), vision_transcription=_lane(_VISION, off_host=True))
    with override_settings(cadrumo_llm_ollama_chat_url=_CLOSED_ENDPOINT):
        status = read_local_reader_status(lanes, roles=EXTRACTION_READER_ROLES, which=lambda _name: None)
    assert status.host.reachable is False
    assert status.extraction_ready is True
    assert all(row.ready and row.model is None and row.installed is None for row in status.roles)


def test_on_host_roles_are_judged_each_against_the_program_inventory() -> None:
    """A missing vision model must not stop text reads, and vice versa."""
    with _runtime(installed=[_TEXT]):
        status = read_local_reader_status(_on_host(), roles=EXTRACTION_READER_ROLES, assess_load=False)
    rows = {row.role: row for row in status.roles}
    assert rows[ModelRole.TEXT_EXTRACTION].ready is True
    assert rows[ModelRole.TEXT_EXTRACTION].model == _TEXT
    vision = rows[ModelRole.VISION_TRANSCRIPTION]
    assert vision.ready is False
    assert vision.installed is False
    assert vision.failed_condition_id == ProvisioningPreconditionCondition.ROLE_MODEL_INSTALLED
    assert vision.recovery_action_id == LOCAL_AI_PROVISION_ACTION_ID
    assert status.extraction_ready is False


def test_a_different_size_of_the_same_family_does_not_satisfy_the_role() -> None:
    with _runtime(installed=["synthetic-text:large"]):
        status = read_local_reader_status(_on_host(), roles=(ModelRole.TEXT_EXTRACTION,), assess_load=False)
    (row,) = status.roles
    assert row.ready is False
    assert row.installed is False


def test_installed_on_host_models_are_extraction_ready() -> None:
    with _runtime(installed=[_TEXT, _VISION], residents=[_TEXT]):
        status = read_local_reader_status(_on_host(), roles=EXTRACTION_READER_ROLES, assess_load=False)
    rows = {row.role: row for row in status.roles}
    assert status.extraction_ready is True
    assert rows[ModelRole.TEXT_EXTRACTION].resident is True
    assert rows[ModelRole.VISION_TRANSCRIPTION].resident is False
    assert rows[ModelRole.VISION_TRANSCRIPTION].installed is True


def test_an_unreachable_runtime_reports_unknowns_not_absences() -> None:
    with override_settings(cadrumo_llm_ollama_chat_url=_CLOSED_ENDPOINT):
        status = read_local_reader_status(_on_host(), which=lambda _name: None)
    assert status.extraction_ready is False
    on_host = [row for row in status.roles if row.role in EXTRACTION_READER_ROLES]
    assert all(row.installed is None and row.resident is None for row in on_host)
    assert all(row.failed_condition_id == ProvisioningPreconditionCondition.RUNTIME_REACHABLE for row in on_host)


# ---------------------------------------------------------------------------
# this computer's capacity, judged against the selected entry's size
# ---------------------------------------------------------------------------


def test_a_model_larger_than_the_installed_memory_refuses_with_no_action_even_with_no_runtime() -> None:
    """Setup cannot change the hardware, so capacity decides before reachability."""
    small = _computer(total=_GIB, free=_GIB // 4)
    with override_settings(cadrumo_llm_ollama_chat_url=_CLOSED_ENDPOINT):
        refused = read_local_reader_status(
            _on_host(), roles=(ModelRole.TEXT_EXTRACTION,), which=lambda _name: None, hardware=small
        )
        held = read_local_reader_status(
            _on_host(),
            roles=(ModelRole.TEXT_EXTRACTION,),
            which=lambda _name: None,
            hardware=_computer(total=8 * _GIB, free=_GIB // 4),
        )
    (row,) = refused.roles
    assert row.failed_condition_id == ProvisioningPreconditionCondition.HARDWARE_FLOOR_MET
    assert row.recovery_action_id is None
    assert held.roles[0].failed_condition_id == ProvisioningPreconditionCondition.RUNTIME_REACHABLE


def test_a_card_large_enough_holds_the_model_on_a_computer_with_little_memory() -> None:
    size = 4 * _GIB
    card = AcceleratorDevice(index=0, name="card", total_vram_bytes=size, free_vram_bytes=_GIB // 4)
    large_card = probe_hardware_profile(
        memory=SystemMemoryReading(total_bytes=_GIB, free_bytes=_GIB // 4),
        accelerator=AcceleratorReading(kind=AcceleratorKind.NVIDIA_CUDA, devices=(card,)),
    )
    small_card = large_card.model_copy(
        update={
            "accelerator": AcceleratorReading(
                kind=AcceleratorKind.NVIDIA_CUDA, devices=(card.model_copy(update={"total_vram_bytes": size - 1}),)
            )
        }
    )
    lanes = _on_host(vision_transcription=_lane(_VISION, size=size))
    with _runtime(installed=[_VISION], residents=[_VISION]):
        held = read_local_reader_status(lanes, roles=(ModelRole.VISION_TRANSCRIPTION,), hardware=large_card)
        refused = read_local_reader_status(lanes, roles=(ModelRole.VISION_TRANSCRIPTION,), hardware=small_card)
    assert held.roles[0].ready is True
    assert refused.roles[0].failed_condition_id == ProvisioningPreconditionCondition.HARDWARE_FLOOR_MET


def test_an_entry_with_no_size_makes_no_capacity_or_load_claim() -> None:
    lanes = _on_host(text_extraction=_lane(_TEXT, size=0), vision_transcription=_lane(_VISION, size=None))
    with _runtime(installed=[_TEXT, _VISION]):
        status = read_local_reader_status(lanes, roles=EXTRACTION_READER_ROLES)
    assert status.extraction_ready is True
    assert all(row.load_admitted is None for row in status.roles)


def test_a_busy_computer_admits_the_reader_and_its_load_reads_as_busy_memory() -> None:
    """Another program holding the memory is contention at the load, never this computer's limit."""
    busy = _computer(total=8 * _GIB, free=_GIB)
    freed = _computer(total=8 * _GIB, free=8 * _GIB)
    with _runtime(installed=[_TEXT, _VISION]):
        contended = read_local_reader_status(_on_host(), roles=(ModelRole.VISION_TRANSCRIPTION,), hardware=busy)
        retried = read_local_reader_status(_on_host(), roles=(ModelRole.VISION_TRANSCRIPTION,), hardware=freed)
    (row,) = contended.roles
    assert row.ready is True
    assert row.load_admitted is False
    assert row.contention_causes == (ContentionCause.PEER_PROCESS,)
    assert retried.roles[0].load_admitted is True, "the same load is admitted once the memory is free again"


# ---------------------------------------------------------------------------
# the managed local AI, located from its record
# ---------------------------------------------------------------------------


def _install_local_ai(storage_root: Path, address: str) -> None:
    """Write the engine's local AI record, at ``address``, and the program and models folder it names."""
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
    with override_settings(cadrumo_llm_ollama_chat_url=LOCAL_AI_CHAT_URL):
        status = probe_local_ai_program()
        reader = read_local_reader_status(_on_host(), roles=(ModelRole.TEXT_EXTRACTION,), assess_load=False)
    assert status.available is False
    assert status.facts["local_ai_located"] is False
    assert status.precondition_verdict is not None
    assert status.precondition_verdict.failed_condition_id == ProvisioningPreconditionCondition.RUNTIME_INSTALLED
    assert status.precondition_verdict.action is not None
    assert status.precondition_verdict.action.action_id == LOCAL_AI_PROVISION_ACTION_ID
    assert reader.roles[0].failed_condition_id == ProvisioningPreconditionCondition.RUNTIME_INSTALLED
    assert reader.host.executable_located is False and reader.host.reachable is False
    assert not (tmp_path / "components" / "receipts").exists(), "reading writes nothing"


def test_a_located_local_ai_whose_server_no_manager_runs_refuses_with_its_setup(tmp_path: Path) -> None:
    _, port = _CLOSED_ENDPOINT.removeprefix("http://").split("/")[0].split(":")
    with override_settings(cadrumo_llm_ollama_chat_url=LOCAL_AI_CHAT_URL):
        _install_local_ai(tmp_path, f"127.0.0.1:{port}")
        status = probe_local_ai_program()
    assert status.available is False
    assert status.facts["operator_endpoint"] is False
    assert _CLOSED_ENDPOINT not in status.model_dump_json(), "the verdict never publishes the address"
    assert status.precondition_verdict is not None
    assert status.precondition_verdict.failed_condition_id == ProvisioningPreconditionCondition.RUNTIME_REACHABLE


def test_the_readers_ask_the_server_at_the_address_the_record_names(tmp_path: Path) -> None:
    with _runtime(installed=[_TEXT]) as chat_url:
        address = chat_url.removeprefix("http://").removesuffix("/api/chat")
        with override_settings(cadrumo_llm_ollama_chat_url=LOCAL_AI_CHAT_URL):
            _install_local_ai(tmp_path, address)
            status = probe_local_ai_program()
            reader = read_local_reader_status(_on_host(), roles=(ModelRole.TEXT_EXTRACTION,), assess_load=False)
    assert status.available is True
    assert reader.roles[0].ready is True
    assert reader.host.endpoint_url == chat_url
    assert reader.host.executable_located is True and reader.host.reachable is True


# ---------------------------------------------------------------------------
# where the lanes come from, and the report built from them
# ---------------------------------------------------------------------------


class _AnsweringPort:
    """A model-run port answering each role's lookup from a fixed table; it runs nothing."""

    def __init__(self, answers: dict[ModelRole, RoleLane]) -> None:
        self.answers = answers
        self.asked: list[ModelRole] = []

    async def lookup(self, role: ModelRole) -> ModelRunLane | ModelRunRefusal:
        self.asked.append(role)
        return self.answers.get(role, _no_selection())

    async def selections(self) -> tuple[ModelRunRoleSelection, ...] | ModelRunRefusal:
        return ModelRunRefusal(code=ModelRunRefusalCode.SERVICE_UNAVAILABLE)

    async def run(self, header: ModelRunHeader, body: ModelRunBody) -> ModelRunOutput | ModelRunRefusal:
        del header, body
        return ModelRunRefusal(code=ModelRunRefusalCode.RUN_FAILED)


def test_outside_an_operation_every_role_reads_as_the_service_unavailable() -> None:
    lanes = asyncio.run(read_role_lanes(ModelRole))
    assert set(lanes) == set(ModelRole)
    assert all(
        isinstance(answer, ModelRunRefusal) and answer.code is ModelRunRefusalCode.SERVICE_UNAVAILABLE
        for answer in lanes.values()
    )


def test_the_lanes_are_the_bound_port_s_answer_for_each_role() -> None:
    port = _AnsweringPort({ModelRole.TEXT_EXTRACTION: _lane(_TEXT)})
    with bound_model_runs(port):
        lanes = asyncio.run(read_role_lanes(EXTRACTION_READER_ROLES))
    assert port.asked == list(EXTRACTION_READER_ROLES)
    assert lanes[ModelRole.TEXT_EXTRACTION] == _lane(_TEXT)
    vision = lanes[ModelRole.VISION_TRANSCRIPTION]
    assert isinstance(vision, ModelRunRefusal) and vision.code is ModelRunRefusalCode.NO_SELECTION


def test_the_report_names_only_on_host_models_and_judges_the_first_with_a_size() -> None:
    lanes: dict[ModelRole, RoleLane] = {
        ModelRole.VISION_TRANSCRIPTION: _lane(_VISION, off_host=True),
        ModelRole.TEXT_EXTRACTION: _lane(_TEXT),
        ModelRole.COLUMN_ROLE_MAPPING: _no_selection(),
    }
    with _runtime(installed=[_TEXT], residents=[_TEXT]):
        report = read_local_reader_report(lanes)
    rows = {row.role: row for row in report.models}
    assert rows[ModelRole.VISION_TRANSCRIPTION].selected is True
    assert rows[ModelRole.VISION_TRANSCRIPTION].model is None
    assert rows[ModelRole.TEXT_EXTRACTION].model == _TEXT
    assert rows[ModelRole.TEXT_EXTRACTION].resident is True
    mapping = rows[ModelRole.COLUMN_ROLE_MAPPING]
    assert mapping.selected is False
    assert mapping.precondition_verdict is not None
    assert (
        mapping.precondition_verdict.failed_condition_id == ProvisioningPreconditionCondition.SELECTED_MODEL_AVAILABLE
    )
    assert mapping.facts["role_selection_required"] is True
    assert report.contention is not None
    assert report.contention.model == _TEXT
