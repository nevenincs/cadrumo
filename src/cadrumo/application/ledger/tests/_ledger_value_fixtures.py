"""Canonical dependency-only value fixtures for ledger tests."""

from pathlib import Path

import pytest

from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....core.config import Settings
from ....tests.secure_sql import TestRuntimeProfile
from ..counterparty_establishment import ConfirmedCounterpartyFactsRepository


@pytest.fixture
def repository(runtime_profile: TestRuntimeProfile) -> ConfirmedCounterpartyFactsRepository:
    return ConfirmedCounterpartyFactsRepository(objects=runtime_profile.repository)


@pytest.fixture
def isolated_settings(runtime_profile: TestRuntimeProfile) -> Settings:
    return runtime_profile.settings


@pytest.fixture
def secure_objects(runtime_profile: TestRuntimeProfile) -> SecureObjectRepository:
    return runtime_profile.repository


@pytest.fixture
def pdf_file(tmp_path: Path) -> Path:
    path = tmp_path / "receipt.pdf"
    path.write_bytes(b"%PDF-1.4 test")
    return path


__all__ = ["isolated_settings", "pdf_file", "repository", "secure_objects"]
