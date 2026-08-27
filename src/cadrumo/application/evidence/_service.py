"""Build, verify, and export :class:`EvidenceBundle` manifests.

:class:`EvidenceBundleService` persists bundles through
:class:`EvidenceBundleRepository` and reports integrity checks as an
:class:`EvidenceBundleVerificationReport`.

The repository is a
:class:`~adapters.persistence.storage.SecureBoundRepository` namespace for
encrypted :class:`~adapters.persistence.storage.Envelope`-wrapped
bucket-local manifests, with the namespace, schema version, object-key grammar,
and custody disposition declared by
:data:`adapters.persistence.storage.APPLICATION_EVIDENCE_BUNDLE_NAMESPACE`.
:meth:`EvidenceBundleService.export` is the narrow operator-directed plaintext
exception: it verifies first, writes record bytes to the requested archive path before
``manifest.json``, and does not mutate the secure catalogue.

See Also:
    :class:`EvidenceBundle`,
    :class:`EvidenceRecordRef`,
    :class:`BundleVerificationState`, and
    :class:`EvidenceBundleCheckResult`.
"""

from __future__ import annotations

import zipfile
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import ClassVar, NamedTuple, override

from pydantic import BaseModel, Field

from ...adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ...adapters.persistence.storage import (
    APPLICATION_EVIDENCE_BUNDLE_NAMESPACE,
    SecureBoundRepository,
    secure_object_repository_for_bucket,
)
from ...core import STRICT_FROZEN_CONFIG, Hex64Str
from ...core.config import Settings
from ...core.external_constants import UTF_8_ENCODING
from ...core.hashing import sha256_hex
from ...core.identity import CalculationRevisionId
from ...core.time import now
from ._models import (
    BundleVerificationState,
    EvidenceBundle,
    EvidenceBundleCheckResult,
    EvidenceBundleNotFoundError,
    EvidenceBundleVerificationError,
    EvidenceRecordRef,
    VerificationCheck,
    derive_bundle_id,
)

_MANIFEST_VERSION = 1
_MANIFEST_FILENAME = "manifest.json"


class EvidenceBundleRepository(SecureBoundRepository[EvidenceBundle]):
    """Encrypted repository for bucket-local :class:`EvidenceBundle` manifests.

    The namespace, sensitivity, schema version, and payload type come
    from
    :data:`adapters.persistence.storage.APPLICATION_EVIDENCE_BUNDLE_NAMESPACE`
    so evidence bundles use the same secure-object envelope contract as other
    sensitive bucket-local application state.
    The :class:`~adapters.persistence.storage.SecureBoundRepository` base
    wraps each :class:`EvidenceBundle` in a
    :class:`~adapters.persistence.storage.Envelope` before writing it.

    See Also:
        :class:`EvidenceBundleService`
            Service layer that builds, verifies, and exports bundles.
        :class:`~adapters.persistence.storage.SecureBoundRepository`
            Generic encrypted-envelope repository base used by this store.
    """

    namespace: ClassVar[str] = APPLICATION_EVIDENCE_BUNDLE_NAMESPACE.namespace
    sensitivity: ClassVar = APPLICATION_EVIDENCE_BUNDLE_NAMESPACE.sensitivity
    schema_version: ClassVar[int] = APPLICATION_EVIDENCE_BUNDLE_NAMESPACE.schema_version
    payload_type: ClassVar[type[BaseModel]] = EvidenceBundle

    @override
    def extract_identifier(self, payload: EvidenceBundle) -> str:
        """Return the stable storage key for an :class:`EvidenceBundle`."""
        return payload.bundle_id


class EvidenceBundleVerificationReport(BaseModel):
    """Outcome of a verification pass over an :class:`EvidenceBundle`.

    ``findings`` carries per-check :class:`EvidenceBundleCheckResult`
    values, ``verification_state`` is the summarized
    :class:`BundleVerificationState`, and ``completeness_ratio`` reports
    how much of the manifest's referenced object payload was reachable.
    """

    model_config = STRICT_FROZEN_CONFIG

    bundle_id: Hex64Str
    verification_state: BundleVerificationState
    findings: tuple[EvidenceBundleCheckResult, ...] = Field(default_factory=tuple)
    completeness_ratio: float = Field(ge=0.0, le=1.0)


class _PayloadScan(NamedTuple):
    """What one pass over a manifest's records found in the supplied payloads."""

    reachable: int
    reachable_bytes: int
    digest_passes: int
    digest_failures: list[str]


