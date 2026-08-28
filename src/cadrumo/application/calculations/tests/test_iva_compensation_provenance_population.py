"""Population control for the discriminated IVA-compensation provenance pair.

The refusal side is already proven: the cross-field validator rejects an
operator-seeded row carrying an expediente and an AEAT-capture row carrying
none. What that proves is that the discriminator BITES. It says nothing about
whether it bites the legitimate population too, and a discriminator that
refuses everything passes a refusal test perfectly.

This module measures the legitimate population instead. Every row each of the
three consuming paths can carry is constructed through the real production
producer, persisted through the real encrypted repository, and read back:

* the wallet-balance projection
  (:func:`~application.calculations.query_iva_wallet_balance`),
* the binding-prefill resolver
  (:func:`~application.calculations.extract_modelo_303_local_iva_compensation_recurrence`),
* the Modelo 303 carry-ingress path
  (:func:`~application.calculations.persist_observation_envelope_and_iva_history`
  reached through the two filing boundaries, plus the annual-partition state
  reconstruction).

Two assertions, and the second is why the first is worth anything:

* every row's ``provenance`` is one of the five declared members -- asserted on
  the PROVENANCE FIELD, never on ``status``;
* ``status`` is ``None`` on every non-AEAT path. Before the split, provenance
  was readable off ``status``, so a control that read it there would pass
  against the wrong field while the ruled design was absent. Only the ruled
  design can satisfy this second clause.

The row COUNT each path contributed is reported and gated: a path that
contributes zero rows fails, because a control exercising nothing reads
identically to one that passes. The gate is the property "this path carried at
least one row" plus "every declared member was carried by some path"; the
observed tallies are reported, never pinned.

If any path ever carries a row whose provenance is not one of the five, the
enum is INCOMPLETE: the row must not be forced into an approximate member, and
the discriminated-pair decision must be reopened. The failure messages say so.
"""

from __future__ import annotations

import hashlib
from collections import Counter
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import AnyHttpUrl

from ....adapters.outbound.aeat.sede import (
    FiledDeclaracionArtefact,
    FiledDeclaracionObservation,
    ObservedCasillaValue,
)
from ....core import (
    CasillaId,
    CasillaValueKind,
    IvaCompensationStateProvenance,
    Modelo,
    ObservedHeaderFact,
    Period,
    ResultDisposition,
    validated_casilla_id,
)
from ....core.config import Settings
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.iva_compensation import IvaCompensationPeriodState
from ....domain.modelos import ModeloCode, WorkUnit, derive_work_unit_id
from ....domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from ....tests.filing_evidence import general_m303_filing_evidence
from ....tests.registry_observations import registry_grounded_observations
from ....tests.secure_sql import isolated_runtime_profile
from ...live.filed_observation_persistence import persist_filed_calculation_observation
from ...modelo._filed_revision_observation import persist_filed_revision_observation
from .._binding_prefill import (
    _observation_from_iva_compensation_history,
    extract_modelo_303_local_iva_compensation_recurrence,
)
from .._iva_compensation_annual_partition import (
    _period_state_from_303_envelope,
    resolve_iva_compensation_annual_partition_binding_values,
)
from ..iva_compensation_history import (
    IvaCompensationHistoryRepository,
    correct_iva_compensation_period,
    seed_iva_compensation_period,
)
from ..iva_wallet_balance import query_iva_wallet_balance
from ..observations_repository import CalculationObservationRepository

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

#: The closed taxonomy under measurement, read from the enum rather than
#: restated, so a sixth member widens this set instead of slipping past it.
_DECLARED_PROVENANCES = frozenset(IvaCompensationStateProvenance)

_NIF = "12345678Z"
_AEAT_EXPEDIENTE = "202630300000001Z"
_AEAT_REGISTER_STATUS = "ALTA"
_AS_OF_YEAR = 2026

_SEED_PERIOD = Period.from_year_and_code(2023, "4T")
_CORRECTION_PERIOD = Period.from_year_and_code(2024, "4T")
_APP_FILING_PERIOD = Period.from_year_and_code(2025, "4T")
_AEAT_CAPTURE_PERIOD = Period.from_year_and_code(2026, "1T")

