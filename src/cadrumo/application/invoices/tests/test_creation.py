"""Tests for the rich catalogue-invoice creation application service.

:func:`create_catalogue_invoice` mints a linkable
:class:`~cadrumo.domain.invoices.Invoice` (the only aggregate carrying
``linked_transaction_ids``) so the documented ``invoice add`` ->
``link --invoice-id`` flow has an operator entry point. These tests exercise the
service against the real encrypted :class:`InvoiceCatalogueRepository` (real
master-key provider, real engine) — no mocks.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.loader import load_modelo_path

from ....adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ....core import IntracomOperationType, Period
from ....core.aggregation import InvoiceDevengoRank
from ....core.resources import bundled_path
from ....domain.invoices import (
    InvoiceClass,
    InvoiceLine,
    InvoiceOperationDateRole,
    InvoiceValidationError,
    IvaRate,
    PaymentStatus,
    decompose_invoice,
)
from ....domain.iva import InvoiceKind, IvaCategory
from ....domain.modelos import Modelo349OperadorRow
from ....tests.secure_sql import isolated_runtime_profile
from ...aggregation import (
    CalculationSourceContext,
    invoice_devengo_in_period,
    proxy_attributed_invoice_ids,
    resolve_invoice_devengo,
)
from .. import (
    InvoiceCatalogueSourceResolver,
    build_catalogue_invoice,
    create_catalogue_invoice,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]


class _CanonicalOnlyRateProvider:
    """Real :class:`ExchangeRateProvider` implementation returning a rate ONLY
    for the exact canonical uppercase token - proves the caller normalises
    before querying, rather than mocking the lookup itself."""

    @property
    def rate_source_id(self) -> str:
        return "test_canonical_only"

    def get_eur_rate(self, currency: str, rate_date: date) -> Decimal | None:
        del rate_date
        return Decimal("1.2") if currency == "GBP" else None


_BUCKET_ID = "19191919-1919-4191-8191-191919191919"


def _modelo_349_revision():
    return load_modelo_path(bundled_path("registry", "aeat", "modelos", "349")).revisions["2020-y-siguientes"]


def test_build_catalogue_invoice_derives_grounded_totals() -> None:
    """A single-line invoice synthesised from base + rate carries grounded totals.

    The cuota is resolved against the registry IVA rate, not a hand-typed
    percentage; the Invoice arithmetic invariants then enforce that the totals
    equal the line sums. The derived ``invoice_id`` is the hex-64 hash that
    ``link --invoice-id`` resolves.
    """
    invoice = build_catalogue_invoice(
        bucket_id=_BUCKET_ID,
        kind=InvoiceKind.RECEIVED,
        counterparty_name="Papeleria Sol SL",
        counterparty_tax_id="A58818501",
        counterparty_country="ES",
        invoice_number="2026-0142",
        issued_at=date(2026, 3, 10),
        taxable_base=Decimal("100.00"),
        iva_rate=Decimal("21"),
        currency="EUR",
    )
    assert len(invoice.invoice_id) == 64
    assert invoice.base_total == Decimal("100.00")
    # IVA total is grounded against the registry rate for the general slot;
    # assert the structural identity (total == base + iva, iva == line sum)
    # rather than re-deriving the registry percentage.
    assert invoice.grand_total == invoice.base_total + invoice.iva_total
    assert invoice.iva_total == sum((line.iva_amount for line in invoice.lines), start=Decimal("0"))
    assert invoice.iva_total > Decimal("0")
    assert invoice.linked_transaction_ids == ()


def test_build_catalogue_invoice_exempt_carries_zero_cuota() -> None:
    """An invoice with no IVA rate is EXEMPT and carries a zero cuota."""
    invoice = build_catalogue_invoice(
        bucket_id=_BUCKET_ID,
        kind=InvoiceKind.ISSUED,
        counterparty_name="Cliente SA",
        counterparty_tax_id="A58818501",
        counterparty_country="ES",
        invoice_number="2026-0500",
        issued_at=date(2026, 4, 1),
        taxable_base=Decimal("200.00"),
        iva_rate=None,
        currency="EUR",
    )
    assert invoice.iva_total == Decimal("0")
    assert invoice.grand_total == invoice.base_total


def test_build_catalogue_invoice_refuses_unsupported_rate() -> None:
    """A percentage outside the closed IVA slot taxonomy is refused, with the
    accepted set named — never a bare value-invalid."""
    with pytest.raises(InvoiceValidationError) as exc:
        build_catalogue_invoice(
            bucket_id=_BUCKET_ID,
            kind=InvoiceKind.RECEIVED,
            counterparty_name="Papeleria Sol SL",
            counterparty_tax_id="A58818501",
            counterparty_country="ES",
            invoice_number="2026-0142",
            issued_at=date(2026, 3, 10),
            taxable_base=Decimal("100.00"),
            iva_rate=Decimal("13"),
            currency="EUR",
        )
    # The accepted-rate set is carried structurally on the error context (the
    # CLI boundary renders it through the locale), so assert the context names
    # the closed slot taxonomy rather than the bare message.
    assert exc.value.context is not None
    accepted = exc.value.context["accepted"]
    assert isinstance(accepted, str)
    assert "21" in accepted, exc.value.context


def test_create_catalogue_invoice_persists_and_refuses_duplicate(tmp_path: Path) -> None:
    """The service persists the rich invoice and refuses a duplicate identity.

    A round-trip through the real encrypted repository confirms the invoice is
    reloadable by its derived id; a second create of the same logical identity
    is refused so an accidental re-create cannot clobber a linked record.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        result = create_catalogue_invoice(
            invoice=build_catalogue_invoice(
                bucket_id=_BUCKET_ID,
                kind=InvoiceKind.RECEIVED,
                counterparty_name="Papeleria Sol SL",
                counterparty_tax_id="A58818501",
                counterparty_country="ES",
                invoice_number="2026-0142",
                issued_at=date(2026, 3, 10),
                taxable_base=Decimal("100.00"),
                iva_rate=Decimal("21"),
                currency="EUR",
                payment_status=PaymentStatus.PENDING,
            ),
        )
        reloaded = InvoiceCatalogueRepository(bucket_id=_BUCKET_ID).load().get(result.invoice.invoice_id)
        assert reloaded == result.invoice

        with pytest.raises(InvoiceValidationError):
            create_catalogue_invoice(
                invoice=build_catalogue_invoice(
                    bucket_id=_BUCKET_ID,
                    kind=InvoiceKind.RECEIVED,
                    counterparty_name="Papeleria Sol SL",
                    counterparty_tax_id="A58818501",
                    counterparty_country="ES",
                    invoice_number="2026-0142",
                    issued_at=date(2026, 3, 10),
                    taxable_base=Decimal("100.00"),
                    iva_rate=Decimal("21"),
                    currency="EUR",
                ),
            )


