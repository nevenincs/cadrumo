"""Registry-load tests for the maritime_worker profile section.

Verifies that the committed user-profile schema TOML declares the
worker_class fact and all four supporting vessel/RETMAR facts, and that
the profile schema loads without error after the maritime_worker section
was added.
"""

from __future__ import annotations

import pytest

from aeat.domain.user_profile import ProfileFieldType, load_user_profile_schema

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


def test_user_profile_schema_loads_with_maritime_worker_section() -> None:
    schema = load_user_profile_schema()

    section_keys = {s.key for s in schema.sections}
    assert "maritime_worker" in section_keys


def test_worker_class_fact_is_enum_with_trabajador_del_mar() -> None:
    schema = load_user_profile_schema()

    field = schema.field("maritime_worker.worker_class")

    assert field.type is ProfileFieldType.ENUM
    assert "trabajador_del_mar" in field.enum_values
    assert field.required is False
    assert field.effective_dated is True
    assert "maritime_worker.worker_class" in field.schedule_predicates


def test_worker_class_carries_legal_refs_for_all_three_maritime_axes() -> None:
    schema = load_user_profile_schema()

    field = schema.field("maritime_worker.worker_class")

    # Art. 7.p) foreign-work exemption
    assert any("Art. 7.p)" in ref for ref in field.legal_refs)
    assert any("BOE-A-2006-20764" in ref for ref in field.legal_refs)
    # REBECA exemption
    assert any("BOE-A-1994-16100" in ref for ref in field.legal_refs)
    # DA 41 inactive binding and its enabling law
    assert any("DA 41" in ref for ref in field.legal_refs)
    assert any("BOE-A-2018-9268" in ref for ref in field.legal_refs)
    # RETMAR mandatory filing
    assert any("BOE-A-2015-11346" in ref for ref in field.legal_refs)


def test_vessel_flag_fact_is_enum_with_es_and_foreign() -> None:
    schema = load_user_profile_schema()

    field = schema.field("maritime_worker.vessel_flag")

    assert field.type is ProfileFieldType.ENUM
    assert "ES" in field.enum_values
    assert "foreign" in field.enum_values
    assert field.required is False
    assert any("Art. 7.p)" in ref for ref in field.legal_refs)


def test_waters_type_fact_is_enum_with_national_and_international() -> None:
    schema = load_user_profile_schema()

    field = schema.field("maritime_worker.waters_type")

    assert field.type is ProfileFieldType.ENUM
    assert "national" in field.enum_values
    assert "international" in field.enum_values
    assert field.required is False
    assert any("Art. 7.p)" in ref for ref in field.legal_refs)


def test_vessel_registry_fact_is_enum_covering_rebeca_variants() -> None:
    schema = load_user_profile_schema()

    field = schema.field("maritime_worker.vessel_registry")

    assert field.type is ProfileFieldType.ENUM
    assert "REBECA" in field.enum_values
    assert "rebeca_eu_eea" in field.enum_values
    assert "scheduled_canary_route" in field.enum_values
    assert field.required is False
    assert any("BOE-A-1994-16100" in ref for ref in field.legal_refs)


def test_retmar_registered_fact_is_boolean_with_schedule_predicate() -> None:
    schema = load_user_profile_schema()

    field = schema.field("maritime_worker.retmar_registered")

    assert field.type is ProfileFieldType.BOOLEAN
    assert field.required is False
    assert field.effective_dated is True
    assert "maritime_worker.retmar_registered" in field.schedule_predicates
    assert any("BOE-A-2015-11346" in ref for ref in field.legal_refs)


def test_no_da24_reference_in_maritime_worker_section() -> None:
    """DA 24 LIRPF is a 2015 withholding transition rule and must not
    appear anywhere in the maritime worker profile facts."""
    schema = load_user_profile_schema()

    section = schema.section("maritime_worker")
    for field in section.fields:
        for ref in field.legal_refs:
            assert "DA 24" not in ref, (
                f"field {field.key!r} references DA 24 LIRPF which has no maritime content"
            )
        assert "DA 24" not in field.description, (
            f"field {field.key!r} description mentions DA 24 LIRPF"
        )
