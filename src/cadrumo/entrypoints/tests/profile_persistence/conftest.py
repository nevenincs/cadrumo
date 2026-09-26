"""Fixtures for profile persistence integration tests composed at the entrypoint seam."""

from collections.abc import Iterator
from pathlib import Path

import pytest

from ....adapters.persistence.profile.tests import profile_persistence_fixtures
from .file_flow_test_support import _file_flow_runtime, _FileFlowRuntime, _Repos, _repos

secure_engine = profile_persistence_fixtures.secure_engine
published_authority_lease = profile_persistence_fixtures.published_authority_lease
governed_facts_from_the_session_lease = profile_persistence_fixtures.governed_facts_from_the_session_lease
certificate_secret_backend_factory = profile_persistence_fixtures.certificate_secret_backend_factory
invoice_authority = profile_persistence_fixtures.invoice_authority
ledger_module_runtime = profile_persistence_fixtures.ledger_module_runtime
active_bucket_runtime = profile_persistence_fixtures.active_bucket_runtime
secure_objects = profile_persistence_fixtures.secure_objects


@pytest.fixture
def repos(tmp_path: Path) -> Iterator[_Repos]:
    yield from _repos(tmp_path)


@pytest.fixture
def file_flow_runtime(tmp_path: Path) -> Iterator[_FileFlowRuntime]:
    """Yield the file-flow repository bundle alongside its live engine."""
    yield from _file_flow_runtime(tmp_path)
