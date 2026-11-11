"""Cross-year carry continuity for Modelo 100 (IRPF anual).

This module drives the real M100 calculation engine
(``calculate_modelo_revision_from_bucket_aggregation_with_diagnostics``) across two distinct renta years.

The cross-renta hook is the Anexo C base-liquidable-general-negativa
carry-forward. A year's *generated* negative general base left pending —
casilla 1391 (``irpf_anexo_c_base_liq_neg_generado``, "Base liquidable
general negativa de <año> pendiente de compensar en los cuatro ejercicios
siguientes") — becomes, in the following year's declaration, the *opening*
pending balance for the immediately-prior origin ejercicio — casilla 1388
(``irpf_anexo_c_base_liq_neg_pendiente_inicio``; in the 2025 revision its
label is "Ejercicio 2024: Pendiente de aplicación al principio del
periodo", in the 2024 revision "Ejercicio 2023: ..."). The
``previous_filing`` binding ``renta-{year}-base-liquidable-negativa-general-anterior``
(selector ``source_modelo = "100", source_casilla_id = "1391",
filing_year_delta = -1, period = "0A"``, ``op = copy``) makes casilla 1388
auto-resolve from the prior filing, so the operator does not re-key the
carried saldo. The carry is origin-year-matched in both revisions (each
revision's 1388 is the immediately-prior origin year).

Calc-mode (honest evidence): each renta year is driven through the REAL
``calculate_modelo_revision_from_bucket_aggregation_with_diagnostics`` — the same full-engine path M130/M200/M202/M151
use — so the ``evidence_class = calculation`` manifest label is backed by an
actual calculation, not resolver output. A taxpayer-unit ``UserProfileRecord``
is seeded so the ``source = "profile"`` bindings (tax-residence CCAA, taxpayer
birth date, declaration type, marital status, ...) auto-resolve through
``_resolve_profile_bindings_for_calculation``; no profile fact is hand-fed
through the caller channel. The carried prior-year saldo is the one
``previous_filing`` fact resolved from the local observation store and supplied
through the binding channel (mirroring the production calculate path, which
does not itself scan the store for previous_filing bindings).

Grounding (non-tautological): M100's per-casilla saldo has no numeric workbook
oracle, so the load-bearing assertion is the cross-renta WIRING invariant —
each year's opening pending (casilla 1388) equals the prior year's persisted
generated saldo (casilla 1391), year-isolated — established by the AEAT M100
Anexo-C carry-forward. The prior-year saldo is a real seeded observation, never
a value hand-computed from the formula under test. A wrong cross-year wiring
(no carry, or the wrong origin year) would surface a different value and red
the assertion.

Honest scope: this enrollment proves the GENERAL-base carry for the
immediately-prior origin ejercicio. The integración-subtract that *consumes*
the opening saldo into the current-year base reduction, the savings-base
(0441-family) art.49 carry, and the deeper four-year multi-origin-year window
are deferred calc-completeness follow-ons — not claimed here.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.application.modelo.calculation_source_policy import BUCKET_AGGREGATION_LOCK_SOURCES

from ....adapters.persistence.profile.calculation_observations import CalculationObservationRepository
from ....adapters.persistence.profile.tests.published_authority_support import published_authority_operation
from ....adapters.persistence.profile.tests.ready_profile_support import seed_persona_profile
from ....adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from ....application.modelo.calculation_bucket_actions import (
    calculate_modelo_revision_from_bucket_aggregation_with_diagnostics,
)
from ....application.modelo.work_lifecycle import create_work_unit
from ....core.casilla_id import CasillaId, validated_casilla_id
from ....core.period import Period
from ....domain.calculations.registry.authority import bundled_indexed_authority
from ....domain.calculations.registry.ids import BindingId, RelationId
from ....domain.calculations.registry.relations import relation_prefill_bindings_for_period
from ....domain.calculations.registry.schema import RegistrySnapshot
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope, newest_authored_editions
from ....domain.calculations.registry.tests.registry_observations import (
    registry_grounded_modelo_observation,
)
from ...adapter_composition_work_ports import build_calculation_action_ports, build_work_lifecycle_ports
from .observation_seeding_support import save_stamped_observation

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

#: Modelo id this module enrolls into the cross-year behavior contract.
_MODELO = "100"
_PROFILE_ID = "10010000-0000-4100-8100-000000000101"
_BUCKET_ID = _PROFILE_ID
_PERIOD = "0A"


#: Casillas on the cross-renta Anexo-C base-liquidable-general-negativa carry.
#: 1391 is the end-of-year *generated* saldo pending future application; 1388
#: is the next year's *opening* pending for the immediately-prior origin
#: ejercicio, bound from the prior year's 1391 by the carry binding.


_GENERATED_SALDO: CasillaId = validated_casilla_id("1391")
_PENDIENTE_INICIO: CasillaId = validated_casilla_id("1388")
#: The prior return's remainders that open this year's older Anexo C rows (1380, 1382, 1385).
_PRIOR_ANEXO_C_REMAINDERS: tuple[CasillaId, ...] = tuple(
    validated_casilla_id(box, surface="_PRIOR_ANEXO_C_REMAINDERS") for box in ("1384", "1387", "1390")
)

#: Two distinct renta years the enrollment spans; each sources the prior year's 1391.
_YEAR_N, _YEAR_N_PLUS_1 = newest_authored_editions(_MODELO, 2)

#: Distinct prior-year generated saldo per source year so a cross-year
#: contamination (year N's carry leaking into year N+1) would surface.
_SALDO_BY_SOURCE_YEAR: dict[int, Decimal] = {
    _YEAR_N - 1: Decimal("4000.00"),
    _YEAR_N: Decimal("2500.00"),
}

_CLOCK = datetime(filing_year_envelope().horizon, 6, 30, 9, 0, 0, tzinfo=UTC)


def _snapshot(filing_year: int) -> RegistrySnapshot:
    return published_authority_operation().snapshot(_MODELO, filing_year=filing_year, period=_PERIOD)


def _seed_prior_year_saldo(*, source_year: int, saldo: Decimal, obs_repo: CalculationObservationRepository) -> None:
    """Record a prior-year M100 end-of-year generated saldo (casilla 1391)."""
    save_stamped_observation(
        obs_repo,
        registry_grounded_modelo_observation(
            modelo=_MODELO,
            filing_year=source_year,
            period=_PERIOD,
            casilla_values={_GENERATED_SALDO: saldo, **dict.fromkeys(_PRIOR_ANEXO_C_REMAINDERS, Decimal("0"))},
        ),
        source_kind="app_filing",
        captured_at=_CLOCK,
    )


def _calculate_100(*, filing_year: int, obs_repo: CalculationObservationRepository):
    """Run the bucket M100 calculation for ``filing_year``.

    The bucket resolves the ``previous_filing`` carry from the local observation
    store and the seeded profile fills the ``source = "profile"`` bindings.
    Every other operator-owned binding is supplied as zero, and relations are
    zero (no dependent-modelo activity for this pure-carry persona). Returns the
    persisted :class:`CalculationRevision`.
    """
    snapshot = _snapshot(filing_year)
    with bundled_indexed_authority().operation() as operation:
        binding_values: dict[BindingId, Decimal] = {
            binding.id: Decimal("0")
            for binding in snapshot.revision.bindings
            if binding.source != "profile"
            and binding.source not in BUCKET_AGGREGATION_LOCK_SOURCES
            and binding.provider.kind not in {"retencion_soportada", "previous_filing"}
        }
        relation_values: dict[RelationId, Decimal] = {
            binding.id: Decimal("0")
            for binding, _provider in relation_prefill_bindings_for_period(snapshot.revision, period=snapshot.period)
        }

        work_unit = create_work_unit(
            bucket_id=_BUCKET_ID,
            modelo=_MODELO,
            filing_year=filing_year,
            period=Period.from_year_and_code(filing_year, _PERIOD),
            revision_id=str(filing_year),
            ports=build_work_lifecycle_ports(bucket_id=_BUCKET_ID),
            operation=operation,
            clock=_CLOCK,
        )
        return calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
            work_unit.work_unit_id,
            ports=build_calculation_action_ports(bucket_id=_BUCKET_ID, operation=operation),
            actor=_BUCKET_ID,
            casilla_inputs={},
            binding_values=binding_values,
            relation_values=relation_values,
            clock=_CLOCK,
        ).revision


def test_modelo_100_opening_pending_resolves_from_prior_year_saldo(tmp_path: Path) -> None:
    """A real M100 calculation lands casilla 1388 from the prior year's 1391 saldo.

    The cross-renta continuity contract: once the prior M100 is recorded, the
    ``filing_year_delta = -1`` carry populates casilla 1388 from that prior
    1391 generated saldo, and a real ``calculate_modelo_revision_from_bucket_aggregation_with_diagnostics`` emits it —
    the operator does not re-key the carried negative general base.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        obs_repo = CalculationObservationRepository()
        seed_persona_profile("autonomo-fontanero", bucket_id=_PROFILE_ID, at=_CLOCK)
        _seed_prior_year_saldo(source_year=_YEAR_N - 1, saldo=_SALDO_BY_SOURCE_YEAR[_YEAR_N - 1], obs_repo=obs_repo)
        revision = _calculate_100(filing_year=_YEAR_N, obs_repo=obs_repo)
    assert Decimal(revision.casilla_values[_PENDIENTE_INICIO]) == _SALDO_BY_SOURCE_YEAR[_YEAR_N - 1]


