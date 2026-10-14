"""The service's hosted tree registry, bound to exact admitted leases.

A tree lives exactly as long as the lease it was started for. Retirement of
that lease, from whichever path ends it, reaches :meth:`session_retired`, which
only records the stop and hands it to a bounded background reaper: it never
blocks and never raises, so a retirement observer can finish its sweep.
Service shutdown waits for every reaper. While any tree is bound, a timer
invokes the generic runtime lease observer to revalidate
its leases, so expiry and lock end the tree even when no frontend is calling;
revalidation reads deadlines and never refreshes idle time.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Generator, Iterable
from contextlib import contextmanager
from dataclasses import dataclass, field
from threading import Event, Lock, Thread
from typing import Final
from uuid import UUID

from cadrumo.core.logging import get_logger

from .controller import AgentHostController

_LOGGER = get_logger(__name__)

_REVALIDATE_SECONDS: Final = 1.0


@dataclass
class _BoundAgent:
    profile_id: UUID
    session_id: UUID
    connection_id: UUID
    controller: AgentHostController | None = None
    retired: bool = False


@dataclass(frozen=True, slots=True)
class AgentTreeOwner:
    """The exact profile, lease and connection that started one agent tree.

    A process of the tree is that lease's agent and nothing else: its
    connections are admitted only as the agent, under this lease.
    """

    profile_id: UUID
    session_id: UUID
    connection_id: UUID


@dataclass
class _Reaper:
    session_id: UUID
    profile_id: UUID
    done: Event = field(default_factory=Event)
    failed: bool = False


class RuntimeAgentHosts:
    """Bind, publish, retire and reap hosted agent trees; at most one per profile."""

    def __init__(self, *, revalidate: Callable[[], None]) -> None:
        """Take the runtime's lease revalidation, called by the timer while any tree is bound."""
        self._revalidate = revalidate
        self._lock = Lock()
        self._bound: dict[UUID, _BoundAgent] = {}
        self._reapers: list[_Reaper] = []
        self._trees: list[tuple[AgentHostController, AgentTreeOwner]] = []
        self._closed = False
        self._preparing: set[UUID] = set()
        self._timer: Thread | None = None
        self._timer_stop = Event()

    def reserve(self, *, profile_id: UUID, session_id: UUID, connection_id: UUID) -> bool:
        """Claim the profile's one agent for this session; ``False`` when the profile already has one."""
        with self._lock:
            if self._closed or any(agent.profile_id == profile_id for agent in self._bound.values()):
                return False
            if profile_id in self._preparing:
                # The profile's stores are being brought to current for an earlier start.
                return False
            if any(reaper.profile_id == profile_id and not reaper.done.is_set() for reaper in self._reapers):
                return False
            self._bound[session_id] = _BoundAgent(profile_id, session_id, connection_id)
            return True

    def track(self, controller: AgentHostController, owner: AgentTreeOwner) -> None:
        """Hold a tree and its owning lease for membership questions from before its start until it is reaped."""
        with self._lock:
            self._trees.append((controller, owner))

    def untrack(self, controller: AgentHostController) -> None:
        """Forget a tree whose process is gone."""
        with self._lock:
            self._trees = [(tree, owner) for tree, owner in self._trees if tree is not controller]

    def hosting(self) -> bool:
        """Whether any agent tree is starting, running or being reaped."""
        with self._lock:
            return bool(self._trees)

    def contains_process_id(self, process_id: int) -> bool:
        """Whether the process belongs to any hosted agent tree, starting, running or being reaped."""
        with self._lock:
            trees = tuple(self._trees)
        return any(tree.contains_process_id(process_id) for tree, _owner in trees)

    def owner_of_process(self, process_id: int) -> AgentTreeOwner | None:
        """The lease whose agent tree holds this process, while that tree is bound to it and serving."""
        with self._lock:
            trees = tuple(self._trees)
        for tree, owner in trees:
            if tree.contains_process_id(process_id):
                return owner if self.is_current(owner.session_id) else None
        return None

    def trees_of_profile(self, profile_id: UUID) -> tuple[AgentTreeOwner, ...]:
        """The owners of the profile's bound trees."""
        with self._lock:
            return tuple(
                AgentTreeOwner(agent.profile_id, agent.session_id, agent.connection_id)
                for agent in self._bound.values()
                if agent.profile_id == profile_id
            )

    @contextmanager
    def preparing(self, profile_id: UUID) -> Generator[None]:
        """Hold the profile's stores for one start's store sequence; no other start of the profile is reserved.

        The hold outlives the claim: a session that ends while its stores are
        being prepared gives up its claim, but no new claim is admitted until
        the sequence's processes are gone.
        """
        with self._lock:
            self._preparing.add(profile_id)
        try:
            yield
        finally:
            with self._lock:
                self._preparing.discard(profile_id)

    def quiesced(self, *, profile_id: UUID, session_id: UUID) -> bool:
        """Whether this session's claim is the profile's only agent and no tree of the profile exists.

        A tree being reaped, or one whose stop could not be confirmed, may
        still hold the agent's stores: the profile is then not quiet.
        """
        with self._lock:
            claims = [agent for agent in self._bound.values() if agent.profile_id == profile_id]
            if len(claims) != 1 or claims[0].session_id != session_id or claims[0].controller is not None:
                return False
            if any(owner.profile_id == profile_id for _tree, owner in self._trees):
                return False
            return not any(
                reaper.profile_id == profile_id and (reaper.failed or not reaper.done.is_set())
                for reaper in self._reapers
            )

    def is_current(self, session_id: UUID) -> bool:
        """Whether this session's claim stands: not retired and the owner not closed."""
        with self._lock:
            agent = self._bound.get(session_id)
            return agent is not None and not agent.retired and not self._closed

    def publish(self, session_id: UUID, controller: AgentHostController) -> bool:
        """Attach a started tree to its claim; ``False`` when the session ended while it started."""
        with self._lock:
            agent = self._bound.get(session_id)
            if agent is None or agent.retired or self._closed:
                return False
            agent.controller = controller
            self._start_timer()
            return True

    def release(self, session_id: UUID) -> None:
        """Drop a claim whose start failed; the caller has already stopped any tree it began."""
        with self._lock:
            agent = self._bound.get(session_id)
            if agent is not None and agent.controller is None:
                self._bound.pop(session_id)

    def session_retired(self, session_id: UUID) -> None:
        """Hand the stop of this exact lease's tree to a reaper; never blocks and never raises."""
        try:
            with self._lock:
                agent = self._bound.get(session_id)
                if agent is None:
                    return
                agent.retired = True
                if agent.controller is None:
                    # Still starting: the start sees the retirement and stops its own tree.
                    self._bound.pop(session_id)
                    return
                self._bound.pop(session_id)
                self._reap(agent)
        except Exception:
            _LOGGER.exception("agent tree stop could not be handed to its reaper")

    def stop_profiles(self, profile_ids: Iterable[UUID], *, deadline: float) -> bool:
        """Stop and reap every tree of these profiles; ``True`` once all are gone within the bound."""
        wanted = frozenset(profile_ids)
        with self._lock:
            for agent in [agent for agent in self._bound.values() if agent.profile_id in wanted]:
                agent.retired = True
                self._bound.pop(agent.session_id)
                if agent.controller is not None:
                    self._reap(agent)
            reapers = [reaper for reaper in self._reapers if reaper.profile_id in wanted]
        return _join(reapers, deadline)

    def close(self, *, deadline: float) -> frozenset[UUID]:
        """Refuse new trees, stop every bound tree, and wait for every reaper within the bound.

        Return the profiles whose tree was not confirmed gone.
        """
        with self._lock:
            self._closed = True
            for agent in tuple(self._bound.values()):
                agent.retired = True
                self._bound.pop(agent.session_id)
                if agent.controller is not None:
                    self._reap(agent)
            reapers = list(self._reapers)
        self._timer_stop.set()
        _join(reapers, deadline)
        return frozenset(reaper.profile_id for reaper in reapers if not reaper.done.is_set() or reaper.failed)

    def bound_sessions(self) -> frozenset[UUID]:
        """The sessions that hold a published or starting tree."""
        with self._lock:
            return frozenset(self._bound)

    def _reap(self, agent: _BoundAgent) -> None:
        controller = agent.controller
        if controller is None:
            return
        reaper = _Reaper(agent.session_id, agent.profile_id)
        self._reapers = [item for item in self._reapers if not item.done.is_set() or item.failed]
        self._reapers.append(reaper)
        Thread(target=self._stop, args=(controller, reaper), name="agent-tree-reaper", daemon=True).start()

    def _stop(self, controller: AgentHostController, reaper: _Reaper) -> None:
        try:
            controller.stop()
        except Exception:
            # The tree's containment could not be confirmed; shutdown reports it as uncontained.
            reaper.failed = True
            _LOGGER.exception("agent tree stop failed")
        else:
            self.untrack(controller)
        finally:
            reaper.done.set()

    def _start_timer(self) -> None:
        if self._timer is not None and self._timer.is_alive():
            return
        self._timer_stop.clear()
        self._timer = Thread(target=self._tick, name="agent-lease-revalidation", daemon=True)
        self._timer.start()

    def _tick(self) -> None:
        while not self._timer_stop.wait(_REVALIDATE_SECONDS):
            with self._lock:
                if self._closed or not any(agent.controller is not None for agent in self._bound.values()):
                    return
            try:
                self._revalidate()
            except Exception:
                _LOGGER.exception("agent lease revalidation failed")


def _join(reapers: list[_Reaper], deadline: float) -> bool:
    return all(reaper.done.wait(max(0.0, deadline - time.monotonic())) and not reaper.failed for reaper in reapers)
