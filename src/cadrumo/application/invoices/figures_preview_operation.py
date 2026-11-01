"""Registered read that answers an invoice draft with the backend's own figures and verdict.

A complete draft runs the same construction the add operation runs, so the
verdict is acceptance's own. Nothing can persist: this path holds no repository,
and its exchange-rate source never leaves the process. A foreign-currency draft
is therefore checked unstamped, which changes neither its validity nor its id,
because a stamp enters only the euro projections.

A duplicate is decided at commit against the stored catalogue, so a preview
that would accept can still meet a ``duplicate_invoice`` refusal on add.

A correction states a ``stored`` invoice and a bare base. Nothing here reads that
record, so its verdict covers only the facts the request states; see
``InvoiceFiguresPreviewVerdictScope``.
"""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from datetime import date
from decimal import Decimal, DecimalException
from typing import Literal, NamedTuple

from pydantic import BaseModel, ValidationError

from cadrumo_client.contracts.access_refusals import AccessDenialCode

from ...core.bucket_pointer import require_active_bucket_id
from ...core.errors.hierarchy import CoreValidationError, InternalInvariantError
from ...core.hashing import content_hash_hex
from ...core.identity.documents import IdentityError
from ...core.identity.tax_id import tax_id_identity_token
from ...core.operations import OperationEffect, profile_operation_subject
from ...core.parsing.codes import normalise_iso_4217_currency
from ...core.time.clock import now, today_madrid
from ...core.type_adapters import OBJECT_TUPLE_ADAPTER
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.errors import RegistryValidationError
from ...domain.calculations.registry.governed_fact_scope import validating_governed_facts
from ...domain.currency.models import EurRateLookup, EurRateLookupStatus
from ...domain.invoices.business_premises import (
    lease_reference_fit_finding,
    lease_reference_situation_finding,
    require_situacion_inmueble,
)
from ...domain.invoices.enums import InvoiceClass, default_invoice_class
from ...domain.invoices.errors import InvoiceValidationError
from ...domain.invoices.figures import (
    DatedRateSlot,
    FigureFinding,
    FigureFindingCode,
    FigureFindingSeverity,
    InvoiceFigures,
    InvoiceRuleFinding,
    InvoiceRuleFindingCode,
    LineFigures,
    StatedFigure,
    compute_invoice_figures,
    compute_line_figures,
    dated_rate_slots,
    lease_kind_finding,
    operation_date_role_finding,
)
from ...domain.invoices.models import invoice_class_findings
from ...domain.invoices.validators import validate_counterparty_tax_id, validate_country_code
from ...domain.iva.schema import InvoiceKind, IvaCategory
from ..ledger.read_access import resolve_ledger_read_access
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.capabilities import RECORDED_IDEMPOTENT_SECURE_INPUT_READ_CAPABILITIES
from ..operations.models import OperationRequest, OperationTerminalReceipt, require_succeeded_terminal_receipt
from ..operations.operation_definition import OperationDefinition, build_single_phase_definition
from ..operations.owner import OperationExecutorContext
from ..operations.public_scalar import PublicDecimal, project_facts
from ..operations.registry import OperationPublicDefinitionRegistrationV1
from ..operations.subject_reference import OperationSubjectReferenceV1
from ..user_profile.access_errors import ProfileAccessRefusedError
from .catalogue_add_contracts import INVOICE_LINE_DESCRIPTION_MAX_LENGTH, InvoiceAddLine, InvoiceAddRequest
from .catalogue_add_operation import (
    build_invoice_from_add_request,
    declared_invoice_category,
    declared_invoice_class,
    invoice_add_lease,
    invoice_date_outside_registry_support,
)
from .figures_preview_contracts import (
    INVALID_INVOICE_REFUSAL,
    INVOICE_FIGURES_PREVIEW_LABEL_PREFIX,
    INVOICE_FIGURES_PREVIEW_OPERATION_DEFINITION_ID,
    InvoiceFiguresPreviewExecutionResult,
    InvoiceFiguresPreviewFigure,
    InvoiceFiguresPreviewFinding,
    InvoiceFiguresPreviewLine,
    InvoiceFiguresPreviewLineResult,
    InvoiceFiguresPreviewOnDateSource,
    InvoiceFiguresPreviewRateSlot,
    InvoiceFiguresPreviewRequest,
    InvoiceFiguresPreviewResult,
    InvoiceFiguresPreviewRetention,
    InvoiceFiguresPreviewRuleFinding,
    InvoiceFiguresPreviewStored,
    InvoiceFiguresPreviewTotals,
)

