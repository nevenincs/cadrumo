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
explicit ``C`` disposition and asserts the credit carries normally.

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

from ....core import Period, ResultDisposition
from ....core.casilla_id import CasillaId, validated_casilla_id
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.calculations.registry.bindings import resolve_available_bound_inputs_by_casilla_id
from ....domain.calculations.registry.formula_runtime import RegistryCalculationResult, calculate_registry_snapshot
from ....domain.calculations.registry.ids import RelationId
from ....domain.calculations.registry.relations import materialize_relation_binding_values
from ....domain.calculations.registry.temporal import select_revision
from ....domain.modelos.codes import ModeloCode
from ....domain.modelos.work_unit import WorkUnit, derive_work_unit_id
from ....domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from ....tests import general_m303_filing_evidence
from ....tests.registry_tree import bundled_registry_tree
from ....tests.secure_sql import isolated_runtime_profile
from ...modelo._filed_revision_observation import persist_filed_revision_observation
from .._relation_prefill import resolve_relations_from_local_store
from ..iva_compensation_history import IvaCompensationHistoryRepository
from ..observations_repository import CalculationObservationRepository

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_MODELO = "303"
_YEAR_N = 2025
_YEAR_N_PLUS_1 = 2026
_BUCKET_ID = "2983d936-f658-4178-977b-3d11f30cb3b2"  # was 'bucket-m303-refund'


#: The law-determined Modelo 303 revision for 2025/4T. Stamped on the persisted
#: carry observation so the cross-period carry gate re-confirms it (a divergent
#: stamp would silently drop the carry).
def _law_determined_revision_id(modelo_id: str, *, filing_year: int, period: str) -> str:
    """Resolve the revision the law selects, without validating the whole registry.

    Naming a revision is selection, not filing. Both the validated authority and
    its inspection projection validate the full tree first, which refuses while
    filing capability is absent -- so either would make this constant
    unobtainable for a reason unrelated to the carry under test. The compiler
    plus the canonical temporal resolver answer the same question and are the
    only rungs that stay available.
    """
    modelos, _catalogues = bundled_registry_tree()
    modelo = next(candidate for candidate in modelos if candidate.id == modelo_id)
    return str(select_revision(modelo, filing_year=filing_year, period=period).id)


_REVISION = _law_determined_revision_id("303", filing_year=2025, period="4T")

_CARRY_RELATION: RelationId = "modelo-303-rel-self-compensacion-anteriores"
_CARRY_BINDING = "modelo-303-compensacion-pendiente-anteriores"


_M303_SALDO_COMPENSACION_CASILLA: CasillaId = validated_casilla_id("iva.compensacion-disponible-fin-periodo")

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
    snapshot = bundled_authority().snapshot(_MODELO, filing_year=filing_year, period=period)
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
    inputs = resolve_available_bound_inputs_by_casilla_id(snapshot.revision, binding_values)
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
    filing_instance_evidence = general_m303_filing_evidence(
        Period.from_year_and_code(2025, "4T"), reference="test:m303-refunded-period-carry"
    )
    revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit_id,
        input_values_by_casilla_id={},
        binding_overrides={},
        casilla_values=values,
        filing_instance_evidence=filing_instance_evidence,
        source_provenance=(),
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
        filing_instance_evidence=filing_instance_evidence,
        source_provenance=(),
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
    snapshot_n1 = bundled_authority().snapshot(_MODELO, filing_year=_YEAR_N_PLUS_1, period="1T")
    relation_values = resolve_relations_from_local_store(snapshot_n1, repository=obs_repo)
    resolved: dict[RelationId, Decimal] = {
        item.relation: item.value for item in relation_values.values if item.value is not None
    }
    return resolved.get(_CARRY_RELATION)


def test_refunded_4t_period_carries_zero_into_next_period(tmp_path: Path) -> None:
    """A refunded (devolución) 4T credit period carries ZERO into 1T/N+1 casilla 110.

    The engine produces a real negative-result saldo for 4T/N. Filing that period
    with the filing-boundary ``D`` disposition excludes the generated credit from
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
            result_disposition=ResultDisposition.DEVOLUCION,
            taxpayer_nif="12345678Z",
        )

        carry_in = _carry_in_for_year_n_plus_1(obs_repo)
        history_state = IvaCompensationHistoryRepository().load_period(_year_n_4t_work_unit().period)

    assert carry_in == Decimal("0")
    assert history_state is not None
    assert history_state.generated_amount == Decimal("0")


def test_carried_4t_period_carries_the_credit_forward_control(tmp_path: Path) -> None:
    """CONTROL (non-regressive): the SAME credit period, compensar-disposed, carries forward.

    the standard compensación behaviour every existing carry chain relies on.
    The only difference from the refunded test is the explicit ``C``
    disposition. The engine-produced saldo carries into 1T/N+1 casilla 110
    normally.
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
            result_disposition=ResultDisposition.COMPENSACION,
            taxpayer_nif="12345678Z",
        )

        carry_in = _carry_in_for_year_n_plus_1(obs_repo)
        history_state = IvaCompensationHistoryRepository().load_period(_year_n_4t_work_unit().period)

    assert carry_in is not None
    assert carry_in == carried_saldo
    assert carry_in > Decimal("0")
    assert history_state is not None
    assert history_state.generated_amount == carried_saldo
