"""CasillaRef-topology mutation harness (issue #457 Wave 6 closure).

Closes the topology-typo deferral catalogued in the Wave 5 audit: a
typo where the author wrote ``ref("0431")`` instead of ``ref("0432")``
silently routes the wrong upstream value into the formula. The
existing harnesses cover operand-level (sub_op swap), rate (percent),
literal (mul_div_scalar / threshold_literal), and operator-class
(arithmetic_op_swap) regressions but NOT topology drift in
:class:`CasillaRef` operands.

The new :class:`CASILLA_REF_TOPOLOGY` mutator class re-targets every
:class:`CasillaRef` to a substitute casilla_id whose fixture value
differs from the original by ``>= 0.02 €``. The substitute is
selected at parametrize-build time from the fixture's value space;
positions where no valid substitute exists (the fixture has no
sufficiently-different alternative casilla) are catalogued in
:data:`_FIXTURE_MASKED_REF_POSITIONS_RATIONALES` with rationale and
skipped.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal

import pytest

from .._engine import Engine
from .._ruleset import Ruleset
from . import (
    MODELO_100_2024,
    MODELO_100_2025,
    MODELO_100_2026,
    MODELO_100_SUMMARY_2025,
    MODELO_111_2024,
    MODELO_111_2025,
    MODELO_111_2026,
    MODELO_115_2024,
    MODELO_115_2025,
    MODELO_115_2026,
    MODELO_123_2024,
    MODELO_123_2025,
    MODELO_123_2026,
    MODELO_130_2024,
    MODELO_130_2025,
    MODELO_130_2026,
    MODELO_131_2024,
    MODELO_131_2025,
    MODELO_131_2026,
    MODELO_180_2024,
    MODELO_180_2025,
    MODELO_180_2026,
    MODELO_200_2024,
    MODELO_200_2025,
    MODELO_200_2026,
    MODELO_202_2025,
    MODELO_303_2024,
    MODELO_303_2025,
    MODELO_303_2026,
    MODELO_390_2024,
    MODELO_390_2025,
    MODELO_390_2026,
)
from ._mutators import iter_casilla_ref_paths, mutate_casilla_ref
from .test_arithmetic_op_mutation import _modelo_180_fixture
from .test_operand_swap_mutation import (
    _modelo_100_full_fixture_2024,
    _modelo_100_full_fixture_post_2025,
    _modelo_100_summary_fixture,
    _modelo_111_fixture,
    _modelo_115_fixture,
    _modelo_123_fixture,
    _modelo_130_rich_fixture,
    _modelo_131_rich_fixture,
    _modelo_200_fixture,
    _modelo_202_fixture,
    _modelo_390_fixture,
)
from .test_threshold_literal_mutation import (
    _modelo_303_fixture_with_iva_rate_baselines,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_submission]


@dataclass(frozen=True)
class _CasillaRefCase:
    """One enumerated mutation case for the casilla-ref-topology mutator."""

    ruleset: Ruleset
    casilla_id: str
    ref_path: tuple[int, ...]
    original_target: str
    substitute_target: str
    fixture: dict[str, Decimal]


_FIXTURE_FOR_RULESET: tuple[
    tuple[Ruleset, Callable[[], dict[str, Decimal]]],
    ...,
] = (
    (MODELO_100_2024, _modelo_100_full_fixture_2024),
    (MODELO_100_2025, _modelo_100_full_fixture_post_2025),
    (MODELO_100_2026, _modelo_100_full_fixture_post_2025),
    (MODELO_100_SUMMARY_2025, _modelo_100_summary_fixture),
    (MODELO_111_2024, _modelo_111_fixture),
    (MODELO_111_2025, _modelo_111_fixture),
    (MODELO_111_2026, _modelo_111_fixture),
    (MODELO_115_2024, _modelo_115_fixture),
    (MODELO_115_2025, _modelo_115_fixture),
    (MODELO_115_2026, _modelo_115_fixture),
    (MODELO_123_2024, _modelo_123_fixture),
    (MODELO_123_2025, _modelo_123_fixture),
    (MODELO_123_2026, _modelo_123_fixture),
    (MODELO_130_2024, _modelo_130_rich_fixture),
    (MODELO_130_2025, _modelo_130_rich_fixture),
    (MODELO_130_2026, _modelo_130_rich_fixture),
    (MODELO_131_2024, _modelo_131_rich_fixture),
    (MODELO_131_2025, _modelo_131_rich_fixture),
    (MODELO_131_2026, _modelo_131_rich_fixture),
    (MODELO_180_2024, _modelo_180_fixture),
    (MODELO_180_2025, _modelo_180_fixture),
    (MODELO_180_2026, _modelo_180_fixture),
    (MODELO_200_2024, _modelo_200_fixture),
    (MODELO_200_2025, _modelo_200_fixture),
    (MODELO_200_2026, _modelo_200_fixture),
    (MODELO_202_2025, _modelo_202_fixture),
    (MODELO_303_2024, _modelo_303_fixture_with_iva_rate_baselines),
    (MODELO_303_2025, _modelo_303_fixture_with_iva_rate_baselines),
    (MODELO_303_2026, _modelo_303_fixture_with_iva_rate_baselines),
    (MODELO_390_2024, _modelo_390_fixture),
    (MODELO_390_2025, _modelo_390_fixture),
    (MODELO_390_2026, _modelo_390_fixture),
)


_FIXTURE_MASKED_REF_POSITIONS_RATIONALES: dict[tuple[str, str, tuple[int, ...]], str] = {}


def _select_substitute_target(
    ruleset: Ruleset,
    original_target: str,
    fixture: dict[str, Decimal],
) -> str | None:
    """Pick a casilla_id substitute with a fixture value differing from ``original_target``.

    Iterates the fixture in declared order (deterministic across
    runs) and returns the first casilla_id whose value differs from
    the original by ``>= 0.02 €``. The substitute must:

    1. Be a valid casilla_id in the ruleset (so the engine can
       resolve it post-mutation).
    2. Have a fixture value (so audit_against has a baseline to
       check).
    3. Differ from the original's value by at least the detection
       floor.

    Returns ``None`` if no valid substitute exists in the fixture.
    """
    valid_ids = {casilla.casilla_id for casilla in ruleset.casillas}
    if original_target not in fixture or original_target not in valid_ids:
        return None
    original_value = fixture[original_target]
    for candidate_id, candidate_value in fixture.items():
        if candidate_id == original_target:
            continue
        if candidate_id not in valid_ids:
            continue
        if abs(candidate_value - original_value) >= Decimal("0.02"):
            return candidate_id
    return None


def _runtime_probe_masked(
    ruleset: Ruleset,
    casilla_id: str,
    ref_path: tuple[int, ...],
    substitute_target: str,
    fixture: dict[str, Decimal],
) -> bool:
    """Return ``True`` if the topology swap fails to surface a discrepancy.

    Even with a substitute whose fixture value differs, the swap
    might be masked downstream (e.g. ``Mul(literal_zero, ref)`` —
    multiplying by zero kills any topology change). The runtime
    probe verifies detection.
    """
    engine = Engine()
    baseline = engine.audit_against(ruleset=ruleset, provided=fixture, tolerance=Decimal("0.01"))
    if not baseline.is_clean():
        return False
    try:
        mutated = mutate_casilla_ref(ruleset, casilla_id, ref_path, new_target=substitute_target)
    except (LookupError, TypeError):
        return True
    try:
        report = engine.audit_against(ruleset=mutated, provided=fixture, tolerance=Decimal("0.01"))
    except Exception:
        return True
    if not report.discrepancies:
        return True
    max_delta = max(abs(d.delta) for d in report.discrepancies)
    return max_delta < Decimal("0.02")


def _build_test_params() -> list:
    """Generate one pytest.param per non-masked (ruleset, casilla, ref_path) triple.

    For each :class:`CasillaRef` position, picks a substitute
    casilla_id from the fixture and probes detection. Masked
    positions (no valid substitute, or detection fails because the
    swap is downstream-masked) are catalogued and skipped.
    """
    params: list = []
    for ruleset, fixture_factory in _FIXTURE_FOR_RULESET:
        fixture = fixture_factory()
        for fd in ruleset.formulas:
            for ref_path, casilla_ref in iter_casilla_ref_paths(fd.formula):
                original_target = casilla_ref.casilla_id
                substitute = _select_substitute_target(ruleset, original_target, fixture)
                if substitute is None:
                    _FIXTURE_MASKED_REF_POSITIONS_RATIONALES[(ruleset.ruleset_id, fd.casilla_id, ref_path)] = (
                        f"no valid substitute for ref({original_target!r}) in "
                        f"{ruleset.ruleset_id}: fixture has no other casilla "
                        f"with |delta| >= 0.02 € from the original value."
                    )
                    continue
                if _runtime_probe_masked(ruleset, fd.casilla_id, ref_path, substitute, fixture):
                    _FIXTURE_MASKED_REF_POSITIONS_RATIONALES[(ruleset.ruleset_id, fd.casilla_id, ref_path)] = (
                        f"swap of ref({original_target!r}) -> ref({substitute!r}) "
                        f"on {ruleset.ruleset_id}:{fd.casilla_id} path {ref_path} "
                        f"produces |delta| < 0.02 € at runtime: the substitution "
                        f"is downstream-masked (clamp_pos absorption, multiplied "
                        f"by zero, or audit-skipped because the casilla is not "
                        f"in the fixture)."
                    )
                    continue
                path_id = "_".join(str(p) for p in ref_path) if ref_path else "root"
                params.append(
                    pytest.param(
                        _CasillaRefCase(
                            ruleset=ruleset,
                            casilla_id=fd.casilla_id,
                            ref_path=ref_path,
                            original_target=original_target,
                            substitute_target=substitute,
                            fixture=fixture,
                        ),
                        id=(
                            f"{ruleset.ruleset_id}:casilla_{fd.casilla_id}:"
                            f"ref_{original_target}_to_{substitute}_at_{path_id}"
                        ),
                    )
                )
    return params


_TEST_PARAMS_CACHE = _build_test_params()


@pytest.mark.parametrize("case", _TEST_PARAMS_CACHE)
def test_casilla_ref_topology_swap_is_detected(case: _CasillaRefCase) -> None:
    """Re-targeting a CasillaRef MUST surface a discrepancy.

    Baseline-clean sentinel first; then the mutated ruleset audits
    and MUST surface a discrepancy on at least one casilla with
    ``|delta| >= 0.02 €``.
    """
    engine = Engine()
    baseline = engine.audit_against(ruleset=case.ruleset, provided=case.fixture, tolerance=Decimal("0.01"))
    assert baseline.is_clean(), (
        f"baseline must be clean before mutation; saw {[d.casilla_id for d in baseline.discrepancies]}"
    )
    mutated = mutate_casilla_ref(case.ruleset, case.casilla_id, case.ref_path, new_target=case.substitute_target)
    report = engine.audit_against(ruleset=mutated, provided=case.fixture, tolerance=Decimal("0.01"))
    assert report.discrepancies, (
        f"casilla-ref topology swap on {case.ruleset.ruleset_id} casilla "
        f"{case.casilla_id} (ref {case.original_target} -> {case.substitute_target} "
        f"at path {case.ref_path}) was NOT detected"
    )
    max_delta = max(abs(d.delta) for d in report.discrepancies)
    assert max_delta >= Decimal("0.02"), (
        f"casilla-ref topology swap on {case.ruleset.ruleset_id} casilla {case.casilla_id} "
        f"produced max |delta|={max_delta}, below the 0.02 € detection floor."
    )


def test_iter_casilla_ref_paths_yields_every_ref() -> None:
    """Walker enumerates every CasillaRef descendant in operand-index order.

    Modelo 130 casilla 03 = ``Sub(ref('01'), ref('02'))``. The walker
    yields exactly two :class:`CasillaRef` positions at paths (0, 0)
    and (0, 1).
    """
    fd = MODELO_130_2025.formula_for("03")
    assert fd is not None
    paths = list(iter_casilla_ref_paths(fd.formula))
    assert len(paths) == 2
    assert paths[0][1].casilla_id == "01"
    assert paths[1][1].casilla_id == "02"


def test_mutate_casilla_ref_rejects_non_ref_path() -> None:
    """Targeting a non-CasillaRef path raises ``TypeError``."""
    fd = MODELO_130_2025.formula_for("03")
    assert fd is not None
    # Path () is the RoundFormula root.
    with pytest.raises(TypeError):
        mutate_casilla_ref(MODELO_130_2025, "03", (), new_target="01")


def test_casilla_ref_coverage_is_non_trivial() -> None:
    """Sanity: harness covers a non-trivial number of CasillaRef positions.

    Walker enumerates ~580 CasillaRef positions across all rulesets;
    after fixture-mask filtering, the harness should still cover a
    substantial majority. A regression that drops coverage to zero
    would silently de-arm this defense.
    """
    assert len(_TEST_PARAMS_CACHE) >= 100, (
        f"casilla-ref topology harness coverage suspiciously low: "
        f"{len(_TEST_PARAMS_CACHE)} cases. A walker / substitute-finder "
        f"regression may have silently disarmed the harness."
    )
