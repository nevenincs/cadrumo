"""The document rules an invoice figures preview asks of a draft, and the verdict naming the rule refused."""

from __future__ import annotations

from datetime import date
from typing import Literal, NamedTuple

from pydantic import ValidationError

from ...core.errors.hierarchy import CoreValidationError
from ...core.identity.documents import IdentityError
from ...core.identity.tax_id import tax_id_identity_token
from ...core.parsing.codes import normalise_iso_4217_currency
from ...core.type_adapters import OBJECT_TUPLE_ADAPTER
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.errors import RegistryValidationError
from ...domain.calculations.registry.governed_fact_scope import validating_governed_facts
from ...domain.invoices.business_premises import (
    lease_reference_fit_finding,
    lease_reference_situation_finding,
    require_situacion_inmueble,
)
from ...domain.invoices.enums import InvoiceClass, default_invoice_class
from ...domain.invoices.errors import InvoiceValidationError
from ...domain.invoices.figures import FigureFindingCode
from ...domain.invoices.models import invoice_class_findings
from ...domain.invoices.party_limits import INVOICE_COUNTERPARTY_NAME_MAX_LENGTH
from ...domain.invoices.rule_findings import (
    InvoiceRuleFinding,
    InvoiceRuleFindingCode,
    lease_kind_finding,
    operation_date_role_finding,
)
from ...domain.invoices.validators import validate_counterparty_tax_id, validate_country_code
from ...domain.iva.schema import InvoiceKind, IvaCategory
from .catalogue_add_contracts import INVOICE_LINE_DESCRIPTION_MAX_LENGTH
from .catalogue_add_operation import (
    declared_invoice_category,
    declared_invoice_class,
    invoice_date_outside_registry_support,
)
from .figures_preview_contracts import (
    INVALID_INVOICE_REFUSAL,
    InvoiceFiguresPreviewRequest,
)

type RefusalCode = FigureFindingCode | Literal["invalid_invoice"]


class LocatedRuleFinding(NamedTuple):
    """A rule's answer and, when it concerns one line, that line's key."""

    finding: InvoiceRuleFinding
    line_key: str | None = None


class Verdict(NamedTuple):
    """How a draft was answered, and the rule that refused it when a refusal named one."""

    refusal_code: RefusalCode | None = None
    invoice_id: str | None = None
    refused_by: InvoiceRuleFinding | None = None


def rule_finding_of(error: ValidationError | InvoiceValidationError) -> InvoiceRuleFinding:
    """Read the rule a refusal names, or the fields a nameless one concerns."""
    causes: list[object] = [error]
    located: tuple[str, ...] = ()
    if isinstance(error, ValidationError):
        details = error.errors()
        causes = [getattr(detail.get("ctx", {}).get("error"), "__cause__", None) for detail in details]
        located = tuple(str(detail["loc"][-1]) for detail in details if detail["loc"])
    for cause in causes:
        named = _named_rule_finding(cause, located)
        if named is not None:
            return named
    return other_rule_finding(located)


def _named_rule_finding(cause: object, located: tuple[str, ...]) -> InvoiceRuleFinding | None:
    if not isinstance(cause, InvoiceValidationError) or cause.context is None:
        return None
    code = cause.context.get("rule_finding_code")
    if code is None:
        return None
    named = tuple(str(name) for name in OBJECT_TUPLE_ADAPTER.validate_python(cause.context.get("fields", ())))
    return InvoiceRuleFinding(InvoiceRuleFindingCode(str(code)), str(cause), named or located)


def other_rule_finding(fields: tuple[str, ...] = ()) -> InvoiceRuleFinding:
    """Name a refusal by a rule outside the figures when no rule is named."""
    return InvoiceRuleFinding(
        InvoiceRuleFindingCode.OTHER_INVOICE_RULE,
        "the invoice is refused by a rule outside the figures",
        fields or ("invoice",),
    )


def _blank_finding(value: str | None, code: InvoiceRuleFindingCode, field: str) -> tuple[InvoiceRuleFinding, ...]:
    if value is None or value.strip():
        return ()
    return (InvoiceRuleFinding(code, f"{field} must not be blank", (field,)),)


