"""Canonical real-runtime fixtures for counterparty fact tests."""

from collections.abc import Iterator
from pathlib import Path

import pytest

from ....tests.secure_sql import TestRuntimeProfile, isolated_runtime_profile
from .._counterparty_establishment import ConfirmedCounterpartyFactsRepository

_BUCKET_ID = "36363636-3636-4636-8636-363636363636"


@pytest.fixture
def runtime_profile(tmp_path: Path) -> Iterator[TestRuntimeProfile]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        yield profile


@pytest.fixture
def repository(runtime_profile: TestRuntimeProfile) -> ConfirmedCounterpartyFactsRepository:
    return ConfirmedCounterpartyFactsRepository(objects=runtime_profile.repository)


__all__ = ["repository", "runtime_profile"]
