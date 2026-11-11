"""A Modelo 100 XML export holds every value to the limits AEAT's own XSD declares.

Expected limits are read here from the bundled XSD file with a reader of this module's
own, so a limit this test asserts never comes from the code under test. Each kind of
limit is taken to its exact boundary through the real renderer: the last value the XSD
admits renders and the first it does not is refused, naming the box.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from decimal import Decimal
from functools import cache
from pathlib import Path
from xml.etree.ElementTree import Element

import pytest
from defusedxml import ElementTree as DefusedElementTree

from ....core.errors.error_codes import render_error_text, resolve_error_message
from ....core.modelo import Modelo
from ....core.period import Period
from ....core.prior_domiciliation_election import PriorDomiciliationElection
from ....core.resources.bundled_data import bundled_path
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.bindings import resolve_available_bound_inputs_by_casilla_id
from ....domain.calculations.registry.export_xml_dictionary import XmlDictionaryEntry, xml_dictionary_entries
from ....domain.calculations.registry.tests.authored_editions import (
    newest_authored_edition,
    supported_authored_exercises,
)
from ....domain.calculations.registry.tests.published_authority import published_source_reference
from ....domain.filing.protocols import ModeloInputValue
from ....domain.filing.schema import ModeloDraft
from ....domain.submission.models import ModeloDraftStatus
from ..draft_construction import build_draft
from ..errors import ModeloApplicationError
from ..export import export_draft
from ..export_verification import DeclaracionVerifyVerdict, verify_export
from ..export_xml_dictionary import render_xml_dictionary_layout
from ..export_xml_dictionary_modelo100 import modelo_100_unfiled_comunidad_paths, registry_modelo_100_xml_declarations
from ..export_xml_value_limits import canonical_xml_text, refuse_xml_values_outside_schema, xml_value_schema
from ..runtime import ModeloOperatorProfile, RegistrySchemaAccessor, build_runtime_schema_provider
from .export_support import filer_with_nothing_else, m151_producer_snapshot

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_XSD = "{http://www.w3.org/2001/XMLSchema}"
_YEAR = newest_authored_edition("100")


@cache
def _bundled_xsd(year: int = _YEAR) -> Element[str]:
    # The schema is the official design file the registry publishes for the exercise; its facets are the oracle.
    source = published_source_reference(f"aeat-dr-100-{year}-xsd")
    root = DefusedElementTree.parse(Path(bundled_path() / source.corpus_path)).getroot()
    assert root is not None
    return root


def _facet(type_name: str, facet: str) -> str:
    """Read one facet of one named type straight from the bundled XSD."""
    for simple_type in _bundled_xsd().iter(f"{_XSD}simpleType"):
        if simple_type.get("name") == type_name:
            node = simple_type.find(f"{_XSD}restriction/{_XSD}{facet}")
            assert node is not None, f"{type_name} declares no {facet}"
            return str(node.get("value"))
    pytest.fail(f"the bundled XSD declares no type {type_name}")


@cache
def _types_by_path(year: int = _YEAR) -> dict[str, str]:
    """Map every path the bundled XSD declares to its type name; a complex path maps to ``""``."""
    schema = _bundled_xsd(year)
    complex_types = {name: node for node in schema.iter(f"{_XSD}complexType") if (name := node.get("name")) is not None}
    found: dict[str, str] = {}

    def walk(node: Element[str], path: str, open_types: frozenset[str]) -> None:
        for child in node:
            local = str(child.tag).removeprefix(_XSD)
            if local in {"sequence", "choice", "all", "complexType"}:
                walk(child, path, open_types)
            elif local in {"element", "attribute"}:
                name = child.get("name")
                prefix = "@" if local == "attribute" else ""
                child_path = f"{path}/{prefix}{name}"
                declared = child.get("type")
                if declared in complex_types:
                    found[child_path] = ""
                    if declared not in open_types:
                        walk(complex_types[declared], child_path, open_types | {str(declared)})
                elif declared is not None:
                    found[child_path] = declared
                else:
                    found[child_path] = ""
                    walk(child, child_path, open_types)

    root = next(node for node in schema if node.tag == f"{_XSD}element")
    walk(root, "", frozenset())
    return found


def _provider(operation: PinnedAuthorityOperation, year: int = _YEAR) -> RegistrySchemaAccessor:
    return build_runtime_schema_provider(
        filing_year=year,
        period=Period.from_year_and_code(year, "0A"),
        modelos=("100",),
        operation=operation,
    )


def _entries(provider: RegistrySchemaAccessor) -> tuple[XmlDictionaryEntry, ...]:
    return xml_dictionary_entries(
        provider.get_snapshot("100").revision.export_layouts[0],
        sources=provider.sources,
        source_payloads=provider.source_payloads,
    )


def _plain_path(entry: XmlDictionaryEntry) -> str:
    return "/" + entry.path.strip("/").removeprefix("Declaracion/")


def _row(provider: RegistrySchemaAccessor, *, xsd_type: str) -> XmlDictionaryEntry:
    """Find a row on ``xsd_type`` outside the comunidad branches this draft does not file."""
    types = _types_by_path()
    entries = _entries(provider)
    unfiled = modelo_100_unfiled_comunidad_paths(
        entries,
        {value.casilla_id: value.value for value in _draft(provider).values},
        declarations=registry_modelo_100_xml_declarations(),
    )
    for entry in entries:
        if types.get(_plain_path(entry)) == xsd_type and entry.path not in unfiled:
            return entry
    pytest.fail(f"no row of the {_YEAR} dictionary lands on {xsd_type}")


def _named_row(provider: RegistrySchemaAccessor, field_id: str) -> XmlDictionaryEntry:
    return next(entry for entry in _entries(provider) if entry.field_id == field_id)


def _build_draft(provider: RegistrySchemaAccessor, inputs: Mapping[str, ModeloInputValue]) -> ModeloDraft:
    stated = filer_with_nothing_else(provider)
    amounts = {key: value for key, value in stated.items() if isinstance(value, Decimal)}
    bound = resolve_available_bound_inputs_by_casilla_id(provider.get_snapshot("100").revision, amounts)
    return build_draft(
        modelo="100",
        period=Period.from_year_and_code(_YEAR, "0A"),
        profile=ModeloOperatorProfile(tax_id="12345678Z", display_name="DECLARANTE PRUEBA"),
        inputs={**bound, **stated, **inputs},
        schema_provider=provider,
    ).model_copy(update={"status": ModeloDraftStatus.APROBADO})


_ZERO_DRAFT: list[ModeloDraft] = []


def _draft(provider: RegistrySchemaAccessor, inputs: Mapping[str, ModeloInputValue] | None = None) -> ModeloDraft:
    """Build the draft; the one holding no stated value is costly and immutable, so it is built once."""
    if inputs is not None:
        return _build_draft(provider, inputs)
    if not _ZERO_DRAFT:
        _ZERO_DRAFT.append(_build_draft(provider, {}))
    return _ZERO_DRAFT[0]


def _render_row(provider: RegistrySchemaAccessor, entry: XmlDictionaryEntry, value: object) -> bytes:
    """Render with this row's value as the only one it can take: a box's own value outranks a dictionary value."""
    draft = _draft(provider)
    return render_xml_dictionary_layout(
        provider.get_snapshot("100").revision.export_layouts[0],
        draft=draft.model_copy(update={"values": tuple(v for v in draft.values if v.casilla_id != entry.casilla_id)}),
        headers={},
        aux_version="001",
        dictionary_values={entry.field_id: value},
        schema_provider=provider,
    )


def _written(payload: bytes, entry: XmlDictionaryEntry) -> str | None:
    parts = _plain_path(entry).strip("/").split("/")
    node: Element[str] | None = DefusedElementTree.fromstring(payload)
    for part in parts:
        if node is None:
            return None
        if part.startswith("@"):
            return node.get(part[1:])
        node = node.find(part)
    return None if node is None else node.text


def _refused(provider: RegistrySchemaAccessor, entry: XmlDictionaryEntry, value: object) -> ModeloApplicationError:
    with pytest.raises(ModeloApplicationError) as refused:
        _render_row(provider, entry, value)
    return refused.value


def _message(error: ModeloApplicationError) -> str:
    return str(error.translated_message).rpartition(".")[2]


def _box(entry: XmlDictionaryEntry) -> str:
    return str(entry.casilla_id) if entry.casilla_id is not None else entry.field_id


@pytest.mark.parametrize(
    ("field_id", "xsd_type"),
    [
        ("C1ICRC", "tipo_ReferenciaCatastral"),
        ("IDENTCCVH1", "tipo_Iban"),
        ("C2NOMAFEAC", None),
        ("G4ATIPO", None),
    ],
)
def test_a_maximum_length_admits_its_limit_and_refuses_one_more(
    operation: PinnedAuthorityOperation, field_id: str, xsd_type: str | None
) -> None:
    provider = _provider(operation)
    entry = _named_row(provider, field_id)
    declared = xsd_type or _types_by_path()[_plain_path(entry)]
    limit = int(_facet(declared, "maxLength"))
    at_limit = _fitting_text(declared, limit)

    assert _written(_render_row(provider, entry, at_limit), entry) == at_limit

    error = _refused(provider, entry, at_limit + at_limit[0])
    assert _message(error) == "xml_value_too_long"
    assert error.context == {"box": _box(entry), "field_id": field_id, "limit": str(limit), "observed": limit + 1}


def _fitting_text(type_name: str, length: int) -> str:
    """Build a text of ``length`` that the type's own pattern accepts, whatever alphabet it admits."""
    candidate = "1" * length
    if re.fullmatch(_facet(type_name, "pattern"), candidate) is not None:
        return candidate
    candidate = "A" * length
    assert re.fullmatch(_facet(type_name, "pattern"), candidate) is not None
    return candidate


