"""Inventory ratchet: parameter-level ``Any`` annotations must carry an inline rationale marker.

Rule
----
Every production function whose parameter annotations include a bare ``Any``
(or a generic that contains bare ``Any`` at a parameter position) must have one
of the following marker tokens in the preceding 3 source lines:

- ``KWARGS-ANY-RATIONALE-``  — for circular-import or structural reasons
- ``ANY-RETURN-RATIONALE-``  — for return-type escapes (also covers param
  sites when the same rationale applies to the full signature)
- ``ADAPTER-INTERNAL-ALIAS-RATIONALE-``  — for third-party untyped resources

Structural prevention (W21.P53)
--------------------------------
This test AST-walks **all** production Python files under ``src/aeat/``
(excluding test files) so every new file added by any future campaign is
automatically covered.

The ratchet records the set of (relative-path, function-lineno) pairs that
currently carry an un-annotated ``Any`` parameter.  New sites must be
accompanied by a marker or use the concrete type instead.  Removing an entry
from ``_KNOWN_VIOLATING_LINES`` after adding the marker (or replacing ``Any``)
locks that site at zero forever.

Exclusions
----------
- Files whose name starts with ``test_`` or ends with ``_test.py``.
- Lambda nodes (no function-level marker convention applies; the body is
  usually on one line and the annotation is almost never ``Any``).
"""

from __future__ import annotations

import ast
import pathlib

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.domain_core]

_SRC_ROOT = pathlib.Path(__file__).parent

# Marker token prefixes — any of these in a preceding line satisfies the rule.
_MARKER_TOKENS: tuple[str, ...] = (
    "KWARGS-ANY-RATIONALE-",
    "ANY-RETURN-RATIONALE-",
    "ADAPTER-INTERNAL-ALIAS-RATIONALE-",
)

# How many lines before the function ``def`` line are inspected for markers.
_CONTEXT_LINES = 3

# ---------------------------------------------------------------------------
# Known pre-existing violating sites (W21.P53 backlog).
# Each entry is (relative-posix-path-from-src/aeat/, function-def-lineno).
# New sites must NOT be added here — add a marker comment or use the concrete
# type instead.  Removing an entry after fixing locks that site at zero.
# ---------------------------------------------------------------------------
_KNOWN_VIOLATING_LINES: frozenset[tuple[str, int]] = frozenset(
    {
        ("adapters/outbound/aeat/browser/_factory.py", 176),
        ("adapters/outbound/aeat/browser/_factory.py", 71),
        ("adapters/outbound/aeat/browser/session.py", 215),
        ("adapters/outbound/aeat/verify/__init__.py", 119),
        ("adapters/outbound/storage/_google_drive.py", 647),
        ("adapters/outbound/storage/_google_drive.py", 164),
        ("adapters/outbound/storage/_google_drive.py", 224),
        ("adapters/persistence/storage/envelope/_envelope.py", 171),
        ("adapters/persistence/storage/envelope/_envelope.py", 367),
        ("application/invoices/_importing.py", 135),
        ("application/live/_borrador_100.py", 308),
        ("application/live/_borrador_100.py", 317),
        ("application/live/_censo.py", 397),
        ("application/live/_expedientes.py", 160),
        ("application/live/_notifications.py", 175),
        ("application/live/_snapshot_base.py", 212),
        ("application/live/_snapshot_base.py", 237),
        ("application/live/_snapshot_base.py", 347),
        ("application/live/_snapshot_base.py", 351),
        ("application/transactions/_import.py", 39),
        ("core/i18n/_translatable.py", 20),
        ("core/logging.py", 124),
        ("core/logging.py", 128),
        ("core/logging.py", 132),
        ("core/logging.py", 136),
        ("core/logging.py", 160),
        ("core/logging.py", 229),
        ("domain/calculations/registry/_constructs.py", 35),
        ("domain/calculations/registry/_workbook_parity.py", 417),
        ("domain/modelos/_codes.py", 27),
    }
)


