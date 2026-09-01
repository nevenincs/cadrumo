"""Regression: no production calc/verify/filing/export/projection path injects
a stored, literal, or operator-supplied ``revision_id`` into
``authority.snapshot()`` resolution.

``select_revision``, reached exclusively through
``ValidatedRegistryAuthority.snapshot`` (or, for work-unit addressing,
``law_selected_revision_for_work_target``), is THE single
law-determined period-to-revision resolver.  The ``revision_id`` parameter on
``snapshot()`` / ``select_revision()`` is reclassified as an *assertion
parameter*: legitimate only for (i) registry-derived enumeration and
(ii) fixture / scenario replay pinning.  Only (i) has production members —
scenario replay is exercised by the test harness, which the scan skips along
with every other module under a ``tests/`` directory.

The three benign exemptions confirmed by the registry call-site sweep are pinned
here as named constants.  Any new call site passing a ``revision_id`` into
``authority.snapshot()`` outside these exemptions is a defect and this test
will FAIL.

This is a structural gate (AST walk), not a runtime gate, so it is fast and
catches the violation at CI time regardless of which code-path is exercised.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from ....core.directory_scan import scan_directory

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

# ---------------------------------------------------------------------------
# Named exemptions confirmed by the registry call-site review
# ---------------------------------------------------------------------------
# Paths relative to the ``aeat`` package root (``src/cadrumo/``).  The path
# separator is ``/`` regardless of host OS so the set comparison is portable.

_BENIGN_EXEMPTIONS: frozenset[str] = frozenset(
    {
        # 1. Registry-derived enumeration: iterates revisions FROM the registry
        #    filtered by year/period coverage; the narrowing is
        #    consistent-by-construction with the resolver.
        "application/calculations/cross_period_clean_state.py",
        # 2. Contextless schema-browse fallback: synthesises a representative
        #    (year, period) from the latest open revision's own selector and
        #    narrows to that same revision; consistent-by-construction, and NOT
        #    a calculation-on-a-filing path.
        "application/filing/runtime.py",
        # 3. Registry-derived enumeration: the referential-integrity preflight
        #    probe builds a snapshot for EVERY revision of EVERY bundled modelo,
        #    pinning each revision.id to itself while iterating
        #    authority.modelos / modelo.revisions.values() directly. The pin is
        #    consistent-by-construction (it names the very revision the loop is
        #    on), never a stored/operator-supplied value.
        "application/preflight.py",
    },
)


def _aeat_src_root() -> Path:
    """Return the absolute path to ``src/cadrumo/``."""
    here = Path(__file__).resolve()
    # climb: tests/ -> calculations/ -> application/ -> aeat/ -> src/
    for parent in here.parents:
        if parent.name == "cadrumo" and (parent.parent.name == "src" or (parent / "__init__.py").exists()):
            return parent
    raise RuntimeError(  # pragma: no cover
        "Cannot locate the src/cadrumo/ package root from this test's path",
    )


def _relative_path(path: Path, root: Path) -> str:
    """Return POSIX-style path of *path* relative to *root*."""
    return path.relative_to(root).as_posix()


def _is_test_path(rel: str) -> bool:
    return "/tests/" in rel or rel.endswith("_test.py")


def _find_snapshot_revision_id_injections(root: Path) -> list[tuple[str, int]]:
    """Return ``(rel_path, lineno)`` for every production ``authority.snapshot(revision_id=...)`` call.

    A call site is flagged when:
    - The callee is an attribute access ending in ``.snapshot``
    - One of the keyword arguments is ``revision_id``
    - The containing file is not under a ``tests/`` directory

    The exemption set is NOT applied here; the caller decides how to handle them.
    """
    sites: list[tuple[str, int]] = []
    for path in scan_directory(root, pattern="*.py", recursive=True):
        rel = _relative_path(path, root)
        if _is_test_path(rel):
            continue
        try:
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(path))
        except (SyntaxError, OSError):  # pragma: no cover
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if not (isinstance(func, ast.Attribute) and func.attr == "snapshot"):
                continue
            kw_names = {kw.arg for kw in node.keywords}
            if "revision_id" not in kw_names:
                continue
            sites.append((rel, node.lineno))
    return sites


def test_no_new_snapshot_revision_id_injection_outside_named_exemptions() -> None:
    """No production ``authority.snapshot(revision_id=...)`` call may exist outside the three named exemptions.

    If this test fails a new call site has been added that passes a
    stored/literal/operator-supplied ``revision_id`` into resolution.  That is
    a defect: the ``revision_id`` parameter is an assertion, not a selector.
    Either:

    - Remove the ``revision_id=`` kwarg and let the resolver decide, OR
    - If the call is genuinely one of the three benign shapes (registry-derived
      enumeration, contextless schema-browse, fixture replay), add it to
      ``_BENIGN_EXEMPTIONS`` in this test with a comment justifying the exemption.
    """
    root = _aeat_src_root()
    all_sites = _find_snapshot_revision_id_injections(root)

    # Partition into exempted and non-exempted
    exempted: list[tuple[str, int]] = []
    violations: list[tuple[str, int]] = []
    for rel, lineno in all_sites:
        if rel in _BENIGN_EXEMPTIONS:
            exempted.append((rel, lineno))
        else:
            violations.append((rel, lineno))

    # Every named exemption must still be present (guards against silent deletion
    # of an exemption entry without updating the set).
    exempted_files = {rel for rel, _ in exempted}
    missing_exemptions = _BENIGN_EXEMPTIONS - exempted_files
    assert not missing_exemptions, (
        "Named exemption(s) no longer appear in the production source tree. "
        "If the file was moved or the call site removed, update _BENIGN_EXEMPTIONS "
        "in this test to reflect the current state of the codebase:\n"
        + "\n".join(f"  missing: {e}" for e in sorted(missing_exemptions))
    )

    # No new violations are allowed.
    assert not violations, (
        "Production code injects a stored/literal/operator-supplied revision_id "
        "into authority.snapshot() outside the three named exemptions. "
        "The revision_id parameter on snapshot()/select_revision() is an assertion "
        "parameter, not a selector: production calculation, verification, filing, "
        "export, and projection paths MUST resolve from (modelo, filing_year, period) "
        "alone.\n"
        "Violating call site(s):\n"
        + "\n".join(f"  {rel}:{lineno}" for rel, lineno in sorted(violations))
        + "\n\nEither remove the revision_id= kwarg (let the resolver decide), "
        "or — if the call is genuinely benign (registry-derived enumeration, "
        "contextless schema-browse, fixture replay) — add it to _BENIGN_EXEMPTIONS "
        "in this test with a justifying comment."
    )
