"""CI gate: production code reads the clock through the seam, not a bare wall-clock call.

Walks every production module under ``src/cadrumo`` (tests excluded) and fails if a
bare ``datetime.now(...)`` / ``datetime.utcnow(...)`` / ``datetime.today(...)`` or
``date.today(...)`` call appears — the wall-clock read that bypasses the
deterministic-output seam
(:func:`~core.time.now` / :func:`~core.time.frozen_clock`). A call site that
reads the clock directly is invisible to :func:`~core.time.frozen_clock`, so a
golden capture or replay cannot pin it; routing every read through
:func:`~core.time.now` (a date is ``now().date()``) keeps the seam the single
consulted clock. ``date.today()`` is the sharpest instance of this: it reads the
*local* wall-clock date the frozen-clock seam cannot pin, so a committed docs
golden that derives a deadline posture from it diverges daily — the defect this
gate's ``date`` coverage was added to catch.

Detection is by AST, grounded in each module's own imports so an aliased binding is
caught and an unrelated ``.now()`` / ``.today()`` on a non-datetime object is not:

* ``from datetime import datetime [as X]`` binds a *class* name; ``X.now(...)`` /
  ``X.utcnow(...)`` / ``X.today(...)`` is an offender.
* ``from datetime import date [as X]`` binds a *class* name; ``X.today(...)`` is an
  offender.
* ``import datetime [as Y]`` binds a *module* name; ``Y.datetime.now(...)`` and
  ``Y.date.today(...)`` are offenders.

The seam implementation itself (``core/time/clock.py``) is the one production site
that legitimately calls ``datetime.now(tz=UTC)`` — it is the fallback the seam
returns when unfrozen — and is skipped. The injectable live-AEAT sites, which accept
an explicit ``now=`` parameter and fall back to real wall-clock only when the seam is
deliberately barred (the seam refuses under ``CADRUMO_LIVE_TESTS_ENABLED``), are recorded
in :data:`_ALLOWLIST` with a stated per-entry reason.

``src/cadrumo_runtime`` is scanned separately: every clock read there is classified
``seam`` (follows :func:`~core.time.frozen_clock`) or ``wall`` (authority timing that
must not follow it) in :data:`_RUNTIME_CLASSIFICATION`, keyed by path and enclosing
function, and an unclassified read fails.

This is the clock-seam companion to ``test_external_constants.py``.

See Also:
    :mod:`~tests._inventory`
        Provides the production AST inventory and repository-relative path
        helpers used by this gate.
    :mod:`~core.time`
        Canonical clock and frozen-clock seam protected from direct wall-clock
        reads.
"""

from __future__ import annotations

import ast
from collections.abc import Mapping
from pathlib import Path

import pytest

from ...tests.inventory import SRC_CADRUMO, aeat_relative, production_ast_items, python_files_under

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

#: The one production module that owns a bare ``datetime.now`` for a structural
#: reason: it IS the seam, returning real wall-clock when unfrozen.
_SKIP_FILES: frozenset[str] = frozenset({"core/time/clock.py"})

#: Injectable live-AEAT sites permitted to fall back to a bare ``datetime.now``.
#: Keyed by ``src/cadrumo``-relative POSIX path → reason. Each accepts an explicit
#: ``now=`` parameter (so tests inject a fixed instant) and reads wall-clock only as
#: the default; the deterministic seam is deliberately barred on the live path (it
#: refuses under ``CADRUMO_LIVE_TESTS_ENABLED``), so the fallback is load-bearing, not a
#: mute button. The two regulated ``date.today()`` defaults formerly parked here (the
#: IVA-rate effective-date and the Beckham six-year-window reference) were resolved by
#: the 2026-07-14 Madrid-civil-date ruling: both now default to
#: :func:`cadrumo.core.time.today_madrid`, so the gate ratchets shut on them.
_ALLOWLIST: dict[str, str] = {
    "adapters/outbound/aeat/auth/certificate.py": (
        "Injectable live-AEAT site: certificate validity/expiry evaluators accept an "
        "explicit `now=` and read wall-clock only as the default on the live "
        "certificate path barred from the frozen-clock seam."
    ),
    "adapters/outbound/aeat/browser/site_health_parsers.py": (
        "Injectable live-AEAT site: the browser site-health parser accepts an explicit "
        "`now=` reference and reads wall-clock only as the default while parsing a live "
        "AEAT sede response barred from the frozen-clock seam."
    ),
}

