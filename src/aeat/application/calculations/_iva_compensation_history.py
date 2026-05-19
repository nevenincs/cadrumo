"""Profile-scoped IVA compensation history built from filed Modelo 303s."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field

from ...adapters.outbound.aeat.sede._schema import FiledDeclaracionObservation
from ...adapters.persistence.storage import SensitivityClass, safe_repository_id
from ...adapters.persistence.storage.envelope._secure_repository import SecureBoundRepository

_STRICT_FROZEN = ConfigDict(strict=True, frozen=True, extra="forbid")


class IvaCompensationPeriodState(BaseModel):
    """Latest known Modelo 303 compensation state for one filed period."""

    model_config = _STRICT_FROZEN

    taxpayer_nif: str = Field(min_length=1, max_length=32)
    filing_year: int = Field(ge=2000, le=2099)
    period: str = Field(min_length=1, max_length=8)
    expediente_id: str = Field(min_length=1, max_length=32)
    status: str = Field(min_length=1, max_length=32)
    presented_at: datetime
    prior_pending_amount: Decimal | None = None
    applied_amount: Decimal | None = Field(default=None, ge=Decimal("0"))
    pending_for_later_amount: Decimal | None = Field(default=None, ge=Decimal("0"))
    period_result_amount: Decimal | None = None
    final_result_amount: Decimal | None = None
    generated_amount: Decimal = Field(ge=Decimal("0"))
    available_end_amount: Decimal = Field(ge=Decimal("0"))
    source_observation_key: str = Field(min_length=1, max_length=96)
    source_artefact_sha256: str | None = Field(default=None, min_length=64, max_length=64)


def iva_compensation_period_key(filing_year: int, period: str) -> str:
    """Return the latest-state key for one Modelo 303 period."""

    safe_repository_id(period, context="period")
    if not 2000 <= filing_year <= 2099:
        raise ValueError(f"IVA compensation filing_year {filing_year} out of supported range [2000, 2099]")
    return f"303:{filing_year}:{period}"


class IvaCompensationHistoryRepository(SecureBoundRepository[IvaCompensationPeriodState]):
    """Encrypted profile-local store of Modelo 303 IVA compensation history."""

    namespace: ClassVar[str] = "aeat.calculations.iva_compensation.history"
    sensitivity: ClassVar[SensitivityClass] = SensitivityClass.AUDIT
    schema_version: ClassVar[int] = 1
    payload_type: ClassVar[type[IvaCompensationPeriodState]] = IvaCompensationPeriodState

    def extract_identifier(self, payload: IvaCompensationPeriodState) -> str:
        return iva_compensation_period_key(payload.filing_year, payload.period)

    def load_period(self, filing_year: int, period: str) -> IvaCompensationPeriodState | None:
        """Return latest stored state for one period."""

        return self.load(iva_compensation_period_key(filing_year, period))

    def save_period(self, state: IvaCompensationPeriodState) -> None:
        """Persist latest stored state for one period."""

        self.save(state)

    def list_periods(self) -> tuple[IvaCompensationPeriodState, ...]:
        """Return all stored states in chronological filing order."""

        return tuple(sorted(self.iter_records(), key=lambda item: (item.filing_year, _period_sort_key(item.period))))


def iva_compensation_state_from_filed_observation(
    observation: FiledDeclaracionObservation,
) -> IvaCompensationPeriodState:
    """Build one IVA compensation history state from a filed Modelo 303 observation."""

    if observation.modelo != "303":
        raise ValueError("IVA compensation history only accepts Modelo 303 observations")
    values = _decimal_casilla_values(observation)
    result = values.get("69")
    posterior = values.get("87")
    generated = max(Decimal("0"), -result) if result is not None else Decimal("0")
    available = values.get("iva.compensacion-disponible-fin-periodo")
    if available is None:
        available = (posterior or Decimal("0")) + generated
    source_artefact_sha256 = next(
        (artefact.sha256 for artefact in observation.artefacts if artefact.kind == "submitted_file"),
        None,
    )
    return IvaCompensationPeriodState(
        taxpayer_nif=observation.authenticated_identity,
        filing_year=observation.ejercicio,
        period=observation.period,
        expediente_id=observation.expediente_id,
        status=observation.status,
        presented_at=observation.presented_at,
        prior_pending_amount=values.get("110"),
        applied_amount=values.get("78"),
        pending_for_later_amount=posterior,
        period_result_amount=result,
        final_result_amount=values.get("71"),
        generated_amount=generated,
        available_end_amount=available,
        source_observation_key=f"303:{observation.ejercicio}:{observation.period}:{observation.expediente_id}",
        source_artefact_sha256=source_artefact_sha256,
    )


def _decimal_casilla_values(observation: FiledDeclaracionObservation) -> dict[str, Decimal]:
    values: dict[str, Decimal] = {}
    for casilla in observation.casillas:
        if casilla.source_artefact_kind == "justificante_pdf":
            continue
        try:
            values[casilla.casilla_id] = Decimal(casilla.value)
        except InvalidOperation as exc:
            raise ValueError(f"observed casilla {casilla.casilla_id!r} is not decimal-valued") from exc
    return values


def _period_sort_key(period: str) -> tuple[int, str]:
    upper = period.upper()
    if upper.endswith("T") and upper[:-1].isdigit():
        return (int(upper[:-1]), upper)
    if upper.isdigit():
        return (int(upper), upper)
    if upper == "0A":
        return (99, upper)
    return (100, upper)


__all__ = [
    "IvaCompensationHistoryRepository",
    "IvaCompensationPeriodState",
    "iva_compensation_period_key",
    "iva_compensation_state_from_filed_observation",
]
