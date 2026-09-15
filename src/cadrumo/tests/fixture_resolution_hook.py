"""Fail a session whose collected items request a fixture pytest cannot resolve.

pytest resolves a test's fixture requests only at SETUP. A test naming a
fixture that is defined nowhere, or defined somewhere the test cannot see,
therefore collects cleanly and only errors when it is executed. Every
collect-only preflight reads it as healthy, and a lane that deselects it by
marker, or that is itself non-blocking, never reports it at all: the test is
dead and nothing says so.

The fixture closure is already computed at collection, so the defect is
decidable there. :func:`apply` checks every collected item's static closure --
parameters, ``usefixtures``, autouse fixtures and their transitive
dependencies -- against the fixture definitions pytest resolved for that
item's own node, and records every name that resolves to nothing. Direct
parametrization resolves its arguments; indirect parametrization does not,
because it still needs a real fixture of that name.

The refusal never aborts the run. Every other test still executes and reports
its own verdict; at session finish an ``OK``, ``TESTS_FAILED`` or
``NO_TESTS_COLLECTED`` status becomes ``USAGE_ERROR``, and the terminal summary
names each refused request. Any other status -- an interruption, an internal
error, a usage error, or a custom ``pytest.exit`` code -- already carries a more
specific verdict and is preserved. Aborting at collection instead would erase
every healthy verdict in the lane for the sake of the dead ones.

The same hand-off works in every mode: inside an xdist worker the requests
travel to the controller through ``workeroutput`` and are absorbed on
node-down, because a raise there kills the worker and surfaces as an internal
error; under ``-n0`` and ``--collect-only`` (xdist disables itself for
collection) they are recorded directly.

Where the check stops:

- Dynamic requests through ``request.getfixturevalue`` are not in the static
  closure and are not checked.
- Only items that were collected are checked. A module that fails to import,
  or a path no invocation names, is outside every collection this hook sees.
- Items that carry no fixture closure (custom item types) are skipped. Test
  functions and doctest items carry one and are checked.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

import pytest

UNRESOLVED_FIXTURES_WORKEROUTPUT_KEY = "cadrumo_unresolved_fixture_requests"
"""``config.workeroutput`` key carrying the refused requests out of an xdist worker."""

_REQUEST_FIXTURE_NAME = "request"
_OVERRIDABLE_EXIT_STATUSES = frozenset(
    {pytest.ExitCode.OK, pytest.ExitCode.TESTS_FAILED, pytest.ExitCode.NO_TESTS_COLLECTED},
)


@runtime_checkable
class _FixtureClosure(Protocol):
    """The two closure facts pytest computes for a fixture-requesting item."""

    names_closure: list[str]
    name2fixturedefs: Mapping[str, Sequence[object]]


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


def unresolved_fixture_requests(items: Iterable[pytest.Item]) -> tuple[UnresolvedFixtureRequest, ...]:
    """Return every item whose static fixture closure names an unresolvable fixture.

    pytest records, per item, the definitions applicable to that item's node
    for every name in its closure: visible fixtures (so a definition elsewhere
    in the tree does not count, and a class or module override does), plus the
    pseudo-definitions direct parametrization creates. A closure name with no
    applicable definition, other than pytest's built-in ``request``, is
    unresolved.

    Args:
        items: The collected items to check.

    Returns:
        The refused requests, sorted by node id.

    Raises:
        pytest.UsageError: When an item carries a fixture closure of a shape
            this check cannot read; checking nothing would read green.
    """
    found: list[UnresolvedFixtureRequest] = []
    for item in items:
        closure = getattr(item, "_fixtureinfo", None)
        if closure is None:
            continue
        if not isinstance(closure, _FixtureClosure):
            raise pytest.UsageError(
                f"{item.nodeid}: pytest's fixture closure no longer exposes names_closure and "
                "name2fixturedefs; fixture resolution of the collected tests cannot be checked",
            )
        missing = tuple(
            name
            for name in closure.names_closure
            if name != _REQUEST_FIXTURE_NAME and not closure.name2fixturedefs.get(name)
        )
        if missing:
            path, lineno, _ = item.reportinfo()
            line = "" if lineno is None else f":{lineno + 1}"
            found.append(UnresolvedFixtureRequest(item.nodeid, f"{path}{line}", missing))
    return tuple(sorted(found))


_refused_requests: set[str] = set()
"""Refused requests for this session, deduplicated across xdist workers.

Module-level because the controller sees each worker exactly once, on node
down, and must keep the population until the session finishes.
"""


def apply(config: pytest.Config, items: Sequence[pytest.Item]) -> None:
    """Record every collected item that requests an unresolvable fixture.

    Must run before any selection or hold removes items, so a dead test that
    the active marker expression would deselect is still refused. Never
    modifies ``items`` and never aborts: the verdict lands at session finish.

    Args:
        config: The active :class:`pytest.Config` from the collection hook.
        items: The collected items; never modified.
    """
    rendered = [request.render() for request in unresolved_fixture_requests(items)]
    if not rendered:
        return
    if hasattr(config, "workerinput"):
        config.workeroutput[UNRESOLVED_FIXTURES_WORKEROUTPUT_KEY] = rendered
        return
    _refused_requests.update(rendered)


def reset_refused_requests() -> None:
    """Clear refused-request state for a new pytest session."""
    _refused_requests.clear()


def record_refused_from_node(node: object) -> None:
    """Absorb one xdist worker's refused requests as its node goes down.

    Args:
        node: The xdist worker node that just went down.
    """
    payload = getattr(node, "workeroutput", {}) or {}
    _refused_requests.update(payload.get(UNRESOLVED_FIXTURES_WORKEROUTPUT_KEY, ()))


def fail_session_on_refused_requests(session: pytest.Session) -> None:
    """Turn a passing, failing or empty session with refused requests into ``USAGE_ERROR``.

    Args:
        session: The finishing session, whose exit status may be overridden.
    """
    if _refused_requests and session.exitstatus in _OVERRIDABLE_EXIT_STATUSES:
        session.exitstatus = pytest.ExitCode.USAGE_ERROR


def report_refused_requests(terminalreporter: _TerminalWriter) -> None:
    """Name the refused requests this session collected.

    Args:
        terminalreporter: The active terminal reporter.
    """
    if not _refused_requests:
        return
    terminalreporter.write_sep("=", "UNRESOLVED FIXTURE REQUESTS", red=True, bold=True)
    terminalreporter.write_line(
        f"{len(_refused_requests)} collected test(s) request a fixture that no visible definition provides; "
        "they cannot run, so this session fails.",
        red=True,
        bold=True,
    )
    for rendered in sorted(_refused_requests):
        terminalreporter.write_line(f"  {rendered}")
