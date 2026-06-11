"""Strict boundary models for financial transaction aggregation.

Carries the :class:`Period` parser, the per-casilla
:class:`CasillaProvenance` trace, and the aggregated
:class:`CasillaAggregation` ledger shape.
"""

from __future__ import annotations

import calendar
import re
from collections.abc import Mapping, Sequence
from datetime import date
from decimal import Decimal
from enum import StrEnum
from types import MappingProxyType
from typing import Annotated, Self

from pydantic import (
    BaseModel,
    BeforeValidator,
    Field,
    computed_field,
    field_serializer,
    field_validator,
    model_validator,
)

from ...core._models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core.aggregation import PeriodKind
from ...core.i18n import Translatable as tr
from ...domain.categories import SpendingCategory
from ._errors import AggregationPeriodError


def _coerce_spending_category(value: object) -> object:
    """Accept the canonical SpendingCategory value string AND the enum member.

    Strict pydantic refuses str→Enum coercion by default. Wrapping the
    field with a ``BeforeValidator`` keeps registry/JSON payloads (which
    carry the enum's ``.value`` string) loadable without weakening
    strict-mode for every other field on the model.
    """
    if value is None or isinstance(value, SpendingCategory):
        return value
    if isinstance(value, str):
        return SpendingCategory(value)
    return value


_SpendingCategoryField = Annotated[SpendingCategory, BeforeValidator(_coerce_spending_category)]

_PERIOD_RE = re.compile(r"^(?P<year>\d{4})(?:(?:-?Q(?P<quarter>[1-4]))|(?:-(?P<month>0[1-9]|1[0-2])))?$")


class Quarter(StrEnum):
    """Calendar quarter token used by aggregation period parsing."""

    Q1 = "Q1"
    Q2 = "Q2"
    Q3 = "Q3"
    Q4 = "Q4"


class PeriodType(StrEnum):
    """Aggregation period cadence used by transaction rollups."""

    QUARTERLY = "quarterly"
    ANNUAL = "annual"


_QUARTER_MONTHS: dict[Quarter, tuple[int, int]] = {
    Quarter.Q1: (1, 3),
    Quarter.Q2: (4, 6),
    Quarter.Q3: (7, 9),
    Quarter.Q4: (10, 12),
}