_NO_RATE_SOURCE = "no-rate-source"

type _RefusalCode = FigureFindingCode | Literal["invalid_invoice"]


class _LocatedRuleFinding(NamedTuple):
    """A rule's answer and, when it concerns one line, that line's key."""

    finding: InvoiceRuleFinding
    line_key: str | None = None


class _Verdict(NamedTuple):
    """How a draft was answered, and the rule that refused it when a refusal named one."""

    refusal_code: _RefusalCode | None = None
    invoice_id: str | None = None
    refused_by: InvoiceRuleFinding | None = None


class _NoRateSource:
    """Answer no rate for every currency, so a preview never leaves the process."""

    @property
    def rate_source_id(self) -> str:
        """Name this source for the port; an unfound rate stamps nothing with it."""
        return _NO_RATE_SOURCE

    def lookup_eur_rate(self, currency: str, rate_date: date) -> EurRateLookup:
        """Report the rate as missing, which leaves the record unstamped."""
        return EurRateLookup(status=EurRateLookupStatus.MISSING_RATE, rate_date=rate_date, source=_NO_RATE_SOURCE)


def _decimal(value: PublicDecimal | None) -> Decimal | None:
    return None if value is None else Decimal(value.decimal)


def _public(value: Decimal | None) -> PublicDecimal | None:
    return None if value is None else PublicDecimal(decimal=str(value))


def _resolve_on_date(request: InvoiceFiguresPreviewRequest) -> tuple[date, InvoiceFiguresPreviewOnDateSource]:
    if request.operation_date is not None:
        return request.operation_date, "operation_date"
    if request.issued_at is not None:
        return request.issued_at, "issued_at"
    return today_madrid(), "today"


def _rate_date_unresolved_finding(on_date: date) -> FigureFinding:
    return FigureFinding(
        FigureFindingCode.RATE_DATE_UNRESOLVED,
        "the registry states no IVA rates for this date",
        ("iva_rate", "operation_date", "issued_at"),
        values={"on_date": on_date.isoformat()},
    )


def _slots_on_date(
    on_date: date,
    operation: PinnedAuthorityOperation,
) -> tuple[DatedRateSlot, ...] | None:
    """Return the date's slots, or ``None`` when the date is outside what the registry serves.

    A registry failure on a date inside its support is corrupt authority and stays a failure.
    """
    try:
        with validating_governed_facts(operation):
            return dated_rate_slots(on_date)
    except RegistryValidationError:
        if invoice_date_outside_registry_support(on_date, operation):
            return None
        raise


def _rate_undeclared_finding(token: str) -> FigureFinding:
    return FigureFinding(
        FigureFindingCode.LINE_RATE_UNDECLARED,
        "invoice line IVA rate is not declared by the active registry",
        ("iva_rate",),
        values={"slot": token},
    )


def _slot_refusal_finding(line: InvoiceFiguresPreviewLine, slot: DatedRateSlot, on_date: date) -> FigureFinding:
    return FigureFinding(
        FigureFindingCode.LINE_RATE_COVERAGE_GAP if slot.coverage_gap else FigureFindingCode.LINE_RATE_NOT_IN_FORCE,
        f"line rate {line.iva_rate} is not available on {on_date.isoformat()}",
        ("iva_rate",),
        values={"slot": str(slot.slot), "on_date": on_date.isoformat()},
    )


