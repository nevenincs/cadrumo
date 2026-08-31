"""Casilla 0695's two sign branches carry the value that belongs to each.

AEAT declares casilla 0695 against two sibling fields that are opposite branches
of one quantity rather than two copies of it -- ``TCPP112`` is the amount still to
pay and ``TCNN112`` the refund being requested. Writing the casilla's value into
both declares an amount to pay *and* an amount to refund.

The entries under test are read from the official bundled dictionary rather than
hand-built, and the reason the non-applicable branch is written as zero rather
than omitted is read from the bundled XSD. Both oracles are AEAT's, so neither
assertion restates the code under test.

A write-then-read round trip cannot verify this. The read-side contradiction guard
compares values and raises only on disagreement, while this defect writes the
*same* value into both branches -- so a round trip of our own output agrees with
itself and passes. Every assertion here is therefore an independent expectation
per branch, and absence of the value from the wrong branch is the defect's
signature.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from xml.etree.ElementTree import Element

import pytest
from defusedxml import ElementTree as DefusedElementTree

from ....core.resources.bundled_data import bundled_path
from ....domain.calculations.registry.export_parse import XmlDictionaryEntry, xml_dictionary_entries
from ....tests.registry_tree import bundled_registry_tree
from .._export_xml_dictionary import _modelo_100_sign_branch_value

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_XSD_NS = "{http://www.w3.org/2001/XMLSchema}"
_MODELO_100_2024_XSD = "29-100-esquema-xsd-ejercicio-2024-actualizado-19-01-2026-747-kb-ejecutable.xsd"
_SIGN_BRANCH_CASILLA = "0695"
_NON_NEGATIVE_BRANCH = "TCPP112"
_NEGATIVE_BRANCH = "TCNN112"


def _dictionary_entries() -> tuple[XmlDictionaryEntry, ...]:
    modelos, catalogues = bundled_registry_tree()
    modelo = next(item for item in modelos if item.id == "100")
    revision = modelo.revisions["2024"]
    layout = next(item for item in revision.export_layouts if item.format == "xml_dictionary")
    return tuple(xml_dictionary_entries(layout, source_root=bundled_path(), sources=catalogues.sources))


def _branch_entries() -> dict[str, XmlDictionaryEntry]:
    entries: dict[str, XmlDictionaryEntry] = {
        entry.field_id: entry for entry in _dictionary_entries() if entry.casilla_id == _SIGN_BRANCH_CASILLA
    }
    assert set(entries) == {_NON_NEGATIVE_BRANCH, _NEGATIVE_BRANCH}, (
        f"casilla {_SIGN_BRANCH_CASILLA} no longer declares exactly the two known branches: {sorted(entries)}"
    )
    return entries


def _xsd_element(name: str) -> Element[str]:
    xsd = bundled_path("corpus", "aeat_official", "disenos_registro", "modelo_100", "files", _MODELO_100_2024_XSD)
    root = DefusedElementTree.parse(Path(xsd)).getroot()
    assert root is not None
    for element in root.iter(f"{_XSD_NS}element"):
        if element.attrib.get("name") == name:
            return element
    pytest.fail(f"bundled Modelo 100 XSD declares no element named {name!r}")


def test_both_branches_are_mandatory_so_the_idle_one_is_zeroed_not_omitted() -> None:
    """AEAT's schema is why the non-applicable branch carries zero.

    Omitting it would render a ``CompensacionConyugesRes`` the schema rejects,
    so "write only the matching branch" is not available however sensible it
    sounds.
    """
    for name in (_NON_NEGATIVE_BRANCH, _NEGATIVE_BRANCH):
        assert _xsd_element(name).attrib.get("minOccurs", "1") == "1", f"{name} is optional; zeroing is unnecessary"
    assert _xsd_element("CompensacionConyugesRes").attrib.get("minOccurs") == "0", (
        "the parent block is mandatory, so the branches cannot be skipped by omitting it"
    )


def test_a_positive_amount_reaches_only_the_amount_to_pay_branch() -> None:
    """A positive 0695 is money still owed, and no refund is being requested."""
    entries = _branch_entries()

    assert _modelo_100_sign_branch_value(entries[_NON_NEGATIVE_BRANCH], Decimal("1234.56")) == Decimal("1234.56")
    assert _modelo_100_sign_branch_value(entries[_NEGATIVE_BRANCH], Decimal("1234.56")) == Decimal("0")


def test_a_negative_amount_reaches_only_the_refund_branch() -> None:
    """A negative 0695 is a refund being requested, and nothing is owed."""
    entries = _branch_entries()

    assert _modelo_100_sign_branch_value(entries[_NEGATIVE_BRANCH], Decimal("-987.65")) == Decimal("-987.65")
    assert _modelo_100_sign_branch_value(entries[_NON_NEGATIVE_BRANCH], Decimal("-987.65")) == Decimal("0")


def test_zero_needs_no_tie_break_because_both_branches_agree_on_it() -> None:
    """Both labels admit zero, and both rules yield zero, so the ambiguity is moot."""
    entries = _branch_entries()

    assert _modelo_100_sign_branch_value(entries[_NON_NEGATIVE_BRANCH], Decimal("0")) == Decimal("0")
    assert _modelo_100_sign_branch_value(entries[_NEGATIVE_BRANCH], Decimal("0")) == Decimal("0")


@pytest.mark.parametrize("uncoercible", ["abc", "", "1.234,56", True, None])
def test_a_value_that_will_not_coerce_selects_a_branch_instead_of_raising(uncoercible: object) -> None:
    """Branch selection must not fail on a value it cannot read a sign from.

    ``coerce_decimal`` answers ``None`` for these, so comparing the result
    against zero raised ``TypeError`` on the export path. Reading an unreadable
    amount as zero keeps the selection total; deciding what the value *means*
    belongs to the formatter, which is where every other casilla's is decided.
    """
    entries = _branch_entries()

    assert _modelo_100_sign_branch_value(entries[_NON_NEGATIVE_BRANCH], uncoercible) is uncoercible
    assert _modelo_100_sign_branch_value(entries[_NEGATIVE_BRANCH], uncoercible) == Decimal("0")


def test_the_carry_class_is_left_alone() -> None:
    """Casillas that legitimately write every declared path must pass through.

    0435 and 0460 are carried into the base-liquidable block on AEAT's own
    instruction, so a sign rule that touched them would break a correct filing.
    """
    carried = [entry for entry in _dictionary_entries() if entry.casilla_id in {"0435", "0460"}]

    assert len(carried) == 4, f"expected two rows each for 0435 and 0460, found {len(carried)}"
    for entry in carried:
        for amount in (Decimal("500.00"), Decimal("-500.00"), Decimal("0")):
            assert _modelo_100_sign_branch_value(entry, amount) == amount


def test_restoring_all_write_fails_every_branch_assertion() -> None:
    """Mutation control: the previous behaviour must not satisfy these tests.

    ``all_write`` is what the renderer did before this rule -- return the casilla
    value unchanged for every declared path. If the assertions above can pass
    against it, they are not testing anything.
    """
    entries = _branch_entries()

    def all_write(_entry: object, raw: object) -> object:
        return raw

    caught: list[str] = []
    for label, entry_id, amount, expected in (
        ("positive leaks into refund branch", _NEGATIVE_BRANCH, Decimal("1234.56"), Decimal("0")),
        ("negative leaks into pay branch", _NON_NEGATIVE_BRANCH, Decimal("-987.65"), Decimal("0")),
    ):
        if all_write(entries[entry_id], amount) != expected:
            caught.append(label)

    assert caught == ["positive leaks into refund branch", "negative leaks into pay branch"], (
        f"all-write was not caught by both branch assertions: {caught}"
    )
