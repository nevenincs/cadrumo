"""Document rules outside the invoice figures, each answering with a stable finding code.

A rule answers with an :class:`InvoiceRuleFinding` rather than raising, and
:func:`invoice_rule_refusal` turns that finding into the refusal the invoice
model raises. The arithmetic rules answer the same way from
:mod:`cadrumo.domain.invoices.figures`.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum
from typing import Final

from .errors import InvoiceValidationError

#: The catalogue root under which each document rule's finding is worded, one key per finding code.
INVOICE_RULE_FINDING_WORDS_ROOT: Final = "application.invoices.figures_preview.rule_finding"


class InvoiceRuleFindingCode(StrEnum):
    """Stable, closed names of what a rule outside the figures found on one invoice document."""

    SERIES_REQUIRED_FOR_RECTIFICATIVA = "series_required_for_rectificativa"
    RECTIFIED_INVOICE_REQUIRED = "rectified_invoice_required"
    RECTIFIED_INVOICE_NOT_ALLOWED = "rectified_invoice_not_allowed"
    SIMPLIFICADA_NOT_FOR_INTRA_COMMUNITY = "simplificada_not_for_intra_community"
    COUNTERPARTY_TAX_ID_REQUIRED = "counterparty_tax_id_required"
    COUNTERPARTY_TAX_ID_REQUIRED_BY_CATEGORY = "counterparty_tax_id_required_by_category"
    COUNTERPARTY_TAX_ID_INVALID = "counterparty_tax_id_invalid"
    COUNTERPARTY_COUNTRY_INVALID = "counterparty_country_invalid"
    COUNTERPARTY_NAME_BLANK = "counterparty_name_blank"
    COUNTERPARTY_NAME_TOO_LONG = "counterparty_name_too_long"
    INVOICE_NUMBER_BLANK = "invoice_number_blank"
    CURRENCY_INVALID = "currency_invalid"
    INVOICE_CLASS_UNDECLARED = "invoice_class_undeclared"
    IVA_CATEGORY_UNDECLARED = "iva_category_undeclared"
    INTRA_COMMUNITY_SPANISH_IDENTIFICATION = "intra_community_spanish_identification"
    OPERATION_TYPE_REQUIRED = "operation_type_required"
    OPERATION_DATE_ROLE_MISMATCH = "operation_date_role_mismatch"
    ADVANCE_PAYMENT_NOT_FULLY_COLLECTED = "advance_payment_not_fully_collected"
    LEASE_ONLY_ON_ISSUED = "lease_only_on_issued"
    LEASE_SITUATION_UNDECLARED = "lease_situation_undeclared"
    LEASE_REFERENCE_NOT_ALLOWED = "lease_reference_not_allowed"
    LEASE_REFERENCE_TOO_LONG = "lease_reference_too_long"
    LINE_DESCRIPTION_BLANK = "line_description_blank"
    LINE_DESCRIPTION_TOO_LONG = "line_description_too_long"
    LINE_OSS_RATE_KIND_REFUSED = "line_oss_rate_kind_refused"
    OTHER_INVOICE_RULE = "other_invoice_rule"


@dataclass(frozen=True, slots=True)
class InvoiceRuleFinding:
    """One document rule's answer. It always refuses, and names the fields it concerns."""

    code: InvoiceRuleFindingCode
    message: str
    fields: tuple[str, ...]
    values: Mapping[str, Decimal | str] = field(default_factory=dict[str, Decimal | str])


def rule_finding_words_key(code: InvoiceRuleFindingCode) -> str:
    """The catalogue key of the sentence that words the finding ``code``."""
    return f"{INVOICE_RULE_FINDING_WORDS_ROOT}.{code.value}"


def invoice_rule_refusal(finding: InvoiceRuleFinding) -> InvoiceValidationError:
    """Return the refusal a validator raises for ``finding``, carrying its stable code and the key of its words."""
    return InvoiceValidationError(
        finding.message,
        context={"rule_finding_code": finding.code.value, "fields": finding.fields},
        translated_message=rule_finding_words_key(finding.code),
    )


def raise_first_rule_finding(findings: Iterable[InvoiceRuleFinding | None]) -> None:
    """Raise the refusal of the first present rule finding, in the order given."""
    for finding in findings:
        if finding is not None:
            raise invoice_rule_refusal(finding)


def invoice_class_rule_findings(
    *,
    rectificativa: bool,
    simplificada: bool,
    issued: bool | None,
    series: str | None,
    rectifies_invoice_number: str | None,
    intra_community_supply: bool,
    tax_id_missing: bool,
    category_mandates_tax_id: bool,
    category_value: str = "",
) -> tuple[InvoiceRuleFinding, ...]:
    """Answer the RD 1619/2012 art. 6.1 class axis, in the order the rules are refused.

    ``issued`` is ``None`` while a draft has no kind yet: whether the simplificada
    relief applies is then unknown, so the rule that needs it stays unasked.
    """
    findings = (
        _series_required_finding(rectificativa=rectificativa, series=series),
        _rectified_invoice_required_finding(
            rectificativa=rectificativa, rectifies_invoice_number=rectifies_invoice_number
        ),
        _rectified_invoice_not_allowed_finding(
            rectificativa=rectificativa, rectifies_invoice_number=rectifies_invoice_number
        ),
        _simplificada_intra_community_finding(simplificada=simplificada, intra_community_supply=intra_community_supply),
        _tax_id_required_finding(tax_id_missing=tax_id_missing, issued=issued, simplificada=simplificada),
        _tax_id_required_by_category_finding(
            tax_id_missing=tax_id_missing,
            category_mandates_tax_id=category_mandates_tax_id,
            category_value=category_value,
        ),
    )
    return tuple(finding for finding in findings if finding is not None)