def _scan_record_payloads(
    records: tuple[EvidenceRecordRef, ...],
    record_payloads: Mapping[tuple[str, str], bytes],
) -> _PayloadScan:
    """Recompute every reachable record's digest against its registered value.

    A record absent from ``record_payloads`` is unreachable rather than failed:
    it degrades completeness, while only a digest that disagrees fails
    verification.
    """
    reachable = 0
    reachable_bytes = 0
    digest_passes = 0
    digest_failures: list[str] = []
    for record in records:
        key = (record.object_type.value, record.object_id)
        if key not in record_payloads:
            continue
        reachable += 1
        reachable_bytes += record.payload_size_bytes
        if _hash_payload(record_payloads[key]) == record.content_sha256:
            digest_passes += 1
        else:
            digest_failures.append(record.object_id)
    return _PayloadScan(reachable, reachable_bytes, digest_passes, digest_failures)


def _completeness_ratio(*, total: int, total_bytes: int, reachable: int, reachable_bytes: int) -> float:
    """Return the byte-weighted share of manifest payload actually reached.

    completeness_ratio is documented (EvidenceRecordRef.payload_size_bytes) as
    the byte-weighted share of manifest payload reached, not a bare record
    count: a bundle dominated by one large unreachable record must not read as
    "mostly complete" because the other, tiny records were present. Fall back to
    the count-based ratio only when every record legitimately declares zero
    bytes (nothing to weight by).
    """
    if not total:
        return 1.0
    if total_bytes:
        return reachable_bytes / total_bytes
    return reachable / total


def _verification_state(
    *,
    all_passed: bool,
    digest_failures: list[str],
    completeness: float,
) -> BundleVerificationState:
    """Classify a bundle from its checks: a disagreeing digest always fails."""
    if all_passed:
        return BundleVerificationState.VERIFIED
    if digest_failures:
        return BundleVerificationState.FAILED
    if completeness < 1.0:
        return BundleVerificationState.INCOMPLETE
    return BundleVerificationState.FAILED


def _hash_payload(payload: bytes) -> str:
    return sha256_hex(payload)


