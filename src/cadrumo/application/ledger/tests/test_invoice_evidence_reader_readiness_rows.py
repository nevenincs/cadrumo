"""The reader readiness rows state each role's judgement.

The status is judged by the real local reader status reader from the lanes the
person's selection resolves to, with whether the server holds each model as the
agent states it, and is then projected by the readiness operation's own
projection. Every model id is synthetic.
"""

from __future__ import annotations

from collections.abc import Mapping
from uuid import UUID

import pytest

from cadrumo_client.contracts.model_runs import ModelRunLane, ModelRunRefusal, ModelRunRefusalCode

from ....core.model_roles import ModelRole
from ...local_reader import RoleLane, read_local_reader_status
from ...probe_outcomes import ProbePreconditionCondition
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


def _rows(*, vision_installed: bool = True) -> dict[str, ReaderRoleProjectionV1]:
    status = read_local_reader_status(_lanes(vision_installed=vision_installed))
    projection = LedgerEvidenceReaderReadinessProjection.from_status(_PROFILE, status)
    return {row.role: row for row in projection.roles}


def test_a_missing_model_is_not_ready_and_an_installed_one_is_ready() -> None:
    rows = _rows(vision_installed=False)

    vision = rows[ModelRole.VISION_TRANSCRIPTION.value]
    assert vision.model == _VISION
    assert vision.installed is False and vision.ready is False
    assert vision.failed_condition_id == ProbePreconditionCondition.ROLE_MODEL_INSTALLED.value
    text = rows[ModelRole.TEXT_EXTRACTION.value]
    assert text.installed is True
    assert text.ready is True
    assert text.failed_condition_id is None


def test_a_role_with_no_selection_is_not_ready() -> None:
    rows = _rows()

    assert set(rows) == {role.value for role in ModelRole}
    supply = rows[ModelRole.SUPPLY_NATURE_PROPOSAL.value]
    assert supply.ready is False
    assert supply.model is None
    assert supply.failed_condition_id == ProbePreconditionCondition.SELECTED_MODEL_AVAILABLE.value
    assert rows[ModelRole.VISION_TRANSCRIPTION.value].ready is True
