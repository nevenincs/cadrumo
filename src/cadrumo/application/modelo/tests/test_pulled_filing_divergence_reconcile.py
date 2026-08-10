"""The pulled-filing reconcile must stay silent on an empty bucket and speak on a real gap.

The subject is the advisory that compares a taxpayer's own local calculation
against the filing AEAT already holds for the same modelo and period. It is a
narrowed comparison by design: a freshly onboarded profile computes nothing, so
an unnarrowed reconcile would raise a mismatch on essentially every reconciled
casilla, and the operator would learn only that the bucket is empty. Four states
are pinned here — no pulled filing at all, a pulled filing against an empty
bucket, a pulled filing the local figures agree with, and a pulled filing one
casilla genuinely disagrees with.

The silence cases carry their own controls. Asserting "no findings" against a
bucket that also happens to hold no comparable figures proves nothing, so the
empty-bucket case additionally shows that the SAME two sides produce a
divergence once the scope is removed: the quiet comes from the narrowing, not
from the two sides agreeing.

The divergence case's load-bearing assertion is the grounding. A reconcile
finding makes no independent legal claim — it says the value the registry
grounds at these references does not match what was filed — so it must carry the
diverging casilla's OWN ``legal_refs`` and ``source_refs``, read from that
casilla's registry definition. The assertion is exact tuple equality against the
registry casilla rather than a non-emptiness check, because a non-emptiness check
passes just as happily on references minted for the finding and therefore tests
nothing. A foil casilla whose references differ is asserted alongside it so the
equality is discriminating rather than accidentally true of every casilla.

Real behaviour throughout: a real isolated encrypted profile bucket, the real
SQLite-backed secure-object repository, the real serializer, the real registry
authority, and the production observation write path
(:meth:`CalculationObservationRepository.save_observation`) that the filed-capture
route reaches through. No mock, fake, stub, monkeypatch, skip or xfail.

Neither expected outcome is derived from a registry formula. The subject casilla
is a bound casilla whose value this module supplies on both sides; the gap is an
input to the run, chosen here, not a number read back out of the engine.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....core import BindingSourceKind, Period
from ....core.resources import resources
from ....domain.calculations.registry import (
    BindingId,
    CasillaDefinition,
    CasillaId,
    DataBindingDefinition,
    InputKind,
    ModeloRevision,
    RegistryModeloObservation,
)
from ....domain.modelos import (
    CalculationRevision,
    CalculationRevisionState,
    ModeloCode,
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
    WorkUnit,
    derive_calculation_revision_id,
    derive_work_unit_id,
)
from ....tests.registry_observations import registry_grounded_observations
from ....tests.secure_sql import isolated_runtime_profile
from ...calculations import CalculationObservationRepository, ObservationSourceKind
from .. import CasillaDivergenceKind, detect_casilla_divergences
from .._pulled_filing_reconcile import pulled_filing_divergence_findings

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "20260810-0000-4000-8000-000000000001"
_MODELO = "130"
_FILING_YEAR = 2024
_PERIOD_CODE = "1T"

# Distinct and fixed rather than "now". The revision model documents updated_at
# as EQUAL to created_at on a fresh draft, so equal is precisely the state a
# save-drops-field / load-re-defaults regression collapses to; a differing pair
# is the value that regression could not produce. Frozen instants also keep the
# fixture deterministic.
_CREATED_AT = datetime(2026, 2, 11, 8, 20, 45, tzinfo=UTC)
_UPDATED_AT = datetime(2026, 4, 27, 16, 5, 9, tzinfo=UTC)
_WORK_UNIT_CREATED_AT = datetime(2026, 1, 30, 7, 10, 15, tzinfo=UTC)
_WORK_UNIT_UPDATED_AT = datetime(2026, 5, 2, 19, 55, 40, tzinfo=UTC)
# The capture instant is the moment AEAT's register row was observed, which is
# neither of the local calculation's instants and is never "now": a captured_at
# defaulted at write time would be indistinguishable from a dropped field.
_CAPTURED_AT = datetime(2026, 3, 18, 11, 42, 3, tzinfo=UTC)

_SYNTHETIC_TAX_ID = "12345678Z"
_SYNTHETIC_EXPEDIENTE_ID = f"{_MODELO}{_FILING_YEAR}{_PERIOD_CODE}ABCD1234EFGH567"

# Both sides of the comparison are inputs to the run declared here. Integral
# magnitudes keep the rendered advisory text unambiguous.
_LOCAL_AMOUNT = Decimal("6000")
_FILED_AMOUNT = Decimal("7250")
_AGREED_AMOUNT = Decimal("6000")
_EMPTY_BUCKET_AMOUNT = Decimal("0")

#: Binding sources whose value originates in the very observation store the
#: comparison reads its filed side from. A casilla opened by one of these would
#: be compared against the figures that opened it, so the subject casilla must
#: not be one.
_CARRY_SOURCE_KINDS = frozenset(
    {
        BindingSourceKind.PREVIOUS_FILING,
        BindingSourceKind.RELATION_PREFILL,
    },
)


@pytest.fixture
def observation_repository(tmp_path: Path) -> Iterator[CalculationObservationRepository]:
    """Yield a repository over a real encrypted bucket holding nothing yet."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        yield CalculationObservationRepository(objects=profile.repository)


