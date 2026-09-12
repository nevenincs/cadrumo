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

from ...application.auth.session_types import AeatSession
from ...application.auth.sessions import AuthenticatedAeatSessionResult
from ...core.config import Settings
from ...core.period import Period
from .remote_state_models import (
    IvaCompensationHistoryCaptureReport,
    IvaCompensationHistoryReport,
    IvaRemoteStateAcquisitionManifest,
    IvaWalletCaptureReport,
)

if TYPE_CHECKING:
    pass


class IvaRemoteStatePort(Protocol):
    """Concrete capabilities required by the live IVA application service."""

    @property
    def wallet_target_url(self) -> str: ...

    def active_storage_span(self) -> AbstractContextManager[None]: ...

    def list_history(self, *, as_of_year: int | None) -> IvaCompensationHistoryReport: ...

    def persist_manifest(self, manifest: IvaRemoteStateAcquisitionManifest) -> None: ...

    def active_verified_session(
        self,
        *,
        operation: str,
        target_url: str | None,
    ) -> Awaitable[tuple[AeatSession, Settings]]: ...

    def ensure_authenticated_session(
        self,
        settings: Settings,
        *,
        operation: str,
        target_url: str | None,
    ) -> Awaitable[AuthenticatedAeatSessionResult]: ...

    def capture_history(
        self,
        session: AeatSession,
        *,
        settings: Settings,
        year_from: int,
        year_to: int,
        output_root: Path,
        progress_context: dict[str, object] | None,
    ) -> Awaitable[IvaCompensationHistoryCaptureReport]: ...

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
    ) -> Awaitable[IvaWalletCaptureReport]: ...


__all__ = ["IvaRemoteStatePort"]
