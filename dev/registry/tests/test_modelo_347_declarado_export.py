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

from cadrumo.core.aggregation import BindingSourceKind
from cadrumo.domain.calculations.registry.fixed_width_codec import render_fixed_width_export_field
from cadrumo.domain.calculations.registry.invoice_bindings import (
    InvoiceObservation,
    resolve_invoice_binding_row_values,
)
from cadrumo.domain.calculations.registry.queries import RegistryQueryService
from cadrumo.domain.calculations.registry.schema import ModeloRevision
from cadrumo.domain.calculations.registry.schema_exports import ExportFieldDefinition, ExportRecordDefinition

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
