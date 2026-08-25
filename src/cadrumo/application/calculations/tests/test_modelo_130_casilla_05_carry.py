"""Modelo 130 casilla-05 cumulative pagos-fraccionados carry verification gates.

Stage 2 flips casilla 05
("Pagos fraccionados anteriores") to a bound carry computing the AEAT instrucciones
accumulation identity over the same-ejercicio trimestres anteriores::

    casilla 05(N) = SUM over prior quarters q before N of max(0, casilla 07_q)
                    minus SUM over the same q of casilla 16_q

These gates drive the carry through the real ``previous_filing`` resolver against
real encrypted-SQLite repositories and the real registry authority - no mocks,
stubs, skips, or xfail. They are non-tautological per
``aeat-quality-gates``: the value oracle is the verbatim AEAT
accumulation identity computed by an independent helper, a DIFFERENT code path
than the span binding under test. A binding that summed raw casilla 07 (skipping
the per-quarter max-0) or dropped the minus-16 term fails the identity gate
loudly.

Coverage:

* accumulation-identity oracle: a multi-quarter fixture whose prior
  1T/2T/3T filings carry chosen casilla 07 / 16 (including a NEGATIVE prior 07 and
  a NON-ZERO casilla 16); the 4T casilla 05 must equal the independently-computed
  identity;
* first-quarter-fires-nothing: a 1T (and a first-filer / mid-year-alta
  first quarter) yields casilla 05 = Decimal zero with no carried prior, because
  the expanding span is empty;
* not-captured minoración honesty: a prior filing carrying casilla 07
  but no casilla-16 entry lets the carry proceed (treating the absent minoración
  as zero) rather than dropping it silently.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
from ....adapters.persistence.profile.modelos_verification_reports import VerificationReportCatalogueRepository
from ....core import CasillaId, validated_casilla_id
from ....core.resources import resources
from cadrumo.domain.calculations.registry.bindings import RegistryModeloObservation, resolve_previous_filing_binding_values
from ....tests.registry_observations import registry_grounded_modelo_observation
from ....tests.secure_sql import isolated_runtime_profile
from .._cross_period_clean_state import evaluate_cross_period_clean_state
from .._observations_repository import CalculationObservationRepository

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_CARRY_BINDING_ID = "modelo-130-pagos-fraccionados-anteriores"
_BUCKET_ID = "13005000-0000-4000-8000-000000000130"
_FILING_YEAR = 2026


_M100_ACTIVIDAD_ECONOMICA_NET_INCOME_CASILLA: CasillaId = validated_casilla_id("0224")
_M100_RENDIMIENTO_SOURCE_1479_CASILLA: CasillaId = validated_casilla_id("1479")
_M100_RENDIMIENTO_SOURCE_1553_CASILLA: CasillaId = validated_casilla_id("1553")
_M100_RENDIMIENTO_SOURCE_1577_CASILLA: CasillaId = validated_casilla_id("1577")
_M130_PAGO_FRACCIONADO_CASILLA: CasillaId = validated_casilla_id("07")
_M130_HOME_DEDUCTION_CASILLA: CasillaId = validated_casilla_id("16")
_M130_SALDO_NEGATIVO_CASILLA: CasillaId = validated_casilla_id("saldo-negativo-fin-periodo")


@pytest.fixture
def obs_repo(tmp_path: Path) -> Iterator[CalculationObservationRepository]:
    """A real encrypted-SQLite observation repository over an isolated profile.

    The prior-year M100 minoración source is seeded once so the sibling
    ``irpf.previous_year_economic_activity_net_income`` previous_filing binding
    resolves; it is upstream substrate, not the casilla-05 carry under test.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        repo = CalculationObservationRepository(objects=profile.repository)
        repo.save(
            repo.prepare_observation_envelope(
                registry_grounded_modelo_observation(
                    modelo="100",
                    filing_year=_FILING_YEAR - 1,
                    period="0A",
                    casilla_values={
                        _M100_ACTIVIDAD_ECONOMICA_NET_INCOME_CASILLA: Decimal("0"),
                        _M100_RENDIMIENTO_SOURCE_1479_CASILLA: Decimal("0"),
                        _M100_RENDIMIENTO_SOURCE_1553_CASILLA: Decimal("0"),
                        _M100_RENDIMIENTO_SOURCE_1577_CASILLA: Decimal("0"),
                    },
                ),
                source_kind="app_filing",
            )
        )
        yield repo


