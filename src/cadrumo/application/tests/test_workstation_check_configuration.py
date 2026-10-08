"""Canonical configuration effects on the workstation check report."""

from __future__ import annotations

from typing import cast
from uuid import UUID

import pytest

from ...core.capabilities import ServiceCapability
from ...core.config import Settings, load_settings, override_settings
from .. import workstation_check as module
from ..auth.operator_probe_ports import OperatorProbePorts
from ..preflight import PreflightCheck
from ..provisioning import DependencyStatus
from ..user_profile.capabilities import CapabilityDecision, CapabilitySource, resolve_capability_from_values
from ..workstation_check import WorkstationCheckReport

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE_ID = UUID("f45e95a0-d925-4e71-8ae7-dc4eef9341d4")


def _report(monkeypatch: pytest.MonkeyPatch, *, profile_values: dict[str, str]) -> WorkstationCheckReport:
    """Run canonical report assembly with measured rows held steady."""

    def resolve(capability: ServiceCapability) -> CapabilityDecision:
        return resolve_capability_from_values(
            capability,
            profile_values=profile_values,
            settings=load_settings(),
        )

    vision = DependencyStatus(service="local-reader:vision_transcription", available=True)
    google = DependencyStatus(service="extra:google", available=True)
    browser = DependencyStatus(service="extra:browser", available=True)
    anthropic = DependencyStatus(service="extra:anthropic", available=True)
    extras = (google, browser, anthropic)

    def dependencies() -> tuple[tuple[DependencyStatus, ...], DependencyStatus, tuple[DependencyStatus, ...]]:
        return (vision, *extras), vision, extras

    def preflight(
        *,
        object_path_suffix_length: int,
        operator_probe_ports: OperatorProbePorts,
        settings: Settings | None = None,
    ) -> tuple[PreflightCheck, ...]:
        assert object_path_suffix_length == 1
        assert operator_probe_ports is not None
        del settings
        return ()

    monkeypatch.setattr(module, "resolve_active_capability", resolve)
    monkeypatch.setattr(module, "_probe_dependency_statuses", dependencies)
    monkeypatch.setattr(module, "run_preflight_checks", preflight)
    return module.run_workstation_check(
        profile_id=_PROFILE_ID,
        operator_probe_ports=cast(OperatorProbePorts, object()),
        object_path_suffix_length=1,
    )


@pytest.mark.parametrize(
    ("profile_values", "gestor_mode", "deployment_permitted", "enabled", "source", "issues"),
    [
        ({}, False, False, False, CapabilitySource.DEFAULT, ()),
        (
            {"capabilities.cloud_evidence_upload": "true"},
            False,
            False,
            True,
            CapabilitySource.PROFILE,
            ("cloud_evidence_upload:deployment_permission",),
        ),
        (
            {"capabilities.cloud_evidence_upload": "true"},
            True,
            False,
            False,
            CapabilitySource.SAFETY_FLOOR,
            (),
        ),
    ],
    ids=["default-off", "opt-in-without-deployment-permission", "gestor-safety-floor"],
)
def test_report_issues_follow_the_effective_cloud_capability(
    monkeypatch: pytest.MonkeyPatch,
    profile_values: dict[str, str],
    gestor_mode: bool,
    deployment_permitted: bool,
    enabled: bool,
    source: CapabilitySource,
    issues: tuple[str, ...],
) -> None:
    """Only an effective opt-in without deployment permission becomes an issue."""
    with override_settings(
        cadrumo_active_profile=str(_PROFILE_ID),
        cadrumo_evidence_gestor_mode=gestor_mode,
        cadrumo_evidence_cloud_upload_permitted=deployment_permitted,
    ):
        report = _report(monkeypatch, profile_values=profile_values)

    cloud = next(row for row in report.capabilities if row.capability is ServiceCapability.CLOUD_EVIDENCE_UPLOAD)
    assert cloud.enabled is enabled
    assert cloud.source is source
    assert report.issues == issues
