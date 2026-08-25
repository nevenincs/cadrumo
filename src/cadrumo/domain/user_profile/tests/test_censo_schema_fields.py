"""Shape + legal-grounding tests for the censo schema extension.

Every censo-derived field that drives a downstream calculation MUST
declare ``legal_refs`` pointing to a primary BOE source.
"""

from __future__ import annotations

import pytest

from ....core.resources import resources
from ..schema import ProfileSchemaDefinition
from ._schema_loader_fixtures import function_scoped_schema  # noqa: F401

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


CENSO_DERIVED_FIELDS: tuple[tuple[str, str], ...] = (
    ("contact", "fiscal_address_cadastral_reference"),
    ("contact", "fiscal_address_is_habitual_vivienda"),
    ("censo", "activity_start_date"),
    ("censo", "activity_end_date"),
    ("censo", "establecimiento_type"),
    ("censo", "elected_withholding_pct"),
    ("vivienda_office", "total_m2"),
    ("vivienda_office", "office_m2"),
    ("activities", "iae_epigraph"),
)


def _field(schema: ProfileSchemaDefinition, path: tuple[str, str]):
    """Wrap the dotted-path lookup so tests can pass a typed tuple."""

    return schema.field(".".join(path))


def _legal_ids() -> set[str]:
    catalogues = resources().modelos.authority.catalogues
    return set(catalogues.legal)


def test_every_censo_derived_field_declares_legal_refs(
    schema: ProfileSchemaDefinition,
) -> None:
    """Every censo-derived field must declare ``legal_refs`` pointing
    to a primary BOE source. The schema-load validator fails CI if a
    field drifts."""

    for section_key, field_key in CENSO_DERIVED_FIELDS:
        field = _field(schema, (section_key, field_key))
        assert field.legal_refs, f"censo-derived field {section_key}.{field_key} must declare legal_refs"


def test_vivienda_office_section_carries_raw_m2_inputs(
    schema: ProfileSchemaDefinition,
) -> None:
    """The vivienda_office section stores the raw m2 inputs that derive
    the office-afectacion ratio per LIRPF Art. 30.2 rule 5. The
    engine applies the 0.30 suministros multiplier at calculation
    time; the schema MUST carry both raw inputs separately."""

    section = schema.section("vivienda_office")
    field_keys = {field.key for field in section.fields}
    assert {"total_m2", "office_m2"}.issubset(field_keys)
    legal_ids = _legal_ids()
    expected_refs = {"ley-35-2006:art-30"}
    for field_key in ("total_m2", "office_m2"):
        field = _field(schema, ("vivienda_office", field_key))
        assert field.type.value == "decimal"
        refs = set(field.legal_refs)
        assert refs == expected_refs
        assert refs <= legal_ids


def test_selected_censo_profile_refs_resolve_against_catalogue(
    schema: ProfileSchemaDefinition,
) -> None:
    """Selected censo-derived profile fields carry canonical LegalReference ids."""
    legal_ids = _legal_ids()
    expected = {
        "contact.fiscal_address_cadastral_reference": {"rdleg-1-2004:art-6.3"},
        "contact.fiscal_address_is_habitual_vivienda": {"ley-35-2006:da-23", "ley-35-2006:art-30"},
        "censo.activity_start_date": {"rd-1065-2007:art-9"},
        "censo.activity_end_date": {"rd-1065-2007:art-11"},
    }

    for field_path, expected_refs in expected.items():
        refs = set(schema.field(field_path).legal_refs)
        assert refs == expected_refs
        assert refs <= legal_ids


def test_censo_elected_withholding_enum_covers_15_7_1_pct(
    schema: ProfileSchemaDefinition,
) -> None:
    """The IRPF withholding rate enum on the 036 censo carries the
    three legally-defined values: 15 percent standard, 7 percent
    nuevos-profesionales, 1 percent modulos transport."""

    field = _field(schema, ("censo", "elected_withholding_pct"))
    assert set(field.enum_values) == {"15", "7", "1"}
    expected_refs = {"ley-35-2006:art-101", "rd-439-2007:art-95", "orden-hac-1425-2025:art-4"}
    assert set(field.legal_refs) == expected_refs
    assert expected_refs <= _legal_ids()


def test_censo_establecimiento_type_enum_covers_propio_arrendado_cedido(
    schema: ProfileSchemaDefinition,
) -> None:
    """The establecimiento type enum carries the three forms the 036
    censo declares for the business establishment."""

    field = _field(schema, ("censo", "establecimiento_type"))
    assert set(field.enum_values) == {"propio", "arrendado", "cedido_gratuitamente"}
    expected_refs = {"ley-35-2006:art-28", "ley-35-2006:art-29", "ley-35-2006:art-30"}
    assert set(field.legal_refs) == expected_refs
    assert expected_refs <= _legal_ids()


def test_iae_epigraph_is_wired_to_model_selectors(
    schema: ProfileSchemaDefinition,
) -> None:
    """Closes the dead-field bug on the censo mapping: the
    activities.iae_epigraph field had no model_selectors so it never
    reached TaxpayerProfile or the 036 binding layer."""

    field = _field(schema, ("activities", "iae_epigraph"))
    assert field.model_selectors
    assert any("iae_epigraph" in sel for sel in field.model_selectors)
    expected_refs = {"rdleg-1175-1990:art-unico"}
    assert set(field.legal_refs) == expected_refs
    assert expected_refs <= _legal_ids()
