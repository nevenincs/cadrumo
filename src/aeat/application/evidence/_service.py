"""Evidence bundle service: build, verify, export, replay."""

from __future__ import annotations

import hashlib
import zipfile
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import ClassVar, override

from pydantic import BaseModel, ConfigDict, Field

from ...adapters.persistence.storage import (
    APPLICATION_EVIDENCE_BUNDLE_NAMESPACE,
)
from ...adapters.persistence.storage.envelope import SecureBoundRepository
from ...adapters.persistence.storage.runtime_repository import secure_object_repository_for_bucket
from ...core.config import Settings
from ...core.external_constants import UTF_8_ENCODING
from ._ids import BundleId
from ._models import (
    BundleVerificationState,
    EvidenceBundle,
    EvidenceBundleCheckResult,
    EvidenceBundleNotFoundError,
    EvidenceBundleVerificationError,
    EvidenceRecordRef,
    VerificationCheck,
    derive_bundle_id,
    utcnow,
)

_MANIFEST_VERSION = 1
_MANIFEST_FILENAME = "manifest.json"


class EvidenceBundleRepository(SecureBoundRepository[EvidenceBundle]):
    """Encrypted repository for bucket-local evidence bundle manifests."""

    namespace: ClassVar[str] = APPLICATION_EVIDENCE_BUNDLE_NAMESPACE.namespace
    sensitivity: ClassVar = APPLICATION_EVIDENCE_BUNDLE_NAMESPACE.sensitivity
    schema_version: ClassVar[int] = APPLICATION_EVIDENCE_BUNDLE_NAMESPACE.schema_version
    payload_type: ClassVar[type[BaseModel]] = EvidenceBundle

    @override
    def extract_identifier(self, payload: EvidenceBundle) -> str:
        """Return the stable storage key for an :class:`EvidenceBundle`."""
        return payload.bundle_id


class EvidenceBundleVerificationReport(BaseModel):
    """Outcome of a verification pass over a bundle."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    bundle_id: BundleId
    verification_state: BundleVerificationState
    findings: tuple[EvidenceBundleCheckResult, ...] = Field(default_factory=tuple)
    completeness_ratio: float = Field(ge=0.0, le=1.0)


def _hash_payload(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


class EvidenceBundleService:
    """Application service for the audit verb tree.

    Each method maps to one of the verbs in ``aeat app modelo audit``:
    ``build`` is the constructor side of ``add``-equivalent (audit bundles
    are produced by the file/verify path, not the operator). ``show``,
    ``check``, ``export``, ``replay`` are operator-facing.
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
        calculation_revision_id: str | None = None,
        filing_record_id: str | None = None,
        notes: str = "",
    ) -> EvidenceBundle:
        """Build a new bundle from a mapping of (object_type, object_id) -> raw bytes.

        Returns the persisted :class:`EvidenceBundle` with all record refs
        and provenance metadata populated.
        """
        from ...domain.buckets._event import BucketEventObjectType

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
            created_at=utcnow(),
            notes=notes,
        )
        self._repository_for(bucket_id).save(bundle)
        return bundle

    def show(self, *, bucket_id: str, bundle_id: str) -> EvidenceBundle:
        """Load a bundle by exact or prefix match of ``bundle_id``.

        Tries an exact ``repository.load`` first; falls back to a prefix
        scan over all records in the bucket. Raises
        :class:`EvidenceBundleNotFoundError` when nothing matches.

        Returns:
            :class:`EvidenceBundle`: The retrieved evidence bundle.
        """
        repository = self._repository_for(bucket_id)
        if bundle_id.strip():
            exact = repository.load(bundle_id)
            if exact is not None:
                return exact
        for bundle in repository.iter_records():
            if bundle.bundle_id == bundle_id or bundle.bundle_id.startswith(bundle_id):
                return bundle
        raise EvidenceBundleNotFoundError(
            translated_message="errors.refused.refused_evidence_bundle_not_found",
            context={"bundle_id": bundle_id, "bucket_id": bucket_id},
            suggestion="aeat app modelo audit check",
        )

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
            record_payloads = {}
        bundle = self.show(bucket_id=bucket_id, bundle_id=bundle_id)
        findings: list[EvidenceBundleCheckResult] = []

        findings.append(
            EvidenceBundleCheckResult(
                check=VerificationCheck.BUCKET_BINDING,
                passed=bundle.bucket_id == bucket_id,
                detail=f"manifest bucket={bundle.bucket_id!r}",
            ),
        )

        total = len(bundle.records)
        reachable = 0
        digest_passes = 0
        digest_failures: list[str] = []
        for record in bundle.records:
            key = (record.object_type.value, record.object_id)
            if key not in record_payloads:
                continue
            reachable += 1
            actual = _hash_payload(record_payloads[key])
            if actual == record.content_sha256:
                digest_passes += 1
            else:
                digest_failures.append(record.object_id)

        completeness = reachable / total if total else 1.0
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

        all_passed = all(f.passed for f in findings)
        if all_passed:
            state = BundleVerificationState.VERIFIED
        elif digest_failures:
            state = BundleVerificationState.FAILED
        elif completeness < 1.0:
            state = BundleVerificationState.INCOMPLETE
        else:
            state = BundleVerificationState.FAILED

        return EvidenceBundleVerificationReport(
            bundle_id=bundle.bundle_id,
            verification_state=state,
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
        failed-verification bundles always refuse.
        """
        if record_payloads is None:
            record_payloads = {}
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
                suggestion="aeat app modelo audit check",
            )
        if report.verification_state is BundleVerificationState.INCOMPLETE and not force_incomplete:
            raise EvidenceBundleVerificationError(
                translated_message="errors.refused.refused_evidence_bundle_verification",
                context={
                    "bundle_id": bundle.bundle_id,
                    "verification_state": report.verification_state.value,
                    "force_incomplete": force_incomplete,
                },
                suggestion="aeat app modelo audit export --force-incomplete",
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

    def replay(
        self,
        *,
        bucket_id: str,
        bundle_id: str,
        record_payloads: Mapping[tuple[str, str], bytes] | None = None,
    ) -> EvidenceBundleVerificationReport:
        """Evidence-case replay: re-verify the bundle against supplied payloads.

        Replay never contacts AEAT and never performs live submission.
        Behaviorally this is ``check`` with a different verb name and
        intent: ``check`` is operator diagnostics, ``replay`` is the
        forensic verb invoked when reproducing a historical filing for
        audit handoff.

        Returns an :class:`EvidenceBundleVerificationReport`.
        """
        return self.check(bucket_id=bucket_id, bundle_id=bundle_id, record_payloads=record_payloads)


__all__ = [
    "EvidenceBundleRepository",
    "EvidenceBundleService",
    "EvidenceBundleVerificationReport",
]
