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
validator semantics: M200 is modelled only from 2024, but the prior 00671 is
the operator's historical filing (an observation), so the ``-1`` source
resolves present-or-zero-carry — a first-year filer simply has no prior BIN
to carry (a correct zero, not a silent under-declaration).
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....core.resources import resources
from ....domain.calculations.registry import (
    CasillaObservation,
    RegistryCalculationResult,
    RegistryModeloObservation,
    calculate_registry_snapshot,
    materialize_relation_binding_values,
    resolve_bound_casilla_inputs,
)
from ....domain.deadlines import IVARegime, TaxpayerProfile
from ....domain.modelos._verification_report import ModeloVerificationFindingKind
from ....tests.secure_sql import isolated_runtime_profile
from ...modelo._actions import _evaluate_verification_predicates
from .._binding_prefill import resolve_bindings_from_local_store
from .._multi_year import EnrollmentRecorder, assert_enrollment_matches_manifest
from .._observations_repository import CalculationObservationRepository
from .._relation_prefill import resolve_relations_from_local_store

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

# Casilla-only predicates (cap_le_when_positive) ignore the profile, but
# _evaluate_verification_predicates requires a real TaxpayerProfile; supply a
# minimal one rather than the typed-None hole the casilla-only path tolerated.
_CASILLA_ONLY_PROFILE = TaxpayerProfile(tax_id="B12345678", iva_regime=IVARegime.GENERAL)

_MODELO_200 = "200"

#: Casillas on the cross-year BIN carry.
_M200_BIN_PENDIENTE_FUTUROS = "00671"  # end-of-year stock pending future application
_M200_BIN_PENDIENTE_INICIO = "00670"  # opening stock pending (bound from prior 00671)

#: Two distinct renta years the enrollment spans; each sources the prior year's 00671.
_YEAR_N = 2024
_YEAR_N_PLUS_1 = 2025

#: Distinct prior-year BIN stock per source year so a cross-year contamination surfaces.
_BIN_STOCK_BY_SOURCE_YEAR: dict[int, Decimal] = {
    2023: Decimal("30000.00"),
    2024: Decimal("18000.00"),
}

#: The same-year M202 pagos relation the M200 cuota chain reads; zero here (no
#: instalments) keeps the BIN-stock assertion focused. Supplied directly as a
#: relation value rather than seeded, since pagos are not under test.
_M200_PAGOS_RELATION = "modelo-200-2024-rel-202-pagos-fraccionados"

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
    obs_repo.save_observation(
        RegistryModeloObservation(
            modelo=_MODELO_200,
            filing_year=source_year,
            period="0A",
            observations=(CasillaObservation(casilla_id=_M200_BIN_PENDIENTE_FUTUROS, value=stock),),
        ),
        source_kind="app_filing",
        captured_at=_CLOCK,
    )


def _calculate_200(*, filing_year: int, relation_values: dict[str, Decimal]) -> tuple[RegistryCalculationResult, int]:
    """Run the REAL M200 annual calculation from resolved relations + the SL profile."""
    snapshot = resources().modelos.authority.snapshot(_MODELO_200, filing_year=filing_year, period="0A")
    relation_binding_values = materialize_relation_binding_values(snapshot.revision, relation_values, period="0A")
    # Resolve every previous_filing carry binding (BIN-stock 00670 AND the art.13
    # dotaciones-deterioro 01494/01495) from the local observation store; any the
    # store cannot satisfy default to zero (present-or-zero-carry) so the strict
    # resolver below sees a complete fact set regardless of which carries this
    # scenario seeds.
    prefilled = resolve_bindings_from_local_store(snapshot).binding_values
    carry_defaults = {
        c.binding: Decimal("0") for c in snapshot.revision.casillas if c.input_kind.value == "bound" and c.binding
    }
    binding_values = {**carry_defaults, **prefilled, **relation_binding_values, **_PROFILE_DECIMAL_BINDINGS}
    inputs = resolve_bound_casilla_inputs(snapshot.revision, binding_values)
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
    *, filing_year: int, obs_repo: CalculationObservationRepository,
) -> dict[str, Decimal]:
    snapshot = resources().modelos.authority.snapshot(_MODELO_200, filing_year=filing_year, period="0A")
    resolved = {
        item.relation: item.value
        for item in resolve_relations_from_local_store(snapshot, repository=obs_repo).values
        if item.value is not None
    }
    # No instalments this scenario: supply the same-year M202 pagos relation as zero
    # (it is not the cross-year hook under test).
    resolved.setdefault(_M200_PAGOS_RELATION, Decimal("0"))
    return resolved


def test_modelo_200_opening_bin_stock_resolves_from_prior_year(tmp_path: Path) -> None:
    """Casilla 00670 (opening BIN stock) auto-resolves to the prior year's 00671.

    The cross-year continuity contract: once the prior M200 is recorded, the
    ``filing_year_delta = -1`` carry populates casilla 00670 from that prior
    00671 — the operator does not re-key the carried BIN stock.
    """
    with isolated_runtime_profile(tmp_path=tmp_path):
        obs_repo = CalculationObservationRepository()
        _seed_m200_bin_stock(source_year=2023, stock=_BIN_STOCK_BY_SOURCE_YEAR[2023], obs_repo=obs_repo)
        resolved = _resolve_and_supply_relations(filing_year=_YEAR_N, obs_repo=obs_repo)
        result, _ = _calculate_200(filing_year=_YEAR_N, relation_values=resolved)
    assert Decimal(result.values["00670"]) == _BIN_STOCK_BY_SOURCE_YEAR[2023]


