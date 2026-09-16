"""Shared pytest collection policy enforcing taxonomy and live-import safety.

This module is test-infrastructure, not a production module. The repo-root
``conftest.py`` imports it so every item collected through that root passes
through the same enforcement surface.

The marker contract enforced by :func:`apply` on every collected item:

- Each item must carry exactly one execution marker from
  ``{unit, integration, aeat_live}``. Zero or more than one is refused.
- Each item must carry exactly one accepted ``hex_*`` marker at module level.
- A refusal raises :class:`pytest.UsageError` outside an xdist worker. Inside
  one it takes the same worker-to-controller channel as the serial hold, for
  the reason given below: raising there kills the worker, and the controller
  can then name neither the test nor the contract.
- A ``serial`` item is held out of any run with xdist workers active, and the
  hold is announced.

The live-import contract enforced by :func:`apply_banned_live_import_policy`:

- A file contributing an ``aeat_live`` item may not import any of the banned
  test-double or time-freezing modules. The policy reads source with
  :mod:`ast`; it never executes the file.

The ``serial`` hold exists because the marker was otherwise inert. pytest-xdist
has no notion of it -- its only scheduling primitive is ``--dist=loadgroup``
plus ``xdist_group`` -- so nothing enforced the marker's own contract ("must run
without xdist workers"). It was honoured solely by the justfile splitting the
integration lane into a ``not serial`` parallel pass and a ``-n0`` serial pass;
any other invocation (a bare ``pytest -m integration``, a path-scoped run) ran
isolation-sensitive tests against a run-varying set of co-resident files and
produced failures that belonged to the schedule, not the code.

The hold deselects inside each worker, emits a warning there, and carries the
held node ids back through ``workeroutput``. The controller then reports the
population and exits with ``USAGE_ERROR``. Raising directly from the collection
hook is not available: under xdist this hook runs INSIDE each worker, and an
exception there kills the worker and surfaces as an internal error. The
worker-to-controller handoff preserves a clean worker lifecycle while ensuring
the incomplete invocation cannot finish green.

The two policy functions compose in this order: :func:`apply` validates marker
taxonomy before :func:`apply_banned_live_import_policy` inspects live-marked
modules. The repo-root hook invokes them in that order exactly once per
collection.

Live AEAT access is opt-in gated by the shared :mod:`.live_gate` helper after
this taxonomy check.
"""

from __future__ import annotations

import ast
import warnings
from collections.abc import Iterable
from pathlib import Path
from typing import Protocol

import pytest

from cadrumo.tests.session_exit_status import refuse_session

_EXECUTION_MARKERS = frozenset({"unit", "integration", "aeat_live"})
_SERIAL_MARKER = "serial"
_MAX_NAMED_HELD_ITEMS = 10
_LIVE_ACCESS_MARKERS = frozenset({"aeat_live"})
_BANNED_LIVE_IMPORTS = frozenset(
    {
        "unittest",
        "unittest." + "mo" + "ck",
        "mo" + "ck",
        "pytest_mock",
        "responses",
        "httpx_mock",
        "pytest_httpx",
        "vcr",
        "vcrpy",
        "freezegun",
        "time_machine",
    },
)

SERIAL_HELD_WORKEROUTPUT_KEY = "cadrumo_serial_held"
"""``config.workeroutput`` key carrying the node ids held out of an xdist run."""

MARKER_VIOLATIONS_WORKEROUTPUT_KEY = "cadrumo_marker_violations"
"""``config.workeroutput`` key carrying marker-contract violations found in a worker."""


class SerialTestsHeldWarning(pytest.PytestWarning):
    """Announces ``serial`` items held out of a run with xdist workers active."""


class MarkerContractViolationWarning(pytest.PytestWarning):
    """Announces items refused inside a worker for violating the marker contract."""


_HEX_MARKERS = frozenset(
    {
        "hex_application",
        "hex_core",
        "hex_domain",
        "hex_entrypoint",
        "hex_inbound_adapter",
        "hex_outbound_adapter",
        "hex_persistence_adapter",
    },
)


