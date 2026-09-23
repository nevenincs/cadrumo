"""Secure admission and resolution of ordinary Modelo 390 applicability evidence."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel, Field, ValidationError, model_validator

from ...core.hex import Hex64Str
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.period import Period
from ...core.time.clock import now as _utc_now
from ...core.time.utc import UtcInstant, validate_utc_aware
from ...domain.attachments.enums import AttachmentKind, AttachmentSource
from ...domain.attachments.errors import AttachmentValidationError
from ...domain.attachments.m303_filing_evidence import (
    M303Exonerado390ApplicabilityAssertion,
    M303Exonerado390ApplicabilityAttestation,
    M303Exonerado390ApplicabilityProfileWitness,
    parse_m303_exonerado_390_applicability_attestation,
)
from ...domain.attachments.protocols import AttachmentStoreProtocol
from ...domain.attachments.service import AttachmentBytesContent, AttachmentIngestionRequest, add_attachment
from ...domain.filing_evidence import FilingEvidenceReference
from .action_errors import M303ApplicabilityAttestationUnadmissibleError
from .m303_ordinary_evidence_coordinate import ordinary_m303_evidence_coordinate_supported
from .profile_readiness_gate import load_modelo_work_profile

if TYPE_CHECKING:
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation
    from .work_profile import ModeloWorkProfile

_ATTESTATION_MIME_TYPE = "application/vnd.cadrumo.m303-exonerado-390-applicability+json"
_ATTESTATION_REFERENCE_PREFIX = "attachment:"
_ATTESTATION_SOURCE_COMMAND = "application.modelo.m303_exonerado_390_applicability_attestation"


class M303Exonerado390ApplicabilityAttestationRequest(BaseModel):
    """The operator-owned facts needed to attest ordinary M303 non-applicability."""

    model_config = STRICT_FROZEN_CONFIG

    filing_year: int = Field(ge=1)
    period: Period
    asserted_value: M303Exonerado390ApplicabilityAssertion
    observed_at: UtcInstant

    @model_validator(mode="after")
    def _has_one_filing_coordinate(self) -> M303Exonerado390ApplicabilityAttestationRequest:
        if self.period.filing_year != self.filing_year:
            raise AttachmentValidationError("Modelo 390 applicability request period disagrees with filing year")
        return self


class M303Exonerado390ApplicabilityAttestationAdmission(BaseModel):
    """Safe attachment identity returned after encrypted attestation admission."""

    model_config = STRICT_FROZEN_CONFIG

    attachment_id: Hex64Str
    sha256: Hex64Str

    @model_validator(mode="after")
    def _attachment_id_matches_digest(self) -> M303Exonerado390ApplicabilityAttestationAdmission:
        if self.attachment_id != self.sha256:
            raise AttachmentValidationError("Modelo 390 applicability attachment identity does not match its digest")
        return self

    def filing_evidence_reference(self) -> FilingEvidenceReference:
        """Construct the internal nominal reference without exposing its grammar to a frontend."""
        return _filing_evidence_reference(self.attachment_id, self.sha256)


def admit_m303_exonerado_390_applicability_attestation(
    *,
    bucket_id: str,
    request: M303Exonerado390ApplicabilityAttestationRequest,
    actor: str,
    operation: PinnedAuthorityOperation,
    store: AttachmentStoreProtocol,
    profile: ModeloWorkProfile | None = None,
    clock: Callable[[], datetime] = _utc_now,
) -> M303Exonerado390ApplicabilityAttestationAdmission:
    """Admit one canonical ordinary-M303 assertion into encrypted attachment custody."""
    _require_ordinary_not_applicable_request(request, operation=operation)
    profile = _current_profile(bucket_id=bucket_id, operation=operation, profile=profile)
    captured_at = validate_utc_aware(clock())
    _require_observation_timing(
        observed_at=request.observed_at,
        captured_at=captured_at,
        period=request.period,
        current_at=captured_at,
    )
    attestation = M303Exonerado390ApplicabilityAttestation(
        schema_version=1,
        role="m303_exonerado_390_applicability",
        asserted_value=request.asserted_value,
        filing_year=request.filing_year,
        period=request.period,
        observed_at=request.observed_at,
        profile_witness=M303Exonerado390ApplicabilityProfileWitness.from_profile_record(profile.record),
    )
    payload = attestation.canonical_json_bytes()
    attachment = add_attachment(
        store,
        content=AttachmentBytesContent(data=payload),
        request=AttachmentIngestionRequest(
            kind=AttachmentKind.M303_EXONERADO_390_APPLICABILITY_ATTESTATION,
            source=AttachmentSource.INLINE,
            source_reference=_attestation_source_reference(request),
            mime_type=_ATTESTATION_MIME_TYPE,
            captured_at=captured_at,
            bucket_id=bucket_id,
            captured_by=actor,
            source_command=_ATTESTATION_SOURCE_COMMAND,
        ),
    )
    return M303Exonerado390ApplicabilityAttestationAdmission(
        attachment_id=attachment.attachment_id,
        sha256=attachment.sha256,
    )


def resolve_m303_exonerado_390_not_applicable_attestation(
    *,
    bucket_id: str,
    filing_year: int,
    period: Period,
    evidence_reference: FilingEvidenceReference,
    operation: PinnedAuthorityOperation,
    store: AttachmentStoreProtocol,
    profile: ModeloWorkProfile | None = None,
    clock: Callable[[], datetime] = _utc_now,
) -> FilingEvidenceReference:
    """Resolve one current, custody-verified ordinary M303 non-applicability reference."""
    _require_ordinary_coordinate(filing_year=filing_year, period=period, operation=operation)
    profile = _current_profile(bucket_id=bucket_id, operation=operation, profile=profile)
    attachment_id, sha256 = _parse_filing_evidence_reference(evidence_reference)
    attachment = store.load_manifest(attachment_id)
    if attachment.sha256 != sha256 or attachment.bucket_id != bucket_id:
        raise AttachmentValidationError("Modelo 390 applicability evidence does not belong to this profile bucket")
    if (
        attachment.kind is not AttachmentKind.M303_EXONERADO_390_APPLICABILITY_ATTESTATION
        or attachment.source is not AttachmentSource.INLINE
        or attachment.mime_type != _ATTESTATION_MIME_TYPE
    ):
        raise AttachmentValidationError("attachment is not Modelo 390 applicability evidence")
    store.verify_blob(attachment.attachment_id)
    current_at = validate_utc_aware(clock())
    attestation = _parse_attachment_attestation(
        attachment_id=attachment.attachment_id,
        store=store,
    )
    _require_matching_attestation(
        attestation=attestation,
        filing_year=filing_year,
        period=period,
        profile_witness=M303Exonerado390ApplicabilityProfileWitness.from_profile_record(profile.record),
        captured_at=attachment.captured_at,
        current_at=current_at,
    )
    _require_no_conflicting_attestation(
        store=store,
        bucket_id=bucket_id,
        filing_year=filing_year,
        period=period,
    )
    return _filing_evidence_reference(attachment.attachment_id, attachment.sha256)


def m303_exonerado_390_filing_evidence_reference(*, attachment_id: str, sha256: str) -> FilingEvidenceReference:
    """Validate split CLI-safe identifiers and construct the internal reference."""
    try:
        admission = M303Exonerado390ApplicabilityAttestationAdmission(
            attachment_id=attachment_id,
            sha256=sha256,
        )
    except (ValidationError, AttachmentValidationError) as exc:
        raise M303ApplicabilityAttestationUnadmissibleError(
            "Modelo 390 applicability attachment identity is invalid",
            context={"reason": "malformed_identity"},
        ) from exc
    return admission.filing_evidence_reference()


def _current_profile(
    *,
    bucket_id: str,
    operation: PinnedAuthorityOperation,
    profile: ModeloWorkProfile | None,
) -> ModeloWorkProfile:
    if profile is None:
        profile = load_modelo_work_profile(
            bucket_id=bucket_id,
            profile_decode_context=operation.profile_decode_context(),
        )
    try:
        bucket_identity = UUID(bucket_id)
    except ValueError as exc:
        raise AttachmentValidationError("Modelo 390 applicability evidence bucket is invalid") from exc
    if profile is None or str(profile.record.profile_id) != str(bucket_identity):
        raise AttachmentValidationError("Modelo 390 applicability evidence requires the authenticated current profile")
    return profile


def _require_ordinary_not_applicable_request(
    request: M303Exonerado390ApplicabilityAttestationRequest, *, operation: PinnedAuthorityOperation
) -> None:
    _require_ordinary_coordinate(filing_year=request.filing_year, period=request.period, operation=operation)
    if request.asserted_value is M303Exonerado390ApplicabilityAssertion.APPLICABLE:
        raise AttachmentValidationError("applicable Modelo 390 evidence is not supported by the ordinary path")


def _require_ordinary_coordinate(*, filing_year: int, period: Period, operation: PinnedAuthorityOperation) -> None:
    if not ordinary_m303_evidence_coordinate_supported(filing_year=filing_year, period=period, operation=operation):
        raise AttachmentValidationError(
            "Modelo 390 applicability evidence supports only a quarterly Modelo 303 whose selected record "
            "design declares the ordinary evidence header fields"
        )


def _require_observation_timing(
    *,
    observed_at: datetime,
    captured_at: datetime,
    period: Period,
    current_at: datetime,
) -> None:
    if observed_at > current_at or observed_at > captured_at or observed_at.date() < period.end_date:
        raise AttachmentValidationError("Modelo 390 applicability observation timing is invalid")


def _attestation_source_reference(request: M303Exonerado390ApplicabilityAttestationRequest) -> str:
    return f"m303-exonerado-390-applicability:{request.filing_year}:{request.period.registry_token}"


def _filing_evidence_reference(attachment_id: str, sha256: str) -> FilingEvidenceReference:
    return FilingEvidenceReference(reference=f"{_ATTESTATION_REFERENCE_PREFIX}{attachment_id}:{sha256}")


def _parse_filing_evidence_reference(reference: FilingEvidenceReference) -> tuple[str, str]:
    prefix, separator, payload = reference.reference.partition(":")
    if prefix != _ATTESTATION_REFERENCE_PREFIX.removesuffix(":") or not separator:
        raise AttachmentValidationError("Modelo 390 applicability evidence reference is invalid")
    attachment_id, separator, sha256 = payload.partition(":")
    if not separator or attachment_id != sha256:
        raise AttachmentValidationError("Modelo 390 applicability evidence reference is invalid")
    return attachment_id, sha256


def _parse_attachment_attestation(
    *, attachment_id: str, store: AttachmentStoreProtocol
) -> M303Exonerado390ApplicabilityAttestation:
    return parse_m303_exonerado_390_applicability_attestation(store.read_bytes(attachment_id))


def _require_matching_attestation(
    *,
    attestation: M303Exonerado390ApplicabilityAttestation,
    filing_year: int,
    period: Period,
    profile_witness: M303Exonerado390ApplicabilityProfileWitness,
    captured_at: datetime,
    current_at: datetime,
) -> None:
    if (
        attestation.asserted_value is not M303Exonerado390ApplicabilityAssertion.NOT_APPLICABLE
        or attestation.filing_year != filing_year
        or attestation.period != period
        or attestation.profile_witness != profile_witness
    ):
        raise AttachmentValidationError("Modelo 390 applicability evidence does not match this filing coordinate")
    _require_observation_timing(
        observed_at=attestation.observed_at,
        captured_at=captured_at,
        period=period,
        current_at=current_at,
    )


def _require_no_conflicting_attestation(
    *,
    store: AttachmentStoreProtocol,
    bucket_id: str,
    filing_year: int,
    period: Period,
) -> None:
    values: set[M303Exonerado390ApplicabilityAssertion] = set()
    for attachment in store.iter_manifests():
        if (
            attachment.bucket_id != bucket_id
            or attachment.kind is not AttachmentKind.M303_EXONERADO_390_APPLICABILITY_ATTESTATION
        ):
            continue
        store.verify_blob(attachment.attachment_id)
        attestation = _parse_attachment_attestation(attachment_id=attachment.attachment_id, store=store)
        if attestation.filing_year == filing_year and attestation.period == period:
            values.add(attestation.asserted_value)
    if values != {M303Exonerado390ApplicabilityAssertion.NOT_APPLICABLE}:
        raise AttachmentValidationError("Modelo 390 applicability evidence has conflicting assertions")


__all__ = [
    "M303Exonerado390ApplicabilityAttestationAdmission",
    "M303Exonerado390ApplicabilityAttestationRequest",
    "admit_m303_exonerado_390_applicability_attestation",
    "m303_exonerado_390_filing_evidence_reference",
    "resolve_m303_exonerado_390_not_applicable_attestation",
]