def test_modelo_200_bin_stock_enrolls_two_renta_years(tmp_path: Path) -> None:
    """End-to-end enrollment: M200 BIN stock carry across two renta years.

    Drives the real M200 engine for two distinct renta years (2024, 2025),
    each sourcing the prior year's 00671 BIN stock (2023, 2024), records each
    through the :class:`EnrollmentRecorder` (CALC), and cross-checks the
    recorded two-year set against the authorization manifest. Year N's prior
    filing is in the store but must not contaminate Year N+1's resolver. A
    single-year or stub run raises at :func:`assert_enrollment_matches_manifest`.
    """
    recorder = EnrollmentRecorder(_MODELO_200)

    with isolated_runtime_profile(tmp_path=tmp_path):
        obs_repo = CalculationObservationRepository()
        _seed_m200_bin_stock(source_year=2023, stock=_BIN_STOCK_BY_SOURCE_YEAR[2023], obs_repo=obs_repo)
        _seed_m200_bin_stock(source_year=2024, stock=_BIN_STOCK_BY_SOURCE_YEAR[2024], obs_repo=obs_repo)

        resolved_n = _resolve_and_supply_relations(filing_year=_YEAR_N, obs_repo=obs_repo)
        result_n, produced_n = _calculate_200(filing_year=_YEAR_N, relation_values=resolved_n)
        recorder.record_calculation_year(filing_year=_YEAR_N, produced_value_count=produced_n)

        resolved_n1 = _resolve_and_supply_relations(filing_year=_YEAR_N_PLUS_1, obs_repo=obs_repo)
        result_n1, produced_n1 = _calculate_200(filing_year=_YEAR_N_PLUS_1, relation_values=resolved_n1)
        recorder.record_calculation_year(filing_year=_YEAR_N_PLUS_1, produced_value_count=produced_n1)

    # Wiring invariant: each year's opening BIN stock equals the prior year's
    # end-of-year stock, year-isolated.
    assert Decimal(result_n.values["00670"]) == _BIN_STOCK_BY_SOURCE_YEAR[2023]
    assert Decimal(result_n1.values["00670"]) == _BIN_STOCK_BY_SOURCE_YEAR[2024]

    evidence = recorder.evidence()
    assert evidence.distinct_renta_years == (_YEAR_N, _YEAR_N_PLUS_1)
    assert_enrollment_matches_manifest(evidence)


# ---------------------------------------------------------------------------
# Elective-cap gate (LIS art. 26.1): the operator-elective applied BIN
# compensation (DP200014:00547) must not exceed the computed ceiling
# (DP200014:bin-aplicada-maxima = min(stock, max(EUR 1M, 70%·base previa))).
# The cap_le_when_positive BLOCKING predicate refuses OVER-application but
# permits electing LESS — compensation is a right bounded by a ceiling, not a
# mandate. These tests exercise the predicate semantics directly (the ceiling
# value itself is produced by the real cap formula in the calc E2E above).
# ---------------------------------------------------------------------------

_BIN_CAP_PREDICATE_ID = "modelo-200-compensacion-bin-no-excede-limite-art-26"


def _bin_cap_predicate():
    """Return the art.26.1 cap BLOCKING predicate from the live M200 snapshot."""
    revision = resources().modelos.authority.validate_modelo(_MODELO_200).revisions["2024-y-siguientes"]
    predicate = next(p for p in revision.verification_predicates if p.predicate_id == _BIN_CAP_PREDICATE_ID)
    assert predicate.finding_kind == "BLOCKING_RULE"
    assert "cap_le_when_positive" in predicate.expression
    return predicate


def test_modelo_200_bin_over_application_above_cap_is_blocked() -> None:
    """Applying more BIN than the art.26.1 ceiling fires a BLOCKING finding.

    Ceiling = 1.000.000 (the EUR 1M floor dominates a small 70%·base); electing
    00547 = 1.200.000 over-compensates and must be refused. Non-tautological:
    the predicate is the registry's own cap_le_when_positive, evaluated against
    a hand-built over-claim, not a re-run of the cap formula.
    """
    predicate = _bin_cap_predicate()
    casilla_values = {
        "DP200014:bin-aplicada-maxima": Decimal("1000000.00"),
        "DP200014:00547": Decimal("1200000.00"),  # over the ceiling
    }
    findings = _evaluate_verification_predicates((predicate,), casilla_values, _CASILLA_ONLY_PROFILE)
    assert len(findings) == 1
    assert findings[0].kind is ModeloVerificationFindingKind.BLOCKING_RULE
    assert _BIN_CAP_PREDICATE_ID in findings[0].message


def test_modelo_200_electing_less_than_cap_is_permitted() -> None:
    """Electing LESS BIN than the ceiling raises no finding (compensation is a right).

    The taxpayer may preserve BIN stock for future years; applying below the
    cap is legitimate and the gate must not refuse it. This is the
    no-silent-under-declaration "Good" path: blocking only the over-claim
    direction, permitting the under-direction.
    """
    predicate = _bin_cap_predicate()
    casilla_values = {
        "DP200014:bin-aplicada-maxima": Decimal("1000000.00"),
        "DP200014:00547": Decimal("400000.00"),  # elected below the ceiling
    }
    findings = _evaluate_verification_predicates((predicate,), casilla_values, _CASILLA_ONLY_PROFILE)
    assert findings == []


def test_modelo_200_applying_exactly_the_cap_is_permitted() -> None:
    """Applying exactly the ceiling is permitted (<= holds at equality)."""
    predicate = _bin_cap_predicate()
    casilla_values = {
        "DP200014:bin-aplicada-maxima": Decimal("1000000.00"),
        "DP200014:00547": Decimal("1000000.00"),
    }
    findings = _evaluate_verification_predicates((predicate,), casilla_values, _CASILLA_ONLY_PROFILE)
    assert findings == []