class EvidenceBundleService:
    """Application service for the audit verb tree.

    Each method maps to one of the verbs in ``aeat app modelo audit``:
    ``build`` is the constructor side of ``add``-equivalent (audit bundles
    are produced by the file/verify path, not the operator). ``show``,
    ``check``, and ``export`` are operator-facing.

    Persisted manifests stay inside :class:`EvidenceBundleRepository`.
    Exported ZIP archives are separate caller-directed artifacts and are
    never treated as authoritative storage records.
    """

    def __init__(
        self,
        settings: Settings | None = None,
        repository_factory: Callable[[str], EvidenceBundleRepository] | None = None,
    ) -> None:
        # `load_settings()` honours `override_settings`; bare `Settings()`
        # does not. The repository factory uses the resolved settings so
        # bucket routes are still runtime-created when a test or CLI flow
        # scopes settings through the context variable.
        from ...core.config import load_settings as _load_settings

        self._settings = settings or _load_settings()
        self._repository_factory = repository_factory or self._runtime_repository_for

    def _runtime_repository_for(self, bucket_id: str) -> EvidenceBundleRepository:
        objects = secure_object_repository_for_bucket(bucket_id, self._settings)
        return EvidenceBundleRepository(objects=objects)

    def _repository_for(self, bucket_id: str) -> EvidenceBundleRepository:
        return self._repository_factory(bucket_id)

    def build(
        self,
        *,
        bucket_id: str,
        work_unit_id: str,
        record_payloads: Mapping[tuple[str, str], bytes],
        calculation_revision_id: CalculationRevisionId | None = None,
        filing_record_id: str | None = None,
        notes: str = "",
    ) -> EvidenceBundle:
        """Build a new bundle from a mapping of (object_type, object_id) -> raw bytes.

        The returned :class:`EvidenceBundle` has all record refs and
        provenance metadata populated and has already been saved through
        :class:`EvidenceBundleRepository`.
        """
        from ...domain.buckets import BucketEventObjectType

        records = tuple(
            EvidenceRecordRef(
                object_type=BucketEventObjectType(object_type),
                object_id=object_id,
                content_sha256=_hash_payload(payload),
                payload_size_bytes=len(payload),
            )
            for (object_type, object_id), payload in sorted(record_payloads.items())
        )
        bundle_id = derive_bundle_id(
            bucket_id=bucket_id,
            work_unit_id=work_unit_id,
            manifest_version=_MANIFEST_VERSION,
            records=records,
            calculation_revision_id=calculation_revision_id,
            filing_record_id=filing_record_id,
        )
        bundle = EvidenceBundle(
            bundle_id=bundle_id,
            manifest_version=_MANIFEST_VERSION,
            bucket_id=bucket_id,
            work_unit_id=work_unit_id,
            calculation_revision_id=calculation_revision_id,
            filing_record_id=filing_record_id,
            records=records,
            verification_state=BundleVerificationState.PENDING,
            completeness_ratio=1.0 if records else 0.0,
            created_at=now(),
            notes=notes,
        )
        self._repository_for(bucket_id).save(bundle)
        return bundle

    def show(self, *, bucket_id: str, bundle_id: str) -> EvidenceBundle:
        """Load a bundle by exact or unambiguous prefix match of ``bundle_id``.

        Tries an exact ``repository.load`` first; falls back to a prefix
        scan over all records in the bucket. Every candidate — exact or
        prefix — is bound to ``bucket_id``: a manifest whose own
        ``bucket_id`` disagrees with the requested bucket is never
        returned (it is a foreign or corrupt record, not a match), and a
        prefix matching more than one bundle in this bucket is refused
        rather than silently resolved to the first one found.

        Raises:
            EvidenceBundleNotFoundError: Nothing in ``bucket_id`` matches
                ``bundle_id``, or the prefix matches more than one bundle.

        Returns:
            :class:`EvidenceBundle`: The retrieved evidence bundle.
        """
        repository = self._repository_for(bucket_id)
        if bundle_id.strip():
            exact = repository.load(bundle_id)
            if exact is not None and exact.bucket_id == bucket_id:
                return exact
        matches = [
            bundle
            for bundle in repository.iter_records()
            if bundle.bucket_id == bucket_id
            and (bundle.bundle_id == bundle_id or bundle.bundle_id.startswith(bundle_id))
        ]
        if not matches:
            raise EvidenceBundleNotFoundError(
                translated_message="errors.refused.refused_evidence_bundle_not_found",
                context={"bundle_id": bundle_id, "bucket_id": bucket_id},
            )
        if len(matches) > 1:
            raise EvidenceBundleNotFoundError(
                translated_message="errors.refused.refused_evidence_bundle_ambiguous",
                context={
                    "bundle_id": bundle_id,
                    "bucket_id": bucket_id,
                    "match_count": len(matches),
                    "matches": ", ".join(sorted(bundle.bundle_id for bundle in matches)),
                },
            )
        return matches[0]

    def check(
        self,
        *,
        bucket_id: str,
        bundle_id: str,
        record_payloads: Mapping[tuple[str, str], bytes] | None = None,
    ) -> EvidenceBundleVerificationReport:
        """Re-verify a bundle and return an :class:`EvidenceBundleVerificationReport`.

        The caller supplies the current bucket-scoped object payloads. Each
        record reference is recomputed and compared to the manifest's
        registered digest. The report enumerates which checks passed and
        the overall verification state. Missing records degrade
        completeness; mismatched digests fail verification.

        When ``record_payloads`` is ``None`` (the CLI default until the
        per-object-type loader registry lands), every record reports as
        unreachable and the bundle is classified as INCOMPLETE — the
        operator-honest baseline. Callers that already hold payloads in
        memory (test fixtures, end-to-end driver code) pass them
        explicitly.
        """
        if record_payloads is None:
            record_payloads = dict[tuple[str, str], bytes]()
        bundle = self.show(bucket_id=bucket_id, bundle_id=bundle_id)
        findings: list[EvidenceBundleCheckResult] = []

        findings.append(
            EvidenceBundleCheckResult(
                check=VerificationCheck.BUCKET_BINDING,
                passed=bundle.bucket_id == bucket_id,
                detail=f"manifest bucket={bundle.bucket_id!r}",
            ),
        )
        work_units = WorkUnitCatalogueRepository(bucket_id=bucket_id).load()
        work_unit_exists = work_units.get(bundle.work_unit_id) is not None
        findings.append(
            EvidenceBundleCheckResult(
                check=VerificationCheck.WORK_UNIT_BINDING,
                passed=work_unit_exists,
                detail=f"work_unit_id={bundle.work_unit_id!r}",
            ),
        )

        total = len(bundle.records)
        total_bytes = sum(record.payload_size_bytes for record in bundle.records)
        reachable, reachable_bytes, digest_passes, digest_failures = _scan_record_payloads(
            bundle.records,
            record_payloads,
        )
        completeness = _completeness_ratio(
            total=total,
            total_bytes=total_bytes,
            reachable=reachable,
            reachable_bytes=reachable_bytes,
        )
        findings.append(
            EvidenceBundleCheckResult(
                check=VerificationCheck.OBJECT_REACHABILITY,
                passed=reachable == total,
                detail=f"{reachable}/{total} reachable",
            ),
        )
        findings.append(
            EvidenceBundleCheckResult(
                check=VerificationCheck.RECORD_DIGESTS,
                passed=digest_passes == reachable and not digest_failures,
                detail=(
                    f"{digest_passes}/{reachable} digest matches"
                    if not digest_failures
                    else f"digest mismatch on: {digest_failures!r}"
                ),
            ),
        )

        expected_bundle_id = derive_bundle_id(
            bucket_id=bundle.bucket_id,
            work_unit_id=bundle.work_unit_id,
            manifest_version=bundle.manifest_version,
            records=bundle.records,
            calculation_revision_id=bundle.calculation_revision_id,
            filing_record_id=bundle.filing_record_id,
        )
        findings.append(
            EvidenceBundleCheckResult(
                check=VerificationCheck.MANIFEST_DIGEST,
                passed=expected_bundle_id == bundle.bundle_id,
                detail=f"expected {expected_bundle_id!r}, got {bundle.bundle_id!r}",
            ),
        )

        return EvidenceBundleVerificationReport(
            bundle_id=bundle.bundle_id,
            verification_state=_verification_state(
                all_passed=all(f.passed for f in findings),
                digest_failures=digest_failures,
                completeness=completeness,
            ),
            findings=tuple(findings),
            completeness_ratio=completeness,
        )

    def export(
        self,
        *,
        bucket_id: str,
        bundle_id: str,
        output_path: Path,
        record_payloads: Mapping[tuple[str, str], bytes] | None = None,
        force_incomplete: bool = False,
    ) -> Path:
        """Write a ZIP with each record file then manifest.json last.

        Runs verification first. On failed verification, refuses with
        :class:`EvidenceBundleVerificationError` unless ``force_incomplete``
        is True. Incomplete bundles require ``force_incomplete=True``;
        failed-verification bundles always refuse. The archive is an
        operator-directed plaintext export written to ``output_path``;
        it does not create or update encrypted bucket catalogue records.
        """
        if record_payloads is None:
            record_payloads = dict[tuple[str, str], bytes]()
        bundle = self.show(bucket_id=bucket_id, bundle_id=bundle_id)
        report = self.check(
            bucket_id=bucket_id,
            bundle_id=bundle.bundle_id,
            record_payloads=record_payloads,
        )
        if report.verification_state is BundleVerificationState.FAILED:
            raise EvidenceBundleVerificationError(
                translated_message="errors.refused.refused_evidence_bundle_verification",
                context={"bundle_id": bundle.bundle_id, "verification_state": report.verification_state.value},
            )
        if report.verification_state is BundleVerificationState.INCOMPLETE and not force_incomplete:
            raise EvidenceBundleVerificationError(
                translated_message="errors.refused.refused_evidence_bundle_verification",
                context={
                    "bundle_id": bundle.bundle_id,
                    "verification_state": report.verification_state.value,
                    "force_incomplete": force_incomplete,
                },
            )

        output_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_payload = bundle.model_dump_json(indent=2).encode(UTF_8_ENCODING)

        # Write records first; manifest.json LAST so a partial archive
        # never carries a manifest claiming records that aren't there.
        with zipfile.ZipFile(output_path, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
            for record in bundle.records:
                key = (record.object_type.value, record.object_id)
                if key not in record_payloads:
                    continue
                arcname = f"records/{record.object_type.value}/{record.object_id}.bin"
                archive.writestr(arcname, record_payloads[key])
            archive.writestr(_MANIFEST_FILENAME, manifest_payload)
        return output_path


__all__ = [
    "EvidenceBundleRepository",
    "EvidenceBundleService",
    "EvidenceBundleVerificationReport",
]
