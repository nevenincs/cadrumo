"""Runtime ownership proofs for every public outbound-auth defining module."""

from __future__ import annotations

import ast
from pathlib import Path
from types import ModuleType

import pytest

import cadrumo.adapters.outbound.aeat.auth.authenticator as authenticator
import cadrumo.adapters.outbound.aeat.auth.authenticator_persistence as authenticator_persistence
import cadrumo.adapters.outbound.aeat.auth.authenticator_types as authenticator_types
import cadrumo.adapters.outbound.aeat.auth.browser_lifecycle as browser_lifecycle
import cadrumo.adapters.outbound.aeat.auth.certificate as certificate
import cadrumo.adapters.outbound.aeat.auth.clave_movil as clave_movil
import cadrumo.adapters.outbound.aeat.auth.clave_movil_metadata as clave_movil_metadata
import cadrumo.adapters.outbound.aeat.auth.clave_movil_support as clave_movil_support
import cadrumo.adapters.outbound.aeat.auth.clave_permanente as clave_permanente
import cadrumo.adapters.outbound.aeat.auth.clave_permanente_metadata as clave_permanente_metadata
import cadrumo.adapters.outbound.aeat.auth.clave_permanente_support as clave_permanente_support
import cadrumo.adapters.outbound.aeat.auth.errors as errors
import cadrumo.adapters.outbound.aeat.auth.provider_selection as provider_selection
import cadrumo.adapters.outbound.aeat.auth.providers as providers
import cadrumo.adapters.outbound.aeat.auth.session_store as session_store

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_PUBLIC_DEFINING_MODULES: tuple[ModuleType, ...] = (
    authenticator,
    authenticator_persistence,
    authenticator_types,
    browser_lifecycle,
    certificate,
    clave_movil,
    clave_movil_metadata,
    clave_movil_support,
    clave_permanente,
    clave_permanente_metadata,
    clave_permanente_support,
    errors,
    provider_selection,
    providers,
    session_store,
)


def _imported_names(module: ModuleType) -> frozenset[str]:
    """Return every name imported into ``module`` by its source."""
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
def test_every_public_outbound_auth_export_is_owned_by_its_defining_module(module: ModuleType) -> None:
    """Reject missing, duplicate, imported, anonymous, and foreign exports."""
    exported = tuple(module.__all__)
    assert exported
    assert len(exported) == len(set(exported))
    assert [name for name in exported if name not in vars(module)] == []
    assert sorted(set(exported) & _imported_names(module)) == []
    foreign = {
        name: getattr(getattr(module, name), "__module__", None)
        for name in exported
        if getattr(getattr(module, name), "__module__", None) not in (None, module.__name__)
    }
    assert foreign == {}
