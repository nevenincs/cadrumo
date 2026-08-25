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

The seam implementation itself (``core/time/_clock.py``) is the one production site
that legitimately calls ``datetime.now(tz=UTC)`` — it is the fallback the seam
returns when unfrozen — and is skipped. The injectable live-AEAT sites, which accept
an explicit ``now=`` parameter and fall back to real wall-clock only when the seam is
deliberately barred (the seam refuses under ``CADRUMO_LIVE_TESTS_ENABLED``), are recorded
in :data:`_ALLOWLIST` with a stated per-entry reason.

This is the clock-seam companion to the AST gates in ``test_modelo_string_usage.py``
and ``test_external_constants.py``.

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

from ...tests import SRC_CADRUMO, aeat_relative, production_ast_items

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

#: The one production module that owns a bare ``datetime.now`` for a structural
#: reason: it IS the seam, returning real wall-clock when unfrozen.
_SKIP_FILES: frozenset[str] = frozenset({"core/time/_clock.py"})

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
    "application/auth/_acquisition_lock.py": (
        "Injectable live-AEAT site: the auth acquisition-lock staleness check accepts "
        "an explicit `now=` and falls back to wall-clock only on the live path, where "
        "the frozen-clock seam is barred under CADRUMO_LIVE_TESTS_ENABLED."
    ),
    "adapters/outbound/aeat/auth/certificate.py": (
        "Injectable live-AEAT site: certificate validity/expiry evaluators accept an "
        "explicit `now=` and read wall-clock only as the default on the live "
        "certificate path barred from the frozen-clock seam."
    ),
    "adapters/outbound/aeat/auth/authenticator_types.py": (
        "Injectable live-AEAT site: the authenticator freshness check accepts an "
        "explicit `now=` and falls back to wall-clock only on the live auth path "
        "barred from the frozen-clock seam."
    ),
    "adapters/outbound/aeat/browser/_site_health_parsers.py": (
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
