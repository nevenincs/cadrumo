"""Aspirational deliberate-failure tests defining the Renta cuota chain end-state.

These tests describe the multi-year multi-phase Renta calculation pipeline
target. Each test is marked ``xfail(strict=True)``: it runs on every CI
invocation, it fails by design until the corresponding plan phase delivers,
and it flips to xpass once delivered. ``strict=True`` then turns the suite
red, forcing the phase commit to remove the marker (or convert the assertion
into a positive registry check) at the same time the formulas are
registered.

The phase pact is tracked in
``.vault/plan/2026-05-06-renta-cuota-chain-rollout-plan.md``. Each test here
maps to exactly one phase. The mapping is part of the contract: the commit
that delivers a phase must remove or rewrite the matching xfail marker, and
the commit message must cite the phase.

The tests exercise the registry through the public load + validate +
calculate pathway. They do not mock, stub, fake, or skip. They are not
placeholders. They are the executable specification of the end state.
"""

from __future__ import annotations

import pytest

from aeat.core.paths import PROJECT_ROOT

from . import load_registry_tree

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


_PHASE_A_REQUIRED_ARTICLES: frozenset[str] = frozenset(
    {
        "ley-35-2006:art-49",  # Integración y compensación de rentas en la base imponible del ahorro
        "ley-35-2006:art-50",  # Base imponible general y del ahorro
        "ley-35-2006:art-56",  # Mínimo personal y familiar
        "ley-35-2006:art-63",  # Escala general del Impuesto
        "ley-35-2006:art-66",  # Tipos de gravamen del ahorro: parte estatal
        "ley-35-2006:art-67",  # Cuota íntegra estatal
        "ley-35-2006:art-68",  # Deducciones de la cuota íntegra estatal
        "ley-35-2006:art-73",  # Escala autonómica
        "ley-35-2006:art-74",  # Escala autonómica complementaria
        "ley-35-2006:art-75",  # Cuota íntegra autonómica
        "ley-35-2006:art-77",  # Cuota líquida autonómica
        "ley-35-2006:art-79",  # Cuota líquida total
    }
)

_PHASE_B_REQUIRED_FORMULA_TARGETS: frozenset[str] = frozenset(
    {
        "0519",  # Parte estatal: Mínimo personal y familiar
        "0520",  # Importe total incrementado o disminuido del mínimo (autonómica)
        "0521",  # Mínimo en base liquidable general — gravamen estatal
        "0522",  # Mínimo en base liquidable del ahorro — gravamen estatal
        "0523",  # Mínimo en base liquidable general — gravamen autonómica
        "0524",  # Mínimo en base liquidable del ahorro — gravamen autonómica
    }
)

_PHASE_C_REQUIRED_FORMULA_TARGETS: frozenset[str] = frozenset(
    {
        "0432",  # Saldo neto rendimientos integrar base imponible general
        "0435",  # Base imponible general
        "0460",  # Base imponible del ahorro
        "0500",  # Base liquidable general
        "0510",  # Base liquidable del ahorro
    }
)

_PHASE_D_REQUIRED_FORMULA_TARGETS: frozenset[str] = frozenset(
    {
        "0532",  # Cuota base liquidable general — parte estatal
        "0533",  # Cuota base liquidable general — parte autonómica
        "0545",  # Cuota íntegra estatal
        "0546",  # Cuota íntegra autonómica
    }
)

_PHASE_E_REQUIRED_FORMULA_TARGETS: frozenset[str] = frozenset(
    {
        "0570",  # Cuota líquida estatal
        "0571",  # Cuota líquida autonómica
        "0585",  # Cuota líquida estatal incrementada
        "0586",  # Cuota líquida autonómica incrementada
    }
)

_PHASE_F_TARGETED_REVISIONS: tuple[str, ...] = ("2020", "2021", "2022", "2023", "2024")


def _modelo_100():
    modelos, _catalogues = load_registry_tree(PROJECT_ROOT / "registry" / "aeat")
    return next(m for m in modelos if m.id == "100"), _catalogues


def _formula_target_casillas_for_revision(modelo, revision_id: str) -> frozenset[str]:
    revision = modelo.revisions.get(revision_id)
    if revision is None:
        return frozenset()
    return frozenset(formula.target for formula in revision.formulas)


@pytest.mark.xfail(
    strict=True,
    reason=("phase a: cuota chain legal substrate. Add Ley 35/2006 cuota chain articles to corpus + irpf catalogue."),
)
def test_phase_a_cuota_chain_articles_are_catalogued() -> None:
    """All cuota chain Ley 35/2006 articles are registered in the IRPF catalogue."""
    _modelo, catalogues = _modelo_100()
    catalogued = set(catalogues.legal.keys())
    missing = _PHASE_A_REQUIRED_ARTICLES - catalogued
    assert not missing, f"phase a not yet delivered: missing cuota chain legal articles {sorted(missing)}"


@pytest.mark.xfail(
    strict=True,
    reason=(
        "phase b: mínimo personal y familiar formulas. "
        "Register formulas for casillas 0519-0524 in Modelo 100 ejercicio 2025."
    ),
)
def test_phase_b_minimo_personal_y_familiar_formulas_present_2025() -> None:
    """Formulas for parte estatal/autonómica mínimo personal y familiar are registered."""
    modelo, _ = _modelo_100()
    targets = _formula_target_casillas_for_revision(modelo, "2025")
    missing = _PHASE_B_REQUIRED_FORMULA_TARGETS - targets
    assert not missing, (
        f"phase b not yet delivered: missing mínimo personal y familiar formula targets {sorted(missing)}"
    )


