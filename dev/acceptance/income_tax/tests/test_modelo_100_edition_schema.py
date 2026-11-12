"""The real Modelo 100 renderer held to each edition's bundled XSD, and that XSD to a planted fault.

The whole work-unit route runs for one edition in ``test_modelo_100_export_schema``. Here
a declaration holding the facts the schema requires goes through the real draft builder
and renderer for every edition whose schema is bundled, so a refusal or violation one
edition alone would produce is seen. Editions come from the schema filenames, and each
box from that edition's dictionary, so neither is restated here.
"""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from lxml import etree

from cadrumo.application.filing.draft_construction import build_draft
from cadrumo.application.filing.errors import ModeloApplicationError
from cadrumo.application.filing.export import export_draft, refuse_incomplete_xml_export
from cadrumo.application.filing.runtime import (
    ModeloOperatorProfile,
    RegistrySchemaAccessor,
    build_runtime_schema_provider,
)
from cadrumo.application.filing.tests.export_support import filer_with_nothing_else, m151_producer_snapshot
from cadrumo.core.aggregation import BindingAggregationOp
from cadrumo.core.modelo import Modelo
from cadrumo.core.period import Period
from cadrumo.core.prior_domiciliation_election import PriorDomiciliationElection
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.domain.calculations.registry.binding_aggregation import binding_aggregation_op
from cadrumo.domain.calculations.registry.binding_selector_utils import selector_as_dict
from cadrumo.domain.calculations.registry.binding_targets import revision_bindings_by_id
from cadrumo.domain.calculations.registry.bindings import resolve_available_bound_inputs_by_casilla_id
from cadrumo.domain.calculations.registry.export_xml_dictionary import XmlDictionaryEntry, xml_dictionary_entries
from cadrumo.domain.calculations.registry.tests.authored_editions import supported_authored_exercises
from cadrumo.domain.filing.errors import FilingExportCasillaValueRefusedError
from cadrumo.domain.filing.protocols import ModeloInputValue
from cadrumo.domain.filing.schema import ModeloDraft
from cadrumo.domain.submission.models import ModeloDraftStatus
from dev.registry.record_design_xsd_support import bundled_modelo_100_xsds, record_design_schema_violations

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_EDITION = re.compile(r"ejercicio-(\d{4})")
_XSD_BY_YEAR: dict[int, Path] = {
    int(match.group(1)): xsd for xsd in bundled_modelo_100_xsds() if (match := _EDITION.search(xsd.name))
}
_ACTIVITY_BLOCK = "DatosEconomicos/TomaDatosAmpliada/RegEstimaDirecta/ActividadEstDirecta"
_ACTIVITY_KEY_FIELD = "TACT"
_ACTIVITY_INCOME_FIELD = "E1INGRESO"
_RESULT_FIELD = "RESULTADO"
_IDENTITY: dict[str, object] = {
    "DPNIF_D": "12345678Z",
    "DP_APENOM_D": "DECLARANTE PRUEBA",
    "ECIVIL": "1",
    "DPFNAC_D": date(1975, 6, 15),
    "SEXO_D": "H",
    "ZCCAD": "madrid",
    "TIPOTRIBUTACION": "1",
}


def _provider(operation: PinnedAuthorityOperation, year: int) -> RegistrySchemaAccessor | None:
    """Return the edition's provider; an edition outside the supported span must refuse to give one."""
    if operation.supported_filing_years().admits_coordinate(year):
        return _open_provider(operation, year)
    with pytest.raises(ModeloApplicationError) as refused:
        _open_provider(operation, year)
    assert str(refused.value.translated_message).endswith("registry_empty_for_period")
    return None


def _open_provider(operation: PinnedAuthorityOperation, year: int) -> RegistrySchemaAccessor:
    return build_runtime_schema_provider(
        filing_year=year,
        period=Period.from_year_and_code(year, "0A"),
        modelos=("100",),
        operation=operation,
    )