def _line_figures(
    line: InvoiceFiguresPreviewLine,
    slots: tuple[DatedRateSlot, ...] | None,
    on_date: date,
) -> LineFigures:
    slot = None if slots is None else next((item for item in slots if str(item.slot) == line.iva_rate), None)
    figures = compute_line_figures(
        quantity=_decimal(line.quantity),
        unit_price=_decimal(line.unit_price),
        stated_subtotal=_decimal(line.subtotal),
        stated_iva_amount=_decimal(line.iva_amount),
        slot=slot,
        oss_rate=line.oss_rate_kind is not None,
    )
    rate_findings: tuple[FigureFinding, ...] = ()
    if line.iva_rate is not None and slots is not None:
        if slot is None:
            rate_findings = (_rate_undeclared_finding(line.iva_rate),)
        elif not slot.in_force:
            rate_findings = (_slot_refusal_finding(line, slot, on_date),)
    if not rate_findings:
        return figures
    return LineFigures(
        subtotal=figures.subtotal,
        iva_amount=figures.iva_amount,
        findings=(*figures.findings, *rate_findings),
        numeric_slot=figures.numeric_slot,
    )


def _correction_missing_fields(request: InvoiceFiguresPreviewRequest) -> tuple[str, ...]:
    """A correction restates the facts its rules read; the stored record holds the rest."""
    required: Mapping[str, object] = {
        "kind": request.kind,
        "issued_at": request.issued_at,
        "invoice_class": request.invoice_class,
    }
    return tuple(name for name, value in required.items() if value is None)


def _missing_fields(request: InvoiceFiguresPreviewRequest) -> tuple[str, ...]:
    if request.stored is not None:
        return _correction_missing_fields(request)
    required: Mapping[str, object] = {
        "kind": request.kind,
        "invoice_number": request.invoice_number,
        "counterparty_name": request.counterparty_name,
        "counterparty_country": request.counterparty_country,
        "issued_at": request.issued_at,
        "currency": request.currency,
    }
    missing = [name for name, value in required.items() if value is None]
    if not request.lines:
        missing.append("lines")
    for line in request.lines:
        line_required: Mapping[str, object] = {
            "description": line.description,
            "quantity": line.quantity,
            "unit_price": line.unit_price,
            "iva_rate": line.iva_rate,
        }
        missing.extend(f"lines.{line.key}.{name}" for name, value in line_required.items() if value is None)
        if line.oss_rate_kind is not None and line.iva_amount is None:
            missing.append(f"lines.{line.key}.iva_amount")
    return tuple(missing)


def _figure_for_add(figure: StatedFigure) -> Decimal | None:
    """Return what the add request would carry: the document's figure, else the backend's."""
    return figure.computed if figure.stated is None else figure.stated


def _add_lines(
    request: InvoiceFiguresPreviewRequest,
    lines: tuple[LineFigures, ...],
) -> tuple[InvoiceAddLine, ...] | None:
    """Project the draft's lines to the add request; ``None`` when a rule left a figure unknown."""
    projected: list[InvoiceAddLine] = []
    for line, figures in zip(request.lines, lines, strict=True):
        subtotal = _figure_for_add(figures.subtotal)
        iva_amount = _figure_for_add(figures.iva_amount)
        if (
            subtotal is None
            or iva_amount is None
            or line.description is None
            or line.quantity is None
            or line.unit_price is None
            or line.iva_rate is None
        ):
            return None
        projected.append(
            InvoiceAddLine(
                description=line.description,
                quantity=line.quantity,
                unit_price=line.unit_price,
                subtotal=PublicDecimal(decimal=str(subtotal)),
                iva_rate=line.iva_rate,
                iva_amount=PublicDecimal(decimal=str(iva_amount)),
                spending_category_id=line.spending_category_id,
                oss_rate_kind=line.oss_rate_kind,
            )
        )
    return tuple(projected)


