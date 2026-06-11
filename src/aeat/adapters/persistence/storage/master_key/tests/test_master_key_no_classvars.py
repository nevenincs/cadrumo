"""AST guard test: master-key providers carry zero ClassVar mutable state.

The profile-bucket lifecycle substrate invariant forbids any
module-global or class-level mutable state that could
survive a bucket switch. Cache state moves to the per-bucket
:class:`BucketSession` instance.

Walks the AST of ``_master_key.py`` and asserts that
:class:`KeyringMasterKeyProvider` and :class:`FileFallbackMasterKeyProvider`
declare zero class-level annotations naming :class:`typing.ClassVar`.
This is the regression gate for the master-key substrate invariant.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from ......core.external_constants import UTF_8_ENCODING

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_GUARDED_PROVIDERS = frozenset(
    {
        "KeyringMasterKeyProvider",
        "FileFallbackMasterKeyProvider",
    },
)


def _is_classvar_annotation(node: ast.AST) -> bool:
    """Return whether ``node`` is a ClassVar[...] annotation."""
    if isinstance(node, ast.Subscript):
        return _is_classvar_annotation(node.value)
    if isinstance(node, ast.Attribute):
        return node.attr == "ClassVar"
    if isinstance(node, ast.Name):
        return node.id == "ClassVar"
    return False


def test_master_key_providers_carry_zero_classvar_state() -> None:
    """The guarded providers must declare no ClassVar-annotated attributes."""
    module_path = Path(__file__).parent.parent / "_master_key.py"
    tree = ast.parse(module_path.read_text(encoding=UTF_8_ENCODING), filename=str(module_path))

    violations: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        if node.name not in _GUARDED_PROVIDERS:
            continue
        for stmt in node.body:
            if isinstance(stmt, ast.AnnAssign) and _is_classvar_annotation(stmt.annotation):
                target = ast.unparse(stmt.target) if hasattr(ast, "unparse") else "<attr>"
                violations.append(f"{node.name}:{stmt.lineno}: ClassVar attribute {target}")

    assert violations == [], (
        "Master-key providers must not carry ClassVar mutable state; "
        "every cache moved to the per-bucket BucketSession. Violations:\n  " + "\n  ".join(violations)
    )
