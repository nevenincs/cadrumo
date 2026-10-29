"""Canonical workstation assembly over exact encrypted synthetic profile facts."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID, uuid4

import pytest

from cadrumo_client.contracts.access_refusals import AccessDenialCode

from ...adapters.outbound.components.tests.recorded_rows import set_up_row
from ...adapters.persistence.profile.tests.profile_registration import register_minimal_profile
from ...adapters.persistence.storage.tests.profile_capsule_runtime import open_test_profile_session
from ...adapters.persistence.storage.tests.secure_sql import isolated_profile_storage_root
from ...application import workstation_check as service
from ...application.auth.operator_probe_ports import OperatorProbePorts
from ...application.local_reader import LOCAL_AI_PROGRAM_SERVICE, ProgramRow
from ...application.preflight import HealthSeverity, PreflightCheck
from ...application.provisioning import DependencyStatus
from ...application.user_profile.access_errors import ProfileAccessRefusedError
from ...application.user_profile.capabilities import CapabilitySource
from ...application.workstation_check_operation import WorkstationCheckProjection
from ...core.capabilities import ServiceCapability
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.governed_fact_scope import governed_facts_in_scope
from .. import workstation_check_operation_composition as composition

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]
_PROFILE = UUID("72727272-7272-4272-8272-727272727272")


def test_exact_encrypted_profile_capabilities_and_retained_pin_reach_canonical_report(
    tmp_path: Path,
    authority_operation: PinnedAuthorityOperation,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Canonical capability reads retain source and issue behavior without a live probe."""
    program = DependencyStatus(service=LOCAL_AI_PROGRAM_SERVICE, available=True, facts={"installed": True, "count": 0})
    google = DependencyStatus(service="extra:google", available=True, facts={"installed": True})
    preflight_row = PreflightCheck(
        check="synthetic:registry", healthy=True, severity=HealthSeverity.OK, facts={"assembled": True, "records": 0}
    )
    observed: list[str] = []
    captured: list[OperatorProbePorts] = []

    program_row = set_up_row("local_ai")

    def read_program() -> ProgramRow:
        observed.append("program")
        return program_row

    def dependencies(row: ProgramRow) -> tuple[tuple[DependencyStatus, ...], tuple[DependencyStatus, ...]]:
        assert governed_facts_in_scope() is authority_operation
        assert row is program_row
        observed.append("dependencies")
        return (program, google), (google,)

    def preflight(
        *, object_path_suffix_length: int, operator_probe_ports: OperatorProbePorts
    ) -> tuple[PreflightCheck, ...]:
        assert governed_facts_in_scope() is authority_operation
        assert object_path_suffix_length > 0
        captured.append(operator_probe_ports)
        observed.append("preflight")
        return (preflight_row,)

    monkeypatch.setattr(composition, "read_local_ai_program", read_program)
    monkeypatch.setattr(service, "_probe_dependency_statuses", dependencies)
    monkeypatch.setattr(service, "run_preflight_checks", preflight)
    previous_scope = governed_facts_in_scope()
    with isolated_profile_storage_root(tmp_path=tmp_path), open_test_profile_session(str(_PROFILE)):
        register_minimal_profile(
            profile_id=str(_PROFILE),
            overrides={
                ServiceCapability.LLM_VISION.schema_path: "true",
                ServiceCapability.GOOGLE_EXPORT.schema_path: "false",
                ServiceCapability.CLOUD_EVIDENCE_UPLOAD.schema_path: "false",
            },
        )
        ports = composition.build_workstation_check_operation_ports(profile_id=_PROFILE, operation=authority_operation)
        assert ports.profile_id == _PROFILE and ports.operation is authority_operation
        report = ports.report()
        assert report.profile_id == _PROFILE and not report.issues
        decisions = {row.capability: row for row in report.capabilities}
        assert decisions[ServiceCapability.LLM_VISION].enabled
        assert decisions[ServiceCapability.LLM_VISION].source is CapabilitySource.PROFILE
        assert not decisions[ServiceCapability.GOOGLE_EXPORT].enabled
        assert report.dependencies == (program, google) and report.preflight == (preflight_row,)
        assert WorkstationCheckProjection.from_report(report).to_report() == report
        assert observed == ["program", "dependencies", "preflight"] and captured == [ports.operator_probe_ports]
        assert governed_facts_in_scope() is previous_scope


def test_foreign_profile_refuses_before_probe_composition(
    tmp_path: Path,
    authority_operation: PinnedAuthorityOperation,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An ambient session cannot lend its private observations to a different UUID."""

    def probes() -> OperatorProbePorts:
        raise AssertionError("foreign-profile composition must stop before building probes")

    monkeypatch.setattr(composition, "build_operator_probe_ports", probes)
    with isolated_profile_storage_root(tmp_path=tmp_path), open_test_profile_session(str(_PROFILE)):
        with pytest.raises(ProfileAccessRefusedError) as refused:
            composition.build_workstation_check_operation_ports(profile_id=uuid4(), operation=authority_operation)
        assert refused.value.reason is AccessDenialCode.PROFILE_MISMATCH
