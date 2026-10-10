"""The actor label of an execution comes from the session for an agent and from the request for a person."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import cast
from uuid import UUID

import pytest
from pydantic import BaseModel

from ....core.models import STRICT_FROZEN_CONFIG
from ...user_profile.access_contracts import SessionKind
from ..execution_actor import OperationExecutionCaller, OperationExecutionCallerReader, execution_actor_label
from ..interactions import OperationActorReference
from ..models import OperationIdentity
from ..owner import OperationExecutorContext
from ..registry import OperationFrontendProjection

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_CLIENT = UUID("5aa00000-0000-4000-8000-0000000000dd")
_SUPPLIED = "  Typed by the caller  "
_IDENTITY = OperationIdentity(operation_id="a" * 64, definition_id="domain.thing.record", subject_ref="b" * 64)


class _DerivedActor(BaseModel):
    """The grammar the platform already requires of an actor it derives itself."""

    model_config = STRICT_FROZEN_CONFIG

    reference: OperationActorReference


@dataclass(frozen=True, slots=True)
class _IdentityOnly:
    """The one fact of an executor context the label reads."""

    identity: OperationIdentity


@dataclass(slots=True)
class _SessionHost:
    """Answers for one admitted invocation and keeps what it was asked."""

    caller: OperationExecutionCaller
    asked: list[OperationIdentity] = field(default_factory=list)

    def __call__(self, identity: OperationIdentity) -> OperationExecutionCaller:
        self.asked.append(identity)
        return self.caller


def _context() -> OperationExecutorContext:
    return cast(OperationExecutorContext, _IdentityOnly(_IDENTITY))


def _host(frontend: OperationFrontendProjection, kind: SessionKind = SessionKind.HUMAN) -> _SessionHost:
    return _SessionHost(OperationExecutionCaller(frontend=frontend, session_kind=kind, client_id=_CLIENT))


@pytest.mark.parametrize("kind", list(SessionKind))
def test_an_agent_execution_is_labelled_from_its_session_and_never_from_the_request(kind: SessionKind) -> None:
    """Whatever an MCP caller sends, the label names the session's kind and client."""
    host = _host(OperationFrontendProjection.MCP, kind)

    label = execution_actor_label(host, _context(), supplied=_SUPPLIED)

    assert label == f"agent:mcp.{kind.value}.{_CLIENT}"
    assert host.asked == [_IDENTITY]
    assert execution_actor_label(host, _context(), supplied="another label") == label
    assert "Typed" not in label


@pytest.mark.parametrize("kind", list(SessionKind))
def test_the_agent_label_is_a_bounded_actor_reference(kind: SessionKind) -> None:
    """The label fits every stored actor field and reads as an agent, not as a person."""
    label = execution_actor_label(_host(OperationFrontendProjection.MCP, kind), _context(), supplied=_SUPPLIED)

    assert label.startswith("agent:")
    assert len(label) <= 128
    assert _DerivedActor(reference=label).reference == label


@pytest.mark.parametrize("frontend", [OperationFrontendProjection.CLI, OperationFrontendProjection.TUI])
def test_a_person_execution_keeps_the_supplied_label_exactly(frontend: OperationFrontendProjection) -> None:
    """The command line and the terminal interface record what they sent, unchanged."""
    host = _host(frontend)

    assert execution_actor_label(host, _context(), supplied=_SUPPLIED) == _SUPPLIED
    assert host.asked == [_IDENTITY]


def test_without_a_session_host_the_supplied_label_stands_and_no_identity_is_read() -> None:
    """Where nothing hosts a session no frontend exists to tell apart, and the context is not consulted."""
    reader: OperationExecutionCallerReader | None = None
    context_without_identity = cast(OperationExecutorContext, object())

    assert execution_actor_label(reader, context_without_identity, supplied=_SUPPLIED) == _SUPPLIED
