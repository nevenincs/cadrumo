"""Strict T6 aggregation boundary models."""

from __future__ import annotations

import calendar
import re
from collections.abc import Mapping, Sequence
from datetime import date
from decimal import Decimal
from types import MappingProxyType
from typing import Any, Self

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_serializer, field_validator, model_validator

from ...domain.casillas import PeriodType
from ...domain.deadlines import PeriodKind
from ...domain.formulas._codes import Quarter
from ._errors import AggregationPeriodError, t

_STRICT_FROZEN = ConfigDict(strict=True, frozen=True, extra="forbid")
_PERIOD_RE = re.compile(r"^(?P<year>\d{4})(?:(?:-?Q(?P<quarter>[1-4]))|(?:-(?P<month>0[1-9]|1[0-2])))?$")
_QUARTER_MONTHS: dict[Quarter, tuple[int, int]] = {
    Quarter.Q1: (1, 3),
    Quarter.Q2: (4, 6),
    Quarter.Q3: (7, 9),
    Quarter.Q4: (10, 12),
}


class Period(BaseModel):
    """Inclusive fiscal period used by T6 aggregation."""

    model_config = _STRICT_FROZEN

    raw: str = Field(min_length=4, max_length=16)
    year: int = Field(ge=1990, le=2100)
    quarter: Quarter | None = None
    month: int | None = Field(default=None, ge=1, le=12)
    kind: PeriodKind

    @model_validator(mode="before")
    @classmethod
    def _parse_raw_period(cls, data: Any) -> Any:
        if isinstance(data, cls):
            return data
        if isinstance(data, str):
            text = data.strip().upper()
            match = _PERIOD_RE.fullmatch(text)
            if match is None:
                raise AggregationPeriodError(
                    translated_message=t(
                        "Periodo no valido. Usa YYYY-Qn, YYYYQn, YYYY-MM o YYYY.",
                        "Invalid period. Use YYYY-Qn, YYYYQn, YYYY-MM, or YYYY.",
                        "Ervenytelen idoszak. Hasznald: YYYY-Qn, YYYYQn, YYYY-MM vagy YYYY.",
                    ),
                    context={"period": data},
                )
            year = int(match.group("year"))
            quarter_raw = match.group("quarter")
            month_raw = match.group("month")
            if quarter_raw is not None:
                return {
                    "raw": f"{year}Q{quarter_raw}",
                    "year": year,
                    "quarter": Quarter(f"Q{quarter_raw}"),
                    "month": None,
                    "kind": PeriodKind.QUARTERLY,
                }
            if month_raw is not None:
                return {
                    "raw": f"{year}-{month_raw}",
                    "year": year,
                    "quarter": None,
                    "month": int(month_raw),
                    "kind": PeriodKind.MONTHLY,
                }
            return {
                "raw": str(year),
                "year": year,
                "quarter": None,
                "month": None,
                "kind": PeriodKind.ANNUAL,
            }
        if isinstance(data, Mapping):
            payload = dict(data)
            payload.pop("start", None)
            payload.pop("end", None)
            payload.pop("period_type", None)
            if isinstance(payload.get("quarter"), str):
                payload["quarter"] = Quarter(payload["quarter"])
            if isinstance(payload.get("kind"), str):
                payload["kind"] = PeriodKind(payload["kind"].lower())
            return payload
        return data

    @model_validator(mode="after")
    def _validate_shape(self) -> Self:
        if self.kind is PeriodKind.QUARTERLY and self.quarter is None:
            raise ValueError("quarterly periods require quarter")
        if self.kind is PeriodKind.MONTHLY and self.month is None:
            raise ValueError("monthly periods require month")
        if self.kind is PeriodKind.ANNUAL and (self.quarter is not None or self.month is not None):
            raise ValueError("annual periods cannot carry quarter or month")
        if self.quarter is not None and self.month is not None:
            raise ValueError("period cannot carry both quarter and month")
        return self

    @computed_field  # type: ignore[prop-decorator]
    @property
    def start(self) -> date:
        """Return the first included date."""

        if self.kind is PeriodKind.QUARTERLY:
            assert self.quarter is not None
            month, _ = _QUARTER_MONTHS[self.quarter]
            return date(self.year, month, 1)
        if self.kind is PeriodKind.MONTHLY:
            assert self.month is not None
            return date(self.year, self.month, 1)
        return date(self.year, 1, 1)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def end(self) -> date:
        """Return the last included date."""

        if self.kind is PeriodKind.QUARTERLY:
            assert self.quarter is not None
            _, month = _QUARTER_MONTHS[self.quarter]
            return date(self.year, month, calendar.monthrange(self.year, month)[1])
        if self.kind is PeriodKind.MONTHLY:
            assert self.month is not None
            return date(self.year, self.month, calendar.monthrange(self.year, self.month)[1])
        return date(self.year, 12, 31)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def period_type(self) -> PeriodType:
        """Return the existing casilla-mapping period type where available."""

        if self.kind is PeriodKind.ANNUAL:
            return PeriodType.ANNUAL
        return PeriodType.QUARTERLY

    def contains(self, value: date) -> bool:
        """Return whether ``value`` falls inside this inclusive period."""

        return self.start <= value <= self.end


class CasillaProvenance(BaseModel):
    """Transaction trace for one casilla/category subtotal."""

    model_config = _STRICT_FROZEN

    casilla: str = Field(min_length=2, max_length=8)
    transaction_ids: Sequence[str] = Field(default_factory=tuple)
    subtotal: Decimal
    category_id: str | None = None

    @field_validator("transaction_ids")
    @classmethod
    def _freeze_transaction_ids(cls, value: Sequence[str]) -> tuple[str, ...]:
        return tuple(value)


class CasillaAggregation(BaseModel):
    """Aggregated casilla ledger for one modelo and period."""

    model_config = _STRICT_FROZEN

    modelo: str = Field(min_length=1, max_length=16)
    period: Period
    casilla_values: Mapping[str, Decimal] = Field(default_factory=dict)
    provenance: Sequence[CasillaProvenance] = Field(default_factory=tuple)

    @field_validator("casilla_values")
    @classmethod
    def _freeze_casilla_values(cls, value: Mapping[str, Decimal]) -> Mapping[str, Decimal]:
        return MappingProxyType(dict(sorted(value.items())))

    @field_serializer("casilla_values")
    def _serialize_casilla_values(self, value: Mapping[str, Decimal]) -> dict[str, Decimal]:
        return dict(value)

    @field_validator("provenance")
    @classmethod
    def _freeze_provenance(cls, value: Sequence[CasillaProvenance]) -> tuple[CasillaProvenance, ...]:
        return tuple(value)


__all__ = [
    "CasillaAggregation",
    "CasillaProvenance",
    "Period",
    "PeriodKind",
]
