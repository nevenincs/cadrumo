"""Locale-neutral Modelo lifecycle notices captured at the canonical writer.

The public models carry only the facts the existing CLI notice renderers use.
They are built from the writer's bound work unit and calculation revision, so a
frontend never reopens private catalogues after an operation has settled.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Literal, Self

from pydantic import BaseModel, Field, field_validator, model_validator

from ...core.filing_year import FilingYear
from ...core.identity.hex_ids import CalculationRevisionId, WorkUnitId
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.modelo_rendering import modelo_rendering_value
from ...domain.deadlines.models import TaxpayerProfile
from ...domain.modelos.calculation_revision import CalculationRevision
from ...domain.modelos.row_models import Modelo184MemberRow
from ...domain.modelos.work_unit import WorkUnit
from .calculation_revision_gate import require_calculation_revision_coordinates_current
from .work_plazo import M210PlazoResolution, calculated_m210_plazo_resolution

_M210_CONTEXT_KEYS = frozenset(
    {
        "modelo",
        "filing_year",
        "period",
        "resultado",
        "deadline_window_id",
        "opens_on",
        "closes_on",
        "legal_refs",
        "source_refs",
    }
)
_M210_OPTIONAL_CONTEXT_KEYS = frozenset({"tipo_renta_code", "payment_cutoff_on"})


class ModeloM210PlazoAdvisoryV1(BaseModel):
    """Exact registered window facts behind the existing M210 plazo notice."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    version: Literal[1] = 1
    modelo: Literal["210"] = "210"
    filing_year: FilingYear
    period: str = Field(min_length=1, max_length=16)
    resultado: str = Field(min_length=1, max_length=16)
    deadline_window_id: str = Field(min_length=1, max_length=128)
    opens_on: str = Field(min_length=10, max_length=10)
    closes_on: str = Field(min_length=10, max_length=10)
    legal_refs: str = Field(max_length=4096)
    source_refs: str = Field(max_length=4096)
    tipo_renta_code: str | None = Field(default=None, min_length=1, max_length=32)
    payment_cutoff_on: str | None = Field(default=None, min_length=10, max_length=10)

    @field_validator("opens_on", "closes_on", "payment_cutoff_on")
    @classmethod
    def _iso_date(cls, value: str | None) -> str | None:
        """Refuse malformed public dates before a frontend renders them."""
        if value is not None:
            try:
                if date.fromisoformat(value).isoformat() != value:
                    raise ValueError("plazo date must be canonical ISO format")
            except ValueError as exc:
                raise ValueError("plazo date must be canonical ISO format") from exc
        return value

    @model_validator(mode="after")
    def _window_order(self) -> Self:
        """Reject an impossible window rather than emit contradictory dates."""
        if self.opens_on > self.closes_on:
            raise ValueError("plazo opening date follows closing date")
        return self

    @classmethod
    def from_resolution(cls, resolution: M210PlazoResolution) -> Self:
        """Copy only the declared context keys without losing future facts."""
        context = dict(resolution.context)
        if not _M210_CONTEXT_KEYS.issubset(context) or set(context) - (
            _M210_CONTEXT_KEYS | _M210_OPTIONAL_CONTEXT_KEYS
        ):
            raise ValueError("M210 plazo resolution has an unsupported context shape")
        if context["closes_on"] != resolution.closes_on:
            raise ValueError("M210 plazo resolution disagrees with its context")
        try:
            filing_year = int(context["filing_year"])
        except ValueError as exc:
            raise ValueError("M210 plazo resolution has an invalid filing year") from exc
        if str(filing_year) != context["filing_year"]:
            raise ValueError("M210 plazo resolution has a noncanonical filing year")
        return cls(
            filing_year=filing_year,
            period=context["period"],
            resultado=context["resultado"],
            deadline_window_id=context["deadline_window_id"],
            opens_on=context["opens_on"],
            closes_on=resolution.closes_on,
            legal_refs=context["legal_refs"],
            source_refs=context["source_refs"],
            tipo_renta_code=context.get("tipo_renta_code"),
            payment_cutoff_on=context.get("payment_cutoff_on"),
        )

    def to_resolution(self) -> M210PlazoResolution:
        """Restore the existing CLI renderer's locale-neutral input exactly."""
        context = {
            "modelo": self.modelo,
            "filing_year": str(self.filing_year),
            "period": self.period,
            "resultado": self.resultado,
            "deadline_window_id": self.deadline_window_id,
            "opens_on": self.opens_on,
            "closes_on": self.closes_on,
            "legal_refs": self.legal_refs,
            "source_refs": self.source_refs,
        }
        if self.tipo_renta_code is not None:
            context["tipo_renta_code"] = self.tipo_renta_code
        if self.payment_cutoff_on is not None:
            context["payment_cutoff_on"] = self.payment_cutoff_on
        return M210PlazoResolution(closes_on=self.closes_on, context=context)


