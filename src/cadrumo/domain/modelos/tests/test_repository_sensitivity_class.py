"""Sensitivity-class pinning tests for modelo and bucket catalogues.

The suite writes through the real profile secure-object repositories and then
checks the persisted metadata against the namespace authority, proving modelo
calculation, filing, work-unit, verification-report, and bucket-event catalogues
stay under the ``FINANCIAL`` storage class.

See Also:
    :class:`~adapters.persistence.storage.SecureObjectNamespaceDefinition`
        Namespace source for sensitivity, schema-version, and object-key
        contracts asserted here.
    :class:`~adapters.persistence.storage.SecureObjectRepository`
        Encrypted repository whose persisted metadata is inspected after each
        save.
    :mod:`~adapters.persistence.profile.modelos_work_units`
        Representative modelo catalogue repository covered by this shared
        sensitivity guard.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Protocol

import pytest

from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
from ....adapters.persistence.profile.modelos_verification_reports import VerificationReportCatalogueRepository
from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....adapters.persistence.storage import (
    BUCKET_EVENT_HISTORY_NAMESPACE,
    MODELO_CALCULATION_REVISION_CATALOGUE_NAMESPACE,
    MODELO_FILING_RECORD_CATALOGUE_NAMESPACE,
    MODELO_VERIFICATION_REPORT_CATALOGUE_NAMESPACE,
    MODELO_WORK_UNIT_CATALOGUE_NAMESPACE,
    SecureObjectNamespaceDefinition,
    SecureObjectRepository,
    SensitivityClass,
)
from ....domain.buckets import BucketEventHistoryCatalogue
from ....tests.secure_sql import isolated_runtime_profile
from .. import ModeloRecordCatalogue, VerificationReportCatalogue, WorkUnitCatalogue
from ..calculation_revision import CalculationRevisionCatalogue

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


class _CatalogueRepository(Protocol):
    @property
    def save(self) -> Callable[..., None]: ...


_REPOSITORY_CASES: tuple[
    tuple[
        str,
        Callable[[SecureObjectRepository], _CatalogueRepository],
        Callable[[], object],
        SecureObjectNamespaceDefinition,
    ],
    ...,
] = (
    (
        "CalculationRevisionCatalogueRepository",
        lambda objects: CalculationRevisionCatalogueRepository(objects=objects),
        CalculationRevisionCatalogue,
        MODELO_CALCULATION_REVISION_CATALOGUE_NAMESPACE,
    ),
    (
        "ModeloRecordCatalogueRepository",
        lambda objects: ModeloRecordCatalogueRepository(objects=objects),
        ModeloRecordCatalogue,
        MODELO_FILING_RECORD_CATALOGUE_NAMESPACE,
    ),
    (
        "WorkUnitCatalogueRepository",
        lambda objects: WorkUnitCatalogueRepository(objects=objects),
        WorkUnitCatalogue,
        MODELO_WORK_UNIT_CATALOGUE_NAMESPACE,
    ),
    (
        "VerificationReportCatalogueRepository",
        lambda objects: VerificationReportCatalogueRepository(objects=objects),
        VerificationReportCatalogue,
        MODELO_VERIFICATION_REPORT_CATALOGUE_NAMESPACE,
    ),
    (
        "BucketEventHistoryRepository",
        lambda objects: BucketEventHistoryRepository(objects=objects),
        BucketEventHistoryCatalogue,
        BUCKET_EVENT_HISTORY_NAMESPACE,
    ),
)


@pytest.mark.parametrize(("repository_name", "repository_factory", "catalogue_type", "namespace"), _REPOSITORY_CASES)
def test_repository_persists_catalogue_under_financial_secure_object_metadata(
    tmp_path: Path,
    repository_name: str,
    repository_factory: Callable[[SecureObjectRepository], _CatalogueRepository],
    catalogue_type: Callable[[], object],
    namespace: SecureObjectNamespaceDefinition,
) -> None:
    """Each repository must commit its catalogue as a FINANCIAL secure object.

    The parametrized cases bind each repository to its declared namespace object
    so this test verifies storage metadata rather than mirroring repository
    implementation details.
    """

    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        repository = repository_factory(profile.repository)

        repository.save(catalogue_type())
        object_key = namespace.default_object_key
        assert object_key is not None, f"{repository_name} namespace has no default object key"
        metadata = profile.repository.peek_metadata(namespace.namespace, object_key)

    assert metadata is not None, f"{repository_name} did not persist its catalogue"
    assert metadata.classification == SensitivityClass.FINANCIAL.value
    assert metadata.schema_version == namespace.schema_version
