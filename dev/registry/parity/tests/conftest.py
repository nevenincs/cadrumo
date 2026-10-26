"""Shared fixtures for the Renta WEB Open replay-parity tests.

`registry_tree` is defined in the registry package's own conftest, which
pytest never applies outside `src/`, so this directory redeclares it -- same
object, same session scope, following the precedent at
`dev/registry/tests/conftest.py`.
"""

from __future__ import annotations

import pytest

from cadrumo.domain.calculations.registry.schema import ModeloDefinition, RegistryCatalogues
from cadrumo.domain.calculations.registry.tests.registry_tree import bundled_registry_tree


@pytest.fixture(scope="session")
def registry_tree() -> tuple[tuple[ModeloDefinition, ...], RegistryCatalogues]:
    return bundled_registry_tree()
