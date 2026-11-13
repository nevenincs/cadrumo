"""Registry validation refuses an input-dictionary row the official design does not admit.

Each case starts from the real bundled registry and the real official bytes of an
edition the support envelope covers, then changes one input-dictionary row the
savings detail records need. The admission check is the one the export uses.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import pytest

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.export_xml_dictionary import (
    decode_dictionary_text,
    xml_dictionary_entries,
    xml_input_dictionary_entries,
)
from cadrumo.domain.calculations.registry.schema import ModeloRevision
from cadrumo.domain.calculations.registry.schema_exports import ExportLayoutDefinition
from cadrumo.domain.calculations.registry.tests.authored_editions import (
    revision_covering,
    supported_authored_exercises,
)

from ..xml_input_dictionary import check_xml_input_dictionary_layout, verify_xml_input_dictionary_layouts

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_EDITIONS = supported_authored_exercises("100")


def _revision(authority: ValidatedRegistryAuthority, year: int) -> ModeloRevision:
    modelo = next(item for item in authority.modelos if str(item.id) == "100")
    return modelo.revisions[str(revision_covering("100", year).id)]


def _payloads(authority: ValidatedRegistryAuthority, layout: ExportLayoutDefinition) -> dict[str, bytes]:
    sources = authority.catalogues.sources
    return {ref: (bundled_path() / sources[ref].corpus_path).read_bytes() for ref in layout.source_refs}


def _demanded_line(payloads: Mapping[str, bytes], layout: ExportLayoutDefinition, field: str) -> str:
    assert layout.input_dictionary_source_ref is not None
    text = decode_dictionary_text(payloads[layout.input_dictionary_source_ref])
    return next(line for line in text.splitlines() if line.startswith(f"{field}=["))


def _with_input_line(
    payloads: Mapping[str, bytes], layout: ExportLayoutDefinition, old: str, new: str
) -> dict[str, bytes]:
    assert layout.input_dictionary_source_ref is not None
    reference = layout.input_dictionary_source_ref
    text = decode_dictionary_text(payloads[reference])
    assert text.count(old) == 1
    return {**payloads, reference: text.replace(old, new).encode("utf-8")}


def _setting(authority: ValidatedRegistryAuthority, year: int) -> tuple[ModeloRevision, ExportLayoutDefinition, str]:
    revision = _revision(authority, year)
    layout = revision.export_layouts[0]
    payloads = _payloads(authority, layout)
    sources = authority.catalogues.sources
    offered = {
        entry.field_id for entry in xml_input_dictionary_entries(layout, sources=sources, source_payloads=payloads)
    }
    declared = {
        entry.field_id
        for entry in xml_dictionary_entries(
            layout, sources=sources, source_payloads=payloads, casillas=revision.casillas
        )
    }
    demanded = sorted(
        field
        for binding in revision.bindings
        if isinstance(field := binding.provider.model_dump().get("dictionary_field"), str)
        and field in offered - declared
    )
    assert demanded, f"{year}: no row binding names an input-dictionary field"
    return revision, layout, demanded[0]


@pytest.mark.parametrize("year", _EDITIONS)
def test_every_edition_admits_its_demanded_rows(registry_authority: ValidatedRegistryAuthority, year: int) -> None:
    revision, layout, _field = _setting(registry_authority, year)

    check_xml_input_dictionary_layout(
        layout,
        bindings=revision.bindings,
        casillas=revision.casillas,
        sources=registry_authority.catalogues.sources,
        source_payloads=_payloads(registry_authority, layout),
    )


def test_the_registry_gate_admits_the_bundled_registry(registry_authority: ValidatedRegistryAuthority) -> None:
    verify_xml_input_dictionary_layouts(registry_authority, source_root=Path(bundled_path()))


def test_a_row_the_xsd_does_not_declare_is_refused(registry_authority: ValidatedRegistryAuthority) -> None:
    revision, layout, field = _setting(registry_authority, _EDITIONS[-1])
    payloads = _payloads(registry_authority, layout)
    line = _demanded_line(payloads, layout, field)
    moved = line.replace(f"/{field}]", f"/{field}UNDECLARED]", 1)

    with pytest.raises(RegistryValidationError, match="the XSD declares no such element"):
        check_xml_input_dictionary_layout(
            layout,
            bindings=revision.bindings,
            casillas=revision.casillas,
            sources=registry_authority.catalogues.sources,
            source_payloads=_with_input_line(payloads, layout, line, moved),
        )


def test_a_path_the_declaration_dictionary_defines_differently_is_refused(
    registry_authority: ValidatedRegistryAuthority,
) -> None:
    revision, layout, field = _setting(registry_authority, _EDITIONS[-1])
    payloads = _payloads(registry_authority, layout)
    sources = registry_authority.catalogues.sources
    declared = xml_dictionary_entries(layout, sources=sources, source_payloads=payloads, casillas=revision.casillas)
    line = _demanded_line(payloads, layout, field)
    path = line.split("=[", 1)[1].split("]", 1)[0]
    # An element row the declaration dictionary already carries in the same income section.
    section = path.rsplit("/", 3)[0]
    taken = next(
        entry
        for entry in declared
        if entry.path.startswith(f"{section}/") and not entry.path.rsplit("/", 1)[1].startswith("@")
    )
    conflicting = _with_input_line(payloads, layout, line, line.replace(f"[{path}]", f"[{taken.path}]", 1))

    with pytest.raises(RegistryValidationError, match=f"already defines {taken.path} as {taken.field_id}"):
        check_xml_input_dictionary_layout(
            layout,
            bindings=revision.bindings,
            casillas=revision.casillas,
            sources=sources,
            source_payloads=conflicting,
        )


def test_a_field_neither_dictionary_declares_is_refused(registry_authority: ValidatedRegistryAuthority) -> None:
    revision, layout, field = _setting(registry_authority, _EDITIONS[-1])
    payloads = _payloads(registry_authority, layout)
    line = _demanded_line(payloads, layout, field)

    with pytest.raises(RegistryValidationError, match="neither dictionary declares it"):
        check_xml_input_dictionary_layout(
            layout,
            bindings=revision.bindings,
            casillas=revision.casillas,
            sources=registry_authority.catalogues.sources,
            source_payloads=_with_input_line(payloads, layout, line, ""),
        )
