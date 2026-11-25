"""The exported return states its settlement result in IngresoDevolucionRes/RESINGDEV in every supported ejercicio.

The element is read from the XML the export writes for a draft that carries only the
settlement and filer boxes. Each expected amount is derived from the dictionary label "Resultado a
ingresar o a devolver (casilla [0670] o casilla [0695])" and the draft's own boxes
0670 and 0693, never through the settlement-result role the registry resolves to
the element itself. Years come from the registry envelope.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from pathlib import Path
from xml.etree.ElementTree import Element

import pytest
from defusedxml import ElementTree as DefusedElementTree

from ....core.casilla_id import CasillaId, validated_casilla_id
from ....core.export_layout_format import ExportLayoutFormat
from ....core.modelo import Modelo
from ....core.payment_instalment_election import PaymentInstalmentElection
from ....core.period import Period
from ....core.prior_domiciliation_election import PriorDomiciliationElection
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.bindings import resolve_available_bound_inputs_by_casilla_id
from ....domain.calculations.registry.errors import RegistryValidationError
from ....domain.calculations.registry.export_parse import parse_export_payload
from ....domain.calculations.registry.export_xml_dictionary import XmlDictionaryEntry
from ....domain.calculations.registry.payment_instalment_split import first_instalment_share
from ....domain.calculations.registry.result_casillas import derive_result_disposition
from ....domain.calculations.registry.tests.authored_editions import (
    filing_year_envelope,
    supported_authored_exercises,
)
from ....domain.deadlines.models import RefundAccount
from ....domain.filing.protocols import ModeloInputValue
from ....domain.filing.schema import ModeloDraft
from ....domain.submission.models import ModeloDraftStatus
from ...filing.draft_construction import build_draft
from ...filing.export import export_draft
from ...filing.export_xml_dictionary_rows import xml_dictionary_layout_casillas, xml_dictionary_layout_entries
from ...filing.runtime import ModeloOperatorProfile, RegistrySchemaAccessor, build_runtime_schema_provider
from ...filing.tests.export_support import filer_with_nothing_else, m151_producer_snapshot
from ..export_settlement import declared_settlement, settlement_dictionary_values

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_SALARY = "0003"
_RESULT: CasillaId = validated_casilla_id("0670")
_SUSPENDED = "0693"
_WAIVED = "0694"
_REMAINDER: CasillaId = validated_casilla_id("0695")
_WITHHELD = "renta-retencion-soportada-trabajo"
_RESULT_ELEMENT = "RESINGDEV"
_REMAINDER_ELEMENTS = ("TCPP112", "TCNN112")
_REFUND_IBAN = "ES9121000418450200051332"
_SUSPENDED_AMOUNT = Decimal("200.00")


def _provider(operation: PinnedAuthorityOperation, year: int) -> RegistrySchemaAccessor:
    return build_runtime_schema_provider(
        filing_year=year, period=Period.from_year_and_code(year, "0A"), modelos=("100",), operation=operation
    )


def _draft(provider: RegistrySchemaAccessor, year: int, inputs: Mapping[str, ModeloInputValue]) -> ModeloDraft:
    stated = filer_with_nothing_else(provider)
    stated |= {_SALARY: Decimal("30000.00"), **inputs}
    amounts = {key: value for key, value in stated.items() if isinstance(value, Decimal)}
    bound = resolve_available_bound_inputs_by_casilla_id(provider.get_snapshot("100").revision, amounts)
    return build_draft(
        modelo="100",
        period=Period.from_year_and_code(year, "0A"),
        profile=ModeloOperatorProfile(tax_id="12345678Z", display_name="DECLARANTE PRUEBA"),
        inputs={**bound, **stated},
        schema_provider=provider,
    ).model_copy(update={"status": ModeloDraftStatus.APROBADO})


def _money(draft: ModeloDraft, casilla_id: CasillaId) -> Decimal:
    value = {item.casilla_id: item.value for item in draft.values}[casilla_id]
    assert isinstance(value, Decimal)
    return value


def _settlement(operation: PinnedAuthorityOperation, provider: RegistrySchemaAccessor, year: int, draft: ModeloDraft):
    period = Period.from_year_and_code(year, "0A")
    values = {item.casilla_id: item.value for item in draft.values}
    disposition = derive_result_disposition("100", {_RESULT: _money(draft, _RESULT)}, period=period)
    return settlement_dictionary_values(
        disposition=disposition,
        settlement=declared_settlement("100", provider.get_snapshot("100").revision, values, disposition=disposition),
        instalment=PaymentInstalmentElection.SINGLE,
        first_instalment_share=first_instalment_share("100", period_day=period.end_date, authority=operation),
        charge_account=None,
        refund_account=RefundAccount(iban=_REFUND_IBAN),
    )


def _exported_elements(
    operation: PinnedAuthorityOperation, provider: RegistrySchemaAccessor, year: int, draft: ModeloDraft, path: Path
) -> dict[str, str]:
    export_draft(
        draft,
        output_path=path,
        producer_snapshot=m151_producer_snapshot().model_copy(update={"modelo": Modelo("100")}),
        dictionary_values=_settlement(operation, provider, year, draft),
        prior_domiciliation_election=PriorDomiciliationElection.KEEP,
        product_software_identity=None,
        schema_provider=provider,
    )
    root = DefusedElementTree.fromstring(path.read_bytes())
    return {
        element.tag.rsplit("}", 1)[-1]: element.text
        for element in root.iter()
        if len(element) == 0 and element.text is not None
    }


def _expected_result(draft: ModeloDraft, suspended: Decimal) -> Decimal:
    """The dictionary label's rule over the draft's own boxes: the result 0670, less any suspended part 0693."""
    return _money(draft, _RESULT) - suspended


def _result_element(elements: Mapping[str, str]) -> Decimal:
    assert _RESULT_ELEMENT in elements, "the exported return states no settlement result"
    return Decimal(elements[_RESULT_ELEMENT])


def test_every_supported_year_states_the_result_or_refuses_export_with_its_typed_cause(
    operation: PinnedAuthorityOperation, tmp_path: Path
) -> None:
    envelope = filing_year_envelope()
    authored = set(supported_authored_exercises("100"))
    assert envelope.floor in authored
    for year in envelope.years:
        if year not in authored:
            with pytest.raises(RegistryValidationError, match="reaches 'calculation' authority at most"):
                _provider(operation, year)
            continue
        provider = _provider(operation, year)

        refund = _draft(provider, year, {_WITHHELD: Decimal("20000.00")})
        refund_elements = _exported_elements(operation, provider, year, refund, tmp_path / f"refund-{year}.xml")
        assert _money(refund, _RESULT) < 0, year
        assert _result_element(refund_elements) == _expected_result(refund, Decimal(0)), year
        assert not any(name in refund_elements for name in _REMAINDER_ELEMENTS), year

        payable = _draft(provider, year, {})
        payable_elements = _exported_elements(operation, provider, year, payable, tmp_path / f"payable-{year}.xml")
        assert _money(payable, _RESULT) > 0, year
        assert _result_element(payable_elements) == _expected_result(payable, Decimal(0)), year

        suspended = _draft(provider, year, {_SUSPENDED: _SUSPENDED_AMOUNT})
        suspended_elements = _exported_elements(
            operation, provider, year, suspended, tmp_path / f"suspended-{year}.xml"
        )
        expected = _expected_result(suspended, _SUSPENDED_AMOUNT)
        assert expected > 0 and expected != _money(suspended, _RESULT), year
        assert _result_element(suspended_elements) == expected, year
        # The remainder to pay still reads casilla 0695, which RESINGDEV no longer shares.
        assert Decimal(suspended_elements["TCPP112"]) == _money(suspended, _REMAINDER) == expected, year


def test_a_waived_refund_stays_a_typed_unresolved_outcome_in_every_supported_year(
    operation: PinnedAuthorityOperation,
) -> None:
    for year in supported_authored_exercises("100"):
        provider = _provider(operation, year)
        draft = _draft(provider, year, {_WITHHELD: Decimal("20000.00"), _WAIVED: Decimal("100.00")})
        values = {item.casilla_id: item.value for item in draft.values}

        assert _money(draft, _RESULT) < 0, year
        assert values.get("RESINGDEV") is None, year


def _element_paths(payload: bytes, tag: str) -> list[str]:
    """Every path, below the document root and without namespaces, at which ``tag`` is written."""
    root = DefusedElementTree.fromstring(payload)
    found: list[str] = []

    def walk(element: Element, prefix: str) -> None:
        for child in element:
            name = child.tag.rsplit("}", 1)[-1]
            path = f"{prefix}/{name}"
            if name == tag:
                found.append(path)
            walk(child, path)

    walk(root, "")
    return found


def test_the_result_row_is_written_once_at_its_dictionary_path_and_the_remainder_box_keeps_its_own_value(
    operation: PinnedAuthorityOperation, tmp_path: Path
) -> None:
    """Read each export back through the registry parser, in every supported year.

    Where the dictionary prints the result row under the number of the remainder box
    0695, the remainder box must not reach the result element: a refund leaves 0695 at
    zero while the result is negative, so a misrouted row would show as a second value.
    """
    shared_years: list[int] = []
    for year in supported_authored_exercises("100"):
        provider = _provider(operation, year)
        layout = next(
            item
            for item in provider.get_snapshot("100").revision.export_layouts
            if item.format is ExportLayoutFormat.XML_DICTIONARY
        )
        entries = xml_dictionary_layout_entries(layout, schema_provider=provider)
        result_rows: list[XmlDictionaryEntry] = [entry for entry in entries if entry.field_id == _RESULT_ELEMENT]
        assert len(result_rows) == 1, year
        result_row = result_rows[0]
        remainder_rows = [entry for entry in entries if entry.casilla_id == _REMAINDER]
        assert result_row.casilla_id != _REMAINDER, year
        if result_row.printed_number in {entry.printed_number for entry in remainder_rows}:
            shared_years.append(year)

        refund = _draft(provider, year, {_WITHHELD: Decimal("20000.00")})
        path = tmp_path / f"readback-{year}.xml"
        _exported_elements(operation, provider, year, refund, path)
        payload = path.read_bytes()

        assert _element_paths(payload, _RESULT_ELEMENT) == [result_row.path], year
        parsed = parse_export_payload(
            layout,
            payload,
            sources=provider.sources,
            source_payloads=provider.source_payloads,
            casillas=xml_dictionary_layout_casillas(layout, schema_provider=provider),
        )
        result_fields = [field for field in parsed.fields if field.field_id == _RESULT_ELEMENT]
        assert len(result_fields) == 1, year
        assert result_fields[0].casilla_id == result_row.casilla_id, year
        assert result_fields[0].value == _expected_result(refund, Decimal(0)), year
        assert result_fields[0].value != _money(refund, _REMAINDER), year
        for field in parsed.fields:
            if field.casilla_id == _REMAINDER:
                assert field.value == _money(refund, _REMAINDER), (year, field.field_id)
    assert shared_years, "no supported edition prints the result row under the remainder box's number"
