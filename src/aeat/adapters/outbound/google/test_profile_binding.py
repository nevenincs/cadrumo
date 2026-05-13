"""Tests for the Google OAuth active-profile resolver."""

from __future__ import annotations

from collections.abc import Callable

import pytest

from aeat.adapters.outbound.google._errors import GoogleAuthProfileUnboundError
from aeat.adapters.outbound.google._profile_binding import resolve_active_profile
from aeat.application.workflow._models import WorkflowState

pytestmark = [pytest.mark.unit, pytest.mark.domain_outbound]


class _StubRepository:
    """Drop-in for `WorkflowStateRepository` returning a pre-built state."""

    def __init__(self, state: WorkflowState) -> None:
        self._state = state

    def load(self) -> WorkflowState:
        return self._state


def _patch_repository(monkeypatch: pytest.MonkeyPatch, state: WorkflowState) -> None:
    """Wire `_StubRepository(state)` into the resolver's import path."""

    factory: Callable[[], _StubRepository] = lambda: _StubRepository(state)
    monkeypatch.setattr(
        "aeat.adapters.outbound.google._profile_binding.workflow_state_repository",
        factory,
    )


def test_override_wins_over_workflow_state(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_repository(monkeypatch, WorkflowState(active_profile="primary"))
    assert resolve_active_profile("business") == "business"


def test_override_is_stripped_of_surrounding_whitespace(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_repository(monkeypatch, WorkflowState())
    assert resolve_active_profile("  business  ") == "business"


def test_falls_back_to_workflow_state_when_no_override(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_repository(monkeypatch, WorkflowState(active_profile="primary"))
    assert resolve_active_profile() == "primary"


def test_falls_back_when_override_is_empty_string(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_repository(monkeypatch, WorkflowState(active_profile="primary"))
    assert resolve_active_profile("") == "primary"


def test_falls_back_when_override_is_whitespace(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_repository(monkeypatch, WorkflowState(active_profile="primary"))
    assert resolve_active_profile("   ") == "primary"


def test_strips_workflow_state_active_profile(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_repository(monkeypatch, WorkflowState(active_profile="  primary  "))
    assert resolve_active_profile() == "primary"


def test_raises_when_no_override_and_no_active_profile(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_repository(monkeypatch, WorkflowState())
    with pytest.raises(GoogleAuthProfileUnboundError) as exc_info:
        resolve_active_profile()
    error = exc_info.value
    assert error.suggestion == "aeat config init --tax-id <NIF>"
    assert error.context == {"override": "", "active_profile": ""}


def test_raises_when_active_profile_is_blank_string(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_repository(monkeypatch, WorkflowState(active_profile="   "))
    with pytest.raises(GoogleAuthProfileUnboundError):
        resolve_active_profile()


def test_raised_error_carries_stable_registry_code(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_repository(monkeypatch, WorkflowState())
    try:
        resolve_active_profile()
    except GoogleAuthProfileUnboundError as err:
        assert err.code.code == "REFUSED_GOOGLE_PROFILE_UNBOUND"
    else:
        pytest.fail("resolve_active_profile must raise when no profile is bound")
