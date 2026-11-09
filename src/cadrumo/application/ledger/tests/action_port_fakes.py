"""Empty and in-memory action ports for the shared ledger action bundle in tests."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from hashlib import sha256 as compute_sha256
from pathlib import Path
from typing import override

from ....core.classification.policies import SensitivityClass
from ....core.secure_object_write import SecureObjectWrite, SecureObjectWriteUnit
from ....domain.attachments.models import Attachment
from ....domain.attachments.protocols import AttachmentStoreProtocol
from ....domain.buckets.event import BucketEventHistoryCatalogue
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.invoices.catalogue import InvoiceCatalogue
from ....domain.modelos.calculation_revision import CalculationRevisionCatalogue
from ....domain.modelos.protocols import CalculationRevisionCatalogueRepositoryProtocol
from ....domain.modelos.work_unit import WorkUnitCatalogue
from ....domain.modelos.work_unit_repository import WorkUnitCatalogueRepositoryProtocol
from ....domain.usage_ratios.model import UsageRatioProfile
from ..protocols import (
    BucketEventHistoryCoCommitWriterProtocol,
    InvoiceCatalogueCoCommitWriterProtocol,
)


class InMemoryEventRepository(BucketEventHistoryCoCommitWriterProtocol):
    """In-memory event capability; event persistence is outside this test seam."""

    def __init__(self) -> None:
        self._catalogue = BucketEventHistoryCatalogue()
        self._revision_id = "0" * 64

    @override
    def exists(self) -> bool:
        return bool(self._catalogue.events)

    @override
    def load(self) -> BucketEventHistoryCatalogue:
        return self._catalogue

    @override
    def save(self, catalogue: BucketEventHistoryCatalogue) -> None:
        self._catalogue = catalogue

    @override
    def load_revisioned(self) -> tuple[BucketEventHistoryCatalogue, str]:
        return self._catalogue, self._revision_id

    @override
    def to_secure_object_write(
        self,
        catalogue: BucketEventHistoryCatalogue,
        *,
        expected_revision_id: str | None = None,
    ) -> SecureObjectWrite:
        del expected_revision_id
        self._catalogue = catalogue
        return SecureObjectWrite(
            namespace="application-test-events",
            object_key="classification",
            classification=SensitivityClass.FINANCIAL,
            schema_version=1,
            written_at=datetime.now(UTC),
            payload=b"event-catalogue",
        )


class EmptyInvoiceRepository(InvoiceCatalogueCoCommitWriterProtocol):
    """Unused invoice capability required by the shared ledger action bundle."""

    def __init__(self, *, bucket_id: str) -> None:
        self._bucket_id = bucket_id
        self._catalogue = InvoiceCatalogue()
        self._revision_id = "0" * 64

    @property
    @override
    def bucket_id(self) -> str:
        return self._bucket_id

    @override
    def exists(self) -> bool:
        return bool(self._catalogue.invoices)

    @override
    def load(self) -> InvoiceCatalogue:
        return self._catalogue

    @override
    def save(self, catalogue: InvoiceCatalogue) -> None:
        self._catalogue = catalogue

    @override
    def load_revisioned(self) -> tuple[InvoiceCatalogue, str]:
        return self._catalogue, self._revision_id

    @override
    def to_secure_object_write(
        self,
        catalogue: InvoiceCatalogue,
        *,
        expected_revision_id: str | None = None,
    ) -> SecureObjectWrite:
        del expected_revision_id
        return SecureObjectWrite(
            namespace="application-test-invoices",
            object_key="classification",
            classification=SensitivityClass.FINANCIAL,
            schema_version=1,
            written_at=datetime.now(UTC),
            payload=catalogue.model_dump_json().encode("utf-8"),
        )


class InMemoryAttachmentStore(AttachmentStoreProtocol):
    """Small content-addressed attachment port with no filesystem persistence."""

    def __init__(self) -> None:
        self._blobs: dict[str, bytes] = {}
        self._manifests: dict[str, Attachment] = {}

    @override
    def put_bytes(self, data: bytes) -> str:
        attachment_id = compute_sha256(data).hexdigest()
        self._blobs[attachment_id] = data
        return attachment_id

    @override
    def put_file(self, source: Path) -> tuple[str, int]:
        data = source.read_bytes()
        return self.put_bytes(data), len(data)

    @override
    def read_bytes(self, sha256: str) -> bytes:
        return self._blobs[sha256]

    @override
    def write_manifest(self, attachment: Attachment) -> None:
        self._manifests[attachment.attachment_id] = attachment

    @override
    def load_manifest(self, attachment_id: str) -> Attachment:
        return self._manifests[attachment_id]

    @override
    def iter_manifests(self) -> Iterator[Attachment]:
        for attachment_id in sorted(self._manifests):
            yield self._manifests[attachment_id]

    @override
    def verify_blob(self, attachment_id: str) -> None:
        if compute_sha256(self._blobs[attachment_id]).hexdigest() != attachment_id:
            raise ValueError(f"attachment blob digest mismatch for {attachment_id}")


class EmptyWorkUnitRepository(WorkUnitCatalogueRepositoryProtocol):
    def __init__(self, *, bucket_id: str) -> None:
        self._bucket_id = bucket_id
        self._catalogue = WorkUnitCatalogue()
        self._revision_id = "0" * 64

    @property
    @override
    def bucket_id(self) -> str:
        return self._bucket_id

    @override
    def exists(self) -> bool:
        return bool(self._catalogue.work_units)

    @override
    def load(self) -> WorkUnitCatalogue:
        return self._catalogue

    @override
    def load_revisioned(self) -> tuple[WorkUnitCatalogue, str]:
        return self._catalogue, self._revision_id

    @override
    def save(self, catalogue: WorkUnitCatalogue) -> None:
        self._catalogue = catalogue

    @override
    def mutate(self, mutation: Callable[[WorkUnitCatalogue], WorkUnitCatalogue]) -> WorkUnitCatalogue:
        self._catalogue = mutation(self._catalogue)
        return self._catalogue

    @override
    def save_with_secure_object_writes(
        self,
        catalogue: WorkUnitCatalogue,
        extra_writes: tuple[SecureObjectWrite, ...],
        *,
        expected_revision_id: str | None = None,
    ) -> None:
        del extra_writes, expected_revision_id
        self._catalogue = catalogue

    @override
    def to_secure_object_write(
        self,
        catalogue: WorkUnitCatalogue,
        *,
        expected_revision_id: str | None = None,
    ) -> SecureObjectWrite:
        del expected_revision_id
        return SecureObjectWrite(
            namespace="application-test-work-units",
            object_key="classification",
            classification=SensitivityClass.FINANCIAL,
            schema_version=1,
            written_at=datetime.now(UTC),
            payload=catalogue.model_dump_json().encode("utf-8"),
        )


class EmptyCalculationRepository(CalculationRevisionCatalogueRepositoryProtocol):
    def __init__(self, *, bucket_id: str) -> None:
        self._bucket_id = bucket_id
        self._catalogue = CalculationRevisionCatalogue()
        self._revision_id = "0" * 64

    @property
    @override
    def bucket_id(self) -> str:
        return self._bucket_id

    @override
    def exists(self) -> bool:
        return bool(self._catalogue.revisions)

    @override
    def stored_catalogue_is_known_override_free(self) -> bool:
        return False

    @override
    def load(self, *, operation: PinnedAuthorityOperation | None = None) -> CalculationRevisionCatalogue:
        return self._catalogue

    @override
    def load_revisioned(
        self, *, operation: PinnedAuthorityOperation | None = None
    ) -> tuple[CalculationRevisionCatalogue, str]:
        return self._catalogue, self._revision_id

    @override
    def save(self, catalogue: CalculationRevisionCatalogue) -> None:
        self._catalogue = catalogue

    @override
    def to_secure_object_write_unit(
        self,
        catalogue: CalculationRevisionCatalogue,
        *,
        expected_revision_id: str | None = None,
    ) -> SecureObjectWriteUnit:
        del expected_revision_id
        return SecureObjectWriteUnit(
            writes=(
                SecureObjectWrite(
                    namespace="application-test-calculations",
                    object_key="classification",
                    classification=SensitivityClass.FINANCIAL,
                    schema_version=1,
                    written_at=datetime.now(UTC),
                    payload=catalogue.model_dump_json().encode("utf-8"),
                ),
            )
        )

    @override
    def save_with_secure_object_writes(
        self,
        catalogue: CalculationRevisionCatalogue,
        extra_writes: tuple[SecureObjectWrite, ...],
        *,
        expected_revision_id: str | None = None,
    ) -> None:
        del extra_writes, expected_revision_id
        self._catalogue = catalogue


def empty_usage_ratio_profile(*, bucket_id: str, operation: PinnedAuthorityOperation) -> UsageRatioProfile:
    """Return an empty profile while honoring the operation-bound loader shape."""
    del bucket_id, operation
    return UsageRatioProfile()
