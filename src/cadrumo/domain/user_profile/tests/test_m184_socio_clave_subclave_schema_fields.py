"""Schema coverage for the Modelo 184 socio (member, clave, subclave) facts.

Grounds the governing row-shape decision's profile-schema half: the socio record
repeats per (member, clave, subclave), and carries a set of fields whose
applicability is conditional on the declared clave/subclave. This module
pins the fields exist, are grounded, and resolve in all four shipped
languages -- the defect the standing translation-honesty rule targets is a
field added to the TOML with no catalogue entry, which silently renders its
(often Spanish) schema description as a fallback in every language.
"""

from __future__ import annotations

import pytest

from ....core.config import override_settings
from ..labels import profile_field_label
from ..schema import ProfileFieldType, ProfileSchemaDefinition
from ._schema_loader_fixtures import legal_ids_fixture, module_scoped_schema

__all__ = ["legal_ids_fixture", "module_scoped_schema"]

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_SECTION_KEY = "attribution_entity_socios"

# Every field this schema coverage adds. Excludes the clave-A reducción
# (blocked pending its own citation research), provisiones-gastos-dificil-
# justificacion (computed, not collected) and any clave-E eligibility fact
# (out of scope, tracked gap).
_NEW_FIELD_KEYS = (
    "clave",
    "subclave",
    "codigo_provincia",
    "miembro_a_31_diciembre",
    "dias_miembro",
    "domicilio_fiscal",
    "naturaleza_inmueble",
    "situacion_inmueble",
    "referencia_catastral",
    "clave_declarado",
    "porcentaje_titularidad_inmueble",
    "dias_arrendamiento",
    "reduccion",
    "rendimiento_neto_previo_eo",
    "rendimiento_neto_minorado_agricola_eo",
)

_LANGUAGES = ("es", "en", "ca", "hu")


def test_every_new_field_is_declared_on_the_socios_section(schema: ProfileSchemaDefinition) -> None:
    section = schema.section(_SECTION_KEY)
    declared = {field.key for field in section.fields}

    assert set(_NEW_FIELD_KEYS) <= declared


@pytest.mark.parametrize("field_key", _NEW_FIELD_KEYS)
def test_new_field_label_resolves_in_every_shipped_language(
    schema: ProfileSchemaDefinition,
    field_key: str,
) -> None:
    """Every new field's label is real in es/en/ca/hu, not a fallback echo.

    The defect this pins: a field added to the schema TOML without a
    catalogue entry falls back to the (often long, mixed-language) schema
    ``description`` in every language, which is truthful but not a
    translation. Asserting the four renderings differ from each other AND
    from the raw description is what tells them apart from that fallback.
    """
    section = schema.section(_SECTION_KEY)
    field = next(candidate for candidate in section.fields if candidate.key == field_key)

    rendered: dict[str, str] = {}
    for locale in _LANGUAGES:
        with override_settings(cadrumo_output_language=locale):
            rendered[locale] = profile_field_label(_SECTION_KEY, field)

    for locale, label in rendered.items():
        assert label != field.description, (
            f"{_SECTION_KEY}.{field_key} label under {locale!r} echoed the schema "
            "description -- the catalogue key is missing or untranslated"
        )
        assert label, f"{_SECTION_KEY}.{field_key} label under {locale!r} is empty"

    # es, en, ca and hu are four genuinely distinct languages here, so a
    # translated label set has no duplicate strings across all four.
    assert len(set(rendered.values())) == len(rendered), (
        f"{_SECTION_KEY}.{field_key} rendered the same label under two different languages: {rendered!r}"
    )


def test_clave_and_subclave_enums_match_the_socio_records_own_field_text(
    schema: ProfileSchemaDefinition,
) -> None:
    """Grounded against the SOCIO record's own clave/subclave tables (positions 93-95),
    never the entidad record's lookalike clave-A subclave table at a different byte
    range (a distinct lookalike-table hazard).
    """
    clave = schema.field(f"{_SECTION_KEY}.clave")
    subclave = schema.field(f"{_SECTION_KEY}.subclave")

    assert clave.type is ProfileFieldType.ENUM
    assert set(clave.enum_values) == {"A", "C", "D", "E", "F", "G", "I", "J", "K"}
    assert clave.required is True

    assert subclave.type is ProfileFieldType.ENUM
    assert set(subclave.enum_values) == {"01", "02", "03", "04", "05", "06"}
    assert subclave.required is False


def test_clave_c_inmueble_subblock_fields_are_declared_and_optional(
    schema: ProfileSchemaDefinition,
) -> None:
    inmueble_fields = (
        "naturaleza_inmueble",
        "situacion_inmueble",
        "referencia_catastral",
        "clave_declarado",
        "porcentaje_titularidad_inmueble",
        "dias_arrendamiento",
    )
    for field_key in inmueble_fields:
        field = schema.field(f"{_SECTION_KEY}.{field_key}")
        assert field.required is False, f"{field_key} must stay optional -- it is clave-C conditional"


def test_reduccion_field_cites_both_clave_c_and_clave_d_provisions(
    schema: ProfileSchemaDefinition,
    legal_ids: frozenset[str],
) -> None:
    """The shared REDUCCIÓN field (diseño positions 109-119) covers clave C
    (LIRPF art. 23) and clave D (LIRPF art. 32.1); the clave-A branch of this
    same physical field is deliberately excluded pending its own blocked
    legal citation.
    """
    field = schema.field(f"{_SECTION_KEY}.reduccion")

    assert field.type is ProfileFieldType.MONEY
    expected_refs = {"ley-35-2006:art-23", "ley-35-2006:art-32", "orden-hap-2250-2015:art-3"}
    assert set(field.legal_refs) == expected_refs
    assert expected_refs <= legal_ids


def test_clave_d_subclave_rendimiento_neto_fields_are_money_and_optional(
    schema: ProfileSchemaDefinition,
) -> None:
    for field_key in ("rendimiento_neto_previo_eo", "rendimiento_neto_minorado_agricola_eo"):
        field = schema.field(f"{_SECTION_KEY}.{field_key}")
        assert field.type is ProfileFieldType.MONEY
        assert field.required is False