def _law_resolved_revision() -> ModeloRevision:
    """Resolve the subject revision the way the production reconcile does.

    From ``(modelo, filing_year, period)`` through the registry authority, never
    from a stored revision id, so the revision under test is the law-determined
    one and the work unit below can only assert it rather than select it.
    """
    return resources().modelos.authority.snapshot(_MODELO, filing_year=_FILING_YEAR, period=_PERIOD_CODE).revision


def _subject_casilla(revision: ModeloRevision) -> tuple[CasillaDefinition, DataBindingDefinition]:
    """Return the casilla the comparison is opened on, and the binding that opens it.

    Chosen structurally rather than by hardcoded id: the lowest-ordered
    non-informational casilla carrying a non-carry binding. Overriding that
    binding is independent evidence, so the casilla enters the comparable scope,
    while a carry binding would be evidence read back out of the filed store the
    comparison is measuring against.
    """
    bindings_by_id: dict[BindingId, DataBindingDefinition] = {binding.id: binding for binding in revision.bindings}
    for casilla in sorted(revision.casillas, key=lambda definition: definition.id):
        if casilla.input_kind is InputKind.INFORMATIONAL or casilla.binding is None:
            continue
        binding = bindings_by_id.get(casilla.binding)
        if binding is None or binding.source in _CARRY_SOURCE_KINDS:
            continue
        return casilla, binding
    raise AssertionError(
        f"registry revision {revision.id!r} declares no non-informational casilla with a "
        "non-carry binding; the divergence case would have nothing to open a scope with",
    )


def _grounding_foil(revision: ModeloRevision, subject: CasillaDefinition) -> CasillaDefinition:
    """Return a casilla whose legal references differ from ``subject``'s.

    Without it the exact-equality grounding assertion could be accidentally true:
    a revision whose casillas all shared one reference tuple would satisfy the
    equality even if the finding had minted its references from a constant.
    """
    for casilla in sorted(revision.casillas, key=lambda definition: definition.id):
        if casilla.legal_refs != subject.legal_refs:
            return casilla
    raise AssertionError(
        f"every casilla of registry revision {revision.id!r} carries the same legal_refs, so "
        "the grounding assertion could not distinguish carried references from minted ones",
    )


def _work_unit() -> WorkUnit:
    """Build the work unit under verification against the law-resolved revision.

    ``revision_id`` is the authority's answer, not an injected selector: the
    production reconcile re-resolves it from the same triple and refuses a
    divergence, so a work unit pinned to anything else would silently make every
    case here vacuous.
    """
    revision = _law_resolved_revision()
    period = Period.from_year_and_code(_FILING_YEAR, _PERIOD_CODE)
    work_unit_id = derive_work_unit_id(
        bucket_id=_BUCKET_ID,
        modelo=_MODELO,
        filing_year=_FILING_YEAR,
        period=period,
        revision_id=revision.id,
    )
    return WorkUnit(
        work_unit_id=work_unit_id,
        bucket_id=_BUCKET_ID,
        modelo=ModeloCode(_MODELO),
        filing_year=_FILING_YEAR,
        period=period,
        revision_id=revision.id,
        name=f"{_MODELO}-{_FILING_YEAR}-{_PERIOD_CODE}",
        created_at=_WORK_UNIT_CREATED_AT,
        updated_at=_WORK_UNIT_UPDATED_AT,
    )


