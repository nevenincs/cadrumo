"""Fixtures shared by every profile persistence integration suite.

The persistence adapter tests and the integration tests composed at the
entrypoint seam register the same fixtures from this module in their own
``conftest.py``, so both run against one definition.
"""

from collections.abc import Generator, Iterator

import pytest

from .....application.ledger.invoice_extraction_authority import default_invoice_extraction_period
from .....domain.calculations.registry.authority import bundled_indexed_authority
from .....domain.iva.regime_legend import resolve_regime_legends
from ...storage.sql.secure_objects import SecureObjectRepository
from ...storage.tests.secure_sql import (
    TestRuntimeProfile,
    isolated_runtime_profile,
    reset_secure_object_store,
)
from ...tests.runtime_profile_fixture import default_bucket_runtime_profile_fixture
from ._invoice_confirmation_test_support import InvoiceAuthorityFixture
from .certificate_secret_fakes import InMemoryCertificateSecretBackendFactory
from .ledger_action_persistence_support import BUCKET_ID
from .published_authority_support import release_published_authority_operation

# These suites exercise the profile-bound secure-object adapter through an
# explicitly requested runtime.  The fixture body is composed by the outer
# persistence test owner, not by an application test package.
secure_engine = default_bucket_runtime_profile_fixture(autouse=False, name="secure_engine")

FILING_REVIEW_BUCKET_ID = "66666666-6666-4666-8666-666666666666"


@pytest.fixture(scope="session", autouse=True, name="_published_authority_lease")
def published_authority_lease() -> Iterator[None]:
    """Release the per-worker published authority lease seeded snapshots use."""
    yield
    release_published_authority_operation()


@pytest.fixture(autouse=True, name="_governed_facts_from_the_session_lease")
def governed_facts_from_the_session_lease(operation: object) -> None:
    """Scope every profile persistence test to the published session lease.

    These suites build registry-backed profiles and records throughout, so
    the package opts in once rather than per module.
    """
    del operation


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


@pytest.fixture(scope="module", name="_ledger_module_runtime")
def ledger_module_runtime(tmp_path_factory: pytest.TempPathFactory) -> Iterator[TestRuntimeProfile]:
    """Provision the expensive ledger-action bucket runtime once per module."""
    tmp_path = tmp_path_factory.mktemp("ledger-action-runtime")
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=BUCKET_ID) as profile:
        yield profile


@pytest.fixture(scope="module", name="_active_bucket_runtime")
def active_bucket_runtime(tmp_path_factory: pytest.TempPathFactory) -> Iterator[TestRuntimeProfile]:
    """Provision the shared active bucket for filing review integration tests."""
    tmp_path = tmp_path_factory.mktemp("filing-review-runtime")
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=FILING_REVIEW_BUCKET_ID) as profile:
        yield profile


@pytest.fixture
def secure_objects(_ledger_module_runtime: TestRuntimeProfile) -> Iterator[SecureObjectRepository]:
    """Reset the ledger-action secure store before each integration test."""
    reset_secure_object_store(_ledger_module_runtime.repository)
    yield _ledger_module_runtime.repository
