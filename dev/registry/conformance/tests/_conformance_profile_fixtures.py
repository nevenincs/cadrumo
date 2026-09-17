"""Canonical bundled conformance profile fixtures."""

import pytest

from cadrumo.domain.calculations.registry.governed_fact_scope import validating_governed_facts

from ...compiler.authority import compiled_bundled_authority
from ..profile import RegistryConformanceProfile, audit_bundled_registry_conformance


# Module-scoped fixtures compute outside every test's own scope, so each enters
# the compiled authority's governed facts for the audit it runs.
@pytest.fixture(scope="module")
def degraded_profile() -> RegistryConformanceProfile:
    with validating_governed_facts(compiled_bundled_authority()):
        return audit_bundled_registry_conformance(validate=False)


@pytest.fixture(scope="module")
def validated_profile() -> RegistryConformanceProfile:
    with validating_governed_facts(compiled_bundled_authority()):
        return audit_bundled_registry_conformance()


__all__ = ["degraded_profile", "validated_profile"]
