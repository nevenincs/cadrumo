"""Immutable worker capabilities for the one canonical local quickfile chain."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from ...domain.attachments.protocols import AttachmentStoreProtocol
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.deadlines.models import TaxpayerProfile
from ..auth.certificate_secret_backend import CertificateSecretBackendFactory
from ..auth.operator_probe_ports import OperatorProbePorts
from ..auth.operator_scope_ports import OperatorScopePorts
from ..state_projection_ports import StateProjectionReadPorts
from .calculation_action_ports import CalculationActionPorts
from .export_ports import ModeloExportPorts
from .verification_repository_ports import VerificationRepositoryBundle
from .work_profile import ModeloWorkProfile


@dataclass(frozen=True, slots=True)
class QuickfileOperationPorts:
    """Exact profile, retained generation and supplied existing stage capabilities."""

    profile_id: UUID
    operation: PinnedAuthorityOperation
    profile: ModeloWorkProfile
    workflow_profile: TaxpayerProfile
    calculation: CalculationActionPorts
    verification: VerificationRepositoryBundle
    export: ModeloExportPorts
    read: StateProjectionReadPorts
    certificate_secret_backend_factory: CertificateSecretBackendFactory
    operator_probe_ports: OperatorProbePorts
    operator_scope_ports: OperatorScopePorts
    attachments: AttachmentStoreProtocol


class QuickfileOperationPortsFactory(Protocol):
    """Compose only the admitted profile with explicit concrete writer interception."""

    def __call__(
        self,
        *,
        profile_id: UUID,
        operation: PinnedAuthorityOperation,
        mutation_writer: Callable[[Callable[[], None]], None],
    ) -> QuickfileOperationPorts:
        """Retain one pin and admit each actual prepared local mutation separately."""
        ...
