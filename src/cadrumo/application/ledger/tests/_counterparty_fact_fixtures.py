"""Canonical real-runtime fixtures for counterparty fact tests."""

from ....adapters.persistence.tests.runtime_profile_fixture import bucket_scoped_runtime_profile_fixture

_BUCKET_ID = "36363636-3636-4636-8636-363636363636"

runtime_profile = bucket_scoped_runtime_profile_fixture(_BUCKET_ID, autouse=False, name="runtime_profile")

__all__ = ["runtime_profile"]