def _has_any_annotation(annotation: ast.expr | None) -> bool:
    """Return True if *annotation* is or contains a bare ``Any`` name."""
    if annotation is None:
        return False
    if isinstance(annotation, ast.Name) and annotation.id == "Any":
        return True
    if isinstance(annotation, ast.Subscript):
        return _has_any_annotation(annotation.value) or _has_any_annotation(
            annotation.slice
        )
    if isinstance(annotation, ast.Tuple):
        return any(_has_any_annotation(e) for e in annotation.elts)
    if isinstance(annotation, ast.BinOp):
        return _has_any_annotation(annotation.left) or _has_any_annotation(
            annotation.right
        )
    return False


def _params_have_any(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """Return True if any parameter of *node* carries an ``Any`` annotation."""
    all_args = list(node.args.args) + list(node.args.kwonlyargs)
    if node.args.vararg:
        all_args.append(node.args.vararg)
    if node.args.kwarg:
        all_args.append(node.args.kwarg)
    return any(_has_any_annotation(a.annotation) for a in all_args)


def _preceding_lines_have_marker(
    source_lines: list[str], func_lineno: int
) -> bool:
    """Return True if any of _CONTEXT_LINES before *func_lineno* contain a marker."""
    start = max(0, func_lineno - 1 - _CONTEXT_LINES)
    end = func_lineno - 1
    for line in source_lines[start:end]:
        if any(m in line for m in _MARKER_TOKENS):
            return True
    return False


def _collect_violations() -> list[tuple[str, int]]:
    """Walk all production files and return (rel_path, lineno) pairs without markers."""
    violations: list[tuple[str, int]] = []
    for path in sorted(_SRC_ROOT.rglob("*.py")):
        name = path.name
        if name.startswith("test_") or name.endswith("_test.py"):
            continue
        try:
            source = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        try:
            tree = ast.parse(source)
        except SyntaxError:
            continue
        source_lines = source.splitlines()
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if not _params_have_any(node):
                continue
            if _preceding_lines_have_marker(source_lines, node.lineno):
                continue
            rel = path.relative_to(_SRC_ROOT).as_posix()
            violations.append((rel, node.lineno))
    return violations


def test_no_new_any_param_without_rationale() -> None:
    """New parameter-level ``Any`` annotations must carry an inline rationale marker.

    This test uses a ratchet against ``_KNOWN_VIOLATING_LINES``:

    - Sites already in the ratchet are skipped (tracked for future cleanup).
    - Any site NOT in the ratchet must have a rationale marker in the 3 lines
      before the ``def`` keyword.
    - New files or new functions added by any campaign are automatically covered.

    To remediate a known-violating site: add a marker comment (preferred) or
    replace ``Any`` with the concrete type, then remove the entry from
    ``_KNOWN_VIOLATING_LINES``. The test will then lock that site at zero.

    Marker tokens (any one is sufficient):
      KWARGS-ANY-RATIONALE-<LABEL>
      ANY-RETURN-RATIONALE-<LABEL>
      ADAPTER-INTERNAL-ALIAS-RATIONALE-<LABEL>
    """
    all_violations = _collect_violations()
    new_violations = [
        (rel, lineno)
        for rel, lineno in all_violations
        if (rel, lineno) not in _KNOWN_VIOLATING_LINES
    ]

    if new_violations:
        lines = "\n  ".join(f"{rel}:{lineno}" for rel, lineno in new_violations)
        raise AssertionError(
            f"{len(new_violations)} parameter-Any site(s) found without a rationale marker:\n"
            f"  {lines}\n\n"
            "Add one of the following marker tokens in the 3 lines before the function def:\n"
            "  # KWARGS-ANY-RATIONALE-<LABEL>: <reason>\n"
            "  # ANY-RETURN-RATIONALE-<LABEL>: <reason>\n"
            "  # ADAPTER-INTERNAL-ALIAS-RATIONALE-<LABEL>: <reason>\n"
            "Or replace Any with the concrete type if it is now known.\n"
            f"Ratchet holds {len(_KNOWN_VIOLATING_LINES)} pre-existing sites; "
            "do NOT add new sites to the ratchet — add a marker instead."
        )
