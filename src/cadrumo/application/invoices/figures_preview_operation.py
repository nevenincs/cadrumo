"""Registered read that answers an invoice draft with the backend's own figures and verdict.

A complete draft runs the same construction the add operation runs, so the
verdict is acceptance's own. Nothing can persist: this path holds no repository.
A foreign-currency draft resolves its euro conversion through the same rate
source as add. A rate the source cannot find leaves the draft unstamped, as add
does, which changes neither its validity nor its id; a source that cannot be
reached fails the read with add's own rate error, which is neither a
would-accept nor a would-refuse answer.

A duplicate is decided at commit against the stored catalogue, so a preview
that would accept can still meet a ``duplicate_invoice`` refusal on add.

A correction states a ``stored`` invoice and a bare base. Nothing here reads that
record, so its verdict covers only the facts the request states; see
``InvoiceFiguresPreviewVerdictScope``.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Mapping
from datetime import date
from decimal import Decimal, DecimalException

from pydantic import BaseModel, ValidationError

from cadrumo_client.contracts.access_refusals import AccessDenialCode

from ...core.bucket_pointer import require_active_bucket_id
from ...core.errors.hierarchy import CoreValidationError, InternalInvariantError
from ...core.hashing import content_hash_hex
from ...core.operations import OperationEffect, profile_operation_subject
from ...core.time.clock import now, today_madrid
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.errors import RegistryValidationError
from ...domain.calculations.registry.facts.resolution import reading_dated_facts_below_support
from ...domain.calculations.registry.governed_fact_scope import validating_governed_facts
from ...domain.invoices.errors import InvoiceValidationError
from ...domain.invoices.figures import (
    DatedRateSlot,
    FigureFinding,
    FigureFindingCode,
    FigureFindingSeverity,
    InvoiceFigures,
    LineFigures,
    StatedFigure,
    compute_invoice_figures,
    compute_line_figures,
    dated_rate_slots,
    rate_refusal_finding,
)
from ..ledger.read_access import resolve_ledger_request_read_access
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.capabilities import RECORDED_IDEMPOTENT_SECURE_INPUT_READ_CAPABILITIES
from ..operations.models import OperationRequest, OperationTerminalReceipt, require_succeeded_terminal_receipt
from ..operations.operation_definition import OperationDefinition, build_single_phase_definition
from ..operations.owner import OperationExecutorContext
from ..operations.public_scalar import PublicDecimal
from ..operations.registry import OperationPublicDefinitionRegistrationV1
from ..operations.subject_reference import OperationSubjectReferenceV1
from ..user_profile.access_errors import ProfileAccessRefusedError
from .catalogue_add_contracts import InvoiceAddLine, InvoiceAddRequest
from .catalogue_add_operation import (
    build_invoice_from_add_request,
    invoice_add_lease,
    invoice_date_outside_registry_support,
)
from .catalogue_creation_ports import CatalogueInvoiceRateProviderPort
from .figures_preview_contracts import (
    INVALID_INVOICE_REFUSAL,
    INVOICE_FIGURES_PREVIEW_OPERATION_DEFINITION_ID,
    InvoiceFiguresPreviewExecutionResult,
    InvoiceFiguresPreviewLine,
    InvoiceFiguresPreviewOnDateSource,
    InvoiceFiguresPreviewRequest,
    InvoiceFiguresPreviewResult,
    InvoiceFiguresPreviewStored,
)
from .figures_preview_projection import (
    project_findings,
    project_lines,
    project_retention,
    project_rule_finding,
    project_slot,
    project_totals,
    verdict_label,
)
from .figures_preview_rule_findings import (
    LocatedRuleFinding,
    RefusalCode,
    Verdict,
    draft_rule_findings,
    other_rule_finding,
    rule_finding_of,
    with_refusing_rule,
)


def _decimal(value: PublicDecimal | None) -> Decimal | None:
    return None if value is None else Decimal(value.decimal)


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


def _rate_date_projected_finding(on_date: date, nearest: date) -> FigureFinding:
    return FigureFinding(
        FigureFindingCode.RATE_DATE_PROJECTED,
        "these IVA rates are read from the nearest declarations; this date predates the filing years",
        ("iva_rate", "operation_date", "issued_at"),
        severity=FigureFindingSeverity.WARNING,
        values={"on_date": on_date.isoformat(), "nearest": nearest.isoformat()},
    )


def _rate_date_findings(
    on_date: date,
    slots: tuple[DatedRateSlot, ...] | None,
    operation: PinnedAuthorityOperation,
) -> tuple[FigureFinding, ...]:
    if slots is None:
        return (_rate_date_unresolved_finding(on_date),)
    floor = operation.supported_filing_years().date_envelope().floor
    return (_rate_date_projected_finding(on_date, floor),) if on_date < floor else ()


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
            rate_findings = (rate_refusal_finding(slot.slot, on_date, coverage_gap=slot.coverage_gap),)
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
    rate_provider: CatalogueInvoiceRateProviderPort,
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
        rate_provider=rate_provider,
    )
    return invoice.invoice_id


def _refusal_code_of(error: ValidationError | InvoiceValidationError) -> RefusalCode | None:
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


def _first_refusal_code(findings: tuple[FigureFinding, ...]) -> FigureFindingCode | None:
    return next((item.code for item in findings if item.severity is FigureFindingSeverity.REFUSAL), None)


def _verdict(
    request: InvoiceFiguresPreviewRequest,
    lines: tuple[LineFigures, ...],
    findings: tuple[FigureFinding, ...],
    on_date: date,
    *,
    operation: PinnedAuthorityOperation,
    rate_provider: CatalogueInvoiceRateProviderPort,
) -> Verdict:
    """Answer a complete draft by acceptance itself: a refusal code, or the invoice's id."""
    try:
        add_lines = _add_lines(request, lines)
        if add_lines is None:
            code = _first_refusal_code(findings)
            if code is None:
                raise InternalInvariantError("a complete invoice draft has an unknown figure and no finding")
            return Verdict(code)
        return Verdict(
            invoice_id=_validated_invoice_id(request, add_lines, operation=operation, rate_provider=rate_provider)
        )
    except RegistryValidationError:
        # Caught first: it is a CoreValidationError, and corrupt authority must stay a failure.
        if invoice_date_outside_registry_support(on_date, operation):
            return Verdict(FigureFindingCode.RATE_DATE_UNRESOLVED)
        raise
    except (InvoiceValidationError, ValidationError) as refused:
        code = _refusal_code_of(refused) or _first_refusal_code(findings) or INVALID_INVOICE_REFUSAL
        return Verdict(code, refused_by=rule_finding_of(refused))
    except CoreValidationError:
        return Verdict(INVALID_INVOICE_REFUSAL, refused_by=other_rule_finding())
    except DecimalException:
        return Verdict(FigureFindingCode.FIGURE_OUT_OF_RANGE)


