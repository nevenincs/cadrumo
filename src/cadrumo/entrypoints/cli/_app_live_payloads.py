"""Public typed ``--json`` payload facade for app live CLI commands.

Production CommandSpec declarations retain deferred targets in this module.
Each schema has one service-owned definition below; this facade preserves the
stable import surface consumed by command assembly and emit handlers.
"""

from __future__ import annotations

from ._app_live_borrador_payloads import (
    Borrador100LatestResult,
    Borrador100ListResult,
    Borrador100SnapshotSummaryPayload,
    Borrador100ViewResult,
)
from ._app_live_deudas_payloads import (
    DeudaRowPayload,
    DeudasLatestResult,
    DeudasListResult,
    DeudaSnapshotSummaryPayload,
    DeudasViewResult,
)
from ._app_live_expedientes_payloads import (
    ExpedienteDeclarationPayload,
    ExpedientesCaptureFailurePayload,
    ExpedientesCaptureResult,
    ExpedientesLatestResult,
    ExpedientesListResult,
    ExpedienteSnapshotSummaryPayload,
    ExpedientesViewResult,
)
from ._app_live_filed_payloads import (
    FiledCaptureFailurePayload,
    FiledCaptureResult,
    FiledCaptureSourcesResult,
    FiledDiscoverResult,
    FiledHistoryDiscoveryPairPayload,
    FiledHistoryOnboardingResult,
    FiledHistoryPairOutcomePayload,
    FiledListingRowPayload,
    FiledListResult,
)
from ._app_live_iva_wallet_payloads import (
    IvaCompensationCarryForwardLotPayload,
    IvaCompensationHistoryRowPayload,
    IvaWalletAuthorityDecisionPayload,
    IvaWalletCaptureHistoryResult,
    IvaWalletHistoryResult,
    IvaWalletPullEvidenceResult,
    IvaWalletPullResult,
    LiveIvaAuthOutcomePayload,
    LiveIvaSurfaceOutcomePayload,
)
from ._app_live_justificante_payloads import (
    JustificanteCaptureResult,
    JustificanteListResult,
    JustificanteSnapshotSummaryPayload,
    JustificanteViewResult,
)
from ._app_live_notifications_payloads import (
    NotificationDocumentHistoryEntry,
    NotificationDocumentHistoryResult,
    NotificationDocumentPayload,
    NotificationDocumentPullResult,
    NotificationDocumentViewResult,
    NotificationRowPayload,
    NotificationsCaptureResult,
    NotificationsLatestResult,
    NotificationsListResult,
    NotificationSnapshotListingPayload,
    NotificationsViewResult,
    SancionReadingPayload,
)
from ._app_live_payloads_support import JustificantePeriodToken
from ._app_live_portals_payloads import (
    PortalEntryPayload,
    PortalsListResult,
    PortalsViewResult,
)
from ._app_live_verify_payloads import (
    VerifyLatestResult,
    VerifyListResult,
    VerifyNifIvaResult,
    VerifyObservationPayload,
    VerifyObservationSummaryPayload,
    VerifyTgviResult,
    VerifyViewResult,
)

__all__ = [
    "Borrador100LatestResult",
    "Borrador100ListResult",
    "Borrador100SnapshotSummaryPayload",
    "Borrador100ViewResult",
    "DeudaRowPayload",
    "DeudaSnapshotSummaryPayload",
    "DeudasLatestResult",
    "DeudasListResult",
    "DeudasViewResult",
    "ExpedienteDeclarationPayload",
    "ExpedienteSnapshotSummaryPayload",
    "ExpedientesCaptureFailurePayload",
    "ExpedientesCaptureResult",
    "ExpedientesLatestResult",
    "ExpedientesListResult",
    "ExpedientesViewResult",
    "FiledCaptureFailurePayload",
    "FiledCaptureResult",
    "FiledCaptureSourcesResult",
    "FiledDiscoverResult",
    "FiledHistoryDiscoveryPairPayload",
    "FiledHistoryOnboardingResult",
    "FiledHistoryPairOutcomePayload",
    "FiledListResult",
    "FiledListingRowPayload",
    "IvaCompensationCarryForwardLotPayload",
    "IvaCompensationHistoryRowPayload",
    "IvaWalletAuthorityDecisionPayload",
    "IvaWalletCaptureHistoryResult",
    "IvaWalletHistoryResult",
    "IvaWalletPullEvidenceResult",
    "IvaWalletPullResult",
    "JustificanteCaptureResult",
    "JustificanteListResult",
    "JustificantePeriodToken",
    "JustificanteSnapshotSummaryPayload",
    "JustificanteViewResult",
    "LiveIvaAuthOutcomePayload",
    "LiveIvaSurfaceOutcomePayload",
    "NotificationDocumentHistoryEntry",
    "NotificationDocumentHistoryResult",
    "NotificationDocumentPayload",
    "NotificationDocumentPullResult",
    "NotificationDocumentViewResult",
    "NotificationRowPayload",
    "NotificationSnapshotListingPayload",
    "NotificationsCaptureResult",
    "NotificationsLatestResult",
    "NotificationsListResult",
    "NotificationsViewResult",
    "PortalEntryPayload",
    "PortalsListResult",
    "PortalsViewResult",
    "SancionReadingPayload",
    "VerifyLatestResult",
    "VerifyListResult",
    "VerifyNifIvaResult",
    "VerifyObservationPayload",
    "VerifyObservationSummaryPayload",
    "VerifyTgviResult",
    "VerifyViewResult",
]
