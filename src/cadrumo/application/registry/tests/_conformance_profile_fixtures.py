"""Canonical bundled conformance profile fixtures."""

import pytest

from ..conformance import RegistryConformanceProfile, audit_bundled_registry_conformance


@pytest.fixture(scope="module")
def degraded_profile() -> RegistryConformanceProfile:
    return audit_bundled_registry_conformance(validate=False)


@pytest.fixture(scope="module")
def validated_profile() -> RegistryConformanceProfile:
    return audit_bundled_registry_conformance()


__all__ = ["degraded_profile", "validated_profile"]
