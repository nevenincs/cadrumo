"""M100 Anexo C rental-register merge provider.

The existing M100 ruleset (`anexo_c_2024.py / 2025.py / 2026.py`)
treats casillas 0061/0066/0072/0078/0085 as caller-supplied. This
module bridges the rental register to that ruleset:

  - When the rental register has no fincas registered for the
    period (or the ``store`` argument is ``None``), the supplied
    casilla mapping is returned unchanged. This preserves the
    legacy behaviour for callers that maintain their own
    aggregates.

  - When the rental register has fincas, derived aggregates take
    precedence. Casillas not present in the supplied mapping are
    populated; casillas already present are overridden by the
    derived value but their pre-existing value is surfaced via
    :class:`AnexoCMergeReport` so callers can report a discrepancy.

The M100 audit surface (``Engine.audit_against``) consumes the
final dict; the discrepancy classification falls out of the
existing surface.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from ...core.logging import get_logger
from ._anexo_c_aggregator import AnexoCAggregates, compute_anexo_c_aggregates
from ._repository import (
    RentalAmortizationLedgerRepository,
    RentalContractRepository,
    RentalExpenseRepository,
    RentalFincaRepository,
    RentalIncomeRepository,
)

_log = get_logger(__name__)

ANEXO_C_CASILLAS: tuple[str, ...] = ("0061", "0066", "0072", "0078", "0085")
"""The five casillas this provider manages."""


class AnexoCMergeReport(BaseModel):
    """Per-casilla merge outcome surfaced for caller / audit consumption.

    ``effective_casillas`` carries the full superset of casillas
    after the merge — the value M100 should consume. ``overridden``
    flags casillas where the caller-supplied value differed from
    the register-derived value; the caller can use that signal to
    surface a discrepancy.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    register_used: bool
    aggregates: AnexoCAggregates | None
    effective_casillas: dict[str, Decimal]
    overridden: dict[str, tuple[Decimal, Decimal]] = Field(default_factory=dict)


def compute_or_passthrough(
    *,
    period_year: int,
    provided_casillas: Mapping[str, Decimal],
    finca_repo: RentalFincaRepository | None = None,
    contract_repo: RentalContractRepository | None = None,
    income_repo: RentalIncomeRepository | None = None,
    expense_repo: RentalExpenseRepository | None = None,
    ledger_repo: RentalAmortizationLedgerRepository | None = None,
) -> AnexoCMergeReport:
    """Return the effective Anexo C casillas for ``period_year``.

    When any of the repository arguments is ``None``, the rental
    register is treated as absent and the provided casillas are
    returned unchanged (passthrough mode). This is the legacy M100
    behaviour and preserves the operator's existing flow.

    When all repositories are supplied AND the finca repository
    has at least one row, derived aggregates from the register are
    merged with the provided casillas. Register-derived values take
    precedence; the supplied value is surfaced in
    :attr:`AnexoCMergeReport.overridden` when it differs.

    Args:
        period_year: Ejercicio.
        provided_casillas: Caller-supplied 0061/0066/0072/0078/0085
            mapping. Keys not in ``ANEXO_C_CASILLAS`` are passed
            through untouched.
        finca_repo: Optional :class:`RentalFincaRepository`.
        contract_repo: Optional :class:`RentalContractRepository`.
        income_repo: Optional :class:`RentalIncomeRepository`.
        expense_repo: Optional :class:`RentalExpenseRepository`.
        ledger_repo: Optional :class:`RentalAmortizationLedgerRepository`.

    Returns:
        :class:`AnexoCMergeReport` carrying the final casilla values
        and any overrides surfaced.
    """
    repositories_present = (
        finca_repo is not None
        and contract_repo is not None
        and income_repo is not None
        and expense_repo is not None
        and ledger_repo is not None
    )
    if not repositories_present:
        _log.debug("anexo c provider: no repositories supplied; passthrough for period %d", period_year)
        return AnexoCMergeReport(
            register_used=False,
            aggregates=None,
            effective_casillas=dict(provided_casillas),
        )

    assert finca_repo is not None
    assert contract_repo is not None
    assert income_repo is not None
    assert expense_repo is not None
    assert ledger_repo is not None

    if not finca_repo.list_all():
        _log.debug("anexo c provider: no fincas in register; passthrough for period %d", period_year)
        return AnexoCMergeReport(
            register_used=False,
            aggregates=None,
            effective_casillas=dict(provided_casillas),
        )

    aggregates = compute_anexo_c_aggregates(
        period_year=period_year,
        finca_repo=finca_repo,
        contract_repo=contract_repo,
        income_repo=income_repo,
        expense_repo=expense_repo,
        ledger_repo=ledger_repo,
    )
    derived: dict[str, Decimal] = {
        "0061": aggregates.casilla_0061,
        "0066": aggregates.casilla_0066,
        "0072": aggregates.casilla_0072,
        "0078": aggregates.casilla_0078,
        "0085": aggregates.casilla_0085,
    }

    effective = dict(provided_casillas)
    overridden: dict[str, tuple[Decimal, Decimal]] = {}
    for casilla_id, derived_value in derived.items():
        provided_value = provided_casillas.get(casilla_id)
        if provided_value is not None and provided_value != derived_value:
            overridden[casilla_id] = (provided_value, derived_value)
        effective[casilla_id] = derived_value

    if overridden:
        _log.warning(
            "anexo c provider: register-derived values override provided casillas for period %d: %s",
            period_year,
            sorted(overridden.keys()),
        )
    else:
        _log.debug("anexo c provider: register merged for period %d; no casilla conflicts", period_year)
    return AnexoCMergeReport(
        register_used=True,
        aggregates=aggregates,
        effective_casillas=effective,
        overridden=overridden,
    )


__all__ = [
    "ANEXO_C_CASILLAS",
    "AnexoCMergeReport",
    "compute_or_passthrough",
]
