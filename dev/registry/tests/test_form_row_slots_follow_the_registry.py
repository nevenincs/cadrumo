"""The row counts domain models read must be the rows each Modelo 303 revision declares."""

from __future__ import annotations

import re

import pytest

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.facts.payloads import MappingFactPayload

from ..compiler.authority import compiled_bundled_authority

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_PROJECTED_ROW = re.compile(r'projection_kind = "(?P<kind>\w+)"\s+(?:cohort = "\w+"\s+)?slot = (?P<slot>\d+)')


def _declared_slots_by_revision(kind: str) -> dict[str, int]:
    revisions = bundled_path("registry", "aeat", "modelos", "303", "revisions")
    declared: dict[str, int] = {}
    for revision in revisions.iterdir():
        slots = [
            int(match["slot"])
            for path in revision.rglob("*.toml")
            for match in _PROJECTED_ROW.finditer(path.read_text(encoding="utf-8"))
            if match["kind"] == kind
        ]
        if slots:
            declared[revision.name] = max(slots)
    return declared


@pytest.mark.parametrize(
    ("key", "kind"),
    [
        ("m303.differentiated.row_slots", "m303_differentiated_deduction"),
        ("m303.prorrata.activity_slots", "m303_prorrata_activity"),
        ("m303.exonerado_390.activity_slots", "m303_exonerado_390_activity"),
    ],
)
def test_the_row_count_fact_is_what_every_revision_declares(key: str, kind: str) -> None:
    entries = _entries()

    declared = _declared_slots_by_revision(kind)

    assert declared
    assert set(declared.values()) == {int(entries[key])}


def _entries() -> dict[str, str]:
    payload = compiled_bundled_authority().catalogues.facts.facts["form-row-codes"].variants[0].payload
    assert isinstance(payload, MappingFactPayload)
    assert all(isinstance(entry.key, str) and isinstance(entry.value, str) for entry in payload.entries)
    return {
        entry.key: entry.value
        for entry in payload.entries
        if isinstance(entry.key, str) and isinstance(entry.value, str)
    }


def _all_field_values(name: str) -> dict[str, set[int]]:
    revisions = bundled_path("registry", "aeat", "modelos", "303", "revisions")
    pattern = re.compile(rf"^{name} = (\d+)", re.MULTILINE)
    found: dict[str, set[int]] = {}
    for revision in revisions.iterdir():
        values = {
            int(match)
            for path in revision.rglob("*.toml")
            if "regimen" in path.name
            for match in pattern.findall(path.read_text(encoding="utf-8"))
        }
        if values:
            found[revision.name] = values
    return found


def test_the_sub_indices_are_what_the_later_editions_declare() -> None:
    declared = _all_field_values("sub_index")

    assert declared
    assert all(
        values == {int(code) for code in _entries()["m303.dp30302.sub_indices"].split(",")}
        for values in declared.values()
    )


def test_the_module_rows_are_what_every_edition_declares() -> None:
    declared = _all_field_values("module_order")

    assert declared
    assert {max(values) for values in declared.values()} == {int(_entries()["m303.orden.modules_per_activity"])}


def test_a_page_holds_the_activities_every_edition_declares_and_the_pages_make_the_limit() -> None:
    entries = _entries()
    declared = _declared_slots_by_revision("m303_regimen_simplificado_activity")

    assert set(declared.values()) == {int(entries["m303.dp30302.activities_per_record"])}
    assert int(entries["m303.dp30302.activities_per_record"]) * int(entries["m303.dp30302.records"]) == int(
        entries["m303.dp30302.activities_per_kind"]
    )


