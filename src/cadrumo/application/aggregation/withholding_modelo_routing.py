"""Which withholding modelo receives what, as the registry declares it.

The periodic self-assessments, the form each income kind settles through and the
periodic form each annual summary draws on are form data, so the
``withholding-modelo-routing`` fact declares them. Code keeps only what it means by
an income kind and which kinds a given kind of evidence can prove.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from ...core.modelo import Modelo
from ...domain.calculations.registry.form_codes import FormCodes, resolve_form_codes_leased
from ...domain.calculations.registry.governed_fact_scope import GovernedFactSource
from .withholding_recognition import WithholdingIncomeKind

_ROUTING_FACT: Final = "withholding-modelo-routing"

LEDGER_PAID_INCOME_KINDS: Final[frozenset[WithholdingIncomeKind]] = frozenset(
    {WithholdingIncomeKind.WORK, WithholdingIncomeKind.ORDINARY_MOVABLE_CAPITAL},
)
"""The income kinds the paying ledger transaction proves."""

INVOICE_EVIDENCED_INCOME_KINDS: Final[frozenset[WithholdingIncomeKind]] = frozenset(
    {WithholdingIncomeKind.WORK, WithholdingIncomeKind.PROFESSIONAL, WithholdingIncomeKind.URBAN_RENT},
)
"""The income kinds a received invoice proves; capital income is evidenced by its payment."""


@dataclass(frozen=True, slots=True)
class AnnualWithholdingComposition:
    """How one annual modelo composes its per-perceptor-clave source.

    ``periodic_percepciones`` names the periodic modelo whose active projections
    replace the annual window; ``None`` reads the modelo's own window.
    ``capital_disclosure_retenciones`` names the periodic retencion modelo whose
    captured capital allocations materialise disclosure phases next to that window;
    ``None`` adds no phase rows.
    """

    periodic_percepciones: Modelo | None = None
    capital_disclosure_retenciones: Modelo | None = None

    @property
    def periodic_source(self) -> Modelo | None:
        """Return the periodic modelo whose quarterly windows this composition reads, if any."""
        return self.periodic_percepciones or self.capital_disclosure_retenciones


def _routing(authority: GovernedFactSource | None = None) -> FormCodes:
    return resolve_form_codes_leased(_ROUTING_FACT, authority=authority)


def periodic_withholding_modelos(*, authority: GovernedFactSource | None = None) -> tuple[str, ...]:
    """Return the periodic withholding modelos captured withholding is placed in."""
    return _routing(authority).ordered_codes("periodic.modelos")


def modelo_for_income_kind(income_kind: WithholdingIncomeKind) -> str | None:
    """Return the periodic modelo ``income_kind`` settles through, or ``None`` when no route is declared."""
    return _routing().under("income_kind").get(income_kind.value)


def _modelos_for(kinds: frozenset[WithholdingIncomeKind]) -> frozenset[str]:
    routes = _routing().under("income_kind")
    return frozenset(routes[kind.value] for kind in kinds)


def ledger_payment_modelos() -> frozenset[str]:
    """Return the periodic modelos a ledger payment can evidence."""
    return _modelos_for(LEDGER_PAID_INCOME_KINDS)


def invoice_evidence_modelos() -> frozenset[str]:
    """Return the periodic modelos a received invoice can evidence."""
    return _modelos_for(INVOICE_EVIDENCED_INCOME_KINDS)


def formalization_refused_modelos() -> frozenset[str]:
    """Return the modelos a formalization projection never files into."""
    return _routing().codes("formalization.refused.modelos")


def annual_withholding_composition(modelo: str) -> AnnualWithholdingComposition:
    """Return how annual ``modelo`` composes its source; a modelo no route names reads its own window."""
    routing = _routing()
    percepciones = routing.under("annual.periodic_percepciones").get(modelo)
    disclosure = routing.under("annual.capital_disclosure_retenciones").get(modelo)
    return AnnualWithholdingComposition(
        periodic_percepciones=Modelo(percepciones) if percepciones is not None else None,
        capital_disclosure_retenciones=Modelo(disclosure) if disclosure is not None else None,
    )


def annual_source_observations_modelo(modelo: str) -> str | None:
    """Return the periodic modelo whose annual observations ``modelo`` restates, if it declares one."""
    return _routing().under("annual.source_observations").get(modelo)


__all__ = [
    "INVOICE_EVIDENCED_INCOME_KINDS",
    "LEDGER_PAID_INCOME_KINDS",
    "AnnualWithholdingComposition",
    "annual_source_observations_modelo",
    "annual_withholding_composition",
    "formalization_refused_modelos",
    "invoice_evidence_modelos",
    "ledger_payment_modelos",
    "modelo_for_income_kind",
    "periodic_withholding_modelos",
]
