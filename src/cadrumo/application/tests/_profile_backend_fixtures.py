"""Canonical real profile backend for application reconciliation tests."""

from ...tests.active_profile_isolated_backend_fixture import active_profile_isolated_backend_fixture

_isolated_backend = active_profile_isolated_backend_fixture(profile_overrides={"identity.tax_id": "00000000T"})


__all__ = ["_isolated_backend"]
