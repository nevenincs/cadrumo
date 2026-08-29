"""Review-package build and integrity verification for accountant handoff.

A review package is a shareable, checksum-verifiable ZIP archive assembled
from an already-verified or filed :class:`~domain.modelos.CalculationRevision`:
the fichero-BOE draft export bytes, the revision's typed casilla observations
(regulatory grounding included), its bundled ledger filing evidence (when
present), and a small package-info descriptor binding everything to the
source work unit / bucket / modelo / period.

This module builds and verifies review packages. It reuses the corpus-bundle
checksum-manifest primitive (:func:`~core.corpus_manifest.build_corpus_bundle`
/ :func:`~core.corpus_manifest.verify_corpus_bundle`) rather than
re-deriving SHA-256 bundling logic: a review package is, mechanically, a
:class:`~core.corpus_manifest.CorpusManifest`-checksummed zip whose
members happen to be filing artefacts instead of corpus reference files.

Cryptographic signing (ed25519 sender/recipient identity) and the
counter-signed accountant feedback-package round trip are explicitly OUT OF
SCOPE for this module; :func:`verify_review_package` is an INTEGRITY check
only (did every member arrive byte-for-byte as built), not an authenticity
check (who built it). A future slice adds signing and the counter-sign
receipt workflow on top of the manifest this module produces.

The package is a plaintext operator-directed handoff artefact — the operator
explicitly requested a shareable export, mirroring the existing
:meth:`~application.evidence.EvidenceBundleService.export` and
:func:`~application.modelo.export_modelo_revision` plaintext-export
exceptions. Nothing here mutates encrypted bucket state or persists a new
catalogue record; the ZIP is written directly to the caller-supplied path.

See Also:
    :func:`~application.modelo.export_modelo_revision`:
        Produces the fichero-BOE draft bytes bundled into the package.
    :class:`~domain.modelos.LedgerFilingEvidence`:
        The bundled ledger fact basis included when present on the revision.
    :func:`~core.corpus_manifest.build_corpus_bundle`:
        The reused checksum-manifest zip-build primitive.
    :func:`~core.corpus_manifest.verify_corpus_bundle`:
        The reused checksum-manifest zip-verify primitive.
"""

from __future__ import annotations

import tempfile
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, Field

from ...core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core import Period
from ...core.corpus_manifest import (
    CorpusBundleError,
    CorpusManifestTamperError,
    build_corpus_bundle,
    verify_corpus_bundle,
)
from ...core.errors import CadrumoError
from ...core.external_constants import UTF_8_ENCODING
from ...core.filing_year import FilingYear
from ...core.identity import BucketId, CalculationRevisionId, WorkUnitId
from ...core.time import now as _utc_now
from ...domain.modelos import WorkUnit
from ...domain.modelos.calculation_revision import CURRENT_SEALED_REVISION_STATES, CalculationRevision

#: Wire-format version of the review-package descriptor. Bumped when the
#: package-info schema changes shape.
_PACKAGE_INFO_VERSION = 1

#: Canonical member names inside every review package. Fixed so a receiving
#: side (a future counter-sign import verb) can address members by name
#: rather than re-deriving them from the manifest.
_PACKAGE_INFO_MEMBER = "package-info.json"
_REVISION_MEMBER = "revision.json"
_EVIDENCE_MEMBER = "evidence.json"
_DRAFT_MEMBER = "draft.fichero-boe"

#: Revision states eligible for review-package build. A draft that has not
#: yet reached verified-complete has no filing-grade grounding to share; a
#: superseded revision is stale and must not be handed to an accountant as
#: current.


class ReviewPackageError(CadrumoError):
    """Base error for review-package build/verify failures."""


class ReviewPackageRevisionStateError(ReviewPackageError):
    """Raised when the source revision is not eligible for a review package.

    Eligible states are ``VERIFICADO_COMPLETO`` and ``PRESENTADO`` (see
    :data:`CURRENT_SEALED_REVISION_STATES`): a review package shares a filing-grade
    figure with an accountant, so a bare draft or a superseded revision is
    refused before any bytes are written.
    """


class ReviewPackageIntegrityError(ReviewPackageError):
    """Raised when a review package fails checksum-manifest verification.

    Wraps the underlying :class:`~core.corpus_manifest.CorpusBundleError`
    family (missing/unexpected/mismatched members, manifest tamper, or a
    structurally invalid archive) behind one review-package-scoped error so
    callers do not need to import the corpus-manifest error hierarchy.
    """


