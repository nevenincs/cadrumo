"""Fixtures for profile persistence integration tests composed at the entrypoint seam."""

from collections.abc import Iterator

import pytest

from ....adapters.persistence.profile.tests import profile_persistence_fixtures
from .file_flow_test_support import _file_flow_runtime, _FileFlowRuntime, _Repos, file_flow_repositories
from .file_flow_test_support import file_flow_seeded_profile as _file_flow_seeded_profile
from .secure_store_baseline import SeededDurableProfile

secure_engine = profile_persistence_fixtures.secure_engine
published_authority_lease = profile_persistence_fixtures.published_authority_lease
governed_facts_from_the_session_lease = profile_persistence_fixtures.governed_facts_from_the_session_lease
certificate_secret_backend_factory = profile_persistence_fixtures.certificate_secret_backend_factory
invoice_authority = profile_persistence_fixtures.invoice_authority
ledger_module_runtime = profile_persistence_fixtures.ledger_module_runtime
active_bucket_runtime = profile_persistence_fixtures.active_bucket_runtime
secure_objects = profile_persistence_fixtures.secure_objects


@pytest.fixture(scope="module", name="_file_flow_seeded_profile")
def file_flow_seeded_profile(tmp_path_factory: pytest.TempPathFactory) -> SeededDurableProfile:
    """Pay profile registration and key derivation once per test module."""
    return _file_flow_seeded_profile(tmp_path_factory.mktemp("file-flow-runtime"))


@pytest.fixture
def repos(_file_flow_seeded_profile: SeededDurableProfile) -> Iterator[_Repos]:
    yield from file_flow_repositories(_file_flow_seeded_profile)


@pytest.fixture
def file_flow_runtime(_file_flow_seeded_profile: SeededDurableProfile) -> Iterator[_FileFlowRuntime]:
    """Yield the file-flow repository bundle alongside its live engine."""
    yield from _file_flow_runtime(_file_flow_seeded_profile)
