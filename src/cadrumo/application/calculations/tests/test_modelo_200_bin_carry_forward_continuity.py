"""E2E enrollment: Modelo 200 (IS) cross-year BIN stock carry-forward.

The Impuesto sobre Sociedades carries bases imponibles negativas (BIN)
forward without time limit (LIS art. 26.1). The end-of-year stock pending
application in future periods — casilla 00671 ("pendiente de aplicación en
períodos futuros") — becomes the next ejercicio's opening stock pending at
the start of the period — casilla 00670 ("pendiente de aplicación a
principio del período"). The cross-year binding
``modelo-200-2024-bin-pendiente-ejercicios-anteriores`` (a ``previous_filing``
copy of the prior year's 00671, ``filing_year_delta = -1``) makes casilla
00670 auto-resolve from the prior filing — the operator does not re-key the
carried BIN stock.

This module is the multi-year-renta authorization enrollment for Modelo 200
(CALC evidence class). It drives the REAL M200 registry engine across two
distinct renta (annual) years, records each through the
:class:`EnrollmentRecorder`, and cross-checks the recorded two-year set
against the authorization manifest via
:func:`assert_enrollment_matches_manifest`.

Grounding (non-tautological): the prior-year 00671 BIN stock is a manual
input the test supplies (no formula under test produces it), and the
assertion is the cross-year WIRING invariant — year N's casilla 00670 equals
year N-1's persisted 00671, year-isolated — which LIS art. 26.1 establishes
as the unlimited carry-forward of the pending BIN balance. The elective
amount actually applied (00547) and its 70% / €1.000.000 ceiling are a
separate elective-cap layer; this enrollment proves the STOCK carry.

The cross-year hook relies on the previous_filing observation-coverage
validator semantics: because the repository validates every filed observation
against a real Modelo 200 revision, this test uses target years whose prior
source years are also modelled. Unsupported historical years must fail closed.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....core import CasillaId, RegistryAuthorityGrade, validated_casilla_id
from ....core.resources import resources
from ....domain.calculations.registry import (
    RegistryCalculationResult,
    RegistryModeloObservation,
    RelationId,
    calculate_registry_snapshot,
    materialize_relation_binding_values,
    resolve_available_bound_inputs_by_casilla_id,
)
from ....tests.registry_observations import registry_grounded_observations
from ....tests.secure_sql import isolated_runtime_profile
from .._binding_prefill import resolve_bindings_from_local_store
from .._multi_year import EnrollmentRecorder, assert_enrollment_matches_manifest
from .._observations_repository import CalculationObservationRepository
from .._relation_prefill import resolve_relations_from_local_store

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_MODELO_200 = "200"

#: Casillas on the cross-year BIN carry.
_M200_BIN_PENDIENTE_FUTUROS: CasillaId = validated_casilla_id(
    "00671",
    surface="_M200_BIN_PENDIENTE_FUTUROS",
)  # end-of-year stock pending future application
_M200_BIN_PENDIENTE_INICIO: CasillaId = validated_casilla_id(
    "00670",
    surface="_M200_BIN_PENDIENTE_INICIO",
)  # opening stock pending (bound from prior 00671)
_M200_BIN_APLICADA_MAXIMA: CasillaId = validated_casilla_id(
    "DP200014:bin-aplicada-maxima",
    surface="_M200_BIN_APLICADA_MAXIMA",
)

#: Two distinct renta years the enrollment spans; each sources the prior year's 00671.
_YEAR_N = 2025
_YEAR_N_PLUS_1 = 2026

#: Distinct prior-year BIN stock per source year so a cross-year contamination surfaces.
_BIN_STOCK_BY_SOURCE_YEAR: dict[int, Decimal] = {
    2024: Decimal("30000.00"),
    2025: Decimal("18000.00"),
}

#: The same-year M202 pagos relation the M200 cuota chain reads; zero here (no
#: instalments) keeps the BIN-stock assertion focused. Supplied directly as a
#: relation value rather than seeded, since pagos are not under test.
_M200_PAGOS_RELATION = "modelo-200-2024-rel-202-pagos-fraccionados"
_M200_PAGOS_RELATION_40_2 = "modelo-200-2024-rel-202-pagos-fraccionados-40-2"

#: Minimal SL-persona profile bindings the M200 cuota chain requires to compute.
_PROFILE_DECIMAL_BINDINGS: dict[str, Decimal] = {
    "modelo-200-2024-profile-new-entity-flag": Decimal("0"),
    "modelo-200-2024-profile-incn-prior-12-months": Decimal("500000"),
    "modelo-200-2024-profile-tributacion-estado-porcentaje": Decimal("100"),
}
_PROFILE_ENUM_BINDINGS: dict[str, str] = {
    "modelo-200-2024-profile-legal-entity-form": "sl",
}

_CLOCK = datetime(2027, 1, 20, 9, 0, 0, tzinfo=UTC)


def _seed_m200_bin_stock(*, source_year: int, stock: Decimal, obs_repo: CalculationObservationRepository) -> None:
    """Record a prior-year M200 end-of-year BIN stock (casilla 00671)."""
    obs_repo.save(
        obs_repo.prepare_observation_envelope(
            RegistryModeloObservation(
                modelo=_MODELO_200,
                filing_year=source_year,
                period="0A",
                observations=registry_grounded_observations(
                    modelo=_MODELO_200,
                    filing_year=source_year,
                    period="0A",
                    casilla_values={_M200_BIN_PENDIENTE_FUTUROS: stock},
                    grade=RegistryAuthorityGrade.CALCULATION,
                ),
            ),
            source_kind="app_filing",
            captured_at=_CLOCK,
        )
    )


def _calculate_200(
    *,
    filing_year: int,
    relation_values: dict[RelationId, Decimal],
    manual_inputs: dict[CasillaId, Decimal] | None = None,
) -> tuple[RegistryCalculationResult, int]:
    """Run the REAL M200 annual calculation from resolved relations + the SL profile.

    ``manual_inputs`` supplies operator-keyed manual casilla values (e.g.
    resultado contable 00501) merged over the resolved bound inputs; absent
    manual casillas default to zero in formula evaluation.
    """
    snapshot = resources().modelos.authority.snapshot(
        _MODELO_200, filing_year=filing_year, period="0A", grade=RegistryAuthorityGrade.CALCULATION
    )
    relation_binding_values = materialize_relation_binding_values(snapshot.revision, relation_values, period="0A")
    # Resolve every previous_filing carry binding (BIN-stock 00670 AND the art.13
    # dotaciones-deterioro 01494/01495) from the local observation store; any the
    # store cannot satisfy default to zero (present-or-zero-carry), so the
    # available-value projector below receives every carry this scenario seeds.
    prefilled = resolve_bindings_from_local_store(snapshot).binding_values
    carry_defaults = {
        c.binding: Decimal("0") for c in snapshot.revision.casillas if c.input_kind.value == "bound" and c.binding
    }
    binding_values = {**carry_defaults, **prefilled, **relation_binding_values, **_PROFILE_DECIMAL_BINDINGS}
    inputs = {
        **resolve_available_bound_inputs_by_casilla_id(snapshot.revision, binding_values),
        **(manual_inputs or {}),
    }
    result = calculate_registry_snapshot(
        snapshot,
        inputs=inputs,
        binding_values=binding_values,
        enum_binding_values=_PROFILE_ENUM_BINDINGS,
        relation_values=relation_values,
        date_context={"filing_period": date(filing_year, 7, 25)},
    )
    return result, len(result.values)


def _resolve_and_supply_relations(
    *,
    filing_year: int,
    obs_repo: CalculationObservationRepository,
) -> dict[RelationId, Decimal]:
    snapshot = resources().modelos.authority.snapshot(
        _MODELO_200, filing_year=filing_year, period="0A", grade=RegistryAuthorityGrade.CALCULATION
    )
    resolved = {
        item.relation: item.value
        for item in resolve_relations_from_local_store(snapshot, repository=obs_repo).values
        if item.value is not None
    }
    # No instalments this scenario: supply the same-year M202 pagos relation as zero
    # (it is not the cross-year hook under test).
    resolved.setdefault(_M200_PAGOS_RELATION, Decimal("0"))
    resolved.setdefault(_M200_PAGOS_RELATION_40_2, Decimal("0"))
    return resolved


def test_modelo_200_opening_bin_stock_resolves_from_prior_year(tmp_path: Path) -> None:
    """Casilla 00670 (opening BIN stock) auto-resolves to the prior year's 00671.

    The cross-year continuity contract: once the prior M200 is recorded, the
    ``filing_year_delta = -1`` carry populates casilla 00670 from that prior
    00671 — the operator does not re-key the carried BIN stock.
    """
    with isolated_runtime_profile(tmp_path=tmp_path):
        obs_repo = CalculationObservationRepository()
        _seed_m200_bin_stock(source_year=2024, stock=_BIN_STOCK_BY_SOURCE_YEAR[2024], obs_repo=obs_repo)
        resolved = _resolve_and_supply_relations(filing_year=_YEAR_N, obs_repo=obs_repo)
        result, _ = _calculate_200(filing_year=_YEAR_N, relation_values=resolved)
    assert Decimal(result.values[_M200_BIN_PENDIENTE_INICIO]) == _BIN_STOCK_BY_SOURCE_YEAR[2024]


def test_modelo_200_bin_stock_enrolls_two_renta_years(tmp_path: Path) -> None:
    """End-to-end enrollment: M200 BIN stock carry across two renta years.

    Drives the real M200 engine for two distinct renta years (2025, 2026),
    each sourcing the prior year's 00671 BIN stock (2024, 2025), records each
    through the :class:`EnrollmentRecorder` (CALC), and cross-checks the
    recorded two-year set against the authorization manifest. Year N's prior
    filing is in the store but must not contaminate Year N+1's resolver. A
    single-year or stub run raises at :func:`assert_enrollment_matches_manifest`.
    """
    recorder = EnrollmentRecorder(_MODELO_200)

    with isolated_runtime_profile(tmp_path=tmp_path):
        obs_repo = CalculationObservationRepository()
        _seed_m200_bin_stock(source_year=2024, stock=_BIN_STOCK_BY_SOURCE_YEAR[2024], obs_repo=obs_repo)
        _seed_m200_bin_stock(source_year=2025, stock=_BIN_STOCK_BY_SOURCE_YEAR[2025], obs_repo=obs_repo)

        resolved_n = _resolve_and_supply_relations(filing_year=_YEAR_N, obs_repo=obs_repo)
        result_n, produced_n = _calculate_200(filing_year=_YEAR_N, relation_values=resolved_n)
        recorder.record_calculation_year(filing_year=_YEAR_N, produced_value_count=produced_n)

        resolved_n1 = _resolve_and_supply_relations(filing_year=_YEAR_N_PLUS_1, obs_repo=obs_repo)
        result_n1, produced_n1 = _calculate_200(filing_year=_YEAR_N_PLUS_1, relation_values=resolved_n1)
        recorder.record_calculation_year(filing_year=_YEAR_N_PLUS_1, produced_value_count=produced_n1)

    # Wiring invariant: each year's opening BIN stock equals the prior year's
    # end-of-year stock, year-isolated.
    assert Decimal(result_n.values[_M200_BIN_PENDIENTE_INICIO]) == _BIN_STOCK_BY_SOURCE_YEAR[2024]
    assert Decimal(result_n1.values[_M200_BIN_PENDIENTE_INICIO]) == _BIN_STOCK_BY_SOURCE_YEAR[2025]

    evidence = recorder.evidence()
    assert evidence.distinct_renta_years == (_YEAR_N, _YEAR_N_PLUS_1)
    assert_enrollment_matches_manifest(evidence)


# ---------------------------------------------------------------------------
# Cap-formula worked example (LIS art. 26.1): when the base imponible previa is
# large enough that 70% of it exceeds the EUR 1.000.000 floor, the computed
# ceiling DP200014:bin-aplicada-maxima must select the 70%-of-base-previa branch
# (not the floor), clamped by the available BIN stock. This test drives the REAL
# cap formula end-to-end through the M200 engine so the 70% branch — and the
# base-previa operand it reads — is covered.
# ---------------------------------------------------------------------------

#: Resultado contable de la cuenta de pérdidas y ganancias (casilla 00501), the
#: operand the base imponible previa (00550) is computed from.
_M200_RESULTADO_CONTABLE: CasillaId = validated_casilla_id("00501", surface="_M200_RESULTADO_CONTABLE")
_M200_BASE_PREVIA: CasillaId = validated_casilla_id("DP200014:00550", surface="_M200_BASE_PREVIA")


def test_modelo_200_bin_aplicada_maxima_selects_70_percent_branch(tmp_path: Path) -> None:
    """The art.26.1 ceiling computes 70%·base previa when it exceeds the EUR 1M floor.

    Worked scenario: a sociedad with resultado contable 5.000.000 € and no
    correcciones has base imponible previa (00550) = 5.000.000 €. LIS art. 26.1
    (BOE-A-2014-12328): the BIN compensable límite is «el 70 por ciento de la
    base imponible previa», with «en todo caso» a floor of «1 millón de euros».
    Here 70 %·5.000.000 = 3.500.000 € dominates the 1.000.000 € floor, and the
    BIN stock carried from the prior year (4.000.000 €) does not clip it, so the
    computed ceiling DP200014:bin-aplicada-maxima = 3.500.000 €.

    Non-tautological grounding: the expected 3.500.000 € is the BOE-stated 70 %
    rate applied to the worked base, not a re-run of the registry formula; the
    test proves the engine wires the 70 % branch (and reads casilla 00550 as the
    base operand) rather than falling back to the EUR 1M floor.
    """
    prior_year_bin_stock = Decimal("4000000.00")
    resultado_contable = Decimal("5000000.00")
    expected_ceiling = Decimal("3500000.00")  # 70 % de 5.000.000 € (LIS art. 26.1)

    with isolated_runtime_profile(tmp_path=tmp_path):
        obs_repo = CalculationObservationRepository()
        _seed_m200_bin_stock(source_year=2024, stock=prior_year_bin_stock, obs_repo=obs_repo)
        resolved = _resolve_and_supply_relations(filing_year=_YEAR_N, obs_repo=obs_repo)
        result, _ = _calculate_200(
            filing_year=_YEAR_N,
            relation_values=resolved,
            manual_inputs={_M200_RESULTADO_CONTABLE: resultado_contable},
        )

    # The base previa operand the cap reads is the computed 00550 = 00501.
    assert Decimal(result.values[_M200_BASE_PREVIA]) == resultado_contable
    # The opening BIN stock carried from the prior year does not clip the 70% branch.
    assert Decimal(result.values[_M200_BIN_PENDIENTE_INICIO]) == prior_year_bin_stock
    # The ceiling selects 70%·base previa over the EUR 1M floor and the stock.
    assert Decimal(result.values[_M200_BIN_APLICADA_MAXIMA]) == expected_ceiling
