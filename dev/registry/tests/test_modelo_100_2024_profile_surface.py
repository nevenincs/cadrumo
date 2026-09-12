"""Modelo 100 2024 profile-backed personal/family registry surface."""

from __future__ import annotations

from collections.abc import Mapping
from functools import cache

import pytest

from cadrumo.core.aggregation import BindingSourceKind
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry import bindings as _bindings
from cadrumo.domain.calculations.registry.binding_provider_registration import provider_model_for
from cadrumo.domain.calculations.registry.profile_bindings import ProfileProvider
from cadrumo.domain.calculations.registry.schema import RegistryCatalogues, RegistrySnapshot
from cadrumo.domain.calculations.registry.schema_input_kind import InputKind
from cadrumo.tests.registry_snapshot import build_snapshot

from ..compiler.fact_providers import compile_registered_fact_providers
from ..compiler.loader import load_shared_catalogues
from ..compiler.validator import RegistryValidator
from ..maintenance_support import load_modelo_path

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_EXPECTED_CASILLA_TO_BINDING: Mapping[str, str] = {
    "DPNIF_D": "renta-profile-tax-id",
    "DP_APENOM_D": "renta-profile-display-name",
    "ZCCAD": "renta-profile-tax-residence-ccaa",
    "TIPOTRIBUTACION": "renta-profile-declaration-type",
    "SEXO_D": "renta-profile-taxpayer-sex",
    "ECIVIL": "renta-profile-marital-status",
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

_EXPECTED_ROW_BINDING_TARGETS: Mapping[str, tuple[str, str]] = {
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


def _profile_selector(value: object) -> ProfileProvider:
    assert isinstance(value, ProfileProvider)
    return value


@cache
def _shared_catalogues() -> RegistryCatalogues:
    registry_root = bundled_path("registry", "aeat")
    catalogue = load_shared_catalogues(registry_root)
    return catalogue.model_copy(update={"facts": compile_registered_fact_providers(registry_root)})


@cache
def _modelo_100_2024_snapshot() -> RegistrySnapshot:
    catalogues = _shared_catalogues()
    modelo = load_modelo_path(bundled_path("registry", "aeat", "modelos", "100"))
    RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(modelo)
    return build_snapshot(modelo, catalogues, source_root=bundled_path(), filing_year=2024, period="0A")


def test_profile_selector_is_the_single_profile_dispatch_authority() -> None:
    """The live registry dispatch and loaded profile bindings share one class."""
    assert provider_model_for(BindingSourceKind.PROFILE) is ProfileProvider
    assert not hasattr(_bindings, "ProfileProvider")

    snapshot = _modelo_100_2024_snapshot()
    profile_bindings = tuple(
        binding for binding in snapshot.revision.bindings if binding.source is BindingSourceKind.PROFILE
    )
    assert profile_bindings
    assert all(isinstance(binding.provider, ProfileProvider) for binding in profile_bindings)


def test_modelo_100_2024_profile_family_surface_is_bound_to_profile_registry_facts() -> None:
    snapshot = _modelo_100_2024_snapshot()
    casillas = {casilla.id: casilla for casilla in snapshot.revision.casillas}
    bindings = {binding.id: binding for binding in snapshot.revision.bindings}

    assert set(_EXPECTED_CASILLA_TO_BINDING) <= set(casillas)
    assert set(_EXPECTED_CASILLA_TO_BINDING.values()) <= set(bindings)

    for casilla_id, binding_id in _EXPECTED_CASILLA_TO_BINDING.items():
        casilla = casillas[casilla_id]
        assert casilla.input_kind is InputKind.BOUND
        assert casilla.binding == binding_id

        binding = bindings[binding_id]
        assert binding.source is BindingSourceKind.PROFILE
        assert binding.legal_refs
        assert binding.source_refs

        selector = _profile_selector(binding.provider)
        assert selector.dictionary_field == casilla_id


def test_modelo_100_2024_profile_family_rows_are_repeating_profile_collections() -> None:
    snapshot = _modelo_100_2024_snapshot()
    bindings = {binding.id: binding for binding in snapshot.revision.bindings}

    for binding_id, (collection, field) in _EXPECTED_ROW_BINDING_TARGETS.items():
        selector = _profile_selector(bindings[binding_id].selector)
        assert selector.profile_model == "RentaFamilyProfile"
        assert selector.collection == collection
        assert selector.field == field
        assert selector.repeating is True
        assert bindings[binding_id].source is BindingSourceKind.PROFILE


def test_modelo_100_2024_descendientes_minimos_aggregate_binding_is_wired() -> None:
    """Regression: the descendientes-minimos aggregate selector is a live, consumed binding.

    ``renta-2024-profile-descendientes-minimos-aggregate`` used to select
    ``family.descendientes_minimos_aggregate_2024``, a profile-model attribute
    that :class:`~cadrumo.domain.contribuyente.RentaFamilyProfile` never
    declared (no formula or bound casilla consumed it either) -- a dangling
    selector per ``aeat-calculation-aggregation``. The Option B interim removed
    the binding outright. Option A's computed engine retires the gap for real:
    the derived selector ``renta_family.descendientes_minimos_aggregate_{filing_year}``
    (declared as a year-parameterised pattern rather than a per-year schema field)
    is now populated by
    :func:`~cadrumo.application.modelo.inject_derived_minimo_descendientes_facts`
    and consumed by the binding ``renta-profile-minimo-descendientes-estatal``,
    which feeds casillas 0513/0514 via a live formula.
    """
    snapshot = _modelo_100_2024_snapshot()
    bindings = {binding.id: binding for binding in snapshot.revision.bindings}
    assert "renta-2024-profile-descendientes-minimos-aggregate" not in bindings

    binding = bindings["renta-profile-minimo-descendientes-estatal"]
    assert binding.source is BindingSourceKind.PROFILE
    selector = _profile_selector(binding.provider)
    assert selector.profile_key == "renta_family.descendientes_minimos_aggregate_2024"

    casillas = {casilla.id: casilla for casilla in snapshot.revision.casillas}
    estatal = casillas["0513"]
    autonomico = casillas["0514"]
    assert estatal.input_kind == InputKind.COMPUTED
    assert autonomico.input_kind == InputKind.COMPUTED
    formulas = {formula.id: formula for formula in snapshot.revision.formulas}
    assert estatal.formula is not None
    assert autonomico.formula is not None
    assert formulas[estatal.formula].target_casilla_id == "0513"
    assert formulas[autonomico.formula].target_casilla_id == "0514"


def test_modelo_100_2024_taxpayer_birth_date_profile_binding_remains_available() -> None:
    snapshot = _modelo_100_2024_snapshot()
    casillas = {casilla.id: casilla for casilla in snapshot.revision.casillas}
    bindings = {binding.id: binding for binding in snapshot.revision.bindings}

    casilla = casillas["DPFNAC_D"]
    assert casilla.input_kind is InputKind.BOUND
    assert casilla.binding == "renta-profile-taxpayer-birth-date"

    binding = bindings["renta-profile-taxpayer-birth-date"]
    assert binding.source is BindingSourceKind.PROFILE
    selector = _profile_selector(binding.provider)
    assert selector.profile_key == "renta_taxpayer.birth_date"
    assert selector.xsd_path == "/DatosIdentificativos/Declarante/DPFNAC_D"
    assert selector.dictionary_field == "DPFNAC_D"
    assert selector.format == "date"
