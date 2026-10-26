"""Inward ports for live IVA remote-state acquisition.

The application service owns orchestration and redacted report projection.
AEAT browser access, encrypted evidence persistence, and active-profile session
selection are composed at the entrypoint boundary.
"""

from __future__ import annotations

from collections.abc import Awaitable
from contextlib import AbstractContextManager
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from ...core.config import Settings
from ...core.period import Period
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ..auth.session_types import AeatSession
from ..auth.sessions import AuthenticatedAeatSessionResult
from .filed_data_ports import FiledEffectGuard
from .remote_state_models import (
    IvaCompensationHistoryCaptureReport,
    IvaCompensationHistoryReport,
    IvaRemoteStateAcquisitionManifest,
    IvaWalletCaptureReport,
)
from .session import SessionWriteReporter

if TYPE_CHECKING:
    pass


class IvaRemoteStatePort(Protocol):
    """Concrete capabilities required by the live IVA application service."""

    @property
    def wallet_target_url(self) -> str:
        """Return the live IVA wallet endpoint selected by composition."""
        ...

    def active_storage_span(self) -> AbstractContextManager[None]:
        """Open the storage scope required for the live acquisition."""
        ...

    def list_history(self, *, as_of_year: int | None) -> IvaCompensationHistoryReport:
        """Read persisted IVA compensation history through the port."""
        ...

    def persist_manifest(self, manifest: IvaRemoteStateAcquisitionManifest) -> None:
        """Persist one acquisition manifest through the secure boundary."""
        ...

    def active_verified_session(
        self,
        *,
        operation: str,
        target_url: str | None,
        authority_operation: PinnedAuthorityOperation | None = None,
        effect_guard: FiledEffectGuard | None = None,
        on_session_write: SessionWriteReporter | None = None,
    ) -> Awaitable[tuple[AeatSession, Settings]]:
        """Open the active verified AEAT session for an operation."""
        ...

    def ensure_authenticated_session(
        self,
        settings: Settings,
        *,
        operation: str,
        target_url: str | None,
        authority_operation: PinnedAuthorityOperation | None = None,
        effect_guard: FiledEffectGuard | None = None,
        on_session_write: SessionWriteReporter | None = None,
    ) -> Awaitable[AuthenticatedAeatSessionResult]:
        """Ensure an AEAT session is authenticated for an operation."""
        ...

    def capture_history(
        self,
        session: AeatSession,
        *,
        settings: Settings,
        year_from: int,
        year_to: int,
        output_root: Path,
        progress_context: dict[str, object] | None,
        effect_guard: FiledEffectGuard | None = None,
        authority_operation: PinnedAuthorityOperation | None = None,
    ) -> Awaitable[IvaCompensationHistoryCaptureReport]:
        """Capture IVA compensation history for the requested year range."""
        ...

    def capture_wallet(
        self,
        session: AeatSession,
        *,
        settings: Settings,
        target_year: int,
        target_period: Period,
        taxpayer_nif: str | None,
        output_root: Path | None,
        progress_context: dict[str, object] | None,
        effect_guard: FiledEffectGuard | None = None,
        authority_operation: PinnedAuthorityOperation | None = None,
    ) -> Awaitable[IvaWalletCaptureReport]:
        """Capture IVA wallet state for one target year and period."""
        ...


__all__ = ["IvaRemoteStatePort"]
