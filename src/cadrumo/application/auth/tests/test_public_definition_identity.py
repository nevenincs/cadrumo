"""Runtime ownership proofs for the public authentication modules."""

from __future__ import annotations

import ast
from pathlib import Path
from types import ModuleType

import pytest

from .. import (
    acquisition_lock,
    actions,
    apoderado_flow,
    apoderado_service,
    catalogue,
    certificate_secret_backend,
    certificate_source_operations,
    certificate_sources,
    credentials,
    diagnostics,
    errors,
    models,
    operation_definitions,
    operator,
    operator_cleanup,
    operator_probes,
    operator_results,
    operator_scope,
    probes,
    protocols,
    providers,
    sessions,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PUBLIC_DEFINING_MODULES: tuple[ModuleType, ...] = (
    acquisition_lock,
    actions,
    apoderado_flow,
    apoderado_service,
    catalogue,
    certificate_secret_backend,
    certificate_source_operations,
    certificate_sources,
    credentials,
    diagnostics,
    errors,
    models,
    operation_definitions,
    operator,
    operator_cleanup,
    operator_probes,
    operator_results,
    operator_scope,
    probes,
    protocols,
    providers,
    sessions,
)


def _imported_names(module: ModuleType) -> frozenset[str]:
    """Return names imported into a module namespace by its source file."""
    source_path = Path(module.__file__ or "")
    tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.asname or alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            names.update(alias.asname or alias.name for alias in node.names)
    return frozenset(names)


@pytest.mark.parametrize("module", _PUBLIC_DEFINING_MODULES, ids=lambda module: module.__name__)
def test_every_public_auth_export_has_runtime_identity_at_its_defining_module(module: ModuleType) -> None:
    """Every listed contract is defined here, never imported from a foreign module."""
    exported = tuple(module.__all__)
    assert exported
    assert len(exported) == len(set(exported))

    missing = [name for name in exported if name not in vars(module)]
    assert missing == []

    foreign_runtime_exports = {
        name: getattr(getattr(module, name), "__module__", None)
        for name in exported
        if getattr(getattr(module, name), "__module__", None) not in (None, module.__name__)
    }
    assert foreign_runtime_exports == {}

    foreign_static_exports = sorted(set(exported) & _imported_names(module))
    assert foreign_static_exports == []