def test_build_catalogue_invoice_carries_intra_community_category() -> None:
    """The optional ``iva_category`` stamps the calculation-feeding classification.

    The M349 recapitulative resolver reads ``iva_category`` to derive a
    transaction's clave; without it the catalogue invoice defaults to a
    domestic operation (``None``) that never reaches M349.
    """
    intra = build_catalogue_invoice(
        bucket_id=_BUCKET_ID,
        kind=InvoiceKind.ISSUED,
        counterparty_name="Kunde GmbH",
        counterparty_tax_id="DE345678901",
        counterparty_country="DE",
        invoice_number="EU-001",
        issued_at=date(2026, 2, 10),
        taxable_base=Decimal("2000.00"),
        iva_rate=Decimal("0"),
        currency="EUR",
        iva_category=IvaCategory.INTRA_COMMUNITY_SUPPLY,
        # An entrega intracomunitaria must now state its clave: the category
        # alone cannot separate an ordinary E from a post-importation M or H.
        operation_type=IntracomOperationType.E,
    )
    assert intra.iva_category is IvaCategory.INTRA_COMMUNITY_SUPPLY

    domestic = build_catalogue_invoice(
        bucket_id=_BUCKET_ID,
        kind=InvoiceKind.ISSUED,
        counterparty_name="Cliente SL",
        counterparty_tax_id="A58818501",
        counterparty_country="ES",
        invoice_number="FAC-001",
        issued_at=date(2026, 2, 10),
        taxable_base=Decimal("2000.00"),
        iva_rate=Decimal("21"),
        currency="EUR",
    )
    assert domestic.iva_category is None


