"""Strict pydantic records for the authenticated AEAT sede surface.

Every record represents a read-only AEAT filing, document, or
notification observation. The schema is intentionally narrow so
malformed or unsupported AEAT response shapes fail during parsing.

Every boundary-crossing record carries ``mode: Literal["read"]`` as
part of the structural write-guard — the sede module is incapable
of mutating AEAT state.

Public surface: :class:`Expediente`, :class:`JustificanteRef`,
:class:`SedeCapture`, :class:`FiledDeclaracionArtefact`,
:class:`ObservedCasillaValue`, :class:`FiledDeclaracionObservation`.
"""

from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal
from typing import Final, Literal

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, field_validator

from .....core import Modelo
from .....domain.calculations.registry import CasillaId
from ._errors import SedeValidationError

_STRICT_FROZEN: Final[ConfigDict] = ConfigDict(
    strict=True,
    frozen=True,
    extra="forbid",
)


# AEAT expediente identifiers are <year><sequence><checksum-letter>, e.g.
# "202310013522456T" (length 16). Observed range: 14-20 characters in
# the live capture.
_EXPEDIENTE_ID_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[0-9]{4,}[A-Z0-9]+$")

# CSV (Código Seguro de Verificación) is uppercase hex/alphanumeric.
# Observed: 16 chars ("TUD4V9XAUV7QJ8QV"). Width varies across modelos.
_CSV_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[A-Z0-9]{8,32}$")


