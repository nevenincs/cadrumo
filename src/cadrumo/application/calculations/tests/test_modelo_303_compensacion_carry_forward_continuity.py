"""E2E continuity: Modelo 303 IVA compensación-pendiente cross-year carry.

The autoliquidación IVA experience spans the four quarterly Modelo 303
filings of a renta year and wraps into the next year's first quarter.
LIVA arts. 99, 115-116 and RD 1624/1992 arts. 29-30 define the
compensación carry: when a period's ``iva.resultado`` is negative (more
IVA soportado-deducible than devengado), the credit becomes a saldo a
compensar that rolls forward. The saldo available at the end of one
period (:class:`registry casilla` ``iva.compensacion-disponible-fin-periodo``)
flows into the *next* period's casilla 110 ("Cuotas a compensar pendientes
de periodos anteriores") and is applied there.

The registry models this as the self-relation
``modelo-303-rel-self-compensacion-anteriores``: a ``previous_period``
relation with ``source_period_offset_from_target = -1`` whose
``source_casilla_id`` (``iva.compensacion-disponible-fin-periodo``) feeds the
``target_binding`` ``modelo-303-compensacion-pendiente-anteriores`` (casilla
110). For the 4T → 1T boundary the offset wraps the source year back by one
(1T ordinal 1, offset -1 → prior-year 4T), so the carry is genuinely
cross-renta, not merely cross-quarter.

This module is the multi-year-renta authorization enrollment for Modelo
303. It drives the REAL backend (real encrypted-SQLite observation store,
the real registry authority, the real registry calculation engine, the
real ``previous_filing``/relation resolver — no mocks) across two distinct
renta years: it computes a credit-producing 4T of year N, records it as a
filed observation, then resolves and computes 1T of year N+1 and asserts
its casilla 110 auto-resolves to year N's carried saldo with no manual
re-entry. Both calculated years are recorded through the
:class:`EnrollmentRecorder` and cross-checked against the authorization
manifest via :func:`assert_enrollment_matches_manifest`.

Grounding (non-tautological): the year-N 4T saldo is produced by the
engine from the credit scenario (deducible > devengada), never
hand-computed against the formula under test; the load-bearing assertion
is the *wiring* invariant — year N+1's casilla 110 equals year N's
persisted ``iva.compensacion-disponible-fin-periodo`` — which LIVA art. 99
defines as the prior-period credit carried forward. A registry-gap
WORKAROUND supplies ``modelo-303-autoconsumo-promotor-base = 0`` because
that ``source = "profile"`` binding is not populated on the direct-calculate
path; the workaround is documented inline and does not modify the registry
file.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....core import CasillaId, validated_casilla_id
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.calculations.registry.bindings import (
    RegistryModeloObservation,
    resolve_available_bound_inputs_by_casilla_id,
)
from ....domain.calculations.registry.formula_runtime import RegistryCalculationResult, calculate_registry_snapshot
from ....domain.calculations.registry.ids import RelationId
from ....domain.calculations.registry.relations import materialize_relation_binding_values
from ....tests.secure_sql import isolated_runtime_profile
from .._multi_year import EnrollmentRecorder, assert_enrollment_matches_manifest
from .._observations_repository import CalculationObservationRepository
from .._relation_prefill import resolve_relations_from_local_store

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

#: Modelo id this module enrolls into the multi-year-renta authorization gate.
_MODELO = "303"

#: The two distinct renta years the carry spans (4T/N -> 1T/N+1 wrap).
_YEAR_N = 2025
_YEAR_N_PLUS_1 = 2026

# The 2024 intra-year boundary changes M303's official diseño after 2T. The
# source 2T is governed by ``aeat-dr-303-2024-early`` and the target 3T by
# ``aeat-dr-303-2024-late``; both are the accepted official M303 sources for
# their respective registry revisions.
_YEAR_2024 = 2024
_EARLY_2024_PERIOD = "2T"
_LATE_2024_PERIOD = "3T"
_EARLY_2024_REVISION = "2024-hasta-08-y-2t"
_LATE_2024_REVISION = "2024-desde-09-y-3t"

#: The relation that carries the prior-period saldo into casilla 110, and the
#: binding/casilla it targets. Declared in the 303 2023+ revision.
_CARRY_RELATION: RelationId = "modelo-303-rel-self-compensacion-anteriores"
_CARRY_BINDING = "modelo-303-compensacion-pendiente-anteriores"


_M303_RESULTADO_CASILLA: CasillaId = validated_casilla_id("iva.resultado")
_M303_COMPENSACION_PENDIENTE_CASILLA: CasillaId = validated_casilla_id("iva.compensacion-pendiente-periodos-anteriores")
_M303_SALDO_COMPENSACION_CASILLA: CasillaId = validated_casilla_id("iva.compensacion-disponible-fin-periodo")

#: WORKAROUND — the 303 2023+ revision carries a ``source = "profile"``
#: binding ``modelo-303-autoconsumo-promotor-base`` (LIVA art. 9.1.c / 79.4
#: autoconsumo del promotor). The direct-calculate path does not run the
#: profile resolver, so the binding is unpopulated and the engine refuses the
#: unresolved bound casilla. Supplying it as zero (no autoconsumo del
#: promotor for this filer) lets the engine resolve the dependent casilla.
#: This is a registry-gap workaround, NOT a fix of the registry file.
_AUTOCONSUMO_PROMOTOR_BASE_BINDING = "modelo-303-autoconsumo-promotor-base"

#: The Administración del Estado attribution ratio (casilla 65). For a
#: territorio-común filer the whole result is attributable to the central
#: administration, so the ratio is 100. This is a ``source = "profile"`` binding
#: the direct-calculate path does not populate; supplying 100 reflects the
#: standard (non-foral) filer the carry scenario models. Grounded in LIVA art.
#: 115 and Ley 12/2002 art. 29 (Concierto Económico) — for filers outside the
#: foral territories [65] = 100 and casilla 66 = casilla 64.
_STATE_ATTRIBUTION_RATIO_BINDING = "modelo-303-profile-state-attribution-ratio"

#: The five ``ledger_iva_aggregation`` cuota bindings whose bound casillas the
#: engine requires a fact for. This scenario drives the result through the
#: manual section totals (casillas 27/45), not per-rate ledger detail, so each
#: aggregation binding is supplied as zero (no per-rate ledger line). They feed
#: the informational devengada/deducible *total* casillas, not the [46]
#: régimen-general result that the carry depends on.
_LEDGER_CUOTA_BINDINGS = (
    "modelo-303-iva-repercutido-general-cuota",
    "modelo-303-iva-repercutido-reducido-cuota",
    "modelo-303-iva-repercutido-super-reducido-cuota",
    "modelo-303-iva-soportado-interiores-cuota",
    "modelo-303-iva-soportado-importaciones-cuota",
    "modelo-303-iva-autorepercutido-intracomunitaria-cuota",
    "modelo-303-iva-autorepercutido-intracomunitaria-devengado-base",
    "modelo-303-iva-autorepercutido-intracomunitaria-devengado-cuota",
    "modelo-303-iva-autorepercutido-intracomunitaria-deducible-cuota",
    "modelo-303-iva-autorepercutido-interior-devengado-cuota",
    "modelo-303-iva-autorepercutido-interior-deducible-cuota",
    "modelo-303-casilla-59-entregas-intracomunitarias-base",
    "modelo-303-casilla-60-exportaciones-base",
    "modelo-303-casilla-120-no-sujetas-localizacion-base",
    "modelo-303-casilla-122-inversion-sujeto-pasivo-base",
    "modelo-303-iva-repercutido-general-base",
    "modelo-303-iva-repercutido-reducido-base",
    "modelo-303-iva-repercutido-reducido-transitorio-base",
    "modelo-303-iva-repercutido-reducido-transitorio-cuota",
    "modelo-303-iva-repercutido-super-reducido-base",
    "modelo-303-iva-repercutido-super-reducido-transitorio-base",
    "modelo-303-iva-repercutido-super-reducido-transitorio-cuota",
    "modelo-303-iva-soportado-interiores-base",
    "modelo-303-recargo-equivalencia-general-cuota",
    "modelo-303-recargo-equivalencia-reducido-cuota",
    "modelo-303-recargo-equivalencia-super-reducido-cuota",
    # Criterio-de-caja informational bindings (LIVA arts. 163 decies ff.) for
    # casillas 62/63/74/75; zero when the fixture has no cash-accounting rows.
    "modelo-303-criterio-caja-entregas-art75-base",
    "modelo-303-criterio-caja-entregas-art75-cuota",
    "modelo-303-criterio-caja-adquisiciones-base",
    "modelo-303-criterio-caja-adquisiciones-cuota",
)

_CLOCK = datetime(2026, 5, 1, 9, 0, 0, tzinfo=UTC)

#: Manual section-total casillas that drive the régimen-general result on the
#: printed M303 form: [46] = total cuota devengada - total a deducir (Orden
#: EHA/3786/2008 art. 1). Per commit 2677c82d6, `iva.resultado-regimen-general`
#: reads the COMPUTED semantic totals `iva.cuota-devengada-total` /
#: `iva.cuota-deducible-total`, which the engine derives from per-rate ledger
#: cuota bindings. Per-rate cuota bindings are therefore the only path to inject
#: a credit scenario; the form-number casillas 27 / 45 are display-only
#: re-projections that the formula no longer reads. The fixture drives a single
#: general-rate cuota binding on each side to make `cuota-devengada-total < cuota-
#: deducible-total`, yielding a negative régimen-general result — the IVA credit
#: that becomes the saldo a compensar carried forward.


def _calculate_303(
    *,
    filing_year: int,
    period: str,
    cuota_binding_overrides: Mapping[str, Decimal],
    relation_values: Mapping[RelationId, Decimal],
) -> tuple[RegistryCalculationResult, int]:
    """Run the REAL registry 303 calculation; return result + produced-value count.

    Mirrors the production calculate path's relation materialisation: a
    resolved relation value is copied into its target binding (casilla 110)
    via :func:`materialize_relation_binding_values`, merged with the profile-gap
    workaround bindings, layered under per-rate cuota binding overrides
    supplied by the caller, resolved into bound casilla inputs, and evaluated
    by the engine. Cuota bindings are the only input path into the régimen-
    general formula since `2677c82d6` repointed it at the computed semantic
    totals; manual casilla inputs against the form-number boxes 27/45 are no
    longer read and the engine refuses computed-casilla inputs.
    """
    snapshot = bundled_authority().snapshot(_MODELO, filing_year=filing_year, period=period)
    relation_binding_values = materialize_relation_binding_values(
        snapshot.revision,
        dict(relation_values),
        period=period,
    )
    binding_values = {
        # Casilla 110 is a bound casilla: the engine requires its binding fact
        # to always be present. Default it to zero (no prior-period carry) so
        # year N's 4T — which has no prior period — resolves; the relation
        # materialisation below overrides it for year N+1's 1T with the carried
        # saldo, mirroring the production precedence (relation values win).
        _CARRY_BINDING: Decimal("0"),
        _AUTOCONSUMO_PROMOTOR_BASE_BINDING: Decimal("0"),
        _STATE_ATTRIBUTION_RATIO_BINDING: Decimal("100"),
        **{binding: Decimal("0") for binding in _LEDGER_CUOTA_BINDINGS},
        **cuota_binding_overrides,
        **relation_binding_values,
    }
    inputs = resolve_available_bound_inputs_by_casilla_id(snapshot.revision, binding_values)
    result = calculate_registry_snapshot(
        snapshot,
        inputs=inputs,
        binding_values=binding_values,
        relation_values=dict(relation_values),
        date_context={"filing_period": date(filing_year, 12, 31)},
    )
    return result, len(result.values)


def _registry_observation(
    *,
    filing_year: int,
    period: str,
    result: RegistryCalculationResult,
) -> RegistryModeloObservation:
    return RegistryModeloObservation(
        modelo=_MODELO,
        filing_year=filing_year,
        period=period,
        observations=result.observations,
    )


# Year-N 4T credit scenario: a general-rate cuota repercutida of 21.00 against
# a general-rate cuota soportada (interiores) of 63.00. The engine sums each
# side into the semantic totals (`iva.cuota-devengada-total` = 21,
# `iva.cuota-deducible-total` = 63), then derives `iva.resultado-regimen-general`
# = 21 - 63 = -42, a negative ``iva.resultado`` whose absolute value becomes the
# saldo a compensar generated this period and carried into the next. The exact
# saldo is produced by the engine, never hand-computed against the formula.
_YEAR_N_4T_INPUTS = {
    "modelo-303-iva-repercutido-general-cuota": Decimal("21.00"),
    "modelo-303-iva-soportado-interiores-cuota": Decimal("63.00"),
}

# Year-N+1 1T scenario: a small positive result (cuota repercutida 50, no
# cuota soportada) so the carried prior-year saldo lands in casilla 110 and is
# applied against it.
_YEAR_N_PLUS_1_1T_INPUTS = {
    "modelo-303-iva-repercutido-general-cuota": Decimal("50.00"),
}

# LIVA art. 99 permits a negative settlement to be carried into the following
# period. The official 2024 early M303 design (``aeat-dr-303-2024-early``)
# supplies the 2T form context. These independently grounded inputs make the
# expected source settlement and available carry 42.00: 63.00 deductible VAT
# minus 21.00 accrued VAT, rather than an amount echoed back from the engine.
_YEAR_2024_2T_CREDIT_INPUTS = {
    "modelo-303-iva-repercutido-general-cuota": Decimal("21.00"),
    "modelo-303-iva-soportado-interiores-cuota": Decimal("63.00"),
}
_YEAR_2024_CARRY = Decimal("42.00")


def test_2024_2t_credit_carries_to_3t_across_the_official_design_boundary(tmp_path: Path) -> None:
    """A real 2T/2024 credit reaches 3T's carried-carry casilla and binding.

    LIVA art. 99 makes the 2T surplus available for the following settlement.
    The two source values are independently grounded form inputs: 63.00
    deductible less 21.00 accrued VAT yields the asserted 42.00 carry; the
    calculation engine is not used as the expected-value oracle.
    """
    with isolated_runtime_profile(tmp_path=tmp_path):
        observation_repository = CalculationObservationRepository()
        source_snapshot = bundled_authority().snapshot(
            _MODELO,
            filing_year=_YEAR_2024,
            period=_EARLY_2024_PERIOD,
        )
        assert source_snapshot.revision.id == _EARLY_2024_REVISION
        source_result, _ = _calculate_303(
            filing_year=_YEAR_2024,
            period=_EARLY_2024_PERIOD,
            cuota_binding_overrides=_YEAR_2024_2T_CREDIT_INPUTS,
            relation_values={},
        )
        assert source_result.values[_M303_RESULTADO_CASILLA] == -_YEAR_2024_CARRY
        assert source_result.values[_M303_SALDO_COMPENSACION_CASILLA] == _YEAR_2024_CARRY
        observation_repository.save(
            observation_repository.prepare_observation_envelope(
                _registry_observation(
                    filing_year=_YEAR_2024,
                    period=_EARLY_2024_PERIOD,
                    result=source_result,
                ),
                source_kind="app_filing",
                captured_at=_CLOCK,
                stamped_revision_id=source_snapshot.revision.id,
            )
        )

        target_snapshot = bundled_authority().snapshot(
            _MODELO,
            filing_year=_YEAR_2024,
            period=_LATE_2024_PERIOD,
        )
        assert target_snapshot.revision.id == _LATE_2024_REVISION
        relation_values = resolve_relations_from_local_store(target_snapshot, repository=observation_repository)
        carry_relation = next(item for item in relation_values.values if item.relation == _CARRY_RELATION)
        resolved = {item.relation: item.value for item in relation_values.values if item.value is not None}
        target_binding_values = materialize_relation_binding_values(
            target_snapshot.revision,
            resolved,
            period=_LATE_2024_PERIOD,
        )
        target_result, _ = _calculate_303(
            filing_year=_YEAR_2024,
            period=_LATE_2024_PERIOD,
            cuota_binding_overrides={},
            relation_values=resolved,
        )

    assert carry_relation.source_modelo == _MODELO
    assert carry_relation.source_filing_year == _YEAR_2024
    assert carry_relation.source_periods == (_EARLY_2024_PERIOD,)
    assert carry_relation.value == _YEAR_2024_CARRY
    assert target_binding_values[_CARRY_BINDING] == _YEAR_2024_CARRY
    assert target_result.values[_M303_COMPENSACION_PENDIENTE_CASILLA] == _YEAR_2024_CARRY


def test_2024_3t_refuses_a_2t_observation_stamped_with_the_late_revision(tmp_path: Path) -> None:
    """A persisted 2T observation cannot carry when its design stamp is wrong."""
    with isolated_runtime_profile(tmp_path=tmp_path):
        observation_repository = CalculationObservationRepository()
        source_result, _ = _calculate_303(
            filing_year=_YEAR_2024,
            period=_EARLY_2024_PERIOD,
            cuota_binding_overrides=_YEAR_2024_2T_CREDIT_INPUTS,
            relation_values={},
        )
        observation_repository.save(
            observation_repository.prepare_observation_envelope(
                _registry_observation(
                    filing_year=_YEAR_2024,
                    period=_EARLY_2024_PERIOD,
                    result=source_result,
                ),
                source_kind="app_filing",
                captured_at=_CLOCK,
                # Mutation bite: 2T must be stamped with the early, not 3T,
                # design. The real carry gate drops this persisted source.
                stamped_revision_id=_LATE_2024_REVISION,
            )
        )
        target_snapshot = bundled_authority().snapshot(
            _MODELO,
            filing_year=_YEAR_2024,
            period=_LATE_2024_PERIOD,
        )
        relation_values = resolve_relations_from_local_store(target_snapshot, repository=observation_repository)

    carry_relation = next(item for item in relation_values.values if item.relation == _CARRY_RELATION)
    assert carry_relation.value is None


def test_year_n_4t_credit_produces_carry_forward_saldo(tmp_path: Path) -> None:
    """A credit-making 4T of year N produces a positive carry saldo.

    Deducible exceeds devengada, so ``iva.resultado`` is negative and the
    engine generates a ``iva.compensacion-disponible-fin-periodo`` saldo —
    the seed the next year's 1T carries forward. The value is produced by the
    real engine from the credit scenario, never hand-computed.
    """
    with isolated_runtime_profile(tmp_path=tmp_path):
        result, produced = _calculate_303(
            filing_year=_YEAR_N,
            period="4T",
            cuota_binding_overrides=_YEAR_N_4T_INPUTS,
            relation_values={},
        )
    assert produced > 0
    assert result.values[_M303_RESULTADO_CASILLA] < Decimal("0")
    assert result.values[_M303_SALDO_COMPENSACION_CASILLA] > Decimal("0")


def test_year_n_plus_1_1t_casilla_110_auto_resolves_from_prior_year_4t(tmp_path: Path) -> None:
    """1T of year N+1 auto-resolves casilla 110 to year N's 4T carried saldo.

    The cross-renta continuity contract: once year N's 4T is recorded as a
    filed observation, the relation resolver (``source_period_offset_from_target
    = -1``, which wraps 1T back to the prior year's 4T) populates year N+1's
    1T casilla-110 binding with year N's
    ``iva.compensacion-disponible-fin-periodo`` — the operator does not re-key
    the prior-year credit by hand.
    """
    with isolated_runtime_profile(tmp_path=tmp_path):
        obs_repo = CalculationObservationRepository()
        result_n, _ = _calculate_303(
            filing_year=_YEAR_N,
            period="4T",
            cuota_binding_overrides=_YEAR_N_4T_INPUTS,
            relation_values={},
        )
        carried_saldo = result_n.values[_M303_SALDO_COMPENSACION_CASILLA]
        obs_repo.save(
            obs_repo.prepare_observation_envelope(
                _registry_observation(filing_year=_YEAR_N, period="4T", result=result_n),
                source_kind="app_filing",
                captured_at=_CLOCK,
            )
        )

        snapshot_n1 = bundled_authority().snapshot(_MODELO, filing_year=_YEAR_N_PLUS_1, period="1T")
        relation_values = resolve_relations_from_local_store(snapshot_n1, repository=obs_repo)
        resolved: dict[RelationId, Decimal] = {
            item.relation: item.value for item in relation_values.values if item.value is not None
        }

    assert resolved.get(_CARRY_RELATION) == carried_saldo
    assert carried_saldo > Decimal("0")


def test_modelo_303_compensacion_carry_enrolls_two_renta_years(tmp_path: Path) -> None:
    """End-to-end enrollment: 4T/N credit -> 1T/N+1 casilla 110 across two renta years.

    Drives the REAL 303 backend for both renta years, records each through the
    :class:`EnrollmentRecorder` (calculation mode, evidence = produced-value
    count from a real engine run), and cross-checks the recorded distinct-year
    set against the authorization manifest claim. The load-bearing wiring
    assertion is that year N+1's 1T casilla 110 equals year N's 4T persisted
    saldo — the prior-year credit carried forward with no manual re-entry.
    """
    recorder = EnrollmentRecorder(_MODELO)
    with isolated_runtime_profile(tmp_path=tmp_path):
        obs_repo = CalculationObservationRepository()

        # Year N — 4T: real calculation produces the carry saldo.
        result_n, produced_n = _calculate_303(
            filing_year=_YEAR_N,
            period="4T",
            cuota_binding_overrides=_YEAR_N_4T_INPUTS,
            relation_values={},
        )
        recorder.record_calculation_year(filing_year=_YEAR_N, produced_value_count=produced_n)
        carried_saldo = result_n.values[_M303_SALDO_COMPENSACION_CASILLA]
        obs_repo.save(
            obs_repo.prepare_observation_envelope(
                _registry_observation(filing_year=_YEAR_N, period="4T", result=result_n),
                source_kind="app_filing",
                captured_at=_CLOCK,
            )
        )

        # Year N+1 — 1T: the carry resolves from the local store (cross-renta
        # wrap), lands in casilla 110, and a real calculation runs with it.
        snapshot_n1 = bundled_authority().snapshot(_MODELO, filing_year=_YEAR_N_PLUS_1, period="1T")
        relation_values = resolve_relations_from_local_store(snapshot_n1, repository=obs_repo)
        resolved: dict[RelationId, Decimal] = {
            item.relation: item.value for item in relation_values.values if item.value is not None
        }
        result_n1, produced_n1 = _calculate_303(
            filing_year=_YEAR_N_PLUS_1,
            period="1T",
            cuota_binding_overrides=_YEAR_N_PLUS_1_1T_INPUTS,
            relation_values=resolved,
        )
        recorder.record_calculation_year(filing_year=_YEAR_N_PLUS_1, produced_value_count=produced_n1)

    # Cross-renta wiring invariant: 1T/N+1 casilla 110 == 4T/N persisted saldo.
    assert result_n1.values[_M303_COMPENSACION_PENDIENTE_CASILLA] == carried_saldo
    assert carried_saldo > Decimal("0")

    # Authorization-gate enrollment: the recorded two-year set is cross-checked
    # against the manifest's renta_years claim. A single-year or stub run would
    # raise here, turning the gate RED.
    evidence = recorder.evidence()
    assert evidence.distinct_renta_years == (_YEAR_N, _YEAR_N_PLUS_1)
    assert_enrollment_matches_manifest(evidence)
