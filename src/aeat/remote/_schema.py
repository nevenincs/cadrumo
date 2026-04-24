"""Strict pydantic v2 records for the read-only AEAT remote domain.

Every record is ``strict=True``, ``frozen=True``, ``extra="forbid"`` and
carries the Layer 1 write-guard marker ``mode: Literal["read"] = "read"``.
No ``"write"`` literal is defined anywhere in this subpackage; widening
the marker requires a loud, explicit change that surfaces in code
review.

The records catalogued here are the authoritative typed projection of
the post-auth AEAT Sede Electronica surface. They are consumed by the
reconciliation engine in :mod:`aeat.filing.reconciliation` (landing in
Phase 3) and by the sync-run orchestrator (Phase 5).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import AnyHttpUrl, AwareDatetime, BaseModel, ConfigDict, Field

from ..schema import CasillaDataType
from ._status import RemoteFilingStatus

_STRICT_FROZEN = ConfigDict(strict=True, frozen=True, extra="forbid")

_MODE_READ: Literal["read"] = "read"
"""Shared default for every ``mode`` field in this module."""


class RemoteCasilla(BaseModel):
    """One casilla value as AEAT reports it on the filing-detail page.

    Attributes:
        casilla_id: Canonical casilla identifier (``"01"``, ``"46"``, ...).
        raw_value: Uncoerced string exactly as AEAT prints it, before
            any numeric or boolean parsing.
        data_type: The :class:`aeat.schema.CasillaDataType` resolved
            from the curated catalogue for downstream comparison.
        coerced_value: The value coerced into its native type per
            ``data_type``: :class:`decimal.Decimal` for monetary /
            integer casillas, ``str`` for free-text, ``bool`` for
            check-boxes, :class:`datetime.date` for date casillas,
            ``None`` when the raw value is blank.
        mode: Structural write-guard literal; always ``"read"``.
    """

    model_config = _STRICT_FROZEN

    casilla_id: str = Field(min_length=1, max_length=16)
    raw_value: str = Field(min_length=0, max_length=256)
    data_type: CasillaDataType
    coerced_value: Decimal | str | bool | date | None
    mode: Literal["read"] = _MODE_READ


class RemoteReceipt(BaseModel):
    """Acuse / justificante metadata captured for a remote filing.

    Attributes:
        receipt_id: AEAT-issued stable identifier (CSV, acuse id, ...).
        kind: Discriminator between the two receipt shapes Kent
            encounters: ``"acuse"`` for the acknowledgement of receipt
            and ``"justificante"`` for the downloadable PDF evidence.
        pdf_url: Fully-qualified URL to the PDF as AEAT exposes it.
        content_hash: Hex digest of the fetched PDF body, used to detect
            byte-level drift across repeat fetches.
        captured_at: UTC timestamp recording when the receipt was
            materialised.
        mode: Structural write-guard literal; always ``"read"``.
    """

    model_config = _STRICT_FROZEN

    receipt_id: str = Field(min_length=1, max_length=128)
    kind: Literal["acuse", "justificante"]
    pdf_url: AnyHttpUrl
    content_hash: str = Field(min_length=1, max_length=128)
    captured_at: AwareDatetime
    mode: Literal["read"] = _MODE_READ


class RemoteFiling(BaseModel):
    """Authoritative AEAT record for one ``(modelo, period)`` submission.

    Attributes:
        modelo: AEAT modelo code (``"130"``, ``"303"``, ``"390"``, ...).
        period: Period identifier as AEAT prints it (``"2025-1T"``,
            ``"2025"``).
        expediente_id: AEAT-issued stable identifier for the
            expediente that wraps this filing.
        status: Typed :class:`RemoteFilingStatus` resolved from
            ``raw_status``.
        raw_status: Free-form Spanish status string exactly as AEAT
            printed it; carried verbatim so unknown statuses stay
            observable even when ``status`` folds into
            :attr:`RemoteFilingStatus.UNKNOWN`.
        submitted_at: UTC timestamp AEAT stamped on the receipt when
            it accepted the filing.
        casillas: Ordered tuple of every :class:`RemoteCasilla` parsed
            from the detail page.
        receipts: Tuple of :class:`RemoteReceipt` records associated
            with this filing (acuses, justificantes).
        complementaria_of: Optional ``expediente_id`` of the filing
            this one amends; ``None`` for original filings.
        mode: Structural write-guard literal; always ``"read"``.
    """

    model_config = _STRICT_FROZEN

    modelo: str = Field(min_length=1, max_length=8)
    period: str = Field(min_length=1, max_length=16)
    expediente_id: str = Field(min_length=1, max_length=64)
    status: RemoteFilingStatus
    raw_status: str = Field(min_length=1, max_length=128)
    submitted_at: AwareDatetime
    casillas: tuple[RemoteCasilla, ...]
    receipts: tuple[RemoteReceipt, ...] = ()
    complementaria_of: str | None = Field(default=None, min_length=1, max_length=64)
    mode: Literal["read"] = _MODE_READ


class RemoteExpediente(BaseModel):
    """Expediente wrapper aggregating one or more :class:`RemoteFiling`.

    Attributes:
        expediente_id: AEAT-issued stable identifier.
        modelo: Modelo code of every filing in the expediente.
        period: Period identifier of every filing in the expediente.
        filings: Tuple of original + complementaria filings, ordered
            as AEAT surfaces them (oldest first).
        opened_at: UTC timestamp AEAT stamped when the expediente was
            first opened.
        mode: Structural write-guard literal; always ``"read"``.
    """

    model_config = _STRICT_FROZEN

    expediente_id: str = Field(min_length=1, max_length=64)
    modelo: str = Field(min_length=1, max_length=8)
    period: str = Field(min_length=1, max_length=16)
    filings: tuple[RemoteFiling, ...]
    opened_at: AwareDatetime
    mode: Literal["read"] = _MODE_READ


class RemoteNotification(BaseModel):
    """Notification-centre entry linked to an expediente.

    Attributes:
        notification_id: AEAT-issued stable identifier.
        subject: Single-line subject as AEAT prints it.
        issued_at: UTC timestamp AEAT stamped when it emitted the
            notification.
        acknowledged_at: UTC timestamp Kent acknowledged the
            notification; ``None`` when still pending.
        linked_expediente_id: Optional expediente reference when AEAT
            explicitly wires the notification to one.
        mode: Structural write-guard literal; always ``"read"``.
    """

    model_config = _STRICT_FROZEN

    notification_id: str = Field(min_length=1, max_length=64)
    subject: str = Field(min_length=1, max_length=512)
    issued_at: AwareDatetime
    acknowledged_at: AwareDatetime | None = None
    linked_expediente_id: str | None = Field(default=None, min_length=1, max_length=64)
    mode: Literal["read"] = _MODE_READ


class RemoteNavigationGraph(BaseModel):
    """Stable post-auth URL catalogue used by the live fetchers.

    The catalogue promotes the provisional URL constants inline in
    :mod:`aeat.status._reader` into a typed record that can be passed
    around without cross-importing private modules. Full Phase-2
    population replaces this shell; Phase 1 only locks the shape.

    Attributes:
        expedientes_list_path: Relative path to *Mis expedientes*.
        expediente_detail_template: URL template with ``{expediente_id}``
            for the detail page.
        notificaciones_path: Relative path to *Mis notificaciones*.
        mode: Structural write-guard literal; always ``"read"``.
    """

    model_config = _STRICT_FROZEN

    expedientes_list_path: str = Field(min_length=1, max_length=512)
    expediente_detail_template: str = Field(min_length=1, max_length=512)
    notificaciones_path: str = Field(min_length=1, max_length=512)
    mode: Literal["read"] = _MODE_READ


class RemoteFilingRef(BaseModel):
    """Lightweight reference to a :class:`RemoteFiling` for report payloads.

    The reconciliation comparator emits ``RemoteFilingRef`` rather than
    the full :class:`RemoteFiling` so the persisted divergence record
    stays cheap to serialise and easy to deduplicate.

    Attributes:
        expediente_id: AEAT-issued stable identifier.
        modelo: Modelo code of the referenced filing.
        period: Period identifier of the referenced filing.
        captured_at: UTC timestamp at which the remote snapshot was
            taken (distinct from the filing's ``submitted_at``).
        mode: Structural write-guard literal; always ``"read"``.
    """

    model_config = _STRICT_FROZEN

    expediente_id: str = Field(min_length=1, max_length=64)
    modelo: str = Field(min_length=1, max_length=8)
    period: str = Field(min_length=1, max_length=16)
    captured_at: AwareDatetime
    mode: Literal["read"] = _MODE_READ


# Re-exported symbols kept explicit so wildcard imports stay disabled.
__all__ = [
    "RemoteCasilla",
    "RemoteExpediente",
    "RemoteFiling",
    "RemoteFilingRef",
    "RemoteNavigationGraph",
    "RemoteNotification",
    "RemoteReceipt",
]
