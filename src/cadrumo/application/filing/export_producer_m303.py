"""Modelo 303 lexical projection shared by the declaration export and the declaration form.

The export renders these lexicals into the filing file and the form shows the
same ones, so both read a Modelo 303 identification answer from this module.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date
from typing import Final

from ...core.filing_producer_key import FilingProducerKey
from ...core.period import Period
from ...domain.calculations.registry.form_codes import FormCodes, resolve_form_codes
from ...domain.calculations.registry.m303_schema_vocabulary import (
    m303_regime_composition_export_code,
    m303_tax_territory_exclusively_foral_mark,
    m303_tax_territory_is_foral,
)
from ...domain.calculations.registry.prorrata_register_catalogue import (
    opcion_prorrata_transition,
    revocacion_prorrata_transition,
)
from ...domain.deadlines.models import ModeloIVAProfile
from ...domain.iva.refund_eligibility import is_last_filing_period_of_year
from ...domain.modelos.calculation_revision_m303_evidence import (
    M303Exonerado390FilingEvidence,
    M303InsolvencyFilingFact,
    M303InsolvencyFilingSubtype,
)
from ...domain.modelos.calculation_revision_m303_handoff import M303FilingInstanceEvidence
from ..aggregation.m303_arrivals import M303ProrrataTransitionArrival
from .producer_snapshot import M303FilingFacts


@dataclass(frozen=True)
class M303ProfileLexicals:
    """Rendered lexical values for a Modelo 303 profile's enrolment facts."""

    redeme_enrolled: str | None = None
    exclusively_foral: str | None = None
    regime_composition_code: str | None = None
    cash_accounting_regime_enrolled: str | None = None
    voluntary_sii_enrolled: str | None = None
    hydrocarbon_deposit_advance_payment_deduction_entitled: str | None = None
    is_foral: bool = False


@dataclass(frozen=True)
class M303FilingLexicals:
    """Rendered lexical values for a Modelo 303 filing's period-specific facts."""

    joint_return_elected: str | None = None
    annual_volume_nonzero: str | None = None
    recipient_of_cash_accounting_operations: str | None = None
    prorrata_special_option: str | None = None
    prorrata_special_revocation: str | None = None
    insolvency_declared: str | None = None
    insolvency_judicial_order_date: str | None = None
    insolvency_filing_subtype: str | None = None
    exonerado_390_applicable: str | None = None
    prorrata_transition_applicable: bool | None = None
    """Whether the period asks the prorrata election questions; ``None`` while the register is not read."""


@dataclass(frozen=True)
class M303ForalLexicals:
    """Rendered lexical values for a Modelo 303 foral prorrata election."""

    prorrata_special_option: str | None
    prorrata_special_revocation: str | None


def _m303_lexical_producer_values(
    m303_profile: M303ProfileLexicals,
    m303_filing: M303FilingLexicals,
) -> dict[FilingProducerKey, object]:
    """Key every Modelo 303 lexical by the producer identity the export layout addresses."""
    return {
        FilingProducerKey.M303_REDEME_ENROLLED: m303_profile.redeme_enrolled,
        FilingProducerKey.M303_EXCLUSIVELY_FORAL: m303_profile.exclusively_foral,
        FilingProducerKey.M303_REGIME_COMPOSITION_CODE: m303_profile.regime_composition_code,
        FilingProducerKey.M303_ANNUAL_VOLUME_NONZERO: m303_filing.annual_volume_nonzero,
        FilingProducerKey.M303_JOINT_RETURN_ELECTED: m303_filing.joint_return_elected,
        FilingProducerKey.M303_CASH_ACCOUNTING_REGIME_ENROLLED: m303_profile.cash_accounting_regime_enrolled,
        FilingProducerKey.M303_RECIPIENT_OF_CASH_ACCOUNTING_OPERATIONS: (
            m303_filing.recipient_of_cash_accounting_operations
        ),
        FilingProducerKey.M303_PRORRATA_SPECIAL_OPTION: m303_filing.prorrata_special_option,
        FilingProducerKey.M303_PRORRATA_SPECIAL_REVOCATION: m303_filing.prorrata_special_revocation,
        FilingProducerKey.M303_INSOLVENCY_DECLARED: m303_filing.insolvency_declared,
        FilingProducerKey.M303_INSOLVENCY_JUDICIAL_ORDER_DATE: m303_filing.insolvency_judicial_order_date,
        FilingProducerKey.M303_INSOLVENCY_FILING_SUBTYPE: m303_filing.insolvency_filing_subtype,
        FilingProducerKey.M303_VOLUNTARY_SII_ENROLLED: m303_profile.voluntary_sii_enrolled,
        FilingProducerKey.M303_EXONERADO_390_APPLICABLE: m303_filing.exonerado_390_applicable,
        FilingProducerKey.M303_HYDROCARBON_DEPOSIT_ADVANCE_PAYMENT_DEDUCTION_ENTITLED: (
            m303_profile.hydrocarbon_deposit_advance_payment_deduction_entitled
        ),
    }


