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

FIXTURE DEFAULTS ARE A DELIBERATE AXIS. Every model built here is populated away
from its defaults wherever a non-default value is honest, because the default
state is exactly what a save-drops-field / load-re-defaults regression collapses
to: a fixture sitting at the defaults cannot tell a field that survived from one
that was dropped and re-defaulted on the way back. Where a field IS left at its
default the reason is written beside it, and it is always one of three — the
model refuses a value there in this lifecycle state, the field belongs to a
modelo or artefact family this row is not, or populating it would assert
evidence the run never produced. A field left at its default with no reason is
the state this module does not carry.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....core import CasillaId, Period
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.calculations.registry.bindings import RegistryModeloObservation
from ....domain.calculations.registry.ids import BindingId
from ....domain.calculations.registry.schema import DataBindingDefinition, ModeloRevision
from ....domain.calculations.registry.schema_input_kind import InputKind
from ....domain.calculations.registry.schema_surfaces import CasillaDefinition
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
from .._pulled_filing_reconcile import pulled_filing_divergence_findings
from .._reconcile_casilla import (
    CasillaDivergenceKind,
    detect_casilla_divergences,
)
from .._reconcile_population import _CARRY_SOURCE_KINDS as _PRODUCTION_CARRY_SOURCE_KINDS

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
# The código seguro de verificación is the coordinate that makes a sede
# justificante retrievable from AEAT at all, so a justificante-sourced row
# carrying none is indistinguishable from one whose metadata was dropped.
_SYNTHETIC_JUSTIFICANTE_CSV = "MNPQ7RS9TUVW2XYZ4AB6"
# The runtime harness labels every bucket "Test runtime profile" by default, so
# that value is the one a dropped label re-defaults to.
_BUCKET_LABEL = "Pulled-filing reconcile fixture bucket"

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
#:
#: Imported from the production scope resolver rather than restated. A local copy
#: would keep passing after production widened or narrowed the set, so the test
#: would silently stop selecting the subject the production rule selects — and it
#: would agree with itself while disagreeing with the code under test.
_CARRY_SOURCE_KINDS = _PRODUCTION_CARRY_SOURCE_KINDS