def test_an_exact_length_refuses_one_less_and_one_more(operation: PinnedAuthorityOperation) -> None:
    provider = _provider(operation)
    entry = _named_row(provider, "GFCNIF1")
    required = int(_facet("tipo_Nif", "length"))
    exact = "1" * (required - 1) + "Z"

    assert _written(_render_row(provider, entry, exact), entry) == exact

    for wrong in (exact[1:], "1" + exact):
        error = _refused(provider, entry, wrong)
        assert _message(error) == "xml_value_wrong_length"
        assert error.context == {
            "box": _box(entry),
            "field_id": "GFCNIF1",
            "limit": str(required),
            "observed": len(wrong),
        }


def test_a_comunidad_row_is_held_to_its_limit_only_on_the_comunidad_filed(operation: PinnedAuthorityOperation) -> None:
    """A row of a comunidad this return does not file never reaches the file, so it cannot breach it."""
    provider = _provider(operation)
    entry = _named_row(provider, "CCCAND1")
    limit = int(_facet(_types_by_path()[_plain_path(entry)], "maxLength"))
    layout = provider.get_snapshot("100").revision.export_layouts[0]

    def render(value: str) -> bytes:
        return render_xml_dictionary_layout(
            layout,
            draft=_draft(provider, {str(entry.casilla_id): value}),
            headers={},
            aux_version="001",
            schema_provider=provider,
        )

    assert _written(render("1" * limit), entry) == "1" * limit
    with pytest.raises(ModeloApplicationError) as refused:
        render("1" * (limit + 1))
    assert _message(refused.value) == "xml_value_too_long"
    assert _written(_render_row(provider, entry, "1" * (limit + 1)), entry) is None


