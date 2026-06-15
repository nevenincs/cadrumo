"""Static guard for production exception base classes.

User/application-facing AEAT exceptions must derive from
:class:`aeat.core.errors.AeatError` so they bind to the central error
registry. A tiny allowlist remains for private implementation sentinels
and structural mixin bases that are not raised directly.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_BARE_EXCEPTION_BASES = frozenset({"Exception", "ValueError", "RuntimeError", "KeyError", "TypeError"})
_ALLOWLIST = {
    "aeat.core.errors.AeatError": "central root of the registry-bound exception hierarchy",
    "aeat.application.live._snapshot_base.SnapshotNotFoundError": (
        "structural KeyError mixin; concrete snapshot errors also inherit AeatError"
    ),
    "aeat.application.calculations._multi_year.EnrollmentEvidenceError": (
        "private ValueError raised by the multi-year enrollment recorder validator; "
        "internal contract sentinel — not surfaced to user/CLI/registry-error envelopes"
    ),
    "aeat.domain.calculations.registry._formula_runtime._UnresolvedFormulaDependencyError": (
        "private formula-runtime control-flow sentinel; caught inside calculate_registry_snapshot "
        "to omit non-blocking unresolved formula targets and never raised across the public boundary"
    ),
}


def test_production_exception_classes_do_not_introduce_unregistered_builtin_roots() -> None:
    violations: list[str] = []
    for path in sorted(Path("src/aeat").rglob("*.py")):
        if path.name.startswith(("test_", "_test_")):
            continue
        module_name = _module_name_for_path(path)
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            qualname = f"{module_name}.{node.name}"
            if qualname in _ALLOWLIST:
                continue
            bare_bases = sorted(
                base_name for base in node.bases if (base_name := _base_name(base)) in _BARE_EXCEPTION_BASES
            )
            # Multiple inheritance such as `DomainValidationError(AeatError, ValueError)`
            # preserves built-in compatibility while still routing through a
            # registry-bound AEAT base. The unsafe shape is a new root whose
            # bases are only Python built-ins.
            if bare_bases and len(bare_bases) == len(node.bases):
                violations.append(f"{path}:{node.lineno}: {node.name}({', '.join(bare_bases)})")

    assert violations == []


def test_exception_base_hygiene_allowlist_carries_review_rationales() -> None:
    assert all(reason.strip() for reason in _ALLOWLIST.values())


def _module_name_for_path(path: Path) -> str:
    relative = path.with_suffix("").relative_to(Path("src"))
    parts = list(relative.parts)
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _base_name(node: ast.expr) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return ""
