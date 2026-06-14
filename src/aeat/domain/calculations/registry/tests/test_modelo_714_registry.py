"""Tests for the committed Modelo 714 (patrimonio) registry foundation."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from .....core.resources import bundled_path
from .. import (
    ModeloDefinition,
    RegistryCatalogues,
    RegistryValidator,
    build_snapshot,
    calculate_registry_snapshot,
    load_registry_tree,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _load_modelo_714() -> tuple[ModeloDefinition, RegistryCatalogues]:
    modelos, catalogues = load_registry_tree(bundled_path("registry", "aeat"))
    modelo = next(m for m in modelos if m.id == "714")
    return modelo, catalogues


@pytest.mark.parametrize(
    ("base_liquidable", "expected_cuota"),
    [
        # Oracle from the BOE Ley 19/1991 art. 30 published escala table
        # (bundled corpus ley-19-1991-art-30.html). Boundary values are the
        # table's published "Cuota" column; mid-bracket values are computed as
        # published_fixed + (base - lower_bound) * marginal_rate, derived from
        # the table — NOT from the formula under test (non-tautological).
        ("0", "0.00"),
        ("167129.45", "334.26"),  # bracket-2 lower bound: published cuota
        ("668499.75", "2506.86"),  # bracket-4 lower bound: published cuota
        ("1336999.51", "8523.36"),  # bracket-5 lower bound: published cuota
        ("10695996.06", "183670.29"),  # top bracket lower bound: published cuota
        ("700000", "2790.36"),  # mid bracket-4: 2506.86 + (700000-668499.75)*0.009
        ("1000000", "5490.36"),  # mid bracket-4: 2506.86 + (1000000-668499.75)*0.009
        ("20000000", "509310.43"),  # top bracket: 183670.29 + (20000000-10695996.06)*0.035
    ],
)
def test_modelo_714_cuota_integra_escala_matches_boe_table(base_liquidable: str, expected_cuota: str) -> None:
    """The art. 30 escala formula computes casilla 29 exactly per the BOE table."""
    modelo, catalogues = _load_modelo_714()
    snapshot = build_snapshot(modelo, catalogues, source_root=bundled_path(), filing_year=2024, period="0A")
    result = calculate_registry_snapshot(
        snapshot,
        inputs={"patrimonio.base-liquidable": Decimal(base_liquidable)},
        date_context={"filing_period": date(2024, 12, 31)},
    )
    assert result.values.get("patrimonio.cuota-integra") == Decimal(expected_cuota)


def test_modelo_714_validator_accepts_committed_definition() -> None:
    modelo, catalogues = _load_modelo_714()
    assert modelo.id == "714"
    assert modelo.revisions, "714 must declare at least one revision"
    RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(modelo)


def test_modelo_714_revision_2021_declares_constructs() -> None:
    modelo, _ = _load_modelo_714()
    revision = modelo.revisions["2021-y-siguientes"]
    assert revision.constructs, "714 2021-y-siguientes revision must declare constructs"
    construct_ids = {c.id for c in revision.constructs}
    assert "m714-patrimonio-calculation" in construct_ids


def test_modelo_714_revision_2021_cuota_integra_computed_via_grounded_escala() -> None:
    """Phase-B: cuota íntegra (29) is computed from the Ley 19/1991 art. 30 escala.

    The downstream chain (base imponible, base liquidable, and the post-cuota
    casillas) stays a manual foundation pending its own official formula
    evidence; only the escala step — grounded verbatim in the bundled
    authoritative corpus — is computed. No fake/placeholder formula is declared.
    """
    modelo, _ = _load_modelo_714()
    revision = modelo.revisions["2021-y-siguientes"]
    # The sole Phase-B formula is the real, art.30-grounded escala — not a placeholder.
    escala_formula = next(f for f in revision.formulas if f.target == "patrimonio.cuota-integra")
    assert escala_formula.id == "patrimonio-cuota-integra-escala-estatal"
    assert "ley-19-1991:art-30" in escala_formula.legal_refs
    casillas = {casilla.id: casilla for casilla in revision.casillas}
    # The escala output casilla is computed via that formula.
    assert casillas["patrimonio.cuota-integra"].input_kind == "computed"
    assert casillas["patrimonio.cuota-integra"].formula == "patrimonio-cuota-integra-escala-estatal"
    # The manual foundation (inputs + not-yet-modelled downstream) is unchanged.
    for casilla_id in (
        "patrimonio.base-imponible",
        "patrimonio.base-liquidable",
        "patrimonio.cuota-a-ingresar",
    ):
        assert casillas[casilla_id].input_kind == "manual"


def test_modelo_714_snapshot_builds_for_2021_event_period() -> None:
    modelo, catalogues = _load_modelo_714()
    snapshot = build_snapshot(
        modelo,
        catalogues,
        source_root=bundled_path(),
        filing_year=2021,
        period="0A",
    )
    assert snapshot.revision.id == "2021-y-siguientes"


@pytest.mark.parametrize(
    ("base_liquidable", "expected_cuota", "expected_suelo_80"),
    [
        # Casilla 39 (art. 31 suelo) = 80% of the cuota integra (casilla 29).
        ("0", "0.00", "0.00"),
        ("1336999.51", "8523.36", "6818.69"),  # 8523.36 * 0.80
        ("1000000", "5490.36", "4392.29"),  # 5490.36 * 0.80
        ("20000000", "509310.43", "407448.34"),  # 509310.43 * 0.80
    ],
)
def test_modelo_714_reduccion_limite_80_is_80pct_of_cuota_integra(
    base_liquidable: str, expected_cuota: str, expected_suelo_80: str
) -> None:
    """Casilla 39 (Ley 19/1991 art. 31 suelo) computes as 80% of the cuota integra."""
    modelo, catalogues = _load_modelo_714()
    snapshot = build_snapshot(modelo, catalogues, source_root=bundled_path(), filing_year=2024, period="0A")
    result = calculate_registry_snapshot(
        snapshot,
        inputs={"patrimonio.base-liquidable": Decimal(base_liquidable)},
        date_context={"filing_period": date(2024, 12, 31)},
    )
    assert result.values.get("patrimonio.cuota-integra") == Decimal(expected_cuota)
    assert result.values.get("patrimonio.reduccion-limite-80") == Decimal(expected_suelo_80)