class ReviewPackageManifest(BaseModel):
    """Package-info descriptor embedded in every review package as JSON.

    Distinct from the reused :class:`~core.corpus_manifest.CorpusManifest`
    (which only knows file names, sizes, and digests): this descriptor
    carries the review-domain identity — which work unit, calculation
    revision, bucket, modelo, and period the package represents — so a
    receiving side can address the package without re-parsing the fichero
    bytes.
    """

    model_config = _STRICT_FROZEN

    package_info_version: int = Field(default=_PACKAGE_INFO_VERSION, ge=1)
    bucket_id: BucketId
    work_unit_id: WorkUnitId
    calculation_revision_id: CalculationRevisionId
    modelo: str = Field(min_length=1, max_length=8)
    filing_year: FilingYear
    period: Period
    revision_state: str = Field(min_length=1)
    has_ledger_evidence: bool
    built_at: datetime
    built_by: str = Field(min_length=1, max_length=128)
    notes: str = Field(default="", max_length=2000)


class ReviewPackageBuildResult(BaseModel):
    """Receipt produced by :func:`build_review_package`."""

    model_config = _STRICT_FROZEN

    output_path: Path
    manifest: ReviewPackageManifest
    corpus_root_name: str = Field(min_length=1)
    member_count: int = Field(ge=1)


class ReviewPackageVerification(BaseModel):
    """Outcome of :func:`verify_review_package`.

    ``missing`` / ``unexpected`` / ``mismatched`` mirror
    :class:`~core.corpus_manifest.CorpusBundleVerification` exactly (the
    review package's checksum layer IS a corpus bundle); ``manifest`` is the
    review-specific :class:`ReviewPackageManifest` recovered from the
    package's ``package-info.json`` member once the archive is confirmed
    clean enough to read it.
    """

    model_config = _STRICT_FROZEN

    manifest: ReviewPackageManifest
    missing: tuple[str, ...] = Field(default=())
    unexpected: tuple[str, ...] = Field(default=())
    mismatched: tuple[str, ...] = Field(default=())

    @property
    def is_clean(self) -> bool:
        """Return ``True`` iff every archived member matches its checksum record."""
        return not (self.missing or self.unexpected or self.mismatched)


