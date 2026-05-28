"""Evidence bundle service: build, verify, export, replay."""

from __future__ import annotations

import hashlib
import zipfile
from collections.abc import Mapping
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from ...core.config import Settings
from .._storage_paths import storage_path
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


class EvidenceBundleVerificationReport(BaseModel):
    """Outcome of a verification pass over a bundle."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    bundle_id: str = Field(min_length=64, max_length=64)
    verification_state: BundleVerificationState
    findings: tuple[EvidenceBundleCheckResult, ...] = Field(default_factory=tuple)
    completeness_ratio: float = Field(ge=0.0, le=1.0)


def _load(settings: Settings, bucket_id: str) -> list[EvidenceBundle]:
    path = storage_path(settings.aeat_audit_dir / "evidence-bundles", bucket_id)
    if not path.exists():
        return []
    return [
        EvidenceBundle.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _save(settings: Settings, bucket_id: str, bundles: list[EvidenceBundle]) -> None:
    path = storage_path(settings.aeat_audit_dir / "evidence-bundles", bucket_id)
    payload = "\n".join(b.model_dump_json() for b in bundles)
    if payload:
        payload += "\n"
    path.write_text(payload, encoding="utf-8")


def _hash_payload(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


class EvidenceBundleService:
    """Application service implementing the apex audit verb tree.

    Each method maps to one of the verbs in ``aeat app modelo audit``:
    ``build`` is the constructor side of ``add``-equivalent (audit bundles
    are produced by the file/verify path, not the operator). ``show``,
    ``check``, ``export``, ``replay`` are operator-facing.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        # `load_settings()` honours `override_settings`; bare `Settings()`
        # does not, so CLI tests overriding evidence-dir would otherwise
        # write into the project default.
        from ...core.config import load_settings as _load_settings
        self._settings = settings or _load_settings()

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
        """Build a new bundle from a mapping of (object_type, object_id) -> raw bytes."""
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
        bundles = _load(self._settings, bucket_id)
        bundles.append(bundle)
        _save(self._settings, bucket_id, bundles)
        return bundle

    def show(self, *, bucket_id: str, bundle_id: str) -> EvidenceBundle:
        for bundle in _load(self._settings, bucket_id):
            if bundle.bundle_id == bundle_id or bundle.bundle_id.startswith(bundle_id):
                return bundle
        raise EvidenceBundleNotFoundError(
            f"no evidence bundle matches {bundle_id!r} in bucket {bucket_id!r}",
            suggestion="aeat app modelo audit check",
        )

    def check(
        self,
        *,
        bucket_id: str,
        bundle_id: str,
        record_payloads: Mapping[tuple[str, str], bytes] | None = None,
    ) -> EvidenceBundleVerificationReport:
        """Re-verify a bundle by recomputing record digests from supplied payloads.

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
                f"refusing export of bundle {bundle.bundle_id!r}: verification failed",
                suggestion="aeat app modelo audit check",
            )
        if report.verification_state is BundleVerificationState.INCOMPLETE and not force_incomplete:
            raise EvidenceBundleVerificationError(
                f"refusing export of incomplete bundle {bundle.bundle_id!r} without --force-incomplete",
                suggestion="aeat app modelo audit export --force-incomplete",
            )

        output_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_payload = bundle.model_dump_json(indent=2).encode("utf-8")

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
        """
        return self.check(bucket_id=bucket_id, bundle_id=bundle_id, record_payloads=record_payloads)


__all__ = [
    "EvidenceBundleService",
    "EvidenceBundleVerificationReport",
]
