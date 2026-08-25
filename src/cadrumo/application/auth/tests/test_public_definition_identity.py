"""Runtime ownership proofs for the public authentication modules."""

from __future__ import annotations

import ast
from pathlib import Path
from types import ModuleType

import pytest

import cadrumo.application.auth.acquisition_lock as acquisition_lock
import cadrumo.application.auth.actions as actions
import cadrumo.application.auth.apoderado_flow as apoderado_flow
import cadrumo.application.auth.apoderado_service as apoderado_service
import cadrumo.application.auth.catalogue as catalogue
import cadrumo.application.auth.certificate_secret_backend as certificate_secret_backend
import cadrumo.application.auth.certificate_source_operations as certificate_source_operations
import cadrumo.application.auth.certificate_sources as certificate_sources
import cadrumo.application.auth.credentials as credentials
import cadrumo.application.auth.diagnostics as diagnostics
import cadrumo.application.auth.errors as errors
import cadrumo.application.auth.models as models
import cadrumo.application.auth.operation_definitions as operation_definitions
import cadrumo.application.auth.operator as operator
import cadrumo.application.auth.operator_cleanup as operator_cleanup
import cadrumo.application.auth.operator_probes as operator_probes
import cadrumo.application.auth.operator_results as operator_results
import cadrumo.application.auth.operator_scope as operator_scope
import cadrumo.application.auth.probes as probes
import cadrumo.application.auth.protocols as protocols
import cadrumo.application.auth.providers as providers
import cadrumo.application.auth.sessions as sessions

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