def build_review_package(
    *,
    revision: CalculationRevision,
    work_unit: WorkUnit,
    draft_bytes: bytes,
    output_path: Path,
    built_by: str,
    notes: str = "",
    generated_at: datetime | None = None,
) -> ReviewPackageBuildResult:
    """Assemble a shareable, checksum-verifiable review package ZIP.

    ``revision`` must be in a filing-grade state (``VERIFICADO_COMPLETO`` or
    ``PRESENTADO``); see :data:`CURRENT_SEALED_REVISION_STATES`. ``work_unit`` is
    the revision's parent (carries ``bucket_id`` / ``modelo`` / ``filing_year``
    / ``period``, which :class:`CalculationRevision` itself does not store);
    the caller must confirm ``work_unit.work_unit_id == revision.work_unit_id``
    before calling — this function trusts that binding rather than
    re-resolving it, keeping this module free of a catalogue-repository
    dependency. ``draft_bytes`` is the already-rendered fichero-BOE artefact
    (the caller obtains this from
    :func:`~application.modelo.export_modelo_revision`, which owns every
    export-time safety gate — evidence completeness, cross-period clean
    state, IVA wallet reconciliation — so this function does not re-validate
    export eligibility beyond the revision-state check above).

    The package bundles four members under a checksum manifest built by
    :func:`~core.corpus_manifest.build_corpus_bundle` (reused verbatim,
    not re-derived):

    * ``draft.fichero-boe`` — the rendered filing artefact bytes.
    * ``revision.json`` — the full :class:`CalculationRevision`, including
      its typed ``observations`` (legal_refs / source_refs grounding for
      every casilla).
    * ``evidence.json`` — the revision's bundled
      :class:`~domain.modelos.LedgerFilingEvidence` when present, or an
      explicit ``{"present": false}`` marker when the revision carries no
      ledger evidence (a non-ledger modelo, or a manual-only filing).
    * ``package-info.json`` — the :class:`ReviewPackageManifest` descriptor.

    Members are written to a temporary staging directory then packed with
    :func:`~core.corpus_manifest.build_corpus_bundle`, which itself
    writes atomically (temp-file-then-rename) so a build failure never
    leaves a partial package at ``output_path``. The staging directory is a
    sibling of ``output_path`` (``dir=output_path.parent``), never the
    OS-shared temp directory: it holds the rendered fichero-BOE draft plus
    the revision's typed observations and bundled ledger evidence in
    plaintext for the few milliseconds the archive build takes, and a
    world-shared temp location is not an acceptable home for that
    (``sensitive-financial-data-secure-storage-only``).

    Raises:
        ReviewPackageRevisionStateError: If ``revision.state`` is not in
            :data:`CURRENT_SEALED_REVISION_STATES`.
        ReviewPackageError: If ``work_unit.work_unit_id`` does not match
            ``revision.work_unit_id``.
    """
    if work_unit.work_unit_id != revision.work_unit_id:
        raise ReviewPackageError(
            translated_message="application.modelo.errors.review_package_generic",
            context={
                "work_unit_id": work_unit.work_unit_id,
                "revision_work_unit_id": revision.work_unit_id,
            },
        )
    if revision.state not in CURRENT_SEALED_REVISION_STATES:
        raise ReviewPackageRevisionStateError(
            translated_message="application.modelo.errors.review_package_revision_state",
            context={
                "calculation_revision_id": revision.calculation_revision_id,
                "state": revision.state.value,
                "eligible_states": ", ".join(sorted(s.value for s in CURRENT_SEALED_REVISION_STATES)),
            },
        )

    built_at = generated_at or _utc_now()
    manifest = ReviewPackageManifest(
        bucket_id=work_unit.bucket_id,
        work_unit_id=work_unit.work_unit_id,
        calculation_revision_id=revision.calculation_revision_id,
        modelo=str(work_unit.modelo),
        filing_year=work_unit.filing_year,
        period=work_unit.period,
        revision_state=revision.state.value,
        has_ledger_evidence=revision.ledger_filing_evidence is not None,
        built_at=built_at,
        built_by=built_by,
        notes=notes,
    )

    evidence_payload = (
        revision.ledger_filing_evidence.model_dump_json(indent=2)
        if revision.ledger_filing_evidence is not None
        else '{"present": false}'
    )

    # Pin staging beside the operator-chosen destination rather than the
    # OS-shared temp directory: the members below are plaintext filing
    # evidence, and the default ``tempfile`` location is not a sanctioned
    # home for that (``sensitive-financial-data-secure-storage-only``).
    # ``mkdir`` runs before the ``TemporaryDirectory`` call because the
    # latter requires ``dir`` to already exist; a destination whose parent
    # cannot be created (permission denied, a path component is a file, disk
    # full) refuses loudly here rather than silently falling back to
    # ``tempfile.gettempdir()``.
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="cadrumo-review-package-", dir=output_path.parent) as staging_name:
        staging_root = Path(staging_name)
        (staging_root / _DRAFT_MEMBER).write_bytes(draft_bytes)
        (staging_root / _REVISION_MEMBER).write_text(
            revision.model_dump_json(indent=2),
            encoding=UTF_8_ENCODING,
            newline="\n",
        )
        (staging_root / _EVIDENCE_MEMBER).write_text(evidence_payload, encoding=UTF_8_ENCODING, newline="\n")
        (staging_root / _PACKAGE_INFO_MEMBER).write_text(
            manifest.model_dump_json(indent=2),
            encoding=UTF_8_ENCODING,
            newline="\n",
        )
        corpus_root_name = f"review-package:{revision.calculation_revision_id[:16]}"
        corpus_manifest = build_corpus_bundle(
            staging_root,
            corpus_root_name=corpus_root_name,
            output_path=output_path,
            generated_at=built_at,
        )

    return ReviewPackageBuildResult(
        output_path=output_path,
        manifest=manifest,
        corpus_root_name=corpus_root_name,
        member_count=len(corpus_manifest.entries),
    )