_SEED_AMOUNT = Decimal("120.00")
_SUPERSEDED_SEED_AMOUNT = Decimal("55.00")
_CORRECTION_AMOUNT = Decimal("90.00")
_APP_FILING_RESULTADO = Decimal("-30.00")
_AEAT_CAPTURE_RESULTADO = Decimal("-40.00")

_SEEDED_AT = datetime(2024, 1, 15, 9, 0, tzinfo=UTC)
_CORRECTED_AT = datetime(2025, 1, 15, 9, 0, tzinfo=UTC)
_APP_FILED_AT = datetime(2026, 1, 20, 9, 0, tzinfo=UTC)
_AEAT_PRESENTED_AT = datetime(2026, 4, 18, 9, 0, tzinfo=UTC)

_BUCKET_ID = "0cc751da-f750-4184-84b2-171737aac448"  # was 'bucket-iva-provenance-population'

#: Each entry is ``(target_filing_year, target_period, source_period)``. The
#: Modelo 303 compensation binding declares
#: ``source_period_offset_from_target = -1``, so each target's prior period is
#: the period holding one distinct persisted provenance. Every persisted
#: provenance is therefore reached through the resolver, not just the
#: convenient one.
_PREFILL_TARGETS = (
    (2024, "1T", _SEED_PERIOD),
    (2025, "1T", _CORRECTION_PERIOD),
    (2026, "1T", _APP_FILING_PERIOD),
    (2026, "2T", _AEAT_CAPTURE_PERIOD),
)


_PRIOR_PENDING_CASILLA: CasillaId = validated_casilla_id("iva.compensacion-pendiente-periodos-anteriores")
_APLICADA_CASILLA: CasillaId = validated_casilla_id("iva.compensacion-aplicada-periodo")
_POSTERIOR_CASILLA: CasillaId = validated_casilla_id("iva.compensacion-pendiente-periodos-posteriores")
_RESULTADO_CASILLA: CasillaId = validated_casilla_id("iva.resultado")
_RESULTADO_FINAL_CASILLA: CasillaId = validated_casilla_id("71")


@dataclass(frozen=True)
class _PathCensus:
    """Every row one consuming path carried, plus proof the path actually ran."""

    path: str
    entry_point: str
    rows: tuple[IvaCompensationPeriodState, ...]
    live_evidence: tuple[str, ...]

    @property
    def counts_by_provenance(self) -> dict[IvaCompensationStateProvenance, int]:
        tally: Counter[IvaCompensationStateProvenance] = Counter(row.provenance for row in self.rows)
        return dict(tally)


@dataclass(frozen=True)
class _Population:
    """The three path censuses measured over one shared legitimate population."""

    wallet_balance: _PathCensus
    binding_prefill: _PathCensus
    carry_ingress: _PathCensus

    @property
    def censuses(self) -> tuple[_PathCensus, ...]:
        return (self.wallet_balance, self.binding_prefill, self.carry_ingress)


def _registry_revision_id(*, filing_year: int, period: str) -> str:
    return (
        bundled_authority()
        .snapshot(
            Modelo.M303.value,
            filing_year=filing_year,
            period=period,
        )
        .revision.id
    )


def _app_filed_work_unit() -> WorkUnit:
    """The Modelo 303 work unit the local filing boundary would carry.

    ``persist_filed_revision_observation`` reads only the work unit's
    ``(modelo, filing_year, period, revision_id)``, and the revision id is the
    LAW-determined one for that triple, so the cross-period carry gate
    re-confirms rather than refuses it.
    """
    revision_id = _registry_revision_id(
        filing_year=_APP_FILING_PERIOD.filing_year,
        period=_APP_FILING_PERIOD.registry_token,
    )
    work_unit_id = derive_work_unit_id(
        bucket_id=_BUCKET_ID,
        modelo=Modelo.M303.value,
        filing_year=_APP_FILING_PERIOD.filing_year,
        period=_APP_FILING_PERIOD,
        revision_id=revision_id,
    )
    return WorkUnit(
        work_unit_id=work_unit_id,
        bucket_id=_BUCKET_ID,
        modelo=ModeloCode(Modelo.M303.value),
        filing_year=_APP_FILING_PERIOD.filing_year,
        period=_APP_FILING_PERIOD,
        revision_id=revision_id,
        name="m303-2025-4t",
        created_at=_APP_FILED_AT,
        updated_at=_APP_FILED_AT,
    )


