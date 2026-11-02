"""Filed discovery reduces only on undeclared facts, never on an unreadable profile."""

from __future__ import annotations

from typing import cast

import pytest

from ...adapters.persistence.storage.custody.errors import ProfileCustodyRecordError
from ...adapters.persistence.storage.errors import StorageError
from ...application.live.filed_history_discovery import resolve_discovery_profile
from ...application.wizard import status as wizard_status
from ...application.workflow import persistence as workflow_persistence
from ...application.workflow.state_models import WorkflowState
from ...core.errors.hierarchy import CadrumoError
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.deadlines.errors import ProfileError

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


class _Operation:
    def profile_schema(self) -> object:
        return object()


_OPERATION = cast("PinnedAuthorityOperation", _Operation())


class _Workflow:
    def __init__(self, failure: CadrumoError | None = None) -> None:
        self._failure = failure

    def load(self) -> WorkflowState:
        if self._failure is not None:
            raise self._failure
        return WorkflowState()


@pytest.mark.parametrize(
    "failure",
    (StorageError("synthetic store failure"), ProfileCustodyRecordError("synthetic custody failure")),
)
def test_an_unreadable_profile_state_propagates_instead_of_looking_like_no_profile(
    monkeypatch: pytest.MonkeyPatch,
    failure: CadrumoError,
) -> None:
    monkeypatch.setattr(workflow_persistence, "workflow_state_repository", lambda: _Workflow(failure))

    with pytest.raises(type(failure)):
        resolve_discovery_profile(_OPERATION)


def test_no_active_profile_reduces_discovery(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(workflow_persistence, "workflow_state_repository", _Workflow)

    assert resolve_discovery_profile(_OPERATION) is None


def test_a_profile_with_undeclared_facts_reduces_discovery(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*_args: object, **_kwargs: object) -> None:
        raise ProfileError("iva.m303_regime_composition must be explicitly declared for Modelo IVA")

    monkeypatch.setattr(workflow_persistence, "workflow_state_repository", _Workflow)
    monkeypatch.setattr(wizard_status, "load_active_taxpayer_profile", refuse)

    assert resolve_discovery_profile(_OPERATION) is None