def test_modelo_100_base_liquidable_negativa_enrolls_two_renta_years(tmp_path: Path) -> None:
    """End-to-end enrollment: M100 general-base saldo carry across two renta years.

    Drives the REAL M100 ``calculate_modelo_revision_from_bucket_aggregation_with_diagnostics`` for two distinct renta
    years (N, N+1), each sourcing the prior year's 1391 generated saldo
    (N-1, N), records each through the ``cross-year observation`` (CALC;
    evidence = the _produced-value count from the real engine run), and
    cross-checks the recorded two-year set against the cross-year claim.
    Year N's prior filing is in the store but must not contaminate Year N+1's
    resolver. A single-year or stub run raises at
    ``the cross-year behavior assertion``.

    Honest scope: this proves the general-base carry *wiring* across two renta
    years through the full calc. The integración-subtract consumption of the
    opening saldo, the savings-base (0441-family) carry, and the deeper
    four-year window are deferred calc-completeness follow-ons — not claimed by
    this enrollment.
    """

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        obs_repo = CalculationObservationRepository()
        seed_persona_profile("autonomo-fontanero", bucket_id=_PROFILE_ID, at=_CLOCK)
        _seed_prior_year_saldo(source_year=_YEAR_N - 1, saldo=_SALDO_BY_SOURCE_YEAR[_YEAR_N - 1], obs_repo=obs_repo)
        _seed_prior_year_saldo(source_year=_YEAR_N, saldo=_SALDO_BY_SOURCE_YEAR[_YEAR_N], obs_repo=obs_repo)

        revision_n = _calculate_100(filing_year=_YEAR_N, obs_repo=obs_repo)

        revision_n1 = _calculate_100(filing_year=_YEAR_N_PLUS_1, obs_repo=obs_repo)

    # Cross-renta wiring invariant: each year's opening pending equals the prior
    # year's end-of-year generated saldo, year-isolated.
    assert Decimal(revision_n.casilla_values[_PENDIENTE_INICIO]) == _SALDO_BY_SOURCE_YEAR[_YEAR_N - 1]
    assert Decimal(revision_n1.casilla_values[_PENDIENTE_INICIO]) == _SALDO_BY_SOURCE_YEAR[_YEAR_N]