def test_create_catalogue_invoice_intra_community_feeds_modelo_349(tmp_path: Path) -> None:
    """End-to-end: a stamped intra-community invoice reaches the M349 aggregate.

    This is the anti-tautology proof that ``iva_category`` is not merely stored
    but is read by the live :class:`InvoiceCatalogueSourceResolver`: an issued
    intra-community supply of 2000 must surface as one operator declaring
    2000 of operations for the period it was issued in.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        repository = InvoiceCatalogueRepository(bucket_id=_BUCKET_ID)
        create_catalogue_invoice(
            invoice=build_catalogue_invoice(
                bucket_id=_BUCKET_ID,
                kind=InvoiceKind.ISSUED,
                counterparty_name="Kunde GmbH",
                counterparty_tax_id="DE345678901",
                counterparty_country="DE",
                invoice_number="EU-2026-001",
                issued_at=date(2026, 2, 10),
                taxable_base=Decimal("2000.00"),
                iva_rate=Decimal("0"),
                currency="EUR",
                iva_category=IvaCategory.INTRA_COMMUNITY_SUPPLY,
                operation_type=IntracomOperationType.E,
            ),
            repository=repository,
        )
        resolution = InvoiceCatalogueSourceResolver(invoice_repository=repository).resolve(
            CalculationSourceContext(
                bucket_id=_BUCKET_ID,
                modelo="349",
                filing_year=2026,
                period=Period.from_year_and_code(2026, "1T"),
                revision=_modelo_349_revision(),
            ),
        )

    assert resolution.binding_values["iva-349-declarante-numero-operadores"] == Decimal("1")
    assert resolution.binding_values["iva-349-declarante-importe-operaciones"] == Decimal("2000.00")


def test_create_catalogue_invoice_service_keys_feed_modelo_349(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        repository = InvoiceCatalogueRepository(bucket_id=_BUCKET_ID)
        issued = create_catalogue_invoice(
            invoice=build_catalogue_invoice(
                bucket_id=_BUCKET_ID,
                kind=InvoiceKind.ISSUED,
                counterparty_name="Service SARL",
                counterparty_tax_id="FR12345678901",
                counterparty_country="FR",
                invoice_number="SERV-OUT-2026-001",
                issued_at=date(2026, 2, 10),
                taxable_base=Decimal("4000.00"),
                iva_rate=Decimal("0"),
                currency="EUR",
                operation_type=IntracomOperationType.S,
            ),
            repository=repository,
        ).invoice
        received = create_catalogue_invoice(
            invoice=build_catalogue_invoice(
                bucket_id=_BUCKET_ID,
                kind=InvoiceKind.RECEIVED,
                counterparty_name="Servizi SRL",
                counterparty_tax_id="IT12345678901",
                counterparty_country="IT",
                invoice_number="SERV-IN-2026-001",
                issued_at=date(2026, 3, 5),
                taxable_base=Decimal("3000.00"),
                iva_rate=Decimal("0"),
                currency="EUR",
                operation_type=IntracomOperationType.ADQUISICION_SERVICIOS,
            ),
            repository=repository,
        ).invoice
        resolution = InvoiceCatalogueSourceResolver(invoice_repository=repository).resolve(
            CalculationSourceContext(
                bucket_id=_BUCKET_ID,
                modelo="349",
                filing_year=2026,
                period=Period.from_year_and_code(2026, "1T"),
                revision=_modelo_349_revision(),
            ),
        )

    assert issued.operation_type is IntracomOperationType.S
    assert received.operation_type is IntracomOperationType.ADQUISICION_SERVICIOS
    assert resolution.binding_values["iva-349-declarante-numero-operadores"] == Decimal("2")
    assert resolution.binding_values["iva-349-declarante-importe-operaciones"] == Decimal("7000.00")
    assert resolution.binding_values["iva-349-declarante-numero-operadores-adquisicion"] == Decimal("1")
    assert resolution.binding_values["iva-349-declarante-importe-operaciones-adquisicion"] == Decimal("3000.00")
    rows: dict[tuple[str, str], Modelo349OperadorRow] = {
        (row.codigo_pais, row.clave_operacion): row
        for row in resolution.detail_rows
        if isinstance(row, Modelo349OperadorRow)
    }
    assert rows[("FR", "S")].nif_comunitario == "FR12345678901"
    assert rows[("FR", "S")].importe == Decimal("4000.00")
    assert rows[("IT", "I")].nif_comunitario == "IT12345678901"
    assert rows[("IT", "I")].importe == Decimal("3000.00")


@pytest.mark.parametrize("raw_currency", ["GBP", "gbp", " gbp "])
def test_build_catalogue_invoice_normalises_currency_before_fx_lookup(raw_currency: str) -> None:
    """A padded/lowercase foreign currency must resolve the SAME FX rate as its
    canonical form: the provider is queried with the normalised token, not the
    raw operator input."""
    invoice = build_catalogue_invoice(
        bucket_id=_BUCKET_ID,
        kind=InvoiceKind.RECEIVED,
        counterparty_name="Acme Ltd",
        counterparty_tax_id="GB123456789",
        counterparty_country="GB",
        invoice_number="GB-2026-001",
        issued_at=date(2026, 3, 10),
        taxable_base=Decimal("100.00"),
        iva_rate=None,
        currency=raw_currency,
        rate_provider=_CanonicalOnlyRateProvider(),
    )
    assert invoice.currency == "GBP"
    assert invoice.fx_rate == Decimal("1.2")
    assert invoice.fx_rate_date == date(2026, 3, 10)


def test_build_catalogue_invoice_rounds_half_cent_cuota_away_from_zero() -> None:
    """A cuota whose residual is exactly half a cent rounds up, not to even.

    AEAT publishes euro amounts under half-up rounding, so a residual of
    exactly 0.5 cents rounds away from zero. A taxable base of 10.50 at the
    registry-resolved 21 % tier yields exactly 2.2050, which is the boundary
    that separates the two modes: half-up gives 2.21, while Python's default
    banker's rounding (``ROUND_HALF_EVEN``) keeps the even cent and gives
    2.20 — a filed cuota one cent short of the AEAT figure.
    """
    invoice = build_catalogue_invoice(
        bucket_id=_BUCKET_ID,
        kind=InvoiceKind.ISSUED,
        counterparty_name="Ferreteria Norte SL",
        counterparty_tax_id="A58818501",
        counterparty_country="ES",
        invoice_number="2026-0501",
        issued_at=date(2026, 4, 2),
        taxable_base=Decimal("10.50"),
        iva_rate=Decimal("21"),
        currency="EUR",
    )

    assert invoice.iva_total == Decimal("2.21")
    assert invoice.iva_total != Decimal("2.20")
    assert invoice.lines[0].iva_amount == Decimal("2.21")
    assert invoice.base_total == Decimal("10.50")
    assert invoice.grand_total == Decimal("12.71")


def test_an_operator_supplied_operation_date_survives_to_a_declared_devengo_rank(tmp_path: Path) -> None:
    """The operator has a route to a declared devengo date, and it reaches the rank.

    Period attribution reads the LIVA art. 75 devengo date and discloses when
    it had to substitute the issue date. That disclosure asks the operator to
    record a fecha de operacion, so the route from the creation service to a
    declared rank has to exist end to end -- an advisory whose remedy no
    surface can carry out is permanent noise, not a safeguard.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        recorded = create_catalogue_invoice(
            invoice=build_catalogue_invoice(
                bucket_id=_BUCKET_ID,
                kind=InvoiceKind.ISSUED,
                counterparty_name="Cliente Norte SL",
                counterparty_tax_id="A58818501",
                counterparty_country="ES",
                invoice_number="2026-Q1-OP",
                issued_at=date(2026, 4, 10),
                taxable_base=Decimal("1000.00"),
                iva_rate=Decimal("21"),
                currency="EUR",
                operation_date=date(2026, 3, 28),
            ),
        )
        reloaded = InvoiceCatalogueRepository(bucket_id=_BUCKET_ID).load().get(recorded.invoice.invoice_id)
        assert reloaded is not None
        assert reloaded.operation_date == date(2026, 3, 28)
        assert reloaded.operation_date_role is InvoiceOperationDateRole.OPERATION_PERFORMED

        devengo = resolve_invoice_devengo(reloaded)
        assert devengo.devengo_date == date(2026, 3, 28)
        assert devengo.rank is InvoiceDevengoRank.OPERATION_DATE_DECLARED
        assert invoice_devengo_in_period(reloaded, period=Period.from_year_and_code(2026, "1T")) is True
        assert proxy_attributed_invoice_ids((reloaded,)) == ()