def _calculation(
    work_unit: WorkUnit,
    *,
    casilla_values: Mapping[CasillaId, Decimal],
    binding_overrides: Mapping[BindingId, str] | None = None,
) -> CalculationRevision:
    """Build the local calculation the reconcile compares.

    ``binding_overrides`` is the population-evidence axis every case varies: it
    is what decides whether the local calculation has anything to say about a
    casilla. It is deliberately the ONLY evidence axis exercised, so a case that
    produces findings can only have produced them through it — supplying ledger
    contribution or direct inputs alongside would leave which axis opened the
    scope undetermined.

    ``observations`` is populated from the registry rather than left at its
    default so the persisted grounding envelope is exercised. Their own
    ``formula_id``, ``op`` and ``operand_*`` fields stay empty because the
    subject is a bound casilla and the model contracts those fields as empty when
    no formula ran; filling them would record a computation that did not happen.
    """
    overrides = dict(binding_overrides or {})
    values = dict(casilla_values)
    return CalculationRevision(
        calculation_revision_id=derive_calculation_revision_id(
            work_unit_id=work_unit.work_unit_id,
            input_values_by_casilla_id={},
            binding_overrides=overrides,
            casilla_values=values,
        ),
        work_unit_id=work_unit.work_unit_id,
        state=CalculationRevisionState.BORRADOR,
        binding_overrides=overrides,
        casilla_values=values,
        observations=registry_grounded_observations(
            modelo=_MODELO,
            filing_year=_FILING_YEAR,
            period=_PERIOD_CODE,
            casilla_values=values,
        ),
        created_at=_CREATED_AT,
        updated_at=_UPDATED_AT,
    )


def _persist_pulled_filing(
    repository: CalculationObservationRepository,
    *,
    casilla_values: Mapping[CasillaId, Decimal],
) -> None:
    """Persist one AEAT-observed filing through the production observation write path.

    Synthetic register content, not a test double: the row is written by the same
    repository method the filed-capture finalizer reaches, into the same
    encrypted namespace the reconcile reads, and its provenance is the official
    one a real pull stamps.

    Every defaultable field on the envelope that this row can honestly carry is
    populated away from its default. ``member_nif`` is the deliberate exception:
    a member NIF widens the storage identifier, and the reconcile reads the
    single-filer key, so setting it would file the row where the subject cannot
    find it and silently convert every case below into the no-filing case. The
    Modelo 303 disposition and prior-domiciliation projections and the fichero
    header facts are left unset for the opposite reason: this is a Modelo 130
    register row and no submitted fichero was read, so authoring them would
    assert evidence that does not exist.
    """
    repository.save_observation(
        RegistryModeloObservation(
            modelo=_MODELO,
            filing_year=_FILING_YEAR,
            period=_PERIOD_CODE,
            observations=registry_grounded_observations(
                modelo=_MODELO,
                filing_year=_FILING_YEAR,
                period=_PERIOD_CODE,
                casilla_values=casilla_values,
            ),
        ),
        source_kind=ObservationSourceKind.AEAT_SEDE_JUSTIFICANTE,
        captured_at=_CAPTURED_AT,
        stamped_revision_id=str(_law_resolved_revision().id),
        source_metadata={
            "aeat_register_status": "ALTA",
            "aeat_expediente_id": _SYNTHETIC_EXPEDIENTE_ID,
            "authenticated_identity": _SYNTHETIC_TAX_ID,
        },
    )


def test_no_pulled_filing_produces_no_findings(
    observation_repository: CalculationObservationRepository,
) -> None:
    """A bucket that never pulled anything has nothing to reconcile against.

    Absence of a filed side is not a defect and must not become an advisory: the
    taxpayer may simply not have filed, or the sweep may not have run.
    """
    revision = _law_resolved_revision()
    subject, binding = _subject_casilla(revision)
    work_unit = _work_unit()
    target = _calculation(
        work_unit,
        casilla_values={subject.id: _LOCAL_AMOUNT},
        binding_overrides={binding.id: str(_LOCAL_AMOUNT)},
    )

    # Positive control on the read half: the silence below must come from an
    # absent filing, not from a repository that cannot find a present one.
    stored = observation_repository.load_observation(
        _MODELO,
        Period.from_year_and_code(_FILING_YEAR, _PERIOD_CODE),
    )
    assert stored is None, "the fixture bucket must start with no pulled filing for this modelo and period"

    findings = pulled_filing_divergence_findings(
        work_unit=work_unit,
        target=target,
        observation_repository=observation_repository,
    )

    assert findings == []


