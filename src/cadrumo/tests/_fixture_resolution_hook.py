"""Refuse a collection whose items request a fixture pytest cannot resolve.

pytest resolves a test's fixture requests only at SETUP. A test naming a
fixture that is defined nowhere, or defined in a conftest the test cannot see,
therefore collects cleanly and only errors when it is executed. Every
collect-only preflight reads it as healthy, and a lane that deselects it by
marker, or that is itself non-blocking, never reports it at all: the test is
dead and nothing says so.

The fixture closure is already computed at collection, so the defect is
decidable there. :func:`apply` checks every collected item's static closure --
parameters, ``usefixtures``, autouse fixtures and their transitive
dependencies -- against the fixture definitions visible from that item's node,
and refuses the collection when any name resolves to nothing.

Where the check stops:

- Dynamic requests through ``request.getfixturevalue`` are not in the static
  closure and are not checked.
- Only items that were collected are checked. A module that fails to import,
  or a path no invocation names, is outside every collection this hook sees.
- Items without a fixture closure (doctests, custom item types) are skipped.

Under ``-n0`` and ``--collect-only`` (xdist disables itself for collection) the
refusal is an immediate :class:`pytest.UsageError`. Inside an xdist worker a
raise would kill the worker and surface as an internal error, so the worker
records the refused requests in ``workeroutput``; the controller absorbs them
on node-down, overrides the session exit status to ``USAGE_ERROR`` and names
them in the terminal summary.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol

import pytest

UNRESOLVED_FIXTURES_WORKEROUTPUT_KEY = "cadrumo_unresolved_fixture_requests"
"""``config.workeroutput`` key carrying the refused requests out of an xdist worker."""

_FIXTURE_MANAGER_PLUGIN_NAME = "funcmanage"
_REQUEST_FIXTURE_NAME = "request"


class _FixtureManager(Protocol):
    """The one lookup this hook needs from pytest's fixture manager."""

    def getfixturedefs(self, argname: str, node: pytest.Item) -> Sequence[object] | None: ...


class _TerminalWriter(Protocol):
    """The two writer methods this reporter needs from pytest's terminal."""

    def write_sep(self, sep: str, title: str, **markup: bool) -> None: ...

    def write_line(self, line: str, **markup: bool) -> None: ...


@dataclass(frozen=True, order=True)
class UnresolvedFixtureRequest:
    """One collected item and the fixture names its closure cannot resolve."""

    nodeid: str
    location: str
    fixture_names: tuple[str, ...]

    def render(self) -> str:
        """Return the single-line refusal naming the item, its source and the names."""
        return f"{self.nodeid} ({self.location}): unresolved fixture(s) {list(self.fixture_names)}"


def unresolved_fixture_requests(config: pytest.Config, items: Iterable[pytest.Item]) -> tuple[UnresolvedFixtureRequest, ...]:
    """Return every item whose static fixture closure names an unresolvable fixture.

    A name resolves when a fixture definition of that name is visible from the
    item's own node, when direct parametrization supplies it, or when it is
    pytest's built-in ``request``. Visibility is node-scoped: a fixture defined
    in a conftest the item cannot see does not resolve it.

    Args:
        config: The active configuration, whose plugin manager owns the
            session fixture manager.
        items: The collected items to check.

    Returns:
        The refused requests, sorted by node id.
    """
    manager: _FixtureManager | None = config.pluginmanager.get_plugin(_FIXTURE_MANAGER_PLUGIN_NAME)
    if manager is None:
        return ()
    found: list[UnresolvedFixtureRequest] = []
    for item in items:
        fixture_names = getattr(item, "fixturenames", None)
        if not isinstance(fixture_names, list):
            continue
        callspec = getattr(item, "callspec", None)
        parametrized: Mapping[str, object] = getattr(callspec, "params", {}) if callspec is not None else {}
        missing = tuple(
            name
            for name in fixture_names
            if name != _REQUEST_FIXTURE_NAME and name not in parametrized and not manager.getfixturedefs(name, item)
        )
        if missing:
            path, lineno, _ = item.reportinfo()
            line = "" if lineno is None else f":{lineno + 1}"
            found.append(UnresolvedFixtureRequest(item.nodeid, f"{path}{line}", missing))
    return tuple(sorted(found))


def apply(config: pytest.Config, items: Sequence[pytest.Item]) -> None:
    """Refuse the collection when any collected item requests an unresolvable fixture.

    Must run before any selection or hold removes items, so a dead test that
    the active marker expression would deselect is still refused.

    Args:
        config: The active :class:`pytest.Config` from the collection hook.
        items: The collected items; never modified.

    Raises:
        pytest.UsageError: Outside an xdist worker, when any request is unresolved.
    """
    refused = unresolved_fixture_requests(config, items)
    if not refused:
        return
    rendered = [request.render() for request in refused]
    if hasattr(config, "workerinput"):
        config.workeroutput[UNRESOLVED_FIXTURES_WORKEROUTPUT_KEY] = rendered
        return
    raise pytest.UsageError(
        f"{len(rendered)} collected test(s) request a fixture that no visible definition provides; "
        "they would error at setup and never run:\n  " + "\n  ".join(rendered),
    )


_refused_from_workers: list[str] = []
"""Refused requests reported by xdist workers, deduplicated across workers.

Module-level because the controller sees each worker exactly once, on node
down, and must keep the population until the session finishes.
"""


def reset_refused_requests() -> None:
    """Clear controller-side refused-request state for a new pytest session."""
    _refused_from_workers.clear()


def record_refused_from_node(node: object) -> None:
    """Absorb one worker's refused requests as its node goes down.

    Args:
        node: The xdist worker node that just went down.
    """
    payload = getattr(node, "workeroutput", {}) or {}
    for rendered in payload.get(UNRESOLVED_FIXTURES_WORKEROUTPUT_KEY, ()):
        if rendered not in _refused_from_workers:
            _refused_from_workers.append(rendered)


def fail_session_on_refused_requests(session: pytest.Session) -> None:
    """Override the exit status of a distributed run whose workers refused requests.

    Args:
        session: The finishing session, whose exit status is overridden.
    """
    if _refused_from_workers:
        session.exitstatus = pytest.ExitCode.USAGE_ERROR


def report_refused_requests(terminalreporter: _TerminalWriter) -> None:
    """Name the refused requests a distributed run collected.

    Args:
        terminalreporter: The active terminal reporter.
    """
    if not _refused_from_workers:
        return
    terminalreporter.write_sep("=", "UNRESOLVED FIXTURE REQUESTS", red=True, bold=True)
    terminalreporter.write_line(
        f"{len(_refused_from_workers)} collected test(s) request a fixture that no visible definition provides.",
        red=True,
        bold=True,
    )
    for rendered in _refused_from_workers:
        terminalreporter.write_line(f"  {rendered}")