def _app_filed_revision(work_unit: WorkUnit) -> CalculationRevision:
    """A filed Modelo 303 revision carrying registry-grounded carry observations.

    The five carry-bearing values are declared here as INPUTS to the filing, and
    their provenance comes from the registry authority rather than being
    invented, so the ingress resolves the available/generated pair from real
    grounded rows.
    """
    observations = registry_grounded_observations(
        modelo=Modelo.M303.value,
        filing_year=work_unit.filing_year,
        period=work_unit.period.registry_token,
        casilla_values={
            _PRIOR_PENDING_CASILLA: Decimal("0.00"),
            _APLICADA_CASILLA: Decimal("0.00"),
            _POSTERIOR_CASILLA: Decimal("0.00"),
            _RESULTADO_CASILLA: _APP_FILING_RESULTADO,
            _RESULTADO_FINAL_CASILLA: _APP_FILING_RESULTADO,
        },
    )
    casilla_values = {item.casilla_id: item.value for item in observations if isinstance(item.value, Decimal)}
    filing_instance_evidence = general_m303_filing_evidence(
        work_unit.period,
        reference="test:iva-compensation-provenance-population",
    )
    revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit.work_unit_id,
        input_values_by_casilla_id={},
        binding_overrides={},
        casilla_values=casilla_values,
        filing_instance_evidence=filing_instance_evidence,
        source_provenance=(),
    )
    return CalculationRevision(
        calculation_revision_id=revision_id,
        work_unit_id=work_unit.work_unit_id,
        state=CalculationRevisionState.PRESENTADO,
        casilla_values=casilla_values,
        observations=observations,
        created_at=_APP_FILED_AT,
        updated_at=_APP_FILED_AT,
        verified_at=_APP_FILED_AT,
        verified_by="provenance-population-control",
        filed_at=_APP_FILED_AT,
        filed_by="provenance-population-control",
        filing_instance_evidence=filing_instance_evidence,
        source_provenance=(),
    )


def _aeat_captured_303_observation() -> FiledDeclaracionObservation:
    """One AEAT declarations-register observation as the pull would observe it.

    Synthetic register data pushed through the real persistence function, not a
    stand-in for it. The ``declaration_type`` header is the only evidence that
    can establish an official Modelo 303 disposition, so it is present and its
    ``C`` election agrees with the negative filed resultado.
    """
    body = f"303-{_AEAT_CAPTURE_PERIOD.filing_year}-{_AEAT_CAPTURE_PERIOD.registry_token}-submitted-file".encode()
    external = Settings.external_constants().aeat
    declarations_url = f"{external.domains.www6}{external.sede_paths.declarations_listing}"
    observed = tuple(
        ObservedCasillaValue(
            casilla_id=casilla_id,
            value=str(value),
            value_kind=CasillaValueKind.NUMERIC,
            source_artefact_kind="submitted_file",
            source_locator=f"submitted-file:{official_number}",
            confidence=1.0,
        )
        for casilla_id, official_number, value in (
            (_PRIOR_PENDING_CASILLA, "110", Decimal("0.00")),
            (_APLICADA_CASILLA, "78", Decimal("0.00")),
            (_POSTERIOR_CASILLA, "87", Decimal("0.00")),
            (_RESULTADO_CASILLA, "69", _AEAT_CAPTURE_RESULTADO),
            (_RESULTADO_FINAL_CASILLA, "71", _AEAT_CAPTURE_RESULTADO),
        )
    )
    return FiledDeclaracionObservation(
        modelo=Modelo.M303.value,
        ejercicio=_AEAT_CAPTURE_PERIOD.filing_year,
        period=_AEAT_CAPTURE_PERIOD,
        expediente_id=_AEAT_EXPEDIENTE,
        status=_AEAT_REGISTER_STATUS,
        presented_at=_AEAT_PRESENTED_AT,
        authenticated_identity=_NIF,
        artefacts=(
            FiledDeclaracionArtefact(
                kind="submitted_file",
                source_url=AnyHttpUrl(declarations_url),
                content_type="application/octet-stream",
                byte_count=len(body),
                sha256=hashlib.sha256(body).hexdigest(),
                captured_at=_AEAT_PRESENTED_AT,
            ),
        ),
        casillas=observed,
        headers=(
            ObservedHeaderFact(
                header_key="declaration_type",
                value=ResultDisposition.COMPENSACION.value,
                source_artefact_kind="submitted_file",
                source_locator="submitted-file:declaration-type",
            ),
        ),
        extraction_coverage={"submitted_file": 1.0},
    )