def test_a_taxpayer_name_is_held_to_its_limit(operation: PinnedAuthorityOperation) -> None:
    """A row no casilla addresses is named by AEAT's field id."""
    provider = _provider(operation)
    entry = _named_row(provider, "DP_APENOM_D")
    assert entry.casilla_id is None
    declared = _types_by_path()[_plain_path(entry)]
    limit = int(_facet(declared, "maxLength"))

    assert _written(_render_row(provider, entry, "A" * limit), entry) == "A" * limit

    error = _refused(provider, entry, "A" * (limit + 1))
    assert _message(error) == "xml_value_too_long"
    assert error.context is not None
    assert error.context["box"] == "DP_APENOM_D"


@pytest.mark.parametrize("xsd_type", ["tipo_ImpPositivo", "tipo_ImpNegativo", "tipo_Integer1a365", "tipo_Decimal012"])
def test_a_maximum_admits_its_limit_and_refuses_the_next_value(
    operation: PinnedAuthorityOperation, xsd_type: str
) -> None:
    provider = _provider(operation)
    entry = _row(provider, xsd_type=xsd_type)
    limit = Decimal(_facet(xsd_type, "maxInclusive"))
    step = Decimal(1) if limit == limit.to_integral_value() and "." not in str(limit) else Decimal("0.01")

    assert Decimal(str(_written(_render_row(provider, entry, limit), entry))) == limit

    error = _refused(provider, entry, limit + step)
    assert _message(error) == "xml_value_above_maximum"
    assert error.context is not None
    assert error.context["limit"] == _facet(xsd_type, "maxInclusive")
    assert error.context["box"] == _box(entry)


