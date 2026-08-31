"""Modelo 100 2024 profile-backed personal/family registry surface."""

from __future__ import annotations

from collections.abc import Mapping
from functools import cache

import pytest

from .....core.aggregation import BindingSourceKind
from .....core.directory_scan import scan_directory
from .....core.resources._boundary import bundled_path
from .. import bindings as _bindings
from .._validate import RegistryValidator
from ..bindings import ProfileSelector, selector_model_for_source
from ..loader import load_catalogue_file, load_modelo_path
from ..schema import RegistryCatalogues, RegistrySnapshot
from ..schema_input_kind import InputKind
from ..snapshot import build_snapshot

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_EXPECTED_CASILLA_TO_BINDING: Mapping[str, str] = {
    "DPNIF_D": "renta-2024-profile-tax-id",
    "DP_APENOM_D": "renta-2024-profile-display-name",
    "ZCCAD": "renta-2024-profile-tax-residence-ccaa",
    "TIPOTRIBUTACION": "renta-2024-profile-declaration-type",
    "SEXO_D": "renta-2024-profile-taxpayer-sex",
    "ECIVIL": "renta-2024-profile-marital-status",
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

_EXPECTED_ROW_BINDING_TARGETS: Mapping[str, tuple[str, str]] = {
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


def _profile_selector(value: object) -> ProfileSelector:
    assert isinstance(value, ProfileSelector)
    return value


@cache
def _shared_catalogues() -> RegistryCatalogues:
    legal = {}
    sources = {}
    parameters = {}
    for path in scan_directory(bundled_path("registry", "aeat", "legal"), pattern="*.toml"):
        catalogue = load_catalogue_file(path)
        legal.update(catalogue.legal)
        sources.update(catalogue.sources)
        parameters.update(catalogue.parameters)
    return RegistryCatalogues(legal=legal, sources=sources, parameters=parameters)


@cache
def _modelo_100_2024_snapshot() -> RegistrySnapshot:
    catalogues = _shared_catalogues()
    modelo = load_modelo_path(bundled_path("registry", "aeat", "modelos", "100"))
    RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(modelo)
    return build_snapshot(modelo, catalogues, source_root=bundled_path(), filing_year=2024, period="0A")


def test_profile_selector_is_the_single_profile_dispatch_authority() -> None:
    """The live registry dispatch and loaded profile bindings share one class."""
    assert selector_model_for_source(BindingSourceKind.PROFILE) is ProfileSelector
    assert not hasattr(_bindings, "_ProfileSelector")

    snapshot = _modelo_100_2024_snapshot()
    profile_bindings = tuple(
        binding for binding in snapshot.revision.bindings if binding.source is BindingSourceKind.PROFILE
    )
    assert profile_bindings
    assert all(isinstance(binding.selector, ProfileSelector) for binding in profile_bindings)


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

        selector = _profile_selector(binding.selector)
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
    and consumed by the binding ``renta-2024-profile-minimo-descendientes-estatal``,
    which feeds casillas 0513/0514 via a live formula.
    """
    snapshot = _modelo_100_2024_snapshot()
    bindings = {binding.id: binding for binding in snapshot.revision.bindings}
    assert "renta-2024-profile-descendientes-minimos-aggregate" not in bindings

    binding = bindings["renta-2024-profile-minimo-descendientes-estatal"]
    assert binding.source is BindingSourceKind.PROFILE
    selector = _profile_selector(binding.selector)
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
    assert casilla.binding == "renta-2024-profile-taxpayer-birth-date"

    binding = bindings["renta-2024-profile-taxpayer-birth-date"]
    assert binding.source is BindingSourceKind.PROFILE
    selector = _profile_selector(binding.selector)
    assert selector.profile_key == "renta_taxpayer.birth_date"
    assert selector.xsd_path == "/DatosIdentificativos/Declarante/DPFNAC_D"
    assert selector.dictionary_field == "DPFNAC_D"
    assert selector.format == "date"
