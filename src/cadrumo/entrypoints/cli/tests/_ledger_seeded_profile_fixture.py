"""Canonical seeded-profile fixtures for ledger CLI journeys."""

from __future__ import annotations

from ....tests.active_profile_isolated_backend_fixture import active_profile_isolated_backend_fixture

__all__ = ["_isolated_backend"]

_BUCKET_ID = "00000000-0000-4000-8000-000000000000"

_isolated_backend = active_profile_isolated_backend_fixture(
    bucket_id=_BUCKET_ID,
    dispose_engine_around=True,
    settings_overrides={"cadrumo_output_language": "en"},
)