def _series_required_finding(*, rectificativa: bool, series: str | None) -> InvoiceRuleFinding | None:
    if rectificativa and series in (None, ""):
        return InvoiceRuleFinding(
            InvoiceRuleFindingCode.SERIES_REQUIRED_FOR_RECTIFICATIVA,
            "a factura rectificativa must be issued in a specific series (RD 1619/2012 art. 6.1.a.2.º)",
            ("series",),
        )
    return None


def _rectified_invoice_required_finding(
    *, rectificativa: bool, rectifies_invoice_number: str | None
) -> InvoiceRuleFinding | None:
    if rectificativa and rectifies_invoice_number in (None, ""):
        return InvoiceRuleFinding(
            InvoiceRuleFindingCode.RECTIFIED_INVOICE_REQUIRED,
            "a factura rectificativa must name the invoice it rectifies (LIVA art. 89)",
            ("rectifies_invoice_number",),
        )
    return None


def _rectified_invoice_not_allowed_finding(
    *, rectificativa: bool, rectifies_invoice_number: str | None
) -> InvoiceRuleFinding | None:
    if not rectificativa and rectifies_invoice_number is not None:
        return InvoiceRuleFinding(
            InvoiceRuleFindingCode.RECTIFIED_INVOICE_NOT_ALLOWED,
            "rectifies_invoice_number only applies to a factura rectificativa",
            ("rectifies_invoice_number", "invoice_class"),
        )
    return None


def _simplificada_intra_community_finding(
    *, simplificada: bool, intra_community_supply: bool
) -> InvoiceRuleFinding | None:
    if simplificada and intra_community_supply:
        return InvoiceRuleFinding(
            InvoiceRuleFindingCode.SIMPLIFICADA_NOT_FOR_INTRA_COMMUNITY,
            "a factura simplificada must not be issued for an entrega intracomunitaria exenta "
            "(RD 1619/2012 art. 4.4.a); issue an ordinaria or rectificativa instead",
            ("invoice_class", "iva_category"),
        )
    return None


def _tax_id_required_finding(
    *, tax_id_missing: bool, issued: bool | None, simplificada: bool
) -> InvoiceRuleFinding | None:
    if tax_id_missing and issued is not None and not (simplificada and issued):
        return InvoiceRuleFinding(
            InvoiceRuleFindingCode.COUNTERPARTY_TAX_ID_REQUIRED,
            "counterparty_tax_id is required unless the invoice is simplified and kind is ISSUED; "
            "on a RECEIVED invoice it names the issuer's own identity, which stays mandatory",
            ("counterparty_tax_id",),
        )
    return None


def _tax_id_required_by_category_finding(
    *, tax_id_missing: bool, category_mandates_tax_id: bool, category_value: str
) -> InvoiceRuleFinding | None:
    if tax_id_missing and category_mandates_tax_id:
        return InvoiceRuleFinding(
            InvoiceRuleFindingCode.COUNTERPARTY_TAX_ID_REQUIRED_BY_CATEGORY,
            "counterparty_tax_id is required on a factura simplificada whose iva_category is "
            f"{category_value!r} (RD 1619/2012 art. 6.1.d)",
            ("counterparty_tax_id", "iva_category"),
        )
    return None


def operation_date_role_finding(*, date_stated: bool, role_stated: bool) -> InvoiceRuleFinding | None:
    """An operation date and its LIVA art. 75 role travel together."""
    if date_stated != role_stated:
        return InvoiceRuleFinding(
            InvoiceRuleFindingCode.OPERATION_DATE_ROLE_MISMATCH,
            "operation_date and operation_date_role must be set together",
            ("operation_date",),
        )
    return None


def advance_payment_collection_finding(*, advance_role: bool, fully_collected: bool) -> InvoiceRuleFinding | None:
    """A pago anticipado invoice states one collected amount, so it must be collected in full.

    LIVA art. 75.Dos devengues an advance "por los importes efectivamente
    percibidos". One invoice carries one devengo date, so an advance role on an
    invoice whose price is only partly collected would place the whole base in
    the advance's period at the rate then in force (art. 90.Dos), while the
    remainder devengues at the later entrega or prestación (art. 75.Uno).
    """
    if advance_role and not fully_collected:
        return InvoiceRuleFinding(
            InvoiceRuleFindingCode.ADVANCE_PAYMENT_NOT_FULLY_COLLECTED,
            "a pago anticipado devengues only for the amount collected (LIVA art. 75.Dos); record the "
            "advance as its own invoice, or mark this one PAID if the advance covers the whole price",
            ("operation_date_role", "payment_status"),
        )
    return None


def lease_kind_finding(*, lease_stated: bool, issued: bool) -> InvoiceRuleFinding | None:
    """The lessor records a business-premises lease, so only an issued invoice carries one."""
    if lease_stated and not issued:
        return InvoiceRuleFinding(
            InvoiceRuleFindingCode.LEASE_ONLY_ON_ISSUED,
            "a business-premises lease only applies to an issued invoice",
            ("business_premises_lease", "kind"),
        )
    return None


__all__ = [
    "INVOICE_RULE_FINDING_WORDS_ROOT",
    "InvoiceRuleFinding",
    "InvoiceRuleFindingCode",
    "invoice_class_rule_findings",
    "invoice_rule_refusal",
    "lease_kind_finding",
    "operation_date_role_finding",
    "raise_first_rule_finding",
    "rule_finding_words_key",
]
