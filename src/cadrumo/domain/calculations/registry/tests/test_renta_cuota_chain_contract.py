"""Renta cuota-chain contract checks against the committed registry."""

from __future__ import annotations

import pytest

from .....core import CasillaId, validated_casilla_id
from cadrumo.domain.calculations.registry.schema import ModeloDefinition
from ._registry_schema_support import _committed_modelo

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


_REQUIRED_CUOTA_CHAIN_ARTICLES: frozenset[str] = frozenset(
    {
        "ley-35-2006:art-49",  # Integración y compensación de rentas en la base imponible del ahorro
        "ley-35-2006:art-50",  # Base liquidable general y del ahorro
        "ley-35-2006:art-56",  # Mínimo personal y familiar
        "ley-35-2006:art-62",  # Cuota íntegra estatal
        "ley-35-2006:art-63",  # Escala general del Impuesto
        "ley-35-2006:art-66",  # Tipos de gravamen del ahorro
        "ley-35-2006:art-67",  # Cuota líquida estatal
        "ley-35-2006:art-68",  # Deducciones de la cuota íntegra estatal
        "ley-35-2006:art-73",  # Cuota íntegra autonómica
        "ley-35-2006:art-74",  # Escala autonómica del Impuesto
        "ley-35-2006:art-75",  # Especialidades por anualidades por alimentos a hijos
        "ley-35-2006:art-76",  # Tipo de gravamen del ahorro autonómico
        "ley-35-2006:art-77",  # Cuota líquida autonómica
    },
)

_MINIMO_PERSONAL_Y_FAMILIAR_TARGETS: frozenset[CasillaId] = frozenset(
    validated_casilla_id(casilla_id, surface="_MINIMO_PERSONAL_Y_FAMILIAR_TARGETS")
    for casilla_id in (
        "0519",  # Parte estatal: Mínimo personal y familiar
        "0520",  # Importe total incrementado o disminuido del mínimo (autonómica)
        "0521",  # Mínimo en base liquidable general - gravamen estatal
        "0522",  # Mínimo en base liquidable del ahorro - gravamen estatal
        "0523",  # Mínimo en base liquidable general - gravamen autonómica
        "0524",  # Mínimo en base liquidable del ahorro - gravamen autonómica
    )
)

_BASE_IMPONIBLE_LIQUIDABLE_TARGETS: frozenset[CasillaId] = frozenset(
    validated_casilla_id(casilla_id, surface="_BASE_IMPONIBLE_LIQUIDABLE_TARGETS")
    for casilla_id in (
        "0432",  # Saldo neto rendimientos integrar base imponible general
        "0435",  # Base imponible general
        "0460",  # Base imponible del ahorro
        "0500",  # Base liquidable general
        "0510",  # Base liquidable del ahorro
    )
)

_CUOTA_INTEGRA_TARGETS: frozenset[CasillaId] = frozenset(
    validated_casilla_id(casilla_id, surface="_CUOTA_INTEGRA_TARGETS")
    for casilla_id in (
        "0532",  # Cuota base liquidable general - parte estatal
        "0533",  # Cuota base liquidable general - parte autonómica
        "0545",  # Cuota íntegra estatal
        "0546",  # Cuota íntegra autonómica
    )
)

_CUOTA_LIQUIDA_TARGETS: frozenset[CasillaId] = frozenset(
    validated_casilla_id(casilla_id, surface="_CUOTA_LIQUIDA_TARGETS")
    for casilla_id in (
        "0570",  # Cuota líquida estatal
        "0571",  # Cuota líquida autonómica
        "0585",  # Cuota líquida estatal incrementada
        "0586",  # Cuota líquida autonómica incrementada
    )
)

_MULTI_YEAR_CUOTA_CHAIN_REVISIONS: tuple[str, ...] = ("2020", "2021", "2022", "2023", "2024")

_MULTI_YEAR_REQUIRED_SOURCE_GROUPS: tuple[tuple[str, ...], ...] = tuple(
    (
        f"aeat-renta-{year}-manual-parte1",
        f"boe-modelo-100-{year}-form",
    )
    for year in _MULTI_YEAR_CUOTA_CHAIN_REVISIONS
)

_FULL_CUOTA_CHAIN_TARGETS = (
    _MINIMO_PERSONAL_Y_FAMILIAR_TARGETS
    | _BASE_IMPONIBLE_LIQUIDABLE_TARGETS
    | _CUOTA_INTEGRA_TARGETS
    | _CUOTA_LIQUIDA_TARGETS
)


def _modelo_100():
    return _committed_modelo("100")


