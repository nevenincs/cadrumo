"""The preview answers what acceptance answers, for every draft in the table.

The key property is asserted through the real builder rather than through the
preview's own path. Expected figures are worked by hand in the comments.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from types import SimpleNamespace
from typing import cast
from uuid import UUID

import pytest
from pydantic import ValidationError

from ....core.errors.hierarchy import CoreValidationError
from ....core.operations import profile_operation_subject
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.errors import RegistryValidationError
from ....domain.calculations.registry.tests.authority_lease_support import private_authority_lease
from ....domain.currency.models import EurRateLookup, EurRateLookupStatus
from ....domain.invoices.enums import IvaRate
from ....domain.invoices.errors import InvoiceValidationError
from ....domain.invoices.figures import FigureFindingCode, StatedFigureVerdict
from ....domain.invoices.models import InvoiceLine
from ....domain.iva.schema import InvoiceKind
from ...operations.models import OperationIdentity, OperationRequest
from ...operations.owner import OperationExecutorContext
from ...operations.public_scalar import PublicDecimal
from .. import figures_preview_operation as preview_operation
from ..catalogue_add_operation import _prepare_invoice_add
from ..catalogue_creation import build_catalogue_invoice
from ..figures_preview_contracts import (
    INVOICE_FIGURES_PREVIEW_OPERATION_DEFINITION_ID,
    InvoiceFiguresPreviewExecutionResult,
    InvoiceFiguresPreviewLine,
    InvoiceFiguresPreviewRequest,
    InvoiceFiguresPreviewResult,
)
from ..figures_preview_operation import (
    InvoiceFiguresPreviewExecutor,
    build_invoice_figures_preview_definition,
    preview_invoice_figures,
)
from ..tests._catalogue_creation_fakes import in_memory_catalogue_creation_ports

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000bb")
_APRIL = date(2026, 4, 15)


class _NoRate:
    rate_source_id = "synthetic"

    def lookup_eur_rate(self, currency: str, rate_date: date) -> EurRateLookup:
        return EurRateLookup(status=EurRateLookupStatus.MISSING_RATE, rate_date=rate_date, source="synthetic")


@pytest.fixture
def operation() -> Iterator[PinnedAuthorityOperation]:
    with private_authority_lease() as leased:
        yield leased


def _decimal(value: str | None) -> PublicDecimal | None:
    return None if value is None else PublicDecimal(decimal=value)


def _line(
    key: str = "a",
    *,
    description: str | None = "Synthetic service",
    quantity: str | None = "1",
    unit_price: str | None = "100.00",
    iva_rate: str | None = "RATE_21",
    subtotal: str | None = None,
    iva_amount: str | None = None,
) -> InvoiceFiguresPreviewLine:
    return InvoiceFiguresPreviewLine(
        key=key,
        description=description,
        quantity=_decimal(quantity),
        unit_price=_decimal(unit_price),
        iva_rate=iva_rate,
        subtotal=_decimal(subtotal),
        iva_amount=_decimal(iva_amount),
    )


def _draft(*lines: InvoiceFiguresPreviewLine, **overrides: object) -> InvoiceFiguresPreviewRequest:
    values: dict[str, object] = {
        "profile_id": _PROFILE,
        "kind": InvoiceKind.RECEIVED,
        "invoice_number": "SYN-2026-001",
        "issued_at": _APRIL,
        "counterparty_name": "Synthetic supplier",
        "counterparty_tax_id": "A58818501",
        "counterparty_country": "ES",
        "currency": "EUR",
        "lines": lines or (_line(),),
    }
    values.update(overrides)
    return InvoiceFiguresPreviewRequest.model_validate(values)


def _accepted_by_the_builder(
    draft: InvoiceFiguresPreviewRequest,
    answer: InvoiceFiguresPreviewResult,
    operation: PinnedAuthorityOperation,
) -> str:
    """Call the real builder directly with the figures the answer says add would carry."""
    from ....domain.calculations.registry.governed_fact_scope import validating_governed_facts

    with validating_governed_facts(operation):
        lines = tuple(
            InvoiceLine(
                description=str(line.description),
                quantity=Decimal(str(line.quantity.decimal if line.quantity else "")),
                unit_price=Decimal(str(line.unit_price.decimal if line.unit_price else "")),
                subtotal=_figure_for_builder(result.subtotal),
                iva_rate=IvaRate.from_registry(str(line.iva_rate)),
                iva_amount=_figure_for_builder(result.iva_amount),
            )
            for line, result in zip(draft.lines, answer.lines, strict=True)
        )
    invoice = build_catalogue_invoice(
        bucket_id=str(_PROFILE),
        kind=draft.kind or InvoiceKind.RECEIVED,
        counterparty_name=str(draft.counterparty_name),
        counterparty_tax_id=draft.counterparty_tax_id,
        counterparty_country=str(draft.counterparty_country),
        invoice_number=str(draft.invoice_number),
        issued_at=draft.issued_at or _APRIL,
        operation_date=draft.operation_date,
        currency=str(draft.currency),
        retention_rate=_optional(draft.retention_rate),
        retention_amount=_optional(draft.retention_amount),
        recargo_amount=_optional(draft.recargo_amount),
        lines=lines,
        rate_provider=_NoRate(),
        operation=operation,
    )
    return invoice.invoice_id


def _optional(value: PublicDecimal | None) -> Decimal | None:
    return None if value is None else Decimal(value.decimal)


def _figure_for_builder(figure: object) -> Decimal:
    stated = getattr(figure, "stated", None)
    computed = getattr(figure, "computed", None)
    chosen = stated if stated is not None else computed
    # A rule left no figure at all: any cuota serves, since the builder refuses the rate first.
    return Decimal("0") if chosen is None else Decimal(chosen.decimal)


@dataclass(frozen=True)
class _Case:
    name: str
    draft: dict[str, object]
    verdict: str
    code: FigureFindingCode | str | None = None
    total: str | None = None


def _lines(*lines: InvoiceFiguresPreviewLine) -> dict[str, object]:
    return {"lines": lines}


_TABLE = (
    # 100.00 + 21.00
    _Case("computed", {}, "would_accept", total="121.00"),
    _Case("stated-exact", _lines(_line(subtotal="100.00", iva_amount="21.00")), "would_accept", total="121.00"),
    # A printed cuota inside its cent is stored as printed: 100.00 + 21.01.
    _Case("stated-iva-cent", _lines(_line(iva_amount="21.01")), "would_accept", total="121.01"),
    # 100.01 x 0.21 = 21.0021, which a computed 21.00 satisfies: 100.01 + 21.00.
    _Case("stated-subtotal-cent", _lines(_line(subtotal="100.01")), "would_accept", total="121.01"),
    _Case("stated-iva-beyond", _lines(_line(iva_amount="21.02")), "would_refuse", FigureFindingCode.LINE_IVA_MISMATCH),
    _Case(
        "stated-subtotal-beyond",
        _lines(_line(subtotal="100.02")),
        "would_refuse",
        FigureFindingCode.LINE_SUBTOTAL_MISMATCH,
    ),
    _Case(
        "quantity-zero",
        _lines(_line(quantity="0")),
        "would_refuse",
        FigureFindingCode.LINE_QUANTITY_NOT_POSITIVE,
    ),
    _Case("price-negative", _lines(_line(unit_price="-1")), "would_refuse", FigureFindingCode.LINE_AMOUNT_NEGATIVE),
    _Case(
        "rate-withdrawn",
        _lines(_line(iva_rate="RATE_5")),
        "would_refuse",
        FigureFindingCode.LINE_RATE_NOT_IN_FORCE,
    ),
    _Case(
        "rate-undeclared",
        _lines(_line(iva_rate="RATE_99")),
        "would_refuse",
        FigureFindingCode.LINE_RATE_UNDECLARED,
    ),
    # RDL 4/2024: 7.5 % stood in the last quarter of 2024. 100.00 + 7.50.
    _Case(
        "rate-in-force-on-its-date",
        {"issued_at": date(2024, 11, 1), **_lines(_line(iva_rate="RATE_7.5"))},
        "would_accept",
        total="107.50",
    ),
    # The operation date decides over the issue date.
    _Case(
        "operation-date-decides",
        {"operation_date": date(2024, 11, 1), **_lines(_line(iva_rate="RATE_7.5"))},
        "would_accept",
        total="107.50",
    ),
    _Case(
        "exempt-cuota-not-zero",
        _lines(_line(iva_rate="EXEMPT", iva_amount="0.01")),
        "would_refuse",
        FigureFindingCode.LINE_IVA_NOT_ZERO_FOR_NONNUMERIC,
    ),
    _Case("exempt", _lines(_line(iva_rate="EXEMPT")), "would_accept", total="100.00"),
    # Two tiers: (100.00 + 21.00) + (50.00 + 5.00).
    _Case(
        "two-rates",
        _lines(_line("a"), _line("b", quantity="2", unit_price="25.00", iva_rate="RATE_10")),
        "would_accept",
        total="176.00",
    ),
    # A sub-cent stated subtotal cannot equal a base rounded to the cent.
    _Case(
        "sub-cent-subtotal",
        _lines(_line(subtotal="100.005")),
        "would_refuse",
        FigureFindingCode.BASE_TOTAL_NOT_LINE_SUM,
    ),
    # 100.00 + 21.00 + 5.20 recargo inside the total.
    _Case("recargo", {"recargo_amount": _decimal("5.20")}, "would_accept", total="126.20"),
    _Case(
        "recargo-above-cuota",
        {"recargo_amount": _decimal("21.01")},
        "would_refuse",
        FigureFindingCode.RECARGO_ABOVE_IVA_TOTAL,
    ),
    _Case("recargo-negative", {"recargo_amount": _decimal("-1")}, "would_refuse", FigureFindingCode.RECARGO_NEGATIVE),
    _Case(
        "recargo-on-exempt",
        {"recargo_amount": _decimal("1"), **_lines(_line(iva_rate="EXEMPT"))},
        "would_refuse",
        FigureFindingCode.NONNUMERIC_RECARGO_NOT_ZERO,
    ),
    # 100.00 x 0.15 = 15.00, outside the total.
    _Case(
        "retention",
        {"retention_rate": _decimal("0.15"), "retention_amount": _decimal("15.00")},
        "would_accept",
        total="121.00",
    ),
    _Case(
        "retention-cent",
        {"retention_rate": _decimal("0.15"), "retention_amount": _decimal("15.01")},
        "would_accept",
        total="121.00",
    ),
    _Case(
        "retention-beyond",
        {"retention_rate": _decimal("0.15"), "retention_amount": _decimal("15.02")},
        "would_refuse",
        FigureFindingCode.RETENTION_AMOUNT_MISMATCH,
    ),
    # 100.50 x 0.155 = 15.5775: 15.58 is inside the cent and 15.59 is outside, though both round alike.
    _Case(
        "retention-unrounded-inside",
        {
            "retention_rate": _decimal("0.155"),
            "retention_amount": _decimal("15.58"),
            **_lines(_line(unit_price="100.50")),
        },
        "would_accept",
    ),
    _Case(
        "retention-unrounded-outside",
        {
            "retention_rate": _decimal("0.155"),
            "retention_amount": _decimal("15.59"),
            **_lines(_line(unit_price="100.50")),
        },
        "would_refuse",
        FigureFindingCode.RETENTION_AMOUNT_MISMATCH,
    ),
    _Case("retention-alone", {"retention_amount": _decimal("99")}, "would_accept", total="121.00"),
    _Case(
        "retention-above-base",
        {"retention_amount": _decimal("100.01")},
        "would_refuse",
        FigureFindingCode.RETENTION_AMOUNT_ABOVE_BASE,
    ),
    _Case(
        "retention-rate-alone",
        {"retention_rate": _decimal("0.15")},
        "would_refuse",
        FigureFindingCode.RETENTION_RATE_WITHOUT_AMOUNT,
    ),
    _Case(
        "retention-percent-as-fraction",
        {"retention_rate": _decimal("15"), "retention_amount": _decimal("15.00")},
        "would_refuse",
        FigureFindingCode.RETENTION_RATE_OUT_OF_RANGE,
    ),
    # A rule outside the figures owner still refuses, under the add operation's own code.
    _Case("tax-id-missing", {"counterparty_tax_id": None}, "would_refuse", "invalid_invoice"),
    _Case("country-malformed", {"counterparty_country": "SPAIN"}, "would_refuse", "invalid_invoice"),
    _Case("description-blank", _lines(_line(description="  ")), "would_refuse", "invalid_invoice"),
    _Case("currency-malformed", {"currency": "E1"}, "would_refuse", "invalid_invoice"),
    _Case("tax-id-malformed", {"counterparty_tax_id": "NOT-A-TAX-ID"}, "would_refuse", "invalid_invoice"),
)


@pytest.mark.parametrize("case", _TABLE, ids=lambda case: case.name)
def test_every_verdict_is_the_builders_own(case: _Case, operation: PinnedAuthorityOperation) -> None:
    draft = _draft(**case.draft)
    answer = preview_invoice_figures(draft, operation=operation)

    assert answer.verdict == case.verdict
    assert answer.missing_fields == ()
    assert answer.refusal_code == case.code
    if case.total is not None:
        assert answer.totals.total == PublicDecimal(decimal=case.total)

    if case.verdict == "would_accept":
        assert _accepted_by_the_builder(draft, answer, operation) == answer.invoice_id
        assert all(finding.severity.value == "warning" for finding in answer.findings)
        return
    assert answer.invoice_id is None
    with pytest.raises((InvoiceValidationError, ValidationError, CoreValidationError)):
        _accepted_by_the_builder(draft, answer, operation)


@pytest.mark.parametrize(
    "case",
    tuple(case for case in _TABLE if case.verdict == "would_accept"),
    ids=lambda case: case.name,
)
def test_an_accepted_draft_runs_the_add_path_to_the_same_id_and_persists_nothing(
    case: _Case,
    operation: PinnedAuthorityOperation,
) -> None:
    """The add operation's own preparation agrees, and the preview left its catalogue empty."""
    from ..catalogue_add_contracts import InvoiceAddLine, InvoiceAddRequest

    draft = _draft(**case.draft)
    answer = preview_invoice_figures(draft, operation=operation)
    ports = in_memory_catalogue_creation_ports()
    payload = InvoiceAddRequest(
        profile_id=_PROFILE,
        kind=InvoiceKind.RECEIVED,
        counterparty_name="Synthetic supplier",
        counterparty_tax_id="A58818501",
        counterparty_country="ES",
        invoice_number="SYN-2026-001",
        issued_at=draft.issued_at or _APRIL,
        operation_date=draft.operation_date,
        currency="EUR",
        recargo_amount=draft.recargo_amount,
        retention_rate=draft.retention_rate,
        retention_amount=draft.retention_amount,
        lines=tuple(
            InvoiceAddLine(
                description=str(line.description),
                quantity=line.quantity or PublicDecimal(decimal="1"),
                unit_price=line.unit_price or PublicDecimal(decimal="1"),
                subtotal=result.subtotal.submitted or PublicDecimal(decimal="0"),
                iva_rate=str(line.iva_rate),
                iva_amount=result.iva_amount.submitted or PublicDecimal(decimal="0"),
            )
            for line, result in zip(draft.lines, answer.lines, strict=True)
        ),
    )

    _ports, invoice, _advisory = _prepare_invoice_add(
        factory=lambda *, bucket_id: ports,
        payload=payload,
        profile=str(_PROFILE),
        authority_operation=operation,
    )

    assert invoice.invoice_id == answer.invoice_id
    assert len(ports.invoice_repository.load()) == 0


