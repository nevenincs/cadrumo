"""Mandatory prorrata especial advisory and its pinned legal authority."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Final

from ...core.json_contract import Notice, NoticeSeverity
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.errors import RegistryValidationError
from ...domain.calculations.registry.facts.resolution import MappingFactQuery, ResolvedMappingFact
from ...domain.calculations.registry.prorrata_register_catalogue import especial_prorrata_register_regime
from ...domain.calculations.registry.schema_base import DateAxis
from ...domain.iva.prorrata import especial_mandatory_rule, is_especial_mandatory
from ...domain.iva.prorrata_especial_parameters import ProrrataEspecialMandatoryParameters

_PRORRATA_SPECIAL_LEGAL_REF_KEY: Final = "prorrata_especial_mandatory.legal_ref"


def _resolve_prorrata_special_legal_ref(*, ejercicio: int, operation: PinnedAuthorityOperation) -> str:
    """Resolve the mandatory-special advisory's legal reference from registry data."""
    resolved = operation.resolve_governed_fact(
        MappingFactQuery(
            fact_id="renta-iva-deduction-ratio-policy",
            date_axis=DateAxis.FILING_PERIOD,
            effective_date=date(ejercicio, 12, 31),
        ),
    )
    if not isinstance(resolved, ResolvedMappingFact):
        raise RegistryValidationError("Renta IVA ratio policy must resolve as a mapping fact")
    for entry in resolved.payload.entries:
        if entry.key == _PRORRATA_SPECIAL_LEGAL_REF_KEY:
            value = str(entry.value).strip()
            if value:
                return value
    raise RegistryValidationError(
        f"Renta IVA ratio policy is missing {_PRORRATA_SPECIAL_LEGAL_REF_KEY!r}",
    )


def build_prorrata_especial_mandatory_advisory(
    *,
    deduction_under_general: Decimal,
    deduction_under_especial: Decimal,
    ejercicio: int,
    parameters: ProrrataEspecialMandatoryParameters,
    operation: PinnedAuthorityOperation,
) -> Notice | None:
    """Build the LIVA art. 103.Dos.2.º mandatory-especial settlement advisory.

    At settlement (4T / 0A), once the ejercicio's deducción computed under the
    general regime and under the especial regime are both known, art. 103.Dos.2.º
    makes prorrata especial OBLIGATORY when the general-regime deduction exceeds
    the especial-regime deduction by the margin in force for that ejercicio —
    ten percent or more from 2015, more than twenty percent before it
    (:func:`~domain.iva.prorrata.is_especial_mandatory`). This surfaces that obligation as
    a NON-BLOCKING warning :class:`~core.json_contract.Notice` so the operator
    elects and records especial before filing; it NEVER refuses the in-progress
    filing (the especial election is a filed taxpayer decision and the
    classification data may still be incomplete). Both compared totals ride on
    ``Notice.context`` alongside the ejercicio and the binding legal reference.

    Returns ``None`` when especial is not obligatory (no noise); the two amounts
    must be non-negative (:func:`is_especial_mandatory` refuses negatives).

    Args:
        deduction_under_general: The ejercicio's total deducible IVA under the
            prorrata general regime (single whole-entity percentage).
        deduction_under_especial: The ejercicio's total deducible IVA under the
            prorrata especial regime (per-input art. 106 routing).
        ejercicio: The filing year being settled (for the message and context).
        parameters: The registry-resolved LIVA art-103.Dos.2 margin and its
            comparison direction for that ejercicio.
        operation: Caller-owned generation-pinned authority operation used to
            resolve the advisory's legal reference.
    """
    if not is_especial_mandatory(
        deduction_under_general,
        deduction_under_especial,
        year=ejercicio,
        parameters=parameters,
    ):
        return None
    rule = especial_mandatory_rule(ejercicio, parameters=parameters)
    exceso = f"en un {rule.margin_percentage}% o más" if rule.inclusive else f"en más de un {rule.margin_percentage}%"
    message = (
        f"Prorrata especial obligatoria para {ejercicio} (LIVA art. 103.Dos.2.º): la deducción por "
        f"prorrata general ({deduction_under_general}) supera {exceso} la deducción por prorrata "
        f"especial ({deduction_under_especial}). Aplique y registre la prorrata especial del ejercicio; "
        "este aviso no bloquea la presentación."
    )
    return Notice(
        severity=NoticeSeverity.WARNING,
        code="modelo.work.calculate.prorrata_especial_obligatoria",
        message=message,
        context={
            "ejercicio": str(ejercicio),
            "regime": especial_prorrata_register_regime().value,
            "deduction_under_general": str(deduction_under_general),
            "deduction_under_especial": str(deduction_under_especial),
            # The art. 103.Dos.2.º margin actually applied, and whether reaching
            # it sufficed. Both are year-dependent (twenty percent exclusive
            # before 2015, ten percent inclusive after), so an operator reading
            # the envelope can tell which redaction produced the obligation.
            "margin_percentage": str(rule.margin_percentage),
            "margin_inclusive": "true" if rule.inclusive else "false",
            "legal_refs": _resolve_prorrata_special_legal_ref(ejercicio=ejercicio, operation=operation),
        },
    )