def _correction_verdict(
    stored: InvoiceFiguresPreviewStored,
    findings: tuple[FigureFinding, ...],
    rule_findings: tuple[LocatedRuleFinding, ...],
) -> Verdict:
    """Answer the stated facts of a correction; the update validates the whole record again."""
    code = _first_refusal_code(findings)
    if code is not None:
        return Verdict(code)
    if rule_findings:
        return Verdict(INVALID_INVOICE_REFUSAL)
    return Verdict(invoice_id=stored.invoice_id)


def _draft_verdict(
    request: InvoiceFiguresPreviewRequest,
    lines: tuple[LineFigures, ...],
    every_finding: tuple[FigureFinding, ...],
    on_date: date,
    rule_findings: tuple[LocatedRuleFinding, ...],
    *,
    operation: PinnedAuthorityOperation,
    rate_provider: CatalogueInvoiceRateProviderPort,
) -> Verdict:
    if request.stored is None:
        return _verdict(request, lines, every_finding, on_date, operation=operation, rate_provider=rate_provider)
    return _correction_verdict(request.stored, every_finding, rule_findings)


def _invoice_figures(request: InvoiceFiguresPreviewRequest, lines: tuple[LineFigures, ...]) -> InvoiceFigures:
    return compute_invoice_figures(
        lines=lines,
        stated_base_total=_decimal(request.base_total),
        recargo_amount=_decimal(request.recargo_amount),
        retention_rate=_decimal(request.retention_rate),
        retention_amount=_decimal(request.retention_amount),
        printed_total=_decimal(request.printed_total),
        stored_grand_total=None if request.stored is None else _decimal(request.stored.grand_total),
    )


def _with_other_rule_finding(
    rule_findings: tuple[LocatedRuleFinding, ...],
    verdict: Verdict,
    every_finding: tuple[FigureFinding, ...],
) -> tuple[LocatedRuleFinding, ...]:
    if verdict.refusal_code is not None and not rule_findings and _first_refusal_code(every_finding) is None:
        return (LocatedRuleFinding(other_rule_finding()),)
    return rule_findings