def _persist_every_legitimate_row() -> None:
    """Drive all four persisting producers, one row each, through production code."""
    seed_iva_compensation_period(
        taxpayer_nif=_NIF,
        period=_SEED_PERIOD,
        amount=_SEED_AMOUNT,
        seeded_at=_SEEDED_AT,
    )
    # A correction is only reachable over an existing seed; the corrected period
    # therefore starts seeded and ends carrying OPERATOR_CORRECTION, which is
    # exactly the distinction the retired status literal could not express.
    seed_iva_compensation_period(
        taxpayer_nif=_NIF,
        period=_CORRECTION_PERIOD,
        amount=_SUPERSEDED_SEED_AMOUNT,
        seeded_at=_SEEDED_AT,
    )
    correct_iva_compensation_period(
        taxpayer_nif=_NIF,
        period=_CORRECTION_PERIOD,
        amount=_CORRECTION_AMOUNT,
        corrected_at=_CORRECTED_AT,
    )
    work_unit = _app_filed_work_unit()
    persist_filed_revision_observation(
        revision=_app_filed_revision(work_unit),
        work_unit=work_unit,
        repository=CalculationObservationRepository(),
        captured_at=_APP_FILED_AT,
        result_disposition=ResultDisposition.COMPENSACION,
        taxpayer_nif=_NIF,
    )
    persist_filed_calculation_observation(_aeat_captured_303_observation())


def _wallet_balance_census() -> _PathCensus:
    """Measure the rows the offline wallet-balance projection loads and folds."""
    rows = IvaCompensationHistoryRepository().list_periods()
    report = query_iva_wallet_balance(as_of_year=_AS_OF_YEAR)
    return _PathCensus(
        path="wallet-balance projection",
        entry_point="src/cadrumo/application/calculations/iva_wallet_balance.py:30",
        rows=rows,
        live_evidence=(
            f"query_iva_wallet_balance(as_of_year={_AS_OF_YEAR}) -> "
            f"lot_count={report.lot_count} total_balance={report.total_balance}",
        ),
    )


def _binding_prefill_census() -> _PathCensus:
    """Measure the rows the previous-filing prefill resolver projects and resolves.

    Each target is resolved end to end through
    ``extract_modelo_303_local_iva_compensation_recurrence`` -- the explicit
    wallet-feeding prefill path over the compensation history -- and each source
    row is additionally pushed through the per-row registry projection the
    gather step applies, which is where a provenance-sensitive regression would
    surface as a refusal rather than a wrong number.
    """
    history = IvaCompensationHistoryRepository()
    observations = CalculationObservationRepository()
    rows: list[IvaCompensationPeriodState] = []
    evidence: list[str] = []
    for target_year, target_period, source_period in _PREFILL_TARGETS:
        state = history.load_period(source_period)
        if state is None:
            evidence.append(
                f"{target_year}/{target_period} <- {source_period.filing_year}/"
                f"{source_period.registry_token}: NO SOURCE ROW",
            )
            continue
        projected = _observation_from_iva_compensation_history(state)
        snapshot = bundled_authority().snapshot(
            Modelo.M303.value,
            filing_year=target_year,
            period=target_period,
        )
        recurrence, _report = extract_modelo_303_local_iva_compensation_recurrence(
            snapshot,
            repository=observations,
            iva_history_repository=history,
        )
        rows.append(state)
        evidence.append(
            f"{target_year}/{target_period} <- {source_period.filing_year}/"
            f"{source_period.registry_token} provenance={state.provenance.value} "
            f"projected_casillas={len(projected.observations)} "
            f"recurrence={None if recurrence is None else recurrence.amount}",
        )
    return _PathCensus(
        path="binding-prefill resolver",
        entry_point="src/cadrumo/application/calculations/_binding_prefill.py:873",
        rows=tuple(rows),
        live_evidence=tuple(evidence),
    )