class Period(BaseModel):
    """Inclusive fiscal period used by transaction aggregation.

    Accepts ``YYYY``, ``YYYY-MM``, ``YYYY-Qn``, or ``YYYYQn`` strings
    via the :meth:`_parse_raw_period` validator and exposes derived
    bounds via :attr:`start`, :attr:`end`, and :attr:`period_type`.

    Attributes:
        raw: Original string token after normalisation.
        year: Calendar year, inclusive [1990, 2100].
        quarter: Optional quarter for quarterly periods.
        month: Optional 1-based month for monthly periods.
        kind: The :class:`PeriodKind` discriminator.
    """

    model_config = _STRICT_FROZEN

    raw: str = Field(min_length=4, max_length=16)
    year: int = Field(ge=1990, le=2100)
    quarter: Quarter | None = None
    month: int | None = Field(default=None, ge=1, le=12)
    kind: PeriodKind

    @model_validator(mode="before")
    @classmethod
    def _parse_raw_period(cls, data: object) -> object:
        if isinstance(data, cls):
            return data
        if isinstance(data, str):
            text = data.strip().upper()
            match = _PERIOD_RE.fullmatch(text)
            if match is None:
                raise AggregationPeriodError(
                    message=tr("aggregation.period.parse_error"),
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
                payload["kind"] = PeriodKind(payload["kind"])
            return payload
        return data

    @model_validator(mode="after")
    def _validate_shape(self) -> Self:
        if self.kind is PeriodKind.QUARTERLY and self.quarter is None:
            raise AggregationPeriodError(
                message=tr("aggregation.models.errors.quarter_required"),
            )
        if self.kind is PeriodKind.MONTHLY and self.month is None:
            raise AggregationPeriodError(
                message=tr("aggregation.models.errors.month_required"),
            )
        if self.kind is PeriodKind.ANNUAL and (self.quarter is not None or self.month is not None):
            raise AggregationPeriodError(
                message=tr("aggregation.models.errors.annual_period_mixed"),
            )
        if self.quarter is not None and self.month is not None:
            raise AggregationPeriodError(
                message=tr("aggregation.models.errors.period_type_ambiguous"),
            )
        return self

    @computed_field
    @property
    def start(self) -> date:
        """Return the first :class:`~datetime.date` included in the period."""
        if self.kind is PeriodKind.QUARTERLY:
            assert self.quarter is not None
            month, _ = _QUARTER_MONTHS[self.quarter]
            return date(self.year, month, 1)
        if self.kind is PeriodKind.MONTHLY:
            assert self.month is not None
            return date(self.year, self.month, 1)
        return date(self.year, 1, 1)

    @computed_field
    @property
    def end(self) -> date:
        """Return the last :class:`~datetime.date` included in the period."""
        if self.kind is PeriodKind.QUARTERLY:
            assert self.quarter is not None
            _, month = _QUARTER_MONTHS[self.quarter]
            return date(self.year, month, calendar.monthrange(self.year, month)[1])
        if self.kind is PeriodKind.MONTHLY:
            assert self.month is not None
            return date(self.year, self.month, calendar.monthrange(self.year, self.month)[1])
        return date(self.year, 12, 31)

    @computed_field
    @property
    def period_type(self) -> PeriodType:
        """Return the :class:`PeriodType` matching the aggregation period cadence."""
        if self.kind is PeriodKind.ANNUAL:
            return PeriodType.ANNUAL
        return PeriodType.QUARTERLY

    def contains(self, value: date) -> bool:
        """Return whether ``value`` falls inside this inclusive period.

        Args:
            value: A calendar date to test.

        Returns:
            ``True`` if :attr:`start` <= ``value`` <= :attr:`end`.
        """
        return self.start <= value <= self.end

    @classmethod
    def from_year_and_token(cls, *, year: int, token: str) -> Period:
        """Build a :class:`Period` from a separate filing year and a bare AEAT token.

        This is the canonical operator-grammar constructor: the filing year and
        the registry period token always travel as a ``(year, token)`` pair, never
        as a single combined calendar string. The ledger filters by a calendar
        date span, so only the span-shaped tokens are convertible:

        - ``1T``-``4T`` (quarters)
        - ``0A`` (annual)
        - ``01``-``12`` (months)

        Args:
            year: Filing year (e.g. ``2024``).
            token: A bare span-shaped AEAT period token.

        Raises:
            AggregationPeriodError: When ``token`` is not a span-shaped token the
                ledger can filter by (instalment claves ``1P``-``4P`` and the
                extended union members ``EXT-*`` / ``AD-HOC`` / ``EVENT-N`` carry
                no ledger date span).
        """
        normalised = token.strip().upper()
        if len(normalised) == 2 and normalised.endswith("T") and normalised[0] in "1234":
            return cls.model_validate(
                {
                    "raw": f"{year}Q{normalised[0]}",
                    "year": year,
                    "quarter": Quarter(f"Q{normalised[0]}"),
                    "month": None,
                    "kind": PeriodKind.QUARTERLY,
                },
            )
        if normalised == "0A":
            return cls.model_validate(
                {"raw": str(year), "year": year, "quarter": None, "month": None, "kind": PeriodKind.ANNUAL},
            )
        if len(normalised) == 2 and normalised.isdigit() and 1 <= int(normalised) <= 12:
            return cls.model_validate(
                {
                    "raw": f"{year}-{normalised}",
                    "year": year,
                    "quarter": None,
                    "month": int(normalised),
                    "kind": PeriodKind.MONTHLY,
                },
            )
        raise AggregationPeriodError(
            message=tr("aggregation.period.parse_error"),
            context={"period": token},
        )

    @property
    def registry_token(self) -> str:
        """Return the bare AEAT registry token (``1T``-``4T`` / ``0A`` / ``01``-``12``)."""
        if self.kind is PeriodKind.QUARTERLY:
            assert self.quarter is not None
            return f"{self.quarter.value[1]}T"
        if self.kind is PeriodKind.MONTHLY:
            assert self.month is not None
            return f"{self.month:02d}"
        return "0A"


class CasillaProvenance(BaseModel):
    """Transaction trace backing one (casilla, category) subtotal.

    Attributes:
        casilla: Target casilla code (e.g. ``"02"``).
        transaction_ids: Sorted, frozen tuple of contributing
            transaction IDs.
        subtotal: Sum of contributions for this casilla/category pair.
        category_id: Optional category identifier when the contribution
            came from an expense bucket.
    """

    model_config = _STRICT_FROZEN

    casilla: str = Field(min_length=2, max_length=8)
    transaction_ids: Sequence[str] = Field(default_factory=tuple)
    subtotal: Decimal
    # Typed SpendingCategory enum (was bare ``str`` before R025/R026
    # follow-up). The BeforeValidator coerces canonical string inputs
    # to the enum member so existing TOML/JSON payloads round-trip
    # without registry-data changes. Downstream comparisons no longer
    # need a manual ``normalize_spending_category`` step.
    category_id: _SpendingCategoryField | None = None

    @field_validator("transaction_ids")
    @classmethod
    def _freeze_transaction_ids(cls, value: Sequence[str]) -> tuple[str, ...]:
        """Freeze ``value`` into an immutable tuple."""
        return tuple(value)


class CasillaAggregation(BaseModel):
    """Aggregated casilla ledger for one modelo and period.

    Attributes:
        modelo: Modelo identifier (``ModeloCode.value``) the totals
            belong to.
        period: The :class:`Period` covered.
        casilla_values: Mapping of casilla code to summed
            :class:`~decimal.Decimal` value, sorted and frozen.
        provenance: Tuple of :class:`CasillaProvenance` rows tracing
            each contribution back to its source transactions.
    """

    model_config = _STRICT_FROZEN

    modelo: str = Field(min_length=1, max_length=16)
    period: Period
    casilla_values: Mapping[str, Decimal] = Field(default_factory=dict)
    provenance: Sequence[CasillaProvenance] = Field(default_factory=tuple)

    @field_validator("casilla_values")
    @classmethod
    def _freeze_casilla_values(cls, value: Mapping[str, Decimal]) -> Mapping[str, Decimal]:
        """Return ``value`` as a sorted, immutable :class:`MappingProxyType`."""
        return MappingProxyType(dict(sorted(value.items())))

    @field_serializer("casilla_values")
    def _serialize_casilla_values(self, value: Mapping[str, Decimal]) -> dict[str, Decimal]:
        """Serialise the immutable view back to a plain ``dict`` for JSON output."""
        return dict(value)

    @field_validator("provenance")
    @classmethod
    def _freeze_provenance(cls, value: Sequence[CasillaProvenance]) -> tuple[CasillaProvenance, ...]:
        """Freeze ``value`` into an immutable tuple."""
        return tuple(value)


__all__ = [
    "CasillaAggregation",
    "CasillaProvenance",
    "Period",
    "PeriodKind",
    "PeriodType",
    "Quarter",
]
