"""Registry-load and binding-integrity tests for the maritime worker exemption axis.

Covers two surfaces:
- user_profile/schema.toml: maritime_worker section with worker_class and
  vessel/RETMAR supporting facts (contract profile-load tests).
- categories/trabajador_del_mar.toml: three exemption binding entries each
  carrying canonical legal catalogue ids (contract integrity tests).
"""

from __future__ import annotations

import tomllib
from typing import Any, TypedDict

import pytest

from .....core.resources.bundled_data import bundled_path
from ....user_profile.loader import load_user_profile_schema
from ....user_profile.schema import ProfileFieldType
from ..legal import verify_legal_catalogue
from ._registry_schema_support import _committed_registry_tree

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


class BindingEntry(TypedDict, total=False):
    id: str
    status: str
    annual_cap_eur: str
    exempt_fraction: str
    formula: str
    legal_refs: list[str]


def _load_trabajador_del_mar_bindings() -> list[BindingEntry]:
    path = bundled_path("registry", "aeat", "categories", "trabajador_del_mar.toml")
    with path.open("rb") as fh:
        data: dict[str, Any] = tomllib.load(fh)
    raw_bindings = data.get("exemption_bindings")
    assert isinstance(raw_bindings, list), "trabajador_del_mar.toml must declare [[exemption_bindings]]"

    bindings: list[BindingEntry] = []
    for raw_binding in raw_bindings:
        assert isinstance(raw_binding, dict), "each exemption binding must be a TOML table"
        binding: BindingEntry = {}
        if (raw_id := raw_binding.get("id")) is not None:
            assert isinstance(raw_id, str), "binding id must be a string"
            binding["id"] = raw_id
        if (status := raw_binding.get("status")) is not None:
            assert isinstance(status, str), "binding status must be a string"
            binding["status"] = status
        if (annual_cap_eur := raw_binding.get("annual_cap_eur")) is not None:
            assert isinstance(annual_cap_eur, str), "annual_cap_eur must be stored as a string"
            binding["annual_cap_eur"] = annual_cap_eur
        if (exempt_fraction := raw_binding.get("exempt_fraction")) is not None:
            assert isinstance(exempt_fraction, str), "exempt_fraction must be stored as a string"
            binding["exempt_fraction"] = exempt_fraction
        if (formula := raw_binding.get("formula")) is not None:
            assert isinstance(formula, str), "binding formula must be a string"
            binding["formula"] = formula
        if (legal_refs := raw_binding.get("legal_refs")) is not None:
            assert isinstance(legal_refs, list), "legal_refs must be a list of legal catalogue ids"
            for legal_ref in legal_refs:
                assert isinstance(legal_ref, str), "legal_refs entries must be strings"
            binding["legal_refs"] = legal_refs
        bindings.append(binding)
    return bindings


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

    assert set(field.legal_refs) == {
        "ley-35-2006:art-7",
        "ley-19-1994:art-75",
        "ley-35-2006:da-41",
        "ley-35-2006:art-96",
    }


def test_vessel_flag_fact_is_enum_with_es_and_foreign() -> None:
    schema = load_user_profile_schema()

    field = schema.field("maritime_worker.vessel_flag")

    assert field.type is ProfileFieldType.ENUM
    assert "ES" in field.enum_values
    assert "foreign" in field.enum_values
    assert field.required is False
    assert field.legal_refs == ("ley-35-2006:art-7",)


def test_waters_type_fact_is_enum_with_national_and_international() -> None:
    schema = load_user_profile_schema()

    field = schema.field("maritime_worker.waters_type")

    assert field.type is ProfileFieldType.ENUM
    assert "national" in field.enum_values
    assert "international" in field.enum_values
    assert field.required is False
    assert field.legal_refs == ("ley-35-2006:art-7",)


def test_vessel_registry_fact_is_enum_covering_rebeca_variants() -> None:
    schema = load_user_profile_schema()

    field = schema.field("maritime_worker.vessel_registry")

    assert field.type is ProfileFieldType.ENUM
    assert "REBECA" in field.enum_values
    assert "rebeca_eu_eea" in field.enum_values
    assert "scheduled_canary_route" in field.enum_values
    assert field.required is False
    assert field.legal_refs == ("ley-19-1994:art-75",)