def test_omitting_the_operation_date_leaves_the_record_on_the_issue_date_proxy(tmp_path: Path) -> None:
    """The other direction: the field stays optional and the rank says so.

    Recording a fecha de operacion must not become a precondition for creating
    an invoice -- refusing the ordinary case would be a far worse defect than
    the substitution it prevents.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        recorded = create_catalogue_invoice(
            invoice=build_catalogue_invoice(
                bucket_id=_BUCKET_ID,
                kind=InvoiceKind.ISSUED,
                counterparty_name="Cliente Norte SL",
                counterparty_tax_id="A58818501",
                counterparty_country="ES",
                invoice_number="2026-Q2-NO-OP",
                issued_at=date(2026, 4, 10),
                taxable_base=Decimal("1000.00"),
                iva_rate=Decimal("21"),
                currency="EUR",
            ),
        )
        reloaded = InvoiceCatalogueRepository(bucket_id=_BUCKET_ID).load().get(recorded.invoice.invoice_id)
        assert reloaded is not None
        assert reloaded.operation_date is None
        assert resolve_invoice_devengo(reloaded).rank is InvoiceDevengoRank.ISSUE_DATE_PROXY
        assert proxy_attributed_invoice_ids((reloaded,)) == (reloaded.invoice_id,)


def test_m349_excludes_a_self_contradicting_record_but_names_it(tmp_path: Path) -> None:
    """An art. 25 exemption recorded alongside a repercuted cuota grounds neither.

    The record asserts two things that cannot both be true: an entrega
    intracomunitaria exenta and IVA charged on it. Modelo 349 declares the base
    imponible of the exempt operation, so neither assertion can be trusted to
    produce it, and the contract cannot tell which one the operator got wrong.

    Excluded but NOT silent. A missing intracomunitaria is an under-declaration
    however it went missing, so the exclusion has to arrive with the record
    named.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        repository = InvoiceCatalogueRepository(bucket_id=_BUCKET_ID)
        contradictory = create_catalogue_invoice(
            invoice=build_catalogue_invoice(
                bucket_id=_BUCKET_ID,
                kind=InvoiceKind.ISSUED,
                counterparty_name="Waren GmbH",
                counterparty_tax_id="DE123456789",
                counterparty_country="DE",
                invoice_number="GOODS-OUT-2026-001",
                issued_at=date(2026, 2, 10),
                taxable_base=Decimal("5000.00"),
                iva_rate=Decimal("21"),
                currency="EUR",
                # The CLI derives the category from the operation type before
                # calling this service; the service itself does not, so the test
                # supplies the pair the operator's path would have produced.
                iva_category=IvaCategory.INTRA_COMMUNITY_SUPPLY,
                operation_type=IntracomOperationType.E,
            ),
            repository=repository,
        ).invoice
        resolution = InvoiceCatalogueSourceResolver(invoice_repository=repository).resolve(
            CalculationSourceContext(
                bucket_id=_BUCKET_ID,
                modelo="349",
                filing_year=2026,
                period=Period.from_year_and_code(2026, "1T"),
                revision=_modelo_349_revision(),
            ),
        )

    assert contradictory.iva_category is IvaCategory.INTRA_COMMUNITY_SUPPLY
    assert contradictory.iva_total == Decimal("1050.00")
    assert resolution.binding_values["iva-349-declarante-numero-operadores"] == Decimal("0")
    assert resolution.detail_rows == ()
    messages = [diagnostic.message for diagnostic in resolution.diagnostics]
    assert len(messages) == 1
    assert "GOODS-OUT-2026-001" in messages[0]
    assert "cuota_contradicts_category" in messages[0]