class Expediente(BaseModel):
    """One AEAT expediente as listed under *Mis Expedientes*.

    The sede renders an AJAX-expanded category tree at
    ``/wlpl/TEWV-CORE/ResumenVlt``; leaf rows carry the expediente id
    as the link text and the detail URL on the ``<a>`` ``href``.

    Attributes:
        expediente_id: AEAT-assigned identifier. Shape
            ``<year><sequence><checksum-letter>``, e.g.
            ``"202310013522456T"``.
        modelo: Modelo code inferred from the category path when
            resolvable (e.g. ``"100"`` for IRPF anuales). ``None`` for
            categories that do not map 1:1 to a modelo (sanciones,
            recursos, certificados).
        ejercicio: Tax year inferred from the expediente id's leading
            four digits. Captured against 2021 / 2022 / 2023 IRPF.
        category_path: Breadcrumb through the sede's tree, from
            root to leaf. Example: a four-element tuple from
            "Agencia Estatal de Administración Tributaria" down to
            "Modelo 100- Modelo 102. IRPF. Declaración y documento
            de ingreso o devolución.".
        detail_url: Full URL of the expediente's detail page. Per-year
            endpoint for IRPF:
            ``/wlpl/DASR-CORE/AccesoDR<YYYY>RVlt?exp=<id>``.
        mode: Structural read-only marker.
    """

    model_config = _STRICT_FROZEN

    expediente_id: str = Field(min_length=12, max_length=32)
    modelo: str | None = Field(default=None, max_length=8)
    ejercicio: int | None = Field(default=None, ge=2000, le=2099)
    category_path: tuple[str, ...] = Field(min_length=1)
    detail_url: AnyHttpUrl
    mode: Literal["read"] = "read"

    @field_validator("expediente_id")
    @classmethod
    def _expediente_id_shape(cls, value: str) -> str:
        """Reject ``expediente_id`` values that do not match the AEAT shape pattern."""
        if not _EXPEDIENTE_ID_PATTERN.match(value):
            raise SedeValidationError(f"expediente_id does not match AEAT shape: {value!r}")
        return value

    @field_validator("category_path")
    @classmethod
    def _category_path_non_empty(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        """Reject empty / whitespace entries inside ``category_path``."""
        for entry in value:
            if not entry:
                raise SedeValidationError("category_path entries must be non-empty")
        return value


class JustificanteRef(BaseModel):
    """CSV-keyed handle for AEAT's document verifier.

    On every expediente detail page, the *Grabación de la declaración*
    link carries the document's CSV in its ``href``. The same CSV
    unlocks both the HTML cotejo viewer (``CotejoIdSv``) and the raw
    PDF (``CotejoDocIdSv``).

    Attributes:
        csv: Código Seguro de Verificación — AEAT's per-document hash.
        expediente_id: The expediente this CSV belongs to; tracked so
            reconciliation can tie a justificante back to its listing
            row.
        cotejo_url: Viewer URL
            ``/wlpl/KATA-APLI/cotejo/CotejoIdSv?CSV=<csv>``.
        pdf_url: Raw PDF URL
            ``/wlpl/KATA-APLI/cotejo/CotejoDocIdSv?CSV=<csv>``.
        mode: Structural read-only marker.
    """

    model_config = _STRICT_FROZEN

    csv: str = Field(min_length=8, max_length=32)
    expediente_id: str = Field(min_length=12, max_length=32)
    cotejo_url: AnyHttpUrl
    pdf_url: AnyHttpUrl
    mode: Literal["read"] = "read"

    @field_validator("csv")
    @classmethod
    def _csv_shape(cls, value: str) -> str:
        """Reject CSV values that do not match the AEAT uppercase alphanumeric pattern."""
        if value is not None and not _CSV_PATTERN.match(value):
            raise SedeValidationError(f"csv does not match AEAT shape: {value!r}")
        return value


class SedeCapture(BaseModel):
    """One complete sede-side capture of a filing.

    Bundles the expediente listing metadata, the CSV handle, the raw
    PDF bytes, and the captured-at timestamp. Produced by
    :func:`aeat.adapters.outbound.aeat.sede.capture_justificante`; consumed by the reconciler.

    Attributes:
        expediente: The expediente the capture originated from.
        ref: The CSV handle the capture used.
        pdf_bytes: Raw PDF body as served by AEAT.
        pdf_sha256: Lowercase hex sha-256 of ``pdf_bytes``.
        captured_at: UTC timestamp of the fetch completion.
        mode: Structural read-only marker.
    """

    model_config = _STRICT_FROZEN

    expediente: Expediente
    ref: JustificanteRef
    pdf_bytes: bytes
    pdf_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    captured_at: datetime
    mode: Literal["read"] = "read"


class FiledDeclaracionArtefact(BaseModel):
    """One immutable artefact captured from AEAT's filed-declaration surface.

    The artefact is evidence of what AEAT served during a read-only
    session. It is not calculation authority; legal/formula authority
    remains in BOE, AEAT instructions, manuals, and registry definitions.
    """

    model_config = _STRICT_FROZEN

    kind: Literal["register_row", "submitted_file", "declaration_pdf", "justificante_pdf"]
    source_url: AnyHttpUrl
    content_type: str = Field(min_length=1, max_length=255)
    byte_count: int = Field(ge=0)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    captured_at: datetime
    storage_ref: str | None = Field(default=None, min_length=1, max_length=4096)
    mode: Literal["read"] = "read"


class ObservedCasillaValue(BaseModel):
    """One casilla value observed from an AEAT filed-data artefact."""

    model_config = _STRICT_FROZEN

    casilla_id: CasillaId
    value: str = Field(min_length=1, max_length=4096)
    source_artefact_kind: Literal["submitted_file", "declaration_pdf", "justificante_pdf", "derived_registry_formula"]
    source_locator: str = Field(min_length=1, max_length=512)
    confidence: float = Field(ge=0, le=1)
    mode: Literal["read"] = "read"


class IvaCompensationWalletRow(BaseModel):
    """One AEAT wallet row for IVA compensation generated in a source period.

    The row represents external AEAT state, not a filed-declaration casilla. It
    maps one line of AEAT's "Cartera de cuotas de IVA a compensar" detail table:
    the period that generated the credit plus its still-available balance
    (the "Cuota Disponible" column), carried in ``pending_amount``.

    AEAT's read-only cartera consultation surface exposes only the available
    balance per generation period; it does not break out the original generated
    amount or the cumulative applied amount. ``generated_amount`` and
    ``applied_amount`` are therefore optional and stay ``None`` for this surface,
    reserved for a richer AEAT view that itemises the movement columns.
    """

    model_config = _STRICT_FROZEN

    generation_year: int = Field(ge=2000, le=2099)
    generation_period: str = Field(min_length=1, max_length=8)
    generated_amount: Decimal | None = Field(default=None, ge=Decimal("0"))
    applied_amount: Decimal | None = Field(default=None, ge=Decimal("0"))
    pending_amount: Decimal = Field(ge=Decimal("0"))
    raw_label: str | None = Field(default=None, min_length=1, max_length=256)
    mode: Literal["read"] = "read"


class IvaCompensationWalletObservation(BaseModel):
    """Read-only observation of AEAT's IVA compensation wallet.

    Produced by the authenticated Sede wallet reader. Calculation code
    must not consume this record directly; it is raw evidence consumed
    by the reconciliation layer, which emits the effective binding
    decision for Modelo 303 casilla `110`.
    """

    model_config = _STRICT_FROZEN

    taxpayer_nif: str = Field(min_length=1, max_length=32)
    authenticated_identity: str = Field(min_length=1, max_length=32)
    target_modelo: Literal[Modelo.M303] = Modelo.M303
    target_year: int = Field(ge=2000, le=2099)
    target_period: str = Field(min_length=1, max_length=8)
    rows: tuple[IvaCompensationWalletRow, ...] = ()
    total_pending: Decimal = Field(ge=Decimal("0"))
    source_url: AnyHttpUrl
    captured_at: datetime
    raw_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    mode: Literal["read"] = "read"


class FiledDeclaracionObservation(BaseModel):
    """Normalized read-only observation of one filed AEAT declaration.

    A complete observation starts from the register row and may include
    submitted machine-readable data, declaration PDFs, and justificante
    PDFs. Parsed casillas are observations only; downstream calculation
    logic must validate them through registry extraction profiles.
    """

    model_config = _STRICT_FROZEN

    modelo: str = Field(min_length=1, max_length=8)
    ejercicio: int = Field(ge=2000, le=2099)
    period: str = Field(min_length=1, max_length=8)
    expediente_id: str = Field(min_length=12, max_length=32)
    status: str = Field(min_length=1, max_length=32)
    presented_at: datetime
    authenticated_identity: str = Field(min_length=1, max_length=32)
    artefacts: tuple[FiledDeclaracionArtefact, ...] = Field(min_length=1)
    casillas: tuple[ObservedCasillaValue, ...] = ()
    metadata: dict[str, str] = Field(default_factory=dict)
    extraction_coverage: dict[str, float] = Field(default_factory=dict)
    registry_snapshot_id: str | None = Field(default=None, min_length=1, max_length=128)
    mode: Literal["read"] = "read"

    @field_validator("expediente_id")
    @classmethod
    def _observation_expediente_id_shape(cls, value: str) -> str:
        """Reject ``expediente_id`` values that do not match the AEAT shape pattern."""
        if not _EXPEDIENTE_ID_PATTERN.match(value):
            raise SedeValidationError(f"expediente_id does not match AEAT shape: {value!r}")
        return value


__all__ = [
    "Expediente",
    "FiledDeclaracionArtefact",
    "FiledDeclaracionObservation",
    "IvaCompensationWalletObservation",
    "IvaCompensationWalletRow",
    "JustificanteRef",
    "ObservedCasillaValue",
    "SedeCapture",
]