def test_retmar_registered_fact_is_boolean_with_schedule_predicate() -> None:
    schema = load_user_profile_schema()

    field = schema.field("maritime_worker.retmar_registered")

    assert field.type is ProfileFieldType.BOOLEAN
    assert field.required is False
    assert field.effective_dated is True
    assert "maritime_worker.retmar_registered" in field.schedule_predicates
    assert field.legal_refs == ("ley-35-2006:art-96",)


def test_no_da24_reference_in_maritime_worker_section() -> None:
    """DA 24 LIRPF is a 2015 withholding transition rule and must not
    appear anywhere in the maritime worker profile facts."""
    schema = load_user_profile_schema()

    section = schema.section("maritime_worker")
    for field in section.fields:
        for ref in field.legal_refs:
            assert "DA 24" not in ref, f"field {field.key!r} references DA 24 LIRPF which has no maritime content"
        assert "DA 24" not in field.description, f"field {field.key!r} description mentions DA 24 LIRPF"


# --- contract: binding-entry integrity tests ---


def test_trabajador_del_mar_toml_declares_three_binding_entries() -> None:
    bindings = _load_trabajador_del_mar_bindings()

    ids = [b.get("id") for b in bindings]
    assert "art-7p-foreign-work" in ids
    assert "rebeca-50pct" in ids
    assert "da41-tuna-fleet-inactive" in ids
    assert len(ids) == 3, f"expected exactly 3 binding entries, got {ids}"


def test_art7p_binding_has_required_fields_and_legal_refs() -> None:
    bindings = _load_trabajador_del_mar_bindings()
    binding = next(b for b in bindings if b.get("id") == "art-7p-foreign-work")

    assert binding.get("status") == "active"
    assert binding.get("annual_cap_eur") == "60100"
    assert "formula" in binding

    assert binding.get("legal_refs") == ["ley-35-2006:art-7"]


def test_rebeca_binding_has_required_fields_and_legal_refs() -> None:
    bindings = _load_trabajador_del_mar_bindings()
    binding = next(b for b in bindings if b.get("id") == "rebeca-50pct")

    assert binding.get("status") == "active"
    assert binding.get("exempt_fraction") == "0.50"

    assert binding.get("legal_refs") == ["ley-19-1994:art-75"]


def test_da41_binding_is_inactive_and_has_legal_refs() -> None:
    bindings = _load_trabajador_del_mar_bindings()
    binding = next(b for b in bindings if b.get("id") == "da41-tuna-fleet-inactive")

    assert binding.get("status") == "inactive_pending_eu_clearance", (
        "DA 41 binding must be marked inactive_pending_eu_clearance; "
        "it must not be treated as active (AEAT 2024 confirms non-applicability)"
    )
    assert binding.get("exempt_fraction") == "0.50"

    assert binding.get("legal_refs") == ["ley-35-2006:da-41"]


def test_binding_legal_refs_resolve_against_catalogue_and_corpus() -> None:
    _, catalogues = _committed_registry_tree()
    refs = {legal_ref for binding in _load_trabajador_del_mar_bindings() for legal_ref in binding.get("legal_refs", [])}

    assert refs == {
        "ley-35-2006:art-7",
        "ley-19-1994:art-75",
        "ley-35-2006:da-41",
    }
    assert refs <= set(catalogues.legal)
    verify_legal_catalogue({ref: catalogues.legal[ref] for ref in refs}, source_root=bundled_path())


def test_no_da24_reference_in_trabajador_del_mar_toml() -> None:
    """DA 24 LIRPF has zero maritime content and must not appear in any binding."""
    bindings = _load_trabajador_del_mar_bindings()

    for binding in bindings:
        bid = binding.get("id", "unknown")
        for ref in binding.get("legal_refs", []):
            assert "DA 24" not in ref, f"binding {bid!r} legal_ref references DA 24 LIRPF"


def test_all_binding_entries_carry_nonempty_legal_refs() -> None:
    bindings = _load_trabajador_del_mar_bindings()

    for binding in bindings:
        bid = binding.get("id", "unknown")
        legal_refs = binding.get("legal_refs")
        assert isinstance(legal_refs, list) and legal_refs, f"binding {bid!r} must declare legal_refs ids"
        for ref in legal_refs:
            assert isinstance(ref, str) and ref, f"binding {bid!r} has an empty legal_ref id"
