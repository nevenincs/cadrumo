"""Verifying an edition below filing grade adds its advisory checks beside the grade refusal, and nothing else.

Every coordinate comes from the published registry: the subject is any edition of
the support envelope the authority serves below filing grade, its grade is read
from the authority, and the checks are the registry's own predicates.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from ....core.authority_grade import RegistryAuthorityGrade
from ....core.casilla_id import CasillaId, validated_casilla_id
from ....core.external_constants import OutputLanguage
from ....core.i18n.render import tr
from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.bindings import CasillaObservation
from ....domain.calculations.registry.errors import NoRevisionForPeriodError
from ....domain.calculations.registry.schema_references import RegistrySnapshotRef, TemporalProjectionDirection
from ....domain.calculations.registry.schema_verification import (
    VerificationFindingKind,
    VerificationPredicateDefinition,
    VerificationPredicateOperator,
    parse_verification_predicate_expression_memo,
)
from ....domain.calculations.registry.temporal import revision_temporal_resolution
from ....domain.calculations.registry.tests.authored_editions import (
    filing_grade_exercises,
    filing_year_envelope,
)
from ....domain.deadlines.models import IVARegime, TaxpayerProfile
from ....domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from ....domain.modelos.codes import ModeloCode
from ....domain.modelos.verification_report import (
    ModeloVerificationFinding,
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
)
from ....domain.modelos.work_unit import WorkUnit, derive_work_unit_id
from ..finding_message_text import BELOW_FILING_GRADE_NOTICE_LOCALE_KEY, finding_message_text
from ..verification_finding_contracts import REGISTRY_SNAPSHOT_GRADE_INSUFFICIENT_SCENARIO
from ..verification_predicates import advisory_predicate_finding, evaluate_predicate_expression
from ..verification_projection import ModeloFindingSnapshot
from ..verification_report_public_facts import ModeloVerificationFindingProjection
from ..verification_revision_findings import collect_revision_verification_findings
from ..work_review_contracts import ModeloWorkReviewFindingSnapshot
from .advisory_diagnostic_repositories import EmptyTransactionCatalogueRepository
from .invoice_catalogue_fake import InvoiceCatalogueFake

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_T0 = datetime(filing_year_envelope().horizon, 1, 15, 12, 0, 0, tzinfo=UTC)
_BUCKET = "below-filing-grade-advisories"
_GRADE_REFUSAL = "application.modelo.findings.registry_authority_grade_insufficient"
_ANNUAL = "0A"


def _casilla(token: str) -> CasillaId:
    return validated_casilla_id(token, surface="test_verify_below_filing_grade_advisories")


def _work_unit(operation: PinnedAuthorityOperation, modelo: str, filing_year: int, period_code: str) -> WorkUnit:
    period = Period.from_year_and_code(filing_year, period_code)
    revision_id = str(operation.revision_for_context(modelo, filing_year=filing_year, period=period.registry_token).id)
    code = ModeloCode(modelo)
    return WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=_BUCKET, modelo=code, filing_year=filing_year, period=period, revision_id=revision_id
        ),
        bucket_id=_BUCKET,
        modelo=code,
        filing_year=filing_year,
        period=period,
        revision_id=revision_id,
        name=f"{modelo}-{filing_year}-{period.registry_token}",
        created_at=_T0,
        updated_at=_T0,
    )


def _revision(work_unit: WorkUnit, casilla_values: dict[CasillaId, Decimal]) -> CalculationRevision:
    return CalculationRevision(
        calculation_revision_id=derive_calculation_revision_id(
            work_unit_id=work_unit.work_unit_id,
            input_values_by_casilla_id={},
            binding_overrides={},
            casilla_values=casilla_values,
            filing_instance_evidence=None,
            source_provenance=(),
        ),
        work_unit_id=work_unit.work_unit_id,
        registry_snapshot_ref=RegistrySnapshotRef(
            modelo=work_unit.modelo,
            revision_id=work_unit.revision_id,
            modelo_year=work_unit.filing_year,
            period=work_unit.period.registry_token,
        ),
        state=CalculationRevisionState.BORRADOR,
        input_values_by_casilla_id={},
        casilla_values=casilla_values,
        observations=tuple(
            CasillaObservation(
                casilla_id=casilla_id,
                value=value,
                legal_refs=("ley-27-2014:art-10",),
                source_refs=("below-filing-grade-advisories",),
            )
            for casilla_id, value in casilla_values.items()
        ),
        created_at=_T0,
        updated_at=_T0,
        filing_instance_evidence=None,
        source_provenance=(),
    )


def _verify(
    operation: PinnedAuthorityOperation, work_unit: WorkUnit, casilla_values: dict[CasillaId, Decimal]
) -> tuple[list[ModeloVerificationFinding], set[str]]:
    """Run the real revision verification and return its findings and precondition scenarios."""
    findings, _resolved, _missing, failures = collect_revision_verification_findings(
        work_unit=work_unit,
        target=_revision(work_unit, casilla_values),
        profile=_profile(),
        transaction_repository=EmptyTransactionCatalogueRepository(bucket_id=_BUCKET),
        invoice_repository=InvoiceCatalogueFake(),
        operation=operation,
        work_profile=None,
    )
    return findings, {failure.scenario_id for failure in failures.values()}


def _casillas(predicate: VerificationPredicateDefinition) -> tuple[CasillaId, ...]:
    return tuple(
        _casilla(token) for token in parse_verification_predicate_expression_memo(predicate.expression).casilla_ids
    )


_PAIR = 2
"""The firing values and violation candidates each name two boxes."""

_FIRING_VALUES = {
    VerificationPredicateOperator.IMPLIES_NONZERO: (Decimal("100.00"), None),
    VerificationPredicateOperator.EQUALS: (Decimal("100.00"), Decimal("90.00")),
}
"""Values that fire each two-casilla advisory operator: a nonzero antecedent left unanswered, or two unequal boxes."""

_VIOLATION_CANDIDATES: tuple[tuple[Decimal, Decimal], ...] = (
    (Decimal("1000.00"), Decimal("10.00")),
    (Decimal("10.00"), Decimal("1000.00")),
    (Decimal("100.00"), Decimal("0")),
    (Decimal("0"), Decimal("100.00")),
)
"""Two-casilla value pairs tried, in order, until the real evaluator reports a blocking check violated."""


@dataclass(frozen=True, slots=True)
class _BelowFilingSubject:
    """An edition below filing grade with one advisory check it fires and one blocking check it violates."""

    work_unit: WorkUnit
    grade: RegistryAuthorityGrade
    advisory: VerificationPredicateDefinition
    firing_values: Mapping[CasillaId, Decimal]
    blocking: VerificationPredicateDefinition
    violating_values: Mapping[CasillaId, Decimal]


def _firing_values(predicate: VerificationPredicateDefinition) -> dict[CasillaId, Decimal] | None:
    """Values that fire a two-casilla advisory of an operator in :data:`_FIRING_VALUES`, else ``None``."""
    memo = parse_verification_predicate_expression_memo(predicate.expression)
    if predicate.finding_kind is not VerificationFindingKind.ADVISORY or memo.operator not in _FIRING_VALUES:
        return None
    casillas = _casillas(predicate)
    if len(casillas) != _PAIR:
        return None
    (first, second), (first_value, second_value) = casillas, _FIRING_VALUES[memo.operator]
    return {first: first_value} if second_value is None else {first: first_value, second: second_value}


def _violating_values(predicate: VerificationPredicateDefinition) -> dict[CasillaId, Decimal] | None:
    """Two-casilla values the real evaluator reports as violating a blocking check, else ``None``."""
    if predicate.finding_kind is not VerificationFindingKind.BLOCKING_RULE:
        return None
    casillas = _casillas(predicate)
    if len(casillas) != _PAIR:
        return None
    first, second = casillas
    for first_value, second_value in _VIOLATION_CANDIDATES:
        values = {first: first_value, second: second_value}
        try:
            holds = evaluate_predicate_expression(predicate.expression, values, _profile())
        except (ValueError, LookupError):
            continue
        if not holds:
            return values
    return None


def _subject_at(operation: PinnedAuthorityOperation, modelo: str, year: int) -> _BelowFilingSubject | None:
    """The subject the annual edition of ``modelo`` for ``year`` offers, or ``None`` when it offers none."""
    try:
        grade = operation.reachable_authority_grade(modelo, filing_year=year, period=_ANNUAL)
    except NoRevisionForPeriodError:
        # The modelo serves no annual declaration for the year.
        return None
    if grade is RegistryAuthorityGrade.FILING:
        return None
    revision = operation.revision_for_context(modelo, filing_year=year, period=_ANNUAL)
    resolution = revision_temporal_resolution(
        revision, filing_year=year, period=_ANNUAL, support=operation.supported_filing_years()
    )
    # A projected year is refused as projected; the grade refusal under test is an edition's own declared grade.
    if resolution.projection_direction is not TemporalProjectionDirection.AUTHORED:
        return None
    work_unit = _work_unit(operation, modelo, year, _ANNUAL)
    predicates = operation.revision(work_unit.modelo, work_unit.revision_id).verification_predicates
    advisory = next(((item, values) for item in predicates if (values := _firing_values(item)) is not None), None)
    blocking = next(((item, values) for item in predicates if (values := _violating_values(item)) is not None), None)
    if advisory is None or blocking is None:
        return None
    return _BelowFilingSubject(
        work_unit=work_unit,
        grade=grade,
        advisory=advisory[0],
        firing_values=advisory[1],
        blocking=blocking[0],
        violating_values=blocking[1],
    )


def _below_filing_subject(operation: PinnedAuthorityOperation) -> _BelowFilingSubject:
    """Return the newest authored envelope edition of any modelo that is below filing grade and declares both checks.

    Editions rise to filing grade as their evidence lands, so the modelo and year are read from the authority,
    never fixed.
    """
    for year in sorted(filing_year_envelope().years, reverse=True):
        for modelo in sorted(operation.modelo_ids()):
            subject = _subject_at(operation, modelo, year)
            if subject is not None:
                return subject
    raise AssertionError(
        "precondition: an authored annual edition below filing grade inside the support envelope declares a two-box advisory "
        "check and a two-box blocking check"
    )


def _advisory_finding(
    findings: list[ModeloVerificationFinding], predicate: VerificationPredicateDefinition
) -> ModeloVerificationFinding:
    (advisory,) = [
        finding for finding in findings if finding.message_facts.get("predicate_id") == predicate.predicate_id
    ]
    return advisory


def test_the_under_declaration_advisory_appears_next_to_the_grade_refusal(
    *, operation: PinnedAuthorityOperation
) -> None:
    subject = _below_filing_subject(operation)
    work_unit, grade, predicate = subject.work_unit, subject.grade, subject.advisory
    assert predicate.finding_kind is VerificationFindingKind.ADVISORY

    findings, scenarios = _verify(operation, work_unit, dict(subject.firing_values))

    refusals = [finding for finding in findings if finding.message_locale_key == _GRADE_REFUSAL]
    (refusal,) = refusals
    assert refusal.severity is ModeloVerificationFindingSeverity.BLOCKING
    assert refusal.below_filing_grade is None
    assert refusal.message_facts["declared_grade"] == grade.value
    assert scenarios == {REGISTRY_SNAPSHOT_GRADE_INSUFFICIENT_SCENARIO}
    advisory = _advisory_finding(findings, predicate)
    assert advisory.kind is ModeloVerificationFindingKind.ADVISORY
    assert advisory.severity is ModeloVerificationFindingSeverity.WARNING
    assert advisory.below_filing_grade is grade
    assert advisory.legal_refs == tuple(predicate.legal_refs)
    assert advisory.model_dump(mode="json")["below_filing_grade"] == grade.value


@pytest.mark.parametrize("language", tuple(OutputLanguage))
def test_the_advisory_says_its_edition_is_not_filing_grade(
    language: OutputLanguage, *, operation: PinnedAuthorityOperation
) -> None:
    subject = _below_filing_subject(operation)
    findings, _scenarios = _verify(operation, subject.work_unit, dict(subject.firing_values))
    advisory = _advisory_finding(findings, subject.advisory)

    notice = tr(BELOW_FILING_GRADE_NOTICE_LOCALE_KEY, locale=language.value)
    own = tr(advisory.message_locale_key, locale=language.value)
    assert notice != BELOW_FILING_GRADE_NOTICE_LOCALE_KEY
    assert finding_message_text(advisory, language) == f"{own} {notice}"


def test_no_blocking_registry_check_is_evaluated_below_filing_grade(*, operation: PinnedAuthorityOperation) -> None:
    subject = _below_filing_subject(operation)
    work_unit, grade, blocking = subject.work_unit, subject.grade, subject.blocking
    assert blocking.finding_kind is VerificationFindingKind.BLOCKING_RULE
    values = dict(subject.violating_values)
    # The values violate the edition's blocking check through the real evaluator.
    assert not evaluate_predicate_expression(blocking.expression, values, _profile())

    findings, scenarios = _verify(operation, work_unit, values)

    (refusal,) = [finding for finding in findings if finding.severity is ModeloVerificationFindingSeverity.BLOCKING]
    assert refusal.message_locale_key == _GRADE_REFUSAL
    assert scenarios == {REGISTRY_SNAPSHOT_GRADE_INSUFFICIENT_SCENARIO}
    assert all(
        finding.kind is ModeloVerificationFindingKind.ADVISORY and finding.below_filing_grade is grade
        for finding in findings
        if finding is not refusal
    )


@pytest.mark.parametrize("modelo", ["100", "390"])
def test_a_filing_grade_edition_verifies_as_before(modelo: str, *, operation: PinnedAuthorityOperation) -> None:
    work_unit = _work_unit(operation, modelo, filing_grade_exercises(modelo)[-1], _ANNUAL)
    assert (
        operation.reachable_authority_grade(
            modelo, filing_year=work_unit.filing_year, period=work_unit.period.registry_token
        )
        is RegistryAuthorityGrade.FILING
    )
    revision = operation.revision(work_unit.modelo, work_unit.revision_id)
    predicate = next(
        item
        for item in revision.verification_predicates
        if item.finding_kind is VerificationFindingKind.ADVISORY
        and parse_verification_predicate_expression_memo(item.expression).operator in _FIRING_VALUES
    )
    first_value, second_value = _FIRING_VALUES[
        parse_verification_predicate_expression_memo(predicate.expression).operator
    ]
    first, second = _casillas(predicate)
    values = {first: first_value} if second_value is None else {first: first_value, second: second_value}

    findings, _scenarios = _verify(operation, work_unit, values)

    assert all(finding.message_locale_key != _GRADE_REFUSAL for finding in findings)
    assert all(finding.below_filing_grade is None for finding in findings)
    assert all("below_filing_grade" not in finding.model_dump(mode="json") for finding in findings)
    assert advisory_predicate_finding(predicate) in findings


def test_the_grade_survives_every_finding_projection(*, operation: PinnedAuthorityOperation) -> None:
    subject = _below_filing_subject(operation)
    grade = subject.grade
    findings, _scenarios = _verify(operation, subject.work_unit, dict(subject.firing_values))
    advisory = _advisory_finding(findings, subject.advisory)

    assert ModeloFindingSnapshot.from_finding(advisory).to_finding() == advisory
    assert ModeloVerificationFindingProjection.from_finding(advisory).to_finding() == advisory
    assert ModeloWorkReviewFindingSnapshot.from_finding(advisory).to_finding() == advisory
    assert ModeloFindingSnapshot.from_finding(advisory).model_dump(mode="json")["below_filing_grade"] == grade.value


@pytest.mark.parametrize(
    ("kind", "severity", "grade"),
    [
        (
            ModeloVerificationFindingKind.ADVISORY,
            ModeloVerificationFindingSeverity.WARNING,
            RegistryAuthorityGrade.FILING,
        ),
        (
            ModeloVerificationFindingKind.BLOCKING_RULE,
            ModeloVerificationFindingSeverity.BLOCKING,
            RegistryAuthorityGrade.CALCULATION,
        ),
        (
            ModeloVerificationFindingKind.ADVISORY,
            ModeloVerificationFindingSeverity.BLOCKING,
            RegistryAuthorityGrade.CALCULATION,
        ),
    ],
)
def test_only_an_advisory_warning_carries_a_grade_below_filing(
    kind: ModeloVerificationFindingKind,
    severity: ModeloVerificationFindingSeverity,
    grade: RegistryAuthorityGrade,
) -> None:
    with pytest.raises(ValueError, match="filing grade"):
        ModeloVerificationFinding(
            kind=kind,
            severity=severity,
            message_locale_key="application.modelo.findings.registry_advisory_predicate_fired",
            legal_refs=("ley-27-2014:art-10",),
            below_filing_grade=grade,
        )


def _profile() -> TaxpayerProfile:
    return TaxpayerProfile(tax_id="X0001500M", iva_regime=IVARegime("GENERAL"))
