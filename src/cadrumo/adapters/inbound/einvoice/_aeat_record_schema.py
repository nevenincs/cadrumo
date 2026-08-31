"""Derive AEAT record-schema obligations from the bundled XSDs themselves.

The mandatory-element set for a SII or VERI*FACTU record is READ FROM THE
SCHEMA at runtime, never hand-copied into this file. That is the whole point:
a transcribed list of "the 14 mandatory elements of a registro de alta" is
correct exactly once, rots on the first AEAT schema revision, and rots
silently, because nothing compares it back to its source. A derived set cannot
drift from the schema, because it has no independent existence.

An XSD is itself XML, so the derivation runs through the SAME hardened parser
(:func:`~._xml.parse_hardened_xml`) every other document on this path uses.
Production therefore gains no second XML stack and no second hardening posture
on the most hostile input surface in the product: no XML this package reads
touches ``lxml``. That is narrower than "lxml stays out of the runtime", which
an earlier version of this paragraph claimed and ``pyproject.toml`` explicitly
corrects -- production DOES rely on lxml, as BeautifulSoup's parser backend for
AEAT HTML, named in the AEAT adapter's one HTML constructor. The two are
separate reliances on separate input surfaces, and only the XML one is this
module's concern. The real XSD engine still has
a job -- it validates this module's derivation in CI, by an INDEPENDENT method,
so a bug in the walk below is caught by libxml2 rather than by agreement with
itself.

What the walk must handle, because AEAT's schemas use all of it:

* ``minOccurs`` defaults to 1 when absent, so an element with no ``minOccurs``
  attribute is MANDATORY. Reading absence as optional inverts the whole set.
* A ``complexType`` may extend another through
  ``complexContent/extension@base``, and the base's mandatory children are
  mandatory in the derived type too. SII's ``FacturaExpedidaType`` reaches
  ``ImporteTotal`` and ``FechaOperacion`` only through its base.
* An element inside a ``choice`` is NOT individually mandatory even when it
  declares ``minOccurs="1"`` -- the choice makes it one alternative among
  several. ``Encadenamiento`` states ``PrimerRegistro`` and ``RegistroAnterior``
  this way, and treating either as required refuses every valid record.
"""

from __future__ import annotations

from functools import lru_cache
from xml.etree.ElementTree import Element

from ....core.resources._boundary import bundled_path
from ._xml import parse_hardened_xml

__all__ = [
    "AEAT_RECORD_SCHEMA_FAMILIES",
    "mandatory_child_elements",
    "schema_declared_max_occurs",
]

_XSD_NS = "{http://www.w3.org/2001/XMLSchema}"

#: The two bundled record-schema families, by directory name. Each keeps its
#: own directory because both import a file named ``SuministroInformacion.xsd``
#: in DIFFERENT target namespaces; see the bundled ``manifest.json``.
AEAT_RECORD_SCHEMA_FAMILIES: tuple[str, ...] = ("sii", "verifactu")

_SCHEMA_ROOT = ("corpus", "aeat_official", "einvoice_record_schemas")


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


@lru_cache(maxsize=8)
def _schema_documents(family: str) -> tuple[Element, ...]:
    """Parse a family's bundled schema documents, hardened and cached.

    Cached because the mandatory sets are consulted per record and the base
    schema is ~83 KB; parsing it for every record in a 10000-record batch would
    dominate the read. The parsed trees are never mutated by this module.
    """
    if family not in AEAT_RECORD_SCHEMA_FAMILIES:
        message = f"unknown AEAT record-schema family {family!r}; bundled families are {AEAT_RECORD_SCHEMA_FAMILIES}"
        raise ValueError(message)
    directory = bundled_path(*_SCHEMA_ROOT, family)
    return tuple(
        parse_hardened_xml((directory / name).read_bytes())
        for name in ("SuministroInformacion.xsd", "SuministroLR.xsd")
    )


def _named_complex_types(family: str) -> dict[str, Element]:
    """Return every named ``complexType`` in a family, keyed by bare name."""
    found: dict[str, Element] = {}
    for document in _schema_documents(family):
        for node in document.iter(f"{_XSD_NS}complexType"):
            name = node.get("name")
            if name and name not in found:
                found[name] = node
    return found


def _collect_particles(particle: Element, names: set[str], *, optional: bool) -> None:
    """Walk a content model, collecting the names it makes mandatory.

    Descends through the particle constructors (``sequence``, ``all``,
    ``choice``, and the ``complexContent``/``extension`` wrappers) and STOPS at
    every ``element``. Not descending into an element is the load-bearing part:
    an element's own children belong to IT, not to the type being described, so
    a walk that recurses into them reports a nested obligation as a top-level
    one. ``Destinatarios`` is optional ``[0..1]`` while the ``IDDestinatario``
    inside it is ``[1..1000]``; flattening the two claims every VERI*FACTU
    record must name a recipient, which would refuse every factura simplificada
    -- a document type the schema explicitly provides for.
    """
    for child in particle:
        tag = _local(child.tag)
        if tag == "element":
            name = child.get("name") or (child.get("ref") or "").rsplit(":", 1)[-1]
            if name and not optional and child.get("minOccurs", "1") != "0":
                names.add(name)
            continue
        if tag == "choice":
            # A choice states alternatives. Even a member declaring
            # minOccurs="1" is not individually required, so everything below
            # is collected as optional. Encadenamiento's PrimerRegistro /
            # RegistroAnterior pair is exactly this shape.
            _collect_particles(child, names, optional=True)
            continue
        if tag in {"sequence", "all", "complexContent", "extension", "restriction", "group"}:
            _collect_particles(child, names, optional=optional or child.get("minOccurs", "1") == "0")


def mandatory_child_elements(family: str, type_name: str) -> frozenset[str]:
    """Return the element names a record of *type_name* MUST declare.

    Follows ``complexContent/extension@base`` so an inherited obligation counts,
    and excludes anything inside an ``xs:choice``, which states alternatives
    rather than requirements.

    Args:
        family: A member of :data:`AEAT_RECORD_SCHEMA_FAMILIES`.
        type_name: The bare ``complexType`` name, e.g.
            ``"RegistroFacturacionAltaType"``.

    Returns:
        The mandatory child element names, derived from the bundled schema.

    Raises:
        KeyError: When the schema declares no such type -- a caller naming a
            type the schema does not have is a bug, not a document problem.
    """
    types = _named_complex_types(family)
    return frozenset(_mandatory_names(types, type_name, seen=frozenset()))


def _mandatory_names(types: dict[str, Element], type_name: str, *, seen: frozenset[str]) -> set[str]:
    if type_name in seen:
        # A cyclic extension chain is malformed; stop rather than recurse away.
        return set()
    node = types[type_name]
    names: set[str] = set()
    for extension in node.iter(f"{_XSD_NS}extension"):
        base = (extension.get("base") or "").rsplit(":", 1)[-1]
        if base in types:
            names |= _mandatory_names(types, base, seen=seen | {type_name})
    _collect_particles(node, names, optional=False)
    return names


def schema_declared_max_occurs(family: str, element_name: str) -> str | None:
    """Return the ``maxOccurs`` a family's schema declares for *element_name*.

    Exposed so a refusal can quote the schema's own bound rather than a number
    written into a message by hand. Returns ``None`` when the schema declares no
    such element, and ``"1"`` when it declares one with no explicit bound.
    """
    for document in _schema_documents(family):
        for element in document.iter(f"{_XSD_NS}element"):
            name = element.get("name") or (element.get("ref") or "").rsplit(":", 1)[-1]
            if name == element_name:
                return element.get("maxOccurs", "1")
    return None
