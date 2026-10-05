"""Canonical bundled conformance profile fixtures."""

import pytest

from cadrumo.domain.calculations.registry.governed_fact_scope import outside_governed_fact_validation

from ..profile import RegistryConformanceProfile, audit_bundled_registry_conformance


# The conformance CLI runs with no enclosing governed-fact scope, so the audit
# must scope the authority it audits itself. Clearing any ambient scope here
# keeps every profile test exercising that, rather than a scope lent by the
# test harness.
@pytest.fixture(scope="module")
def degraded_profile() -> RegistryConformanceProfile:
    with outside_governed_fact_validation():
        return audit_bundled_registry_conformance(validate=False)


@pytest.fixture(scope="module")
def validated_profile() -> RegistryConformanceProfile:
    with outside_governed_fact_validation():
        return audit_bundled_registry_conformance()


__all__ = ["degraded_profile", "validated_profile"]