def _validated_invoice_id(
    request: InvoiceFiguresPreviewRequest,
    lines: tuple[InvoiceAddLine, ...],
    *,
    operation: PinnedAuthorityOperation,
) -> str:
    """Run the add operation's own construction; nothing it returns is persisted."""
    if (
        request.kind is None
        or request.invoice_number is None
        or request.counterparty_name is None
        or request.counterparty_country is None
        or request.issued_at is None
        or request.currency is None
    ):
        raise InternalInvariantError("an incomplete invoice draft reached its validation")
    payload = InvoiceAddRequest.model_validate(
        {
            "profile_id": request.profile_id,
            "kind": request.kind,
            "counterparty_name": request.counterparty_name,
            "counterparty_tax_id": request.counterparty_tax_id,
            "counterparty_country": request.counterparty_country,
            "invoice_number": request.invoice_number,
            "issued_at": request.issued_at,
            "currency": request.currency,
            "notes": request.notes,
            "iva_category": request.iva_category,
            "operation_type": request.operation_type,
            "operation_date": request.operation_date,
            "retention_rate": request.retention_rate,
            "retention_amount": request.retention_amount,
            "invoice_class": request.invoice_class,
            "series": request.series,
            "rectifies_invoice_number": request.rectifies_invoice_number,
            "recargo_amount": request.recargo_amount,
            "business_premises_lease": (
                None if request.business_premises_lease is None else request.business_premises_lease.model_dump()
            ),
            "lines": lines,
        }
    )
    profile = str(request.profile_id)
    invoice, _advisory_required = build_invoice_from_add_request(
        payload=payload,
        business_premises_lease=invoice_add_lease(payload, authority_operation=operation),
        profile=profile,
        authority_operation=operation,
        rate_provider=_NoRateSource(),
    )
    return invoice.invoice_id


def _refusal_code_of(error: ValidationError | InvoiceValidationError) -> _RefusalCode | None:
    """Read the stable figure code a refusal carries; a rule outside the owner carries none."""
    causes: list[object] = [error]
    if isinstance(error, ValidationError):
        causes = [getattr(detail.get("ctx", {}).get("error"), "__cause__", None) for detail in error.errors()]
    for cause in causes:
        if isinstance(cause, InvoiceValidationError) and cause.context is not None:
            code = cause.context.get("finding_code")
            if code is not None:
                return FigureFindingCode(str(code))
    return None


def _rule_finding_of(error: ValidationError | InvoiceValidationError) -> InvoiceRuleFinding:
    """Read the rule a refusal names, or the fields a nameless one concerns."""
    causes: list[object] = [error]
    located: tuple[str, ...] = ()
    if isinstance(error, ValidationError):
        details = error.errors()
        causes = [getattr(detail.get("ctx", {}).get("error"), "__cause__", None) for detail in details]
        located = tuple(str(detail["loc"][-1]) for detail in details if detail["loc"])
    for cause in causes:
        if isinstance(cause, InvoiceValidationError) and cause.context is not None:
            code = cause.context.get("rule_finding_code")
            if code is not None:
                named = tuple(
                    str(name) for name in OBJECT_TUPLE_ADAPTER.validate_python(cause.context.get("fields", ()))
                )
                return InvoiceRuleFinding(InvoiceRuleFindingCode(str(code)), str(cause), named or located)
    return _other_rule_finding(located)


def _other_rule_finding(fields: tuple[str, ...] = ()) -> InvoiceRuleFinding:
    return InvoiceRuleFinding(
        InvoiceRuleFindingCode.OTHER_INVOICE_RULE,
        "the invoice is refused by a rule outside the figures",
        fields or ("invoice",),
    )


def _first_refusal_code(findings: tuple[FigureFinding, ...]) -> FigureFindingCode | None:
    return next((item.code for item in findings if item.severity is FigureFindingSeverity.REFUSAL), None)