def _carry_ingress_census() -> _PathCensus:
    """Measure the rows the Modelo 303 carry-ingress path builds.

    Two shapes reach the ingress: the persisted state the two filing boundaries
    write through
    :func:`~application.calculations.persist_observation_envelope_and_iva_history`,
    and the never-persisted state the Modelo 390 annual partition reconstructs
    from the same filed envelope.
    """
    history = IvaCompensationHistoryRepository()
    observations = CalculationObservationRepository()
    rows: list[IvaCompensationPeriodState] = []
    evidence: list[str] = []
    for period in (_APP_FILING_PERIOD, _AEAT_CAPTURE_PERIOD):
        persisted = history.load_period(period)
        if persisted is None:
            evidence.append(f"{period.filing_year}/{period.registry_token}: NO INGRESS ROW PERSISTED")
            continue
        rows.append(persisted)
        payload = observations.load_observation(Modelo.M303.value, period)
        if payload is None:
            evidence.append(f"{period.filing_year}/{period.registry_token}: NO INGRESS ENVELOPE STORED")
            continue
        reconstructed = _period_state_from_303_envelope(payload)
        rows.append(reconstructed)
        partition = resolve_iva_compensation_annual_partition_binding_values(
            bundled_authority().snapshot(Modelo.M390.value, filing_year=period.filing_year, period="0A").revision,
            (payload,),
            filing_year=period.filing_year,
        )
        evidence.append(
            f"{period.filing_year}/{period.registry_token} persisted={persisted.provenance.value} "
            f"reconstructed={reconstructed.provenance.value} "
            f"m390_partition_bindings={len(partition)}",
        )
    return _PathCensus(
        path="M303 carry-ingress path",
        entry_point="src/cadrumo/application/calculations/iva_compensation_history.py:392",
        rows=tuple(rows),
        live_evidence=tuple(evidence),
    )


@pytest.fixture(scope="module")
def population(tmp_path_factory: pytest.TempPathFactory) -> Iterator[_Population]:
    """Build the legitimate population once and measure all three paths over it."""
    with isolated_runtime_profile(tmp_path=tmp_path_factory.mktemp("iva-provenance-population")):
        _persist_every_legitimate_row()
        yield _Population(
            wallet_balance=_wallet_balance_census(),
            binding_prefill=_binding_prefill_census(),
            carry_ingress=_carry_ingress_census(),
        )


def _provenance_token(provenance: object) -> str:
    """Render a provenance for the census without assuming it is a declared member.

    The disconfirming case this control exists to surface is a row whose
    provenance is NOT one of the five. Reading ``.value`` unconditionally would
    raise on exactly that row and bury the instructive refusal under an
    attribute error, so the reporter renders whatever arrived and lets the
    assertion below name the finding.
    """
    return str(getattr(provenance, "value", provenance))


def _report(census: _PathCensus) -> None:
    print(f"\n[{census.path}] entry point {census.entry_point}")
    print(f"[{census.path}] rows exercised: {len(census.rows)}")
    for provenance, count in sorted((_provenance_token(item), n) for item, n in census.counts_by_provenance.items()):
        print(f"[{census.path}]   {provenance}: {count}")
    for line in census.live_evidence:
        print(f"[{census.path}]   evidence: {line}")


