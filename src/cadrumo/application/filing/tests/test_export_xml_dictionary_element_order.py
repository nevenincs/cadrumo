"""Rendered sibling order follows the sequence AEAT's XSD declares.

The declaration body is an ``xs:sequence``, so sibling order is part of the
schema rather than a presentation choice. The dictionary rows that drive the
writer are not in that order -- under ``Declarante`` the dictionary reaches
``SEXO_D`` before ``ECIVIL``, while the schema places it after ``DPFNAC_D`` --
so creating each element as its row is reached produced a document AEAT's own
schema rejects.

Expected orders are never written by hand here. Each assertion reads the child
sequence the bundled official XSD declares and checks the rendered document
against it, so the oracle is AEAT's schema rather than a restatement of the code
under test. :func:`test_the_order_oracle_rejects_the_dictionarys_own_order` keeps
that oracle honest: it fails if the oracle ever stops discriminating, which would
make every other assertion here vacuous.
"""

from __future__ import annotations

from pathlib import Path
from xml.etree.ElementTree import Element

import pytest
from defusedxml import ElementTree as DefusedElementTree

from ....domain.calculations.registry import xml_dictionary_entries
from .._export_xml_dictionary import (
    _xml_dictionary_element_order,
    _xml_dictionary_xsd_source,
    render_xml_dictionary_layout,
)
from .test_export import _approved_modelo_100_xml_dictionary_draft, _schema_provider

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

# Populating the identity fields is what makes this module non-vacuous: their
# dictionary order is one of the orders that diverges, and a sparser draft
# leaves the divergence unexercised.
_IDENTITY_HEADERS = {
    "surnames": "SURNAME BLANK",
    "name": "STATE",
    "sexo_d": "H",
    "ecivil": "1",
    "dpfnac_d": "1/1/1980",
}


def _rendered_declaration() -> Element[str]:
    draft = _approved_modelo_100_xml_dictionary_draft()
    provider = _schema_provider(filing_year=2024, period="0A", modelos=("100",))
    layout = provider.get_subview("100").export_layouts[0]
    payload = render_xml_dictionary_layout(
        layout,
        draft=draft,
        headers=dict(_IDENTITY_HEADERS),
        schema_provider=provider,
    )
    root = DefusedElementTree.fromstring(payload)
    assert root is not None
    return root


def _declared_order() -> dict[str, tuple[str, ...]]:
    provider = _schema_provider(filing_year=2024, period="0A", modelos=("100",))
    layout = provider.get_subview("100").export_layouts[0]
    return _xml_dictionary_element_order(
        _xml_dictionary_xsd_source(layout, provider.sources),
        source_root=provider.source_root,
    )


def _follows(observed: tuple[str, ...], declared: tuple[str, ...]) -> bool:
    """Whether ``observed`` is ordered consistently with ``declared``."""
    ranks = [declared.index(name) for name in observed if name in declared]
    return ranks == sorted(ranks)


def _dictionary_child_order(parent_path: str) -> tuple[str, ...]:
    """First-encounter child order for ``parent_path``, as the dictionary lists it."""
    provider = _schema_provider(filing_year=2024, period="0A", modelos=("100",))
    layout = provider.get_subview("100").export_layouts[0]
    entries = xml_dictionary_entries(layout, source_root=provider.source_root, sources=provider.sources)
    seen: list[str] = []
    for entry in entries:
        parts = [part for part in entry.path.strip("/").split("/") if part and not part.startswith("@")]
        if parts and parts[0] == "Declaracion":
            parts = parts[1:]
        for index in range(len(parts) - 1):
            if "/" + "/".join(parts[: index + 1]) != parent_path:
                continue
            child = parts[index + 1]
            if child not in seen:
                seen.append(child)
    return tuple(seen)


def test_the_order_oracle_rejects_the_dictionarys_own_order() -> None:
    """The oracle discriminates, so a passing assertion below means something.

    The dictionary's own child order for ``Declarante`` is the order the writer
    used to emit, and AEAT's schema rejects it. If this ever passes, the schema
    and the dictionary have converged and the rest of this module is vacuous.
    """
    declared = _declared_order()["/DatosIdentificativos/Declarante"]
    from_dictionary = _dictionary_child_order("/DatosIdentificativos/Declarante")

    assert _follows(declared, declared)
    assert not _follows(from_dictionary, declared), (
        "the dictionary's Declarante order no longer diverges from the XSD; "
        "this module's assertions no longer prove anything"
    )


