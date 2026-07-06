"""Anti-regression tests for the workflow declaration-pointer surface (DB-05).

The public facade and engine must use the canonical ``_models.py`` helpers,
and ``declaration_key`` stores the filing year and bare registry token as
separate key segments, never as a combined token such as ``2025Q1``.

See Also:
    :func:`~application.workflow.declaration_key`
        Public facade helper that must remain the single declaration-key entry
        point for callers.
    :func:`~application.workflow._models.declaration_key`
        Canonical model helper whose separated period identity is under test.
    :func:`~application.workflow._models.update_declaration_pointer`
        Pointer upsert helper that writes keys through the same canonical path.
    :class:`~application.workflow.WorkflowState`
        Immutable state record whose ``declarations`` map is keyed by
        ``declaration_key``.
    :class:`~core.Period`
        Typed period identity required instead of combined string period tokens.
    Governing vault records
        ``2026-06-01-domain-boundary-audit-audit`` DB-05 and
        ``2026-06-01-domain-boundary-audit-plan`` W07.P19.S67-S69 record the
        duplicate-helper collapse and this regression surface.
"""

from __future__ import annotations

from typing import Any, cast

import pytest

from ....core import Period
from .. import WorkflowState, _engine, _models, declaration_key, update_declaration_pointer

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_workflow_declaration_pointer_surface_uses_canonical_helpers() -> None:
    """DB-05: public and engine call sites use the canonical model helpers."""
    assert declaration_key is _models.declaration_key
    assert update_declaration_pointer is _models.update_declaration_pointer
    assert _engine.declaration_key is declaration_key


def test_declaration_key_uses_separated_period_identity() -> None:
    period = Period.from_year_and_code(2025, "1T")

    assert declaration_key("130", period) == "130:2025:1T"


def test_declaration_key_rejects_combined_string_period() -> None:
    combined_period = cast(Any, "2025Q1")
    with pytest.raises(TypeError, match=r"aeat\.core\.Period"):
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
