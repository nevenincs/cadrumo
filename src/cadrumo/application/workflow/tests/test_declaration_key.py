"""Anti-regression tests for the workflow declaration-pointer surface.

The public facade and engine must use the canonical state-contract helpers,
and ``declaration_key`` stores the filing year and bare registry token as
separate key segments, never as a combined token such as ``2025Q1``.

See Also:
    :func:`~application.workflow.declaration_key`
        Public facade helper that must remain the single declaration-key entry
        point for callers.
    :func:`~application.workflow._state_models.declaration_key`
        Canonical model helper whose separated period identity is under test.
    :func:`~application.workflow._state_models.update_declaration_pointer`
        Pointer upsert helper that writes keys through the same canonical path.
    :class:`~application.workflow.WorkflowState`
        Immutable state record whose ``declarations`` map is keyed by
        ``declaration_key``.
    :class:`~core.Period`
        Typed period identity required instead of combined string period tokens.
"""

from __future__ import annotations

import json
from typing import Any, cast

import pytest
from pydantic import ValidationError

from ....core import Modelo, Period
from ....domain.submission import ModeloDraftStatus
from .. import (
    WorkflowResult,
    WorkflowState,
    _engine,
    _run_models,
    _state_models,
    declaration_key,
    update_declaration_pointer,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_workflow_declaration_pointer_surface_uses_canonical_helpers() -> None:
    """Public and engine call sites use the canonical model helpers."""
    assert declaration_key is _state_models.declaration_key
    assert update_declaration_pointer is _state_models.update_declaration_pointer
    assert _engine.declaration_key is declaration_key


def test_workflow_facade_resolves_contracts_from_their_canonical_owners() -> None:
    """State and run symbols resolve directly from their cohesive owners."""
    assert WorkflowState is _state_models.WorkflowState
    assert WorkflowState.__module__ == "cadrumo.application.workflow._state_models"
    assert WorkflowResult is _run_models.WorkflowResult
    assert WorkflowResult.__module__ == "cadrumo.application.workflow._run_models"


def test_declaration_key_uses_separated_period_identity() -> None:
    period = Period.from_year_and_code(2025, "1T")

    assert declaration_key("130", period) == "130:2025:1T"


def test_declaration_key_rejects_combined_string_period() -> None:
    combined_period = cast(Any, "2025Q1")
    with pytest.raises(TypeError, match=r"cadrumo\.core\.Period"):
        declaration_key("130", combined_period)


def test_update_declaration_pointer_uses_typed_period_key() -> None:
    period = Period.from_year_and_code(2025, "1T")

    state = update_declaration_pointer(
        WorkflowState(),
        modelo="130",
        period=period,
        draft_id="d" * 64,
        status="BORRADOR",
    )

    assert set(state.declarations) == {"130:2025:1T"}
    pointer = state.declarations["130:2025:1T"]
    assert pointer.period == period
    assert pointer.draft_id == "d" * 64


def test_workflow_state_serialization_rejects_unknown_declaration_identity_and_status() -> None:
    """Persisted declaration pointers retain closed Modelo and draft-status identities."""
    period = Period.from_year_and_code(2025, "1T")
    state = update_declaration_pointer(
        WorkflowState(),
        modelo="130",
        period=period,
        draft_id="d" * 64,
        status="BORRADOR",
    )
    pointer = state.declarations["130:2025:1T"]
    assert pointer.modelo is Modelo.M130
    assert pointer.status is ModeloDraftStatus.BORRADOR

    persisted = json.loads(state.model_dump_json())
    for field, invalid_value in (("modelo", "999"), ("status", "NOT_A_DRAFT_STATUS")):
        invalid = json.loads(json.dumps(persisted))
        invalid["declarations"]["130:2025:1T"][field] = invalid_value

        with pytest.raises(ValidationError, match=field):
            WorkflowState.model_validate_json(json.dumps(invalid))