def test_a_pulled_filing_against_an_empty_bucket_produces_no_findings(
    observation_repository: CalculationObservationRepository,
) -> None:
    """The freshly onboarded case the whole narrowing exists for.

    The local calculation supplied no independent evidence anywhere, so it has
    nothing to disagree with even though it holds a figure and the filed side
    holds a different one. The control below is what makes this assertion worth
    anything: those same two sides DO diverge once the scope is removed, so the
    silence is the narrowing working rather than the two sides agreeing.
    """
    revision = _law_resolved_revision()
    subject, _binding = _subject_casilla(revision)
    work_unit = _work_unit()
    target = _calculation(work_unit, casilla_values={subject.id: _EMPTY_BUCKET_AMOUNT})
    _persist_pulled_filing(observation_repository, casilla_values={subject.id: _FILED_AMOUNT})

    findings = pulled_filing_divergence_findings(
        work_unit=work_unit,
        target=target,
        observation_repository=observation_repository,
    )

    assert findings == []
    unscoped = detect_casilla_divergences(
        computed=target.casilla_values,
        filed={subject.id: _FILED_AMOUNT},
    )
    assert [row.casilla_id for row in unscoped] == [subject.id], (
        "the two sides must genuinely disagree without the scope, or this case proves "
        "nothing about the narrowing"
    )


def test_a_populated_calculation_agreeing_with_the_filing_produces_no_findings(
    observation_repository: CalculationObservationRepository,
) -> None:
    """A populated bucket whose figures match what AEAT holds must stay quiet.

    This is the pole that stops the advisory from firing on every verified
    filing: the scope is non-empty here, so silence can only come from the two
    sides agreeing.
    """
    revision = _law_resolved_revision()
    subject, binding = _subject_casilla(revision)
    work_unit = _work_unit()
    target = _calculation(
        work_unit,
        casilla_values={subject.id: _AGREED_AMOUNT},
        binding_overrides={binding.id: str(_AGREED_AMOUNT)},
    )
    _persist_pulled_filing(observation_repository, casilla_values={subject.id: _AGREED_AMOUNT})

    findings = pulled_filing_divergence_findings(
        work_unit=work_unit,
        target=target,
        observation_repository=observation_repository,
    )

    assert findings == []


def test_a_diverging_casilla_raises_one_warning_carrying_that_casillas_own_grounding(
    observation_repository: CalculationObservationRepository,
) -> None:
    """One genuine disagreement, one non-blocking advisory, grounded by carry.

    The grounding assertions are the point of this case. A reconcile finding
    asserts no legal proposition of its own, so its references must be the
    diverging casilla's own registry references. Exact tuple equality is asserted
    rather than non-emptiness: a finding carrying references minted for itself
    would satisfy a non-emptiness check and fail this one. The foil casilla makes
    that equality discriminating — its references differ, so equality with the
    subject's is a statement about which casilla diverged rather than a property
    every casilla of the revision happens to share.
    """
    revision = _law_resolved_revision()
    subject, binding = _subject_casilla(revision)
    foil = _grounding_foil(revision, subject)
    work_unit = _work_unit()
    target = _calculation(
        work_unit,
        casilla_values={subject.id: _LOCAL_AMOUNT},
        binding_overrides={binding.id: str(_LOCAL_AMOUNT)},
    )
    _persist_pulled_filing(observation_repository, casilla_values={subject.id: _FILED_AMOUNT})

    findings = pulled_filing_divergence_findings(
        work_unit=work_unit,
        target=target,
        observation_repository=observation_repository,
    )

    assert len(findings) == 1, f"exactly one casilla disagrees; got {[row.message for row in findings]}"
    finding = findings[0]
    assert finding.kind is ModeloVerificationFindingKind.RECONCILIATION_MISMATCH
    assert finding.severity is ModeloVerificationFindingSeverity.WARNING, (
        "the reconcile is advisory: a blocking severity here would refuse a filing on "
        "evidence that may simply be a later AEAT correction"
    )

    # The subject rides a field, not only the prose: an automated operator routes
    # on structure, and a coordinate recoverable only by parsing a message is not
    # a coordinate. The magnitudes stay message-only, which is presentation.
    assert finding.casilla_id == subject.id, (
        "the diverging casilla must be routable from the finding itself, not parsed out of its text"
    )
    assert subject.number in finding.message
    assert str(_LOCAL_AMOUNT) in finding.message
    assert str(_FILED_AMOUNT) in finding.message
    assert CasillaDivergenceKind.VALUE_MISMATCH.value in finding.message
    assert finding.next_action is not None

    assert finding.legal_refs == subject.legal_refs, (
        "the finding must carry the diverging casilla's own legal references, not references "
        f"minted for it; expected {subject.legal_refs!r}, got {finding.legal_refs!r}"
    )
    assert finding.source_refs == subject.source_refs, (
        "the finding must carry the diverging casilla's own source references, not references "
        f"minted for it; expected {subject.source_refs!r}, got {finding.source_refs!r}"
    )
    assert finding.legal_refs != foil.legal_refs, (
        f"casilla {foil.number} carries different legal references, so a finding matching it "
        "would mean the grounding is not read from the diverging casilla at all"
    )