def apply(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Apply the hexagonal marker taxonomy contract to the collected items.

    Raises :class:`pytest.UsageError` for items missing exactly one execution
    marker or exactly one accepted hexagonal architecture marker.

    Args:
        config: The active :class:`pytest.Config` from the collection hook.
        items: The mutable collection items list; filtered in-place.
    """
    remaining: list[pytest.Item] = []
    violations: list[str] = []
    offending: list[pytest.Item] = []
    for item in items:
        violation = _marker_contract_violation(item)
        if violation is not None:
            violations.append(violation)
            offending.append(item)
            continue
        remaining.append(item)
    items[:] = remaining
    _refuse_marker_violations(config, violations, offending)
    _hold_serial_items_from_xdist(config, items)


def _marker_contract_violation(item: pytest.Item) -> str | None:
    """Return the taxonomy violation this item carries, or ``None`` when it is sound."""
    owned = {m.name for m in item.iter_markers()}
    execution = owned & _EXECUTION_MARKERS
    if len(execution) != 1:
        return (
            f"{item.nodeid}: must carry exactly one of {{unit, integration, aeat_live}}, "
            f"found {sorted(execution) or 'none'}"
        )
    hex_markers = {name for name in owned if name.startswith("hex_")}
    if len(hex_markers) != 1 or not hex_markers <= _HEX_MARKERS:
        return f"{item.nodeid}: must carry exactly one accepted hex_* marker, found {sorted(hex_markers) or 'none'}"
    return None


def _refuse_marker_violations(
    config: pytest.Config,
    violations: list[str],
    offending: list[pytest.Item],
) -> None:
    """Refuse a mis-marked item where the refusal can actually be read.

    Outside a worker the violation raises, which is the clearest report pytest
    offers. INSIDE an xdist worker it must not: this hook runs in the worker,
    and an exception there kills it, so the controller reports only
    ``assert not crashitem`` and never names the test or the contract. The
    violation therefore travels the same worker-to-controller channel the
    serial hold uses, leaving a clean worker lifecycle while keeping the run
    from finishing green.
    """
    if not violations:
        return
    if not hasattr(config, "workerinput"):
        raise pytest.UsageError("\n".join(violations))
    config.hook.pytest_deselected(items=offending)
    config.workeroutput[MARKER_VIOLATIONS_WORKEROUTPUT_KEY] = violations
    warnings.warn(
        "Marker contract violated by "
        f"{len(violations)} collected test(s), which did NOT execute: {'; '.join(violations)}",
        MarkerContractViolationWarning,
        stacklevel=1,
    )


def apply_banned_live_import_policy(items: Iterable[pytest.Item]) -> None:
    """Exit collection when a live-marked module imports a banned dependency.

    This policy is intentionally separate from :func:`apply`: callers retain
    the established taxonomy-first error order while the root conftest can own
    both collection contracts. It makes no change to ``items`` and is therefore
    idempotent across repeated hook delivery.

    Args:
        items: Collected test items whose live-marked source modules are scanned.
    """
    import_violations = _check_banned_live_imports(_live_item_paths(items))
    if not import_violations:
        return
    header = "Banned import in live-marked file (see src/cadrumo/tests/README.md):"
    message = header + "\n  " + "\n  ".join(import_violations)
    pytest.exit(message, returncode=2)


def _live_item_paths(items: Iterable[pytest.Item]) -> set[Path]:
    """Return source files that contributed an ``aeat_live`` item."""
    return {item.path for item in items if {mark.name for mark in item.iter_markers()} & _LIVE_ACCESS_MARKERS}


def _check_banned_live_imports(paths: Iterable[Path]) -> list[str]:
    """Return one violation for each live-marked module importing a banned target."""
    violations: list[str] = []
    for path in sorted(paths):
        hits = _scan_banned_live_imports(path)
        if hits:
            violations.append(f"{path}: imports banned symbol(s) {sorted(hits)} in a file containing an aeat_live item")
    return violations


def _scan_banned_live_imports(path: Path) -> set[str]:
    """AST-scan ``path`` for banned import targets without executing its source.

    Source is read as bytes so :func:`ast.parse` honours PEP 263 encoding
    cookies. An unreadable or syntactically invalid module is left to pytest's
    own collection diagnostics rather than being misreported as this policy.
    """
    try:
        source = path.read_bytes()
    except OSError:
        return set()
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError:
        return set()

    hits: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            hits.update(_banned_hits_for_import(node))
        elif isinstance(node, ast.ImportFrom):
            hits.update(_banned_hits_for_import_from(node))
    return hits


def _banned_hits_for_import(node: ast.Import) -> set[str]:
    """Collect banned targets from one ``import X[, Y...]`` statement."""
    hits: set[str] = set()
    for alias in node.names:
        name = alias.name
        if name in _BANNED_LIVE_IMPORTS:
            hits.add(name)
        root = name.split(".", 1)[0]
        if root in _BANNED_LIVE_IMPORTS:
            hits.add(root)
    return hits


def _banned_hits_for_import_from(node: ast.ImportFrom) -> set[str]:
    """Collect banned targets from one ``from X import Y`` statement."""
    if node.module is None:
        return set()
    hits: set[str] = set()
    module = node.module
    if module in _BANNED_LIVE_IMPORTS:
        hits.add(module)
    root = module.split(".", 1)[0]
    if root in _BANNED_LIVE_IMPORTS:
        hits.add(root)
    return hits


def _hold_serial_items_from_xdist(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Deselect ``serial`` items when xdist workers are active, and say so.

    ``config.workerinput`` is present only inside an xdist worker, and is the
    signal that holds up: a worker reports ``numprocesses`` as ``None`` (the
    controller's value does not travel), so the worker-input probe -- not the
    worker count -- is what distinguishes a distributed run from ``-n0``.

    Args:
        config: The active :class:`pytest.Config` from the collection hook.
        items: The mutable collection items list; filtered in-place.
    """
    if not hasattr(config, "workerinput"):
        return
    held = [item for item in items if item.get_closest_marker(_SERIAL_MARKER) is not None]
    if not held:
        return
    items[:] = [item for item in items if item.get_closest_marker(_SERIAL_MARKER) is None]
    config.hook.pytest_deselected(items=held)

    node_ids = sorted(item.nodeid for item in held)
    # ``workeroutput`` is the sanctioned worker-to-controller channel; xdist
    # ships it on node-down, where ``pytest_testnodedown`` can read it. Written
    # here so the controller-side node-down hook can turn the hold into a
    # non-zero exit rather than leaving a green run that dropped tests.
    config.workeroutput[SERIAL_HELD_WORKEROUTPUT_KEY] = node_ids
    named = ", ".join(node_ids[:_MAX_NAMED_HELD_ITEMS])
    elided = len(node_ids) - _MAX_NAMED_HELD_ITEMS
    if elided > 0:
        named = f"{named}, and {elided} more"
    warnings.warn(
        f"Held {len(node_ids)} serial-marked test(s) out of this run because xdist workers are active; "
        f"they did NOT execute: {named}. "
        "Serial tests mutate or read process-global state and must run with no workers. "
        "Run them with `just test-integration-serial`, or add -n0 to this invocation.",
        SerialTestsHeldWarning,
        stacklevel=1,
    )


_held_from_workers: list[str] = []
"""Serial node ids held out of an xdist run, accumulated across workers.

Module-level because the controller sees each worker exactly once, on node
down, and must survive until the session finishes to decide the exit status.
"""


def reset_held_serials() -> None:
    """Clear controller-side held-serial state for a new pytest session."""
    _held_from_workers.clear()


def record_held_from_node(node: object) -> None:
    """Absorb one worker's held-serial ids as its node goes down.

    ``workeroutput`` is the sanctioned worker-to-controller channel. The hop
    is REQUIRED rather than convenient: xdist deselects inside the workers,
    so the controller's own ``deselected`` stat never receives these items
    and cannot be used as the signal.

    Args:
        node: The xdist worker node that just went down.
    """
    payload = getattr(node, "workeroutput", {}) or {}
    for node_id in payload.get(SERIAL_HELD_WORKEROUTPUT_KEY, ()):
        if node_id not in _held_from_workers:
            _held_from_workers.append(node_id)


_marker_violations_from_workers: list[str] = []
"""Marker-contract violations reported by workers, accumulated across them.

Module-level for the same reason as the held-serial list: the controller sees
each worker once, on node down, and must still know at session finish.
"""


def reset_marker_violations() -> None:
    """Clear controller-side marker-violation state for a new pytest session."""
    _marker_violations_from_workers.clear()


def record_marker_violations_from_node(node: object) -> None:
    """Absorb one worker's marker-contract violations as its node goes down.

    Args:
        node: The xdist worker node that just went down.
    """
    payload = getattr(node, "workeroutput", {}) or {}
    for violation in payload.get(MARKER_VIOLATIONS_WORKEROUTPUT_KEY, ()):
        if violation not in _marker_violations_from_workers:
            _marker_violations_from_workers.append(violation)


def marker_violations() -> tuple[str, ...]:
    """Return the marker-contract violations this run found, in first-seen order."""
    return tuple(_marker_violations_from_workers)


def fail_session_on_marker_violations(session: pytest.Session) -> None:
    """Refuse a run whose workers collected a mis-marked test.

    ``USAGE_ERROR`` matches the raise this stands in for at ``-n0``: the
    invocation's test taxonomy is what was wrong, and the status stays
    distinguishable from tests-failed.

    Args:
        session: The finishing session, whose exit status may be replaced.
    """
    if _marker_violations_from_workers:
        refuse_session(session)


def report_marker_violations(terminalreporter: _TerminalWriter) -> None:
    """Name every mis-marked test a worker refused, and the contract it broke.

    Args:
        terminalreporter: The active terminal reporter.
    """
    if not _marker_violations_from_workers:
        return
    terminalreporter.write_sep("=", "MARKER CONTRACT VIOLATED", red=True, bold=True)
    terminalreporter.write_line(
        f"{len(_marker_violations_from_workers)} test(s) were NOT RUN: their markers do not satisfy the taxonomy.",
        red=True,
        bold=True,
    )
    for violation in _marker_violations_from_workers:
        terminalreporter.write_line(f"  {violation}")


def held_serial_node_ids() -> tuple[str, ...]:
    """Return the serial node ids held out of this run, in first-seen order."""
    return tuple(_held_from_workers)


def fail_session_on_held_serials(session: pytest.Session) -> None:
    """Refuse a run that silently held isolation-sensitive tests back.

    Keyed on the held list being NON-EMPTY, never on workers merely being
    active, so a parallel run that selected no serial test is untouched.

    ``USAGE_ERROR`` is deliberate: the invocation, not the code, is what was
    wrong, and it stays distinguishable from tests-failed and from an xdist
    abort. Without this the run completes GREEN with those tests unrun, and
    a warning in a fourteen-thousand-test footer scrolls past -- the same
    false-green shape as a marker expression silently deselecting a whole
    lane.

    The replacement goes through the shared allow-list, so an interruption, an
    internal error or a custom ``pytest.exit`` status is preserved.

    Args:
        session: The finishing session, whose exit status may be replaced.
    """
    if _held_from_workers:
        refuse_session(session)


class _TerminalWriter(Protocol):
    """The two writer methods this reporter needs from pytest's terminal.

    Declared structurally rather than importing ``TerminalReporter`` from
    ``_pytest.terminal``: that is a private module whose shape is not a
    published contract, and the parameter was previously typed ``object``
    with a blanket attribute-access ignore, which suppressed any real
    error alongside the two it was aimed at.
    """

    def write_sep(self, sep: str, title: str, **markup: bool) -> None: ...

    def write_line(self, line: str, **markup: bool) -> None: ...


def report_held_serials(terminalreporter: _TerminalWriter) -> None:
    """Name the held tests and the invocation that would run them.

    Args:
        terminalreporter: The active terminal reporter.
    """
    if not _held_from_workers:
        return
    write_sep = terminalreporter.write_sep
    write_line = terminalreporter.write_line
    write_sep("=", "SERIAL TESTS HELD BACK", red=True, bold=True)
    write_line(
        f"{len(_held_from_workers)} isolation-sensitive tests were NOT RUN: they cannot be "
        "scheduled alongside a parallel lane.",
        red=True,
        bold=True,
    )
    for node_id in _held_from_workers:
        write_line(f"  {node_id}")
    write_line("Run them with `just test-integration-serial`, or add -n0 to this invocation.")