def test_a_class_the_registry_does_not_declare_is_refused_as_the_add_path_refuses(
    operation: PinnedAuthorityOperation,
) -> None:
    answer = preview_invoice_figures(_draft(invoice_class="UNDECLARED"), operation=operation)

    assert answer.verdict == "would_refuse"
    assert answer.refusal_code == "invalid_invoice"


def test_the_stated_figure_comes_back_beside_the_backends_with_its_verdict(
    operation: PinnedAuthorityOperation,
) -> None:
    within = preview_invoice_figures(_draft(_line(iva_amount="21.01")), operation=operation).lines[0].iva_amount
    assert within.computed == PublicDecimal(decimal="21.00")
    assert within.stated == PublicDecimal(decimal="21.01")
    assert within.verdict is StatedFigureVerdict.WITHIN_TOLERANCE
    assert within.submitted == PublicDecimal(decimal="21.01")

    refused = preview_invoice_figures(_draft(_line(iva_amount="21.02")), operation=operation).lines[0].iva_amount
    assert refused.computed == PublicDecimal(decimal="21.00")
    assert refused.verdict is StatedFigureVerdict.REFUSED
    assert refused.submitted is None


def test_a_differing_printed_total_warns_and_never_blocks(operation: PinnedAuthorityOperation) -> None:
    answer = preview_invoice_figures(_draft(printed_total=_decimal("121.01")), operation=operation)

    assert answer.verdict == "would_accept"
    assert [finding.code for finding in answer.findings] == [FigureFindingCode.PRINTED_TOTAL_DIFFERS]
    assert answer.findings[0].severity.value == "warning"