def preview_invoice_figures(
    request: InvoiceFiguresPreviewRequest,
    *,
    operation: PinnedAuthorityOperation,
    rate_provider: CatalogueInvoiceRateProviderPort,
) -> InvoiceFiguresPreviewResult:
    """Answer one draft from the figures owner and, when complete, from acceptance itself.

    A date the registry serves no rates for yields no slots and no cuota, and a
    finding saying so. The moment the registry answers for that date, the same
    path returns its slots with no other change here. A date older than the
    filing years reads the nearest declarations, and a finding says the answer
    is a projection; a declared legal start after the date still answers nothing.
    """
    with reading_dated_facts_below_support():
        return _preview_invoice_figures(request, operation=operation, rate_provider=rate_provider)


def _preview_invoice_figures(
    request: InvoiceFiguresPreviewRequest,
    *,
    operation: PinnedAuthorityOperation,
    rate_provider: CatalogueInvoiceRateProviderPort,
) -> InvoiceFiguresPreviewResult:
    """Answer one draft inside the reach its date needs.

    A refused draft always says why: a refusing figure finding, a rule finding, or
    ``other_invoice_rule`` when acceptance refused by a rule no code names yet.
    """
    on_date, on_date_source = _resolve_on_date(request)
    slots = _slots_on_date(on_date, operation)
    lines = tuple(_line_figures(line, slots, on_date) for line in request.lines)
    invoice = _invoice_figures(request, lines)
    date_findings = _rate_date_findings(on_date, slots, operation)
    line_findings = tuple(finding for figures in lines for finding in figures.findings)
    every_finding = (*date_findings, *line_findings, *invoice.findings)
    missing = _missing_fields(request)
    rule_findings = draft_rule_findings(request, on_date, operation=operation)
    verdict = (
        Verdict()
        if missing
        else _draft_verdict(
            request, lines, every_finding, on_date, rule_findings, operation=operation, rate_provider=rate_provider
        )
    )
    rule_findings = _with_other_rule_finding(with_refusing_rule(rule_findings, verdict), verdict, every_finding)
    return InvoiceFiguresPreviewResult(
        profile_id=request.profile_id,
        input_digest=content_hash_hex(request.model_dump(mode="json")),
        on_date=on_date,
        on_date_source=on_date_source,
        rate_slots=() if slots is None else tuple(project_slot(slot) for slot in slots),
        lines=project_lines(request, lines),
        totals=project_totals(invoice),
        retention=project_retention(invoice),
        findings=project_findings(request, lines, date_findings, invoice),
        missing_fields=missing,
        verdict=verdict_label(missing, verdict.invoice_id),
        refusal_code=verdict.refusal_code,
        invoice_id=verdict.invoice_id,
        rule_findings=tuple(project_rule_finding(item) for item in rule_findings),
        verdict_scope="whole_draft" if request.stored is None else "correction_facts",
    )


type InvoiceFiguresPreviewRateProviderFactory = Callable[[], CatalogueInvoiceRateProviderPort]
"""Return the rate source add uses, called inside the worker on each read."""


class InvoiceFiguresPreviewExecutor:
    """Answer one draft inside the exact profile's worker."""

    def __init__(self, rate_provider_factory: InvoiceFiguresPreviewRateProviderFactory) -> None:
        """Bind the factory of the rate source that add resolves a foreign currency through."""
        self._rate_provider_factory = rate_provider_factory

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
            rate_provider=self._rate_provider_factory(),
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


def build_invoice_figures_preview_definition(
    rate_provider_factory: InvoiceFiguresPreviewRateProviderFactory,
) -> OperationDefinition:
    """Declare the exact-profile read; a draft's figures stay in encrypted custody."""
    return build_single_phase_definition(
        definition_id=INVOICE_FIGURES_PREVIEW_OPERATION_DEFINITION_ID,
        request_type=InvoiceFiguresPreviewRequest,
        subject_reference=OperationSubjectReferenceV1.profile(),
        result_type=InvoiceFiguresPreviewExecutionResult,
        executor_type=InvoiceFiguresPreviewExecutor,
        build=lambda: InvoiceFiguresPreviewExecutor(rate_provider_factory),
        capabilities=RECORDED_IDEMPOTENT_SECURE_INPUT_READ_CAPABILITIES,
    )


def resolve_invoice_figures_preview_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Bind the read to the exact profile, as every ledger read is."""
    return resolve_ledger_request_read_access(
        request,
        context,
        definition_id=INVOICE_FIGURES_PREVIEW_OPERATION_DEFINITION_ID,
        request_type=InvoiceFiguresPreviewRequest,
    )


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
    "InvoiceFiguresPreviewRateProviderFactory",
    "build_invoice_figures_preview_definition",
    "build_invoice_figures_preview_registration",
    "preview_invoice_figures",
    "resolve_invoice_figures_preview_access",
]
