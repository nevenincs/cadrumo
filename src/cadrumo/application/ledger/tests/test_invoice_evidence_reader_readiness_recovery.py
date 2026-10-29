"""The reader readiness rows name the setup action the judgement named, and only that one.

The status is judged by the real local reader status reader from the
components role's row for the local AI program and the lanes the person's
selection resolves to, with whether the server holds each model as the agent
states it, and is then projected by the readiness operation's own projection.
A row offers setup only when the judgement names it: a model the server does
not hold or a program that is not set up does, and a role with no selection or
an unknown program does not. Every model id is synthetic.
"""

from __future__ import annotations

from collections.abc import Mapping
from uuid import UUID

import pytest

from cadrumo_client.contracts.model_runs import ModelRunLane, ModelRunRefusal, ModelRunRefusalCode

from ....core.model_roles import ModelRole
from ...dependency_contracts import DependencyState
from ...local_reader import ProgramRow, RoleLane, read_local_reader_status
from ...probe_outcomes import LOCAL_AI_PROVISION_ACTION_ID, ProbePreconditionCondition
from ...tests.local_ai_program_rows import local_ai_row
from ..invoice_evidence_readiness_operation import LedgerEvidenceReaderReadinessProjection, ReaderRoleProjectionV1

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE = UUID("5c11a0e7-3b2d-4c6e-8f1a-2b3c4d5e6f70")
_VISION = "synthetic-vision:small"
_TEXT = "synthetic-text:small"


def _on_host(model: str, *, installed: bool) -> ModelRunLane:
    return ModelRunLane(
        provider_id="ollama",
        transport="api",
        model=model,
        reads_off_host=False,
        licence=None,
        size_bytes=None,
        vision=None,
        context_length=None,
        installed=installed,
    )


def _lanes(*, vision_installed: bool) -> Mapping[ModelRole, RoleLane]:
    """Both reader roles selected on the local lane, the text model held; the other roles have no selection."""
    return {
        ModelRole.TEXT_EXTRACTION: _on_host(_TEXT, installed=True),
        ModelRole.VISION_TRANSCRIPTION: _on_host(_VISION, installed=vision_installed),
        ModelRole.COLUMN_ROLE_MAPPING: ModelRunRefusal(code=ModelRunRefusalCode.NO_SELECTION),
        ModelRole.SUPPLY_NATURE_PROPOSAL: ModelRunRefusal(code=ModelRunRefusalCode.NO_SELECTION),
    }


_SET_UP: ProgramRow = local_ai_row(DependencyState.READY)


def _rows(program: ProgramRow = _SET_UP, *, vision_installed: bool = True) -> dict[str, ReaderRoleProjectionV1]:
    status = read_local_reader_status(_lanes(vision_installed=vision_installed), program)
    projection = LedgerEvidenceReaderReadinessProjection.from_status(_PROFILE, status)
    return {row.role: row for row in projection.roles}


def test_a_missing_model_offers_the_local_ai_setup_and_an_installed_one_is_ready() -> None:
    rows = _rows(vision_installed=False)

    vision = rows[ModelRole.VISION_TRANSCRIPTION.value]
    assert vision.model == _VISION
    assert vision.installed is False and vision.ready is False
    assert vision.failed_condition_id == ProbePreconditionCondition.ROLE_MODEL_INSTALLED.value
    assert vision.recovery_action_id == LOCAL_AI_PROVISION_ACTION_ID
    text = rows[ModelRole.TEXT_EXTRACTION.value]
    assert text.installed is True
    assert text.ready is True
    assert text.failed_condition_id is None
    assert text.recovery_action_id is None


def test_a_program_not_set_up_offers_the_local_ai_setup_on_every_on_host_role() -> None:
    rows = _rows(local_ai_row(DependencyState.ABSENT))

    assert set(rows) == {role.value for role in ModelRole}
    for role in (ModelRole.TEXT_EXTRACTION, ModelRole.VISION_TRANSCRIPTION):
        row = rows[role.value]
        assert not row.ready
        assert row.failed_condition_id == ProbePreconditionCondition.RUNTIME_INSTALLED.value
        assert row.recovery_action_id == LOCAL_AI_PROVISION_ACTION_ID


def test_an_unknown_program_offers_no_setup() -> None:
    """A components role that could not answer is no evidence the program is missing."""
    rows = _rows(None)

    for role in (ModelRole.TEXT_EXTRACTION, ModelRole.VISION_TRANSCRIPTION):
        row = rows[role.value]
        assert not row.ready
        assert row.failed_condition_id == ProbePreconditionCondition.RUNTIME_INSTALLED.value
        assert row.recovery_action_id is None


def test_a_role_with_no_selection_offers_no_setup() -> None:
    rows = _rows()

    supply = rows[ModelRole.SUPPLY_NATURE_PROPOSAL.value]
    assert supply.ready is False
    assert supply.model is None
    assert supply.failed_condition_id == ProbePreconditionCondition.SELECTED_MODEL_AVAILABLE.value
    assert supply.recovery_action_id is None
    assert rows[ModelRole.VISION_TRANSCRIPTION.value].recovery_action_id is None, "a ready role offers nothing"
