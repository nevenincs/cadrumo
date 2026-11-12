"""Resolve the start of the período impositivo a period without a calendar span is filed for.

A record design that writes the "fecha de inicio del período impositivo" of a
period that has no calendar span of its own, such as the devengo of every
Modelo 202 page 01, needs the entity's período impositivo, not the period's:

- LIS art. 27.1: the período impositivo coincides with the entity's ejercicio
  económico, which the declaración censal states as its closing day and month
  (Modelo 036, casilla [640]).
- LIS art. 40: a pago fraccionado is "a cuenta de la liquidación correspondiente
  al período impositivo que esté en curso el día anterior al inicio" of its
  payment period.
- An entity's first período impositivo begins on its constitution date
  (Modelo 036 [B9]); none began before it.

The facts are the operator's stated ones; an unstated or impossible one refuses
as profile readiness naming every fact to state, never a padded or guessed date.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Final

from ...core.period import Period
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.period import ejercicio_closing_is_valid, instalment_period_in_progress_date, periodo_impositivo_start
from ..filing.producer_snapshot import FilingProducerSnapshotError
from ..operator_actions.preconditions import profile_required_facts_missing_verdict
from .profile_export_binding import resolve_profile_path_values

CIERRE_EJERCICIO_DIA_PATH: Final = "taxpayer_type.cierre_ejercicio_dia"
CIERRE_EJERCICIO_MES_PATH: Final = "taxpayer_type.cierre_ejercicio_mes"
FECHA_CONSTITUCION_PATH: Final = "taxpayer_type.fecha_constitucion"

#: The served words of the refusal: the export needs a fact which is not stated.
_PRODUCER_FACT_REQUIRED_MESSAGE: Final = "application.filing.export.errors.producer_fact_required"
_FACTS_MISSING_REASON: Final = "periodo_impositivo_facts_missing"
_CONSTITUTED_LATER_REASON: Final = "periodo_impositivo_constituted_after_period"


@dataclass(frozen=True, slots=True)
class PeriodoImpositivo:
    """The período impositivo in progress and where the one before it began.

    ``prior_start`` is ``None`` when this is the entity's first período: it was
    constituted within it, so no período impositivo inmediato anterior exists.
    """

    start: date
    prior_start: date | None

    @property
    def prior_lasted_twelve_months(self) -> bool:
        """Whether the immediately preceding período was the twelve months before this one began."""
        return self.prior_start is not None and self.prior_start == _same_day_a_year_earlier(self.start)


def resolve_periodo_impositivo_start(
    *,
    modelo: str,
    bucket_id: str,
    period: Period,
    operation: PinnedAuthorityOperation,
) -> PeriodoImpositivo | None:
    """Return the período impositivo of an instalment, or ``None`` when the period has its own span.

    The facts are read as in force on the day whose período impositivo the
    instalment is on account of. A period with neither a span nor an instalment
    payment month resolves nothing here; its renderer refuses the slot as an
    assembly fault.

    Raises:
        FilingProducerSnapshotError: A fact is unstated or impossible, or the
            stated constitution follows that day; the refusal opens the first.
    """
    if period.has_date_span():
        return None
    on = instalment_period_in_progress_date(period, authority=operation)
    if on is None:
        return None
    return periodo_impositivo_from_facts(
        modelo=modelo,
        on=on,
        profile_values=resolve_profile_path_values(bucket_id=bucket_id, operation=operation, as_of=on),
    )


def periodo_impositivo_start_from_facts(*, modelo: str, on: date, profile_values: Mapping[str, str]) -> date:
    """Return the first day of the período impositivo in progress on ``on`` from the stated facts.

    Raises:
        FilingProducerSnapshotError: As :func:`periodo_impositivo_from_facts`.
    """
    return periodo_impositivo_from_facts(modelo=modelo, on=on, profile_values=profile_values).start


def periodo_impositivo_from_facts(*, modelo: str, on: date, profile_values: Mapping[str, str]) -> PeriodoImpositivo:
    """Return the período impositivo in progress on ``on``, and its predecessor's start, from the stated facts.

    Raises:
        FilingProducerSnapshotError: A fact is unstated or impossible, or the
            stated constitution follows ``on``.
    """
    closing_day = _stated_integer(profile_values.get(CIERRE_EJERCICIO_DIA_PATH))
    closing_month = _stated_integer(profile_values.get(CIERRE_EJERCICIO_MES_PATH))
    constitution = _stated_date(profile_values.get(FECHA_CONSTITUCION_PATH))
    missing = _missing_paths(closing_day, closing_month, constitution)
    if missing or closing_day is None or closing_month is None or constitution is None:
        raise _facts_refusal(modelo, missing, reason=_FACTS_MISSING_REASON)
    start = periodo_impositivo_start(
        on=on, closing_day=closing_day, closing_month=closing_month, constitution=constitution
    )
    if start is None:
        # No período impositivo was in progress: the stated constitution is what contradicts the filing.
        raise _facts_refusal(modelo, (FECHA_CONSTITUCION_PATH,), reason=_CONSTITUTED_LATER_REASON)
    prior_start = periodo_impositivo_start(
        on=start - timedelta(days=1), closing_day=closing_day, closing_month=closing_month, constitution=constitution
    )
    return PeriodoImpositivo(start=start, prior_start=prior_start)


def _same_day_a_year_earlier(day: date) -> date:
    try:
        return day.replace(year=day.year - 1)
    except ValueError:
        # 29 February has no day a common year earlier; that year's ejercicio began on 1 March.
        return day.replace(year=day.year - 1, month=day.month + 1, day=1)


def _missing_paths(closing_day: int | None, closing_month: int | None, constitution: date | None) -> tuple[str, ...]:
    missing: list[str] = []
    closing_stated = closing_day is not None and closing_month is not None
    if closing_stated and not ejercicio_closing_is_valid(closing_day=closing_day, closing_month=closing_month):
        # A day the stated month never has: either half may be the wrong one, so both are named.
        missing.extend((CIERRE_EJERCICIO_DIA_PATH, CIERRE_EJERCICIO_MES_PATH))
    else:
        missing.extend(
            path
            for path, value in ((CIERRE_EJERCICIO_DIA_PATH, closing_day), (CIERRE_EJERCICIO_MES_PATH, closing_month))
            if value is None
        )
    if constitution is None:
        missing.append(FECHA_CONSTITUCION_PATH)
    return tuple(missing)


def _stated_integer(text: str | None) -> int | None:
    stated = (text or "").strip()
    return int(stated) if stated.isdigit() else None


def _stated_date(text: str | None) -> date | None:
    try:
        return date.fromisoformat((text or "").strip())
    except ValueError:
        return None


def _facts_refusal(modelo: str, paths: tuple[str, ...], *, reason: str) -> FilingProducerSnapshotError:
    listed = ", ".join(paths)
    return FilingProducerSnapshotError(
        f"the período impositivo start needs profile facts that are not stated: {listed}",
        translated_message=_PRODUCER_FACT_REQUIRED_MESSAGE,
        context={
            "fact": listed,
            "missing_profile_paths": listed,
            "profile_path": paths[0],
            "reason": reason,
        },
        precondition_verdict=profile_required_facts_missing_verdict(modelo=modelo, field_paths=paths),
    )


__all__ = [
    "CIERRE_EJERCICIO_DIA_PATH",
    "CIERRE_EJERCICIO_MES_PATH",
    "FECHA_CONSTITUCION_PATH",
    "PeriodoImpositivo",
    "periodo_impositivo_from_facts",
    "periodo_impositivo_start_from_facts",
    "resolve_periodo_impositivo_start",
]
