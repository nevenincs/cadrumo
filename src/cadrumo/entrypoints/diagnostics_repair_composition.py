"""Compose the repair and diagnostics operations and the adapters their work reaches.

The four ``diagnostics`` repair operations run in a profile's worker. This
module binds each one's port to its outbound or persistence adapter: the
profile's own secure-object store, the browser that probes connectivity, and
the session host's caller reader. The profile-record reader the command line
and the runtime's repair act both use is bound here too, so the two read a
record through the same door.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import UUID

from ..application.diagnostics_repair_operations import (
    build_connectivity_probe_definition,
    build_connectivity_probe_registration,
    build_secure_objects_check_definition,
    build_secure_objects_check_registration,
    build_secure_objects_quarantine_definition,
    build_secure_objects_quarantine_registration,
    build_workflow_progress_reset_definition,
    build_workflow_progress_reset_registration,
)
from ..application.operations.operation_definition import OperationDefinition
from ..application.operations.registry import OperationPublicDefinitionRegistrationV1
from .adapter_composition import build_diagnostics_ports

if TYPE_CHECKING:
    from ..application.connectivity_probe import ConnectivityProbePort, ObservedSiteHealth
    from ..application.diagnostics_ports import DiagnosticsPorts
    from ..application.operations.execution_actor import OperationExecutionCallerReader
    from ..domain.user_profile.values import UserProfileRecord

__all__ = [
    "DiagnosticsRepairOperations",
    "build_diagnostics_repair_operations",
    "build_profile_diagnostics_ports",
    "probe_aeat_sede_connectivity",
    "read_session_profile_record",
]


@dataclass(frozen=True, slots=True)
class DiagnosticsRepairOperations:
    """The definitions and public registrations of the repair and diagnostics family."""

    definitions: tuple[OperationDefinition, ...]
    registrations: tuple[OperationPublicDefinitionRegistrationV1, ...]


def build_profile_diagnostics_ports(*, profile_id: UUID) -> DiagnosticsPorts:
    """Bind secure-object diagnostics to exactly ``profile_id``'s own store."""
    return build_diagnostics_ports(bucket_id=str(profile_id))


def probe_aeat_sede_connectivity() -> ObservedSiteHealth:
    """Browse once to the configured public landing page and classify its answer."""
    # The browser adapter loads only when a probe runs, not when operations are composed.
    from ..adapters.outbound.aeat.browser.connectivity import probe_browser_connectivity

    return probe_browser_connectivity()


def read_session_profile_record(*, profile_id: str, bucket_id: str) -> UserProfileRecord:
    """Read one profile's record through the session this process already holds for it.

    Raises:
        ProfileNotFoundError: No session in this process serves ``bucket_id``;
            the reader opens none of its own.
    """
    from ..adapters.persistence.storage.master_key.active_session import active_bucket_session_serves
    from ..application.user_profile.profile_record_repository import ProfileRecordRepository
    from ..domain.calculations.registry.authority import bundled_indexed_authority
    from ..domain.user_profile.errors import ProfileNotFoundError

    if active_bucket_session_serves(bucket_id):
        with bundled_indexed_authority().operation() as operation:
            return ProfileRecordRepository.for_current_session(
                bucket_id,
                profile_decode_context=operation.profile_decode_context(),
            ).load(profile_id)
    raise ProfileNotFoundError("profile record requires its active authenticated custody session")


def build_diagnostics_repair_operations(
    *,
    execution_caller_reader: OperationExecutionCallerReader | None = None,
    connectivity_probe: ConnectivityProbePort = probe_aeat_sede_connectivity,
) -> DiagnosticsRepairOperations:
    """Bind the adapters to the four repair operations that run in a profile's worker.

    ``execution_caller_reader`` is the session host's, so a progress reset an
    agent submits records the agent's session as its actor.
    ``connectivity_probe`` browses to the probed site; a host that must not
    start a browser binds its own.
    """
    connectivity = build_connectivity_probe_definition(connectivity_probe)
    check = build_secure_objects_check_definition(build_profile_diagnostics_ports)
    quarantine = build_secure_objects_quarantine_definition(build_profile_diagnostics_ports)
    reset = build_workflow_progress_reset_definition(execution_caller_reader=execution_caller_reader)
    # Ordered by definition id, the order a registry requires of its public registrations.
    return DiagnosticsRepairOperations(
        definitions=(connectivity, check, quarantine, reset),
        registrations=(
            build_connectivity_probe_registration(connectivity),
            build_secure_objects_check_registration(check),
            build_secure_objects_quarantine_registration(quarantine),
            build_workflow_progress_reset_registration(reset),
        ),
    )
