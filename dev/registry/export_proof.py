"""Two-channel proof contracts for the canonical filing export writer."""

from __future__ import annotations

from enum import StrEnum
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, model_validator

from cadrumo.core.models import STRICT_FROZEN_CONFIG

from ._filing_export_proof_contracts import (
    FilingExportConformanceReceipt,
    FilingExportConformanceRenderInputs,
    FilingExportConformanceVectorEvidence,
    FilingExportDictionaryValue,
    FilingExportGeneratedOutput,
    FilingExportOfficialProbe,
    FilingExportProof,
    FilingExportProofCoordinate,
    FilingExportProofToken,
    FilingExportPublicProvenance,
    FilingExportSecureCustodyRecord,
    FilingExportSecureReplayEvidence,
    FilingExportSecureReplayReceipt,
    FilingExportSourcePinnedProbeExpectation,
)

_Token = FilingExportProofToken

FilingExportConformanceReceipt.__module__ = __name__
FilingExportConformanceRenderInputs.__module__ = __name__
FilingExportConformanceVectorEvidence.__module__ = __name__
FilingExportDictionaryValue.__module__ = __name__
FilingExportGeneratedOutput.__module__ = __name__
FilingExportOfficialProbe.__module__ = __name__
FilingExportProof.__module__ = __name__
FilingExportProofCoordinate.__module__ = __name__
FilingExportPublicProvenance.__module__ = __name__
FilingExportSecureCustodyRecord.__module__ = __name__
FilingExportSecureReplayEvidence.__module__ = __name__
FilingExportSecureReplayReceipt.__module__ = __name__
FilingExportSourcePinnedProbeExpectation.__module__ = __name__


class FilingExportProofChannel(StrEnum):
    """Mandatory proof channel that a refusal prevents from satisfying."""

    CONFORMANCE = "conformance"
    SECURE_REPLAY = "secure_replay"


class FilingExportProofRefusalReason(StrEnum):
    """Application-local fail-closed proof refusal taxonomy."""

    EVIDENCE_MISSING = "evidence_missing"
    AUTHORITY_UNAVAILABLE = "authority_unavailable"
    IDENTITY_MISMATCH = "identity_mismatch"
    PROVENANCE_MISMATCH = "provenance_mismatch"
    CANONICAL_WRITER_FAILED = "canonical_writer_failed"
    CUSTODY_FAILED = "custody_failed"
    PROOF_VALIDATION_FAILED = "proof_validation_failed"


class FilingExportProofRefusal(BaseModel):
    """Typed per-channel reason a complete proof cannot be issued."""

    model_config = STRICT_FROZEN_CONFIG

    coordinate: FilingExportProofCoordinate
    channel: FilingExportProofChannel
    reason: FilingExportProofRefusalReason
    authority_id: _Token | None = None


class FilingExportProofAssessment(BaseModel):
    """Exactly one complete proof or one-or-more explicit refusals."""

    model_config = STRICT_FROZEN_CONFIG

    coordinate: FilingExportProofCoordinate
    proof: FilingExportProof | None = None
    refusals: tuple[FilingExportProofRefusal, ...] = ()

    @model_validator(mode="after")
    def _require_proof_xor_refusals(self) -> FilingExportProofAssessment:
        if (self.proof is None) == (not self.refusals):
            raise ValueError("filing export assessment requires proof xor refusals")
        if self.proof is not None and self.proof.coordinate != self.coordinate:
            raise ValueError("filing export assessment proof must match its coordinate")
        if any(refusal.coordinate != self.coordinate for refusal in self.refusals):
            raise ValueError("filing export assessment refusals must match its coordinate")
        channels = tuple(refusal.channel for refusal in self.refusals)
        if len(channels) != len(set(channels)):
            raise ValueError("filing export assessment permits at most one refusal per channel")
        return self


@runtime_checkable
class FilingExportProofAuthority(Protocol):
    """Composite authority consumed by dynamic release assessment."""

    def assess_for(self, coordinate: FilingExportProofCoordinate) -> FilingExportProofAssessment:
        """Return complete two-channel proof or explicit per-channel refusal."""
        ...


__all__ = [
    "FilingExportConformanceReceipt",
    "FilingExportConformanceRenderInputs",
    "FilingExportConformanceVectorEvidence",
    "FilingExportDictionaryValue",
    "FilingExportGeneratedOutput",
    "FilingExportOfficialProbe",
    "FilingExportProof",
    "FilingExportProofAssessment",
    "FilingExportProofAuthority",
    "FilingExportProofChannel",
    "FilingExportProofCoordinate",
    "FilingExportProofRefusal",
    "FilingExportProofRefusalReason",
    "FilingExportPublicProvenance",
    "FilingExportSecureCustodyRecord",
    "FilingExportSecureReplayEvidence",
    "FilingExportSecureReplayReceipt",
    "FilingExportSourcePinnedProbeExpectation",
]