class Modelo184SocioHandoffV1(BaseModel):
    """One member's attributed base and the registry-declared handoff target."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    nif: str = Field(min_length=1, max_length=32)
    nombre: str = Field(max_length=200)
    porcentaje: str = Field(min_length=1, max_length=128)
    importe: str = Field(min_length=1, max_length=128)
    code: str = Field(min_length=1, max_length=128)
    target_casilla: str = Field(min_length=1, max_length=32)
    legal_refs: str = Field(max_length=4096)

    @field_validator("porcentaje", "importe")
    @classmethod
    def _finite_decimal(cls, value: str) -> str:
        """Preserve decimal precision without accepting nonfinite text."""
        try:
            amount = Decimal(value)
        except InvalidOperation as exc:
            raise ValueError("handoff amount must be decimal text") from exc
        if not amount.is_finite():
            raise ValueError("handoff amount must be finite")
        return value

    @model_validator(mode="after")
    def _share_range(self) -> Self:
        """Match the canonical member-row percentage bound."""
        if not Decimal("0") <= Decimal(self.porcentaje) <= Decimal("100"):
            raise ValueError("handoff percentage is outside [0, 100]")
        return self


class ModeloLifecycleAdvisories(BaseModel):
    """Strict recorded advisory facts bound to one calculated revision."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    version: Literal[1] = 1
    work_unit_id: WorkUnitId
    calculation_revision_id: CalculationRevisionId
    modelo: str = Field(min_length=1, max_length=8)
    filing_year: FilingYear
    period: str = Field(min_length=1, max_length=16)
    m210_plazo: ModeloM210PlazoAdvisoryV1 | None = None
    m184_socio_handoffs: tuple[Modelo184SocioHandoffV1, ...] = Field(default_factory=tuple, max_length=20_000)

    @model_validator(mode="after")
    def _modelo_membership(self) -> Self:
        """Refuse notices attached to a different form or filing period."""
        if self.m210_plazo is not None and (
            self.modelo != "210"
            or self.m210_plazo.filing_year != self.filing_year
            or self.m210_plazo.period != self.period
        ):
            raise ValueError("M210 plazo advisory does not match its work unit")
        if self.m184_socio_handoffs and self.modelo != "184":
            raise ValueError("M184 handoff cannot belong to another modelo")
        return self


def _require_advisory_revision_coordinate(work_unit: WorkUnit, revision: CalculationRevision) -> None:
    """Require stored work-unit coordinates before resolving current authority."""
    coordinate = revision.registry_snapshot_ref
    if (
        revision.work_unit_id != work_unit.work_unit_id
        or str(coordinate.modelo) != str(work_unit.modelo)
        or coordinate.modelo_year != work_unit.filing_year
        or coordinate.period != work_unit.period.registry_token
        or coordinate.revision_id != work_unit.revision_id
    ):
        raise ValueError("calculation revision does not match the work unit")


def build_modelo_lifecycle_advisories(
    *,
    work_unit: WorkUnit,
    revision: CalculationRevision,
    workflow_profile: TaxpayerProfile,
    operation: PinnedAuthorityOperation,
) -> ModeloLifecycleAdvisories:
    """Capture canonical advisory facts before the operation releases authority."""
    _require_advisory_revision_coordinate(work_unit, revision)
    require_calculation_revision_coordinates_current(revision, operation=operation)

    m210_plazo = None
    if str(work_unit.modelo) == "210":
        resolution = calculated_m210_plazo_resolution(
            work_unit=work_unit,
            revision=revision,
            workflow_profile=workflow_profile,
            operation=operation,
        )
        if resolution is not None:
            m210_plazo = ModeloM210PlazoAdvisoryV1.from_resolution(resolution)

    handoffs: tuple[Modelo184SocioHandoffV1, ...] = ()
    if str(work_unit.modelo) == "184":
        rows = tuple(row for row in revision.detail_rows if isinstance(row, Modelo184MemberRow))
        if rows:
            code = modelo_rendering_value("m184.socio_handoff.code", authority=operation)
            target_casilla = modelo_rendering_value("m184.socio_handoff.target_casilla", authority=operation)
            legal_refs = modelo_rendering_value("m184.socio_handoff.legal_refs", authority=operation)
            handoffs = tuple(
                Modelo184SocioHandoffV1(
                    nif=row.nif,
                    nombre=row.nombre,
                    porcentaje=str(row.porcentaje),
                    importe=str(row.importe),
                    code=code,
                    target_casilla=target_casilla,
                    legal_refs=legal_refs,
                )
                for row in rows
            )

    return ModeloLifecycleAdvisories(
        work_unit_id=work_unit.work_unit_id,
        calculation_revision_id=revision.calculation_revision_id,
        modelo=str(work_unit.modelo),
        filing_year=work_unit.filing_year,
        period=work_unit.period.registry_token,
        m210_plazo=m210_plazo,
        m184_socio_handoffs=handoffs,
    )


__all__ = [
    "Modelo184SocioHandoffV1",
    "ModeloLifecycleAdvisories",
    "ModeloM210PlazoAdvisoryV1",
    "build_modelo_lifecycle_advisories",
]