#: Attribute names that read the wall clock off a ``datetime`` class binding.
_DATETIME_CLOCK_ATTRS: frozenset[str] = frozenset({"now", "utcnow", "today"})
#: Attribute names that read the wall clock off a ``date`` class binding.
_DATE_CLOCK_ATTRS: frozenset[str] = frozenset({"today"})


def _clock_bindings(tree: ast.Module) -> tuple[set[str], set[str], set[str]]:
    """Return ``(datetime_classes, date_classes, module_names)`` bound in this module.

    ``datetime_classes`` are names bound by ``from datetime import datetime [as X]``;
    ``date_classes`` are names bound by ``from datetime import date [as X]``;
    ``module_names`` are names bound by ``import datetime [as Y]``. Imports are
    collected wherever they appear (module level or function-local), matching the
    module's real binding surface.
    """
    datetime_classes: set[str] = set()
    date_classes: set[str] = set()
    module_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "datetime":
            for alias in node.names:
                if alias.name == "datetime":
                    datetime_classes.add(alias.asname or alias.name)
                elif alias.name == "date":
                    date_classes.add(alias.asname or alias.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "datetime":
                    module_names.add(alias.asname or alias.name)
    return datetime_classes, date_classes, module_names


def _is_bare_clock_read(
    node: ast.Call,
    datetime_classes: set[str],
    date_classes: set[str],
    module_names: set[str],
) -> bool:
    """Return whether ``node`` reads the wall clock off a ``datetime``/``date`` binding.

    Offenders: ``<datetime>.now/utcnow/today(...)``, ``<date>.today(...)``, and the
    module-qualified ``<mod>.datetime.now/utcnow/today(...)`` / ``<mod>.date.today(...)``.
    """
    func = node.func
    if not isinstance(func, ast.Attribute):
        return False
    attr = func.attr
    target = func.value
    # `X.<attr>(...)` where X is a class binding.
    if isinstance(target, ast.Name):
        if target.id in datetime_classes and attr in _DATETIME_CLOCK_ATTRS:
            return True
        return target.id in date_classes and attr in _DATE_CLOCK_ATTRS
    # `Y.datetime.<attr>(...)` / `Y.date.today(...)` where Y is the datetime module binding.
    if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name) and target.value.id in module_names:
        if target.attr == "datetime" and attr in _DATETIME_CLOCK_ATTRS:
            return True
        return target.attr == "date" and attr in _DATE_CLOCK_ATTRS
    return False


def test_no_bare_wall_clock_reads_in_production(source_tree_ast: Mapping[Path, ast.AST]) -> None:
    """No production module reads a bare ``datetime.now``/``utcnow`` outside the seam.

    Self-verifying: the offender worklist is recomputed from each module's AST on
    every run and the datetime bindings are resolved per module, so the gate ratchets
    — it cannot pass with a stale baseline, and a stale allowlist entry fails loudly.
    """
    offenders: list[str] = []
    used_allowlist: set[str] = set()

    for path, tree in production_ast_items(source_tree_ast):
        assert isinstance(tree, ast.Module), f"Expected a module AST for {path}, got {type(tree).__name__}"
        rel = aeat_relative(path)
        if rel in _SKIP_FILES:
            continue
        datetime_classes, date_classes, module_names = _clock_bindings(tree)
        if not (datetime_classes or date_classes or module_names):
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not _is_bare_clock_read(
                node, datetime_classes, date_classes, module_names
            ):
                continue
            if rel in _ALLOWLIST:
                used_allowlist.add(rel)
                continue
            offenders.append(
                f"src/cadrumo/{rel}:{node.lineno}: bare datetime/date clock read; "
                "use cadrumo.core.time.now() (a date is now().date()) so the frozen-clock seam can pin it",
            )

    assert not offenders, (
        "Bare wall-clock reads found in production code; route them through "
        "cadrumo.core.time.now() (the deterministic-output seam) instead:\n" + "\n".join(offenders)
    )
    stale = set(_ALLOWLIST) - used_allowlist
    assert not stale, "Stale _ALLOWLIST entries no longer read a bare clock; remove them:\n" + "\n".join(
        f"  {rel}" for rel in sorted(stale)
    )


