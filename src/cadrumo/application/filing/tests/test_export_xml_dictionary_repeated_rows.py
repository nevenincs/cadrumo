"""Two sales of a year reach the Modelo 100 XML as two elements, read through the real resolver and the real export.

The expected figures are worked by hand from the Manual Renta definition: the value of
transmission is the amount less its costs, and the gain or loss is that value less the net
value of the element. The 12,000.00 element loses 297.53 to the 2025 charge, so its net value is
11,702.47.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path
from xml.etree.ElementTree import Element

import pytest
from defusedxml import ElementTree

from cadrumo.domain.renta.actividad_asset.disposal import ActivityAssetDisposal, ActivityAssetDisposalReason

from ....core.modelo import Modelo
from ....core.period import Period
from ....core.prior_domiciliation_election import PriorDomiciliationElection
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.binding_targets import revision_bindings_by_id
from ....domain.calculations.registry.binding_value_contract import BindingValueChannel
from ....domain.calculations.registry.bindings import resolve_available_bound_inputs_by_casilla_id
from ....domain.calculations.registry.export_xml_dictionary import xml_dictionary_entries
from ....domain.filing.errors import FilingExportValidationError
from ....domain.filing.protocols import ModeloInputScalar, ModeloInputValue
from ....domain.filing.schema import ModeloDraft
from ....domain.renta.actividad_asset.lifecycle import ActivityAssetRevision
from ....domain.submission.models import ModeloDraftStatus
from ...actividad_asset.history import ActivityAssetHistory
from ...aggregation.source_mesh import CalculationSourceResolution
from ...aggregation.tests.test_modelo_source_mesh_ledger import _acquisition_row, register_asset, resolve_m100
from .._export_xml_dictionary import render_xml_dictionary_layout
from ..draft_construction import build_draft
from ..export import export_draft
from ..export_verification import verify_export
from ..runtime import ModeloOperatorProfile, RegistrySchemaAccessor, build_runtime_schema_provider
from .export_support import m151_producer_snapshot

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_XSD = "{http://www.w3.org/2001/XMLSchema}"
_ELEMENT_PATH = "DatosEconomicos/TomaDatosAmpliada/GPOtrosElementos/ElementoPatrimonial"


def _history(
    year: int,
    *,
    second_proceeds: str = "10000.00",
    extra_sales: int = 0,
    first_transaction_id: str = "c" * 64,
) -> ActivityAssetHistory:
    def sold(asset: ActivityAssetRevision, proceeds: str, costs: str, on: date) -> ActivityAssetRevision:
        return asset.with_disposal(
            ActivityAssetDisposal(
                disposal_date=on,
                reason=ActivityAssetDisposalReason.SALE,
                proceeds=Decimal(proceeds),
                transmission_costs=Decimal(costs),
            ),
        )

    in_service = date(year, 1, 1)
    first = register_asset("first", transaction_id=first_transaction_id, in_service=in_service)
    second = register_asset("second", transaction_id="d" * 64, in_service=in_service)
    others = tuple(
        register_asset(f"other-{index}", transaction_id=f"{index:064x}", in_service=in_service)
        for index in range(extra_sales)
    )
    history = ActivityAssetHistory(revisions=(first, second, *others))
    history = history.apply_correction(sold(first, "12000.00", "100.00", date(year, 6, 30)), ())
    history = history.apply_correction(sold(second, second_proceeds, "0.00", date(year, 9, 1)), ())
    for asset in others:
        history = history.apply_correction(sold(asset, "13000.00", "0.00", date(year, 6, 30)), ())
    return history


def _inputs(resolution: CalculationSourceResolution) -> dict[str, ModeloInputValue]:
    inputs: dict[str, ModeloInputValue] = {
        **{str(binding_id): value for binding_id, value in resolution.binding_values.items()},
        **{str(binding_id): value for binding_id, value in resolution.enum_binding_values.items()},
    }
    rows: dict[str, dict[str, ModeloInputScalar]] = {}
    for (binding_id, row_index), value in resolution.row_binding_values.items():
        rows.setdefault(str(binding_id), {})[str(row_index)] = value
    inputs.update(rows)
    return inputs


def _provider(operation: PinnedAuthorityOperation, year: int) -> RegistrySchemaAccessor:
    return build_runtime_schema_provider(
        filing_year=year,
        period=Period.from_year_and_code(year, "0A"),
        modelos=("100",),
        operation=operation,
    )


def _filer_with_nothing_else(provider: RegistrySchemaAccessor) -> dict[str, ModeloInputValue]:
    """State every fact the revision reads as absent, for a Madrid filer: the sales are the subject here."""
    inputs: dict[str, ModeloInputValue] = {
        "renta-profile-tax-residence-ccaa": "madrid",
        "renta-profile-taxpayer-birth-date": "1975-06-15",
        "renta-modelo-130-pagos-fraccionados": Decimal("0"),
        "renta-modelo-131-pagos-fraccionados": Decimal("0"),
    }
    for binding_id, binding in revision_bindings_by_id(provider.get_snapshot("100").revision).items():
        if binding.value.channel in {BindingValueChannel.DECIMAL, BindingValueChannel.INTEGER}:
            inputs[str(binding_id)] = Decimal("0")
        elif binding.value.channel is BindingValueChannel.BOOLEAN:
            inputs[str(binding_id)] = False
    inputs["renta-profile-declaration-type"] = Decimal("1")
    inputs["renta-modelo-100-estimacion-directa-es-normal"] = True
    return inputs


def _draft(provider: RegistrySchemaAccessor, year: int, inputs: dict[str, ModeloInputValue]) -> ModeloDraft:
    stated = {**_filer_with_nothing_else(provider), **inputs}
    amounts = {key: value for key, value in stated.items() if isinstance(value, Decimal)}
    bound_boxes = resolve_available_bound_inputs_by_casilla_id(provider.get_snapshot("100").revision, amounts)
    return build_draft(
        modelo="100",
        period=Period.from_year_and_code(year, "0A"),
        profile=ModeloOperatorProfile(tax_id="12345678Z", display_name="DECLARANTE PRUEBA"),
        inputs={**bound_boxes, **stated},
        schema_provider=provider,
    ).model_copy(update={"status": ModeloDraftStatus.APROBADO})


def _elements(payload: bytes) -> list[Element]:
    return ElementTree.fromstring(payload).findall(_ELEMENT_PATH)


def _render(provider: RegistrySchemaAccessor, draft: ModeloDraft) -> bytes:
    return render_xml_dictionary_layout(
        provider.get_snapshot("100").revision.export_layouts[0],
        draft=draft,
        headers={},
        aux_version="001",
        schema_provider=provider,
    )


def _resolved(
    year: int = 2025, *, second_proceeds: str = "10000.00", extra_sales: int = 0
) -> CalculationSourceResolution:
    return resolve_m100(_history(year, second_proceeds=second_proceeds, extra_sales=extra_sales), year=year)


def test_two_sales_export_as_two_elements_each_with_its_own_figures(
    operation: PinnedAuthorityOperation, tmp_path: Path
) -> None:
    provider = _provider(operation, 2025)
    bought = _acquisition_row("first", activity=None)
    resolved = resolve_m100(_history(2025, first_transaction_id=bought.transaction_id), rows=(bought,))
    draft = _draft(provider, 2025, _inputs(resolved))
    output_path = tmp_path / "modelo-100-2025.xml"

    export_draft(
        draft,
        output_path=output_path,
        producer_snapshot=m151_producer_snapshot().model_copy(update={"modelo": Modelo("100")}),
        prior_domiciliation_election=PriorDomiciliationElection.KEEP,
        product_software_identity=None,
        schema_provider=provider,
    )

    first, second = _elements(output_path.read_bytes())
    # A gain: 12,000 less 100 of costs is 11,900; less the net value of 11,702.47 is 197.53.
    assert first.findtext("G2DB") == "5"
    assert first.findtext("F2ONEROSA") == "1"
    assert first.findtext("G2DC") == "30/6/2025"
    assert first.findtext("G2DD") == "5/4/2025"
    assert first.findtext("G2DE") == "11900.00"
    assert first.findtext("G2DF") == "11702.47"
    assert first.findtext("G2DI") == "197.53"
    assert first.findtext("G2DS") == "197.53"
    assert first.find("G2DG") is None
    assert first.find("G2DH") is None
    # A loss: 10,000 with no costs, against a net value of 11,702.47 at 2025-06-30 terms.
    assert second.findtext("G2DC") == "1/9/2025"
    assert second.findtext("G2DE") == "10000.00"
    loss = Decimal(second.findtext("G2DF") or "") - Decimal("10000.00")
    assert second.findtext("G2DG") == str(loss)
    assert second.findtext("G2DH") == str(loss)
    assert second.find("G2DI") is None
    assert second.find("G2DS") is None
    assert verify_export(draft, file_path=output_path, schema_provider=provider).verdict.value == "match"


@pytest.mark.parametrize("year", [2022, 2023, 2024, 2025])
def test_every_edition_places_the_declared_columns_in_the_schema_order(
    operation: PinnedAuthorityOperation, year: int
) -> None:
    provider = _provider(operation, year)
    layout = provider.get_snapshot("100").revision.export_layouts[0]
    dictionary = {
        entry.casilla_id: entry.field_id
        for entry in xml_dictionary_entries(layout, sources=provider.sources, source_payloads=provider.source_payloads)
        if f"/{_ELEMENT_PATH}/" in entry.path
    }
    columns = ("1626", "1612", "1631", "1632", "1633", "1637", "1638", "1639", "1640", "1654")
    assert set(columns) <= set(dictionary), f"{year} dictionary no longer carries a declared column"
    schema = ElementTree.fromstring(provider.source_payloads[f"aeat-dr-100-{year}-xsd"])
    element = next(item for item in schema.iter(f"{_XSD}element") if item.get("name") == "ElementoPatrimonial")
    element_type = next(item for item in schema.iter(f"{_XSD}complexType") if item.get("name") == element.get("type"))
    schema_order = [item.get("name") for item in (element if len(element) else element_type).iter(f"{_XSD}element")]

    elements = _elements(_render(provider, _draft(provider, year, _inputs(_resolved(year=year)))))

    assert len(elements) == 2
    for sale in elements:
        written = [child.tag for child in sale]
        assert {"G2DB", "F2ONEROSA", "G2DC", "G2DE", "G2DF"} <= set(written)
        assert written == sorted(written, key=schema_order.index)


def test_the_scalar_totals_stay_on_the_draft(operation: PinnedAuthorityOperation) -> None:
    provider = _provider(operation, 2025)
    draft = _draft(provider, 2025, _inputs(_resolved(second_proceeds="13000.00")))

    values = {value.casilla_id: value.value for value in draft.values}
    rows = _elements(_render(provider, draft))

    assert len(rows) == 2
    assert values["1654"] == sum((Decimal(row.findtext("G2DS") or "0") for row in rows), Decimal("0"))


def test_a_typed_date_row_refuses_an_invalid_iso_date(operation: PinnedAuthorityOperation) -> None:
    provider = _provider(operation, 2025)
    draft = _draft(provider, 2025, _inputs(_resolved()))
    date_binding = "renta-activity-asset-disposal-row-transmission-date-1631"
    rows = tuple(
        value.model_copy(update={"value": "2025-99-01"}) if value.binding_id == date_binding else value
        for value in draft.binding_values
    )
    assert any(value.binding_id == date_binding for value in rows)
    with pytest.raises(FilingExportValidationError, match=r"date row binding .* carries an invalid date"):
        _render(provider, draft.model_copy(update={"binding_values": rows}))


def test_a_box_total_the_rows_do_not_add_up_to_refuses(operation: PinnedAuthorityOperation) -> None:
    provider = _provider(operation, 2025)
    inputs = _inputs(_resolved(second_proceeds="13000.00"))
    gain_total = next(key for key in inputs if key == "renta-activity-asset-disposal-gain-element-1654")
    inputs[gain_total] = Decimal("1.00")

    with pytest.raises(FilingExportValidationError, match="do not add up"):
        _render(provider, _draft(provider, 2025, inputs))


def test_a_value_on_another_box_of_the_element_refuses_rather_than_landing_on_a_sale(
    operation: PinnedAuthorityOperation,
) -> None:
    provider = _provider(operation, 2025)
    inputs = {**_inputs(_resolved(second_proceeds="13000.00")), "1652": Decimal("10.00")}

    with pytest.raises(FilingExportValidationError, match="do not add up"):
        _render(provider, _draft(provider, 2025, inputs))


def test_more_sales_than_the_schema_admits_refuses(operation: PinnedAuthorityOperation) -> None:
    provider = _provider(operation, 2025)
    # The bound comes from the XSD: 79 extra sales fill it exactly, and one more passes it.
    _render(provider, _draft(provider, 2025, _inputs(_resolved(second_proceeds="13000.00", extra_sales=78))))
    inputs = _inputs(_resolved(second_proceeds="13000.00", extra_sales=79))

    with pytest.raises(FilingExportValidationError, match="80 times"):
        _render(provider, _draft(provider, 2025, inputs))