def test_an_empty_draft_is_incomplete_with_null_figures_never_zero(operation: PinnedAuthorityOperation) -> None:
    answer = preview_invoice_figures(
        InvoiceFiguresPreviewRequest(
            profile_id=_PROFILE,
            lines=(InvoiceFiguresPreviewLine(key="a"),),
        ),
        operation=operation,
    )

    assert answer.verdict == "incomplete"
    assert answer.on_date_source == "today"
    assert {"kind", "issued_at", "lines.a.quantity", "lines.a.iva_rate"} <= set(answer.missing_fields)
    line = answer.lines[0]
    assert line.subtotal.computed is None
    assert line.iva_amount.computed is None
    assert answer.totals.model_dump() == {
        "base": None,
        "iva": None,
        "recargo": None,
        "total": None,
        "net_of_retention": None,
    }
    assert answer.invoice_id is None


def test_a_bare_base_stays_incomplete_and_still_answers_the_retention(operation: PinnedAuthorityOperation) -> None:
    answer = preview_invoice_figures(
        InvoiceFiguresPreviewRequest(
            profile_id=_PROFILE,
            issued_at=_APRIL,
            base_total=_decimal("100.50"),
            retention_rate=_decimal("0.155"),
            retention_amount=_decimal("15.59"),
        ),
        operation=operation,
    )

    assert answer.verdict == "incomplete"
    assert "lines" in answer.missing_fields
    assert answer.totals.iva is None
    assert answer.totals.total is None
    assert answer.retention.implied == PublicDecimal(decimal="15.58")
    assert [finding.code for finding in answer.findings] == [FigureFindingCode.RETENTION_AMOUNT_MISMATCH]


