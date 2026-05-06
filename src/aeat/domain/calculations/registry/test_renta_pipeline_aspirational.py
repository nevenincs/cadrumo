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
        "ley-35-2006:art-50",  # Base liquidable general y del ahorro
        "ley-35-2006:art-56",  # Mínimo personal y familiar
        "ley-35-2006:art-63",  # Escala general del Impuesto
        "ley-35-2006:art-66",  # Tipos de gravamen del ahorro
        "ley-35-2006:art-67",  # Cuota líquida estatal
        "ley-35-2006:art-68",  # Deducciones de la cuota íntegra estatal
        "ley-35-2006:art-73",  # Base liquidable autonómica sometida a gravamen
        "ley-35-2006:art-74",  # Escala autonómica del Impuesto
        "ley-35-2006:art-75",  # Cuota íntegra autonómica
        "ley-35-2006:art-77",  # Cuota líquida autonómica
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

# Phase F is decomposed into a substrate prerequisite (F0) and the formula
# replication itself (F1). The registry validator requires every formula to
# cite at least one ``official_source_guidance`` source; for prior years the
# AEAT manual and BOE form orden have to be catalogued first or the formulas
# cannot pass validation. The data dictionary that already exists for prior
# years carries ``layout_authority`` evidence which the validator rejects for
# formula citations.
_PHASE_F0_REQUIRED_SUBSTRATE: tuple[tuple[str, ...], ...] = tuple(
    (
        f"aeat-renta-{year}-manual-parte1",
        f"boe-modelo-100-{year}-form",
    )
    for year in _PHASE_F_TARGETED_REVISIONS
)


def _modelo_100():
    modelos, _catalogues = load_registry_tree(PROJECT_ROOT / "registry" / "aeat")
    return next(m for m in modelos if m.id == "100"), _catalogues


def _formula_target_casillas_for_revision(modelo, revision_id: str) -> frozenset[str]:
    revision = modelo.revisions.get(revision_id)
    if revision is None:
        return frozenset()
    return frozenset(formula.target for formula in revision.formulas)


def test_phase_a_cuota_chain_articles_are_catalogued() -> None:
    """All cuota chain Ley 35/2006 articles are registered in the IRPF catalogue.

    Phase A delivered: 11 articles (49, 50, 56, 63, 66, 67, 68, 73, 74, 75, 77)
    catalogued and corpus-grounded. Cuota líquida total is the sum of art-67
    (estatal) and art-77 (autonómica); there is no separate "total" article in
    Ley 35/2006 (art-79 is the cuota diferencial). This test now stays green
    as a regression guard against any of the cuota chain articles being
    removed from the catalogue.
    """
    _modelo, catalogues = _modelo_100()
    catalogued = set(catalogues.legal.keys())
    missing = _PHASE_A_REQUIRED_ARTICLES - catalogued
    assert not missing, f"cuota chain regression: missing IRPF articles {sorted(missing)}"


def test_phase_b_minimo_personal_y_familiar_formulas_present_2025() -> None:
    """Formulas for parte estatal/autonómica mínimo personal y familiar are registered.

    Phase B delivered: 6 formulas (0519, 0520, 0521, 0522, 0523, 0524) that
    aggregate the mínimo del contribuyente, descendientes, ascendientes and
    discapacidad rows into the parte estatal and autonómica totals, and split
    those totals into the portions that fall under base liquidable general /
    base liquidable del ahorro per the AEAT-form-prescribed min() rule.
    """
    modelo, _ = _modelo_100()
    targets = _formula_target_casillas_for_revision(modelo, "2025")
    missing = _PHASE_B_REQUIRED_FORMULA_TARGETS - targets
    assert not missing, f"mínimo personal y familiar regression: missing formula targets {sorted(missing)}"


