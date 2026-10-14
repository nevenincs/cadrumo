"""Modelo 347 period, threshold, and correction tests."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import seed_test_profile_record
from cadrumo.adapters.persistence.storage.tests.secure_sql import TestRuntimeProfile
from cadrumo.application.aggregation.source_mesh import CalculationSourceContext
from cadrumo.application.modelo.work_profile import ModeloWorkProfile
from cadrumo.core.aggregation import ThirdPartyDeclarationRole
from cadrumo.core.period import Period
from cadrumo.domain.invoices.enums import invoice_class_rectificativa
from cadrumo.domain.invoices.models import Invoice
from cadrumo.domain.iva.classification import InvoiceKind
from cadrumo.domain.iva.schema import IvaCategory
from cadrumo.domain.user_profile.tests.profile_creation_authority import (
    profile_creation_context_for_test as _profile_creation_context_for_test,
)
from cadrumo.domain.user_profile.values import ProfileSetupState, UserProfileFact
from cadrumo.domain.user_profile.values import create_user_profile_record as _create_profile_record_for_test

from .published_authority_support import published_authority_operation
from .source_resolver_test_support import (
    _BUCKET_ID,
    _domestic_invoice,
    _invoice,
    _m347_2026_context,
    _modelo_revision,
    _public_administration_profile_facts,
    _public_resolution,
    _statutory_information_duty_profile_facts,
    _unsettled_reading_refs,
)
from .source_resolver_test_support import _generation_pinned_authority as _generation_pinned_authority
from .source_resolver_test_support import secure_profile as secure_profile

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]


def _seed_profile(bucket_id: str, facts: tuple[UserProfileFact, ...]) -> None:
    seed_test_profile_record(
        _create_profile_record_for_test(
            context=_profile_creation_context_for_test(),
            setup_state=ProfileSetupState.COMPLETE,
            profile_id=bucket_id,
            facts=facts,
        ),
    )


def _m347_context(bucket_id: str, *, filing_year: int) -> CalculationSourceContext:
    return CalculationSourceContext(
        bucket_id=bucket_id,
        modelo="347",
        filing_year=filing_year,
        period=Period.from_year_and_code(filing_year, "0A"),
        revision=_modelo_revision("347", "2025-y-siguientes" if filing_year >= 2025 else "2011-2024"),
    )


def test_m347_clave_d_kept_apart_from_adquisiciones_is_declared_and_disclosed_as_unsettled(
    secure_profile: TestRuntimeProfile,
) -> None:
    """Art. 33.3 neither joins clave D to the ordinary adquisiciones nor separates it.

    The registry keeps D in its own bucket and flags that reading, so a D
    acquisition is declared on it and the calculation says the reading is
    open. An ordinary acquisition of the same filer carries no such advisory.
    """
    _seed_profile(secure_profile.bucket_id, _statutory_information_duty_profile_facts())
    context = _m347_context(secure_profile.bucket_id, filing_year=2026)
    outside_activity_purchase = _invoice(
        bucket_id=None,
        kind=InvoiceKind.RECEIVED,
        invoice_number="M347-D-UNSETTLED-2026-001",
        issued_at=date(2026, 5, 1),
        counterparty_tax_id="C3333333G",
        counterparty_name="Proveedor Al Margen SL",
        counterparty_country="ES",
        base_total=Decimal("3500.00"),
        iva_category=IvaCategory("domestic_general"),
    ).model_copy(update={"outside_economic_activity": True})
    within_activity_purchase = outside_activity_purchase.model_copy(
        update={"outside_economic_activity": False, "invoice_number": "M347-A-SETTLED-2026-001"},
    )

    disclosed = _public_resolution((outside_activity_purchase,), context=context)
    ordinary = _public_resolution((within_activity_purchase,), context=context)

    assert disclosed.binding_values["modelo-347-declarante-numero-personas-entidades"] == Decimal("1")
    assert _unsettled_reading_refs(disclosed) == ["m347-threshold-bucket:adquisiciones_al_margen_de_la_actividad"]
    advisory = next(item for item in disclosed.diagnostics if item.reason == "unsettled_legal_reading")
    assert "M347-D-UNSETTLED-2026-001" in advisory.message
    assert advisory.asserted_legal_refs == ("rd-1065-2007:art-33",)
    assert advisory.remedy
    assert ordinary.binding_values["modelo-347-declarante-numero-personas-entidades"] == Decimal("1")
    assert _unsettled_reading_refs(ordinary) == []


def test_m347_clave_e_below_the_floor_is_declared_from_2014_and_disclosed_until_the_2025_design(
    secure_profile: TestRuntimeProfile,
) -> None:
    """A 1,000 EUR subvención: declared in 2024 and in 2025, but disclosed only in 2024.

    The consolidated art. 33.3 relates subvenciones "cualquiera que sea su
    importe"; the 2011 design still used for 2024 says "superiores a 3.005,06
    euros", so 2024 carries the advisory and 2025, whose design agrees with
    the regulation, does not.
    """
    _seed_profile(secure_profile.bucket_id, _public_administration_profile_facts())
    resolutions = {}
    for filing_year in (2024, 2025):
        subvencion = _invoice(
            bucket_id=None,
            kind=InvoiceKind.ISSUED,
            invoice_number=f"M347-E-{filing_year}-001",
            issued_at=date(filing_year, 5, 1),
            counterparty_tax_id="C3333333G",
            counterparty_name="Beneficiario Subvencion SL",
            counterparty_country="ES",
            base_total=Decimal("1000.00"),
            iva_category=IvaCategory("domestic_general"),
        ).model_copy(update={"is_subvencion_ayuda": True})
        resolutions[filing_year] = _public_resolution(
            (subvencion,), context=_m347_context(secure_profile.bucket_id, filing_year=filing_year)
        )

    for resolution in resolutions.values():
        assert resolution.binding_values["modelo-347-declarante-numero-personas-entidades"] == Decimal("1")
        assert resolution.binding_values["modelo-347-declarante-importe-total-anual-operaciones"] == Decimal("1000.00")
    assert _unsettled_reading_refs(resolutions[2024]) == ["m347-threshold-bucket:subvenciones_satisfechas"]
    assert _unsettled_reading_refs(resolutions[2025]) == []


def test_m347_nil_total_in_a_bucket_without_floor_is_declared_and_disclosed(
    secure_profile: TestRuntimeProfile,
) -> None:
    """A bucket related whatever its amount admits a nil total; whether it belongs is not settled."""
    _seed_profile(secure_profile.bucket_id, _public_administration_profile_facts())
    context = _m347_context(secure_profile.bucket_id, filing_year=2026)
    nil_subvencion = _invoice(
        bucket_id=None,
        kind=InvoiceKind.ISSUED,
        invoice_number="M347-E-NIL-2026-001",
        issued_at=date(2026, 5, 1),
        counterparty_tax_id="C3333333G",
        counterparty_name="Beneficiario Subvencion SL",
        counterparty_country="ES",
        base_total=Decimal("0.00"),
        iva_category=IvaCategory("domestic_general"),
    ).model_copy(update={"is_subvencion_ayuda": True})
    positive_subvencion = _invoice(
        bucket_id=None,
        kind=InvoiceKind.ISSUED,
        invoice_number="M347-E-POSITIVE-2026-001",
        issued_at=date(2026, 5, 1),
        counterparty_tax_id="B12345674",
        counterparty_name="Otro Beneficiario SL",
        counterparty_country="ES",
        base_total=Decimal("10.00"),
        iva_category=IvaCategory("domestic_general"),
    ).model_copy(update={"is_subvencion_ayuda": True})

    resolution = _public_resolution((nil_subvencion, positive_subvencion), context=context)

    assert resolution.binding_values["modelo-347-declarante-numero-personas-entidades"] == Decimal("2")
    assert _unsettled_reading_refs(resolution) == ["m347-threshold-bucket:nonpositive-total"]
    advisory = next(item for item in resolution.diagnostics if item.reason == "unsettled_legal_reading")
    assert "M347-E-NIL-2026-001" in advisory.message
    assert "M347-E-POSITIVE-2026-001" not in advisory.message


def _sale(bucket_id: str, *, invoice_number: str, issued_at: date, gross: str) -> Invoice:
    """An issued domestic sale to one customer whose gross total is ``gross`` (21% IVA included)."""
    gross_total = Decimal(gross)
    base_total = (gross_total / Decimal("1.21")).quantize(Decimal("0.01"))
    return _domestic_invoice(
        bucket_id=bucket_id,
        kind=InvoiceKind.ISSUED,
        invoice_number=invoice_number,
        issued_at=issued_at,
        counterparty_tax_id="B12345674",
        counterparty_name="Cliente Rectificado SL",
        base_total=base_total,
        iva_total=gross_total - base_total,
    )


def _rectificativa_of(original_number: str, sale: Invoice) -> Invoice:
    """``sale`` reissued as the factura rectificativa of ``original_number`` (RD 1619/2012 art. 15)."""
    return sale.model_copy(
        update={
            "invoice_class": invoice_class_rectificativa(),
            "series": "R",
            "rectifies_invoice_number": original_number,
        },
    )


def _declarado_row(resolution, *, clave: str) -> dict[str, object]:
    rows: dict[int, dict[str, object]] = {}
    for (binding_id, row_index), value in resolution.row_binding_values.items():
        rows.setdefault(row_index, {})[str(binding_id).removeprefix("modelo-347-contraparte-row-")] = value
    return next(row for row in rows.values() if row["clave"] == clave)


def test_m347_nets_a_rectificativa_against_the_operation_it_corrects(secure_profile: TestRuntimeProfile) -> None:
    """RD 1065/2007 art. 34.4: the annual amount is declared "neto de las devoluciones, descuentos y bonificaciones".

    A 5,000 sale in the first quarter and its 1,000 rectificativa in the second
    leave one declarado record of 4,000 (5,000 in Q1, -1,000 in Q2). Added
    rather than netted, the same two invoices would declare 6,000.
    """
    bucket_id = secure_profile.bucket_id
    sale = _sale(bucket_id, invoice_number="F-2026-001", issued_at=date(2026, 2, 10), gross="5000.00")
    correction = _rectificativa_of(
        "F-2026-001",
        _sale(bucket_id, invoice_number="R-2026-001", issued_at=date(2026, 5, 10), gross="1000.00"),
    )

    resolution = _public_resolution((sale, correction), context=_m347_2026_context(bucket_id))

    assert resolution.binding_values["modelo-347-declarante-numero-personas-entidades"] == Decimal("1")
    assert resolution.binding_values["modelo-347-declarante-importe-total-anual-operaciones"] == Decimal("4000.00")
    row = _declarado_row(resolution, clave="B")
    assert (row["importe"], row["importe-q1"], row["importe-q2"]) == (
        Decimal("4000.00"),
        Decimal("5000.00"),
        Decimal("-1000.00"),
    )
    assert _unsettled_reading_refs(resolution) == ["m347-rectificativa:netted-as-reduction"]
    advisory = next(item for item in resolution.diagnostics if item.reason == "unsettled_legal_reading")
    assert "R-2026-001" in advisory.message
    assert "not related in this ejercicio" not in advisory.message
    assert advisory.asserted_legal_refs == ("rd-1065-2007:art-34.4",)


def test_m347_full_rectification_nets_to_nil_and_is_left_out_with_an_advisory(
    secure_profile: TestRuntimeProfile,
) -> None:
    """A sale rectified in full nets to nil: art. 33.1 relates only a party above its floor, so no record."""
    bucket_id = secure_profile.bucket_id
    sale = _sale(bucket_id, invoice_number="F-2026-002", issued_at=date(2026, 3, 1), gross="5000.00")
    correction = _rectificativa_of(
        "F-2026-002",
        _sale(bucket_id, invoice_number="R-2026-002", issued_at=date(2026, 9, 1), gross="5000.00"),
    )

    resolution = _public_resolution((sale, correction), context=_m347_2026_context(bucket_id))

    assert resolution.binding_values["modelo-347-declarante-numero-personas-entidades"] == Decimal("0")
    assert resolution.binding_values["modelo-347-declarante-importe-total-anual-operaciones"] == Decimal("0")
    assert resolution.row_binding_values == {}
    assert _unsettled_reading_refs(resolution) == [
        "m347-rectificativa:netted-as-reduction",
        "m347-threshold-bucket:nonpositive-total-left-out",
    ]
    left_out = next(
        item for item in resolution.diagnostics if item.source_ref == "m347-threshold-bucket:nonpositive-total-left-out"
    )
    assert "F-2026-002" in left_out.message
    assert "R-2026-002" in left_out.message
    assert left_out.asserted_legal_refs == ("rd-1065-2007:art-33", "rd-1065-2007:art-34.4")


def test_m347_rectificativa_of_an_invoice_outside_the_ejercicio_is_named(
    secure_profile: TestRuntimeProfile,
) -> None:
    """A rectificativa of a 2025 sale reduces the 2026 total, and the advisory says its original is not in 2026."""
    bucket_id = secure_profile.bucket_id
    earlier_sale = _sale(bucket_id, invoice_number="F-2025-099", issued_at=date(2025, 11, 20), gross="2000.00")
    sale = _sale(bucket_id, invoice_number="F-2026-003", issued_at=date(2026, 4, 1), gross="6000.00")
    correction = _rectificativa_of(
        "F-2025-099",
        _sale(bucket_id, invoice_number="R-2026-003", issued_at=date(2026, 1, 15), gross="500.00"),
    )

    resolution = _public_resolution((earlier_sale, sale, correction), context=_m347_2026_context(bucket_id))

    assert resolution.binding_values["modelo-347-declarante-importe-total-anual-operaciones"] == Decimal("5500.00")
    advisory = next(
        item for item in resolution.diagnostics if item.source_ref == "m347-rectificativa:netted-as-reduction"
    )
    assert "R-2026-003 rectify an invoice not related in this ejercicio" in advisory.message


def _regime_profile_facts(
    *,
    estimation: str,
    iva_regime: str,
    extra: tuple[UserProfileFact, ...] = (),
) -> tuple[UserProfileFact, ...]:
    return (
        UserProfileFact(path="identity.tax_id", value="B12345674"),
        UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
        UserProfileFact(path="irpf.estimation_regime", value=estimation),
        UserProfileFact(path="iva.regime", value=iva_regime),
        UserProfileFact(path="iva.m303_regime_composition", value="general"),
        UserProfileFact(path="iva.redeme_enrolled", value=False),
        UserProfileFact(path="iva.cash_accounting_regime_enrolled", value=False),
        UserProfileFact(path="iva.voluntary_sii_enrolled", value=False),
        UserProfileFact(path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled", value=False),
        *extra,
    )


def _supplier_and_customer_invoices(bucket_id: str) -> tuple[Invoice, Invoice]:
    """A received invoice from a supplier and an issued one to a customer, each above the floor."""
    received = _domestic_invoice(
        bucket_id=bucket_id,
        kind=InvoiceKind.RECEIVED,
        invoice_number="M347-PROVEEDOR-2026-001",
        issued_at=date(2026, 6, 1),
        counterparty_tax_id="A58818501",
        counterparty_name="Proveedor Mayorista SA",
        base_total=Decimal("5000.00"),
        iva_total=Decimal("1050.00"),
    )
    issued = _domestic_invoice(
        bucket_id=bucket_id,
        kind=InvoiceKind.ISSUED,
        invoice_number="M347-CLIENTE-2026-001",
        issued_at=date(2026, 6, 1),
        counterparty_tax_id="C3333333G",
        counterparty_name="Cliente Hosteleria SL",
        base_total=Decimal("4000.00"),
        iva_total=Decimal("840.00"),
    )
    return received, issued


def _declared_invoice_ids(resolution) -> set[str]:
    return {item.source_ref.split(":", 1)[1] for item in resolution.provenance}


@pytest.mark.parametrize(
    ("estimation", "iva_regime", "received_declared"),
    [
        pytest.param("objetiva", "RECARGO_EQUIVALENCIA", False, id="modulos-recargo"),
        pytest.param("objetiva", "REAGP", False, id="modulos-reagp"),
        pytest.param("objetiva", "SIMPLIFICADO", True, id="modulos-simplificado"),
        pytest.param("directa_normal", "GENERAL", True, id="directa-general"),
        pytest.param("directa_simplificada", "RECARGO_EQUIVALENCIA", True, id="directa-recargo"),
    ],
)
def test_m347_relates_only_issued_invoices_of_an_estimacion_objetiva_filer_under_a_special_regime(
    secure_profile: TestRuntimeProfile,
    estimation: str,
    iva_regime: str,
    received_declared: bool,
) -> None:
    """Art. 32.b: "salvo por las operaciones por las que emitan factura", plus the simplificado's received invoices.

    The issued invoice is declared for every filer. The received one from a
    supplier above the floor is left out only for a módulos filer under the
    recargo de equivalencia or the REAGP; the simplificado's libro registro de
    facturas recibidas keeps it, and a filer outside estimación objetiva is
    never scoped.
    """
    _seed_profile(secure_profile.bucket_id, _regime_profile_facts(estimation=estimation, iva_regime=iva_regime))
    received, issued = _supplier_and_customer_invoices(secure_profile.bucket_id)

    resolution = _public_resolution(
        (received, issued), context=_m347_context(secure_profile.bucket_id, filing_year=2026)
    )

    expected = {issued.invoice_id, received.invoice_id} if received_declared else {issued.invoice_id}
    assert _declared_invoice_ids(resolution) == expected
    assert resolution.binding_values["modelo-347-declarante-numero-personas-entidades"] == Decimal(len(expected))


def test_m347_reads_the_filer_regime_as_of_the_filing_period(secure_profile: TestRuntimeProfile) -> None:
    """A regime that starts after the ejercicio does not reach back into it.

    The filer moves from the general regime to the recargo de equivalencia
    from 2027. For 2026 the received invoice is still related; read without
    the filing period's date, the later regime would wrongly drop it.
    """
    general_until_2026 = tuple(
        fact.model_copy(update={"valid_to": date(2026, 12, 31)}) if fact.path == "iva.regime" else fact
        for fact in _regime_profile_facts(estimation="objetiva", iva_regime="GENERAL")
    )
    recargo_from_2027 = UserProfileFact(path="iva.regime", value="RECARGO_EQUIVALENCIA", valid_from=date(2027, 1, 1))
    _seed_profile(secure_profile.bucket_id, (*general_until_2026, recargo_from_2027))
    received, issued = _supplier_and_customer_invoices(secure_profile.bucket_id)

    in_2026 = _public_resolution((received, issued), context=_m347_context(secure_profile.bucket_id, filing_year=2026))

    assert _declared_invoice_ids(in_2026) == {issued.invoice_id, received.invoice_id}


def test_m347_reads_the_filer_from_the_calculation_pinned_profile_not_per_invoice() -> None:
    """The pinned profile and authority lease of the context decide every invoice; nothing is reloaded.

    No profile is stored for this bucket and no profile session is open, so an
    invoice-by-invoice reload would find no roles and no regime. The roles and
    the art. 32.b scope therefore reach the three invoices only through the
    context's own pinned profile: the received clave D acquisition classifies
    as D, the received ordinary purchase is related under the simplificado,
    and a recargo de equivalencia filer drops the received ones.
    """
    operation = published_authority_operation()
    decode_context = operation.profile_decode_context()
    outside_activity, issued = _supplier_and_customer_invoices(_BUCKET_ID)
    outside_activity = outside_activity.model_copy(update={"outside_economic_activity": True})
    ordinary_purchase = _domestic_invoice(
        bucket_id=_BUCKET_ID,
        kind=InvoiceKind.RECEIVED,
        invoice_number="M347-COMPRA-2026-002",
        issued_at=date(2026, 7, 1),
        counterparty_tax_id="B11223344",
        counterparty_name="Otro Proveedor SL",
        base_total=Decimal("5000.00"),
        iva_total=Decimal("1050.00"),
    )
    roles = UserProfileFact(
        path="taxpayer_type.declaration_roles",
        value=ThirdPartyDeclarationRole.from_registry("statutory_information_duty_entity").value,
    )

    def resolution_for(iva_regime: str):
        record = _create_profile_record_for_test(
            context=_profile_creation_context_for_test(),
            setup_state=ProfileSetupState.COMPLETE,
            profile_id=_BUCKET_ID,
            facts=_regime_profile_facts(estimation="objetiva", iva_regime=iva_regime, extra=(roles,)),
        )
        context = _m347_context(_BUCKET_ID, filing_year=2026).model_copy(
            update={
                "profile": ModeloWorkProfile(record=record, profile_decode_context=decode_context),
                "operation": operation,
            },
        )
        return _public_resolution((outside_activity, issued, ordinary_purchase), context=context)

    simplificado = resolution_for("SIMPLIFICADO")
    recargo = resolution_for("RECARGO_EQUIVALENCIA")

    assert _declared_invoice_ids(simplificado) == {
        outside_activity.invoice_id,
        issued.invoice_id,
        ordinary_purchase.invoice_id,
    }
    clave_d_rows = {
        row_index
        for (binding_id, row_index), value in simplificado.row_binding_values.items()
        if binding_id == "modelo-347-contraparte-row-clave" and value == "D"
    }
    assert len(clave_d_rows) == 1
    assert _declared_invoice_ids(recargo) == {issued.invoice_id}
