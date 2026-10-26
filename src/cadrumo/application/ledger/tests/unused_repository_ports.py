"""Failing repository capabilities for unit tests that isolate another owner."""

from __future__ import annotations

from typing import Never

from pydantic import BaseModel

from ....domain.transactions.models import LedgerDatePartition


class ProfileOnlyCatalogueRepository[CatalogueT: BaseModel]:
    """Expose a profile identity and refuse every catalogue access or mutation."""

    def __init__(self, bucket_id: str) -> None:
        self.bucket_id = bucket_id

    def exists(self) -> bool:
        raise AssertionError("this unit test does not access this catalogue")

    def load(self, **_kwargs: object) -> CatalogueT:
        raise AssertionError("this unit test does not read this catalogue")

    def load_revisioned(self, **_kwargs: object) -> tuple[CatalogueT, str]:
        raise AssertionError("this unit test does not read this catalogue revision")

    def load_by_ids(self, transaction_ids: object) -> CatalogueT:
        raise AssertionError("this unit test does not read transaction identities")

    def load_for_date_range(self, start: object, end: object) -> CatalogueT:
        raise AssertionError("this unit test does not read a date window")

    def partition_by_date_range(self, start: object, end: object) -> LedgerDatePartition:
        raise AssertionError("this unit test does not partition transactions")

    def save(self, catalogue: object) -> Never:
        raise AssertionError("this unit test does not save this catalogue")

    def mutate(self, mutation: object) -> CatalogueT:
        raise AssertionError("this unit test does not mutate this catalogue")

    def to_secure_object_write(self, catalogue: object, **_kwargs: object) -> Never:
        raise AssertionError("this unit test does not prepare secure catalogue writes")

    def save_with_secure_object_writes(self, catalogue: object, extra_writes: object, **_kwargs: object) -> Never:
        raise AssertionError("this unit test does not co-commit this catalogue")

    def replace_if_current_with_secure_object_writes(
        self, current: object, replacement: object, extra_writes: object
    ) -> Never:
        raise AssertionError("this unit test does not replace a transaction")


class UnusedAttachmentStore:
    """Refuse attachment access when an isolated worker owns the tested outcome."""

    def put_bytes(self, data: bytes) -> Never:
        raise AssertionError("this unit test does not store attachment bytes")

    def put_file(self, source: object) -> Never:
        raise AssertionError("this unit test does not store attachment files")

    def read_bytes(self, sha256: str) -> Never:
        raise AssertionError("this unit test does not read attachment bytes")

    def write_manifest(self, attachment: object) -> Never:
        raise AssertionError("this unit test does not write attachment manifests")

    def load_manifest(self, attachment_id: str) -> Never:
        raise AssertionError("this unit test does not read attachment manifests")

    def iter_manifests(self) -> Never:
        raise AssertionError("this unit test does not enumerate attachment manifests")

    def verify_blob(self, attachment_id: str) -> Never:
        raise AssertionError("this unit test does not verify attachment blobs")


class UnusedBucketEventRepository:
    """Refuse event reads and writes replaced by the unit test's owning seam."""

    def __init__(self, backend: object | None = None) -> None:
        self.secure_object_repository = backend

    def exists(self) -> Never:
        raise AssertionError("this unit test does not access bucket events")

    def load(self) -> Never:
        raise AssertionError("this unit test does not read bucket events")

    def load_revisioned(self) -> Never:
        raise AssertionError("this unit test does not read bucket event revisions")

    def save(self, catalogue: object) -> Never:
        raise AssertionError("this unit test does not save bucket events")

    def to_secure_object_write(self, catalogue: object, **_kwargs: object) -> Never:
        raise AssertionError("this unit test does not prepare bucket event writes")


class UnusedEvidenceAttachmentIngestor:
    """Expose custody identity while refusing an unexpected ingestion call."""

    def __init__(self, backend: object | None = None) -> None:
        self.secure_object_repository = backend

    def ingest(self, request: object) -> Never:
        raise AssertionError("this unit test does not ingest attachments")
