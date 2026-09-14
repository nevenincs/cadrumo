"""Inward fakes for application operator-probe tests."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import override

from ..operator_probe_ports import (
    ActiveProfileSessionPresencePort,
    CertificateHealthBand,
    CertificateHealthObservation,
    CertificateHealthProbePort,
    CertificateHealthProbeRequest,
    CertificateHealthProbeResult,
    ClaveIdentityFailure,
    ClaveIdentityObservation,
    ClaveIdentityProbePort,
    ClaveIdentityProbeResult,
    OperatorProbePorts,
)


@dataclass
class FakeActiveProfileSessionPresence(ActiveProfileSessionPresencePort):
    """Report the explicitly selected session state to an application probe."""

    bound: bool = True

    @override
    def is_bound(self) -> bool:
        return self.bound


@dataclass
class FakeCertificateHealthProbe(CertificateHealthProbePort):
    """Return a caller-supplied application health result."""

    result: CertificateHealthProbeResult = field(
        default_factory=lambda: CertificateHealthObservation(
            severity=CertificateHealthBand.OK,
            days_until_expiry=365,
        ),
    )
    evaluator: Callable[[CertificateHealthProbeRequest], CertificateHealthProbeResult] | None = None

    @override
    def evaluate(self, request: CertificateHealthProbeRequest) -> CertificateHealthProbeResult:
        if self.evaluator is not None:
            return self.evaluator(request)
        return self.result


@dataclass
class FakeClaveIdentityProbe(ClaveIdentityProbePort):
    """Return translated identity facts without importing the Cl@ve adapter."""

    result_by_raw: dict[str, ClaveIdentityProbeResult] = field(default_factory=dict)
    default_kind: str = "DNI"

    @override
    def classify(self, raw: str) -> ClaveIdentityProbeResult:
        if raw in self.result_by_raw:
            return self.result_by_raw[raw]
        if not raw:
            return ClaveIdentityFailure(detail="identity is not configured")
        return ClaveIdentityObservation(kind=self.default_kind)


def fake_operator_probe_ports(
    *,
    active_profile_session_bound: bool = True,
    certificate_health: CertificateHealthProbeResult | None = None,
    certificate_evaluator: Callable[[CertificateHealthProbeRequest], CertificateHealthProbeResult] | None = None,
    clave_identity: ClaveIdentityProbeResult | None = None,
    clave_identity_results: Mapping[str, ClaveIdentityProbeResult] | None = None,
) -> OperatorProbePorts:
    """Build a complete inward fake bundle for an application test."""
    clave_probe = FakeClaveIdentityProbe()
    if clave_identity is not None:
        clave_probe.default_kind = (
            clave_identity.kind if isinstance(clave_identity, ClaveIdentityObservation) else "DNI"
        )
    if clave_identity_results is not None:
        clave_probe.result_by_raw.update(clave_identity_results)
    return OperatorProbePorts(
        active_profile_session=FakeActiveProfileSessionPresence(active_profile_session_bound),
        certificate_health=FakeCertificateHealthProbe(
            result=certificate_health
            if certificate_health is not None
            else CertificateHealthObservation(
                severity=CertificateHealthBand.OK,
                days_until_expiry=365,
            ),
            evaluator=certificate_evaluator,
        ),
        clave_identity=clave_probe,
    )


__all__ = [
    "FakeActiveProfileSessionPresence",
    "FakeCertificateHealthProbe",
    "FakeClaveIdentityProbe",
    "fake_operator_probe_ports",
]
