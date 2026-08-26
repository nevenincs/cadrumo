"""Canonical schema-loader fixtures for the user-profile schema test cluster.

The fixture providers deliberately retain the scopes established by their
former local definitions. Both have pytest's effective name ``schema``, but
test modules import exactly one provider so their visibility never competes.
"""

from __future__ import annotations

import pytest

from ....tests.registry_tree import bundled_registry_tree
from ..loader import load_user_profile_schema
from ..schema import ProfileSchemaDefinition


@pytest.fixture(name="schema", scope="function")
def function_scoped_schema() -> ProfileSchemaDefinition:
    """Load the frozen schema separately for each requesting test."""
    return load_user_profile_schema()


@pytest.fixture(name="schema", scope="module")
def module_scoped_schema() -> ProfileSchemaDefinition:
    """Load the frozen schema once for each requesting test module."""
    return load_user_profile_schema()


@pytest.fixture(name="legal_ids", scope="module")
def legal_ids_fixture() -> frozenset[str]:
    """The legal-reference catalogue, read without a filing claim.

    Consumers only check that a profile-schema legal ref resolves against the
    catalogue -- a pure structural lookup, never a filing operation -- so this
    reads the compile-only tree directly rather than through
    ``bundled_authority()``, whose ``.load()`` validates every
    modelo in the bundled tree before returning anything.
    """
    _modelos, catalogues = bundled_registry_tree()
    return frozenset(catalogues.legal)
