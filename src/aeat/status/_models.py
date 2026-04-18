"""Strict pydantic v2 wire schemas for the AEAT status reader (#43).

Every record is:

- ``strict=True`` — pydantic will not silently coerce types.
- ``frozen=True`` — records are immutable value objects.
- ``extra="forbid"`` — unexpected fields are a parse error, not a
  silent pass-through.

Closed enumerations are :class:`enum.StrEnum` (``AeatStatusKind``,
``PayorKind``). Where the AEAT portal currently hands us free-form
Spanish strings (e.g. expediente ``status``), we accept ``str`` with
a minimum length and plan to narrow to enums in a follow-up once a
full dataset is observed. See the ADR for the rationale.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import StrEnum

from pydantic import AnyHttpUrl, AwareDatetime, BaseModel, ConfigDict, Field

from ..i18n import Translatable


class AeatStatusKind(StrEnum):
    """Top-level status surfaces served by the AEAT Sede Electrónica."""

    EXPEDIENTE = "expediente"
    NOTIFICACION = "notificacion"
    DEVOLUCION = "devolucion"
    BORRADOR_IRPF = "borrador_irpf"
    DATOS_FISCALES = "datos_fiscales"
    CALENDARIO = "calendario"


class PayorKind(StrEnum):
    """Closed set of payor kinds that appear in ``datos fiscales``."""

    EMPLOYER = "employer"
    BANK = "bank"
    PENSION = "pension"
    OTHER = "other"


class _StatusRecord(BaseModel):
    """Common config base for every status-reader wire record."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")


class Expediente(_StatusRecord):
    """A single filing expediente row from *Mis expedientes*.

    ``detail_url`` is optional: AEAT renders an ``Acciones`` / ``Detalle``
    anchor in some campaigns but not others. Populated by
    :func:`aeat.status._parsers.parse_expedientes` when the listing
    carries one; otherwise ``None`` and the consumer constructs the URL
    from ``aeat_status_detail_url_template``.
    """

    expediente_id: str = Field(min_length=1, max_length=64)
    modelo: str = Field(min_length=1, max_length=16)
    period: str = Field(min_length=1, max_length=16)
    status: str = Field(min_length=1, max_length=128)
    presented_at: AwareDatetime
    csv: str | None = Field(default=None, min_length=1, max_length=64)
    justificante_url: AnyHttpUrl | None = None
    detail_url: AnyHttpUrl | None = None
    source_page_url: AnyHttpUrl
    fetched_at: AwareDatetime


class Notificacion(_StatusRecord):
    """A single entry from *Mis notificaciones*.

    ``kind`` is a free-form string in v1; it will be narrowed to an
    enum once the #46 notification triage work lands.
    """

    notificacion_id: str = Field(min_length=1, max_length=64)
    kind: str = Field(min_length=1, max_length=64)
    title: Translatable
    body_excerpt: Translatable
    received_at: AwareDatetime
    due_at: AwareDatetime | None = None
    source_page_url: AnyHttpUrl
    fetched_at: AwareDatetime


class Devolucion(_StatusRecord):
    """A refund row from *Mis devoluciones*."""

    modelo: str = Field(min_length=1, max_length=16)
    period: str = Field(min_length=1, max_length=16)
    amount: Decimal
    status: str = Field(min_length=1, max_length=64)
    expected_payment_date: date | None = None
    source_page_url: AnyHttpUrl
    fetched_at: AwareDatetime


class BorradorIrpf(_StatusRecord):
    """The pre-filled draft state for the annual IRPF return."""

    year: int = Field(ge=2000, le=2100)
    status: str = Field(min_length=1, max_length=64)
    total_a_devolver: Decimal | None = None
    total_a_pagar: Decimal | None = None
    source_page_url: AnyHttpUrl
    fetched_at: AwareDatetime


class Payor(_StatusRecord):
    """A single payor reported to AEAT (employer, bank, …)."""

    name: str = Field(min_length=1, max_length=256)
    tax_id: str = Field(min_length=1, max_length=32)
    kind: PayorKind
    gross_amount: Decimal
    retencion: Decimal
    notes: str = Field(default="", max_length=512)


class DatosFiscales(_StatusRecord):
    """The third-party data AEAT has on the user for a given year."""

    year: int = Field(ge=2000, le=2100)
    payors: tuple[Payor, ...]
    source_page_url: AnyHttpUrl
    fetched_at: AwareDatetime


class CalendarioEntry(_StatusRecord):
    """A single upcoming filing window in the user's personalised calendar."""

    modelo: str = Field(min_length=1, max_length=16)
    period: str = Field(min_length=1, max_length=16)
    opens_on: date
    closes_on: date
    source_page_url: AnyHttpUrl
    fetched_at: AwareDatetime
