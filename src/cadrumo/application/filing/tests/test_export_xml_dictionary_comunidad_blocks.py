"""A declaration carries its filer's autonomic deductions and no other comunidad's.

AEAT declares the fifteen comunidad blocks as an ``xs:choice``, so at most one may
appear. Each block also declares its deduction total against casilla 0564, so
rendering every declared path for that casilla writes one comunidad's total into
all fifteen and produces a document the schema rejects.

The oracles here are AEAT's own: the model group is read from the bundled XSD and
the block membership from the bundled dictionary, so neither assertion restates
the code under test.

Absence is the assertion that matters. A write-then-read round trip cannot catch
this defect -- the read-side contradiction guard raises only on disagreement, and
sixteen copies of one value agree with each other -- so what is checked is that
the fourteen other blocks are *not* written.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from decimal import Decimal

import pytest

from ....core.resources.bundled_data import bundled_path
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.export_parse import xml_dictionary_entries
from ....domain.calculations.registry.governed_fact_scope import validating_governed_facts
from ....domain.calculations.registry.tests.registry_tree import bundled_registry_tree
from ....domain.filing.errors import FilingExportValidationError
from .._export_xml_dictionary import (
    _modelo_100_comunidad_block,
    _modelo_100_unfiled_comunidad_paths,
    registry_modelo_100_xml_declarations,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_MODELO_100_2024_XSD = "29-100-esquema-xsd-ejercicio-2024-actualizado-19-01-2026-747-kb-ejecutable.xsd"
_SHARED_TOTAL = "0564"


@pytest.fixture(scope="module")
def _declarations(operation: PinnedAuthorityOperation) -> Mapping[str, str]:
    """Resolve Modelo 100 XML routing declarations through the pinned authority."""
    with validating_governed_facts(operation):
        return registry_modelo_100_xml_declarations()


def _entries():
    modelos, catalogues = bundled_registry_tree()
    modelo = next(item for item in modelos if item.id == "100")
    revision = modelo.revisions["2024"]
    layout = next(item for item in revision.export_layouts if item.format == "xml_dictionary")
    return xml_dictionary_entries(
        layout,
        sources=catalogues.sources,
        source_payloads={
            str(source.id): (bundled_path() / source.corpus_path).read_bytes() for source in catalogues.sources.values()
        },
    )


def _own_casillas(block: str, *, declarations: Mapping[str, str]) -> list[str]:
    return sorted(
        {
            entry.casilla_id
            for entry in _entries()
            if _modelo_100_comunidad_block(entry.path, declarations=declarations) == block
            and entry.casilla_id is not None
            and entry.casilla_id != _SHARED_TOTAL
        }
    )


def test_aeat_declares_the_comunidad_blocks_as_a_choice() -> None:
    """The schema, not an inference from prose, is why only one block may appear.

    A ``sequence`` would have meant writing the others as zero, which is what the
    sign-branch pair next door requires. The model group is the whole difference.
    """
    xsd = bundled_path("corpus", "aeat_official", "disenos_registro", "modelo_100", "files", _MODELO_100_2024_XSD)
    text = xsd.read_bytes().decode("iso-8859-1")
    start = text.find('complexType name="tipo_DeduccionAutonomicaRes"')
    assert start != -1, "the bundled XSD no longer declares tipo_DeduccionAutonomicaRes"
    body = text[start : text.find("</xs:complexType>", start)]

    group = re.search(r"<xs:(choice|sequence|all)([^>]*)>", body)
    assert group is not None and group.group(1) == "choice", "the comunidad blocks are no longer a choice"
    assert group.group(2).strip() == "", "the choice declares bounds that would admit more than one block"
    assert len(re.findall(r"<xs:element ", body)) == 15


def test_only_the_filed_comunidad_survives(_declarations: Mapping[str, str]) -> None:
    """A Madrid filer writes Madrid's block, and the other fourteen are omitted."""
    entries = _entries()
    madrid_casilla = _own_casillas("MadridRes", declarations=_declarations)[0]

    unfiled = _modelo_100_unfiled_comunidad_paths(
        entries,
        {madrid_casilla: Decimal("250.00")},
        declarations=_declarations,
    )

    written: set[str] = set()
    for entry in entries:
        block = _modelo_100_comunidad_block(entry.path, declarations=_declarations)
        if block is not None and entry.path not in unfiled:
            written.add(block)
    assert written == {"MadridRes"}, f"expected only MadridRes to survive, got {sorted(written)}"


