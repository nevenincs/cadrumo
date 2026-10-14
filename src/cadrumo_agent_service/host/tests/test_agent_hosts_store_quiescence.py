"""A profile's agent stores are changed only while the profile holds no other agent tree or start."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from uuid import uuid4

import pytest

from ..agent_hosts import AgentTreeOwner, RuntimeAgentHosts
from ..controller import AgentGenerations, AgentHostController, AgentLaunch, AgentProcess, ResolvedAgentCredentials

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


class _NeverStarted:
    """The launcher and credential source of a tree that is never started: only its identity matters here."""

    def launch(
        self, *, executable: Path, arguments: Sequence[str], directory: Path, environment: Mapping[str, str]
    ) -> AgentProcess:
        raise AssertionError("never started")

    def resolve_for_agent(self) -> ResolvedAgentCredentials:
        raise AssertionError("never started")

    def current_generations(self) -> AgentGenerations | None:
        return None


def _controller() -> AgentHostController:
    launch = AgentLaunch(executable=Path("/agent"), arguments=(), directory=Path("/root"), environment={})
    return AgentHostController(launcher=_NeverStarted(), credentials=_NeverStarted(), launch=launch)


def test_the_only_claim_with_no_tree_is_quiet_and_any_other_claim_or_tree_is_not() -> None:
    hosts = RuntimeAgentHosts(revalidate=lambda: None)
    profile, session, other_profile = uuid4(), uuid4(), uuid4()
    assert hosts.reserve(profile_id=profile, session_id=session, connection_id=uuid4())
    assert hosts.quiesced(profile_id=profile, session_id=session)
    assert not hosts.quiesced(profile_id=profile, session_id=uuid4())
    # Another profile's tree does not concern this profile's stores.
    hosts.track(_controller(), AgentTreeOwner(other_profile, uuid4(), uuid4()))
    assert hosts.quiesced(profile_id=profile, session_id=session)
    tree = _controller()
    hosts.track(tree, AgentTreeOwner(profile, uuid4(), uuid4()))
    assert not hosts.quiesced(profile_id=profile, session_id=session)
    hosts.untrack(tree)
    assert hosts.quiesced(profile_id=profile, session_id=session)


def test_no_start_of_the_profile_is_reserved_while_its_stores_are_prepared_even_after_the_claim_ends() -> None:
    hosts = RuntimeAgentHosts(revalidate=lambda: None)
    profile, session = uuid4(), uuid4()
    assert hosts.reserve(profile_id=profile, session_id=session, connection_id=uuid4())
    with hosts.preparing(profile):
        hosts.session_retired(session)
        assert not hosts.reserve(profile_id=profile, session_id=uuid4(), connection_id=uuid4())
        assert hosts.reserve(profile_id=uuid4(), session_id=uuid4(), connection_id=uuid4())
    assert hosts.reserve(profile_id=profile, session_id=uuid4(), connection_id=uuid4())
