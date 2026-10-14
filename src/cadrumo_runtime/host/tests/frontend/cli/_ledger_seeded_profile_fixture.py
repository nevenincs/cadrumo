"""Canonical seeded-profile fixtures for ledger CLI journeys."""

from __future__ import annotations

from .runtime_profile_backend import runtime_profile_backend_fixture

__all__ = ["_isolated_backend"]

_isolated_backend = runtime_profile_backend_fixture(settings_overrides={"cadrumo_output_language": "en"})