def _name_length_findings(name: str | None) -> tuple[InvoiceRuleFinding, ...]:
    if name is None or len(name) <= INVOICE_COUNTERPARTY_NAME_MAX_LENGTH:
        return ()
    return (
        InvoiceRuleFinding(
            InvoiceRuleFindingCode.COUNTERPARTY_NAME_TOO_LONG,
            "a counterparty name is longer than an invoice holds",
            ("counterparty_name",),
            values={"limit": str(INVOICE_COUNTERPARTY_NAME_MAX_LENGTH)},
        ),
    )


def _valid_country(country: str | None) -> tuple[str | None, tuple[InvoiceRuleFinding, ...]]:
    """Return the canonical country a tax id is judged under, and what refuses the stated one."""
    if country is None:
        return None, ()
    try:
        return validate_country_code(country), ()
    except RegistryValidationError:
        raise
    except (InvoiceValidationError, CoreValidationError) as refused:
        return None, (
            InvoiceRuleFinding(
                InvoiceRuleFindingCode.COUNTERPARTY_COUNTRY_INVALID, str(refused), ("counterparty_country",)
            ),
        )


def _counterparty_rule_findings(request: InvoiceFiguresPreviewRequest) -> tuple[InvoiceRuleFinding, ...]:
    """Judge the country and the tax id as the invoice's own normaliser judges them."""
    country, findings = _valid_country(request.counterparty_country)
    if request.counterparty_tax_id is None:
        return findings
    try:
        validate_counterparty_tax_id(tax_id_identity_token(request.counterparty_tax_id), country=country)
    except RegistryValidationError:
        raise
    except (InvoiceValidationError, IdentityError, CoreValidationError) as refused:
        return (
            *findings,
            InvoiceRuleFinding(
                InvoiceRuleFindingCode.COUNTERPARTY_TAX_ID_INVALID,
                str(refused),
                ("counterparty_tax_id", "counterparty_country"),
            ),
        )
    return findings


def _currency_rule_findings(request: InvoiceFiguresPreviewRequest) -> tuple[InvoiceRuleFinding, ...]:
    if request.currency is None:
        return ()
    try:
        normalise_iso_4217_currency(request.currency)
    except CoreValidationError as refused:
        return (InvoiceRuleFinding(InvoiceRuleFindingCode.CURRENCY_INVALID, str(refused), ("currency",)),)
    return ()


def _stated_class(request: InvoiceFiguresPreviewRequest) -> InvoiceClass | InvoiceRuleFinding:
    try:
        return declared_invoice_class(request.invoice_class) or default_invoice_class()
    except InvoiceValidationError as refused:
        return InvoiceRuleFinding(InvoiceRuleFindingCode.INVOICE_CLASS_UNDECLARED, str(refused), ("invoice_class",))


def _stated_category(
    request: InvoiceFiguresPreviewRequest,
    on_date: date,
    operation: PinnedAuthorityOperation,
) -> IvaCategory | InvoiceRuleFinding | None:
    try:
        return declared_invoice_category(request.iva_category, effective_date=on_date, authority_operation=operation)
    except InvoiceValidationError as refused:
        return InvoiceRuleFinding(InvoiceRuleFindingCode.IVA_CATEGORY_UNDECLARED, str(refused), ("iva_category",))


def _class_rule_findings(
    request: InvoiceFiguresPreviewRequest,
    on_date: date,
    operation: PinnedAuthorityOperation,
) -> tuple[InvoiceRuleFinding, ...]:
    """Ask the class axis over the text as the invoice normalises it."""
    invoice_class = _stated_class(request)
    category = _stated_category(request, on_date, operation)
    undeclared = tuple(item for item in (invoice_class, category) if isinstance(item, InvoiceRuleFinding))
    if isinstance(invoice_class, InvoiceRuleFinding):
        return undeclared
    return (
        *undeclared,
        *invoice_class_findings(
            invoice_class=invoice_class,
            kind=request.kind,
            series=(request.series or "").strip() or None,
            rectifies_invoice_number=(request.rectifies_invoice_number or "").strip().upper() or None,
            category=None if isinstance(category, InvoiceRuleFinding) else category,
            tax_id_missing=request.counterparty_tax_id is None,
            effective_date=on_date,
        ),
    )