def test_every_rendered_parent_follows_its_declared_child_sequence() -> None:
    """No rendered element sits ahead of a sibling the schema declares before it."""
    declared_order = _declared_order()
    root = _rendered_declaration()
    checked = 0
    offenders: list[str] = []

    def visit(node: Element[str], path: str) -> None:
        nonlocal checked
        children = tuple(str(child.tag) for child in node)
        declared = declared_order.get(path)
        if declared is not None and len(children) > 1:
            checked += 1
            if not _follows(children, declared):
                offenders.append(f"{path}: rendered {children} against declared {declared}")
        for child in node:
            visit(child, f"{path}/{child.tag}")

    visit(root, "")

    assert checked > 0, "no rendered parent carried enough children to check an order"
    assert not offenders, "rendered children diverge from the declared XSD sequence:\n" + "\n".join(offenders)


def test_the_identity_block_renders_in_schema_order_not_dictionary_order() -> None:
    """The worked case: ``SEXO_D`` follows ``DPFNAC_D``, as the schema declares."""
    root = _rendered_declaration()
    declarante = root.find("./DatosIdentificativos/Declarante")
    assert declarante is not None
    rendered = tuple(str(child.tag) for child in declarante)
    declared = _declared_order()["/DatosIdentificativos/Declarante"]

    assert set(rendered) >= {"ECIVIL", "DPFNAC_D", "SEXO_D"}
    assert _follows(rendered, declared)
    assert rendered.index("SEXO_D") > rendered.index("DPFNAC_D")


def test_ordering_changes_no_rendered_value() -> None:
    """Placement is all the schema order decides; every value is untouched.

    A reordering that also altered a value would be a filed-data change wearing a
    structural change's clothes, so the value set is pinned independently.
    """
    root = _rendered_declaration()
    values: dict[str, str] = {}

    def collect(node: Element[str], path: str) -> None:
        for name, value in node.attrib.items():
            values[f"{path}/@{name}"] = value
        children = list(node)
        if not children:
            values[path] = (node.text or "").strip()
        for child in children:
            collect(child, f"{path}/{child.tag}")

    collect(root, "")

    assert values["/DatosIdentificativos/Declarante/DPNIF_D"] == "12345678Z"
    assert values["/DatosIdentificativos/Declarante/SEXO_D"] == "H"
    assert values["/DatosIdentificativos/Declarante/ECIVIL"] == "1"
    assert values["/DatosIdentificativos/Declarante/DPFNAC_D"] == "1/1/1980"
    assert values["/DatosEconomicos/TomaDatosAmpliada/RdtoTrabajo/TPDIN"] == "12000.25"


def test_declared_order_covers_every_dictionary_parent_path() -> None:
    """The schema describes every parent the dictionary addresses.

    The writer falls back to first-encounter order for a path the schema does not
    describe. That fallback must stay unreachable for Modelo 100: if it is ever
    reached, some parent silently keeps emitting in dictionary order.
    """
    provider = _schema_provider(filing_year=2024, period="0A", modelos=("100",))
    layout = provider.get_subview("100").export_layouts[0]
    entries = xml_dictionary_entries(layout, source_root=provider.source_root, sources=provider.sources)
    declared_order = _declared_order()

    uncovered: set[str] = set()
    for entry in entries:
        parts = [part for part in entry.path.strip("/").split("/") if part and not part.startswith("@")]
        if parts and parts[0] == "Declaracion":
            parts = parts[1:]
        for index in range(1, len(parts)):
            path = "/" + "/".join(parts[:index])
            if path not in declared_order:
                uncovered.add(path)

    assert not uncovered, f"dictionary addresses parents the XSD does not describe: {sorted(uncovered)}"


def test_the_declared_order_is_read_from_the_bundled_official_schema() -> None:
    """The oracle is AEAT's shipped file, not a table restated in this tree."""
    provider = _schema_provider(filing_year=2024, period="0A", modelos=("100",))
    layout = provider.get_subview("100").export_layouts[0]
    source = _xml_dictionary_xsd_source(layout, provider.sources)
    assert provider.source_root is not None
    assert Path(provider.source_root / source.corpus_path).is_file()
