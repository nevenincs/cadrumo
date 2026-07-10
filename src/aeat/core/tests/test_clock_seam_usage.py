"""CI gate: production code reads the clock through the seam, not a bare ``datetime.now``.

Walks every production module under ``src/aeat`` (tests excluded) and fails if a
bare ``datetime.now(...)`` / ``datetime.utcnow(...)`` call appears — the wall-clock
read that bypasses the deterministic-output seam
(:func:`~core.time.now` / :func:`~core.time.frozen_clock`). A call site that
reads the clock directly is invisible to :func:`~core.time.frozen_clock`, so a
golden capture or replay cannot pin it; routing every read through
:func:`~core.time.now` keeps the seam the single consulted clock.

Detection is by AST, grounded in each module's own imports so an aliased binding is
caught and an unrelated ``.now()`` on a non-datetime object is not:

* ``from datetime import datetime [as X]`` binds a *class* name; ``X.now(...)`` /
  ``X.utcnow(...)`` is an offender.
* ``import datetime [as Y]`` binds a *module* name; ``Y.datetime.now(...)`` is an
  offender.

The seam implementation itself (``core/time/_clock.py``) is the one production site
that legitimately calls ``datetime.now(tz=UTC)`` — it is the fallback the seam
returns when unfrozen — and is skipped. The injectable live-AEAT sites, which accept
an explicit ``now=`` parameter and fall back to real wall-clock only when the seam is
deliberately barred (the seam refuses under ``AEAT_LIVE_TESTS_ENABLED``), are recorded
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

from ...tests import aeat_relative, production_ast_items

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

#: The one production module that owns a bare ``datetime.now`` for a structural
#: reason: it IS the seam, returning real wall-clock when unfrozen.
_SKIP_FILES: frozenset[str] = frozenset({"core/time/_clock.py"})

#: Injectable live-AEAT sites permitted to fall back to a bare ``datetime.now``.
#: Keyed by ``src/aeat``-relative POSIX path → reason. Each accepts an explicit
#: ``now=`` parameter (so tests inject a fixed instant) and reads wall-clock only as
#: the default; the deterministic seam is deliberately barred on the live path (it
#: refuses under ``AEAT_LIVE_TESTS_ENABLED``), so the fallback is load-bearing, not a
#: mute button.
_ALLOWLIST: dict[str, str] = {
    "application/auth/_acquisition_lock.py": (
        "Injectable live-AEAT site: the auth acquisition-lock staleness check accepts "
        "an explicit `now=` and falls back to wall-clock only on the live path, where "
        "the frozen-clock seam is barred under AEAT_LIVE_TESTS_ENABLED."
    ),
    "adapters/outbound/aeat/auth/certificate.py": (
        "Injectable live-AEAT site: certificate validity/expiry evaluators accept an "
        "explicit `now=` and read wall-clock only as the default on the live "
        "certificate path barred from the frozen-clock seam."
    ),
    "adapters/outbound/aeat/auth/_authenticator_types.py": (
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

#: Attribute names that read the wall clock off a datetime binding.
_CLOCK_ATTRS: frozenset[str] = frozenset({"now", "utcnow"})


def _datetime_bindings(tree: ast.Module) -> tuple[set[str], set[str]]:
    """Return ``(class_names, module_names)`` bound to ``datetime`` in this module.

    ``class_names`` are names bound by ``from datetime import datetime [as X]``;
    ``module_names`` are names bound by ``import datetime [as Y]``. Imports are
    collected wherever they appear (module level or function-local), matching the
    module's real binding surface.
    """
    class_names: set[str] = set()
    module_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "datetime":
            for alias in node.names:
                if alias.name == "datetime":
                    class_names.add(alias.asname or alias.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "datetime":
                    module_names.add(alias.asname or alias.name)
    return class_names, module_names


def _is_bare_clock_read(node: ast.Call, class_names: set[str], module_names: set[str]) -> bool:
    """Return whether ``node`` is ``<datetime>.now(...)`` / ``<datetime>.utcnow(...)``."""
    func = node.func
    if not isinstance(func, ast.Attribute) or func.attr not in _CLOCK_ATTRS:
        return False
    target = func.value
    # `X.now(...)` where X is the datetime class binding.
    if isinstance(target, ast.Name) and target.id in class_names:
        return True
    # `Y.datetime.now(...)` where Y is the datetime module binding.
    return (
        isinstance(target, ast.Attribute)
        and target.attr == "datetime"
        and isinstance(target.value, ast.Name)
        and target.value.id in module_names
    )


def test_no_bare_wall_clock_reads_in_production(source_tree_ast: Mapping[Path, ast.AST]) -> None:
    """No production module reads a bare ``datetime.now``/``utcnow`` outside the seam.

    Self-verifying: the offender worklist is recomputed from each module's AST on
    every run and the datetime bindings are resolved per module, so the gate ratchets
    — it cannot pass with a stale baseline, and a stale allowlist entry fails loudly.
    """
    offenders: list[str] = []
    used_allowlist: set[str] = set()

    for path, tree in production_ast_items(source_tree_ast):
        rel = aeat_relative(path)
        if rel in _SKIP_FILES:
            continue
        class_names, module_names = _datetime_bindings(tree)
        if not class_names and not module_names:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not _is_bare_clock_read(node, class_names, module_names):
                continue
            if rel in _ALLOWLIST:
                used_allowlist.add(rel)
                continue
            offenders.append(
                f"src/aeat/{rel}:{node.lineno}: bare datetime clock read; "
                "use aeat.core.time.now() so the frozen-clock seam can pin it",
            )

    assert not offenders, (
        "Bare wall-clock reads found in production code; route them through "
        "aeat.core.time.now() (the deterministic-output seam) instead:\n" + "\n".join(offenders)
    )
    stale = set(_ALLOWLIST) - used_allowlist
    assert not stale, "Stale _ALLOWLIST entries no longer read a bare clock; remove them:\n" + "\n".join(
        f"  {rel}" for rel in sorted(stale)
    )
