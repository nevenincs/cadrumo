"""Fixtures for profile persistence integration tests."""

from collections.abc import Generator, Iterator
from pathlib import Path

import pytest

from cadrumo.adapters.persistence.profile.tests.certificate_secret_fakes import InMemoryCertificateSecretBackendFactory
from cadrumo.adapters.persistence.profile.tests.file_flow_test_support import (
    _file_flow_runtime,
    _FileFlowRuntime,
    _Repos,
    _repos,
)
from cadrumo.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from cadrumo.adapters.persistence.storage.tests.secure_sql import (
    TestRuntimeProfile,
    isolated_runtime_profile,
    reset_secure_object_store,
)
from cadrumo.adapters.persistence.tests.runtime_profile_fixture import default_bucket_runtime_profile_fixture
from cadrumo.application.ledger.invoice_extraction_authority import default_invoice_extraction_period
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.iva.regime_legend import resolve_regime_legends

from ._invoice_confirmation_test_support import InvoiceAuthorityFixture
from .ledger_action_persistence_support import _BUCKET_ID
from .published_authority_support import release_published_authority_operation

# These suites exercise the profile-bound secure-object adapter through an
# explicitly requested runtime.  The fixture body is composed by the outer
# persistence test owner, not by an application test package.
secure_engine = default_bucket_runtime_profile_fixture(autouse=False, name="secure_engine")


@pytest.fixture(scope="session", autouse=True)
def _published_authority_lease() -> Iterator[None]:
    """Release the per-worker published authority lease seeded snapshots use."""
    yield
    release_published_authority_operation()


@pytest.fixture
def certificate_secret_backend_factory() -> InMemoryCertificateSecretBackendFactory:
    """Inject the application certificate-secret capability without a persistence adapter."""
    return InMemoryCertificateSecretBackendFactory()


@pytest.fixture
def invoice_authority() -> Generator[InvoiceAuthorityFixture]:
    """Keep extraction, legends, and confirmation on one live authority lease."""
    with bundled_indexed_authority().operation() as operation:
        period = default_invoice_extraction_period()
        yield InvoiceAuthorityFixture(
            operation=operation,
            legends=resolve_regime_legends(operation=operation, effective_date=period.end_date),
        )


@pytest.fixture(scope="module")
def _ledger_module_runtime(tmp_path_factory: pytest.TempPathFactory) -> Iterator[TestRuntimeProfile]:
    """Provision the expensive ledger-action bucket runtime once per module."""
    tmp_path = tmp_path_factory.mktemp("ledger-action-runtime")
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        yield profile


_FILING_REVIEW_BUCKET_ID = "66666666-6666-4666-8666-666666666666"


@pytest.fixture(scope="module")
def _active_bucket_runtime(tmp_path_factory: pytest.TempPathFactory) -> Iterator[TestRuntimeProfile]:
    """Provision the shared active bucket for filing review integration tests."""
    tmp_path = tmp_path_factory.mktemp("filing-review-runtime")
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_FILING_REVIEW_BUCKET_ID) as profile:
        yield profile


@pytest.fixture
def secure_objects(_ledger_module_runtime: TestRuntimeProfile) -> Iterator[SecureObjectRepository]:
    """Reset the ledger-action secure store before each integration test."""
    reset_secure_object_store(_ledger_module_runtime.repository)
    yield _ledger_module_runtime.repository


@pytest.fixture
def repos(tmp_path: Path) -> Iterator[_Repos]:
    yield from _repos(tmp_path)


@pytest.fixture
def file_flow_runtime(tmp_path: Path) -> Iterator[_FileFlowRuntime]:
    """Yield the file-flow repository bundle alongside its live engine."""
    yield from _file_flow_runtime(tmp_path)
