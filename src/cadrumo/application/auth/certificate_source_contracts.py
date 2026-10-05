"""Closed request and result projection schemas for local certificate source operations."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from ...core.models import STRICT_FROZEN_CONFIG
from .models import CertificateSourceName
from .operator_results import (
    CertificateSourceCheckReport,
    CertificateSourceListResult,
    CertificateSourceMutationResult,
)
from .probes import PROBE_RESULTS_NEEDING_ATTENTION

CERTIFICATE_SOURCE_REGISTER_OPERATION_DEFINITION_ID = "auth.certificate.source.register"


CERTIFICATE_SOURCE_LIST_OPERATION_DEFINITION_ID = "auth.certificate.source.list"


CERTIFICATE_SOURCE_SELECT_OPERATION_DEFINITION_ID = "auth.certificate.source.select"


CERTIFICATE_SOURCE_REMOVE_OPERATION_DEFINITION_ID = "auth.certificate.source.remove"


CERTIFICATE_SOURCE_CHECK_OPERATION_DEFINITION_ID = "auth.certificate.source.check"


class CertificateSourceRegisterRequest(BaseModel):
    """Register or re-point one named source in the exact active profile."""

    model_config = STRICT_FROZEN_CONFIG

    profile_id: UUID
    name: CertificateSourceName
    certificate_path: Path
    friendly_name: str | None = Field(default=None, max_length=256)

    @field_validator("friendly_name")
    @classmethod
    def _normalize_friendly_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class CertificateSourceListRequest(BaseModel):
    """List source metadata from the exact active profile."""

    model_config = STRICT_FROZEN_CONFIG

    profile_id: UUID


class CertificateSourceSelectRequest(BaseModel):
    """Select one previously registered certificate source."""

    model_config = STRICT_FROZEN_CONFIG

    profile_id: UUID
    name: CertificateSourceName


class CertificateSourceRemoveRequest(BaseModel):
    """Remove one named source; an absent name remains an idempotent no-op."""

    model_config = STRICT_FROZEN_CONFIG

    profile_id: UUID
    name: CertificateSourceName


class CertificateSourceCheckRequest(BaseModel):
    """Check local health for every named source in the exact active profile."""

    model_config = STRICT_FROZEN_CONFIG

    profile_id: UUID


type CertificateSourceOperationRequest = (
    CertificateSourceRegisterRequest
    | CertificateSourceListRequest
    | CertificateSourceSelectRequest
    | CertificateSourceRemoveRequest
    | CertificateSourceCheckRequest
)


class CertificateSourceRegisterProjection(BaseModel):
    """Registered-source receipt bound to the terminal profile subject."""

    model_config = STRICT_FROZEN_CONFIG

    profile_id: UUID
    result: CertificateSourceMutationResult


class CertificateSourceListProjection(BaseModel):
    """Source inventory bound to the terminal profile subject."""

    model_config = STRICT_FROZEN_CONFIG

    profile_id: UUID
    result: CertificateSourceListResult

    @field_validator("result")
    @classmethod
    def _validate_inventory(cls, result: CertificateSourceListResult) -> CertificateSourceListResult:
        names = tuple(source.name for source in result.sources)
        active_names = tuple(source.name for source in result.sources if source.active)
        if names != tuple(sorted(names)) or len(set(names)) != len(names):
            raise ValueError("certificate source inventory is not canonically ordered")
        if active_names != ((result.active_source,) if result.active_source else ()):
            raise ValueError("certificate source inventory has an inconsistent active selection")
        return result


class CertificateSourceSelectProjection(BaseModel):
    """Selected-source receipt bound to the terminal profile subject."""

    model_config = STRICT_FROZEN_CONFIG

    profile_id: UUID
    result: CertificateSourceMutationResult


class CertificateSourceRemoveProjection(BaseModel):
    """Removal receipt bound to the terminal profile subject."""

    model_config = STRICT_FROZEN_CONFIG

    profile_id: UUID
    result: CertificateSourceMutationResult


class CertificateSourceCheckProjection(BaseModel):
    """Health report bound to the terminal profile subject."""

    model_config = STRICT_FROZEN_CONFIG

    profile_id: UUID
    result: CertificateSourceCheckReport

    @field_validator("result")
    @classmethod
    def _validate_report(cls, result: CertificateSourceCheckReport) -> CertificateSourceCheckReport:
        names = tuple(entry.name for entry in result.entries)
        active_names = tuple(entry.name for entry in result.entries if entry.active)
        expected_warnings = any(entry.result in PROBE_RESULTS_NEEDING_ATTENTION for entry in result.entries)
        if names != tuple(sorted(names)) or len(set(names)) != len(names):
            raise ValueError("certificate source health report is not canonically ordered")
        if len(active_names) > 1 or result.has_warnings is not expected_warnings:
            raise ValueError("certificate source health report has inconsistent summary facts")
        return result