def _row(provider: RegistrySchemaAccessor, field_id: str) -> XmlDictionaryEntry:
    entries = xml_dictionary_entries(
        provider.get_snapshot("100").revision.export_layouts[0],
        sources=provider.sources,
        source_payloads=provider.source_payloads,
        casillas=provider.get_snapshot("100").revision.casillas,
    )
    return next(entry for entry in entries if entry.field_id == field_id)


def _draft(
    provider: RegistrySchemaAccessor,
    year: int,
    inputs: dict[str, ModeloInputValue],
    facts: dict[str, ModeloInputValue] | None = None,
) -> ModeloDraft:
    stated = {**filer_with_nothing_else(provider), **(facts or {})}
    amounts = {key: value for key, value in stated.items() if isinstance(value, Decimal)}
    bound = resolve_available_bound_inputs_by_casilla_id(provider.get_snapshot("100").revision, amounts)
    return build_draft(
        modelo="100",
        period=Period.from_year_and_code(year, "0A"),
        profile=ModeloOperatorProfile(tax_id="12345678Z", display_name="DECLARANTE PRUEBA"),
        inputs={**bound, **stated, **inputs},
        schema_provider=provider,
    ).model_copy(update={"status": ModeloDraftStatus.APROBADO})


def _value(draft: ModeloDraft, entry: XmlDictionaryEntry) -> object:
    return next((value.value for value in draft.values if value.casilla_id == entry.casilla_id), None)


def _render(provider: RegistrySchemaAccessor, draft: ModeloDraft, folder: Path) -> bytes:
    stated = {_row(provider, _ACTIVITY_INCOME_FIELD).casilla_id: Decimal("1000.00")}
    result = _row(provider, _RESULT_FIELD)
    # The result is required and an edition's bare draft may leave it unresolved; stating it
    # here keeps this test on the rest of the document.
    if _value(draft, result) is None:
        stated[result.casilla_id] = Decimal("0.00")
    values = tuple(
        value.model_copy(update={"value": stated[value.casilla_id]}) if value.casilla_id in stated else value
        for value in draft.values
    )
    output = folder / "modelo-100.xml"
    export_draft(
        draft.model_copy(update={"values": values}),
        output_path=output,
        producer_snapshot=m151_producer_snapshot().model_copy(update={"modelo": Modelo("100")}),
        dictionary_values=_IDENTITY,
        prior_domiciliation_election=PriorDomiciliationElection.KEEP,
        product_software_identity=None,
        schema_provider=provider,
    )
    return output.read_bytes()


def _activity_key_inputs(provider: RegistrySchemaAccessor, *, key: str | None) -> dict[str, ModeloInputValue]:
    return {} if key is None else {str(_row(provider, _ACTIVITY_KEY_FIELD).casilla_id): key}


@pytest.mark.parametrize("year", sorted(_XSD_BY_YEAR))
def test_a_declaration_holding_its_required_facts_is_valid_and_planting_a_fault_fails(
    operation: PinnedAuthorityOperation, year: int, tmp_path: Path
) -> None:
    provider = _provider(operation, year)
    if provider is None:
        return
    payload = _render(provider, _draft(provider, year, _activity_key_inputs(provider, key="A05")), tmp_path)

    assert record_design_schema_violations(payload, xsd=_XSD_BY_YEAR[year]) == ()

    document = etree.fromstring(payload)
    block = document.find(_ACTIVITY_BLOCK)
    assert block is not None
    key = block.find(_ACTIVITY_KEY_FIELD)
    assert key is not None
    block.remove(key)
    planted = record_design_schema_violations(etree.tostring(document), xsd=_XSD_BY_YEAR[year])
    assert len(planted) == 1, planted
    assert _ACTIVITY_KEY_FIELD in planted[0]


