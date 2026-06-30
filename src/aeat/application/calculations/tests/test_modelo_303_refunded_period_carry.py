"""Modelo 303 refunded-period cross-period carry: devolución carries zero forward.

A REDEME company under the accepted standing monthly-devolución disposition
policy (or any taxpayer who elects devolución for an eligible negative period)
files that period as a refund request, not as compensación carried into the next
period. The local-file cross-period carry must honour that disposition: when the
filed revision is requested as devolución, the persisted
``iva.compensacion-disponible-fin-periodo`` carries ZERO generated credit, so the
next period's casilla 110 auto-resolves to zero rather than double-claiming the
requested devolución credit.

The CONTROL persists the SAME engine-produced negative-result revision with the
default carried disposition and asserts the credit carries normally — the
behaviour-preserving default that keeps every existing carry chain green.

Grounding (non-tautological): the negative-result saldo is produced by the REAL
registry engine from a credit scenario (deducible > devengada), never
hand-computed against the formula under test. The refunded assertion is the
structural zero-carry invariant; the control compares two engine-derived carry
reads, not a literal. Legal basis: RD 1624/1992 art. 30 / Ley 37/1992 art. 116.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....core import Period
from ....core.resources import resources
from ....domain.calculations.registry import (
    CasillaId,
    RegistryCalculationResult,
    RelationId,
    calculate_registry_snapshot,
    materialize_relation_binding_values,
    resolve_bound_inputs_by_casilla_id,
    validated_casilla_id,
)
from ....domain.modelos._calculation_revision import (
    CalculationRevision,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from ....domain.modelos._codes import ModeloCode
from ....domain.modelos._work_unit import WorkUnit, derive_work_unit_id
from ....tests.secure_sql import isolated_runtime_profile
from ...modelo._filed_revision_observation import persist_filed_revision_observation
from .._observations_repository import CalculationObservationRepository
from .._relation_prefill import resolve_relations_from_local_store

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_MODELO = "303"
_YEAR_N = 2025
_YEAR_N_PLUS_1 = 2026
_BUCKET_ID = "bucket-m303-refund"
#: The law-determined Modelo 303 revision for 2025/4T. Stamped on the persisted
#: carry observation so the cross-period carry gate re-confirms it (a divergent
#: stamp would silently drop the carry).
_REVISION = "2023-y-siguientes"

_CARRY_RELATION: RelationId = "modelo-303-rel-self-compensacion-anteriores"
_CARRY_BINDING = "modelo-303-compensacion-pendiente-anteriores"


def _casilla_id(value: object) -> CasillaId:
    try:
        return validated_casilla_id(value, surface="test casilla id")
    except ValueError as exc:
        raise AssertionError(f"test fixture casilla key {value!r} is not a canonical casilla.id") from exc


_M303_SALDO_COMPENSACION_CASILLA: CasillaId = _casilla_id("iva.compensacion-disponible-fin-periodo")

#: Profile-gap workaround bindings (mirror the carry-continuity contract module;
#: the direct-calculate path does not run the profile resolver).
_AUTOCONSUMO_PROMOTOR_BASE_BINDING = "modelo-303-autoconsumo-promotor-base"
_STATE_ATTRIBUTION_RATIO_BINDING = "modelo-303-profile-state-attribution-ratio"
_LEDGER_CUOTA_BINDINGS = (
    "modelo-303-iva-repercutido-general-cuota",
    "modelo-303-iva-repercutido-reducido-cuota",
    "modelo-303-iva-repercutido-super-reducido-cuota",
    "modelo-303-iva-soportado-interiores-cuota",
    "modelo-303-iva-soportado-importaciones-cuota",
    "modelo-303-iva-autorepercutido-intracomunitaria-cuota",
    "modelo-303-iva-autorepercutido-intracomunitaria-devengado-cuota",
    "modelo-303-iva-autorepercutido-intracomunitaria-deducible-cuota",
    "modelo-303-iva-autorepercutido-interior-devengado-cuota",
    "modelo-303-iva-autorepercutido-interior-deducible-cuota",
    "modelo-303-casilla-59-entregas-intracomunitarias-base",
    "modelo-303-casilla-60-exportaciones-base",
    "modelo-303-iva-repercutido-general-base",
    "modelo-303-iva-repercutido-reducido-base",
    "modelo-303-iva-repercutido-super-reducido-base",
    "modelo-303-iva-soportado-interiores-base",
    "modelo-303-recargo-equivalencia-general-cuota",
    "modelo-303-recargo-equivalencia-reducido-cuota",
    "modelo-303-recargo-equivalencia-super-reducido-cuota",
)

#: A general-rate cuota repercutida below the cuota soportada, so the régimen
#: general result is negative — the IVA credit that becomes the saldo a compensar.
_YEAR_N_4T_CREDIT_INPUTS = {
    "modelo-303-iva-repercutido-general-cuota": Decimal("21.00"),
    "modelo-303-iva-soportado-interiores-cuota": Decimal("63.00"),
}
_YEAR_N_PLUS_1_1T_INPUTS = {
    "modelo-303-iva-repercutido-general-cuota": Decimal("50.00"),
}

_CLOCK = datetime(2026, 5, 1, 9, 0, 0, tzinfo=UTC)


def _calculate_303(
    *,
    filing_year: int,
    period: str,
    cuota_binding_overrides: Mapping[str, Decimal],
    relation_values: Mapping[RelationId, Decimal],
) -> RegistryCalculationResult:
    snapshot = resources().modelos.authority.snapshot(_MODELO, filing_year=filing_year, period=period)
    relation_binding_values = materialize_relation_binding_values(
        snapshot.revision,
        dict(relation_values),
        period=period,
    )
    binding_values = {
        _CARRY_BINDING: Decimal("0"),
        _AUTOCONSUMO_PROMOTOR_BASE_BINDING: Decimal("0"),
        _STATE_ATTRIBUTION_RATIO_BINDING: Decimal("100"),
        **{binding: Decimal("0") for binding in _LEDGER_CUOTA_BINDINGS},
        **cuota_binding_overrides,
        **relation_binding_values,
    }
    inputs = resolve_bound_inputs_by_casilla_id(snapshot.revision, binding_values)
    return calculate_registry_snapshot(
        snapshot,
        inputs=inputs,
        binding_values=binding_values,
        relation_values=dict(relation_values),
        date_context={"filing_period": date(filing_year, 12, 31)},
    )


def _revision_from_result(result: RegistryCalculationResult) -> CalculationRevision:
    """Wrap the engine outputs as a minimal filed CalculationRevision.

    ``persist_filed_revision_observation`` reads only ``revision.observations``
    and the work unit's ``(modelo, filing_year, period)`` key, so a content-
    addressed-id-bearing revision carrying the engine's typed observations is the
    complete input.
    """
    work_unit_id = _year_n_4t_work_unit().work_unit_id
    values = dict(result.values)
    revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit_id,
        input_values_by_casilla_id={},
        binding_overrides={},
        casilla_values=values,
    )
    return CalculationRevision(
        calculation_revision_id=revision_id,
        work_unit_id=work_unit_id,
        state=CalculationRevisionState.PRESENTADO,
        casilla_values=values,
        observations=result.observations,
        created_at=_CLOCK,
        updated_at=_CLOCK,
        verified_at=_CLOCK,
        verified_by="refund-carry-test",
        filed_at=_CLOCK,
        filed_by="refund-carry-test",
    )


def _year_n_4t_work_unit() -> WorkUnit:
    """Build the Modelo 303 2025/4T work unit carrying the law-determined revision.

    Built directly (not via ``create_work_unit``) so the test stays a focused
    carry-projection check: ``persist_filed_revision_observation`` reads only the
    work unit's ``(modelo, filing_year, period, revision_id)``.
    """
    period = Period.from_year_and_code(_YEAR_N, "4T")
    work_unit_id = derive_work_unit_id(
        bucket_id=_BUCKET_ID,
        modelo=_MODELO,
        filing_year=_YEAR_N,
        period=period,
        revision_id=_REVISION,
    )
    return WorkUnit(
        work_unit_id=work_unit_id,
        bucket_id=_BUCKET_ID,
        modelo=ModeloCode(_MODELO),
        filing_year=_YEAR_N,
        period=period,
        revision_id=_REVISION,
        name="m303-2025-4t",
        created_at=_CLOCK,
        updated_at=_CLOCK,
    )


def _carry_in_for_year_n_plus_1(obs_repo: CalculationObservationRepository) -> Decimal | None:
    """Resolve year N+1 1T casilla 110 from whatever year-N 4T carry is persisted."""
    snapshot_n1 = resources().modelos.authority.snapshot(_MODELO, filing_year=_YEAR_N_PLUS_1, period="1T")
    relation_values = resolve_relations_from_local_store(snapshot_n1, repository=obs_repo)
    resolved: dict[RelationId, Decimal] = {
        item.relation: item.value for item in relation_values.values if item.value is not None
    }
    return resolved.get(_CARRY_RELATION)


def test_refunded_4t_period_carries_zero_into_next_period(tmp_path: Path) -> None:
    """A refunded (devolución) 4T credit period carries ZERO into 1T/N+1 casilla 110.

    The engine produces a real negative-result saldo for 4T/N. Filing that period
    as a refund request (``refunded=True``) excludes the generated credit from
    compensación carry, so the persisted carry observation drops the generated
    component and the next period auto-resolves to zero — the requested devolución
    credit is not double-claimed.
    """
    with isolated_runtime_profile(tmp_path=tmp_path):
        result_n = _calculate_303(
            filing_year=_YEAR_N,
            period="4T",
            cuota_binding_overrides=_YEAR_N_4T_CREDIT_INPUTS,
            relation_values={},
        )
        # The scenario genuinely generated a credit; refunding it must zero the carry.
        assert result_n.values[_M303_SALDO_COMPENSACION_CASILLA] > Decimal("0")

        obs_repo = CalculationObservationRepository()
        persist_filed_revision_observation(
            revision=_revision_from_result(result_n),
            work_unit=_year_n_4t_work_unit(),
            repository=obs_repo,
            captured_at=_CLOCK,
            refunded=True,
        )

        carry_in = _carry_in_for_year_n_plus_1(obs_repo)

    assert carry_in == Decimal("0")


def test_carried_4t_period_carries_the_credit_forward_control(tmp_path: Path) -> None:
    """CONTROL (non-regressive): the SAME credit period, compensar-disposed, carries forward.

    The only difference from the refunded test is ``refunded=False`` (the
    default). The engine-produced saldo carries into 1T/N+1 casilla 110 normally —
    the standard compensación behaviour every existing carry chain relies on.
    """
    with isolated_runtime_profile(tmp_path=tmp_path):
        result_n = _calculate_303(
            filing_year=_YEAR_N,
            period="4T",
            cuota_binding_overrides=_YEAR_N_4T_CREDIT_INPUTS,
            relation_values={},
        )
        carried_saldo = result_n.values[_M303_SALDO_COMPENSACION_CASILLA]
        assert carried_saldo > Decimal("0")

        obs_repo = CalculationObservationRepository()
        persist_filed_revision_observation(
            revision=_revision_from_result(result_n),
            work_unit=_year_n_4t_work_unit(),
            repository=obs_repo,
            captured_at=_CLOCK,
        )

        carry_in = _carry_in_for_year_n_plus_1(obs_repo)

    assert carry_in is not None
    assert carry_in == carried_saldo
    assert carry_in > Decimal("0")