def _assert_population(census: _PathCensus) -> None:
    """Assert the whole legitimate population of one path, on the provenance field."""
    _report(census)
    assert census.rows, (
        f"the {census.path} ({census.entry_point}) carried ZERO rows. A control exercising zero "
        "rows reads identically to one that passes, so this is a failure, not a pass"
    )
    for line in census.live_evidence:
        assert "NO SOURCE ROW" not in line and "NO INGRESS" not in line, (
            f"the {census.path} lost a row it was built to carry: {line}"
        )
    for row in census.rows:
        assert row.provenance in _DECLARED_PROVENANCES, (
            f"the {census.path} carries a row for {row.filing_year}/{row.period.registry_token} whose "
            f"provenance {row.provenance!r} is not one of the five declared members "
            f"{sorted(item.value for item in _DECLARED_PROVENANCES)}. The enum is INCOMPLETE: reopen the "
            "discriminated-pair decision and declare the missing member rather than forcing this row "
            "into an approximate one"
        )
        if row.provenance is IvaCompensationStateProvenance.AEAT_CAPTURE:
            assert row.expediente_id is not None, (
                f"the {census.path} carries an aeat_capture row for {row.filing_year}/"
                f"{row.period.registry_token} with no AEAT-issued expediente_id"
            )
            assert row.status is not None, (
                f"the {census.path} carries an aeat_capture row for {row.filing_year}/"
                f"{row.period.registry_token} with no AEAT-printed register status"
            )
            continue
        # The anti-vacuity clause. Only the ruled design satisfies it: while
        # status still carried provenance, a control could read provenance off
        # status and pass against the wrong field.
        assert row.status is None, (
            f"the {census.path} carries a {row.provenance.value} row for {row.filing_year}/"
            f"{row.period.registry_token} with status {row.status!r}. status reports the AEAT-printed "
            "register status and nothing else; a value here means provenance is once again readable "
            "off two fields that can disagree"
        )
        assert row.expediente_id is None, (
            f"the {census.path} carries a {row.provenance.value} row for {row.filing_year}/"
            f"{row.period.registry_token} with expediente_id {row.expediente_id!r}. Only an AEAT "
            "capture receives an expediente from AEAT; anything else is a synthetic marker "
            "impersonating an AEAT-issued identifier"
        )


def test_the_provenance_taxonomy_is_the_closed_five_this_control_measures() -> None:
    """The measured taxonomy is the declared one; a sixth member re-opens this control."""
    assert {item.value for item in IvaCompensationStateProvenance} == {
        "aeat_capture",
        "app_filing",
        "casilla_reconstruction",
        "operator_seed",
        "operator_correction",
    }, (
        "the declared provenance taxonomy changed. Every path below must be re-measured against the "
        "new member before the discriminated pair can be trusted again"
    )


def test_the_wallet_balance_projection_carries_its_whole_legitimate_population(population: _Population) -> None:
    """Every stored row the offline balance query folds still constructs and still loads."""
    _assert_population(population.wallet_balance)


def test_the_binding_prefill_resolver_carries_its_whole_legitimate_population(population: _Population) -> None:
    """Every stored row the previous-filing prefill resolves still constructs and still loads."""
    _assert_population(population.binding_prefill)


def test_the_m303_carry_ingress_path_carries_its_whole_legitimate_population(population: _Population) -> None:
    """Every row the carry ingress writes or reconstructs still constructs and still loads."""
    _assert_population(population.carry_ingress)


def test_every_declared_provenance_member_is_carried_by_a_live_path(population: _Population) -> None:
    """No declared member is unexercised, and no path contributes nothing.

    The gate is the PROPERTY that each path carried at least one row and that
    the union covers the declared taxonomy. The tallies are reported for review,
    never pinned: a pinned count encodes a moment and then detects nothing.
    """
    aggregate: Counter[IvaCompensationStateProvenance] = Counter()
    for census in population.censuses:
        assert census.rows, (
            f"the {census.path} ({census.entry_point}) contributed zero rows to the census, so its "
            "silence proves nothing about the discriminated pair"
        )
        aggregate.update(census.counts_by_provenance)
    print("\n[aggregate] rows exercised per path:")
    for census in population.censuses:
        print(f"[aggregate]   {census.path}: {len(census.rows)}")
    print("[aggregate] rows exercised per provenance:")
    for provenance, count in sorted((_provenance_token(item), n) for item, n in aggregate.items()):
        print(f"[aggregate]   {provenance}: {count}")

    unexercised = sorted(item.value for item in _DECLARED_PROVENANCES if item not in aggregate)
    assert not unexercised, (
        f"declared provenance members {unexercised} were carried by no path. Either the producer for "
        "that member is unreachable from these three paths, or the member is declared for a supplying "
        "path that does not exist"
    )
