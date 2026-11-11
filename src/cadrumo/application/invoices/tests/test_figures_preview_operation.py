"""The preview answers what acceptance answers, for every draft in the table.

The key property is asserted through the real builder rather than through the
preview's own path. Expected figures are worked by hand in the comments.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

from ....core.aggregation import IntracomOperationType
from ....core.errors.hierarchy import CoreValidationError
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.errors import RegistryValidationError
from ....domain.calculations.registry.tests.authority_lease_support import private_authority_lease
from ....domain.currency.models import EurRateLookup, EurRateLookupStatus
from ....domain.invoices.enums import IvaRate
from ....domain.invoices.errors import InvoiceValidationError
from ....domain.invoices.figures import FigureFindingCode, StatedFigureVerdict
from ....domain.invoices.models import InvoiceLine
from ....domain.invoices.rule_findings import InvoiceRuleFindingCode
from ....domain.iva.schema import InvoiceKind
from ...operations.public_scalar import PublicDecimal, restore_facts
from .. import figures_preview_operation as preview_operation
from ..catalogue_add_contracts import InvoiceAddRequest
from ..catalogue_add_operation import build_invoice_from_add_request, invoice_add_lease, prepare_invoice_add
from ..catalogue_creation import build_catalogue_invoice
from ..catalogue_creation_ports import CatalogueInvoiceRateError, CatalogueInvoiceRateProviderPort
from ..catalogue_lifecycle import CatalogueInvoicePatch
from ..figures_preview_contracts import (
    INVOICE_CORRECTION_JUDGED_FIELDS,
    InvoiceFiguresPreviewLine,
    InvoiceFiguresPreviewRequest,
    InvoiceFiguresPreviewResult,
    InvoiceFiguresPreviewStored,
)
from ..figures_preview_operation import (
    preview_invoice_figures,
)
from ..tests.catalogue_creation_fakes import in_memory_catalogue_creation_ports
from .figures_preview_support import APRIL, PROFILE, NoRate, Unreachable, preview_draft, preview_line, public_decimal

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


class _Answering:
    """A rate source that answers one status the way the host's source would."""

    rate_source_id = "synthetic"

    def __init__(self, status: EurRateLookupStatus) -> None:
        self._status = status
        self.asked: list[tuple[str, date]] = []

    def lookup_eur_rate(self, currency: str, rate_date: date) -> EurRateLookup:
        self.asked.append((currency, rate_date))
        if self._status is EurRateLookupStatus.FOUND:
            return EurRateLookup(
                status=self._status,
                rate_date=rate_date,
                source="synthetic",
                rate=Decimal("0.9"),
                observation_date=rate_date,
            )
        return EurRateLookup(status=self._status, rate_date=rate_date, source="synthetic")


def _preview(
    request: InvoiceFiguresPreviewRequest,
    *,
    operation: PinnedAuthorityOperation,
    rate_provider: CatalogueInvoiceRateProviderPort | None = None,
) -> InvoiceFiguresPreviewResult:
    return preview_invoice_figures(request, operation=operation, rate_provider=rate_provider or NoRate())


@pytest.fixture
def operation() -> Iterator[PinnedAuthorityOperation]:
    with private_authority_lease() as leased:
        yield leased


