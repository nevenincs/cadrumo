"""Canonical validated registry authority fixture for documentation tests."""

from cadrumo.tests.registry_authority_fixture import bundled_registry_authority_fixture

authority = bundled_registry_authority_fixture(name="authority")

__all__ = ["authority"]
