"""Shape + legal-grounding tests for the censo schema extension.

Every censo-derived field that drives a downstream calculation MUST
declare ``legal_refs`` pointing to a primary BOE source.
"""

from __future__ import annotations

import pytest

from ...calculations.registry.tests.published_authority import published_legal_reference
from ..schema import ProfileSchemaDefinition
from ._schema_loader_fixtures import function_scoped_schema

__all__ = ["function_scoped_schema"]

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


CENSO_DERIVED_FIELDS: tuple[tuple[str, str], ...] = (
    ("contact", "fiscal_address_cadastral_reference"),
    ("censo", "activity_start_date"),
    ("censo", "activity_end_date"),
    ("vivienda_office", "total_m2"),
    ("vivienda_office", "office_m2"),
    ("activities", "iae_epigraph"),
)


def _field(schema: ProfileSchemaDefinition, path: tuple[str, str]):
    """Wrap the dotted-path lookup so tests can pass a typed tuple."""

    return schema.field(".".join(path))


def _published_legal_ids(candidates: set[str]) -> set[str]:
    """Return the candidates the published authority declares; an absent id refuses."""
    return {reference_id for reference_id in candidates if published_legal_reference(reference_id).id == reference_id}


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
    expected_refs = {"ley-35-2006:art-30"}
    for field_key in ("total_m2", "office_m2"):
        field = _field(schema, ("vivienda_office", field_key))
        assert field.type.value == "decimal"
        refs = set(field.legal_refs)
        assert refs == expected_refs
        assert refs <= _published_legal_ids(refs)


def test_selected_censo_profile_refs_resolve_against_catalogue(
    schema: ProfileSchemaDefinition,
) -> None:
    """Selected censo-derived profile fields carry canonical LegalReference ids."""
    expected = {
        "contact.fiscal_address_cadastral_reference": {"rdleg-1-2004:art-6.3"},
        "censo.activity_start_date": {"rd-1065-2007:art-9"},
        "censo.activity_end_date": {"rd-1065-2007:art-11"},
    }

    for field_path, expected_refs in expected.items():
        refs = set(schema.field(field_path).legal_refs)
        assert refs == expected_refs
        assert refs <= _published_legal_ids(refs)


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
    assert expected_refs <= _published_legal_ids(expected_refs)