def _verdict(
    request: InvoiceFiguresPreviewRequest,
    lines: tuple[LineFigures, ...],
    findings: tuple[FigureFinding, ...],
    on_date: date,
    *,
    operation: PinnedAuthorityOperation,
) -> _Verdict:
    """Answer a complete draft by acceptance itself: a refusal code, or the invoice's id."""
    try:
        add_lines = _add_lines(request, lines)
        if add_lines is None:
            code = _first_refusal_code(findings)
            if code is None:
                raise InternalInvariantError("a complete invoice draft has an unknown figure and no finding")
            return _Verdict(code)
        return _Verdict(invoice_id=_validated_invoice_id(request, add_lines, operation=operation))
    except RegistryValidationError:
        # Caught first: it is a CoreValidationError, and corrupt authority must stay a failure.
        if invoice_date_outside_registry_support(on_date, operation):
            return _Verdict(FigureFindingCode.RATE_DATE_UNRESOLVED)
        raise
    except (InvoiceValidationError, ValidationError) as refused:
        code = _refusal_code_of(refused) or _first_refusal_code(findings) or INVALID_INVOICE_REFUSAL
        return _Verdict(code, refused_by=_rule_finding_of(refused))
    except CoreValidationError:
        return _Verdict(INVALID_INVOICE_REFUSAL, refused_by=_other_rule_finding())
    except DecimalException:
        return _Verdict(FigureFindingCode.FIGURE_OUT_OF_RANGE)


def _correction_verdict(
    stored: InvoiceFiguresPreviewStored,
    findings: tuple[FigureFinding, ...],
    rule_findings: tuple[_LocatedRuleFinding, ...],
) -> _Verdict:
    """Answer the stated facts of a correction; the update validates the whole record again."""
    code = _first_refusal_code(findings)
    if code is not None:
        return _Verdict(code)
    if rule_findings:
        return _Verdict(INVALID_INVOICE_REFUSAL)
    return _Verdict(invoice_id=stored.invoice_id)


def _blank_finding(value: str | None, code: InvoiceRuleFindingCode, field: str) -> tuple[InvoiceRuleFinding, ...]:
    if value is None or value.strip():
        return ()
    return (InvoiceRuleFinding(code, f"{field} must not be blank", (field,)),)


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