@pytest.mark.parametrize("xsd_type", ["tipo_ImpNegativo", "tipo_Integer1a365"])
def test_a_minimum_admits_its_limit_and_refuses_the_next_value(
    operation: PinnedAuthorityOperation, xsd_type: str
) -> None:
    provider = _provider(operation)
    entry = _row(provider, xsd_type=xsd_type)
    limit = Decimal(_facet(xsd_type, "minInclusive"))
    step = Decimal(1) if "." not in str(limit) else Decimal("0.01")

    assert Decimal(str(_written(_render_row(provider, entry, limit), entry))) == limit

    # Below a minimum of one the next value is zero, which an optional branch prunes.
    below = limit - step if limit - step != 0 else limit - 2 * step
    error = _refused(provider, entry, below)
    assert _message(error) == "xml_value_below_minimum"
    assert error.context is not None
    assert error.context["limit"] == _facet(xsd_type, "minInclusive")


def test_a_figure_beyond_decimal_working_precision_is_refused_by_its_box(operation: PinnedAuthorityOperation) -> None:
    """Rendering it used to raise a raw arithmetic error instead of a refusal."""
    provider = _provider(operation)
    entry = _row(provider, xsd_type="tipo_ImpPositivo")

    assert _message(_refused(provider, entry, Decimal("1E+40"))) == "xml_value_above_maximum"


def test_characters_outside_the_declared_pattern_are_refused(operation: PinnedAuthorityOperation) -> None:
    provider = _provider(operation)
    entry = _named_row(provider, "IDENTCCVH1")
    assert re.fullmatch(_facet("tipo_Iban", "pattern"), "ES12") is not None
    assert re.fullmatch(_facet("tipo_Iban", "pattern"), "ES-12") is None

    assert _written(_render_row(provider, entry, "ES12"), entry) == "ES12"
    assert _message(_refused(provider, entry, "ES-12")) == "xml_value_illegal_characters"


def test_ordinary_text_is_capitalized_where_the_type_admits_only_capitals(
    operation: PinnedAuthorityOperation, tmp_path: Path
) -> None:
    """A mixed-case, accented value exports through the real route and still verifies."""
    provider = _provider(operation)
    entry = _named_row(provider, "C1ICRC")
    typed = "calle ñu-5 José á"
    assert re.fullmatch(_facet("tipo_ReferenciaCatastral", "pattern"), typed) is None
    assert re.fullmatch(_facet("tipo_ReferenciaCatastral", "pattern"), typed.upper()) is not None
    draft = _draft(provider, {str(entry.casilla_id): typed})
    output_path = tmp_path / "text.xml"

    _export(provider, draft, output_path)

    assert _written(output_path.read_bytes(), entry) == typed.upper()
    assert verify_export(draft, file_path=output_path, schema_provider=provider).verdict is (
        DeclaracionVerifyVerdict.MATCH
    )


def test_a_value_capitals_cannot_make_valid_is_refused_unchanged(operation: PinnedAuthorityOperation) -> None:
    """Dropping or replacing a character would file text the taxpayer never stated."""
    provider = _provider(operation)
    entry = _named_row(provider, "C1ICRC")
    for typed in ("calle 5ª", "precio 5€"):
        assert re.fullmatch(_facet("tipo_ReferenciaCatastral", "pattern"), typed.upper()) is None
        assert _message(_refused(provider, entry, typed)) == "xml_value_illegal_characters"


def test_capitalizing_does_not_escape_the_length_limit(operation: PinnedAuthorityOperation) -> None:
    """A letter that grows when capitalized is measured as the file would hold it."""
    provider = _provider(operation)
    entry = _named_row(provider, "C1ICRC")
    limit = int(_facet("tipo_ReferenciaCatastral", "maxLength"))

    error = _refused(provider, entry, "ß" * limit)

    assert _message(error) == "xml_value_too_long"
    assert error.context is not None
    assert error.context["observed"] == 2 * limit


def test_a_taxpayer_name_is_capitalized_only_by_its_type(operation: PinnedAuthorityOperation) -> None:
    provider = _provider(operation)
    entry = _named_row(provider, "DP_APENOM_D")

    assert _written(_render_row(provider, entry, "Pérez Núñez, José"), entry) == "PÉREZ NÚÑEZ, JOSÉ"