def test_every_skip_file_still_needs_its_skip() -> None:
    """A skipped module must still exist and still read a bare clock.

    ``_ALLOWLIST`` is reconciled above by the scan itself, but ``_SKIP_FILES``
    short-circuits before any detection runs, so nothing else observes it. That
    asymmetry is the hazard: presence is not liveness. A skip whose module was
    deleted, renamed, or since routed through the seam keeps exempting the path,
    silently pre-authorising whatever later takes it.

    This is the redundancy check rather than an existence check -- drop the
    skip, re-run the real detector over the module, and require it to still
    fire. An entry that would pass without its skip is dead weight.
    """
    stale: list[str] = []
    for rel in sorted(_SKIP_FILES):
        path = SRC_CADRUMO / rel
        if not path.is_file():
            stale.append(f"{rel} (file absent)")
            continue
        tree = ast.parse(path.read_bytes().decode("utf-8"))
        datetime_classes, date_classes, module_names = _clock_bindings(tree)
        still_offends = any(
            _is_bare_clock_read(node, datetime_classes, date_classes, module_names)
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
        )
        if not still_offends:
            stale.append(f"{rel} (no bare clock read remains; drop the skip)")
    assert not stale, "Stale _SKIP_FILES entries; remove them:\n" + "\n".join(f"  {entry}" for entry in stale)


SRC_RUNTIME: Path = SRC_CADRUMO.parent / "cadrumo_runtime"
"""Root of the ``src/cadrumo_runtime`` package tree."""

_SEAM = "seam"
_WALL = "wall"

_CLOCK_MODULES: frozenset[str] = frozenset({"cadrumo.core.time", "cadrumo.core.time.clock"})
#: Clock-module names a runtime module may bind, mapped to the kind of read they are.
_CLOCK_NAME_KIND: dict[str, str] = {"now": _SEAM, "today_madrid": _SEAM, "wall_now": _WALL}
_TIME_CLOCK_ATTRS: frozenset[str] = frozenset({"time", "time_ns"})

_HOST_INERT = "Runtime host or frontend process: it never enters frozen_clock, so the seam read equals real time here."