def _line_rule_findings(request: InvoiceFiguresPreviewRequest) -> tuple[_LocatedRuleFinding, ...]:
    return tuple(
        _LocatedRuleFinding(finding, line.key)
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


def _draft_rule_findings(
    request: InvoiceFiguresPreviewRequest,
    on_date: date,
    *,
    operation: PinnedAuthorityOperation,
) -> tuple[_LocatedRuleFinding, ...]:
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
    return (*(_LocatedRuleFinding(item) for item in document), *lines)


def _with_refusing_rule(
    rule_findings: tuple[_LocatedRuleFinding, ...],
    verdict: _Verdict,
) -> tuple[_LocatedRuleFinding, ...]:
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
    return (*rule_findings, _LocatedRuleFinding(refused_by))


def _project_figure(figure: StatedFigure) -> InvoiceFiguresPreviewFigure:
    return InvoiceFiguresPreviewFigure(
        computed=_public(figure.computed),
        stated=_public(figure.stated),
        verdict=figure.verdict,
        submitted=_public(figure.submitted),
    )


def _rate_slot_label_key(slot: str) -> str:
    token = slot.lower().replace(".", "_")
    return f"{INVOICE_FIGURES_PREVIEW_LABEL_PREFIX}rate_slot.{token}"


def _project_slot(slot: DatedRateSlot) -> InvoiceFiguresPreviewRateSlot:
    return InvoiceFiguresPreviewRateSlot(
        slot=str(slot.slot),
        fraction=_public(slot.fraction),
        in_force=slot.in_force,
        coverage_gap=slot.coverage_gap,
        label_key=_rate_slot_label_key(str(slot.slot)),
    )


def _project_finding(finding: FigureFinding, line_key: str | None = None) -> InvoiceFiguresPreviewFinding:
    return InvoiceFiguresPreviewFinding(
        code=finding.code,
        severity=finding.severity,
        fields=finding.fields,
        line_key=line_key,
        values=project_facts(finding.values),
        label_key=f"{INVOICE_FIGURES_PREVIEW_LABEL_PREFIX}finding.{finding.code.value}",
    )


def _project_rule_finding(located: _LocatedRuleFinding) -> InvoiceFiguresPreviewRuleFinding:
    finding = located.finding
    return InvoiceFiguresPreviewRuleFinding(
        code=finding.code,
        fields=finding.fields,
        line_key=located.line_key,
        values=project_facts(finding.values),
        label_key=f"{INVOICE_FIGURES_PREVIEW_LABEL_PREFIX}rule_finding.{finding.code.value}",
    )


def _project_totals(figures: InvoiceFigures) -> InvoiceFiguresPreviewTotals:
    return InvoiceFiguresPreviewTotals(
        base=_public(figures.base_total),
        iva=_public(figures.iva_total),
        recargo=_public(figures.recargo_amount),
        total=_public(figures.total),
        net_of_retention=_public(figures.net_of_retention),
    )


def _project_retention(figures: InvoiceFigures) -> InvoiceFiguresPreviewRetention:
    return InvoiceFiguresPreviewRetention(
        rate=_public(figures.retention_rate),
        amount=_public(figures.retention_amount),
        implied=_public(figures.retention_implied),
    )


def preview_invoice_figures(
    request: InvoiceFiguresPreviewRequest,
    *,
    operation: PinnedAuthorityOperation,
) -> InvoiceFiguresPreviewResult:
    """Answer one draft from the figures owner and, when complete, from acceptance itself.

    A date the registry serves no rates for yields no slots and no cuota, and a
    finding saying so. The moment the registry answers for that date, the same
    path returns its slots with no other change here.

    A refused draft always says why: a refusing figure finding, a rule finding, or
    ``other_invoice_rule`` when acceptance refused by a rule no code names yet.
    """
    on_date, on_date_source = _resolve_on_date(request)
    slots = _slots_on_date(on_date, operation)
    lines = tuple(_line_figures(line, slots, on_date) for line in request.lines)
    invoice = compute_invoice_figures(
        lines=lines,
        stated_base_total=_decimal(request.base_total),
        recargo_amount=_decimal(request.recargo_amount),
        retention_rate=_decimal(request.retention_rate),
        retention_amount=_decimal(request.retention_amount),
        printed_total=_decimal(request.printed_total),
        stored_grand_total=None if request.stored is None else _decimal(request.stored.grand_total),
    )
    date_findings = () if slots is not None else (_rate_date_unresolved_finding(on_date),)
    line_findings = tuple(finding for figures in lines for finding in figures.findings)
    every_finding = (*date_findings, *line_findings, *invoice.findings)
    missing = _missing_fields(request)
    rule_findings = _draft_rule_findings(request, on_date, operation=operation)
    verdict = _Verdict()
    if not missing:
        verdict = (
            _verdict(request, lines, every_finding, on_date, operation=operation)
            if request.stored is None
            else _correction_verdict(request.stored, every_finding, rule_findings)
        )
    rule_findings = _with_refusing_rule(rule_findings, verdict)
    if verdict.refusal_code is not None and not rule_findings and _first_refusal_code(every_finding) is None:
        rule_findings = (_LocatedRuleFinding(_other_rule_finding()),)
    return InvoiceFiguresPreviewResult(
        profile_id=request.profile_id,
        input_digest=content_hash_hex(request.model_dump(mode="json")),
        on_date=on_date,
        on_date_source=on_date_source,
        rate_slots=() if slots is None else tuple(_project_slot(slot) for slot in slots),
        lines=tuple(
            InvoiceFiguresPreviewLineResult(
                key=line.key,
                subtotal=_project_figure(figures.subtotal),
                iva_amount=_project_figure(figures.iva_amount),
            )
            for line, figures in zip(request.lines, lines, strict=True)
        ),
        totals=_project_totals(invoice),
        retention=_project_retention(invoice),
        findings=(
            *(_project_finding(finding) for finding in date_findings),
            *(
                _project_finding(finding, line.key)
                for line, figures in zip(request.lines, lines, strict=True)
                for finding in figures.findings
            ),
            *(_project_finding(finding) for finding in invoice.findings),
        ),
        missing_fields=missing,
        verdict="incomplete" if missing else "would_accept" if verdict.invoice_id is not None else "would_refuse",
        refusal_code=verdict.refusal_code,
        invoice_id=verdict.invoice_id,
        rule_findings=tuple(_project_rule_finding(item) for item in rule_findings),
        verdict_scope="whole_draft" if request.stored is None else "correction_facts",
    )


class InvoiceFiguresPreviewExecutor:
    """Answer one draft inside the exact profile's worker."""

    async def execute(
        self,
        request: OperationRequest[InvoiceFiguresPreviewRequest],
        context: OperationExecutorContext,
    ) -> str:
        """Check the exact profile, then answer from the pinned authority; nothing is written."""
        bucket_id = str(request.payload.profile_id)
        subject = profile_operation_subject(bucket_id)
        if (
            request.definition_id != INVOICE_FIGURES_PREVIEW_OPERATION_DEFINITION_ID
            or context.identity.definition_id != INVOICE_FIGURES_PREVIEW_OPERATION_DEFINITION_ID
            or request.subject_ref != subject
            or context.identity.subject_ref != subject
            or require_active_bucket_id() != bucket_id
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        await context.events.phase(INVOICE_FIGURES_PREVIEW_OPERATION_DEFINITION_ID)
        answer = await asyncio.to_thread(
            preview_invoice_figures,
            request.payload,
            operation=context.authority_operation,
        )
        return await context.operands.put(InvoiceFiguresPreviewExecutionResult(result=answer), written_at=now())


def _project_result(result: BaseModel, receipt: OperationTerminalReceipt, /) -> BaseModel:
    if type(result) is not InvoiceFiguresPreviewExecutionResult:
        raise ValueError("invalid invoice figures preview result")
    require_succeeded_terminal_receipt(
        receipt,
        definition_id=INVOICE_FIGURES_PREVIEW_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(result.result.profile_id)),
        effect=OperationEffect.NONE,
        message="invoice figures preview has an incompatible terminal receipt",
    )
    return result.result


def build_invoice_figures_preview_definition() -> OperationDefinition:
    """Declare the exact-profile read; a draft's figures stay in encrypted custody."""
    return build_single_phase_definition(
        definition_id=INVOICE_FIGURES_PREVIEW_OPERATION_DEFINITION_ID,
        request_type=InvoiceFiguresPreviewRequest,
        subject_reference=OperationSubjectReferenceV1.profile(),
        result_type=InvoiceFiguresPreviewExecutionResult,
        executor_type=InvoiceFiguresPreviewExecutor,
        build=InvoiceFiguresPreviewExecutor,
        capabilities=RECORDED_IDEMPOTENT_SECURE_INPUT_READ_CAPABILITIES,
    )


def resolve_invoice_figures_preview_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Bind the read to the exact profile, as every ledger read is."""
    if request.definition_id != INVOICE_FIGURES_PREVIEW_OPERATION_DEFINITION_ID or not isinstance(
        request.payload, InvoiceFiguresPreviewRequest
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    return resolve_ledger_read_access(request, context, profile_id=request.payload.profile_id, periods=frozenset())


def build_invoice_figures_preview_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind bounded schemas, exact-profile access and receipt projection."""
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=InvoiceFiguresPreviewResult,
        result_projector=_project_result,
        access_resolver=resolve_invoice_figures_preview_access,
    )


__all__ = [
    "InvoiceFiguresPreviewExecutor",
    "build_invoice_figures_preview_definition",
    "build_invoice_figures_preview_registration",
    "preview_invoice_figures",
    "resolve_invoice_figures_preview_access",
]