def test_phase_c_base_imponible_liquidable_formulas_present_2025() -> None:
    """Base imponible general/ahorro and base liquidable general/ahorro formulas registered.

    Phase C delivered: 5 formulas (0432, 0435, 0460, 0500, 0510). The base
    case formulas aggregate computed income casillas (0025 trabajo, 0060
    capital mobiliario general, 0155/0156 capital inmobiliario, 0235
    estimacion directa) into the saldo neto rendimientos, then add the
    saldo negativo de ganancias y pérdidas patrimoniales (0433) to produce
    base imponible general (0435). Base imponible del ahorro (0460) sums
    the saldo neto positivo de capital mobiliario ahorro (0429) and the
    saldo neto positivo total ganancias patrimoniales (0424). Base
    liquidable general/ahorro (0500/0510) subtract the tributación
    conjunta and pensiones compensatorias reductions and the bases
    negativas compensables. These are first-pass formulas covering the
    base case (no prior-year carry-forward compensation chains); the
    multi-year compensation refinement is tracked in Phase F.
    """
    modelo, _ = _modelo_100()
    targets = _formula_target_casillas_for_revision(modelo, "2025")
    missing = _PHASE_C_REQUIRED_FORMULA_TARGETS - targets
    assert not missing, f"base imponible/liquidable regression: missing formula targets {sorted(missing)}"


def test_phase_d_cuota_integra_formulas_present_2025() -> None:
    """Cuota íntegra estatal and autonómica aggregator formulas registered.

    Phase D delivered: 4 formulas (0532, 0533, 0545, 0546). 0532/0533 split
    the cuota base liquidable general into estatal/autonómica via the
    AEAT-form-prescribed subtraction (cuota at base liquidable general -
    cuota at mínimo personal y familiar). 0545/0546 sum those with the cuota
    base liquidable del ahorro (0540/0541) to produce cuota íntegra estatal
    and autonómica per LIRPF art. 62.
    """
    modelo, _ = _modelo_100()
    targets = _formula_target_casillas_for_revision(modelo, "2025")
    missing = _PHASE_D_REQUIRED_FORMULA_TARGETS - targets
    assert not missing, f"cuota íntegra regression: missing formula targets {sorted(missing)}"


def test_phase_e_cuota_liquida_formulas_present_2025() -> None:
    """Cuota líquida estatal/autonómica and incrementada counterparts registered.

    Phase E delivered: 4 formulas (0570, 0571, 0585, 0586). 0570/0571 subtract
    the state-side / autonomic-side deduction columns (vivienda habitual,
    nueva creación, donativos, inversión empresarial, Reserva Canarias,
    Ceuta/Melilla, alquiler vivienda transitorio, energy efficiency, La
    Palma residence) from the cuota íntegra. 0585/0586 add the incremento
    por pérdida del derecho al incentivo (0568/0569) and the regularised
    deductions perdidas (0572/0574/0577/0579) to produce the cuota líquida
    incrementada estatal and autonómica that feed casilla 0587.
    """
    modelo, _ = _modelo_100()
    targets = _formula_target_casillas_for_revision(modelo, "2025")
    missing = _PHASE_E_REQUIRED_FORMULA_TARGETS - targets
    assert not missing, f"cuota líquida regression: missing formula targets {sorted(missing)}"


@pytest.mark.xfail(
    strict=True,
    reason=(
        "phase f0: prior-year substrate. "
        "Each ejercicio 2020-2024 needs aeat-renta-{year}-manual-parte1 and "
        "boe-modelo-100-{year}-form catalogued as official_source_guidance "
        "before phase f1 formula backport can pass validation."
    ),
)
def test_phase_f0_prior_year_substrate_is_catalogued() -> None:
    """Each prior-year ejercicio carries an AEAT manual + BOE form orden source.

    The registry validator requires every formula to cite at least one source
    of evidence_tier=official_source_guidance. The 2025 chain currently uses
    aeat-renta-2025-manual-parte1 and boe-modelo-100-2025-form. Replicating
    this for each prior year is the substrate prerequisite for phase F1.
    """
    _modelo, catalogues = _modelo_100()
    catalogued_sources = set(catalogues.sources.keys())
    gaps: dict[str, list[str]] = {}
    for year, required in zip(_PHASE_F_TARGETED_REVISIONS, _PHASE_F0_REQUIRED_SUBSTRATE):
        missing = [src for src in required if src not in catalogued_sources]
        if missing:
            gaps[year] = missing
    assert not gaps, f"phase f0 not yet delivered: prior-year substrate sources missing {gaps}"


@pytest.mark.xfail(
    strict=True,
    reason=(
        "phase f1: multi-year formula backport. "
        "Replicate phases B-E formulas across ejercicios 2020-2024 with year-scoped "
        "official_source_guidance citations. Blocked on phase f0 substrate."
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
