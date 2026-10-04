"""Modelo 347 type 1 totals and declarado identification, resolved from the compiled authored registry.

Both record designs (aeat-dr-347-2011 and aeat-dr-347-2025) fill the type 1
NÚMERO TOTAL DE PERSONAS Y ENTIDADES (136-144) and IMPORTE TOTAL ANUAL (145-160)
from the type 2 records, so the export fields read the declarante summary
bindings directly and no manual casilla stands in for them. The declarado NIF
"solo se cumplimentará con los NIF asignados en España"; a non-resident without
permanent establishment is declared by its país de residencia (79-80), and the
2025 design adds the NIF OPERADOR COMUNITARIO (264-280), "incompatible
(excluyente)" with the Spanish NIF, under RD 1065/2007 art. 34.1.b.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cadrumo.application.aggregation.source_mesh import CalculationSourceContext
from cadrumo.application.invoices.source_resolver import InvoiceCatalogueSourceResolver
from cadrumo.application.invoices.source_resolver_ports import InvoiceSourceResolverPorts
from cadrumo.application.modelo.work_profile import ModeloWorkProfile
from cadrumo.core.aggregation import BindingSourceKind, ThirdPartyDeclarationRole
from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from cadrumo.domain.calculations.registry.fixed_width_codec import render_fixed_width_export_field
from cadrumo.domain.calculations.registry.invoice_bindings import (
    InvoiceObservation,
    resolve_invoice_binding_row_values,
)
from cadrumo.domain.calculations.registry.queries import RegistryQueryService
from cadrumo.domain.calculations.registry.schema import ModeloRevision
from cadrumo.domain.calculations.registry.schema_exports import ExportFieldDefinition, ExportRecordDefinition
from cadrumo.domain.invoices.enums import IvaRate, PaymentStatus, invoice_class_rectificativa
from cadrumo.domain.invoices.models import Invoice, InvoiceCatalogue, InvoiceLine, derive_invoice_id
from cadrumo.domain.invoices.tests.catalogue_support import build_invoice_catalogue
from cadrumo.domain.iva.classification import InvoiceKind
from cadrumo.domain.user_profile.tests.profile_creation_authority import profile_creation_context_for_test
from cadrumo.domain.user_profile.values import ProfileSetupState, UserProfileFact, create_user_profile_record

from ..compiler.authority import compiled_bundled_authority
from ..compiler.validate_revision_rules import validate_informative_class_invariant

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain, pytest.mark.usefixtures("governed_fact_scope")]

_REVISIONS = ("2011-2024", "2025-y-siguientes")
_COUNT = "modelo-347-declarante-numero-personas-entidades"
_TOTAL = "modelo-347-declarante-importe-total-anual-operaciones"
_NIF = "modelo-347-contraparte-row-nif"
_COUNTRY = "modelo-347-contraparte-row-pais-codigo"
_COMMUNITY_VAT = "modelo-347-contraparte-row-nif-operador-comunitario"
_NAME = "modelo-347-contraparte-row-nombre"


def _revision(revision_id: str) -> ModeloRevision:
    return next(
        revision
        for _modelo, revision in RegistryQueryService(compiled_bundled_authority()).iter_modelo_revisions(
            modelo_codes=("347",),
        )
        if revision.id == revision_id
    )


def _record(revision: ModeloRevision, record_id: str) -> ExportRecordDefinition:
    return next(record for layout in revision.export_layouts for record in layout.records if record.id == record_id)


def _field(record: ExportRecordDefinition, offset: int) -> ExportFieldDefinition:
    return next(field for field in record.fields if field.offset == offset)


@pytest.mark.parametrize("revision_id", _REVISIONS)
def test_type_1_totals_are_export_fields_reading_the_summary_bindings(revision_id: str) -> None:
    revision = _revision(revision_id)
    declarante = _record(revision, "m347-declarante")
    count, total = _field(declarante, 136), _field(declarante, 145)

    assert (str(count.binding), str(total.binding)) == (_COUNT, _TOTAL)
    assert count.casilla_id is None and total.casilla_id is None
    assert (total.data_type, total.signed, total.length) == ("money", True, 16)
    assert render_fixed_width_export_field(total, Decimal("-250.10")) == "N000000000025010"
    assert render_fixed_width_export_field(count, Decimal(3)) == "000000003"
    casilla_ids = {str(casilla.id) for casilla in revision.casillas}
    assert not casilla_ids & {"decl.total-personas-entidades", "decl.importe-total-anual"}


def test_modelo_347_stays_informative_with_no_bound_casilla() -> None:
    modelo = compiled_bundled_authority().modelo("347")

    assert modelo.calculation_class == "informative"
    assert validate_informative_class_invariant(modelo) == []


def _observation(party_tax_id: str, country_code: str, name: str) -> InvoiceObservation:
    return InvoiceObservation(
        invoice_id=f"inv-{party_tax_id}",
        source_kind=BindingSourceKind.COLLECTIBLE_INVOICE,
        party_tax_id=party_tax_id,
        country_code=country_code,
        transaction_date=date(2025, 5, 12),
        base_amount=Decimal("8000.00"),
        invoice_total_amount=Decimal("8000.00"),
        operation_clave="B",
        party_legal_name=name,
    )


_PARTIES = (
    _observation("B12345674", "ES", "CLIENTE NACIONAL SL"),
    _observation("DE123456789", "DE", "KUNDE GMBH"),
    _observation("123456789", "US", "CUSTOMER INC"),
)


def _rows(revision: ModeloRevision) -> dict[str, dict[str, object]]:
    values = resolve_invoice_binding_row_values(revision, _PARTIES, effective_date=date(2025, 12, 31))
    by_index: dict[int, dict[str, object]] = {}
    for (binding_id, row_index), value in values.items():
        by_index.setdefault(row_index, {})[str(binding_id)] = value
    return {str(row[_NAME]): row for row in by_index.values()}


def test_declarado_rows_identify_residents_by_nif_and_non_residents_by_country_and_nif_iva() -> None:
    revision = _revision("2025-y-siguientes")
    rows = _rows(revision)
    declarado = _record(revision, "m347-declarado")
    nif, country, community = _field(declarado, 18), _field(declarado, 79), _field(declarado, 264)

    assert (str(nif.binding), str(country.binding), str(community.binding)) == (_NIF, _COUNTRY, _COMMUNITY_VAT)
    resident, community_operator, third_country = (
        rows["CLIENTE NACIONAL SL"],
        rows["KUNDE GMBH"],
        rows["CUSTOMER INC"],
    )
    assert (resident[_NIF], resident[_COUNTRY], resident[_COMMUNITY_VAT]) == ("B12345674", "", "")
    assert (community_operator[_NIF], community_operator[_COUNTRY], community_operator[_COMMUNITY_VAT]) == (
        "",
        "DE",
        "DE123456789",
    )
    assert (third_country[_NIF], third_country[_COUNTRY], third_country[_COMMUNITY_VAT]) == ("", "US", "")
    assert render_fixed_width_export_field(nif, community_operator[_NIF]) == " " * 9
    assert render_fixed_width_export_field(country, resident[_COUNTRY]) == "  "
    assert render_fixed_width_export_field(community, community_operator[_COMMUNITY_VAT]) == "DE123456789      "


def test_a_malformed_community_identifier_is_declared_by_country_alone() -> None:
    revision = _revision("2025-y-siguientes")
    values = resolve_invoice_binding_row_values(
        revision, (_observation("DE12", "DE", "KUNDE GMBH"),), effective_date=date(2025, 12, 31)
    )
    row = {str(binding_id): value for (binding_id, _index), value in values.items()}

    assert (row[_NIF], row[_COUNTRY], row[_COMMUNITY_VAT]) == ("", "DE", "")


def test_the_2011_design_has_no_community_identifier_slot() -> None:
    revision = _revision("2011-2024")

    assert _COMMUNITY_VAT not in {str(binding.id) for binding in revision.bindings}
    assert str(_field(_record(revision, "m347-declarado"), 18).binding) == _NIF


_BUCKET_ID = "24242424-2424-4242-8242-242424242424"
_IMPORTE = "modelo-347-contraparte-row-importe"
_QUARTERS = tuple(f"modelo-347-contraparte-row-importe-q{quarter}" for quarter in range(1, 5))
_CRITERIO_CAJA = "modelo-347-contraparte-row-criterio-caja"
_INVERSION_SUJETO_PASIVO = "modelo-347-contraparte-row-inversion-sujeto-pasivo"
_PROVINCIA = "modelo-347-contraparte-row-provincia-codigo"


@pytest.mark.parametrize(("revision_id", "year"), (("2011-2024", 2024), ("2025-y-siguientes", 2025)))
def test_provincia_export_reads_each_declared_row_binding(revision_id: str, year: int) -> None:
    revision = _revision(revision_id)
    field = _field(_record(revision, "m347-declarado"), 77)
    assert str(field.binding) == _PROVINCIA and field.casilla_id is None
    observations = tuple(
        observation.model_copy(update={"transaction_date": date(year, 5, 12)}) for observation in _PARTIES
    )
    values = resolve_invoice_binding_row_values(revision, observations, effective_date=date(year, 12, 31))
    foreign_provinces = [value for (binding_id, _index), value in values.items() if str(binding_id) == _PROVINCIA]
    assert foreign_provinces.count("99") == 2
    assert all(render_fixed_width_export_field(field, value) == "99" for value in foreign_provinces if value == "99")


def _filer_profile(operation: PinnedAuthorityOperation, *extra: UserProfileFact) -> ModeloWorkProfile:
    facts = (
        UserProfileFact(path="identity.tax_id", value="B12345674"),
        UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
        UserProfileFact(path="iva.regime", value="GENERAL"),
        UserProfileFact(path="iva.m303_regime_composition", value="general"),
        UserProfileFact(path="iva.redeme_enrolled", value=False),
        UserProfileFact(path="iva.voluntary_sii_enrolled", value=False),
        UserProfileFact(path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled", value=False),
        *extra,
    )
    if not any(fact.path == "iva.cash_accounting_regime_enrolled" for fact in facts):
        facts = (*facts, UserProfileFact(path="iva.cash_accounting_regime_enrolled", value=False))
    record = create_user_profile_record(
        context=profile_creation_context_for_test(),
        setup_state=ProfileSetupState.COMPLETE,
        profile_id=_BUCKET_ID,
        facts=facts,
    )
    return ModeloWorkProfile(record=record, profile_decode_context=operation.profile_decode_context())


def _role(token: str) -> UserProfileFact:
    return UserProfileFact(
        path="taxpayer_type.declaration_roles",
        value=ThirdPartyDeclarationRole.from_registry(token).value,
    )


def _operation(
    number: str,
    issued_at: date,
    base: str,
    *,
    iva: str = "0",
    kind: InvoiceKind = InvoiceKind.ISSUED,
    tax_id: str = "C3333333G",
    name: str = "CONTRAPARTE PRUEBA SL",
    country: str = "ES",
    **facts: object,
) -> Invoice:
    """One operation of ``base`` plus ``iva`` at 21% (exempt when ``iva`` is nil), built inside an operation."""
    base_total, iva_total = Decimal(base), Decimal(iva)
    total = base_total + iva_total
    return Invoice.model_validate(
        {
            "invoice_id": derive_invoice_id(
                kind=kind,
                invoice_number=number,
                issued_at=issued_at,
                counterparty_tax_id=tax_id,
                currency="EUR",
                grand_total=total,
            ),
            "kind": kind,
            "invoice_number": number,
            "issued_at": issued_at,
            "counterparty_name": name,
            "counterparty_tax_id": tax_id,
            "counterparty_country": country,
            "base_total": base_total,
            "iva_total": iva_total,
            "grand_total": total,
            "currency": "EUR",
            "lines": (
                InvoiceLine(
                    description="Operacion",
                    quantity=Decimal("1"),
                    unit_price=base_total,
                    subtotal=base_total,
                    iva_rate=IvaRate.from_registry("RATE_21" if iva_total else "EXEMPT"),
                    iva_amount=iva_total,
                ),
            ),
            "payment_status": PaymentStatus.PAID,
            **facts,
        },
    )


class _CatalogueReader:
    def __init__(self, invoices: tuple[Invoice, ...]) -> None:
        self._catalogue = build_invoice_catalogue(invoices)

    def load(self) -> InvoiceCatalogue:
        return self._catalogue


def _resolve_2025(invoices: tuple[Invoice, ...], profile: ModeloWorkProfile):
    context = CalculationSourceContext(
        bucket_id=_BUCKET_ID,
        modelo="347",
        filing_year=2025,
        period=Period.from_year_and_code(2025, "0A"),
        revision=_revision("2025-y-siguientes"),
        profile=profile,
    )
    return InvoiceCatalogueSourceResolver(
        ports=InvoiceSourceResolverPorts(catalogue_reader=_CatalogueReader(invoices)),
    ).resolve(context)


def _declarado_rows(resolution) -> list[dict[str, object]]:
    rows: dict[int, dict[str, object]] = {}
    for (binding_id, row_index), value in resolution.row_binding_values.items():
        rows.setdefault(row_index, {})[str(binding_id)] = value
    return [rows[index] for index in sorted(rows)]


def _render(record: ExportRecordDefinition, offset: int, row: dict[str, object]) -> str:
    field = _field(record, offset)
    return render_fixed_width_export_field(field, row[str(field.binding)])


def test_a_net_negative_declarado_renders_the_n_sign_in_the_2025_record() -> None:
    """RD 1065/2007 art. 34.4 nets the rectificativas; the 2025 design signs a negative amount with "N".

    aeat-dr-347-2025 pos. 83: "Se consignará una "N" cuando el importe anual de las
    operaciones sea menor que 0 (cero)", and the same for each quarter (pos. 136, 168,
    200, 232). A public administration's 1,000 subvención (clave E, related whatever its
    amount) and its 1,500 rectificativa net to -500 through the real resolver, and the
    compiled 2025 declarado record renders that row as "N" plus the unsigned amount.
    """
    with bundled_indexed_authority().operation() as operation:
        subvencion = _operation("E-2025-001", date(2025, 2, 3), "1000.00", is_subvencion_ayuda=True)
        correction = _operation(
            "E-2025-001R",
            date(2025, 5, 5),
            "1500.00",
            is_subvencion_ayuda=True,
            invoice_class=invoice_class_rectificativa(),
            series="R",
            rectifies_invoice_number="E-2025-001",
        )
        resolution = _resolve_2025(
            (subvencion, correction),
            _filer_profile(operation, _role("public_administration_entity")),
        )

    (row,) = _declarado_rows(resolution)
    declarado = _record(_revision("2025-y-siguientes"), "m347-declarado")
    assert row["modelo-347-contraparte-row-clave"] == "E"
    assert _render(declarado, 83, row) == "N000000000050000"
    assert _render(declarado, 136, row) == " 000000000100000"
    assert _render(declarado, 168, row) == "N000000000150000"
    assert resolution.binding_values[_TOTAL] == Decimal("-500.00")


def _by_name(rows: list[dict[str, object]]) -> dict[tuple[str, str, str], dict[str, object]]:
    return {(str(row[_NAME]), str(row[_CRITERIO_CAJA]), str(row[_INVERSION_SUJETO_PASIVO])): row for row in rows}


def _source_refs(resolution) -> set[str | None]:
    return {item.source_ref for item in resolution.diagnostics}


def test_criterio_de_caja_and_reverse_charge_operations_are_separate_records_with_their_own_marks() -> None:
    """RD 1065/2007 art. 34.1.j and k: these operations "se harán constar separadamente".

    One customer buys 4,000 ordinarily and 5,000 under the criterio de caja (the
    invoice prints the RD 1619/2012 art. 6.1.p mention); one supplier sells 6,000
    with the declarant as sujeto pasivo and 4,000 ordinarily. Each counterparty's
    floor is judged on its whole total, and each splits into a marked record and
    an unmarked one, so no mark is stamped on an operation it does not describe.
    The criterio de caja record carries no quarterly amounts (2025 design, pos.
    136-151: "Este campo no tendrá contenido ... sujetos pasivos destinatarios"),
    the others keep theirs.
    """
    with bundled_indexed_authority().operation() as operation:
        invoices = (
            _operation("V-1", date(2025, 2, 10), "4000.00", tax_id="C3333333G", name="CLIENTE CAJA SL"),
            _operation(
                "V-2",
                date(2025, 5, 10),
                "4132.23",
                iva="867.77",
                tax_id="C3333333G",
                name="CLIENTE CAJA SL",
                legal_mentions=("CASH_ACCOUNTING_REGIME",),
            ),
            _operation(
                "C-1",
                date(2025, 8, 1),
                "6000.00",
                kind=InvoiceKind.RECEIVED,
                tax_id="B87654323",
                name="SUBCONTRATA OBRA SL",
                iva_category="domestic_reverse_charge",
            ),
            _operation(
                "C-2",
                date(2025, 11, 1),
                "4000.00",
                kind=InvoiceKind.RECEIVED,
                tax_id="B87654323",
                name="SUBCONTRATA OBRA SL",
            ),
        )
        resolution = _resolve_2025(invoices, _filer_profile(operation))

    rows = _by_name(_declarado_rows(resolution))
    assert set(rows) == {
        ("CLIENTE CAJA SL", "", ""),
        ("CLIENTE CAJA SL", "X", ""),
        ("SUBCONTRATA OBRA SL", "", "X"),
        ("SUBCONTRATA OBRA SL", "", ""),
    }
    cash = rows[("CLIENTE CAJA SL", "X", "")]
    assert cash[_IMPORTE] == Decimal("5000.00")
    assert [cash[quarter] for quarter in _QUARTERS] == ["", "", "", ""]
    ordinary_sale = rows[("CLIENTE CAJA SL", "", "")]
    assert [ordinary_sale[quarter] for quarter in _QUARTERS] == [
        Decimal("4000.00"),
        Decimal("0"),
        Decimal("0"),
        Decimal("0"),
    ]
    reverse_charge = rows[("SUBCONTRATA OBRA SL", "", "X")]
    assert (reverse_charge[_IMPORTE], reverse_charge[_QUARTERS[2]]) == (Decimal("6000.00"), Decimal("6000.00"))
    declarado = _record(_revision("2025-y-siguientes"), "m347-declarado")
    cash_field, reverse_field = _field(declarado, 281), _field(declarado, 282)
    assert str(cash_field.binding) == _CRITERIO_CAJA and cash_field.casilla_id is None
    assert str(reverse_field.binding) == _INVERSION_SUJETO_PASIVO and reverse_field.casilla_id is None
    assert render_fixed_width_export_field(cash_field, cash[_CRITERIO_CAJA]) == "X"
    assert render_fixed_width_export_field(reverse_field, cash[_INVERSION_SUJETO_PASIVO]) == " "
    assert render_fixed_width_export_field(reverse_field, reverse_charge[_INVERSION_SUJETO_PASIVO]) == "X"
    assert resolution.binding_values[_COUNT] == Decimal("4")
    assert "m347-record:criterio-caja-devengo" in _source_refs(resolution)


@pytest.mark.parametrize(
    "filer_fact",
    [
        pytest.param(_role("propiedad_horizontal_entity"), id="propiedad-horizontal"),
        pytest.param(UserProfileFact(path="iva.cash_accounting_regime_enrolled", value=True), id="criterio-de-caja"),
    ],
)
def test_an_annual_basis_filer_reports_no_quarterly_amounts(filer_fact: UserProfileFact) -> None:
    """RD 1065/2007 art. 33.1: these filers "suministrarán toda la información ... sobre una base de cómputo anual"."""
    with bundled_indexed_authority().operation() as operation:
        purchase = _operation(
            "C-4",
            date(2025, 6, 1),
            "5000.00",
            kind=InvoiceKind.RECEIVED,
            tax_id="B87654323",
            name="PROVEEDOR SL",
        )
        resolution = _resolve_2025((purchase,), _filer_profile(operation, filer_fact))

    (row,) = _declarado_rows(resolution)
    assert row[_IMPORTE] == Decimal("5000.00")
    assert [row[quarter] for quarter in _QUARTERS] == ["", "", "", ""]
    assert row[_CRITERIO_CAJA] == ""


def test_a_non_resident_declarado_carries_provincia_99_and_a_spanish_one_is_disclosed() -> None:
    """Both designs, pos. 77-78: "En el caso de no residentes sin establecimiento permanente se consignará 99"."""
    with bundled_indexed_authority().operation() as operation:
        invoices = (
            _operation("V-4", date(2025, 2, 1), "8000.00", tax_id="US000000001", name="CUSTOMER INC", country="US"),
            _operation("V-5", date(2025, 2, 1), "8000.00", tax_id="C3333333G", name="CLIENTE NACIONAL SL"),
        )
        resolution = _resolve_2025(invoices, _filer_profile(operation))

    provincia = {str(row[_NAME]): row[_PROVINCIA] for row in _declarado_rows(resolution)}
    assert provincia == {"CUSTOMER INC": "99", "CLIENTE NACIONAL SL": ""}
    advisory = next(item for item in resolution.diagnostics if item.source_ref == "m347-record:provincia-not-recorded")
    assert "C3333333G" in advisory.message
    assert "US000000001" not in advisory.message


def test_declared_sales_disclose_that_cash_collections_are_not_recorded() -> None:
    """Art. 34.1.h: no invoice records a cash collection, so the metálico amount is disclosed, not guessed."""
    with bundled_indexed_authority().operation() as operation:
        sale = _operation("V-6", date(2025, 9, 1), "8000.00", tax_id="C3333333G", name="CLIENTE EFECTIVO SL")
        purchase = _operation(
            "C-5",
            date(2025, 9, 1),
            "8000.00",
            kind=InvoiceKind.RECEIVED,
            tax_id="B87654323",
            name="PROVEEDOR SL",
        )
        with_sale = _resolve_2025((sale, purchase), _filer_profile(operation))
        purchases_only = _resolve_2025((purchase,), _filer_profile(operation))

    advisory = next(item for item in with_sale.diagnostics if item.source_ref == "m347-record:metalico-not-recorded")
    assert advisory.asserted_legal_refs == ("rd-1065-2007:art-34.1.h",)
    assert "m347-record:metalico-not-recorded" not in _source_refs(purchases_only)