def test_rate_slots_follow_the_draft_date_through_the_real_authority(operation: PinnedAuthorityOperation) -> None:
    answer = preview_invoice_figures(_draft(), operation=operation)
    slots = {slot.slot: slot for slot in answer.rate_slots}

    assert slots["RATE_21"].fraction == PublicDecimal(decimal="0.21")
    assert slots["RATE_21"].in_force
    assert not slots["RATE_5"].in_force
    assert slots["RATE_5"].fraction is None
    assert slots["EXEMPT"].in_force
    assert slots["EXEMPT"].fraction is None
    assert slots["RATE_7.5"].label_key == "application.invoices.figures_preview.rate_slot.rate_7_5"


def test_a_date_before_the_registry_floor_is_a_typed_finding_and_invents_no_rate(
    operation: PinnedAuthorityOperation,
) -> None:
    floor = operation.supported_filing_years().date_envelope().floor
    before = floor - timedelta(days=1)
    draft = _draft(issued_at=before)

    answer = preview_invoice_figures(draft, operation=operation)

    assert answer.verdict == "would_refuse"
    assert answer.refusal_code is FigureFindingCode.RATE_DATE_UNRESOLVED
    assert answer.rate_slots == ()
    assert FigureFindingCode.RATE_DATE_UNRESOLVED in [finding.code for finding in answer.findings]
    # The subtotal needs no rate; the cuota and everything summed from it stay unknown.
    assert answer.lines[0].subtotal.computed == PublicDecimal(decimal="100.00")
    assert answer.lines[0].iva_amount.computed is None
    assert answer.totals.iva is None
    assert answer.totals.total is None
    # Today's add path fails on the same date, so the refusal is true of acceptance.
    with pytest.raises(RegistryValidationError):
        _accepted_by_the_builder(draft, answer, operation)


