"""DT 12ª apartado-3 window fact-gate on the calculate-shortcut path (LIVE).

Proves the fact-gated non-application posture end-to-end through the real
:func:`build_work_calculate_input_bundle` shortcut path against a real Modelo 100
work unit (real registry authority, real semantic-role resolution, real domain
compute — no mocks, stubs, skips, or xfail):

- Out-of-window (declared years prove the apartado-3 window CLOSED): the 40%
  reducción is WITHHELD (the reducción casilla is not injected) and a
  ``dt12_regime_window_closed`` advisory surfaces — the legally correct result,
  since applying an out-of-window reducción would over-reduce the return
  (under-declaration of tax per no-silent-under-declaration).
- In-window: the reducción injects exactly as before (the DT 12ª Carla oracle
  6.981,82 €) with no window advisory.
- Absent years: the reducción injects with a ``dt12_regime_window_unverified``
  advisory prompting the operator to confirm the window.
- Parcial rescate type: adds the ``dt12_parcial_rescate_guidance`` advisory.

Expected verdicts derive from the LIRPF DT 12ª apartado-3 window rules and the
DT 12ª 40% formula, not from the code under test.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....core.period import Period
from ....core.rescate_type import RescateType
from ....domain.calculations.registry.authority import bundled_authority
from ....tests.profile_capsule import open_test_profile_session
from ....tests.secure_sql import isolated_profile_storage_root
from ....tests.user_profile import register_minimal_profile
from ..calculate_input import WorkCalculateInputBundle, build_work_calculate_input_bundle
from ..semantic_role_resolution import casilla_id_for_unique_semantic_role
from ..work_lifecycle import create_work_unit

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "20000000-0000-4000-8000-0000000d1200"
_FILING_YEAR = 2024
_ANNUAL_PERIOD = "0A"
_REDUCCION_SEMANTIC_ROLE = "irpf_rendimiento_trabajo_reduccion"

# DT 12ª Carla oracle split: 9600 / 33000 * 60000 * 40% = 6981.82.
_GROSS = "60000"
_PRE_2007 = "9600"
_TOTALES = "33000"
_EXPECTED_REDUCCION = Decimal("6981.82")


def _create_m100_work_unit() -> tuple[str, str]:
    """Register a minimal natural-person profile + M100 work unit; return ids.

    Returns:
        ``(work_unit_id, reduccion_casilla_id)`` for the DT 12ª reducción slot.
    """
    period = Period.from_year_and_code(_FILING_YEAR, _ANNUAL_PERIOD)
    snapshot = bundled_authority().snapshot("100", filing_year=_FILING_YEAR, period=period.registry_token)
    reduccion_casilla_id = casilla_id_for_unique_semantic_role(snapshot, _REDUCCION_SEMANTIC_ROLE)
    assert reduccion_casilla_id is not None

    # Seeded through a detached WorkflowState, never a repository read: the
    # capsule publishes by an atomic no-replace rename onto
    # ``buckets/<profile-id>``, which a workflow-state repository
    # construction would otherwise materialise first and collide with.
    register_minimal_profile(profile_id=_BUCKET_ID)
    work_unit = create_work_unit(
        bucket_id=_BUCKET_ID,
        modelo="100",
        filing_year=_FILING_YEAR,
        period=period,
        revision_id=snapshot.revision.id,
        clock=datetime(2026, 6, 30, 12, 0, tzinfo=UTC),
    )
    return work_unit.work_unit_id, reduccion_casilla_id


def _build_bundle(
    work_unit_id: str,
    *,
    rescate_plan_pensiones_tipo: RescateType | None = None,
    rescate_plan_pensiones_contingencia_year: int | None = None,
    rescate_plan_pensiones_rescate_year: int | None = None,
) -> WorkCalculateInputBundle:
    return build_work_calculate_input_bundle(
        work_unit_id=work_unit_id,
        casilla_overrides={},
        binding_overrides={},
        relation_overrides={},
        detail_rows=(),
        borrador_snapshot_id=None,
        rescate_plan_pensiones_capital=Decimal(_GROSS),
        rescate_plan_pensiones_aportaciones_pre_2007=Decimal(_PRE_2007),
        rescate_plan_pensiones_aportaciones_totales=Decimal(_TOTALES),
        rescate_plan_pensiones_tipo=rescate_plan_pensiones_tipo,
        rescate_plan_pensiones_contingencia_year=rescate_plan_pensiones_contingencia_year,
        rescate_plan_pensiones_rescate_year=rescate_plan_pensiones_rescate_year,
    )


def _reasons(bundle: WorkCalculateInputBundle) -> list[str]:
    return [str(diag.reason) for diag in bundle.shortcut_diagnostics]


def test_out_of_window_withholds_the_reduccion(tmp_path: Path) -> None:
    """Declared years proving the window closed WITHHOLD the 40% reducción."""
    with isolated_profile_storage_root(tmp_path=tmp_path), open_test_profile_session(_BUCKET_ID):
        work_unit_id, reduccion_casilla_id = _create_m100_work_unit()
        # Contingencia 2020 (general branch): window closes end-2022; a 2024
        # rescate is out of window.
        bundle = _build_bundle(
            work_unit_id,
            rescate_plan_pensiones_contingencia_year=2020,
            rescate_plan_pensiones_rescate_year=2024,
        )

    assert reduccion_casilla_id not in bundle.casilla_inputs
    assert "dt12_regime_window_closed" in _reasons(bundle)
    closed = next(d for d in bundle.shortcut_diagnostics if str(d.reason) == "dt12_regime_window_closed")
    assert closed.casilla_id == reduccion_casilla_id
    assert "2020" in closed.message and "2022" in closed.message
    # Advisory-asserted: no casilla in reach carries DT 12ª's own grounding.
    assert closed.asserted_legal_refs == ("ley-35-2006:dt-12",)


def test_in_window_injects_the_reduccion_without_advisory(tmp_path: Path) -> None:
    """An in-window rescate injects the 40% reducción and raises no window advisory."""
    with isolated_profile_storage_root(tmp_path=tmp_path), open_test_profile_session(_BUCKET_ID):
        work_unit_id, reduccion_casilla_id = _create_m100_work_unit()
        # Contingencia 2024, rescate 2024: inside the general window [2024, 2026].
        bundle = _build_bundle(
            work_unit_id,
            rescate_plan_pensiones_contingencia_year=2024,
            rescate_plan_pensiones_rescate_year=2024,
        )

    assert bundle.casilla_inputs[reduccion_casilla_id] == _EXPECTED_REDUCCION
    assert _reasons(bundle) == []


def test_rescate_year_defaults_to_filing_year(tmp_path: Path) -> None:
    """Omitting --rescate-year uses the work unit filing year for the window check."""
    with isolated_profile_storage_root(tmp_path=tmp_path), open_test_profile_session(_BUCKET_ID):
        work_unit_id, reduccion_casilla_id = _create_m100_work_unit()
        # Contingencia 2020, rescate_year omitted -> defaults to filing year 2024
        # -> out of the [2020, 2022] window -> withheld.
        bundle = _build_bundle(work_unit_id, rescate_plan_pensiones_contingencia_year=2020)

    assert reduccion_casilla_id not in bundle.casilla_inputs
    assert "dt12_regime_window_closed" in _reasons(bundle)


def test_absent_contingencia_year_injects_with_unverified_advisory(tmp_path: Path) -> None:
    """No contingencia year injects the reducción and warns the window is unverified."""
    with isolated_profile_storage_root(tmp_path=tmp_path), open_test_profile_session(_BUCKET_ID):
        work_unit_id, reduccion_casilla_id = _create_m100_work_unit()
        bundle = _build_bundle(work_unit_id)

    assert bundle.casilla_inputs[reduccion_casilla_id] == _EXPECTED_REDUCCION
    assert "dt12_regime_window_unverified" in _reasons(bundle)
    unverified = next(d for d in bundle.shortcut_diagnostics if str(d.reason) == "dt12_regime_window_unverified")
    assert unverified.asserted_legal_refs == ("ley-35-2006:dt-12",)


def test_parcial_type_adds_guidance_advisory(tmp_path: Path) -> None:
    """A parcial rescate adds the shared-window/mixed-forfeiture guidance advisory."""
    with isolated_profile_storage_root(tmp_path=tmp_path), open_test_profile_session(_BUCKET_ID):
        work_unit_id, reduccion_casilla_id = _create_m100_work_unit()
        bundle = _build_bundle(
            work_unit_id,
            rescate_plan_pensiones_tipo=RescateType.PARCIAL,
            rescate_plan_pensiones_contingencia_year=2024,
            rescate_plan_pensiones_rescate_year=2024,
        )

    # In-window, so no window advisory, but the parcial guidance is present and
    # the reducción still injects.
    assert bundle.casilla_inputs[reduccion_casilla_id] == _EXPECTED_REDUCCION
    assert _reasons(bundle) == ["dt12_parcial_rescate_guidance"]
    guidance = bundle.shortcut_diagnostics[0]
    assert guidance.asserted_legal_refs == ("ley-35-2006:dt-12",)


def test_total_type_adds_no_guidance_advisory(tmp_path: Path) -> None:
    """A total rescate does not raise the parcial guidance advisory."""
    with isolated_profile_storage_root(tmp_path=tmp_path), open_test_profile_session(_BUCKET_ID):
        work_unit_id, _ = _create_m100_work_unit()
        bundle = _build_bundle(
            work_unit_id,
            rescate_plan_pensiones_tipo=RescateType.TOTAL,
            rescate_plan_pensiones_contingencia_year=2024,
            rescate_plan_pensiones_rescate_year=2024,
        )

    assert "dt12_parcial_rescate_guidance" not in _reasons(bundle)