#: Every clock read in ``src/cadrumo_runtime``, keyed ``<path under src/cadrumo_runtime>::<scope>``
#: where scope is the dotted enclosing class/function chain. Value is ``(classification, reason)``.
#: ``wall`` reads (``wall_now``, a bare ``datetime.now``, ``time.time``) are authority or
#: diagnostic timing that a fixed clock must never reach; ``seam`` reads go through ``now()``.
_RUNTIME_CLASSIFICATION: dict[str, tuple[str, str]] = {
    "adapters/worker_authorization_lease.py::_validated_authority_permit": (
        _WALL,
        "Lease expiry: authority expires on real time, never on a frozen past instant.",
    ),
    "adapters/worker_authorization.py::WorkerAuthorizationServer.__init__": (
        _WALL,
        "Default wall_clock of the authorization server checks lease expiry on real time.",
    ),
    "adapters/profile_worker.py::ProfileWorkerProcess.__init__": (
        _WALL,
        "Default wall_clock handed to the authorization server; lease expiry stays on real time.",
    ),
    "host/session_hold_operations.py::OperationRelay._respond": (
        _WALL,
        "responded_at stamps an interaction response the runtime correlates with lease and session state.",
    ),
    "host/worker_stall_watchdog.py::_header_line": (
        _WALL,
        "Diagnostic stamp beside a stall timer; a fixed instant would make dumps unorderable.",
    ),
    "adapters/worker_authorization_client.py::WorkerAuthorizationClient._check": (
        _WALL,
        "Lease reply expiry check in the worker process; authority expires on real time.",
    ),
}
_RUNTIME_CLASSIFICATION.update(
    dict.fromkeys(
        (
            "application/enrollment_recipient.py::VolatileEnrollmentRecipient.__init__",
            "application/enrollment_recipient.py::VolatileEnrollmentRecipient._offer_remaining",
            "application/enrollment_recipient.py::VolatileEnrollmentRecipient._binding",
            "application/enrollment_recipient.py::VolatileEnrollmentRecipient._exchange",
            "application/enrollment_recipient.py::VolatileEnrollmentRecipient._wait_for_exchange",
            "application/enrollment_recipient.py::VolatileEnrollmentRecipient._require_completion_deadline",
            "commands/runtime_access_management.py::profile_sessions",
            "host/enrollment_connections.py::RuntimeEnrollmentConnections._prepare_offer",
            "host/enrollment_offer.py::RuntimeEnrollmentOffer.lapses_at",
            "host/enrollment_offer.py::RuntimeEnrollmentOffer._require_offer_window",
            "host/frontend/tui/aeat_sync/runtime_handoff.py::_select_handoff_action",
            "host/frontend/tui/bound_session.py::_status_confirms_session",
            "host/frontend/tui/bound_session.py::BoundSession._arm_expiry",
            "host/frontend/tui/bound_session.py::BoundSession._expiry_due",
            "host/frontend/tui/bound_session.py::BoundSession.lifetime_ended",
            "host/frontend/tui/runtime_access_management.py::RuntimeAccessManagementScreen._retain_self_lock_after_human_refusal",
            "host/frontend/tui/runtime_account_session.py::read_runtime_account_session",
            "host/frontend/tui/runtime_session.py::RuntimeRestrictedSessionApp._status_is_current",
            "host/frontend/tui/runtime_session.py::RuntimeRestrictedSessionApp._arm_lapse",
            "host/frontend/tui/secret/automation_requester.py::RuntimeAutomationRequesterScreen.on_mount",
            "host/frontend/tui/secret/runtime_login_attempt.py::RuntimeLoginAttemptMixin._accepted_handoff",
            "host/operation_host.py::ProfileWorkerOperationHost.operation_secret",
            "host/profile_connection_sessions.py::_log_person_activity",
            "host/profile_connection_sessions.py::_log_human_issuance",
            "host/profile_connection_sessions.py::ProfileConnectionSessionMixin._human_sign_out",
            "host/profile_connections.py::RuntimeProfileConnections.__init__",
            "host/profile_host.py::RuntimeProfileHost.__init__",
            "host/profile_login.py::ProfileWorkerHumanLogin.authenticate",
            "host/profile_login.py::ProfileWorkerHumanLogin.resume",
            "host/profile_login.py::ProfileWorkerHumanLogin.seconds_until_expiry",
            "host/profile_login.py::_abandoned",
            "host/profile_receipt.py::resume_profile_candidate",
            "host/session_owner.py::ProfileWorkerSessionOwner.__init__",
            "host/session_watch.py::_seconds_until_deadline",
            "host/terminated_operations.py::settle_terminated_worker_operations",
            "host/terminated_operations.py::settle_drained_worker_operations",
            "host/worker_extension_records.py::write_extension_record",
        ),
        (_SEAM, _HOST_INERT),
    ),
)


def _is_time_module_clock_read(node: ast.Call, time_modules: set[str], time_functions: set[str]) -> bool:
    """Return whether ``node`` is ``time.time()``/``time.time_ns()`` or their ``from time import`` form."""
    func = node.func
    if isinstance(func, ast.Name):
        return func.id in time_functions
    return (
        isinstance(func, ast.Attribute)
        and isinstance(func.value, ast.Name)
        and func.value.id in time_modules
        and func.attr in _TIME_CLOCK_ATTRS
    )


def _runtime_clock_reads(tree: ast.Module) -> list[tuple[str, int, str]]:
    """Return ``(scope, line, kind)`` for each clock read in a runtime module.

    A read is a use of a clock-module name (``now``, ``today_madrid``, ``wall_now``,
    aliased or not), a bare ``datetime``/``date`` clock call as
    :func:`_is_bare_clock_read` defines it, or ``time.time``/``time.time_ns``.
    The kind is ``seam`` for ``now``/``today_madrid`` and ``wall`` for the rest.
    """
    datetime_classes, date_classes, module_names = _clock_bindings(tree)
    clock_names: dict[str, str] = {}
    time_modules: set[str] = set()
    time_functions: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module in _CLOCK_MODULES:
            for alias in node.names:
                if alias.name in _CLOCK_NAME_KIND:
                    clock_names[alias.asname or alias.name] = _CLOCK_NAME_KIND[alias.name]
        elif isinstance(node, ast.ImportFrom) and node.module == "time":
            time_functions.update(a.asname or a.name for a in node.names if a.name in _TIME_CLOCK_ATTRS)
        elif isinstance(node, ast.Import):
            time_modules.update(a.asname or a.name for a in node.names if a.name == "time")
    reads: list[tuple[str, int, str]] = []

    def visit(node: ast.AST, scope: tuple[str, ...]) -> None:
        where = ".".join(scope) or "<module>"
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Load) and child.id in clock_names:
                reads.append((where, child.lineno, clock_names[child.id]))
            elif isinstance(child, ast.Call) and (
                _is_bare_clock_read(child, datetime_classes, date_classes, module_names)
                or _is_time_module_clock_read(child, time_modules, time_functions)
            ):
                reads.append((where, child.lineno, _WALL))
            if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
                visit(child, (*scope, child.name))
            else:
                visit(child, scope)

    visit(tree, ())
    return reads