def test_a_stated_cuota_before_the_floor_is_not_treated_as_checked(operation: PinnedAuthorityOperation) -> None:
    floor = operation.supported_filing_years().date_envelope().floor
    answer = preview_invoice_figures(
        _draft(_line(iva_amount="21.00"), issued_at=floor - timedelta(days=1)),
        operation=operation,
    )

    assert answer.verdict == "would_refuse"
    assert answer.lines[0].iva_amount.verdict is StatedFigureVerdict.NOT_CHECKED
    assert answer.lines[0].iva_amount.submitted is None


def test_a_registry_failure_inside_its_support_stays_a_failure(
    operation: PinnedAuthorityOperation,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def corrupt(_on_date: date) -> tuple[()]:
        raise RegistryValidationError("corrupt authority")

    monkeypatch.setattr(preview_operation, "dated_rate_slots", corrupt)

    with pytest.raises(RegistryValidationError):
        preview_invoice_figures(_draft(), operation=operation)


def test_a_registry_failure_during_acceptance_inside_its_support_stays_a_failure(
    operation: PinnedAuthorityOperation,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def corrupt(**_kwargs: object) -> None:
        raise RegistryValidationError("corrupt authority")

    monkeypatch.setattr(preview_operation, "build_invoice_from_add_request", corrupt)

    with pytest.raises(RegistryValidationError):
        preview_invoice_figures(_draft(), operation=operation)


def test_a_magnitude_beyond_decimal_arithmetic_is_a_typed_refusal(operation: PinnedAuthorityOperation) -> None:
    answer = preview_invoice_figures(_draft(_line(quantity="1E+30")), operation=operation)

    assert answer.verdict == "would_refuse"
    assert answer.refusal_code is FigureFindingCode.FIGURE_OUT_OF_RANGE


def test_a_foreign_draft_never_asks_a_rate_source_and_keeps_its_id(operation: PinnedAuthorityOperation) -> None:
    answer = preview_invoice_figures(_draft(currency="USD"), operation=operation)

    assert answer.verdict == "would_accept"
    assert answer.invoice_id is not None


def test_the_digest_binds_the_answer_to_the_draft(operation: PinnedAuthorityOperation) -> None:
    first = preview_invoice_figures(_draft(), operation=operation)
    again = preview_invoice_figures(_draft(), operation=operation)
    other = preview_invoice_figures(_draft(_line(unit_price="100.01")), operation=operation)

    assert first.input_digest == again.input_digest
    assert first.input_digest != other.input_digest


@pytest.mark.parametrize(
    "values",
    (
        {"lines": (_line(),), "base_total": _decimal("1")},
        {"lines": (_line("same"), _line("same"))},
    ),
    ids=("lines-and-base", "duplicate-keys"),
)
def test_the_request_refuses_an_incoherent_shape(values: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        InvoiceFiguresPreviewRequest.model_validate({"profile_id": _PROFILE, **values})


def test_the_request_round_trips_through_json() -> None:
    draft = _draft(printed_total=_decimal("121.00"))

    assert InvoiceFiguresPreviewRequest.model_validate_json(draft.model_dump_json()) == draft


class _Operands:
    def __init__(self) -> None:
        self.value: InvoiceFiguresPreviewExecutionResult | None = None

    async def put(self, operand: object, *, written_at: object) -> str:
        assert isinstance(operand, InvoiceFiguresPreviewExecutionResult)
        self.value = operand
        return "d" * 64


class _Events:
    def __init__(self) -> None:
        self.phases: list[str] = []

    async def phase(self, phase_code: str) -> None:
        self.phases.append(phase_code)


def _executor_context(authority: PinnedAuthorityOperation, subject: str) -> tuple[OperationExecutorContext, _Operands]:
    operands = _Operands()
    context = SimpleNamespace(
        identity=OperationIdentity(
            operation_id="a" * 64,
            definition_id=INVOICE_FIGURES_PREVIEW_OPERATION_DEFINITION_ID,
            subject_ref=subject,
        ),
        authority_operation=authority,
        events=_Events(),
        operands=operands,
    )
    return cast(OperationExecutorContext, context), operands


def test_the_executor_answers_inside_the_exact_profile(
    operation: PinnedAuthorityOperation,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(preview_operation, "require_active_bucket_id", lambda: str(_PROFILE))
    subject = profile_operation_subject(str(_PROFILE))
    context, operands = _executor_context(operation, subject)
    request = OperationRequest[InvoiceFiguresPreviewRequest](
        definition_id=INVOICE_FIGURES_PREVIEW_OPERATION_DEFINITION_ID,
        subject_ref=subject,
        payload=_draft(),
    )

    reference = asyncio.run(InvoiceFiguresPreviewExecutor().execute(request, context))

    assert reference == "d" * 64
    assert operands.value is not None
    assert operands.value.result.verdict == "would_accept"


def test_the_executor_refuses_a_foreign_active_profile(
    operation: PinnedAuthorityOperation,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from ...user_profile.access_errors import ProfileAccessRefusedError

    monkeypatch.setattr(preview_operation, "require_active_bucket_id", lambda: "another-profile")
    subject = profile_operation_subject(str(_PROFILE))
    context, operands = _executor_context(operation, subject)
    request = OperationRequest[InvoiceFiguresPreviewRequest](
        definition_id=INVOICE_FIGURES_PREVIEW_OPERATION_DEFINITION_ID,
        subject_ref=subject,
        payload=_draft(),
    )

    with pytest.raises(ProfileAccessRefusedError):
        asyncio.run(InvoiceFiguresPreviewExecutor().execute(request, context))
    assert operands.value is None


def test_the_definition_is_a_read_holding_its_input_in_secure_custody() -> None:
    definition = build_invoice_figures_preview_definition()

    assert definition.capabilities.request_storage.value == "secure_reference"
    assert definition.capabilities.sensitive_input.value == "secure_reference"