def test_m349_declares_a_coherent_exempt_supply_with_no_diagnostic(tmp_path: Path) -> None:
    """The other direction: the same operation, recorded consistently, declares.

    Identical to the contradiction case except the cuota is zero, as LIVA
    art. 25 requires. A check that fired on both would have destroyed the
    recapitulativa rather than protected it.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        repository = InvoiceCatalogueRepository(bucket_id=_BUCKET_ID)
        create_catalogue_invoice(
            invoice=build_catalogue_invoice(
                bucket_id=_BUCKET_ID,
                kind=InvoiceKind.ISSUED,
                counterparty_name="Waren GmbH",
                counterparty_tax_id="DE123456789",
                counterparty_country="DE",
                invoice_number="GOODS-OUT-2026-002",
                issued_at=date(2026, 2, 10),
                taxable_base=Decimal("5000.00"),
                iva_rate=Decimal("0"),
                currency="EUR",
                iva_category=IvaCategory.INTRA_COMMUNITY_SUPPLY,
                operation_type=IntracomOperationType.E,
            ),
            repository=repository,
        )
        resolution = InvoiceCatalogueSourceResolver(invoice_repository=repository).resolve(
            CalculationSourceContext(
                bucket_id=_BUCKET_ID,
                modelo="349",
                filing_year=2026,
                period=Period.from_year_and_code(2026, "1T"),
                revision=_modelo_349_revision(),
            ),
        )

    assert resolution.binding_values["iva-349-declarante-numero-operadores"] == Decimal("1")
    assert resolution.binding_values["iva-349-declarante-importe-operaciones"] == Decimal("5000.00")
    assert resolution.diagnostics == ()


def test_intracommunity_services_now_carry_a_category_and_reach_m349(tmp_path: Path) -> None:
    """An intracomunitaria de servicios is grounded, and files under S and I.

    Before the service categories existed, operation types S and I mapped to no
    IvaCategory at all, so an ordinary cross-border service was ungrounded to
    every consumer that reads the IVA treatment -- including the decomposition
    contract, which had to be narrowed to contradictions only because absence
    could not be distinguished from an unrepresentable operation.

    The two categories are deliberately not the goods ones. A service is NO
    SUJETA in Spain by the art. 69.Uno.1.º localisation rule, where an entrega
    de bienes is EXEMPT under art. 25, and Modelo 349 reports them under
    distinct claves -- so declaring a service as E would file it as goods.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        repository = InvoiceCatalogueRepository(bucket_id=_BUCKET_ID)
        issued = create_catalogue_invoice(
            invoice=build_catalogue_invoice(
                bucket_id=_BUCKET_ID,
                kind=InvoiceKind.ISSUED,
                counterparty_name="Service SARL",
                counterparty_tax_id="FR12345678901",
                counterparty_country="FR",
                invoice_number="SERV-OUT-2026-100",
                issued_at=date(2026, 2, 10),
                taxable_base=Decimal("4000.00"),
                iva_rate=Decimal("0"),
                currency="EUR",
                iva_category=IvaCategory.INTRA_COMMUNITY_SERVICE_SUPPLY,
                operation_type=IntracomOperationType.S,
            ),
            repository=repository,
        ).invoice
        received = create_catalogue_invoice(
            invoice=build_catalogue_invoice(
                bucket_id=_BUCKET_ID,
                kind=InvoiceKind.RECEIVED,
                counterparty_name="Servizi SRL",
                counterparty_tax_id="IT12345678901",
                counterparty_country="IT",
                invoice_number="SERV-IN-2026-100",
                issued_at=date(2026, 3, 5),
                taxable_base=Decimal("3000.00"),
                iva_rate=Decimal("0"),
                currency="EUR",
                iva_category=IvaCategory.INTRA_COMMUNITY_SERVICE_ACQUISITION_REVERSE_CHARGE,
                operation_type=IntracomOperationType.ADQUISICION_SERVICIOS,
            ),
            repository=repository,
        ).invoice
        resolution = InvoiceCatalogueSourceResolver(invoice_repository=repository).resolve(
            CalculationSourceContext(
                bucket_id=_BUCKET_ID,
                modelo="349",
                filing_year=2026,
                period=Period.from_year_and_code(2026, "1T"),
                revision=_modelo_349_revision(),
            ),
        )

    # Grounded now: the decomposition contract can answer for these records,
    # which is what the category being absent previously made impossible.
    for invoice in (issued, received):
        assert decompose_invoice(invoice).defects == ()

    assert resolution.binding_values["iva-349-declarante-numero-operadores"] == Decimal("2")
    assert resolution.binding_values["iva-349-declarante-importe-operaciones"] == Decimal("7000.00")
    rows = {
        (row.codigo_pais, row.clave_operacion): row
        for row in resolution.detail_rows
        if isinstance(row, Modelo349OperadorRow)
    }
    assert rows[("FR", "S")].importe == Decimal("4000.00")
    assert rows[("IT", "I")].importe == Decimal("3000.00")
    # Filed under the service claves, NOT under the goods claves E and A.
    assert ("FR", "E") not in rows
    assert ("IT", "A") not in rows
    assert resolution.diagnostics == ()


