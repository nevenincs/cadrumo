"""Modelo 100 profile-backed personal/family registry coverage on every edition that carries it."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

import pytest

from cadrumo.domain.calculations.registry.tests.authored_editions import authored_revisions_where
from cadrumo.domain.user_profile.values import create_user_profile_record as _create_profile_record_for_test

from ....core.aggregation import BindingSourceKind
from ....domain.calculations.registry.schema import RegistrySnapshot
from ....domain.calculations.registry.schema_input_kind import InputKind
from ....domain.calculations.registry.tests.published_authority import (
    PublishedGovernedFactSource,
    published_profile_schema,
    published_snapshot,
)
from ....domain.calculations.registry.tests.published_authority import (
    leased_profile_create_context as _profile_creation_context_for_test,
)
from ....domain.user_profile.registry_contract import profile_binding_selectors
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, UserProfileRecord
from ...user_profile.projections import profile_fact_index
from ..profile_binding import resolve_profile_binding_value

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("authority_operation")]

_SUPPORT = PublishedGovernedFactSource().supported_filing_years()

_PROFILE_ID = "10000000-0000-4000-8000-000000000366"
_BUCKET_ID = _PROFILE_ID
_CLOCK = datetime(_SUPPORT.horizon, 7, 1, 12, 0, 0, tzinfo=UTC)

_CASILLA_TO_BINDING: Mapping[str, str] = {
    "DPNIF_D": "renta-profile-tax-id",
    "DP_APENOM_D": "renta-profile-display-name",
    "ZCCAD": "renta-profile-tax-residence-ccaa",
    "TIPOTRIBUTACION": "renta-profile-declaration-type",
    "SEXO_D": "renta-profile-taxpayer-sex",
    "ECIVIL": "renta-profile-marital-status",
    "DPFNAC_D": "renta-profile-taxpayer-birth-date",
    "DPNIF_C": "renta-profile-spouse-tax-id",
    "DP_APENOM_C": "renta-profile-spouse-display-name",
    "DPFNAC_C": "renta-profile-spouse-birth-date",
    "SEXO_C": "renta-profile-spouse-sex",
    "DPGMIN_D": "renta-profile-taxpayer-disability-grade",
    "DECFAL": "renta-profile-taxpayer-death-date",
    "DPGMIN_C": "renta-profile-spouse-disability-grade",
    "NORESIDENTE": "renta-profile-spouse-non-resident-irpf",
    "RESIDENTEUE": "renta-profile-spouse-eu-eea-resident",
    "ZRUE2": "renta-profile-spouse-eu-eea-country",
    "HIJOSUE": "renta-profile-family-descendants-eu-eea-deduction",
    "PH18": "renta-profile-family-minor-children-in-unit",
    "NIFDLG": "renta-family-descendant-tax-id",
    "APENOMDLG": "renta-family-descendant-display-name",
    "FNACDLG": "renta-family-descendant-birth-date",
    "MINUSDLG": "renta-family-descendant-disability-grade",
    "FALLDLG": "renta-family-descendant-death-date",
    "DNIASDLG": "renta-family-ascendant-tax-id",
    "APENOMDLG_ASC": "renta-family-ascendant-display-name",
    "ANOASDLG": "renta-family-ascendant-birth-date",
    "PCTMINASDLG": "renta-family-ascendant-disability-grade",
    "CONVASDLG": "renta-family-ascendant-cohabiting-descendant-count",
    "FALLASDLG": "renta-family-ascendant-death-date",
}

# The first authored Modelo 100 edition that binds every personal and family field
# above to the profile; every later supported year keeps the construct.
_PROFILE_BACKED_FIRST_EDITION = next(
    revision.valid_from.year
    for revision in authored_revisions_where(
        "100", lambda revision: set(_CASILLA_TO_BINDING.values()) <= {b.id for b in revision.bindings}
    )
)
_PROFILE_BACKED_YEARS = tuple(year for year in _SUPPORT.years if year >= _PROFILE_BACKED_FIRST_EDITION)
# The personal facts are fixed ages at the first profile-backed exercise.
_TAXPAYER_BIRTH_DATE = date(_PROFILE_BACKED_FIRST_EDITION - 44, 3, 15)
_SPOUSE_BIRTH_DATE = date(_PROFILE_BACKED_FIRST_EDITION - 46, 7, 22)

_SCALAR_PROFILE_BINDING_VALUES: Mapping[str, object] = {
    "renta-profile-tax-id": "12345678Z",
    "renta-profile-tax-residence-ccaa": "madrid",
    "renta-profile-declaration-type": Decimal("2"),
    "renta-profile-taxpayer-sex": "H",
    "renta-profile-marital-status": Decimal("2"),
    "renta-profile-taxpayer-birth-date": _TAXPAYER_BIRTH_DATE,
    "renta-profile-spouse-tax-id": "98765432B",
    "renta-profile-spouse-birth-date": _SPOUSE_BIRTH_DATE,
    "renta-profile-spouse-sex": "M",
    "renta-profile-taxpayer-disability-grade": Decimal("0"),
    "renta-profile-taxpayer-death-date": date(_PROFILE_BACKED_FIRST_EDITION, 11, 3),
    "renta-profile-spouse-disability-grade": Decimal("0"),
    "renta-profile-spouse-non-resident-irpf": True,
    "renta-profile-spouse-eu-eea-resident": True,
    "renta-profile-spouse-eu-eea-country": "DE",
    "renta-profile-family-descendants-eu-eea-deduction": True,
    "renta-profile-family-minor-children-in-unit": False,
}

_ROW_BINDINGS: Mapping[str, tuple[str, str]] = {
    "renta-family-descendant-tax-id": ("descendants", "tax_id"),
    "renta-family-descendant-display-name": ("descendants", "display_name"),
    "renta-family-descendant-birth-date": ("descendants", "birth_date"),
    "renta-family-descendant-disability-grade": ("descendants", "disability_grade"),
    "renta-family-descendant-death-date": ("descendants", "death_date"),
    "renta-family-ascendant-tax-id": ("ascendants", "tax_id"),
    "renta-family-ascendant-display-name": ("ascendants", "display_name"),
    "renta-family-ascendant-birth-date": ("ascendants", "birth_date"),
    "renta-family-ascendant-disability-grade": ("ascendants", "disability_grade"),
    "renta-family-ascendant-cohabiting-descendant-count": ("ascendants", "cohabiting_descendant_count"),
    "renta-family-ascendant-death-date": ("ascendants", "death_date"),
}


def _snapshot(filing_year: int) -> RegistrySnapshot:
    return published_snapshot("100", filing_year=filing_year, period="0A")


def _full_profile() -> UserProfileRecord:
    return _create_profile_record_for_test(
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
            UserProfileFact(path="renta_taxpayer.birth_date", value=_TAXPAYER_BIRTH_DATE),
            UserProfileFact(path="renta_taxpayer.disability_grade", value="0"),
            UserProfileFact(path="renta_taxpayer.death_date", value=date(_PROFILE_BACKED_FIRST_EDITION, 11, 3)),
            UserProfileFact(path="renta_spouse.tax_id", value="98765432B"),
            UserProfileFact(path="renta_spouse.surnames", value="Martinez"),
            UserProfileFact(path="renta_spouse.name", value="Carlos"),
            UserProfileFact(path="renta_spouse.birth_date", value=_SPOUSE_BIRTH_DATE),
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
        context=_profile_creation_context_for_test(),
    )


@pytest.mark.parametrize("filing_year", _PROFILE_BACKED_YEARS)
def test_modelo_100_personal_family_construct_is_profile_backed(filing_year: int) -> None:
    snapshot = _snapshot(filing_year)
    construct = snapshot.constructs["renta-personal-family"]
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
        selector: Any = binding.provider
        assert selector.dictionary_field == casilla_id


@pytest.mark.parametrize("filing_year", _PROFILE_BACKED_YEARS)
def test_modelo_100_profile_binding_selectors_target_real_profile_schema(filing_year: int) -> None:
    snapshot = _snapshot(filing_year)
    schema = published_profile_schema()
    schema_selectors = {f"{section.key}.{field.key}" for section in schema.sections for field in section.fields} | {
        selector for section in schema.sections for field in section.fields for selector in field.model_selectors
    }
    bindings = {binding.id: binding for binding in snapshot.revision.bindings}

    for binding_id in _CASILLA_TO_BINDING.values():
        selectors = profile_binding_selectors(bindings[binding_id].provider)
        assert selectors, binding_id
        missing = set(selectors) - schema_selectors
        assert not missing, f"{binding_id}: selectors outside profile schema: {sorted(missing)}"


@pytest.mark.parametrize("filing_year", _PROFILE_BACKED_YEARS)
def test_modelo_100_scalar_profile_values_resolve_from_real_profile_facts(filing_year: int) -> None:
    snapshot = _snapshot(filing_year)
    schema = published_profile_schema()
    facts = profile_fact_index(_full_profile(), schema)
    bindings = {binding.id: binding for binding in snapshot.revision.bindings}

    for binding_id, expected in _SCALAR_PROFILE_BINDING_VALUES.items():
        value = resolve_profile_binding_value(bindings[binding_id], facts)
        assert value == expected, f"{binding_id}: expected {expected!r}, got {value!r}"


@pytest.mark.parametrize("filing_year", _PROFILE_BACKED_YEARS)
def test_modelo_100_family_row_bindings_address_repeating_profile_collections(filing_year: int) -> None:
    snapshot = _snapshot(filing_year)
    bindings = {binding.id: binding for binding in snapshot.revision.bindings}

    for binding_id, (collection, field) in _ROW_BINDINGS.items():
        selector: Any = bindings[binding_id].provider
        assert selector.profile_model == "RentaFamilyProfile"
        assert selector.collection == collection
        assert selector.field == field
        assert selector.repeating is True