def verify_review_package(package_path: Path) -> ReviewPackageVerification:
    """Verify a review package's checksum manifest and recover its descriptor.

    Delegates the checksum layer entirely to
    :func:`~core.corpus_manifest.verify_corpus_bundle` (no hashing logic
    is re-derived here). When the archive is clean, the embedded
    ``package-info.json`` member is loaded and validated into a
    :class:`ReviewPackageManifest`. A dirty archive still returns a best-effort
    manifest recovery when ``package-info.json`` itself matches its checksum
    record (so the caller can report WHICH package failed even when some
    other member is missing or mismatched); if the descriptor itself cannot
    be recovered, verification fails loudly rather than fabricating a
    manifest.

    This is an INTEGRITY check only: it confirms every archived member
    matches the manifest byte-for-byte. It makes no claim about WHO built the
    package (that is the deferred cryptographic-signing slice).

    Raises:
        FileNotFoundError: If ``package_path`` does not exist.
        ReviewPackageIntegrityError: If the archive is not a valid zip, the
            embedded corpus manifest is absent/structurally invalid/tampered,
            or the ``package-info.json`` member cannot be recovered.
    """
    try:
        result = verify_corpus_bundle(package_path)
    except (CorpusBundleError, CorpusManifestTamperError) as exc:
        raise ReviewPackageIntegrityError(
            translated_message="application.modelo.errors.review_package_integrity",
            context={"package_path": str(package_path), "detail": str(exc)},
        ) from exc

    manifest = _recover_package_manifest(
        package_path,
        result_missing=result.missing,
        result_mismatched=result.mismatched,
    )

    return ReviewPackageVerification(
        manifest=manifest,
        missing=tuple(sorted(m for m in result.missing if m != _PACKAGE_INFO_MEMBER)),
        unexpected=result.unexpected,
        mismatched=tuple(sorted(m for m in result.mismatched if m != _PACKAGE_INFO_MEMBER)),
    )


def _recover_package_manifest(
    package_path: Path,
    *,
    result_missing: tuple[str, ...],
    result_mismatched: tuple[str, ...],
) -> ReviewPackageManifest:
    """Load and validate the embedded ``package-info.json`` descriptor.

    Raises :class:`ReviewPackageIntegrityError` when the descriptor member is
    itself missing, mismatched, or structurally invalid — the descriptor is
    the one member verification cannot proceed without.
    """
    import json
    import zipfile

    from pydantic import ValidationError

    if _PACKAGE_INFO_MEMBER in result_missing or _PACKAGE_INFO_MEMBER in result_mismatched:
        raise ReviewPackageIntegrityError(
            translated_message="application.modelo.errors.review_package_integrity",
            context={
                "package_path": str(package_path),
                "detail": f"embedded descriptor {_PACKAGE_INFO_MEMBER!r} is missing or checksum-mismatched",
            },
        )
    try:
        with zipfile.ZipFile(package_path, mode="r") as archive:
            raw = archive.read(_PACKAGE_INFO_MEMBER)
        # ``model_validate_json`` (not ``model_validate`` over ``json.loads``
        # output) so pydantic's own JSON-mode datetime/period parsing applies;
        # the strict frozen config used across this module rejects a bare ISO
        # datetime *string* handed to ``model_validate`` via a plain dict.
        return ReviewPackageManifest.model_validate_json(raw)
    except (KeyError, zipfile.BadZipFile, json.JSONDecodeError, ValidationError) as exc:
        raise ReviewPackageIntegrityError(
            translated_message="application.modelo.errors.review_package_integrity",
            context={"package_path": str(package_path), "detail": str(exc)},
        ) from exc


def assert_review_package_verifies(package_path: Path) -> ReviewPackageManifest:
    """Verify ``package_path`` and raise on any drift; return its descriptor on success.

    Mirrors :func:`~core.corpus_manifest.assert_corpus_bundle_verifies`
    for the review-package surface: the operator-facing assertion a receiving
    side calls before trusting a handed-over package.
    """
    verification = verify_review_package(package_path)
    if not verification.is_clean:
        raise ReviewPackageIntegrityError(
            translated_message="application.modelo.errors.review_package_integrity",
            context={
                "package_path": str(package_path),
                "detail": (
                    f"missing={list(verification.missing)} "
                    f"unexpected={list(verification.unexpected)} "
                    f"mismatched={list(verification.mismatched)}"
                ),
                "missing": ", ".join(verification.missing),
                "unexpected": ", ".join(verification.unexpected),
                "mismatched": ", ".join(verification.mismatched),
            },
        )
    return verification.manifest


__all__ = [
    "ReviewPackageBuildResult",
    "ReviewPackageError",
    "ReviewPackageIntegrityError",
    "ReviewPackageManifest",
    "ReviewPackageRevisionStateError",
    "ReviewPackageVerification",
    "assert_review_package_verifies",
    "build_review_package",
    "verify_review_package",
]
