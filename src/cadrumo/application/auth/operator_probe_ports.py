"""Application-owned capabilities for local operator authentication probes.

The operator probe use case only needs three small observations from the outer
runtime: whether an active profile session exists, the health facts of a local
certificate bundle, and the kind of a configured Cl@ve identity.  Concrete
adapter records, enums, and exceptions stay outside this contract; adapters
translate them into the closed results declared here.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Protocol

from pydantic import SecretStr


class CertificateHealthBand(StrEnum):
    """Application vocabulary for a certificate's expiry health."""

    OK = "ok"
    WARN = "warn"
    CRITICAL = "critical"
    EXPIRED = "expired"


@dataclass(frozen=True, slots=True)
class CertificateHealthObservation:
    """Translated health facts required by the application probe."""

    severity: CertificateHealthBand
    days_until_expiry: int


@dataclass(frozen=True, slots=True)
class CertificateHealthFailure:
    """Translated certificate-load failure safe for application projection."""

    detail: str


CertificateHealthProbeResult = CertificateHealthObservation | CertificateHealthFailure


@dataclass(frozen=True, slots=True)
class CertificateHealthProbeRequest:
    """Application-owned input for one certificate health observation."""

    path: Path
    password: SecretStr
    warn_days: int
    critical_days: int
    friendly_name: str | None


class ActiveProfileSessionPresencePort(Protocol):
    """Observe whether the storage runtime has an active profile session."""

    def is_bound(self) -> bool:
        """Return whether a profile session is currently bound."""
        ...


class CertificateHealthProbePort(Protocol):
    """Obtain translated health or failure facts for one certificate bundle."""

    def evaluate(self, request: CertificateHealthProbeRequest) -> CertificateHealthProbeResult:
        """Evaluate the requested bundle without leaking adapter types."""
        ...


@dataclass(frozen=True, slots=True)
class ClaveIdentityObservation:
    """Translated accepted Cl@ve identity kind (for example, DNI or NIE)."""

    kind: str


@dataclass(frozen=True, slots=True)
class ClaveIdentityFailure:
    """Translated Cl@ve identity configuration refusal."""

    detail: str


ClaveIdentityProbeResult = ClaveIdentityObservation | ClaveIdentityFailure


class ClaveIdentityProbePort(Protocol):
    """Classify a configured Cl@ve identity at the outbound boundary."""

    def classify(self, raw: str) -> ClaveIdentityProbeResult:
        """Return an accepted identity kind or a translated configuration fault."""
        ...


@dataclass(frozen=True, slots=True)
class OperatorProbePorts:
    """Required outbound capabilities for all operator authentication probes."""

    active_profile_session: ActiveProfileSessionPresencePort
    certificate_health: CertificateHealthProbePort
    clave_identity: ClaveIdentityProbePort


__all__ = [
    "ActiveProfileSessionPresencePort",
    "CertificateHealthBand",
    "CertificateHealthFailure",
    "CertificateHealthObservation",
    "CertificateHealthProbePort",
    "CertificateHealthProbeRequest",
    "CertificateHealthProbeResult",
    "ClaveIdentityFailure",
    "ClaveIdentityObservation",
    "ClaveIdentityProbePort",
    "ClaveIdentityProbeResult",
    "OperatorProbePorts",
]