def _runtime_clock_problems(
    sources: Mapping[str, str],
    classification: Mapping[str, tuple[str, str]],
) -> list[str]:
    """Return every unclassified, misclassified, mixed or stale entry for the given sources.

    ``sources`` maps a path under ``src/cadrumo_runtime`` to its text.
    """
    problems: list[str] = []
    seen: dict[str, set[str]] = {}
    for rel, text in sorted(sources.items()):
        for scope, line, kind in _runtime_clock_reads(ast.parse(text)):
            key = f"{rel}::{scope}"
            seen.setdefault(key, set()).add(kind)
            declared = classification.get(key)
            if declared is None:
                problems.append(f"{key} (line {line}): unclassified {kind} clock read; classify it as seam or wall")
            elif declared[0] != kind:
                problems.append(f"{key} (line {line}): read is {kind} but classified {declared[0]}")
    problems.extend(f"{key}: stale entry, no clock read remains" for key in sorted(set(classification) - set(seen)))
    problems.extend(
        f"{key}: mixes {sorted(kinds)} reads; split the function"
        for key, kinds in sorted(seen.items())
        if len(kinds) > 1
    )
    return problems


def _runtime_sources() -> dict[str, str]:
    """Return the production text of ``src/cadrumo_runtime`` keyed by POSIX relative path."""
    sources: dict[str, str] = {}
    for path in python_files_under(SRC_RUNTIME):
        rel = path.relative_to(SRC_RUNTIME)
        if "tests" in rel.parts or rel.name.startswith(("test_", "_test_")):
            continue
        sources[rel.as_posix()] = path.read_bytes().decode("utf-8")
    return sources


def test_runtime_clock_reads_are_all_classified() -> None:
    """Each ``src/cadrumo_runtime`` clock read is classified seam or wall, with no stale entry."""
    sources = _runtime_sources()
    assert sources, "no runtime modules found; the scan root is wrong"
    problems = _runtime_clock_problems(sources, _RUNTIME_CLASSIFICATION)
    assert not problems, "Runtime clock reads need an explicit seam/wall classification:\n" + "\n".join(problems)


def test_runtime_clock_gate_refuses_defects_in_a_synthetic_source() -> None:
    """Positive control: the gate refuses unclassified, misclassified and stale entries."""
    source = (
        "from datetime import UTC, datetime\n"
        "from cadrumo.core.time.clock import now as fixed_now, wall_now\n"
        "def lease_check():\n"
        "    return fixed_now()\n"
        "class Hold:\n"
        "    def stamp(self):\n"
        "        return datetime.now(UTC)\n"
        "def audit():\n"
        "    return wall_now()\n"
    )
    sources = {"host/fixture.py": source}
    assert len(_runtime_clock_problems(sources, {})) == 3
    partial = {"host/fixture.py::lease_check": (_SEAM, "x"), "host/fixture.py::audit": (_WALL, "x")}
    assert _runtime_clock_problems(sources, partial) == [
        "host/fixture.py::Hold.stamp (line 7): unclassified wall clock read; classify it as seam or wall",
    ]
    full = {**partial, "host/fixture.py::Hold.stamp": (_WALL, "x")}
    assert _runtime_clock_problems(sources, full) == []
    wrong = {**full, "host/fixture.py::lease_check": (_WALL, "x")}
    assert any("read is seam but classified wall" in item for item in _runtime_clock_problems(sources, wrong))
    stale = {**full, "host/fixture.py::gone": (_WALL, "x")}
    assert any("stale entry" in item for item in _runtime_clock_problems(sources, stale))
    time_read = {"host/t.py": "import time\ndef f():\n    return time.time()\n"}
    assert any("unclassified wall" in item for item in _runtime_clock_problems(time_read, {}))