def test_a_listed_code_typed_in_lowercase_takes_the_listed_form(operation: PinnedAuthorityOperation) -> None:
    provider = _provider(operation)
    entry = _row(provider, xsd_type="tipo_SINO_Exclusivo")

    assert _written(_render_row(provider, entry, "si"), entry) == "SI"


def test_a_file_from_elsewhere_in_lowercase_is_not_excused_by_normalization(
    operation: PinnedAuthorityOperation, tmp_path: Path
) -> None:
    """Capitalizing belongs to writing. What a file already holds is judged as it stands."""
    provider = _provider(operation)
    entry = _named_row(provider, "C1ICRC")
    typed = "CALLE MAYOR"
    draft = _draft(provider, {str(entry.casilla_id): typed})
    good = tmp_path / "good.xml"
    _export(provider, draft, good)
    held = tmp_path / "lower.xml"
    held.write_bytes(good.read_bytes().replace(typed.encode(), typed.lower().encode(), 1))

    with pytest.raises(ModeloApplicationError) as refused:
        verify_export(draft, file_path=held, schema_provider=provider)

    assert _message(refused.value) == "xml_value_illegal_characters"


def test_a_character_xml_cannot_carry_is_refused_by_its_box(operation: PinnedAuthorityOperation) -> None:
    provider = _provider(operation)
    entry = _named_row(provider, "IDENTCCVH1")

    error = _refused(provider, entry, "ES\x0112")

    assert _message(error) == "xml_value_illegal_characters"
    assert error.context is not None
    assert error.context["box"] == _box(entry)


def test_a_value_the_type_does_not_list_is_refused(operation: PinnedAuthorityOperation) -> None:
    provider = _provider(operation)
    entry = _row(provider, xsd_type="tipo_SINO_Exclusivo")
    listed = {
        node.get("value")
        for simple_type in _bundled_xsd().iter(f"{_XSD}simpleType")
        if simple_type.get("name") == "tipo_SINO_Exclusivo"
        for node in simple_type.iter(f"{_XSD}enumeration")
    }
    assert "SI" in listed
    assert "QUIZA" not in listed

    assert _written(_render_row(provider, entry, "SI"), entry) == "SI"
    assert _message(_refused(provider, entry, "QUIZA")) == "xml_value_not_listed"


def test_text_on_a_numeric_type_is_refused(operation: PinnedAuthorityOperation) -> None:
    """A year row is declared as dictionary text, so only the XSD knows it must be a number."""
    provider = _provider(operation)
    entry = _row(provider, xsd_type="tipo_Anno")
    first_year = _facet("tipo_Anno", "minInclusive")

    assert _written(_render_row(provider, entry, first_year), entry) == first_year
    assert _message(_refused(provider, entry, "ABCD")) == "xml_value_not_a_number"


def test_zero_placeholders_of_a_type_starting_at_one_do_not_reach_the_check(
    operation: PinnedAuthorityOperation,
) -> None:
    """A calculated zero on an optional branch is pruned, so it is not refused for a file that never holds it."""
    provider = _provider(operation)
    entry = _row(provider, xsd_type="tipo_Integer1a365")
    assert Decimal(_facet("tipo_Integer1a365", "minInclusive")) > 0

    assert _written(_render_row(provider, entry, Decimal("0")), entry) is None


def _export(provider: RegistrySchemaAccessor, draft: ModeloDraft, output_path: Path) -> None:
    export_draft(
        draft,
        output_path=output_path,
        producer_snapshot=m151_producer_snapshot().model_copy(update={"modelo": Modelo("100")}),
        prior_domiciliation_election=PriorDomiciliationElection.KEEP,
        product_software_identity=None,
        schema_provider=provider,
    )


def _overflow_casilla_inputs(provider: RegistrySchemaAccessor, length: int) -> dict[str, ModeloInputValue]:
    entry = _named_row(provider, "C1ICRC")
    return {str(entry.casilla_id): "1" * length}