def _formula_target_casillas_for_revision(modelo: ModeloDefinition, revision_id: str) -> frozenset[CasillaId]:
    revision = modelo.revisions.get(revision_id)
    if revision is None:
        return frozenset[CasillaId]()
    return frozenset(formula.target_casilla_id for formula in revision.formulas)


def test_renta_cuota_chain_articles_are_catalogued() -> None:
    """All cuota chain Ley 35/2006 articles are registered in the IRPF catalogue."""

    _modelo, catalogues = _modelo_100()
    catalogued = set(catalogues.legal.keys())
    missing = _REQUIRED_CUOTA_CHAIN_ARTICLES - catalogued
    assert not missing, f"cuota chain regression: missing IRPF articles {sorted(missing)}"


def test_renta_minimo_personal_y_familiar_formulas_present_2025() -> None:
    """Mínimo personal y familiar formulas are registered for ejercicio 2025."""

    modelo, _ = _modelo_100()
    targets = _formula_target_casillas_for_revision(modelo, "2025")
    missing = _MINIMO_PERSONAL_Y_FAMILIAR_TARGETS - targets
    assert not missing, f"mínimo personal y familiar regression: missing formula targets {sorted(missing)}"


def test_renta_base_imponible_liquidable_formulas_present_2025() -> None:
    """Base imponible and base liquidable formulas are registered for ejercicio 2025."""

    modelo, _ = _modelo_100()
    targets = _formula_target_casillas_for_revision(modelo, "2025")
    missing = _BASE_IMPONIBLE_LIQUIDABLE_TARGETS - targets
    assert not missing, f"base imponible/liquidable regression: missing formula targets {sorted(missing)}"


def test_renta_cuota_integra_formulas_present_2025() -> None:
    """Cuota íntegra formulas are registered for ejercicio 2025."""

    modelo, _ = _modelo_100()
    targets = _formula_target_casillas_for_revision(modelo, "2025")
    missing = _CUOTA_INTEGRA_TARGETS - targets
    assert not missing, f"cuota íntegra regression: missing formula targets {sorted(missing)}"


def test_renta_cuota_liquida_formulas_present_2025() -> None:
    """Cuota líquida formulas are registered for ejercicio 2025."""

    modelo, _ = _modelo_100()
    targets = _formula_target_casillas_for_revision(modelo, "2025")
    missing = _CUOTA_LIQUIDA_TARGETS - targets
    assert not missing, f"cuota líquida regression: missing formula targets {sorted(missing)}"


def test_renta_multi_year_cuota_chain_sources_are_catalogued() -> None:
    """Each supported prior ejercicio carries AEAT manual and BOE form sources."""

    _modelo, catalogues = _modelo_100()
    catalogued_sources = set(catalogues.sources.keys())
    gaps: dict[str, list[str]] = {}
    for year, required in zip(_MULTI_YEAR_CUOTA_CHAIN_REVISIONS, _MULTI_YEAR_REQUIRED_SOURCE_GROUPS, strict=True):
        missing = [src for src in required if src not in catalogued_sources]
        if missing:
            gaps[year] = missing
    assert not gaps, f"prior ejercicios missing Renta cuota-chain authority sources {gaps}"


def test_renta_cuota_chain_present_in_all_supported_revisions() -> None:
    """Each supported ejercicio carries the full cuota-chain formula set."""

    modelo, _ = _modelo_100()
    gaps: dict[str, list[str]] = {}
    for revision_id in _MULTI_YEAR_CUOTA_CHAIN_REVISIONS:
        targets = _formula_target_casillas_for_revision(modelo, revision_id)
        missing = _FULL_CUOTA_CHAIN_TARGETS - targets
        if missing:
            gaps[revision_id] = sorted(missing)
    assert not gaps, f"supported ejercicios missing cuota-chain formula targets {gaps}"


def test_renta_cuota_chain_can_support_multi_year_calculation_parity() -> None:
    """All supported ejercicios expose the casilla chain needed for calculation parity."""

    modelo, _ = _modelo_100()
    incomplete_revisions: list[str] = []
    for revision_id in (*_MULTI_YEAR_CUOTA_CHAIN_REVISIONS, "2025"):
        targets = _formula_target_casillas_for_revision(modelo, revision_id)
        if not _FULL_CUOTA_CHAIN_TARGETS.issubset(targets):
            incomplete_revisions.append(revision_id)
    assert not incomplete_revisions, (
        "full multi-year cuota chain incomplete in revisions "
        f"{incomplete_revisions}; calculation parity requires every supported revision "
        "to carry the cuota-chain formula targets"
    )