def _prior_m130(period: str, *, casilla_07: Decimal, casilla_16: Decimal | None) -> RegistryModeloObservation:
    """Build a prior-quarter M130 observation carrying casilla 07 and (optionally) 16.

    The casilla-15 carry binding also reads ``saldo-negativo-fin-periodo`` from
    every prior quarter, so each fixture row carries a zeroed saldo (a positive
    prior result) to keep that sibling binding resolvable. ``casilla_16 = None``
    omits the casilla-16 entry entirely (the not-captured shape).
    """
    casilla_values = {
        _M130_PAGO_FRACCIONADO_CASILLA: casilla_07,
        _M130_SALDO_NEGATIVO_CASILLA: Decimal("0"),
    }
    if casilla_16 is not None:
        casilla_values[_M130_HOME_DEDUCTION_CASILLA] = casilla_16
    return registry_grounded_modelo_observation(
        modelo="130",
        filing_year=_FILING_YEAR,
        period=period,
        casilla_values=casilla_values,
    )


def _resolve_casilla_05(obs_repo: CalculationObservationRepository, *, target_period: str) -> Decimal | None:
    snapshot = resources().modelos.authority.snapshot("130", filing_year=_FILING_YEAR, period=target_period)
    observations = tuple(
        payload.observation for source_modelo in ("130", "100") for payload in obs_repo.iter_modelo(source_modelo)
    )
    resolved = resolve_previous_filing_binding_values(
        snapshot.revision,
        observations,
        filing_year=_FILING_YEAR,
        period=target_period,
    )
    return resolved.get(_CARRY_BINDING_ID)


def _accumulation_identity(quarters: dict[str, tuple[Decimal, Decimal]]) -> Decimal:
    """Independent AEAT identity: SUM max(0, 07_q) - SUM 16_q (a different code path).

    ``quarters`` maps each prior period to its ``(casilla_07, casilla_16)`` pair.
    This helper deliberately re-expresses the verbatim instrucciones rule by hand
    so it cannot share the span-binding implementation it validates.
    """
    zero = Decimal("0")
    positive_part = sum((max(zero, c07) for c07, _c16 in quarters.values()), zero)
    minoracion = sum((c16 for _c07, c16 in quarters.values()), zero)
    return positive_part - minoracion


def test_4t_casilla_05_equals_accumulation_identity_with_negative_07_and_nonzero_16(
    obs_repo: CalculationObservationRepository,
) -> None:
    """4T casilla 05 = SUM max(0, prior 07_q) - SUM prior 16_q, oracle-grounded.

    Prior quarters (independently fixed inputs, NOT engine-derived for this gate -
    the values are the fixture, and the identity is computed by a separate helper):

      1T: 07 = +400, 16 = 50
      2T: 07 = -150 (a loss quarter), 16 = 0
      3T: 07 = +600, 16 = 90

    Identity: SUM max(0, 07) = 400 + 0 + 600 = 1000 ; SUM 16 = 50 + 0 + 90 = 140
              casilla 05(4T) = 1000 - 140 = 860.

    A binding that summed raw 07 (including the -150) would give
    (400 - 150 + 600) - 140 = 710; a binding that dropped the minus-16 term would
    give 1000. Both regressions fail this gate.
    """
    quarters: dict[str, tuple[Decimal, Decimal]] = {
        "1T": (Decimal("400"), Decimal("50")),
        "2T": (Decimal("-150"), Decimal("0")),
        "3T": (Decimal("600"), Decimal("90")),
    }
    for period, (casilla_07, casilla_16) in quarters.items():
        obs_repo.save(
            obs_repo.prepare_observation_envelope(
                _prior_m130(period, casilla_07=casilla_07, casilla_16=casilla_16),
                source_kind="app_filing",
            )
        )

    resolved = _resolve_casilla_05(obs_repo, target_period="4T")

    expected = _accumulation_identity(quarters)
    assert expected == Decimal("860")  # the identity is the fixture-grounded oracle
    assert resolved == expected