def test_the_shared_total_reaches_exactly_one_comunidad_block(_declarations: Mapping[str, str]) -> None:
    """Casilla 0564's sixteen paths collapse to the summary plus one block."""
    entries = _entries()
    madrid_casilla = _own_casillas("MadridRes", declarations=_declarations)[0]

    unfiled = _modelo_100_unfiled_comunidad_paths(
        entries,
        {madrid_casilla: Decimal("250.00")},
        declarations=_declarations,
    )

    total_paths = [entry.path for entry in entries if entry.casilla_id == _SHARED_TOTAL]
    surviving = [path for path in total_paths if path not in unfiled]
    assert len(total_paths) == 16, f"casilla {_SHARED_TOTAL} no longer declares sixteen paths"
    assert len(surviving) == 2, f"expected the summary plus one block, got {surviving}"
    assert (
        sum(1 for path in surviving if _modelo_100_comunidad_block(path, declarations=_declarations) == "MadridRes")
        == 1
    )
    assert sum(1 for path in surviving if _modelo_100_comunidad_block(path, declarations=_declarations) is None) == 1


def test_no_autonomic_deductions_writes_no_block_and_no_total(_declarations: Mapping[str, str]) -> None:
    """A filer claiming none carries neither the summary nor any comunidad block."""
    entries = _entries()

    unfiled = _modelo_100_unfiled_comunidad_paths(entries, {}, declarations=_declarations)

    for entry in entries:
        if (
            _modelo_100_comunidad_block(entry.path, declarations=_declarations) is not None
            or entry.casilla_id == _SHARED_TOTAL
        ):
            assert entry.path in unfiled, f"{entry.path} would still be written with no deductions claimed"


def test_zero_only_cross_block_values_are_absent_not_a_conflict(_declarations: Mapping[str, str]) -> None:
    """String zero placeholders across CCAA blocks select no ``xs:choice`` branch."""
    entries = _entries()
    values = {
        _own_casillas("AragonRes", declarations=_declarations)[0]: "0",
        _own_casillas("MadridRes", declarations=_declarations)[0]: "0.00",
    }

    unfiled = _modelo_100_unfiled_comunidad_paths(entries, values, declarations=_declarations)

    assert all(
        entry.path in unfiled
        for entry in entries
        if _modelo_100_comunidad_block(entry.path, declarations=_declarations) is not None
        or entry.casilla_id == _SHARED_TOTAL
    )


def test_two_comunidades_refuses_and_names_both(_declarations: Mapping[str, str]) -> None:
    """The schema admits one, so a draft carrying two has no correct rendering."""
    entries = _entries()
    values = {
        _own_casillas("MadridRes", declarations=_declarations)[0]: Decimal("250.00"),
        _own_casillas("CatalunyaRes", declarations=_declarations)[0]: Decimal("100.00"),
    }

    with pytest.raises(FilingExportValidationError) as excinfo:
        _modelo_100_unfiled_comunidad_paths(entries, values, declarations=_declarations)

    message = str(excinfo.value)
    assert "MadridRes" in message and "CatalunyaRes" in message, f"the refusal names neither comunidad: {message}"


def test_nothing_outside_the_autonomic_blocks_is_ever_withheld(_declarations: Mapping[str, str]) -> None:
    """The rule is scoped: no path outside the comunidad blocks is affected.

    0435 and 0460 are carried into the base-liquidable block on AEAT's own
    instruction, so a rule reaching them would break a correct filing.
    """
    entries = _entries()
    madrid_casilla = _own_casillas("MadridRes", declarations=_declarations)[0]

    unfiled = _modelo_100_unfiled_comunidad_paths(
        entries,
        {madrid_casilla: Decimal("250.00")},
        declarations=_declarations,
    )

    for path in unfiled:
        assert _modelo_100_comunidad_block(path, declarations=_declarations) is not None, (
            f"{path} is outside the comunidad blocks"
        )
    carried = {entry.path for entry in entries if entry.casilla_id in {"0435", "0460"}}
    assert carried.isdisjoint(unfiled)


def test_restoring_all_write_fails_the_single_block_assertion(_declarations: Mapping[str, str]) -> None:
    """Mutation control: the previous behaviour must not satisfy these tests."""
    entries = _entries()

    def all_write(_entries: object, _values: object) -> frozenset[str]:
        return frozenset[str]()

    unfiled = all_write(entries, {})
    written: set[str] = set()
    for entry in entries:
        block = _modelo_100_comunidad_block(entry.path, declarations=_declarations)
        if block is not None and entry.path not in unfiled:
            written.add(block)
    assert len(written) == 15, "all-write no longer writes every comunidad block; the control is stale"
    assert written != {"MadridRes"}, "all-write satisfied the single-block assertion, so it proves nothing"