#: Every producer identity the Modelo 303 lexicals feed, read from the one mapping that keys them.
M303_LEXICAL_PRODUCER_KEYS: Final = frozenset(
    _m303_lexical_producer_values(M303ProfileLexicals(), M303FilingLexicals())
)


def m303_context_producer_values(
    m303_profile: M303ProfileLexicals,
    m303_filing: M303FilingLexicals,
) -> dict[FilingProducerKey, object]:
    """Resolve the Modelo 303 producer values exactly as the export renders them, foral override included.

    Callers that hold only part of the facts pass lexicals built from that part.
    A lexical they do not hold stays ``None``, never a default answer.
    """
    values = _m303_lexical_producer_values(m303_profile, m303_filing)
    _apply_foral_m303_overrides(values, m303_profile, m303_filing)
    return values


def _apply_foral_m303_overrides(
    values: dict[FilingProducerKey, object],
    m303_profile: M303ProfileLexicals,
    m303_filing: M303FilingLexicals,
) -> None:
    if not m303_profile.is_foral:
        return
    foral = m303_foral_lexicals(m303_filing)
    codes = _m303_form_codes()
    not_answered = codes.code("answer.no")
    values.update(
        {
            FilingProducerKey.M303_REDEME_ENROLLED: not_answered,
            FilingProducerKey.M303_EXCLUSIVELY_FORAL: m303_profile.exclusively_foral,
            FilingProducerKey.M303_REGIME_COMPOSITION_CODE: codes.code("regime_composition.general_only"),
            FilingProducerKey.M303_JOINT_RETURN_ELECTED: not_answered,
            FilingProducerKey.M303_CASH_ACCOUNTING_REGIME_ENROLLED: not_answered,
            FilingProducerKey.M303_RECIPIENT_OF_CASH_ACCOUNTING_OPERATIONS: not_answered,
            FilingProducerKey.M303_PRORRATA_SPECIAL_OPTION: foral.prorrata_special_option,
            FilingProducerKey.M303_PRORRATA_SPECIAL_REVOCATION: foral.prorrata_special_revocation,
            FilingProducerKey.M303_INSOLVENCY_DECLARED: None,
            FilingProducerKey.M303_INSOLVENCY_JUDICIAL_ORDER_DATE: None,
            FilingProducerKey.M303_INSOLVENCY_FILING_SUBTYPE: None,
            FilingProducerKey.M303_VOLUNTARY_SII_ENROLLED: not_answered,
            FilingProducerKey.M303_EXONERADO_390_APPLICABLE: not_answered,
            FilingProducerKey.M303_ANNUAL_VOLUME_NONZERO: not_answered,
            FilingProducerKey.M303_HYDROCARBON_DEPOSIT_ADVANCE_PAYMENT_DEDUCTION_ENTITLED: not_answered,
        },
    )


def m303_profile_lexicals(
    iva_profile: ModeloIVAProfile | None,
    period: Period | None,
) -> M303ProfileLexicals:
    """Project the Modelo 303 IVA profile into rendered lexicals dated by the filing ``period``, when known."""
    if iva_profile is None:
        return M303ProfileLexicals()
    a30 = (
        yes_no(iva_profile.hydrocarbon_deposit_advance_payment_deduction_entitled)
        if period is not None and m303_a30_entitlement_applicable(period)
        else _m303_outside_period()
        if period is not None
        else None
    )
    territory_date = date(period.filing_year, 1, 1) if period is not None else None
    is_foral = m303_tax_territory_is_foral(
        iva_profile.tax_territory,
        effective_date=territory_date,
    )
    exclusively_foral = m303_tax_territory_exclusively_foral_mark(
        iva_profile.tax_territory,
        effective_date=territory_date,
    )
    return M303ProfileLexicals(
        redeme_enrolled=yes_no(iva_profile.redeme_enrolled),
        exclusively_foral=exclusively_foral,
        regime_composition_code=(
            m303_regime_composition_export_code(iva_profile.regime_composition)
            if iva_profile.regime_composition is not None
            else None
        ),
        cash_accounting_regime_enrolled=yes_no(iva_profile.cash_accounting_regime_enrolled),
        voluntary_sii_enrolled=yes_no(iva_profile.voluntary_sii_enrolled),
        hydrocarbon_deposit_advance_payment_deduction_entitled=a30,
        is_foral=is_foral,
    )


def m303_filing_lexicals(m303_facts: M303FilingFacts | None) -> M303FilingLexicals:
    """Project the Modelo 303 filing facts into their rendered period-specific lexicals."""
    if m303_facts is None:
        return M303FilingLexicals()
    transition = m303_facts.prorrata_transition
    transition_applicable = transition.is_applicable
    special_option, special_revocation = _m303_prorrata_election_lexicals(transition, transition_applicable)
    return replace(
        _m303_evidence_lexicals(
            period=m303_facts.period,
            joint_return_elected=m303_facts.joint_return_elected,
            annual_volume_nonzero=m303_facts.annual_volume_nonzero,
            insolvency=m303_facts.insolvency,
            exonerado_390=m303_facts.exonerado_390,
        ),
        recipient_of_cash_accounting_operations=yes_no(
            m303_facts.supplier_regime.recipient_of_cash_accounting_operations,
        ),
        prorrata_special_option=special_option,
        prorrata_special_revocation=special_revocation,
        prorrata_transition_applicable=transition_applicable,
    )


