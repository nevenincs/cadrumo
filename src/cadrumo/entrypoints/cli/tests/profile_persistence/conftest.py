"""Fixtures for CLI-composed profile persistence integration tests."""

from collections.abc import Iterator

import pytest

from cadrumo.entrypoints.tests.profile_persistence.file_flow_test_support import (
    Repos,
    file_flow_repositories,
    file_flow_seeded_profile,
)
from cadrumo.entrypoints.tests.profile_persistence.secure_store_baseline import SeededDurableProfile

from .....adapters.persistence.profile.tests import profile_persistence_fixtures

secure_engine = profile_persistence_fixtures.secure_engine
published_authority_lease = profile_persistence_fixtures.published_authority_lease
governed_facts_from_the_session_lease = profile_persistence_fixtures.governed_facts_from_the_session_lease
certificate_secret_backend_factory = profile_persistence_fixtures.certificate_secret_backend_factory
invoice_authority = profile_persistence_fixtures.invoice_authority
ledger_module_runtime = profile_persistence_fixtures.ledger_module_runtime
active_bucket_runtime = profile_persistence_fixtures.active_bucket_runtime
secure_objects = profile_persistence_fixtures.secure_objects


@pytest.fixture(scope="module")
def _file_flow_seeded_profile(tmp_path_factory: pytest.TempPathFactory) -> SeededDurableProfile:
    return file_flow_seeded_profile(tmp_path_factory.mktemp("file-flow-runtime"))


@pytest.fixture
def repos(_file_flow_seeded_profile: SeededDurableProfile) -> Iterator[Repos]:
    yield from file_flow_repositories(_file_flow_seeded_profile)