def _accepted_by_the_builder(
    draft: InvoiceFiguresPreviewRequest,
    answer: InvoiceFiguresPreviewResult,
    operation: PinnedAuthorityOperation,
    rate_provider: CatalogueInvoiceRateProviderPort,
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
        bucket_id=str(PROFILE),
        kind=draft.kind or InvoiceKind.RECEIVED,
        counterparty_name=str(draft.counterparty_name),
        counterparty_tax_id=draft.counterparty_tax_id,
        counterparty_country=str(draft.counterparty_country),
        invoice_number=str(draft.invoice_number),
        issued_at=draft.issued_at or APRIL,
        operation_date=draft.operation_date,
        currency=str(draft.currency),
        retention_rate=_optional(draft.retention_rate),
        retention_amount=_optional(draft.retention_amount),
        recargo_amount=_optional(draft.recargo_amount),
        lines=lines,
        rate_provider=rate_provider,
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
    rule: InvoiceRuleFindingCode | None = None
    rates: EurRateLookupStatus = EurRateLookupStatus.MISSING_RATE


def _lines(*lines: InvoiceFiguresPreviewLine) -> dict[str, object]:
    return {"lines": lines}


_TABLE = (
    # 100.00 + 21.00
    _Case("computed", {}, "would_accept", total="121.00"),
    _Case("stated-exact", _lines(preview_line(subtotal="100.00", iva_amount="21.00")), "would_accept", total="121.00"),
    # A printed cuota inside its cent is stored as printed: 100.00 + 21.01.
    _Case("stated-iva-cent", _lines(preview_line(iva_amount="21.01")), "would_accept", total="121.01"),
    # 100.01 x 0.21 = 21.0021, which a computed 21.00 satisfies: 100.01 + 21.00.
    _Case("stated-subtotal-cent", _lines(preview_line(subtotal="100.01")), "would_accept", total="121.01"),
    # A foreign currency resolves its rate through the source add uses, whatever that source answers.
    _Case("foreign-rate-found", {"currency": "USD"}, "would_accept", total="121.00", rates=EurRateLookupStatus.FOUND),
    _Case("foreign-rate-missing", {"currency": "USD"}, "would_accept", total="121.00"),
    _Case(
        "foreign-currency-unsupported",
        {"currency": "USD"},
        "would_accept",
        total="121.00",
        rates=EurRateLookupStatus.UNSUPPORTED_CURRENCY,
    ),
    _Case(
        "foreign-refused-by-figures",
        {**_lines(preview_line(iva_amount="21.02")), "currency": "USD"},
        "would_refuse",
        FigureFindingCode.LINE_IVA_MISMATCH,
        rates=EurRateLookupStatus.FOUND,
    ),
    _Case(
        "stated-iva-beyond",
        _lines(preview_line(iva_amount="21.02")),
        "would_refuse",
        FigureFindingCode.LINE_IVA_MISMATCH,
    ),
    _Case(
        "stated-subtotal-beyond",
        _lines(preview_line(subtotal="100.02")),
        "would_refuse",
        FigureFindingCode.LINE_SUBTOTAL_MISMATCH,
    ),
    _Case(
        "quantity-zero",
        _lines(preview_line(quantity="0")),
        "would_refuse",
        FigureFindingCode.LINE_QUANTITY_NOT_POSITIVE,
    ),
    _Case(
        "price-negative", _lines(preview_line(unit_price="-1")), "would_refuse", FigureFindingCode.LINE_AMOUNT_NEGATIVE
    ),
    _Case(
        "rate-withdrawn",
        _lines(preview_line(iva_rate="RATE_5")),
        "would_refuse",
        FigureFindingCode.LINE_RATE_NOT_IN_FORCE,
    ),
    _Case(
        "rate-undeclared",
        _lines(preview_line(iva_rate="RATE_99")),
        "would_refuse",
        FigureFindingCode.LINE_RATE_UNDECLARED,
    ),
    # RDL 4/2024: 7.5 % stood in the last quarter of 2024. 100.00 + 7.50.
    _Case(
        "rate-in-force-on-its-date",
        {"issued_at": date(2024, 11, 1), **_lines(preview_line(iva_rate="RATE_7.5"))},
        "would_accept",
        total="107.50",
    ),
    # The operation date decides over the issue date.
    _Case(
        "operation-date-decides",
        {"operation_date": date(2024, 11, 1), **_lines(preview_line(iva_rate="RATE_7.5"))},
        "would_accept",
        total="107.50",
    ),
    _Case(
        "exempt-cuota-not-zero",
        _lines(preview_line(iva_rate="EXEMPT", iva_amount="0.01")),
        "would_refuse",
        FigureFindingCode.LINE_IVA_NOT_ZERO_FOR_NONNUMERIC,
    ),
    _Case("exempt", _lines(preview_line(iva_rate="EXEMPT")), "would_accept", total="100.00"),
    # Two tiers: (100.00 + 21.00) + (50.00 + 5.00).
    _Case(
        "two-rates",
        _lines(preview_line("a"), preview_line("b", quantity="2", unit_price="25.00", iva_rate="RATE_10")),
        "would_accept",
        total="176.00",
    ),
    # A sub-cent stated subtotal cannot equal a base rounded to the cent.
    _Case(
        "sub-cent-subtotal",
        _lines(preview_line(subtotal="100.005")),
        "would_refuse",
        FigureFindingCode.BASE_TOTAL_NOT_LINE_SUM,
    ),
    # 100.00 + 21.00 + 5.20 recargo inside the total.
    _Case("recargo", {"recargo_amount": public_decimal("5.20")}, "would_accept", total="126.20"),
    _Case(
        "recargo-above-cuota",
        {"recargo_amount": public_decimal("21.01")},
        "would_refuse",
        FigureFindingCode.RECARGO_ABOVE_IVA_TOTAL,
    ),
    _Case(
        "recargo-negative", {"recargo_amount": public_decimal("-1")}, "would_refuse", FigureFindingCode.RECARGO_NEGATIVE
    ),
    _Case(
        "recargo-on-exempt",
        {"recargo_amount": public_decimal("1"), **_lines(preview_line(iva_rate="EXEMPT"))},
        "would_refuse",
        FigureFindingCode.NONNUMERIC_RECARGO_NOT_ZERO,
    ),
    # 100.00 x 0.15 = 15.00, outside the total.
    _Case(
        "retention",
        {"retention_rate": public_decimal("0.15"), "retention_amount": public_decimal("15.00")},
        "would_accept",
        total="121.00",
    ),
    _Case(
        "retention-cent",
        {"retention_rate": public_decimal("0.15"), "retention_amount": public_decimal("15.01")},
        "would_accept",
        total="121.00",
    ),
    _Case(
        "retention-beyond",
        {"retention_rate": public_decimal("0.15"), "retention_amount": public_decimal("15.02")},
        "would_refuse",
        FigureFindingCode.RETENTION_AMOUNT_MISMATCH,
    ),
    # 100.50 x 0.155 = 15.5775: 15.58 is inside the cent and 15.59 is outside, though both round alike.
    _Case(
        "retention-unrounded-inside",
        {
            "retention_rate": public_decimal("0.155"),
            "retention_amount": public_decimal("15.58"),
            **_lines(preview_line(unit_price="100.50")),
        },
        "would_accept",
    ),
    _Case(
        "retention-unrounded-outside",
        {
            "retention_rate": public_decimal("0.155"),
            "retention_amount": public_decimal("15.59"),
            **_lines(preview_line(unit_price="100.50")),
        },
        "would_refuse",
        FigureFindingCode.RETENTION_AMOUNT_MISMATCH,
    ),
    _Case("retention-alone", {"retention_amount": public_decimal("99")}, "would_accept", total="121.00"),
    _Case(
        "retention-above-base",
        {"retention_amount": public_decimal("100.01")},
        "would_refuse",
        FigureFindingCode.RETENTION_AMOUNT_ABOVE_BASE,
    ),
    _Case(
        "retention-rate-alone",
        {"retention_rate": public_decimal("0.15")},
        "would_refuse",
        FigureFindingCode.RETENTION_RATE_WITHOUT_AMOUNT,
    ),
    _Case(
        "retention-percent-as-fraction",
        {"retention_rate": public_decimal("15"), "retention_amount": public_decimal("15.00")},
        "would_refuse",
        FigureFindingCode.RETENTION_RATE_OUT_OF_RANGE,
    ),
    # A rule outside the figures owner still refuses, under the add operation's own code.
    _Case(
        "tax-id-missing",
        {"counterparty_tax_id": None},
        "would_refuse",
        "invalid_invoice",
        rule=InvoiceRuleFindingCode.COUNTERPARTY_TAX_ID_REQUIRED,
    ),
    _Case(
        "country-malformed",
        {"counterparty_country": "SPAIN"},
        "would_refuse",
        "invalid_invoice",
        rule=InvoiceRuleFindingCode.COUNTERPARTY_COUNTRY_INVALID,
    ),
    _Case(
        "description-blank",
        _lines(preview_line(description="  ")),
        "would_refuse",
        "invalid_invoice",
        rule=InvoiceRuleFindingCode.LINE_DESCRIPTION_BLANK,
    ),
    _Case(
        "currency-malformed",
        {"currency": "E1"},
        "would_refuse",
        "invalid_invoice",
        rule=InvoiceRuleFindingCode.CURRENCY_INVALID,
    ),
    _Case(
        "tax-id-malformed",
        {"counterparty_tax_id": "NOT-A-TAX-ID"},
        "would_refuse",
        "invalid_invoice",
        rule=InvoiceRuleFindingCode.COUNTERPARTY_TAX_ID_INVALID,
    ),
)

_ISSUED_FRENCH = {
    "kind": InvoiceKind.ISSUED,
    "counterparty_tax_id": "FR40303265045",
    "counterparty_country": "FR",
}
_ON_SPANISH_PREMISES = "spain_other_than_basque_navarre"


def _leased(situation: str, reference: str | None) -> dict[str, object]:
    return {
        "kind": InvoiceKind.ISSUED,
        "business_premises_lease": {"situacion_inmueble": situation, "referencia_catastral": reference},
    }


# Each rule's row runs add's own request decoding and builder, so an answer here
# cannot agree merely because it read its own path.
_RULE_TABLE = (
    _Case("ordinary", {}, "would_accept"),
    _Case(
        "checksum-wrong",
        {"counterparty_tax_id": "B00000282"},
        "would_refuse",
        "invalid_invoice",
        rule=InvoiceRuleFindingCode.COUNTERPARTY_TAX_ID_INVALID,
    ),
    _Case(
        "rectificativa-without-series-or-number",
        {"invoice_class": "RECTIFICATIVA"},
        "would_refuse",
        "invalid_invoice",
        rule=InvoiceRuleFindingCode.SERIES_REQUIRED_FOR_RECTIFICATIVA,
    ),
    _Case(
        "rectificativa-without-number",
        {"invoice_class": "RECTIFICATIVA", "series": "R"},
        "would_refuse",
        "invalid_invoice",
        rule=InvoiceRuleFindingCode.RECTIFIED_INVOICE_REQUIRED,
    ),
    _Case(
        "rectificativa-with-blank-series",
        {"invoice_class": "RECTIFICATIVA", "series": "   ", "rectifies_invoice_number": "F-1"},
        "would_refuse",
        "invalid_invoice",
        rule=InvoiceRuleFindingCode.SERIES_REQUIRED_FOR_RECTIFICATIVA,
    ),
    _Case(
        "rectificativa-whole",
        {"invoice_class": "RECTIFICATIVA", "series": "R", "rectifies_invoice_number": "F-1"},
        "would_accept",
    ),
    _Case(
        "rectified-number-on-ordinary",
        {"rectifies_invoice_number": "F-1"},
        "would_refuse",
        "invalid_invoice",
        rule=InvoiceRuleFindingCode.RECTIFIED_INVOICE_NOT_ALLOWED,
    ),
    # RD 1619/2012 art. 6.1.d: the relief covers an issued simplificada, not a received one.
    _Case(
        "simplificada-issued-relieved",
        {"invoice_class": "SIMPLIFICADA", "kind": InvoiceKind.ISSUED, "counterparty_tax_id": None},
        "would_accept",
    ),
    _Case(
        "simplificada-received-needs-tax-id",
        {"invoice_class": "SIMPLIFICADA", "counterparty_tax_id": None},
        "would_refuse",
        "invalid_invoice",
        rule=InvoiceRuleFindingCode.COUNTERPARTY_TAX_ID_REQUIRED,
    ),
    _Case(
        "simplificada-category-mandates-tax-id",
        {
            "invoice_class": "SIMPLIFICADA",
            "kind": InvoiceKind.ISSUED,
            "counterparty_tax_id": None,
            "iva_category": "domestic_reverse_charge",
        },
        "would_refuse",
        "invalid_invoice",
        rule=InvoiceRuleFindingCode.COUNTERPARTY_TAX_ID_REQUIRED_BY_CATEGORY,
    ),
    _Case(
        "simplificada-for-intra-community",
        {
            **_ISSUED_FRENCH,
            "invoice_class": "SIMPLIFICADA",
            "iva_category": "intra_community_supply",
            "operation_type": IntracomOperationType("E"),
        },
        "would_refuse",
        "invalid_invoice",
        rule=InvoiceRuleFindingCode.SIMPLIFICADA_NOT_FOR_INTRA_COMMUNITY,
    ),
    _Case(
        "operation-type-required",
        {**_ISSUED_FRENCH, "iva_category": "intra_community_supply"},
        "would_refuse",
        "invalid_invoice",
        rule=InvoiceRuleFindingCode.OPERATION_TYPE_REQUIRED,
    ),
    _Case(
        "operation-type-stated",
        {**_ISSUED_FRENCH, "iva_category": "intra_community_supply", "operation_type": IntracomOperationType("E")},
        "would_accept",
    ),
    _Case(
        "class-undeclared",
        {"invoice_class": "UNDECLARED"},
        "would_refuse",
        "invalid_invoice",
        rule=InvoiceRuleFindingCode.INVOICE_CLASS_UNDECLARED,
    ),
    _Case(
        "category-undeclared",
        {"iva_category": "undeclared"},
        "would_refuse",
        "invalid_invoice",
        rule=InvoiceRuleFindingCode.IVA_CATEGORY_UNDECLARED,
    ),
    _Case(
        "name-blank",
        {"counterparty_name": "   "},
        "would_refuse",
        "invalid_invoice",
        rule=InvoiceRuleFindingCode.COUNTERPARTY_NAME_BLANK,
    ),
    _Case(
        "lease-on-received",
        {**_leased(_ON_SPANISH_PREMISES, None), "kind": InvoiceKind.RECEIVED},
        "would_refuse",
        "invalid_invoice",
        rule=InvoiceRuleFindingCode.LEASE_ONLY_ON_ISSUED,
    ),
    _Case("lease-reference-25", _leased(_ON_SPANISH_PREMISES, "A" * 25), "would_accept"),
    # The Modelo 347 design gives the reference 25 positions; add's wire takes 32 and the record 64.
    _Case(
        "lease-reference-26",
        _leased(_ON_SPANISH_PREMISES, "A" * 26),
        "would_refuse",
        "invalid_invoice",
        rule=InvoiceRuleFindingCode.LEASE_REFERENCE_TOO_LONG,
    ),
    _Case(
        "lease-reference-33",
        _leased(_ON_SPANISH_PREMISES, "A" * 33),
        "would_refuse",
        "invalid_invoice",
        rule=InvoiceRuleFindingCode.LEASE_REFERENCE_TOO_LONG,
    ),
    _Case(
        "lease-reference-abroad",
        _leased("abroad", "A"),
        "would_refuse",
        "invalid_invoice",
        rule=InvoiceRuleFindingCode.LEASE_REFERENCE_NOT_ALLOWED,
    ),
    _Case(
        "lease-situation-undeclared",
        _leased("nowhere", None),
        "would_refuse",
        "invalid_invoice",
        rule=InvoiceRuleFindingCode.LEASE_SITUATION_UNDECLARED,
    ),
    _Case(
        "description-beyond-the-line",
        _lines(preview_line(description="x" * 4097)),
        "would_refuse",
        "invalid_invoice",
        rule=InvoiceRuleFindingCode.LINE_DESCRIPTION_TOO_LONG,
    ),
    _Case("counterparty-name-at-the-bound", {"counterparty_name": "n" * 256}, "would_accept"),
    _Case(
        "counterparty-name-beyond-the-bound",
        {"counterparty_name": "n" * 257},
        "would_refuse",
        "invalid_invoice",
        rule=InvoiceRuleFindingCode.COUNTERPARTY_NAME_TOO_LONG,
    ),
)


def _added_by_add_itself(
    draft: InvoiceFiguresPreviewRequest,
    answer: InvoiceFiguresPreviewResult,
    operation: PinnedAuthorityOperation,
) -> str:
    """Send the draft through add's own wire decoding and builder."""
    body = draft.model_dump(mode="json", exclude={"printed_total", "base_total", "stored"})
    for raw, result in zip(body["lines"], answer.lines, strict=True):
        raw.pop("key")
        raw["subtotal"] = {"decimal": _figure_for_builder(result.subtotal).__str__()}
        raw["iva_amount"] = {"decimal": _figure_for_builder(result.iva_amount).__str__()}
    payload = InvoiceAddRequest.model_validate_json(json.dumps(body))
    invoice, _advisory = build_invoice_from_add_request(
        payload=payload,
        business_premises_lease=invoice_add_lease(payload, authority_operation=operation),
        profile=str(PROFILE),
        authority_operation=operation,
        rate_provider=NoRate(),
    )
    return invoice.invoice_id


def _rule_codes(answer: InvoiceFiguresPreviewResult) -> set[InvoiceRuleFindingCode]:
    return {finding.code for finding in answer.rule_findings}


@pytest.mark.parametrize("case", _TABLE, ids=lambda case: case.name)
def test_every_verdict_is_the_builders_own(case: _Case, operation: PinnedAuthorityOperation) -> None:
    draft = preview_draft(**case.draft)
    answer = _preview(draft, operation=operation, rate_provider=_Answering(case.rates))

    assert answer.verdict == case.verdict
    assert answer.missing_fields == ()
    assert answer.refusal_code == case.code
    if case.total is not None:
        assert answer.totals.total == PublicDecimal(decimal=case.total)

    if case.verdict == "would_accept":
        assert _accepted_by_the_builder(draft, answer, operation, _Answering(case.rates)) == answer.invoice_id
        assert all(finding.severity.value == "warning" for finding in answer.findings)
        return
    assert answer.invoice_id is None
    with pytest.raises((InvoiceValidationError, ValidationError, CoreValidationError)):
        _accepted_by_the_builder(draft, answer, operation, _Answering(case.rates))
    if case.rule is not None:
        assert case.rule in _rule_codes(answer)


@pytest.mark.parametrize("case", _RULE_TABLE, ids=lambda case: case.name)
def test_every_rule_names_itself_and_its_verdict_is_adds_own(case: _Case, operation: PinnedAuthorityOperation) -> None:
    draft = preview_draft(**case.draft)
    answer = _preview(draft, operation=operation)

    assert answer.verdict == case.verdict
    assert answer.verdict_scope == "whole_draft"
    if case.verdict == "would_accept":
        assert _added_by_add_itself(draft, answer, operation) == answer.invoice_id
        assert answer.rule_findings == ()
        return
    assert answer.refusal_code == case.code
    assert case.rule in _rule_codes(answer)
    assert all(
        finding.label_key == f"application.invoices.figures_preview.rule_finding.{finding.code.value}"
        for finding in answer.rule_findings
    )
    with pytest.raises((InvoiceValidationError, ValidationError, CoreValidationError)):
        _added_by_add_itself(draft, answer, operation)


@pytest.mark.parametrize("case", (*_TABLE, *_RULE_TABLE), ids=lambda case: case.name)
def test_a_refused_draft_always_says_why(case: _Case, operation: PinnedAuthorityOperation) -> None:
    answer = _preview(preview_draft(**case.draft), operation=operation)

    said = answer.rule_findings or tuple(item for item in answer.findings if item.severity.value == "refusal")
    assert bool(said) == (answer.verdict == "would_refuse")


def test_the_rule_findings_locate_a_field_and_serve_the_limit(operation: PinnedAuthorityOperation) -> None:
    too_long = _preview(preview_draft(**_leased(_ON_SPANISH_PREMISES, "A" * 26)), operation=operation)
    finding = next(
        item for item in too_long.rule_findings if item.code is InvoiceRuleFindingCode.LEASE_REFERENCE_TOO_LONG
    )
    assert finding.fields == ("referencia_catastral",)
    assert restore_facts(finding.values) == {"limit": "25"}

    described = _preview(preview_draft(preview_line("long", description="x" * 4097)), operation=operation)
    line_finding = described.rule_findings[0]
    assert (line_finding.line_key, line_finding.fields) == ("long", ("description",))
    assert restore_facts(line_finding.values) == {"limit": "4096"}


def test_an_incomplete_draft_hears_every_rule_it_can_be_asked(operation: PinnedAuthorityOperation) -> None:
    answer = _preview(
        InvoiceFiguresPreviewRequest(
            profile_id=PROFILE,
            kind=InvoiceKind.RECEIVED,
            invoice_class="RECTIFICATIVA",
            counterparty_country="ES",
        ),
        operation=operation,
    )

    assert answer.verdict == "incomplete"
    assert answer.refusal_code is None
    assert _rule_codes(answer) == {
        InvoiceRuleFindingCode.SERIES_REQUIRED_FOR_RECTIFICATIVA,
        InvoiceRuleFindingCode.RECTIFIED_INVOICE_REQUIRED,
        InvoiceRuleFindingCode.COUNTERPARTY_TAX_ID_REQUIRED,
    }


def test_without_a_kind_the_tax_id_rule_stays_unasked(operation: PinnedAuthorityOperation) -> None:
    answer = _preview(InvoiceFiguresPreviewRequest(profile_id=PROFILE), operation=operation)

    assert answer.rule_findings == ()


def _correction(**overrides: object) -> InvoiceFiguresPreviewRequest:
    values: dict[str, object] = {
        "profile_id": PROFILE,
        "kind": InvoiceKind.ISSUED,
        "invoice_class": "ORDINARIA",
        "counterparty_tax_id": "B00010157",
        "counterparty_country": "ES",
        "issued_at": APRIL,
        "base_total": public_decimal("1000.00"),
        "stored": InvoiceFiguresPreviewStored(invoice_id="f" * 64, grand_total=PublicDecimal(decimal="1210.00")),
    }
    values.update(overrides)
    return InvoiceFiguresPreviewRequest.model_validate(values)


def test_a_correction_serves_what_is_left_to_pay_on_the_stored_total(operation: PinnedAuthorityOperation) -> None:
    # 1000.00 x 0.07 = 70.00 of retención; 1210.00 stored - 70.00 = 1140.00 to pay.
    answer = _preview(
        _correction(retention_rate=public_decimal("0.07"), retention_amount=public_decimal("70.00")),
        operation=operation,
    )

    assert answer.verdict == "would_accept"
    assert answer.verdict_scope == "correction_facts"
    assert answer.invoice_id == "f" * 64
    assert answer.missing_fields == ()
    assert answer.totals.total == PublicDecimal(decimal="1210.00")
    assert answer.totals.net_of_retention == PublicDecimal(decimal="1140.00")
    assert answer.totals.iva is None


def test_a_correction_with_no_retention_owes_its_total(operation: PinnedAuthorityOperation) -> None:
    answer = _preview(_correction(), operation=operation)

    assert answer.totals.net_of_retention == PublicDecimal(decimal="1210.00")


def test_a_correction_refuses_a_retention_that_disagrees_with_the_stored_base(
    operation: PinnedAuthorityOperation,
) -> None:
    # 1000.00 x 0.07 = 70.00; 70.02 is beyond the cent.
    answer = _preview(
        _correction(retention_rate=public_decimal("0.07"), retention_amount=public_decimal("70.02")),
        operation=operation,
    )

    assert answer.verdict == "would_refuse"
    assert answer.refusal_code is FigureFindingCode.RETENTION_AMOUNT_MISMATCH
    assert answer.invoice_id is None


@pytest.mark.parametrize(
    ("overrides", "expected"),
    (
        ({"invoice_class": "RECTIFICATIVA"}, InvoiceRuleFindingCode.SERIES_REQUIRED_FOR_RECTIFICATIVA),
        ({"invoice_class": "RECTIFICATIVA", "series": "R"}, InvoiceRuleFindingCode.RECTIFIED_INVOICE_REQUIRED),
        ({"rectifies_invoice_number": "F-1"}, InvoiceRuleFindingCode.RECTIFIED_INVOICE_NOT_ALLOWED),
        ({"counterparty_tax_id": None}, InvoiceRuleFindingCode.COUNTERPARTY_TAX_ID_REQUIRED),
        ({"counterparty_tax_id": "B00000282"}, InvoiceRuleFindingCode.COUNTERPARTY_TAX_ID_INVALID),
        ({"operation_date": date(2026, 4, 1)}, InvoiceRuleFindingCode.OPERATION_DATE_ROLE_MISMATCH),
    ),
    ids=("no-series", "no-rectified-number", "number-on-ordinary", "no-tax-id", "bad-checksum", "date-without-role"),
)
def test_a_correction_serves_a_verdict_for_each_stated_rule(
    overrides: dict[str, object],
    expected: InvoiceRuleFindingCode,
    operation: PinnedAuthorityOperation,
) -> None:
    answer = _preview(_correction(**overrides), operation=operation)

    assert answer.verdict == "would_refuse"
    assert answer.refusal_code == "invalid_invoice"
    assert expected in _rule_codes(answer)


def test_a_stored_operation_date_can_move_and_cannot_be_taken_away(operation: PinnedAuthorityOperation) -> None:
    stored = InvoiceFiguresPreviewStored(
        invoice_id="f" * 64,
        grand_total=PublicDecimal(decimal="1210.00"),
        operation_date_role="OPERATION_PERFORMED",
    )

    moved = _preview(_correction(stored=stored, operation_date=date(2026, 4, 1)), operation=operation)
    taken = _preview(_correction(stored=stored), operation=operation)

    assert moved.verdict == "would_accept"
    assert taken.verdict == "would_refuse"
    assert _rule_codes(taken) == {InvoiceRuleFindingCode.OPERATION_DATE_ROLE_MISMATCH}


def test_a_correction_needs_only_the_facts_its_rules_read(operation: PinnedAuthorityOperation) -> None:
    answer = _preview(_correction(kind=None, issued_at=None, invoice_class=None), operation=operation)

    assert answer.verdict == "incomplete"
    assert answer.missing_fields == ("kind", "issued_at", "invoice_class")
    assert answer.verdict_scope == "correction_facts"


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

    draft = preview_draft(**case.draft)
    answer = _preview(draft, operation=operation)
    ports = in_memory_catalogue_creation_ports()
    payload = InvoiceAddRequest(
        profile_id=PROFILE,
        kind=InvoiceKind.RECEIVED,
        counterparty_name="Synthetic supplier",
        counterparty_tax_id="B00010157",
        counterparty_country="ES",
        invoice_number="SYN-2026-001",
        issued_at=draft.issued_at or APRIL,
        operation_date=draft.operation_date,
        currency=str(draft.currency),
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

    _ports, invoice, _advisory = prepare_invoice_add(
        factory=lambda *, bucket_id: ports,
        payload=payload,
        profile=str(PROFILE),
        authority_operation=operation,
    )

    assert invoice.invoice_id == answer.invoice_id
    assert len(ports.invoice_repository.load()) == 0


def test_a_class_the_registry_does_not_declare_is_refused_as_the_add_path_refuses(
    operation: PinnedAuthorityOperation,
) -> None:
    answer = _preview(preview_draft(invoice_class="UNDECLARED"), operation=operation)

    assert answer.verdict == "would_refuse"
    assert answer.refusal_code == "invalid_invoice"


def test_the_stated_figure_comes_back_beside_the_backends_with_its_verdict(
    operation: PinnedAuthorityOperation,
) -> None:
    within = _preview(preview_draft(preview_line(iva_amount="21.01")), operation=operation).lines[0].iva_amount
    assert within.computed == PublicDecimal(decimal="21.00")
    assert within.stated == PublicDecimal(decimal="21.01")
    assert within.verdict is StatedFigureVerdict.WITHIN_TOLERANCE
    assert within.submitted == PublicDecimal(decimal="21.01")

    refused = _preview(preview_draft(preview_line(iva_amount="21.02")), operation=operation).lines[0].iva_amount
    assert refused.computed == PublicDecimal(decimal="21.00")
    assert refused.verdict is StatedFigureVerdict.REFUSED
    assert refused.submitted is None


def test_a_differing_printed_total_warns_and_never_blocks(operation: PinnedAuthorityOperation) -> None:
    answer = _preview(preview_draft(printed_total=public_decimal("121.01")), operation=operation)

    assert answer.verdict == "would_accept"
    assert [finding.code for finding in answer.findings] == [FigureFindingCode.PRINTED_TOTAL_DIFFERS]
    assert answer.findings[0].severity.value == "warning"


def test_an_empty_draft_is_incomplete_with_null_figures_never_zero(operation: PinnedAuthorityOperation) -> None:
    answer = _preview(
        InvoiceFiguresPreviewRequest(
            profile_id=PROFILE,
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
    answer = _preview(
        InvoiceFiguresPreviewRequest(
            profile_id=PROFILE,
            issued_at=APRIL,
            base_total=public_decimal("100.50"),
            retention_rate=public_decimal("0.155"),
            retention_amount=public_decimal("15.59"),
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
    answer = _preview(preview_draft(), operation=operation)
    slots = {slot.slot: slot for slot in answer.rate_slots}

    assert slots["RATE_21"].fraction == PublicDecimal(decimal="0.21")
    assert slots["RATE_21"].in_force
    assert not slots["RATE_5"].in_force
    assert slots["RATE_5"].fraction is None
    assert slots["EXEMPT"].in_force
    assert slots["EXEMPT"].fraction is None
    assert slots["RATE_7.5"].label_key == "application.invoices.figures_preview.rate_slot.rate_7_5"


def test_a_date_before_the_registry_floor_reads_the_nearest_rates_marked_as_a_projection(
    operation: PinnedAuthorityOperation,
) -> None:
    floor = operation.supported_filing_years().date_envelope().floor
    before = floor - timedelta(days=1)

    answer = _preview(preview_draft(issued_at=before), operation=operation)

    assert answer.verdict == "would_accept"
    assert answer.refusal_code is None
    projected = [item for item in answer.findings if item.code is FigureFindingCode.RATE_DATE_PROJECTED]
    assert len(projected) == 1
    assert projected[0].severity == "warning"
    assert {item.key: item.value for item in projected[0].values} == {
        "on_date": before.isoformat(),
        "nearest": floor.isoformat(),
    }
    assert {slot.slot: slot for slot in answer.rate_slots}["RATE_21"].fraction == PublicDecimal(decimal="0.21")
    assert answer.lines[0].iva_amount.computed == PublicDecimal(decimal="21.00")


def test_a_date_inside_the_registry_support_carries_no_projection_finding(
    operation: PinnedAuthorityOperation,
) -> None:
    floor = operation.supported_filing_years().date_envelope().floor
    answer = _preview(preview_draft(issued_at=floor), operation=operation)
    assert FigureFindingCode.RATE_DATE_PROJECTED not in [item.code for item in answer.findings]


@pytest.mark.parametrize(
    ("on_date", "fraction", "cuota"),
    (
        # AEAT 2020 IVA manual, art. 90: 18 % until 31 August 2012.
        (date(2012, 8, 31), "0.18", "18.00"),
        # RDL 20/2012 art. 23.Dos: 21 % from the next day.
        (date(2012, 9, 1), "0.21", "21.00"),
        (date(2020, 12, 31), "0.21", "21.00"),
    ),
)
def test_a_date_before_the_filing_years_reads_its_published_rate_and_warns(
    operation: PinnedAuthorityOperation,
    on_date: date,
    fraction: str,
    cuota: str,
) -> None:
    answer = _preview(preview_draft(preview_line(iva_amount=cuota), issued_at=on_date), operation=operation)

    assert {slot.slot: slot for slot in answer.rate_slots}["RATE_21"].fraction == PublicDecimal(decimal=fraction)
    assert answer.lines[0].iva_amount.computed == PublicDecimal(decimal=cuota)
    assert FigureFindingCode.RATE_DATE_PROJECTED in [item.code for item in answer.findings]


def test_the_earliest_projected_date_answers_the_grounded_rate(operation: PinnedAuthorityOperation) -> None:
    answer = _preview(preview_draft(issued_at=date(2021, 1, 1)), operation=operation)

    assert {slot.slot: slot for slot in answer.rate_slots}["RATE_21"].fraction == PublicDecimal(decimal="0.21")
    assert FigureFindingCode.RATE_DATE_PROJECTED in [item.code for item in answer.findings]


def test_a_registry_failure_inside_its_support_stays_a_failure(
    operation: PinnedAuthorityOperation,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def corrupt(_on_date: date) -> tuple[()]:
        raise RegistryValidationError("corrupt authority")

    monkeypatch.setattr(preview_operation, "dated_rate_slots", corrupt)

    with pytest.raises(RegistryValidationError):
        _preview(preview_draft(), operation=operation)


def test_a_registry_failure_during_acceptance_inside_its_support_stays_a_failure(
    operation: PinnedAuthorityOperation,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def corrupt(**_kwargs: object) -> None:
        raise RegistryValidationError("corrupt authority")

    monkeypatch.setattr(preview_operation, "build_invoice_from_add_request", corrupt)

    with pytest.raises(RegistryValidationError):
        _preview(preview_draft(), operation=operation)


def test_a_magnitude_beyond_decimal_arithmetic_is_a_typed_refusal(operation: PinnedAuthorityOperation) -> None:
    answer = _preview(preview_draft(preview_line(quantity="1E+30")), operation=operation)

    assert answer.verdict == "would_refuse"
    assert answer.refusal_code is FigureFindingCode.FIGURE_OUT_OF_RANGE


def test_a_foreign_draft_asks_the_rate_source_add_asks_and_keeps_its_id(operation: PinnedAuthorityOperation) -> None:
    found = _Answering(EurRateLookupStatus.FOUND)
    stamped = _preview(preview_draft(currency="USD"), operation=operation, rate_provider=found)
    unstamped = _preview(preview_draft(currency="USD"), operation=operation)

    assert found.asked == [("USD", APRIL)]
    assert stamped.verdict == unstamped.verdict == "would_accept"
    assert stamped.invoice_id is not None
    assert stamped.invoice_id == unstamped.invoice_id


def test_a_euro_draft_asks_no_rate_source(operation: PinnedAuthorityOperation) -> None:
    answer = _preview(preview_draft(), operation=operation, rate_provider=Unreachable())

    assert answer.verdict == "would_accept"


def test_an_unreachable_rate_source_is_neither_an_acceptance_nor_a_refusal_and_add_fails_alike(
    operation: PinnedAuthorityOperation,
) -> None:
    """Add cannot construct the invoice without its rate source, so the preview cannot say it would."""
    draft = preview_draft(currency="USD")
    answer = _preview(draft, operation=operation)
    assert answer.verdict == "would_accept"

    with pytest.raises(CatalogueInvoiceRateError):
        _accepted_by_the_builder(draft, answer, operation, Unreachable())
    with pytest.raises(CatalogueInvoiceRateError):
        _preview(draft, operation=operation, rate_provider=Unreachable())


def test_the_digest_binds_the_answer_to_the_draft(operation: PinnedAuthorityOperation) -> None:
    first = _preview(preview_draft(), operation=operation)
    again = _preview(preview_draft(), operation=operation)
    other = _preview(preview_draft(preview_line(unit_price="100.01")), operation=operation)

    assert first.input_digest == again.input_digest
    assert first.input_digest != other.input_digest


@pytest.mark.parametrize(
    "values",
    (
        {"lines": (preview_line(),), "base_total": public_decimal("1")},
        {"lines": (preview_line("same"), preview_line("same"))},
        {"stored": {"invoice_id": "f" * 64, "grand_total": {"decimal": "1"}}},
    ),
    ids=("lines-and-base", "duplicate-keys", "stored-without-its-base"),
)
def test_the_request_refuses_an_incoherent_shape(values: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        InvoiceFiguresPreviewRequest.model_validate({"profile_id": PROFILE, **values})


def test_the_request_round_trips_through_json() -> None:
    draft = preview_draft(printed_total=public_decimal("121.00"))

    assert InvoiceFiguresPreviewRequest.model_validate_json(draft.model_dump_json()) == draft


@pytest.mark.parametrize(
    ("field", "overrides"),
    (
        ("counterparty_country", {"counterparty_country": "FR"}),
        ("iva_category", {"iva_category": "no_such_category"}),
        ("operation_date", {"operation_date": date(2026, 4, 1)}),
        ("series", {"invoice_class": "RECTIFICATIVA", "series": "R"}),
        ("invoice_class", {"invoice_class": "RECTIFICATIVA"}),
        ("rectifies_invoice_number", {"rectifies_invoice_number": "F-1"}),
        ("retention_rate", {"retention_rate": public_decimal("0.07")}),
        ("retention_amount", {"retention_rate": public_decimal("0.07"), "retention_amount": public_decimal("70.02")}),
    ),
)
def test_a_judged_correction_field_moves_the_verdict_the_update_waits_on(
    field: str, overrides: dict[str, object], operation: PinnedAuthorityOperation
) -> None:
    assert field in INVOICE_CORRECTION_JUDGED_FIELDS
    plain = _preview(_correction(), operation=operation)
    changed = _preview(_correction(**overrides), operation=operation)

    assert (changed.verdict, changed.rule_findings, changed.findings) != (
        plain.verdict,
        plain.rule_findings,
        plain.findings,
    )


@pytest.mark.parametrize(
    ("field", "overrides"),
    (("notes", {"notes": "x"}), ("counterparty_name", {"counterparty_name": "Otra S.L."})),
)
def test_a_correction_field_outside_the_judged_set_leaves_the_verdict_alone(
    field: str, overrides: dict[str, object], operation: PinnedAuthorityOperation
) -> None:
    assert field not in INVOICE_CORRECTION_JUDGED_FIELDS
    assert field in CatalogueInvoicePatch.model_fields
    plain = _preview(_correction(), operation=operation)
    changed = _preview(_correction(**overrides), operation=operation)

    assert (changed.verdict, changed.rule_findings, changed.findings) == (
        plain.verdict,
        plain.rule_findings,
        plain.findings,
    )


def test_every_judged_field_is_one_a_correction_may_name_and_the_preview_is_told() -> None:
    assert CatalogueInvoicePatch.model_fields.keys() >= INVOICE_CORRECTION_JUDGED_FIELDS
    assert InvoiceFiguresPreviewRequest.model_fields.keys() >= INVOICE_CORRECTION_JUDGED_FIELDS