def test_export_writes_nothing_for_a_draft_holding_an_overflow(
    operation: PinnedAuthorityOperation, tmp_path: Path
) -> None:
    provider = _provider(operation)
    limit = int(_facet("tipo_ReferenciaCatastral", "maxLength"))
    output_path = tmp_path / "modelo-100.xml"

    with pytest.raises(ModeloApplicationError) as refused:
        _export(provider, _draft(provider, _overflow_casilla_inputs(provider, limit + 1)), output_path)

    assert _message(refused.value) == "xml_value_too_long"
    assert refused.value.context is not None
    assert refused.value.context["box"] == str(_named_row(provider, "C1ICRC").casilla_id)
    assert not output_path.exists()


def _overflowing_file(provider: RegistrySchemaAccessor, tmp_path: Path) -> tuple[ModeloDraft, Path]:
    """Write a file stating exactly what its draft holds, one character past the XSD limit."""
    limit = int(_facet("tipo_ReferenciaCatastral", "maxLength"))
    good_path = tmp_path / "good.xml"
    _export(provider, _draft(provider, _overflow_casilla_inputs(provider, limit)), good_path)
    fitting = "1" * limit
    bad_path = tmp_path / "overflow.xml"
    bad_path.write_bytes(good_path.read_bytes().replace(fitting.encode(), (fitting + "1").encode(), 1))
    return _draft(provider, _overflow_casilla_inputs(provider, limit + 1)), bad_path


def test_verification_refuses_a_file_that_agrees_with_its_draft_but_not_with_the_schema(
    operation: PinnedAuthorityOperation, tmp_path: Path
) -> None:
    provider = _provider(operation)
    draft, bad_path = _overflowing_file(provider, tmp_path)

    with pytest.raises(ModeloApplicationError) as refused:
        verify_export(draft, file_path=bad_path, schema_provider=provider)

    assert _message(refused.value) == "xml_value_too_long"
    assert refused.value.context is not None
    assert refused.value.context["box"] == str(_named_row(provider, "C1ICRC").casilla_id)


def test_verification_still_matches_a_file_at_the_limit(operation: PinnedAuthorityOperation, tmp_path: Path) -> None:
    provider = _provider(operation)
    limit = int(_facet("tipo_ReferenciaCatastral", "maxLength"))
    draft = _draft(provider, _overflow_casilla_inputs(provider, limit))
    output_path = tmp_path / "good.xml"
    _export(provider, draft, output_path)

    assert verify_export(draft, file_path=output_path, schema_provider=provider).verdict is (
        DeclaracionVerifyVerdict.MATCH
    )


def test_verification_refuses_a_value_the_schema_has_no_place_for(
    operation: PinnedAuthorityOperation, tmp_path: Path
) -> None:
    provider = _provider(operation)
    draft = _draft(provider)
    good = tmp_path / "good.xml"
    _export(provider, draft, good)
    extended = tmp_path / "extended.xml"
    extended.write_bytes(good.read_bytes().replace(b"</Aux>", b"<NOT_DECLARED>1</NOT_DECLARED></Aux>", 1))

    with pytest.raises(ModeloApplicationError) as refused:
        verify_export(draft, file_path=extended, schema_provider=provider)

    assert _message(refused.value) == "xml_value_undeclared"


def test_verification_refuses_more_decimals_than_the_type_declares(
    operation: PinnedAuthorityOperation, tmp_path: Path
) -> None:
    """The renderer quantizes, so only a file from elsewhere can carry these digits."""
    provider = _provider(operation)
    entry = _row(provider, xsd_type="tipo_ImpPositivo")
    allowed = int(_facet("tipo_ImpPositivo", "fractionDigits"))
    good = "1." + "5" * allowed
    payload = _render_row(provider, entry, Decimal(good))
    assert _written(payload, entry) == good
    held = tmp_path / "decimals.xml"
    held.write_bytes(payload.replace(f">{good}<".encode(), f">{good}5<".encode(), 1))

    with pytest.raises(ModeloApplicationError) as refused:
        verify_export(_draft(provider), file_path=held, schema_provider=provider)

    assert _message(refused.value) == "xml_value_too_many_decimals"
    assert refused.value.context is not None
    assert refused.value.context["limit"] == str(allowed)
    assert refused.value.context["observed"] == allowed + 1
    # A trailing zero is not a digit of the value, so the next file is within the type.
    within = tmp_path / "within.xml"
    within.write_bytes(payload.replace(f">{good}<".encode(), f">{good}0<".encode(), 1))
    assert verify_export(_draft(provider), file_path=within, schema_provider=provider).file_sha256 is not None


