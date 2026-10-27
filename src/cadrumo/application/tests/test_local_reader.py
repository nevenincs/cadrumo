"""Real-behaviour tests for the local AI program's row and the per-role reader status.

The program's state is the components role's status row, given here through
the row contract every surface decodes it into. Each role's lane is what the
agent service resolved for the person's selection, given as the typed lookup
answer, with whether the local AI server holds the model as the agent's live
catalogue states it. Nothing here asks a server. Every model id is synthetic.
"""

from __future__ import annotations

import asyncio

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

from ...core.model_roles import ModelRole
from .. import provisioning
from ..dependency_contracts import (
    DependencyState,
)
from ..local_reader import (
    EXTRACTION_READER_ROLES,
    LOCAL_AI_PROGRAM_SERVICE,
    ProgramRow,
    RoleLane,
    judge_local_ai_program,
    probe_local_ai_program,
    read_local_reader_status,
    read_role_lanes,
)
from ..local_reader_report import read_local_reader_report
from ..operations.model_runs import bound_model_runs
from ..provisioning_contracts import LOCAL_AI_PROVISION_ACTION_ID, ProvisioningPreconditionCondition
from .local_ai_program_rows import LOCAL_AI_VERSION, local_ai_row

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_GIB = 1024**3
_VISION = "synthetic-vision:small"
_TEXT = "synthetic-text:small"


_READY = local_ai_row(DependencyState.READY)
_ABSENT = local_ai_row(DependencyState.ABSENT)