def test_the_epigraph_digits_fill_the_field_the_record_declares() -> None:
    entries = _entries()
    revisions = bundled_path("registry", "aeat", "modelos", "303", "revisions")
    field = re.compile(r'length = (\d+)(?:(?!\[\[).)*?field = "iae_epigrafe"', re.DOTALL)
    lengths = {
        int(match)
        for revision in revisions.iterdir()
        for path in revision.rglob("*regimen*.toml")
        for match in field.findall(path.read_text(encoding="utf-8"))
    }

    assert lengths == {
        int(entries["m303.dp30302.iae_whole_digits"]) + int(entries["m303.dp30302.iae_fractional_digits"])
    }


_LAYOUT_LENGTH = re.compile(
    r'^length = (?P<length>\d+)\n(?:kind = "\w+"\n)(?:producer_key|binding) = "(?P<key>[^"]+)"', re.MULTILINE
)


def _layout_lengths(modelo: str, field_key: str) -> set[int]:
    revisions = bundled_path("registry", "aeat", "modelos", modelo, "revisions")
    return {
        int(match["length"])
        for path in revisions.rglob("export/*.toml")
        for match in _LAYOUT_LENGTH.finditer(path.read_text(encoding="utf-8"))
        if match["key"] == field_key
    }


@pytest.mark.parametrize(
    ("key", "modelo", "field_key"),
    [
        ("m296.telefono_max", "296", "m296.dec.telefono"),
        ("m296.numero_total_perceptores_max", "296", "m296.dec.numero_total_de_perceptores"),
        ("m347.inmueble.referencia_catastral_max", "347", "modelo-347-inmueble-row-referencia-catastral"),
        ("m360.numero_registro_anterior_max", "360", "m360.solicitud.numero_registro_declaracion_anterior"),
        ("m360.full_name_max", "360", "m360.representante.full_name"),
        ("m360.email_max", "360", "m360.solicitante.email"),
        ("m360.email_max", "360", "m360.representante.email"),
        ("m360.phone_max", "360", "m360.solicitante.phone"),
        ("m360.address.street_type_max", "360", "m360.solicitante.domicilio.tipo_via"),
        ("m360.address.street_name_max", "360", "m360.solicitante.domicilio.nombre_via"),
        ("m360.address.number_type_max", "360", "m360.solicitante.domicilio.tipo_numeracion"),
        ("m360.address.number_qualifier_max", "360", "m360.solicitante.domicilio.calificador_numero"),
        ("m360.address.block_max", "360", "m360.solicitante.domicilio.bloque"),
        ("m360.address.portal_max", "360", "m360.solicitante.domicilio.portal"),
        ("m360.address.staircase_max", "360", "m360.solicitante.domicilio.escalera"),
        ("m360.address.floor_max", "360", "m360.solicitante.domicilio.planta"),
        ("m360.address.door_max", "360", "m360.solicitante.domicilio.puerta"),
        ("m360.address.complement_max", "360", "m360.solicitante.domicilio.datos_complementarios"),
        ("m360.address.locality_max", "360", "m360.solicitante.domicilio.localidad"),
        ("m360.address.municipality_max", "360", "m360.solicitante.domicilio.nombre_municipio"),
        ("m360.address.province_max", "360", "m360.solicitante.domicilio.provincia"),
        ("m360.address.house_number_digits", "360", "m360.solicitante.domicilio.numero_casa"),
        ("m360.address.postal_code_digits", "360", "m360.solicitante.domicilio.codigo_postal"),
        ("m360.po_box.number_digits", "360", "m360.solicitante.apartado_correos.numero"),
        ("m360.foreign_address.street_max", "360", "m360.solicitante.foreign_address.street"),
        ("m360.foreign_address.city_max", "360", "m360.solicitante.foreign_address.city"),
        ("m360.foreign_address.postal_code_max", "360", "m360.solicitante.foreign_address.postal_code"),
        ("m360.foreign_address.region_max", "360", "m360.solicitante.foreign_address.region"),
    ],
)
def test_a_declared_width_is_the_published_layout_s_length(key: str, modelo: str, field_key: str) -> None:
    assert _layout_lengths(modelo, field_key) == {int(_entries()[key])}