@pytest.mark.parametrize("year", sorted(_XSD_BY_YEAR))
def test_activity_figures_without_the_activity_key_refuse_by_that_box(
    operation: PinnedAuthorityOperation, year: int, tmp_path: Path
) -> None:
    provider = _provider(operation, year)
    if provider is None:
        return
    draft = _draft(provider, year, _activity_key_inputs(provider, key=None))
    payload = _render(provider, draft, tmp_path)

    assert record_design_schema_violations(payload, xsd=_XSD_BY_YEAR[year]) != ()
    with pytest.raises(ModeloApplicationError) as refused:
        refuse_incomplete_xml_export(
            provider.get_snapshot("100").revision.export_layouts[0],
            draft=draft,
            payload=payload,
            schema_provider=provider,
        )

    assert str(refused.value.translated_message).endswith("xml_value_required_missing")
    assert (refused.value.context or {})["box"] == str(_row(provider, _ACTIVITY_KEY_FIELD).casilla_id)


_COMPENSATION_BLOCK = "DatosEconomicos/Resultados/BaseLiquidableRes"
# Editions whose applied compensation the base liquidable general feeds, from the registry's support floor up.
_COMPENSATING_EDITIONS = tuple(year for year in sorted(_XSD_BY_YEAR) if year in supported_authored_exercises("100"))


@pytest.mark.parametrize("year", _COMPENSATING_EDITIONS)
def test_the_base_liquidable_general_is_exported_before_the_compensation_of_earlier_negative_bases(
    operation: PinnedAuthorityOperation, year: int, tmp_path: Path
) -> None:
    """BLGRAL carries 0500 before JCOMPE is applied and BLGGRAV carries what is left.

    The design orders BLGRAL, JCOMPE and BLGGRAV and defines JCOMPE as the
    compensation applied "si la casilla [0500] es positiva", so the exported base
    liquidable general does not already hold the compensation.
    """
    provider = _provider(operation, year)
    if provider is None:
        return
    pending = Decimal("1000.00")
    inputs: dict[str, ModeloInputValue] = {
        **_activity_key_inputs(provider, key="A05"),
        "0003": Decimal("20000.00"),
        str(_row(provider, "C3BLAEM1").casilla_id): pending,
        # The schema's tipo_Titular: 2 is DECLARANTE, the holder of the pending base.
        str(_row(provider, "C3BLT").casilla_id): "2",
    }
    # Last year's own negative base opens this year's previous-year row.
    draft = _draft(provider, year, inputs, {"renta-base-liquidable-negativa-general-anterior": pending})
    values = {value.casilla_id: value.value for value in draft.values}
    # Art. 50.1: the base imponible general less the joint and previsión social reductions.
    base = Decimal(str(values["0435"])) - Decimal(str(values["0461"])) - Decimal(str(values["0468"]))
    assert base > pending
    assert values["1388"] == pending

    payload = _render(provider, draft, tmp_path)

    assert record_design_schema_violations(payload, xsd=_XSD_BY_YEAR[year]) == ()
    block = etree.fromstring(payload).find(_COMPENSATION_BLOCK)
    assert block is not None
    assert Decimal(block.findtext("BLGRAL") or "") == base
    assert Decimal(block.findtext("JCOMPE") or "") == pending
    assert Decimal(block.findtext("BLGGRAV") or "") == base - pending
    order = [child.tag for child in block]
    assert order.index("BLGRAL") < order.index("JCOMPE") < order.index("BLGGRAV")


def _activity_row_columns(provider: RegistrySchemaAccessor) -> tuple[tuple[str, XmlDictionaryEntry], ...]:
    """Each row binding of the edition whose column sits in the activity block, with that column's row."""
    entries = xml_dictionary_entries(
        provider.get_snapshot("100").revision.export_layouts[0],
        sources=provider.sources,
        source_payloads=provider.source_payloads,
        casillas=provider.get_snapshot("100").revision.casillas,
    )
    columns: list[tuple[str, XmlDictionaryEntry]] = []
    for binding_id, binding in sorted(revision_bindings_by_id(provider.get_snapshot("100").revision).items()):
        target = selector_as_dict(binding).get("target_casilla_id")
        if binding_aggregation_op(binding) is not BindingAggregationOp.ROWS or target is None:
            continue
        columns.extend(
            (binding_id, entry)
            for entry in entries
            if entry.casilla_id == target and entry.path.startswith(f"/{_ACTIVITY_BLOCK}/")
        )
    return tuple(columns)


