"""Whether a period token names a filing period of one modelo, decided once for every frontend.

A terminal option, a TUI field and a window picker all receive a period as a
token such as ``1T``, ``0A`` or ``07``. Each admits it by the same rule here:
the token must make a typed :class:`~cadrumo.core.period.Period` for the year,
and the modelo's registry editions must declare it. A token the registry
declares but that is no local filing period, such as a census event name,
carries the jurisdiction refusal that modelo is created with.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

from ...core.period import Period, PeriodError
from ...domain.calculations.registry.period_selector_match import selector_token_for_request
from .registry_discovery import declared_modelo_period_tokens
from .work_create_policy import modelo_work_create_refusal_locale_key

if TYPE_CHECKING:
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation

__all__ = [
    "ModeloPeriodAdmission",
    "ModeloPeriodAdmissionOutcome",
    "admit_modelo_period",
]


class ModeloPeriodAdmissionOutcome(StrEnum):
    """What a frontend does with a period token."""

    ADMITTED = "admitted"
    """The token names a filing period this modelo declares."""
    NOT_A_PERIOD = "not_a_period"
    """The token makes no typed period for the year."""
    NOT_DECLARED = "not_declared"
    """The token is a period, but no edition of this modelo declares it."""
    NOT_LOCAL_WORK = "not_local_work"
    """The modelo declares the token, but it is no period local work can be created for."""


@dataclass(frozen=True, slots=True)
class ModeloPeriodAdmission:
    """One period token's admission, with what a frontend needs to say why it was refused."""

    outcome: ModeloPeriodAdmissionOutcome
    period: Period | None
    """The typed period, set exactly when the token is admitted."""
    declared_tokens: tuple[str, ...]
    """Every period token the modelo's editions declare, sorted; empty when the registry declares none."""
    refusal_locale_key: str | None = None
    """The jurisdiction refusal of a modelo whose declared token is no local period."""


def admit_modelo_period(
    modelo: str,
    filing_year: int,
    token: str,
    *,
    operation: PinnedAuthorityOperation,
) -> ModeloPeriodAdmission:
    """Admit ``token`` as a filing period of ``modelo`` in ``filing_year``, or say why not.

    A modelo whose registry declares no period tokens admits any typed period,
    as it did before its tokens were declared.
    """
    code = token.strip()
    declared = declared_modelo_period_tokens(modelo, operation=operation)
    is_declared = selector_token_for_request(declared, code) is not None
    try:
        period = Period.from_year_and_code(filing_year, code)
    except PeriodError:
        refusal = modelo_work_create_refusal_locale_key(modelo.strip()) if is_declared else None
        outcome = (
            ModeloPeriodAdmissionOutcome.NOT_A_PERIOD
            if refusal is None
            else ModeloPeriodAdmissionOutcome.NOT_LOCAL_WORK
        )
        return ModeloPeriodAdmission(outcome, None, declared, refusal)
    if declared and not is_declared and str(period.code) not in declared:
        return ModeloPeriodAdmission(ModeloPeriodAdmissionOutcome.NOT_DECLARED, None, declared)
    return ModeloPeriodAdmission(ModeloPeriodAdmissionOutcome.ADMITTED, period, declared)
