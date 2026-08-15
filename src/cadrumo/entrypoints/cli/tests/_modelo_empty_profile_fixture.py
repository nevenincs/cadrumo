"""Canonical empty-profile fixture for Modelo CLI inventory checks."""

from __future__ import annotations

from ....tests.profile_storage_root_fixture import isolated_profile_storage_fixture

__all__ = ["_isolated_backend"]

_isolated_backend = isolated_profile_storage_fixture(name="_isolated_backend", dispose_engine_around=True)