def _editions_with_activity_rows(
    operation: PinnedAuthorityOperation,
) -> tuple[tuple[int, RegistrySchemaAccessor, str, XmlDictionaryEntry], ...]:
    editions = tuple(
        (year, provider, *columns[0])
        for year in sorted(_XSD_BY_YEAR)
        if operation.supported_filing_years().admits_coordinate(year)
        and (columns := _activity_row_columns(provider := _open_provider(operation, year)))
    )
    # The first edition with a per-activity row book must reach these tests, or they prove nothing.
    assert editions
    return editions


def _rows_draft(provider: RegistrySchemaAccessor, year: int, binding_id: str, rows: dict[str, str]) -> ModeloDraft:
    return _draft(provider, year, {**_activity_key_inputs(provider, key="A05"), binding_id: rows})


def test_the_activity_key_goes_into_the_one_activity_the_row_book_opens(
    operation: PinnedAuthorityOperation, tmp_path: Path
) -> None:
    """A box held for the whole activity block fills its only occurrence, beside the row the book states."""
    for year, provider, binding_id, column in _editions_with_activity_rows(operation):
        folder = tmp_path / str(year)
        folder.mkdir()

        payload = _render(provider, _rows_draft(provider, year, binding_id, {"1": "125.00"}), folder)

        assert record_design_schema_violations(payload, xsd=_XSD_BY_YEAR[year]) == ()
        blocks = etree.fromstring(payload).findall(_ACTIVITY_BLOCK)
        assert len(blocks) == 1
        assert blocks[0].findtext(_ACTIVITY_KEY_FIELD) == "A05"
        assert Decimal(blocks[0].findtext(column.path.removeprefix(f"/{_ACTIVITY_BLOCK}/")) or "") == Decimal("125.00")


def test_a_box_for_the_whole_block_refuses_when_the_row_book_opens_two_activities(
    operation: PinnedAuthorityOperation, tmp_path: Path
) -> None:
    """With two occurrences the activity key could describe either, so neither is chosen."""
    for year, provider, binding_id, _ in _editions_with_activity_rows(operation):
        folder = tmp_path / str(year)
        folder.mkdir()
        draft = _rows_draft(provider, year, binding_id, {"1": "125.00", "2": "75.00"})

        with pytest.raises(FilingExportCasillaValueRefusedError) as refused:
            _render(provider, draft, folder)

        assert refused.value.casilla_id == _row(provider, _ACTIVITY_KEY_FIELD).casilla_id
        assert (refused.value.context or {}).get("value") == "A05"


def test_a_box_whose_activity_already_states_another_value_refuses(
    operation: PinnedAuthorityOperation, tmp_path: Path
) -> None:
    """The one occurrence states the column, so a different box value for it is never written over the row."""
    for year, provider, binding_id, column in _editions_with_activity_rows(operation):
        folder = tmp_path / str(year)
        folder.mkdir()
        draft = _rows_draft(provider, year, binding_id, {"1": "125.00"})
        values = tuple(
            value.model_copy(update={"value": Decimal("130.00")}) if value.casilla_id == column.casilla_id else value
            for value in draft.values
        )
        assert any(value.casilla_id == column.casilla_id for value in values)

        with pytest.raises(FilingExportCasillaValueRefusedError) as refused:
            _render(provider, draft.model_copy(update={"values": values}), folder)

        assert refused.value.casilla_id == column.casilla_id
        assert (refused.value.context or {}).get("value") == "130.00"
