"""Read the official repeat limits of an XML design from the schema the revision cites.

A design states how often an element may repeat in its XSD ``maxOccurs``. The
generator opens one repeating group per such element and bounds it by that
limit, so the bound is the design's own figure rather than a number chosen per
modelo. Paths are element names below the document root, the same shape as the
dictionary's element paths, and ``None`` is an unbounded element.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Final
from xml.etree.ElementTree import Element

from defusedxml import ElementTree

from cadrumo.domain.calculations.registry.schema_base import RegistrySourceKind
from cadrumo.domain.calculations.registry.schema_exports import ExportLayoutDefinition
from cadrumo.domain.calculations.registry.schema_references import SourceReference

__all__ = ["OfficialRepeats", "official_repeats", "read_xsd_repeats"]

_XS: Final[str] = "{http://www.w3.org/2001/XMLSchema}"
_GROUPS: Final[frozenset[str]] = frozenset({f"{_XS}sequence", f"{_XS}choice", f"{_XS}all", f"{_XS}complexContent"})
_MAX_DEPTH: Final[int] = 64

type OfficialRepeats = Mapping[tuple[str, ...], int | None]


def _local(name: str) -> str:
    return name.rsplit(":", 1)[-1]


def _repeat_limit(element: Element) -> tuple[bool, int | None]:
    raw = element.get("maxOccurs", "1").strip()
    if raw == "unbounded":
        return True, None
    limit = int(raw)
    return limit > 1, limit


class _SchemaWalk:
    def __init__(self, schema: Element) -> None:
        self.types = {
            item.get("name", ""): item for item in schema.findall(f"{_XS}complexType") if item.get("name") is not None
        }
        self.repeats: dict[tuple[str, ...], int | None] = {}

    def element(self, element: Element, path: tuple[str, ...]) -> None:
        if len(path) > _MAX_DEPTH:
            return
        repeats, limit = _repeat_limit(element)
        if repeats:
            self.repeats[path] = limit
        inline = element.find(f"{_XS}complexType")
        named = self.types.get(_local(element.get("type", "")))
        for complex_type in (inline, named):
            if complex_type is not None:
                self.content(complex_type, path, depth=0)

    def content(self, node: Element, path: tuple[str, ...], *, depth: int) -> None:
        if depth > _MAX_DEPTH:
            return
        for child in node:
            if child.tag == f"{_XS}element" and child.get("name") is not None:
                self.element(child, (*path, str(child.get("name"))))
            elif child.tag in _GROUPS:
                self.content(child, path, depth=depth + 1)
            elif child.tag == f"{_XS}extension":
                base = self.types.get(_local(child.get("base", "")))
                if base is not None:
                    self.content(base, path, depth=depth + 1)
                self.content(child, path, depth=depth + 1)


def read_xsd_repeats(payload: bytes) -> dict[tuple[str, ...], int | None]:
    """Return each repeating element's path below the root, mapped to its limit."""
    schema = ElementTree.fromstring(payload)
    walk = _SchemaWalk(schema)
    for root in schema.findall(f"{_XS}element"):
        if root.get("name") is not None:
            walk.element(root, ())
    return walk.repeats


def official_repeats(
    layout: ExportLayoutDefinition,
    sources: Mapping[str, SourceReference],
    data_root: Path,
) -> dict[tuple[str, ...], int | None]:
    """Read the repeat limits of the one XSD the XML layout cites; none when it cites none or several."""
    schemas = [
        source
        for source_ref in layout.source_refs
        if (source := sources.get(str(source_ref))) is not None and source.kind is RegistrySourceKind.XSD
    ]
    if len(schemas) != 1:
        return {}
    return read_xsd_repeats((data_root / schemas[0].corpus_path).read_bytes())
