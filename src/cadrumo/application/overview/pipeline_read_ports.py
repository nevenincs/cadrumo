"""Exact-profile capabilities for a read-only pipeline inspection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.modelos.protocols import VerificationReportCatalogueRepositoryProtocol
from ..ledger.action_ports import LedgerActionPorts
from ..modelo.calculation_action_ports import CalculationActionPorts


@dataclass(frozen=True, slots=True)
class PipelineReadPorts:
    """Canonical query ports and a report repository bound to one worker."""

    bucket_id: str
    ledger: LedgerActionPorts
    calculation: CalculationActionPorts
    verification: VerificationReportCatalogueRepositoryProtocol


class PipelineReadPortsFactory(Protocol):
    """Compose the requested profile under the operation's retained authority."""

    def __call__(self, *, bucket_id: str, operation: PinnedAuthorityOperation) -> PipelineReadPorts:
        """Return capabilities without migrating any persisted catalogue."""
        ...