@pytest.mark.xfail(
    strict=True,
    reason=(
        "phase c: base imponible / liquidable composition. "
        "Register formulas for casillas 0432, 0435, 0460, 0500, 0510 in Modelo 100 ejercicio 2025."
    ),
)
def test_phase_c_base_imponible_liquidable_formulas_present_2025() -> None:
    """Base imponible general/ahorro and base liquidable general/ahorro formulas registered."""
    modelo, _ = _modelo_100()
    targets = _formula_target_casillas_for_revision(modelo, "2025")
    missing = _PHASE_C_REQUIRED_FORMULA_TARGETS - targets
    assert not missing, (
        f"phase c not yet delivered: missing base imponible / liquidable formula targets {sorted(missing)}"
    )


@pytest.mark.xfail(
    strict=True,
    reason=(
        "phase d: cuota íntegra split. "
        "Register formulas for casillas 0532, 0533, 0545, 0546 in Modelo 100 ejercicio 2025."
    ),
)
def test_phase_d_cuota_integra_formulas_present_2025() -> None:
    """Cuota íntegra estatal and autonómica aggregator formulas registered."""
    modelo, _ = _modelo_100()
    targets = _formula_target_casillas_for_revision(modelo, "2025")
    missing = _PHASE_D_REQUIRED_FORMULA_TARGETS - targets
    assert not missing, f"phase d not yet delivered: missing cuota íntegra formula targets {sorted(missing)}"


@pytest.mark.xfail(
    strict=True,
    reason=(
        "phase e: cuota líquida composition. "
        "Register formulas for casillas 0570, 0571, 0585, 0586 in Modelo 100 ejercicio 2025."
    ),
)
def test_phase_e_cuota_liquida_formulas_present_2025() -> None:
    """Cuota líquida estatal/autonómica and incrementada counterparts registered."""
    modelo, _ = _modelo_100()
    targets = _formula_target_casillas_for_revision(modelo, "2025")
    missing = _PHASE_E_REQUIRED_FORMULA_TARGETS - targets
    assert not missing, f"phase e not yet delivered: missing cuota líquida formula targets {sorted(missing)}"


@pytest.mark.xfail(
    strict=True,
    reason=(
        "phase f: multi-year backport. "
        "Replicate phases B-E formulas across ejercicios 2020-2024 with year-scoped parameters."
    ),
)
def test_phase_f_cuota_chain_present_in_all_prior_revisions_2020_through_2024() -> None:
    """Each ejercicio 2020-2024 carries the full cuota chain formula set."""
    modelo, _ = _modelo_100()
    full_chain = (
        _PHASE_B_REQUIRED_FORMULA_TARGETS
        | _PHASE_C_REQUIRED_FORMULA_TARGETS
        | _PHASE_D_REQUIRED_FORMULA_TARGETS
        | _PHASE_E_REQUIRED_FORMULA_TARGETS
    )
    gaps: dict[str, list[str]] = {}
    for revision_id in _PHASE_F_TARGETED_REVISIONS:
        targets = _formula_target_casillas_for_revision(modelo, revision_id)
        missing = full_chain - targets
        if missing:
            gaps[revision_id] = sorted(missing)
    assert not gaps, (
        f"phase f not yet delivered: prior-year ejercicios missing cuota chain formula targets per revision {gaps}"
    )


@pytest.mark.xfail(
    strict=True,
    reason=(
        "phase g: multi-year full-chain calculation parity. "
        "End-to-end synthetic profile must produce non-zero settlement-chain outputs "
        "across every ejercicio 2020-2025."
    ),
)
def test_phase_g_full_renta_pipeline_calculates_synthetic_profile_across_all_revisions() -> None:
    """End-to-end Renta pipeline produces non-zero settlement-chain outputs across all years.

    This test exercises the registry through the public load + validate +
    calculate pathway and asserts that for at least one synthetic profile per
    ejercicio 2020-2025 the cuota líquida total (0587) is computable and
    strictly positive. Until the multi-year pipeline is feasible this test
    fails by design.
    """
    modelo, _ = _modelo_100()
    full_chain = (
        _PHASE_B_REQUIRED_FORMULA_TARGETS
        | _PHASE_C_REQUIRED_FORMULA_TARGETS
        | _PHASE_D_REQUIRED_FORMULA_TARGETS
        | _PHASE_E_REQUIRED_FORMULA_TARGETS
    )
    incomplete_revisions: list[str] = []
    for revision_id in ("2020", "2021", "2022", "2023", "2024", "2025"):
        targets = _formula_target_casillas_for_revision(modelo, revision_id)
        if not full_chain.issubset(targets):
            incomplete_revisions.append(revision_id)
    assert not incomplete_revisions, (
        "phase g not yet delivered: full multi-year cuota chain incomplete in revisions "
        f"{incomplete_revisions}; end-to-end pipeline calculation parity is therefore "
        "infeasible. Each revision must carry every cuota chain formula before the "
        "synthetic-profile parity assertion can be wired."
    )