def _mixed_rate_lines() -> tuple[InvoiceLine, ...]:
    """A 21% line and a 10% line, the ordinary mixed-rate invoice."""
    return (
        InvoiceLine(
            description="Consultoria",
            quantity=Decimal("1"),
            unit_price=Decimal("1000.00"),
            subtotal=Decimal("1000.00"),
            iva_rate=IvaRate.RATE_21,
            iva_amount=Decimal("210.00"),
        ),
        InvoiceLine(
            description="Transporte de viajeros",
            quantity=Decimal("1"),
            unit_price=Decimal("500.00"),
            subtotal=Decimal("500.00"),
            iva_rate=IvaRate.RATE_10,
            iva_amount=Decimal("50.00"),
        ),
    )


def test_a_supplied_line_set_persists_per_rate_instead_of_collapsing_to_one_line(
    tmp_path: Path,
) -> None:
    """A mixed-rate invoice keeps its per-rate breakdown through persistence.

    Every canonically-written invoice previously carried exactly one
    synthesised line at one rate, because the builder derived the line from a
    single taxable base and a single rate. A real invoice mixing 21% and 10% is
    ordinary, and collapsing it reports the correct GRAND TOTAL while
    attributing the whole cuota to one rate -- which is precisely the axis the
    IVA modelos declare, so the error is invisible in the total and wrong in
    the return.

    Persisted through the real encrypted repository rather than asserted on the
    in-memory model, because the claim is that the breakdown SURVIVES, not
    merely that the builder assembled it.
    """
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        result = create_catalogue_invoice(
            invoice=build_catalogue_invoice(
                bucket_id=profile.bucket_id,
                kind=InvoiceKind.ISSUED,
                counterparty_name="Cliente Mixto SL",
                counterparty_tax_id="B12345674",
                counterparty_country="ES",
                invoice_number="F-2026-MIXED-001",
                issued_at=date(2026, 4, 1),
                taxable_base=Decimal("1500.00"),
                iva_rate=None,
                currency="EUR",
                lines=_mixed_rate_lines(),
            ),
            repository=InvoiceCatalogueRepository(objects=profile.repository),
        )
        restored = InvoiceCatalogueRepository(objects=profile.repository).load().get(result.invoice.invoice_id)

    assert restored is not None
    assert len(restored.lines) == 2
    assert [line.iva_rate for line in restored.lines] == [IvaRate.RATE_21, IvaRate.RATE_10]
    # Per-rate cuota, not one blended figure: 210 belongs to the 21% base and
    # 50 to the 10% base, and a collapse would put all 260 on a single rate.
    assert [line.iva_amount for line in restored.lines] == [Decimal("210.00"), Decimal("50.00")]
    assert restored.base_total == Decimal("1500.00")
    assert restored.iva_total == Decimal("260.00")
    assert restored.grand_total == Decimal("1760.00")


def test_a_supplied_line_set_refuses_a_taxable_base_that_disagrees_with_it() -> None:
    """Two disagreeing sources of truth for the base must refuse, not resolve.

    With a line set supplied the caller states the base twice: once as the
    summed subtotals and once as ``taxable_base``. Silently preferring either
    would let a caller believe the other was recorded, and on this field that
    means declaring a base the operator never entered.
    """
    with pytest.raises(InvoiceValidationError, match="summed line subtotals"):
        build_catalogue_invoice(
            bucket_id=None,
            kind=InvoiceKind.ISSUED,
            counterparty_name="Cliente Mixto SL",
            counterparty_tax_id="B12345674",
            counterparty_country="ES",
            invoice_number="F-2026-MIXED-002",
            issued_at=date(2026, 4, 1),
            taxable_base=Decimal("1400.00"),
            iva_rate=None,
            currency="EUR",
            lines=_mixed_rate_lines(),
        )


