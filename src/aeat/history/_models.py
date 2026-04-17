"""Strict pydantic v2 records for the AEAT filing-history reader (#168).

Every type crossing a boundary — wire (per-modelo parsers), disk
(``FilingHistory`` JSON file), or CLI — is a strict+frozen
:class:`pydantic.BaseModel` or a closed :class:`enum.StrEnum`. See
[[2026-04-16-aeat-history-fetch-adr]] decision D4.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import AnyHttpUrl, AwareDatetime, BaseModel, ConfigDict, Field, model_validator

_STRICT_FROZEN = ConfigDict(strict=True, frozen=True, extra="forbid")
_STRICT_MUTABLE = ConfigDict(strict=True, extra="forbid")

# Mirrors the ``_CASILLA_ID_RE`` in ``aeat.casillas.models`` but is
# declared locally per ADR D12: cross-importing a private module from
# a sibling subpackage is forbidden by the public-API discipline.
_CASILLA_ID_RE = re.compile(r"^[0-9A-Z]{2,8}$")
_EXPEDIENTE_ID_RE = re.compile(r"^[0-9A-Z]{1,64}$")


class HistoryModelo(StrEnum):
    """Closed set of modelos supported by the v1 filing-history reader.

    The registered parsers under ``_parsers/`` cover exactly these
    modelos; any other modelo raises
    :class:`HistoryUnsupportedModeloError` at fetch time. See ADR D6.
    """

    MODELO_130 = "130"
    MODELO_303 = "303"
    MODELO_390 = "390"


class FiledModeloMetadata(BaseModel):
    """Header metadata for a filed modelo as surfaced by AEAT.

    Mirrors the subset of :class:`aeat.status.Expediente` fields that
    survive to the detail page, extended with the fields the detail
    page adds (``tax_id`` when the detail form prints it explicitly,
    ``complementaria_of`` when the filing amends a prior one).

    Attributes:
        expediente_id: AEAT-issued stable identifier.
        modelo: AEAT modelo code (``"130"``, ``"303"``, ``"390"``).
        period: Filing period identifier as AEAT prints it
            (``"2025-1T"``, ``"2025"``).
        status: Free-form AEAT status string (``"Presentada"``,
            ``"En tramitación"``, ``"Rechazada"``, …).
        presented_at: UTC timestamp AEAT stamped on the receipt.
        tax_id: NIF/NIE of the filing taxpayer.
        csv: Código Seguro de Verificación if printed on the page.
        justificante_url: URL of the downloadable justificante PDF if
            the row links to one.
        complementaria_of: ``expediente_id`` of the filing this one
            amends, or ``None`` for an ordinaria.
        source_page_url: Detail-page URL the metadata was parsed from.
        fetched_at: UTC wall-clock time the HTML was captured.
    """

    model_config = _STRICT_FROZEN

    expediente_id: str = Field(min_length=1, max_length=64)
    modelo: str = Field(min_length=1, max_length=16)
    period: str = Field(min_length=1, max_length=16)
    status: str = Field(min_length=1, max_length=128)
    presented_at: AwareDatetime
    tax_id: str = Field(min_length=4, max_length=32)
    csv: str | None = Field(default=None, min_length=1, max_length=64)
    justificante_url: AnyHttpUrl | None = None
    complementaria_of: str | None = Field(default=None, max_length=64)
    source_page_url: AnyHttpUrl
    fetched_at: AwareDatetime

    @model_validator(mode="after")
    def _check_invariants(self) -> FiledModeloMetadata:
        if not _EXPEDIENTE_ID_RE.match(self.expediente_id):
            raise ValueError(f"expediente_id must match {_EXPEDIENTE_ID_RE.pattern!r}: {self.expediente_id!r}")
        if self.complementaria_of is not None and not _EXPEDIENTE_ID_RE.match(self.complementaria_of):
            raise ValueError(f"complementaria_of must match {_EXPEDIENTE_ID_RE.pattern!r}: {self.complementaria_of!r}")
        now = datetime.now(UTC)
        if self.presented_at > now:
            raise ValueError(f"presented_at ({self.presented_at}) is in the future (now={now})")
        if self.fetched_at < self.presented_at:
            raise ValueError(f"fetched_at ({self.fetched_at}) is before presented_at ({self.presented_at})")
        return self


class RawCalculationPayload(BaseModel):
    """Casilla→value mapping plus headline totals for a filed modelo.

    Values are carried verbatim from the portal as strings (see ADR
    D3). Casilla-type coercion belongs to the verification engine,
    which owns the join against :class:`aeat.casillas.CasillaRecord`.
    Headline totals are an exception: they are carried as
    :class:`decimal.Decimal` because the portal labels them
    explicitly and downstream reconciliation wants a comparable
    numeric.

    Attributes:
        casillas: Mapping of ``casilla_id`` to the raw portal string.
            Keys must match ``^[0-9A-Z]{2,8}$``. Empty dict is a
            valid payload for rejected or in-tramitación filings.
        total_a_ingresar: "Total a ingresar" if labelled on the page.
        total_a_devolver: "Total a devolver" if labelled on the page.
        resultado_a_compensar: Modelo 303-specific "a compensar"
            figure, if labelled.
        source_page_url: Detail-page URL the payload was parsed from.
        fetched_at: UTC wall-clock time the HTML was captured.
    """

    model_config = _STRICT_FROZEN

    casillas: dict[str, str] = Field(default_factory=dict)
    total_a_ingresar: Decimal | None = None
    total_a_devolver: Decimal | None = None
    resultado_a_compensar: Decimal | None = None
    source_page_url: AnyHttpUrl
    fetched_at: AwareDatetime

    @model_validator(mode="after")
    def _check_casilla_keys(self) -> RawCalculationPayload:
        for key, value in self.casillas.items():
            if not _CASILLA_ID_RE.match(key):
                raise ValueError(f"casilla id {key!r} does not match {_CASILLA_ID_RE.pattern!r}")
            if not isinstance(value, str):  # pragma: no cover - pydantic strict already blocks
                raise ValueError(f"casilla value for {key!r} must be a string, got {type(value).__name__}")
        return self


class FiledModelo(BaseModel):
    """A single filed modelo with its extracted calculations.

    Attributes:
        metadata: Header :class:`FiledModeloMetadata`.
        calculations: Casilla-level :class:`RawCalculationPayload`.
        parse_warnings: Non-fatal observations from the parser —
            e.g. "total_a_ingresar label absent" or
            "casilla table empty". Callers that want strict parsing
            can filter on this field. See ADR D11.
    """

    model_config = _STRICT_FROZEN

    metadata: FiledModeloMetadata
    calculations: RawCalculationPayload
    parse_warnings: tuple[str, ...] = Field(default_factory=tuple)

    @model_validator(mode="after")
    def _cross_field_invariants(self) -> FiledModelo:
        if self.calculations.source_page_url != self.metadata.source_page_url:
            raise ValueError("calculations.source_page_url must equal metadata.source_page_url")
        if self.calculations.fetched_at != self.metadata.fetched_at:
            raise ValueError("calculations.fetched_at must equal metadata.fetched_at")
        return self


class FilingHistory(BaseModel):
    """Typed container mapping ``expediente_id`` to :class:`FiledModelo`.

    This is the single on-disk persistence shape for the filing
    history. Uniqueness is validated — every dict key must equal the
    enclosed record's ``metadata.expediente_id``.

    The container is strict but not frozen so :meth:`upsert` can
    mutate :attr:`entries`. Mutate **only** via :meth:`upsert`;
    direct writes to ``history.entries[key] = record`` bypass the
    ``_check_unique_ids`` validator, which runs on construction
    only.

    Attributes:
        entries: Mapping of ``expediente_id`` to :class:`FiledModelo`.
    """

    model_config = _STRICT_MUTABLE

    entries: dict[str, FiledModelo] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _check_unique_ids(self) -> FilingHistory:
        for key, record in self.entries.items():
            if key != record.metadata.expediente_id:
                raise ValueError(
                    f"FilingHistory key {key!r} does not match metadata.expediente_id {record.metadata.expediente_id!r}"
                )
        return self

    def get(self, expediente_id: str) -> FiledModelo | None:
        """Return the record for ``expediente_id``, or ``None``."""
        return self.entries.get(expediente_id)

    def upsert(self, record: FiledModelo) -> None:
        """Insert or replace ``record`` in the history."""
        self.entries[record.metadata.expediente_id] = record

    def values(self) -> tuple[FiledModelo, ...]:
        """Return every record as an ordered tuple."""
        return tuple(self.entries.values())