def test_3t_casilla_05_sums_only_quarters_before_target(
    obs_repo: CalculationObservationRepository,
) -> None:
    """3T casilla 05 sums only {1T, 2T} - the expanding span excludes the target.

    Seeds 1T/2T/3T but the 3T target span is {1T, 2T}; the 3T prior filing's own
    07/16 must NOT contribute. Identity over {1T, 2T}: max(0, 400) + max(0, 200)
    minus (50 + 30) = 600 - 80 = 520.
    """
    quarters: dict[str, tuple[Decimal, Decimal]] = {
        "1T": (Decimal("400"), Decimal("50")),
        "2T": (Decimal("200"), Decimal("30")),
        "3T": (Decimal("999"), Decimal("999")),  # the target's own row must be excluded
    }
    for period, (casilla_07, casilla_16) in quarters.items():
        obs_repo.save(
            obs_repo.prepare_observation_envelope(
                _prior_m130(period, casilla_07=casilla_07, casilla_16=casilla_16),
                source_kind="app_filing",
            )
        )

    resolved = _resolve_casilla_05(obs_repo, target_period="3T")

    expected = _accumulation_identity({"1T": quarters["1T"], "2T": quarters["2T"]})
    assert expected == Decimal("520")
    assert resolved == expected


def test_first_quarter_carry_resolves_nothing(
    obs_repo: CalculationObservationRepository,
) -> None:
    """1T (and a first-filer / mid-year-alta first quarter) carries no casilla 05.

    The expanding span is empty at 1T, so the carry binding produces no anchor and
    resolves to nothing (the engine then materialises casilla 05 = absent-by-design
    zero). No prior observation is required, and seeding none must not error - the
    first-obligation filer fires no carry.
    """
    resolved = _resolve_casilla_05(obs_repo, target_period="1T")
    assert resolved is None


def test_not_captured_minoracion_proceeds_treating_absent_16_as_zero(
    obs_repo: CalculationObservationRepository,
) -> None:
    """A prior filing carrying casilla 07 but NO casilla-16 entry does not hard-fail.

    Per the ratified casilla-16 filed-zero-vs-not-captured distinction, an absent
    minoración is treated as zero so the carry proceeds; the application advisory
    (``prior_payment_minoracion_not_captured``) names the gap. Here the 2T target's
    only prior quarter (1T) carries 07 = 300 with NO casilla-16 entry; the carry
    resolves to max(0, 300) - 0 = 300 rather than raising.
    """
    obs_repo.save(
        obs_repo.prepare_observation_envelope(
            _prior_m130("1T", casilla_07=Decimal("300"), casilla_16=None),
            source_kind="app_filing",
        )
    )

    resolved = _resolve_casilla_05(obs_repo, target_period="2T")

    assert resolved == Decimal("300")


def test_first_filer_2t_alta_clean_state_suppresses_pre_activity_casilla_05_requirement(
    obs_repo: CalculationObservationRepository,
) -> None:
    """A mid-year alta (2T) first filer returns a clean cross-period verdict.

    The casilla-05 carry registers a 1T prior-quarter requirement for a 2T target,
    but a taxpayer whose activity began in 2T had no 1T obligation. The activity-start
    scoping (``partition_cross_period_requirements_by_activity_start`` /
    ``_period_strictly_before_activity_start``) bound to the operator-declared
    ``activity_start_date`` suppresses the pre-activity 1T requirement: it resolves
    to a provenance-marked no-prior-obligation zero rather than a missing-observation
    blocker, so the verdict is clean for a genuine first filer.
    """
    snapshot = resources().modelos.authority.snapshot("130", filing_year=_FILING_YEAR, period="2T")
    # Activity starts mid-2T; the 1T period (ending 2026-03-31) is strictly prior.
    verdict = evaluate_cross_period_clean_state(
        snapshot,
        bucket_id=_BUCKET_ID,
        observation_repository=obs_repo,
        filing_repository=ModeloRecordCatalogueRepository(),
        calculation_repository=CalculationRevisionCatalogueRepository(),
        verification_repository=VerificationReportCatalogueRepository(),
        activity_start_date=date(2026, 4, 15),
    )

    assert verdict.clean, f"a 2T-alta first filer must be clean; blockers={verdict.blockers}"
    suppressed = verdict.suppressed_pre_activity_dependencies
    suppressed_origins = {origin_id for dependency in suppressed for origin_id in dependency.requirement.origin_ids}
    assert _CARRY_BINDING_ID in suppressed_origins, (
        "the pre-activity 1T casilla-05 carry requirement must be suppressed as no-prior-obligation"
    )