@pytest.fixture
def observation_repository(tmp_path: Path) -> Iterator[CalculationObservationRepository]:
    """Yield a repository over a real encrypted bucket holding nothing yet.

    ``label`` is the harness's one defaultable provisioning argument and lands in
    the bucket's plaintext manifest, so it is supplied rather than left at the
    shared default it would re-default to if the manifest write dropped it.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID, label=_BUCKET_LABEL) as profile:
        yield CalculationObservationRepository(objects=profile.repository)


def _law_resolved_revision() -> ModeloRevision:
    """Resolve the subject revision the way the production reconcile does.

    From ``(modelo, filing_year, period)`` through the registry authority, never
    from a stored revision id, so the revision under test is the law-determined
    one and the work unit below can only assert it rather than select it.
    """
    return bundled_authority().snapshot(_MODELO, filing_year=_FILING_YEAR, period=_PERIOD_CODE).revision


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


def _work_unit(*, current_calculation_revision_id: str | None = None) -> WorkUnit:
    """Build the work unit under verification against the law-resolved revision.

    ``revision_id`` is the authority's answer, not an injected selector: the
    production reconcile re-resolves it from the same triple and refuses a
    divergence, so a work unit pinned to anything else would silently make every
    case here vacuous.

    ``current_calculation_revision_id`` points at the draft calculation this unit
    holds, so the pair is internally coherent rather than a unit claiming to hold
    no calculation while a calculation for it is under verification. It is not
    one of the five axes ``derive_work_unit_id`` folds, so attaching it once the
    calculation exists leaves the content-addressed id untouched.

    The remaining defaultable fields stay at their defaults, each because the
    model or the modelo leaves no honest alternative:

    * ``state`` stays ``BORRADOR``. The only other member is ``DESCARTADO``,
      which names an abandoned unit, and the reconcile is a live-verification
      advisory.
    * ``discarded_at``, ``discarded_by`` and ``discard_reason`` are REFUSED by
      the model while the state is ``BORRADOR``; there is no non-default value
      to populate rather than a value not chosen.
    * ``filed_calculation_revision_id`` and ``current_filing_record_id`` would
      assert a local filing. This application never files; the calculation here
      is a draft, and the filed side of the comparison is AEAT's own register
      row rather than anything this bucket recorded. Pointing either at the
      draft would also contradict its ``BORRADOR`` state.
    * ``causante_ccaa`` is the ISD (650/660) and ITPyAJD (600/620) jurisdiction
      axis. Modelo 130 follows the declarant's profile CCAA, so a value here
      would state a jurisdiction the modelo does not carry.
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
        current_calculation_revision_id=current_calculation_revision_id,
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
    default so the persisted grounding envelope is exercised.

    The other three evidence axes stay empty on purpose, and that IS the design
    above rather than an unconsidered default: ``input_values_by_casilla_id``
    (direct operator input), ``source_transaction_ids`` (ledger contribution)
    and ``relation_overrides`` are the remaining inputs
    ``resolve_casilla_population_scope`` reads. Supplying any of them alongside
    the overrides would leave which axis opened the scope undetermined, and a
    relation value would be worse still — its value originates in the very
    filed-observation store the comparison reads its filed side from, which is
    why the scope excludes relations from evidence in the first place.

    Every remaining defaultable field is left at its default for a stated
    reason:

    * ``row_binding_values`` carries row-indexed values for repeating export
      records. Modelo 130 declares scalar casillas only, so a row coordinate
      here would index records the diseño does not have.
    * ``m210_official_tipo_renta_code`` and ``m210_gross_income_source_mode``
      are Modelo 210 axes; the code field's validator refuses any token outside
      the registry's Modelo 210 projection, so no honest value exists for a 130.
    * ``borrador_snapshot_id`` and ``bindings_sourced_from_borrador`` would say
      the local figures were sourced from an AEAT borrador, which contradicts
      the operator override that actually supplies them here.
    * ``unresolved_outcomes`` records casillas the engine could not resolve.
      Every casilla here resolves — the values are supplied — and a populated
      entry becomes a BLOCKING verification finding, which would change what
      each case measures.
    * ``ledger_filing_snapshot`` and ``ledger_filing_evidence`` are captured at
      verify/file time over consumed ledger rows. This is an unsnapshotted
      draft that consumed none.
    * ``source_provenance`` traces which resolver mesh and which upstream source
      objects produced the revision. No mesh ran; the values were supplied
      directly, so a trace would name resolvers that never executed.
    * ``source_issues`` records a source that reached no declared binding. There
      is no unrouted source here, and a populated issue both blocks verification
      and enters the content-addressed id.
    * ``detail_rows`` belongs to the informational modelos whose content is
      repeating records (184, 232, 347, 349). Modelo 130 is not one.
    * ``verified_at``, ``verified_by``, ``filed_at``, ``filed_by``,
      ``superseded_at``, ``discarded_at``, ``discarded_by`` and
      ``discard_reason`` are REFUSED by the model while the state is
      ``BORRADOR``. There is no non-default value available to populate.
    * ``amendment_kind``, ``amends_filing_record_id`` and ``amendment_reason``
      are all-set-or-all-None. Declaring an amendment would make the divergence
      case ambiguous rather than stronger: an amendment draft is EXPECTED to
      disagree with the filing it amends, so a finding could no longer be read
      as a genuine gap.

    The registry-grounded observations themselves leave ``formula_id``, ``op``,
    ``operand_refs``, ``operand_casilla_refs`` and ``operand_values`` empty
    because the subject is a bound casilla and the model contracts those fields
    as empty when no formula ran; filling them would record a computation that
    did not happen. ``absent_by_design`` stays ``False`` for the opposite
    reason — it marks a zero materialised because the binding found no source
    anchor for the period, and this fixture supplies a real value through that
    binding, so ``True`` would mislabel a value-bearing observation.
    """
    overrides = dict(binding_overrides or {})
    values = dict(casilla_values)
    return CalculationRevision(
        calculation_revision_id=derive_calculation_revision_id(
            work_unit_id=work_unit.work_unit_id,
            input_values_by_casilla_id={},
            binding_overrides=overrides,
            casilla_values=values,
            filing_instance_evidence=None,
            source_provenance=(),
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
        filing_instance_evidence=None,
        source_provenance=(),
    )


def _work_unit_and_calculation(
    *,
    casilla_values: Mapping[CasillaId, Decimal],
    binding_overrides: Mapping[BindingId, str] | None = None,
) -> tuple[WorkUnit, CalculationRevision]:
    """Return the coherent work unit and draft calculation each case runs on.

    The calculation is built first because its content-addressed id is what the
    unit's ``current_calculation_revision_id`` points at. The draft unit the
    calculation is addressed to and the returned unit share one ``work_unit_id``:
    that pointer is not one of the id's five axes, so attaching it cannot
    re-address the calculation away from the unit that carries it.
    """
    draft_unit = _work_unit()
    target = _calculation(
        draft_unit,
        casilla_values=casilla_values,
        binding_overrides=binding_overrides,
    )
    return _work_unit(current_calculation_revision_id=target.calculation_revision_id), target


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
    populated away from its default: ``captured_at`` is an explicit instant,
    ``stamped_revision_id`` the law-resolved id, and ``source_metadata`` carries
    the register status, the expediente id, the authenticated identity and the
    justificante CSV — the coordinate that makes a sede justificante retrievable
    at all, and therefore the one whose absence would be indistinguishable from
    a metadata field dropped at persistence.

    The rest are left at their defaults, each for a reason:

    * ``member_nif`` widens the storage identifier for a grupo-de-entidades
      member, and the reconcile reads the single-filer key. Setting it would
      file the row where the subject cannot find it and silently convert every
      case below into the no-filing case.
    * ``source_headers`` carries typed diseño header facts, and
      ``ObservedHeaderFact`` admits a single source artefact kind — the
      submitted fichero — because a justificante is a receipt that does not
      expose the record design's header fields. This row's provenance IS a
      justificante, so a header fact here would attribute evidence to a source
      that cannot produce it, and its locator would name a record position no
      artefact was read from.
    * ``result_disposition`` is the validated Modelo 303 declaration
      disposition and ``prior_domiciliation_election`` the Modelo 303
      rectificativa's prior-direct-debit election. This is a Modelo 130 register
      row; neither concept exists for it.
    * ``normalize_m303_carry`` is the Modelo 303 carry-ingress policy switch. It
      returns the envelope untouched for any other modelo, so enabling it here
      would state an intent the write path cannot act on.

    ``m303_compensation_basis`` is set only by that ingress on the envelope it
    returns; the write path exposes no parameter for it, so it is not a fixture
    choice to make.
    """
    repository.save(
        repository.prepare_observation_envelope(
            RegistryModeloObservation(
                modelo=_MODELO,
                filing_year=_FILING_YEAR,
                period=_PERIOD_CODE,
                # ``filing_period`` is omitted because the model's own before-validator
                # hydrates it from filing_year and period and then refuses any value
                # inconsistent with them, so no differing value is constructible.
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
                "aeat_justificante_csv": _SYNTHETIC_JUSTIFICANTE_CSV,
            },
        )
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
    work_unit, target = _work_unit_and_calculation(
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
    work_unit, target = _work_unit_and_calculation(casilla_values={subject.id: _EMPTY_BUCKET_AMOUNT})
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
        "the two sides must genuinely disagree without the scope, or this case proves nothing about the narrowing"
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
    work_unit, target = _work_unit_and_calculation(
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
    work_unit, target = _work_unit_and_calculation(
        casilla_values={subject.id: _LOCAL_AMOUNT},
        binding_overrides={binding.id: str(_LOCAL_AMOUNT)},
    )
    _persist_pulled_filing(observation_repository, casilla_values={subject.id: _FILED_AMOUNT})

    findings = pulled_filing_divergence_findings(
        work_unit=work_unit,
        target=target,
        observation_repository=observation_repository,
    )

    assert len(findings) == 1, f"exactly one casilla disagrees; got {findings!r}"
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
    assert finding.message_facts["casilla_number"] == subject.number
    assert finding.message_facts["computed_value"] == _LOCAL_AMOUNT
    assert finding.message_facts["filed_value"] == _FILED_AMOUNT
    assert finding.message_facts["mismatch_kind"] == CasillaDivergenceKind.VALUE_MISMATCH.value
    assert "next_action" not in finding.model_dump(mode="json")

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