def test_omitting_the_line_set_still_synthesises_the_single_line() -> None:
    """Positive control: the additive change leaves the single-rate path intact.

    The overwhelming majority of invoices carry one rate, and every existing
    caller omits the line set. If this regressed, the mixed-rate proof above
    would still pass while the common path broke.
    """
    invoice = build_catalogue_invoice(
        bucket_id=None,
        kind=InvoiceKind.ISSUED,
        counterparty_name="Cliente Simple SL",
        counterparty_tax_id="B12345674",
        counterparty_country="ES",
        invoice_number="F-2026-SIMPLE-001",
        issued_at=date(2026, 4, 1),
        taxable_base=Decimal("1000.00"),
        iva_rate=Decimal("21"),
        currency="EUR",
    )

    assert len(invoice.lines) == 1
    assert invoice.lines[0].iva_rate is IvaRate.RATE_21
    assert invoice.iva_total == Decimal("210.00")
    assert invoice.grand_total == Decimal("1210.00")


def test_a_rectificativa_with_series_and_recargo_is_writable_and_persists(tmp_path: Path) -> None:
    """The four axes the aggregate modelled and no write path could set.

    Before these parameters existed every canonically-written invoice was
    ORDINARIA with no series and no recargo BY CONSTRUCTION, and a
    rectificativa could not be represented at all -- the aggregate claimed a
    vocabulary the writer could not speak. Folding the operator surface onto an
    aggregate that cannot express a rectificativa would have been a capability
    loss on its face, which is why the conservation inventory named this a
    blocking row.

    Persisted and reloaded rather than asserted in memory, because the claim is
    that all four SURVIVE the encrypted boundary.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        result = create_catalogue_invoice(
            invoice=build_catalogue_invoice(
                bucket_id=_BUCKET_ID,
                kind=InvoiceKind.ISSUED,
                counterparty_name="Minorista Recargo SL",
                counterparty_tax_id="B12345674",
                counterparty_country="ES",
                invoice_number="R-2026-0001",
                issued_at=date(2026, 5, 4),
                taxable_base=Decimal("1000.00"),
                iva_rate=Decimal("21"),
                currency="EUR",
                invoice_class=InvoiceClass.RECTIFICATIVA,
                series="R",
                rectifies_invoice_number="F-2026-0044",
                recargo_amount=Decimal("52.00"),
            ),
        )
        restored = InvoiceCatalogueRepository(bucket_id=_BUCKET_ID).load().get(result.invoice.invoice_id)

    assert restored is not None
    assert restored.invoice_class is InvoiceClass.RECTIFICATIVA
    assert restored.series == "R"
    assert restored.rectifies_invoice_number == "F-2026-0044"
    assert restored.recargo_amount == Decimal("52.00")
    # The recargo is INSIDE the invoice total (LIVA art. 161): 1000 + 210 + 52.
    assert restored.grand_total == Decimal("1262.00")


def test_a_recargo_on_an_exempt_supply_refuses() -> None:
    """A recargo cannot ride on a supply that bears no cuota (LIVA art. 161).

    The recargo de equivalencia is charged on top of the cuota of a taxable
    supply, so a supply that is exempt by law bears no recargo either. Passing
    one through the new writer parameter must therefore refuse rather than be
    carried into the totals.

    This is the sharper of the two available refusals and the reason the
    parameter is safe to expose: the writer does not merely add the figure to
    the grand total, it hands it to invariants that already know when a recargo
    is legally impossible.
    """
    from pydantic import ValidationError

    with pytest.raises(ValidationError, match="recargo_amount must be zero"):
        build_catalogue_invoice(
            bucket_id=_BUCKET_ID,
            kind=InvoiceKind.ISSUED,
            counterparty_name="Minorista Recargo SL",
            counterparty_tax_id="B12345674",
            counterparty_country="ES",
            invoice_number="R-2026-0002",
            issued_at=date(2026, 5, 4),
            taxable_base=Decimal("1000.00"),
            iva_rate=None,
            currency="EUR",
            recargo_amount=Decimal("52.00"),
        )


def test_the_default_invoice_class_is_still_ordinaria() -> None:
    """Positive control: the additive change leaves the ordinary path alone.

    Every existing caller omits all four axes, so a regression here would break
    the common case while the rectificativa proof above still passed.
    """
    invoice = build_catalogue_invoice(
        bucket_id=_BUCKET_ID,
        kind=InvoiceKind.ISSUED,
        counterparty_name="Cliente Ordinario SL",
        counterparty_tax_id="B12345674",
        counterparty_country="ES",
        invoice_number="F-2026-0100",
        issued_at=date(2026, 5, 4),
        taxable_base=Decimal("1000.00"),
        iva_rate=Decimal("21"),
        currency="EUR",
    )

    assert invoice.invoice_class is InvoiceClass.ORDINARIA
    assert invoice.series is None
    assert invoice.recargo_amount is None
    assert invoice.grand_total == Decimal("1210.00")


@pytest.mark.parametrize(
    ("kind", "expected_event"),
    [
        (InvoiceKind.ISSUED, "COLLECTIBLE_INVOICE_CREATED"),
        (InvoiceKind.RECEIVED, "PAYABLE_INVOICE_CREATED"),
    ],
)
def test_canonical_creation_emits_the_lifecycle_event_for_its_direction(
    tmp_path: Path,
    kind: InvoiceKind,
    expected_event: str,
) -> None:
    """The canonical store now emits the audit trail the slim store carried.

    The canonical write paths emitted NO bucket event of any kind, while the
    slim services emitted six types and returned their ids in the operator's
    mutation result. Repointing the operator's verbs onto this store would
    therefore have dropped the invoice audit trail and the event-ids field in
    one change, and deleting the slim store would have orphaned six enum
    members. That is why the conservation inventory ruled this a blocking row.

    Parametrised over both directions because the event type is chosen BY
    direction: a single-direction test would pass while the other half emitted
    the wrong event, which is the same silent mis-attribution the campaign has
    already found on other axes.
    """
    from ....domain.buckets import BucketEventType

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        result = create_catalogue_invoice(
            invoice=build_catalogue_invoice(
                bucket_id=_BUCKET_ID,
                kind=kind,
                counterparty_name="Papeleria Sol SL",
                counterparty_tax_id="A58818501",
                counterparty_country="ES",
                invoice_number=f"EV-2026-{kind.value}",
                issued_at=date(2026, 6, 1),
                taxable_base=Decimal("100.00"),
                iva_rate=Decimal("21"),
                currency="EUR",
            ),
        )
        from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository

        history = BucketEventHistoryRepository(objects=profile.repository).load().events.values()

    assert len(result.bucket_event_ids) == 1
    emitted = [event for event in history if event.event_id == result.bucket_event_ids[0]]
    assert len(emitted) == 1, "the returned event id must resolve in the bucket history"
    assert emitted[0].event_type is getattr(BucketEventType, expected_event)
    assert emitted[0].object_id == result.invoice.invoice_id


def test_an_entrega_intracomunitaria_must_state_its_modelo_349_clave() -> None:
    """The one category that cannot settle its own clave is refused without one.

    Claves E, M and H all carry ``INTRA_COMMUNITY_SUPPLY``: M and H are supplies
    following an exempt importation (LIVA art. 27.12), and no category predicate
    separates them from an ordinary entrega. The operator is looking at the
    document and knows which it is; the Modelo 349 resolver, running later, does
    not and can only infer E and disclose that it guessed.

    Capturing the fact where it exists is what makes the downstream disclosure a
    genuine last resort rather than the normal path.
    """
    with pytest.raises(InvoiceValidationError, match="must state its Modelo 349 operation type"):
        build_catalogue_invoice(
            bucket_id=_BUCKET_ID,
            kind=InvoiceKind.ISSUED,
            counterparty_name="Kunde GmbH",
            counterparty_tax_id="DE345678901",
            counterparty_country="DE",
            invoice_number="EU-NO-CLAVE",
            issued_at=date(2026, 2, 10),
            taxable_base=Decimal("2000.00"),
            iva_rate=Decimal("0"),
            currency="EUR",
            iva_category=IvaCategory.INTRA_COMMUNITY_SUPPLY,
        )


def test_the_clave_requirement_is_scoped_to_the_one_ambiguous_category() -> None:
    """Categories that determine their own clave are not made to restate it.

    The service categories give S and I and triangulation gives T, so demanding
    an operation type for them would be a redundant required field -- which is
    how a boundary check earns the reputation that gets it removed. A domestic
    invoice is likewise untouched.

    The positive control for the refusal above: without this, a check that
    refused every category would satisfy that test while blocking ordinary
    invoice creation entirely.
    """
    for category in (
        IvaCategory.INTRA_COMMUNITY_SERVICE_SUPPLY,
        IvaCategory.INTRA_COMMUNITY_TRIANGULATION,
        IvaCategory.DOMESTIC_EXEMPT,
    ):
        invoice = build_catalogue_invoice(
            bucket_id=_BUCKET_ID,
            kind=InvoiceKind.ISSUED,
            counterparty_name="Kunde GmbH",
            counterparty_tax_id="DE345678901",
            counterparty_country="DE",
            invoice_number=f"EU-{category.value}",
            issued_at=date(2026, 2, 10),
            taxable_base=Decimal("2000.00"),
            iva_rate=Decimal("0"),
            currency="EUR",
            iva_category=category,
        )
        assert invoice.iva_category is category