def _lane(
    model: str, *, off_host: bool = False, size: int | None = 2 * _GIB, installed: bool | None = True
) -> ModelRunLane:
    return ModelRunLane(
        provider_id="ollama" if not off_host else "hosted",
        transport="api",
        model=model,
        reads_off_host=off_host,
        licence=None,
        size_bytes=size,
        vision=None,
        context_length=None,
        installed=None if off_host else installed,
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


# ---------------------------------------------------------------------------
# the program, from the components role's row
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("state", [DependencyState.READY, DependencyState.STALE])
def test_a_usable_program_is_available_with_its_version(state: DependencyState) -> None:
    program = judge_local_ai_program(local_ai_row(state))
    assert program.available is True
    assert program.state is state
    assert program.version == LOCAL_AI_VERSION
    assert program.facts == {"local_ai_state": state.value, "local_ai_version": LOCAL_AI_VERSION}
    assert program.precondition_verdict is None


@pytest.mark.parametrize(
    "state", [DependencyState.ABSENT, DependencyState.FAILED, DependencyState.PROVISIONING, DependencyState.UNKNOWN]
)
def test_a_program_not_usable_refuses_with_the_button_its_row_names(state: DependencyState) -> None:
    program = judge_local_ai_program(local_ai_row(state))
    assert program.available is False
    assert program.version is None, "an absent program's row names the version setup would install"
    verdict = program.precondition_verdict
    assert verdict is not None
    assert verdict.failed_condition_id == ProvisioningPreconditionCondition.RUNTIME_INSTALLED
    assert verdict.action is not None
    assert verdict.action.action_id == LOCAL_AI_PROVISION_ACTION_ID
    assert verdict.evidence[0].values["local_ai_state"] == state.value


def test_no_row_is_unknown_and_offers_no_setup() -> None:
    """A role that could not answer says nothing about the program, so nothing is set up on its silence."""
    program = judge_local_ai_program(None)
    assert program.available is False
    assert program.state is None
    assert program.facts == {"local_ai_state": "unknown"}
    assert program.precondition_verdict is not None
    assert program.precondition_verdict.failed_condition_id == ProvisioningPreconditionCondition.RUNTIME_INSTALLED
    assert program.precondition_verdict.action is None


def test_the_doctor_row_is_the_program_judgement_and_names_no_model() -> None:
    ready = probe_local_ai_program(_READY)
    absent = probe_local_ai_program(_ABSENT)
    assert ready.service == absent.service == LOCAL_AI_PROGRAM_SERVICE
    assert (ready.available, absent.available) == (True, False)
    assert ready.facts == judge_local_ai_program(_READY).facts
    assert "model" not in ready.facts and "model" not in absent.facts


# ---------------------------------------------------------------------------
# each role's selected lane
# ---------------------------------------------------------------------------


def test_a_role_with_no_selection_is_not_ready_and_offers_no_setup() -> None:
    status = read_local_reader_status(
        _on_host(vision_transcription=_no_selection()), _READY, roles=EXTRACTION_READER_ROLES
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
    status = read_local_reader_status({}, _READY, roles=(ModelRole.TEXT_EXTRACTION,))
    (row,) = status.roles
    assert row.ready is False
    assert row.failed_condition_id == ProvisioningPreconditionCondition.SELECTED_MODEL_AVAILABLE


def test_off_host_lanes_need_nothing_local_and_name_no_local_model() -> None:
    lanes = _on_host(text_extraction=_lane(_TEXT, off_host=True), vision_transcription=_lane(_VISION, off_host=True))
    status = read_local_reader_status(lanes, _ABSENT, roles=EXTRACTION_READER_ROLES)
    assert status.program.available is False
    assert status.extraction_ready is True
    assert all(row.ready and row.model is None and row.installed is None for row in status.roles)


def test_on_host_roles_are_judged_each_by_what_the_agent_states_the_server_holds() -> None:
    """A missing vision model must not stop text reads, and vice versa."""
    lanes = _on_host(vision_transcription=_lane(_VISION, installed=False))
    status = read_local_reader_status(lanes, _READY, roles=EXTRACTION_READER_ROLES)
    rows = {row.role: row for row in status.roles}
    assert rows[ModelRole.TEXT_EXTRACTION].ready is True
    assert rows[ModelRole.TEXT_EXTRACTION].model == _TEXT
    assert rows[ModelRole.TEXT_EXTRACTION].installed is True
    vision = rows[ModelRole.VISION_TRANSCRIPTION]
    assert vision.ready is False
    assert vision.installed is False
    assert vision.failed_condition_id == ProvisioningPreconditionCondition.ROLE_MODEL_INSTALLED
    assert vision.recovery_action_id == LOCAL_AI_PROVISION_ACTION_ID
    assert status.extraction_ready is False


def test_an_installed_state_nobody_stated_is_unknown_and_never_offers_a_download() -> None:
    lanes = _on_host(text_extraction=_lane(_TEXT, installed=None))
    status = read_local_reader_status(lanes, _READY, roles=(ModelRole.TEXT_EXTRACTION,))
    (row,) = status.roles
    assert row.ready is False
    assert row.installed is None
    assert row.failed_condition_id == ProvisioningPreconditionCondition.RUNTIME_REACHABLE
    assert row.recovery_action_id is None


def test_installed_on_host_models_on_a_ready_program_are_extraction_ready() -> None:
    status = read_local_reader_status(_on_host(), _READY, roles=EXTRACTION_READER_ROLES)
    assert status.extraction_ready is True
    assert status.program.available is True
    assert all(row.installed is True for row in status.roles)


@pytest.mark.parametrize("program", [_ABSENT, None], ids=["absent", "unknown"])
def test_on_host_roles_wait_on_a_program_that_is_not_usable(program: ProgramRow) -> None:
    """An installed model is no reader while the program that serves it is absent or unknown."""
    status = read_local_reader_status(_on_host(), program, roles=EXTRACTION_READER_ROLES)
    assert status.extraction_ready is False
    assert all(row.failed_condition_id == ProvisioningPreconditionCondition.RUNTIME_INSTALLED for row in status.roles)
    expected = None if program is None else LOCAL_AI_PROVISION_ACTION_ID
    assert all(row.recovery_action_id == expected for row in status.roles)


# ---------------------------------------------------------------------------
# a model's size is no judgement made here
# ---------------------------------------------------------------------------

# Larger than any computer's memory, so a size-based refusal would have to fire.
_BEYOND_ANY_MEMORY = 2**60


def test_a_model_larger_than_any_memory_is_not_refused_when_the_program_holds_it() -> None:
    """Whether the computer can hold the model is the native setup's and the agent's to say, never this read's."""
    lanes = _on_host(
        text_extraction=_lane(_TEXT, size=_BEYOND_ANY_MEMORY),
        vision_transcription=_lane(_VISION, size=_BEYOND_ANY_MEMORY),
    )
    status = read_local_reader_status(lanes, _READY, roles=EXTRACTION_READER_ROLES)
    assert status.extraction_ready is True
    assert all(row.ready and row.failed_condition_id is None for row in status.roles)


def test_a_model_larger_than_any_memory_waits_on_the_program_with_its_setup_action() -> None:
    """Only the program's state refuses here, so the refusal offers the setup that can change it."""
    lanes = _on_host(text_extraction=_lane(_TEXT, size=_BEYOND_ANY_MEMORY))
    status = read_local_reader_status(lanes, _ABSENT, roles=(ModelRole.TEXT_EXTRACTION,))
    (row,) = status.roles
    assert row.ready is False
    assert row.failed_condition_id == ProvisioningPreconditionCondition.RUNTIME_INSTALLED
    assert row.recovery_action_id == LOCAL_AI_PROVISION_ACTION_ID


def test_a_model_not_held_by_the_server_is_refused_for_the_setup_whatever_its_size() -> None:
    lanes = _on_host(vision_transcription=_lane(_VISION, size=_BEYOND_ANY_MEMORY, installed=False))
    status = read_local_reader_status(lanes, _READY, roles=(ModelRole.VISION_TRANSCRIPTION,))
    (row,) = status.roles
    assert row.failed_condition_id == ProvisioningPreconditionCondition.ROLE_MODEL_INSTALLED
    assert row.recovery_action_id == LOCAL_AI_PROVISION_ACTION_ID


def test_a_status_read_measures_nothing_of_this_computer(monkeypatch: pytest.MonkeyPatch) -> None:
    def _measured() -> object:
        raise AssertionError("the reader status must not measure this computer")

    monkeypatch.setattr(provisioning, "read_system_memory", _measured)
    monkeypatch.setattr(provisioning, "read_accelerator", _measured)
    status = read_local_reader_status(_on_host(), _READY, roles=EXTRACTION_READER_ROLES)
    assert status.extraction_ready is True


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


def test_the_report_names_only_on_host_models_and_each_role_s_selection() -> None:
    lanes: dict[ModelRole, RoleLane] = {
        ModelRole.VISION_TRANSCRIPTION: _lane(_VISION, off_host=True),
        ModelRole.TEXT_EXTRACTION: _lane(_TEXT),
        ModelRole.COLUMN_ROLE_MAPPING: _no_selection(),
    }
    report = read_local_reader_report(lanes)
    rows = {row.role: row for row in report.models}
    assert set(rows) == set(ModelRole)
    assert rows[ModelRole.VISION_TRANSCRIPTION].selected is True
    assert rows[ModelRole.VISION_TRANSCRIPTION].model is None
    assert rows[ModelRole.TEXT_EXTRACTION].model == _TEXT
    mapping = rows[ModelRole.COLUMN_ROLE_MAPPING]
    assert mapping.selected is False
    assert mapping.precondition_verdict is not None
    assert (
        mapping.precondition_verdict.failed_condition_id == ProvisioningPreconditionCondition.SELECTED_MODEL_AVAILABLE
    )
    assert mapping.facts["role_selection_required"] is True


def test_the_report_states_a_selected_model_s_catalogue_size_and_judges_none_of_it() -> None:
    lanes: dict[ModelRole, RoleLane] = {
        ModelRole.TEXT_EXTRACTION: _lane(_TEXT, size=_BEYOND_ANY_MEMORY),
        ModelRole.VISION_TRANSCRIPTION: _lane(_VISION, size=0),
    }
    rows = {row.role: row for row in read_local_reader_report(lanes).models}
    text = rows[ModelRole.TEXT_EXTRACTION]
    assert text.selected is True
    assert text.facts["size_bytes"] == _BEYOND_ANY_MEMORY
    assert text.precondition_verdict is None
    assert "size_bytes" not in rows[ModelRole.VISION_TRANSCRIPTION].facts
