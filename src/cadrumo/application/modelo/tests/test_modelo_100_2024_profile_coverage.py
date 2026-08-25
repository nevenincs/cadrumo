"""Modelo 100 2024 profile-backed personal/family registry coverage."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

import pytest

from ....core import BindingSourceKind
from ....core.resources import resources
from ....domain.calculations.registry import InputKind, RegistrySnapshot
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, UserProfileRecord
from ....domain.user_profile.loader import load_user_profile_schema
from ....domain.user_profile.registry_contract import profile_binding_selectors
from .._profile_binding import profile_fact_index, resolve_profile_binding_value

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE_ID = "10000000-0000-4000-8000-000000000366"
_BUCKET_ID = _PROFILE_ID
_CLOCK = datetime(2026, 7, 1, 12, 0, 0, tzinfo=UTC)

_CASILLA_TO_BINDING: Mapping[str, str] = {
    "DPNIF_D": "renta-2024-profile-tax-id",
    "DP_APENOM_D": "renta-2024-profile-display-name",
    "ZCCAD": "renta-2024-profile-tax-residence-ccaa",
    "TIPOTRIBUTACION": "renta-2024-profile-declaration-type",
    "SEXO_D": "renta-2024-profile-taxpayer-sex",
    "ECIVIL": "renta-2024-profile-marital-status",
    "DPFNAC_D": "renta-2024-profile-taxpayer-birth-date",
    "DPNIF_C": "renta-2024-profile-spouse-tax-id",
    "DP_APENOM_C": "renta-2024-profile-spouse-display-name",
    "DPFNAC_C": "renta-2024-profile-spouse-birth-date",
    "SEXO_C": "renta-2024-profile-spouse-sex",
    "DPGMIN_D": "renta-2024-profile-taxpayer-disability-grade",
    "DECFAL": "renta-2024-profile-taxpayer-death-date",
    "DPGMIN_C": "renta-2024-profile-spouse-disability-grade",
    "NORESIDENTE": "renta-2024-profile-spouse-non-resident-irpf",
    "RESIDENTEUE": "renta-2024-profile-spouse-eu-eea-resident",
    "ZRUE2": "renta-2024-profile-spouse-eu-eea-country",
    "HIJOSUE": "renta-2024-profile-family-descendants-eu-eea-deduction",
    "PH18": "renta-2024-profile-family-minor-children-in-unit",
    "NIFDLG": "renta-2024-family-descendant-tax-id",
    "APENOMDLG": "renta-2024-family-descendant-display-name",
    "FNACDLG": "renta-2024-family-descendant-birth-date",
    "MINUSDLG": "renta-2024-family-descendant-disability-grade",
    "FALLDLG": "renta-2024-family-descendant-death-date",
    "DNIASDLG": "renta-2024-family-ascendant-tax-id",
    "APENOMDLG_ASC": "renta-2024-family-ascendant-display-name",
    "ANOASDLG": "renta-2024-family-ascendant-birth-date",
    "PCTMINASDLG": "renta-2024-family-ascendant-disability-grade",
    "CONVASDLG": "renta-2024-family-ascendant-cohabiting-descendant-count",
    "FALLASDLG": "renta-2024-family-ascendant-death-date",
}

_SCALAR_PROFILE_BINDING_VALUES: Mapping[str, object] = {
    "renta-2024-profile-tax-id": "12345678Z",
    "renta-2024-profile-tax-residence-ccaa": "madrid",
    "renta-2024-profile-declaration-type": Decimal("2"),
    "renta-2024-profile-taxpayer-sex": "H",
    "renta-2024-profile-marital-status": Decimal("2"),
    "renta-2024-profile-taxpayer-birth-date": date(1980, 3, 15),
    "renta-2024-profile-spouse-tax-id": "98765432B",
    "renta-2024-profile-spouse-birth-date": date(1978, 7, 22),
    "renta-2024-profile-spouse-sex": "M",
    "renta-2024-profile-taxpayer-disability-grade": Decimal("0"),
    "renta-2024-profile-taxpayer-death-date": date(2024, 11, 3),
    "renta-2024-profile-spouse-disability-grade": Decimal("0"),
    "renta-2024-profile-spouse-non-resident-irpf": True,
    "renta-2024-profile-spouse-eu-eea-resident": True,
    "renta-2024-profile-spouse-eu-eea-country": "DE",
    "renta-2024-profile-family-descendants-eu-eea-deduction": True,
    "renta-2024-profile-family-minor-children-in-unit": False,
}

_ROW_BINDINGS: Mapping[str, tuple[str, str]] = {
    "renta-2024-family-descendant-tax-id": ("descendants", "tax_id"),
    "renta-2024-family-descendant-display-name": ("descendants", "display_name"),
    "renta-2024-family-descendant-birth-date": ("descendants", "birth_date"),
    "renta-2024-family-descendant-disability-grade": ("descendants", "disability_grade"),
    "renta-2024-family-descendant-death-date": ("descendants", "death_date"),
    "renta-2024-family-ascendant-tax-id": ("ascendants", "tax_id"),
    "renta-2024-family-ascendant-display-name": ("ascendants", "display_name"),
    "renta-2024-family-ascendant-birth-date": ("ascendants", "birth_date"),
    "renta-2024-family-ascendant-disability-grade": ("ascendants", "disability_grade"),
    "renta-2024-family-ascendant-cohabiting-descendant-count": ("ascendants", "cohabiting_descendant_count"),
    "renta-2024-family-ascendant-death-date": ("ascendants", "death_date"),
}


def _snapshot_2024() -> RegistrySnapshot:
    return resources().modelos.authority.snapshot("100", filing_year=2024, period="0A")


def _full_profile() -> UserProfileRecord:
    return UserProfileRecord(
        setup_state=ProfileSetupState.COMPLETE,
        profile_id=_PROFILE_ID,
        facts=(
            UserProfileFact(path="identity.tax_id", value="12345678Z"),
            UserProfileFact(path="identity.surnames", value="Garcia Lopez"),
            UserProfileFact(path="identity.name", value="Ana"),
            UserProfileFact(path="tax_residence.ccaa", value="madrid"),
            UserProfileFact(path="renta_filing.declaration_type", value="2"),
            UserProfileFact(path="renta_taxpayer.sex", value="H"),
            UserProfileFact(path="renta_taxpayer.marital_status", value="2"),
            UserProfileFact(path="renta_taxpayer.birth_date", value=date(1980, 3, 15)),
            UserProfileFact(path="renta_taxpayer.disability_grade", value="0"),
            UserProfileFact(path="renta_taxpayer.death_date", value=date(2024, 11, 3)),
            UserProfileFact(path="renta_spouse.tax_id", value="98765432B"),
            UserProfileFact(path="renta_spouse.surnames", value="Martinez"),
            UserProfileFact(path="renta_spouse.name", value="Carlos"),
            UserProfileFact(path="renta_spouse.birth_date", value=date(1978, 7, 22)),
            UserProfileFact(path="renta_spouse.sex", value="M"),
            UserProfileFact(path="renta_spouse.disability_grade", value="0"),
            UserProfileFact(path="renta_spouse.non_resident_irpf", value=True),
            UserProfileFact(path="renta_spouse.eu_eea_resident", value=True),
            UserProfileFact(path="renta_spouse.eu_eea_country", value="DE"),
            UserProfileFact(path="renta_family.descendants_eu_eea_deduction", value=True),
            UserProfileFact(path="renta_family.minor_children_in_unit", value=False),
        ),
        created_at=_CLOCK,
        updated_at=_CLOCK,
    )


def test_modelo_100_2024_personal_family_construct_is_profile_backed() -> None:
    snapshot = _snapshot_2024()
    construct = snapshot.constructs["renta-2024-personal-family"]
    casillas = {casilla.id: casilla for casilla in snapshot.revision.casillas}
    bindings = {binding.id: binding for binding in snapshot.revision.bindings}

    assert set(construct.casilla_ids) == set(_CASILLA_TO_BINDING)
    assert set(construct.bindings) == set(_CASILLA_TO_BINDING.values())
    for casilla_id, binding_id in _CASILLA_TO_BINDING.items():
        casilla = casillas[casilla_id]
        assert casilla.input_kind is InputKind.BOUND
        assert casilla.binding == binding_id
        binding = bindings[binding_id]
        assert binding.source is BindingSourceKind.PROFILE
        selector: Any = binding.selector
        assert selector.dictionary_field == casilla_id


def test_modelo_100_2024_profile_binding_selectors_target_real_profile_schema() -> None:
    snapshot = _snapshot_2024()
    schema = load_user_profile_schema()
    schema_selectors = {f"{section.key}.{field.key}" for section in schema.sections for field in section.fields} | {
        selector for section in schema.sections for field in section.fields for selector in field.model_selectors
    }
    bindings = {binding.id: binding for binding in snapshot.revision.bindings}

    for binding_id in _CASILLA_TO_BINDING.values():
        selectors = profile_binding_selectors(bindings[binding_id].selector)
        assert selectors, binding_id
        missing = set(selectors) - schema_selectors
        assert not missing, f"{binding_id}: selectors outside profile schema: {sorted(missing)}"


def test_modelo_100_2024_scalar_profile_values_resolve_from_real_profile_facts() -> None:
    snapshot = _snapshot_2024()
    schema = load_user_profile_schema()
    facts = profile_fact_index(_full_profile(), schema)
    bindings = {binding.id: binding for binding in snapshot.revision.bindings}

    for binding_id, expected in _SCALAR_PROFILE_BINDING_VALUES.items():
        value = resolve_profile_binding_value(bindings[binding_id], facts)
        assert value == expected, f"{binding_id}: expected {expected!r}, got {value!r}"


def test_modelo_100_2024_family_row_bindings_address_repeating_profile_collections() -> None:
    snapshot = _snapshot_2024()
    bindings = {binding.id: binding for binding in snapshot.revision.bindings}

    for binding_id, (collection, field) in _ROW_BINDINGS.items():
        selector: Any = bindings[binding_id].selector
        assert selector.profile_model == "RentaFamilyProfile"
        assert selector.collection == collection
        assert selector.field == field
        assert selector.repeating is True
