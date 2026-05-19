"""AST-guard: master-key providers must not regrow ClassVar caches.

The cascade-closure ADR retired every ``ClassVar`` cache on
:class:`KeyringMasterKeyProvider` and
:class:`FileFallbackMasterKeyProvider` in favour of
:class:`BucketSession` instance state. This test parses the
``_master_key.py`` source and asserts no ``ClassVar`` annotation
remains on either provider class, so a future edit that re-introduces
process-global mutable state fails loudly at the gate rather than
re-creating the bucket-switch-survives-cache defect.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.domain_persistence]

_MASTER_KEY_SRC = Path(__file__).parent / "_master_key.py"


def _classvar_targets(node: ast.ClassDef) -> list[str]:
    """Return every ``ClassVar``-annotated attribute name on ``node``."""

    targets: list[str] = []
    for stmt in node.body:
        if not isinstance(stmt, ast.AnnAssign):
            continue
        annotation = stmt.annotation
        target_name = _bind_name(stmt.target)
        if target_name is None:
            continue
        if _annotation_uses_classvar(annotation):
            targets.append(target_name)
    return targets


def _bind_name(target: ast.expr) -> str | None:
    if isinstance(target, ast.Name):
        return target.id
    return None


def _annotation_uses_classvar(node: ast.expr) -> bool:
    if isinstance(node, ast.Name) and node.id == "ClassVar":
        return True
    if isinstance(node, ast.Subscript):
        value = node.value
        if isinstance(value, ast.Name) and value.id == "ClassVar":
            return True
    return False


def test_keyring_master_key_provider_holds_no_classvar_state() -> None:
    """The OS-keychain provider must own no module-global cache."""

    tree = ast.parse(_MASTER_KEY_SRC.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "KeyringMasterKeyProvider":
            targets = _classvar_targets(node)
            assert targets == [], (
                "KeyringMasterKeyProvider must hold zero ClassVar state — "
                f"found {targets}. ClassVar caches were retired in the "
                "cascade-closure cut; re-introducing them re-creates the "
                "bucket-switch-survives-cache defect this codebase fixed."
            )
            return
    pytest.fail("KeyringMasterKeyProvider class not found in _master_key.py")


def test_file_fallback_master_key_provider_holds_no_classvar_state() -> None:
    """The encrypted-file provider must own no module-global cache."""

    tree = ast.parse(_MASTER_KEY_SRC.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "FileFallbackMasterKeyProvider":
            targets = _classvar_targets(node)
            assert targets == [], (
                "FileFallbackMasterKeyProvider must hold zero ClassVar state — "
                f"found {targets}. ClassVar caches were retired in the "
                "cascade-closure cut; re-introducing them re-creates the "
                "bucket-switch-survives-cache defect this codebase fixed."
            )
            return
    pytest.fail("FileFallbackMasterKeyProvider class not found in _master_key.py")