def _lease_situation_findings(situacion_inmueble: str | None, reference: str | None) -> tuple[InvoiceRuleFinding, ...]:
    try:
        situation = None if situacion_inmueble is None else require_situacion_inmueble(situacion_inmueble)
    except InvoiceValidationError as refused:
        return (
            InvoiceRuleFinding(
                InvoiceRuleFindingCode.LEASE_SITUATION_UNDECLARED, str(refused), ("situacion_inmueble",)
            ),
        )
    finding = lease_reference_situation_finding(situation, reference)
    return () if finding is None else (finding,)


def _lease_rule_findings(request: InvoiceFiguresPreviewRequest) -> tuple[InvoiceRuleFinding, ...]:
    lease = request.business_premises_lease
    if lease is None:
        return ()
    reference = (lease.referencia_catastral or "").strip().upper() or None
    kind_finding = (
        None
        if request.kind is None
        else lease_kind_finding(lease_stated=True, issued=request.kind is InvoiceKind.ISSUED)
    )
    return (
        *(() if kind_finding is None else (kind_finding,)),
        *_lease_situation_findings(lease.situacion_inmueble, reference),
        *(fit for fit in (lease_reference_fit_finding(reference),) if fit is not None),
    )


def _line_description_findings(description: str) -> tuple[InvoiceRuleFinding, ...]:
    if len(description) > INVOICE_LINE_DESCRIPTION_MAX_LENGTH:
        return (
            InvoiceRuleFinding(
                InvoiceRuleFindingCode.LINE_DESCRIPTION_TOO_LONG,
                "a line description is longer than an invoice line holds",
                ("description",),
                values={"limit": str(INVOICE_LINE_DESCRIPTION_MAX_LENGTH)},
            ),
        )
    return _blank_finding(description, InvoiceRuleFindingCode.LINE_DESCRIPTION_BLANK, "description")


def _line_rule_findings(request: InvoiceFiguresPreviewRequest) -> tuple[LocatedRuleFinding, ...]:
    return tuple(
        LocatedRuleFinding(finding, line.key)
        for line in request.lines
        if line.description is not None
        for finding in _line_description_findings(line.description)
    )


def _operation_date_rule_findings(request: InvoiceFiguresPreviewRequest) -> tuple[InvoiceRuleFinding, ...]:
    if request.stored is None:
        return ()
    finding = operation_date_role_finding(
        date_stated=request.operation_date is not None,
        role_stated=request.stored.operation_date_role is not None,
    )
    return () if finding is None else (finding,)


def draft_rule_findings(
    request: InvoiceFiguresPreviewRequest,
    on_date: date,
    *,
    operation: PinnedAuthorityOperation,
) -> tuple[LocatedRuleFinding, ...]:
    """Ask every document rule whose inputs the draft states, complete or not.

    A date the registry does not serve leaves the dated vocabularies unasked; its
    own finding already says so. On a complete draft the verdict stays acceptance's.
    """
    lines = _line_rule_findings(request)
    try:
        with validating_governed_facts(operation):
            document = (
                *_blank_finding(
                    request.counterparty_name, InvoiceRuleFindingCode.COUNTERPARTY_NAME_BLANK, "counterparty_name"
                ),
                *_name_length_findings(request.counterparty_name),
                *_blank_finding(request.invoice_number, InvoiceRuleFindingCode.INVOICE_NUMBER_BLANK, "invoice_number"),
                *_counterparty_rule_findings(request),
                *_currency_rule_findings(request),
                *_class_rule_findings(request, on_date, operation),
                *_lease_rule_findings(request),
                *_operation_date_rule_findings(request),
            )
    except RegistryValidationError:
        if invoice_date_outside_registry_support(on_date, operation):
            return lines
        raise
    return (*(LocatedRuleFinding(item) for item in document), *lines)


def with_refusing_rule(
    rule_findings: tuple[LocatedRuleFinding, ...],
    verdict: Verdict,
) -> tuple[LocatedRuleFinding, ...]:
    """Add the rule acceptance named, unless asking the draft had already found it."""
    refused_by = verdict.refused_by
    if refused_by is None:
        return rule_findings
    if refused_by.code is InvoiceRuleFindingCode.OTHER_INVOICE_RULE and (
        rule_findings or verdict.refusal_code != INVALID_INVOICE_REFUSAL
    ):
        return rule_findings
    if any(item.finding.code is refused_by.code for item in rule_findings):
        return rule_findings
    return (*rule_findings, LocatedRuleFinding(refused_by))