def test_every_box_refused_is_listed(operation: PinnedAuthorityOperation) -> None:
    provider = _provider(operation)
    first, second = _named_row(provider, "IDENTCCVH1"), _named_row(provider, "C2NOMAFEAC")
    draft = _draft(provider)
    boxes = {first.casilla_id, second.casilla_id}
    with pytest.raises(ModeloApplicationError) as refused:
        render_xml_dictionary_layout(
            provider.get_snapshot("100").revision.export_layouts[0],
            draft=draft.model_copy(update={"values": tuple(v for v in draft.values if v.casilla_id not in boxes)}),
            headers={},
            aux_version="001",
            dictionary_values={first.field_id: "1" * 300, second.field_id: "1" * 300},
            schema_provider=provider,
        )

    assert refused.value.context is not None
    listed = str(refused.value.context["refused_boxes"]).split(", ")
    assert {_box(first), _box(second)} == set(listed)


@pytest.mark.parametrize("facet", ["totalDigits", "minLength", "minExclusive"])
def test_a_facet_this_check_cannot_apply_refuses_rather_than_passes(facet: str) -> None:
    schema = DefusedElementTree.fromstring(
        '<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">'
        '<xs:element name="Declaracion"><xs:complexType><xs:sequence>'
        '<xs:element name="Importe" type="tipo_Limitado"/>'
        "</xs:sequence></xs:complexType></xs:element>"
        '<xs:simpleType name="tipo_Limitado"><xs:restriction base="xs:decimal">'
        f'<xs:{facet} value="3"/>'
        "</xs:restriction></xs:simpleType></xs:schema>"
    )
    document = DefusedElementTree.fromstring("<Declaracion><Importe>1</Importe></Declaracion>")

    with pytest.raises(ModeloApplicationError) as refused:
        refuse_xml_values_outside_schema(document, schema=schema, source_id="literal", entries=())

    assert _message(refused.value) == "xml_schema_unreadable"
    assert refused.value.context == {"source_id": "literal", "type_name": "tipo_Limitado"}


@pytest.mark.parametrize("year", supported_authored_exercises("100"))
def test_every_row_the_dictionary_places_has_a_place_in_its_edition(
    operation: PinnedAuthorityOperation, year: int
) -> None:
    """A row the XSD does not declare would be refused the moment it carried a value."""
    types = _types_by_path(year)
    undeclared = [entry.field_id for entry in _entries(_provider(operation, year)) if _plain_path(entry) not in types]

    assert undeclared == []


@pytest.mark.parametrize("locale", ["en", "es", "ca", "hu"])
def test_the_operator_reads_which_box_and_which_limit_and_never_the_value(
    operation: PinnedAuthorityOperation, locale: str
) -> None:
    provider = _provider(operation)
    entry = _named_row(provider, "C1ICRC")
    limit = int(_facet("tipo_ReferenciaCatastral", "maxLength"))
    secret = "7" * (limit + 1)
    failure = _refused(provider, entry, secret)

    assert isinstance(failure, ModeloApplicationError)
    message = resolve_error_message(failure, locale=locale)
    assert _box(entry) in message
    assert str(limit) in message
    assert "xml_value" not in message
    assert secret not in message
    assert secret not in render_error_text(failure)
    assert failure.context is not None
    assert "cause" not in failure.context


_CODE_TYPE_XSD = """<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
  <xs:element name="Doc">
    <xs:complexType>
      <xs:sequence>
        <xs:element name="Code">
          <xs:simpleType><xs:restriction base="xs:string"><xs:pattern value="[A-Z]+"/></xs:restriction></xs:simpleType>
        </xs:element>
      </xs:sequence>
    </xs:complexType>
  </xs:element>
</xs:schema>"""


@pytest.mark.parametrize(
    ("typed", "kept"),
    [("si", "SI"), ("\u0131", "\u0131"), ("\u017f", "\u017f"), ("a\u0131", "a\u0131")],
    ids=["a plain letter capitalizes", "dotless i", "long s", "mixed"],
)
def test_a_letter_that_capitalizes_into_plain_ascii_never_becomes_a_code_letter(typed: str, kept: str) -> None:
    schema = xml_value_schema(DefusedElementTree.fromstring(_CODE_TYPE_XSD), source_id="fixture", root_tag="Doc")

    assert canonical_xml_text(schema, "Doc/Code", typed) == kept