def m303_evidence_lexicals(evidence: M303FilingInstanceEvidence) -> M303FilingLexicals:
    """Project the operator-selected filing evidence alone; the ledger and register arrivals stay unknown."""
    return _m303_evidence_lexicals(
        period=evidence.period,
        joint_return_elected=evidence.joint_return_elected,
        annual_volume_nonzero=evidence.annual_volume_nonzero,
        insolvency=evidence.insolvency,
        exonerado_390=evidence.exonerado_390,
    )


def _m303_evidence_lexicals(
    *,
    period: Period,
    joint_return_elected: bool,
    annual_volume_nonzero: bool | None,
    insolvency: M303InsolvencyFilingFact | None,
    exonerado_390: M303Exonerado390FilingEvidence | None,
) -> M303FilingLexicals:
    # DP30301 Nota 4: the exemption is a question only in the last period; every other period prints "0".
    final_exonerado = exonerado_390 if is_last_filing_period_of_year(period) else None
    insolvency_declared, insolvency_date, insolvency_subtype = _m303_insolvency_lexicals(insolvency)
    return M303FilingLexicals(
        joint_return_elected=yes_no(joint_return_elected),
        # DP30301 Nota 3: the art. 121 answer is printed only by a filer exempt from Modelo 390, and only in the
        # last period; every other filing carries "0" whatever the operator answered.
        annual_volume_nonzero=_m303_annual_volume_lexical(annual_volume_nonzero, final_exonerado),
        insolvency_declared=insolvency_declared,
        insolvency_judicial_order_date=insolvency_date,
        insolvency_filing_subtype=insolvency_subtype,
        exonerado_390_applicable=_m303_outside_period()
        if final_exonerado is None
        else yes_no(final_exonerado.applicable),
    )


def _m303_annual_volume_lexical(
    annual_volume_nonzero: bool | None,
    final_exonerado: M303Exonerado390FilingEvidence | None,
) -> str:
    if final_exonerado is None or not final_exonerado.applicable or annual_volume_nonzero is None:
        return _m303_outside_period()
    return yes_no(annual_volume_nonzero)


def _m303_prorrata_election_lexicals(
    transition: M303ProrrataTransitionArrival,
    applicable: bool,
) -> tuple[str | None, str | None]:
    if not applicable:
        outside = _m303_outside_period()
        return outside, outside
    return (
        yes_no(transition.transition == opcion_prorrata_transition()),
        yes_no(transition.transition == revocacion_prorrata_transition()),
    )


def _m303_insolvency_lexicals(
    insolvency: M303InsolvencyFilingFact | None,
) -> tuple[str, str | None, str | None]:
    if insolvency is None:
        return yes_no(False), None, None
    subtype = _m303_form_codes().code(f"insolvency_subtype.{_M303_INSOLVENCY_SUBTYPE_KEYS[insolvency.subtype]}")
    return yes_no(True), insolvency.judicial_order_date.strftime("%d%m%Y"), subtype


def m303_foral_lexicals(m303_filing: M303FilingLexicals) -> M303ForalLexicals:
    """Project the Modelo 303 filing lexicals into the foral prorrata election lexicals."""
    applicable = m303_filing.prorrata_transition_applicable
    value = None if applicable is None else yes_no(False) if applicable else _m303_outside_period()
    return M303ForalLexicals(prorrata_special_option=value, prorrata_special_revocation=value)


_M303_FORM_CODES_FACT = "modelo-303-identification-form-codes"
_M303_INSOLVENCY_SUBTYPE_KEYS = {
    M303InsolvencyFilingSubtype.PRE_ORDER: "pre_order",
    M303InsolvencyFilingSubtype.POST_ORDER: "post_order",
}


def _m303_form_codes() -> FormCodes:
    return resolve_form_codes(_M303_FORM_CODES_FACT)


def _m303_outside_period() -> str:
    """Return the code a question not asked in this period prints."""
    return _m303_form_codes().code("answer.outside_period")


def yes_no(value: bool) -> str:
    return _m303_form_codes().code("answer.yes" if value else "answer.no")


def m303_a30_entitlement_applicable(period: Period) -> bool:
    """Whether the period asks the hydrocarbon deposit advance payment deduction question."""
    return period.registry_token in _m303_form_codes().codes("hydrocarbon_entitlement.applicable_periods")


__all__ = [
    "M303_LEXICAL_PRODUCER_KEYS",
    "M303FilingLexicals",
    "M303ForalLexicals",
    "M303ProfileLexicals",
    "m303_a30_entitlement_applicable",
    "m303_context_producer_values",
    "m303_evidence_lexicals",
    "m303_filing_lexicals",
    "m303_foral_lexicals",
    "m303_profile_lexicals",
]
