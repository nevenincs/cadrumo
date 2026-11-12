"""Capabilities the pension contribution certificate operations run through.

The composition root binds them inside the admitted profile worker: the
encrypted repository (which alone holds the profile key the issuer and plan
references are digested under), the pinned authority's write answers and the
profile's attachment custody for the certificate bytes.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol
from uuid import UUID

from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ..aggregation.prevision_social_contribution_repository import (
    PrevisionSocialContributionEvidenceCustody,
    PrevisionSocialContributionRecordRepository,
    PrevisionSocialContributionWriteAuthority,
)


class PrevisionSocialCertificateCustody(PrevisionSocialContributionEvidenceCustody, Protocol):
    """Attachment custody that can also take a certificate file the operator names."""

    def ingest(self, *, source_path: Path, data: bytes, mime_type: str, captured_at: datetime) -> str:
        """Keep ``data`` in encrypted custody and return the sha256 it is addressed by."""
        ...


@dataclass(frozen=True, slots=True)
class PrevisionSocialPorts:
    """The capabilities one operation uses, bound to one profile and authority generation."""

    repository: PrevisionSocialContributionRecordRepository
    authority: PrevisionSocialContributionWriteAuthority
    custody: PrevisionSocialCertificateCustody


class PrevisionSocialPortsFactory(Protocol):
    """Compose the capabilities for one admitted profile and pinned authority operation."""

    def __call__(self, *, profile_id: UUID, operation: PinnedAuthorityOperation) -> PrevisionSocialPorts:
        """Return the capabilities for ``profile_id`` under ``operation``."""
        ...


__all__ = ["PrevisionSocialCertificateCustody", "PrevisionSocialPorts", "PrevisionSocialPortsFactory"]
