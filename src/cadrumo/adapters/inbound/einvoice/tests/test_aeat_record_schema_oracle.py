"""Prove the production schema derivation equals what the XSD actually declares.

Production reads the bundled AEAT schemas through the hardened ``defusedxml``
boundary, so ``lxml`` stays out of the runtime. That leaves one exposure: the
walk in :mod:`.._aeat_record_schema` could be wrong, and nothing in production
would notice, because it would be agreeing with itself.

These cases close that by deriving the same sets a SECOND time, with a
different library and a different traversal -- ``lxml``'s XPath over the
compiled schema, rather than an ``ElementTree`` descent -- and asserting the two
agree. Independence of METHOD is the point; a second copy of the same walk would
prove only that it is deterministic.

The oracle is not decorative. The production walk's first version used
``iter()``, which flattens nested particles, and reported ``IDDestinatario`` as
mandatory on every registro de alta because it is ``[1..1000]`` inside an
OPTIONAL ``Destinatarios`` wrapper. That would have refused every factura
simplificada -- a document type the schema explicitly provides for. This oracle
fails on that implementation, which is what makes it worth running.
"""

from __future__ import annotations

from contextlib import suppress

import pytest

from .....core.resources._boundary import bundled_path
from .._aeat_record_schema import (
    AEAT_RECORD_SCHEMA_FAMILIES,
    mandatory_child_elements,
    schema_declared_max_occurs,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]

_XSD = "http://www.w3.org/2001/XMLSchema"
_NS = {"xs": _XSD}

# The record types this reader claims. Listed here rather than derived, because
# the CLAIM is a decision -- which families we support -- while everything about
# their contents is derived. A type named here that the schema does not declare
# fails loudly in `_oracle_mandatory`.
_CLAIMED = (
    ("verifactu", "RegistroFacturacionAltaType"),
    ("verifactu", "RegistroFacturacionAnulacionType"),
    ("sii", "FacturaExpedidaType"),
    ("sii", "FacturaRecibidaType"),
)


def _schema_trees(family: str):
    from lxml import etree

    directory = bundled_path("corpus", "aeat_official", "einvoice_record_schemas", family)
    return [etree.parse(str(directory / name)) for name in ("SuministroInformacion.xsd", "SuministroLR.xsd")]


def _named_type(family: str, type_name: str):
    for tree in _schema_trees(family):
        found = tree.getroot().xpath(f'//xs:complexType[@name="{type_name}"]', namespaces=_NS)
        if found:
            return found[0]
    message = f"{family} schema declares no complexType named {type_name!r}"
    raise AssertionError(message)


def _oracle_mandatory(family: str, type_name: str, *, _depth: int = 0) -> set[str]:
    """Independently derive the mandatory set with lxml XPath.

    Walks the particle tree by explicit axis steps rather than by descent,
    which is what makes it a different method: an element's own children are
    never reachable, because the walk only ever steps from a particle to its
    immediate particle children.
    """
    node = _named_type(family, type_name)
    names: set[str] = set()

    if _depth < 8:
        for extension in node.xpath(".//xs:extension[@base]", namespaces=_NS):
            base = extension.get("base").rsplit(":", 1)[-1]
            # A built-in or foreign-namespace base has no local declaration to
            # walk; that is expected, not a failure of the oracle.
            with suppress(AssertionError):
                names |= _oracle_mandatory(family, base, _depth=_depth + 1)

    def walk(particle, *, optional: bool) -> None:
        for child in particle:
            tag = child.tag.rsplit("}", 1)[-1] if isinstance(child.tag, str) else ""
            if tag == "element":
                name = child.get("name") or (child.get("ref") or "").rsplit(":", 1)[-1]
                if name and not optional and child.get("minOccurs", "1") != "0":
                    names.add(name)
            elif tag == "choice":
                walk(child, optional=True)
            elif tag in {"sequence", "all", "complexContent", "extension", "restriction", "group"}:
                walk(child, optional=optional or child.get("minOccurs", "1") == "0")

    walk(node, optional=False)
    return names


@pytest.mark.parametrize(("family", "type_name"), _CLAIMED)
def test_the_derived_mandatory_set_equals_what_the_schema_declares(family: str, type_name: str) -> None:
    """The production walk agrees with an independent lxml derivation."""
    assert mandatory_child_elements(family, type_name) == frozenset(_oracle_mandatory(family, type_name))


def test_a_nested_element_under_an_optional_wrapper_is_not_mandatory() -> None:
    """The specific inversion the first implementation shipped.

    ``Destinatarios`` is ``[0..1]``; ``IDDestinatario`` inside it is
    ``[1..1000]``. A record naming no recipient at all is valid -- that is a
    factura simplificada -- so a derivation reporting ``IDDestinatario`` as
    mandatory refuses a document class the schema explicitly provides for.

    Asserted on the CONTAINMENT relationship rather than on a count, so it
    keeps meaning if AEAT adds or removes obligations elsewhere in the type.
    """
    mandatory = mandatory_child_elements("verifactu", "RegistroFacturacionAltaType")

    assert "IDDestinatario" not in mandatory
    assert "Destinatarios" not in mandatory
    assert schema_declared_max_occurs("verifactu", "IDDestinatario") == "1000"
    # The wrapper's own children being excluded must not have emptied the set.
    assert {"IDFactura", "Desglose", "ImporteTotal"} <= mandatory


def test_a_choice_member_is_not_individually_mandatory() -> None:
    """``Encadenamiento`` states PrimerRegistro OR RegistroAnterior.

    Both declare ``minOccurs="1"`` inside the choice. Treating either as
    required refuses every record, since no record can carry both.
    """
    mandatory = mandatory_child_elements("verifactu", "RegistroFacturacionAltaType")

    assert "Encadenamiento" in mandatory, "the wrapper itself IS required"
    assert "PrimerRegistro" not in mandatory
    assert "RegistroAnterior" not in mandatory


def test_every_bundled_family_parses_and_declares_the_claimed_types() -> None:
    """Guards the bundling layout the manifest calls load-bearing.

    Both families ship a file named ``SuministroInformacion.xsd`` in different
    target namespaces. If they were ever flattened into one directory, one
    family would resolve against the other's types and this would fail -- the
    SII types are absent from the VERI*FACTU schema and vice versa.
    """
    assert set(AEAT_RECORD_SCHEMA_FAMILIES) == {"sii", "verifactu"}

    assert mandatory_child_elements("verifactu", "RegistroFacturacionAltaType")
    assert mandatory_child_elements("sii", "FacturaExpedidaType")

    with pytest.raises(KeyError):
        mandatory_child_elements("sii", "RegistroFacturacionAltaType")
    with pytest.raises(KeyError):
        mandatory_child_elements("verifactu", "FacturaExpedidaType")
