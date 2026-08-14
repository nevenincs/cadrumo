"""Canonical schema-loader fixtures for the user-profile schema test cluster.

The fixture providers deliberately retain the scopes established by their
former local definitions. Both have pytest's effective name ``schema``, but
test modules import exactly one provider so their visibility never competes.
"""

from __future__ import annotations

import pytest

from ....core.resources import resources
from .._loader import load_user_profile_schema
from .._schema import ProfileSchemaDefinition


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
    return frozenset(resources().modelos.authority.catalogues.legal)
