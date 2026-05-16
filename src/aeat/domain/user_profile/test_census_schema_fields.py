"""Shape + legal-grounding tests for the census schema extension.

Backs W85.S2349 census-sync wave. Every census-derived field that
drives a downstream calculation MUST declare ``legal_refs`` pointing
to a primary BOE source per the ADR amendment.
"""

from __future__ import annotations

import pytest

from . import ProfileSchemaDefinition, load_user_profile_schema

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


CENSUS_DERIVED_FIELDS: tuple[tuple[str, str], ...] = (
    ("contact", "fiscal_address_cadastral_reference"),
    ("contact", "fiscal_address_is_habitual_vivienda"),
    ("census", "activity_start_date"),
    ("census", "activity_end_date"),
    ("census", "establecimiento_type"),
    ("census", "elected_withholding_pct"),
    ("vivienda_office", "total_m2"),
    ("vivienda_office", "office_m2"),
    ("activities", "iae_epigraph"),
)


@pytest.fixture
def schema() -> ProfileSchemaDefinition:
    return load_user_profile_schema()


def _field(schema: ProfileSchemaDefinition, path: tuple[str, str]):
    """Wrap the dotted-path lookup so tests can pass a typed tuple."""

    return schema.field(".".join(path))


def test_every_census_derived_field_declares_legal_refs(
    schema: ProfileSchemaDefinition,
) -> None:
    """The W85 ADR amendment requires every census-derived field to
    declare ``legal_refs`` pointing to a primary BOE source. The
    validator added in this wave fails CI if a field drifts."""

    for section_key, field_key in CENSUS_DERIVED_FIELDS:
        field = _field(schema, (section_key, field_key))
        assert field.legal_refs, (
            f"census-derived field {section_key}.{field_key} must declare legal_refs"
        )


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
    for field_key in ("total_m2", "office_m2"):
        field = _field(schema, ("vivienda_office", field_key))
        assert field.type.value == "decimal"
        assert "Art. 30.2 rule 5" in " ".join(field.legal_refs)


def test_census_elected_withholding_enum_covers_15_7_1_pct(
    schema: ProfileSchemaDefinition,
) -> None:
    """The IRPF withholding rate enum on the 036 census carries the
    three legally-defined values: 15 percent standard, 7 percent
    nuevos-profesionales, 1 percent modulos transport."""

    field = _field(schema, ("census", "elected_withholding_pct"))
    assert set(field.enum_values) == {"15", "7", "1"}
    refs = " ".join(field.legal_refs)
    assert "Art. 101.5" in refs
    assert "Art. 95" in refs


def test_census_establecimiento_type_enum_covers_propio_arrendado_cedido(
    schema: ProfileSchemaDefinition,
) -> None:
    """The establecimiento type enum carries the three forms the 036
    census declares for the business establishment."""

    field = _field(schema, ("census", "establecimiento_type"))
    assert set(field.enum_values) == {"propio", "arrendado", "cedido_gratuitamente"}


def test_iae_epigraph_is_wired_to_model_selectors(
    schema: ProfileSchemaDefinition,
) -> None:
    """Closes the dead-field bug surfaced by the W85 mapping: the
    activities.iae_epigraph field had no model_selectors so it never
    reached AutonomoProfile or the 036 binding layer."""

    field = _field(schema, ("activities", "iae_epigraph"))
    assert field.model_selectors
    assert any("iae_epigraph" in sel for sel in field.model_selectors)
