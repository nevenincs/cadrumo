"""Compose the existing local workstation report inside its exact profile worker."""

from __future__ import annotations

from uuid import UUID

from ..adapters.outbound.storage.path_budget import windows_worst_case_object_path_suffix_length
from ..application.workstation_check import WorkstationCheckReport, require_workstation_profile, run_workstation_check
from ..application.workstation_check_operation import WorkstationCheckPorts
from ..domain.calculations.registry.authority import PinnedAuthorityOperation
from ..domain.calculations.registry.governed_fact_scope import validating_governed_facts
from .adapter_composition import build_operator_probe_ports


def build_workstation_check_operation_ports(
    *, profile_id: UUID, operation: PinnedAuthorityOperation
) -> WorkstationCheckPorts:
    """Bind canonical local probes without a provider request or credential handoff."""
    require_workstation_profile(profile_id)
    operator_probe_ports = build_operator_probe_ports()

    def report() -> WorkstationCheckReport:
        require_workstation_profile(profile_id)
        with validating_governed_facts(operation):
            return run_workstation_check(
                profile_id=profile_id,
                operator_probe_ports=operator_probe_ports,
                object_path_suffix_length=windows_worst_case_object_path_suffix_length(),
            )

    return WorkstationCheckPorts(
        profile_id=profile_id, operation=operation, operator_probe_ports=operator_probe_ports, report=report
    )
