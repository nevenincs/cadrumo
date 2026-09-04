"""Coverage-completeness invariant: no registry modelo is silently absent.

The ``overview`` surface answers "what must this taxpayer file?". A filing
obligation reaches the default calendar only when it has BOTH a deadline window
AND a positive applicability verdict; a modelo failing either was historically
dropped without a trace, so an operator would under-file. These tests pin the
invariant that closes that gap: every
:func:`~cadrumo.application.modelo.registry_discovery.registry_modelo_codes` code
is partitioned into
exactly one disposition — surfaced, confidently excluded, advised (investigate),
or explicitly out of scope — so nothing can vanish silently.

The original Modelo-190 regression is the canonical shape: an applicable
obligation was missing from the surfaced calendar and therefore had to be
advised rather than silently absent. Current Modelo 190 is now window-backed and
must surface on the real calendar; the coverage diagnostic still protects the
same failure mode for any applicable obligation omitted from the surfaced set.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import date

import pytest
from pydantic import ValidationError

from ....core.modelo import OUT_OF_SCOPE_OBLIGATIONS, UNMODELED_OBLIGATIONS, Modelo
from ....domain.calculations.registry.applicability import has_applicability_rule
from ....domain.deadlines.models import (
    IrpfEstimationRegime,
    IrpfIncomeCategory,
    IVARegime,
    TaxpayerProfile,
)
from ....domain.contribuyente.entity_type import EntityType, LegalEntityForm
from ....tests.attribute_scope import scoped_attribute
from ...modelo.registry_discovery import registry_modelo_codes
from .. import coverage as _coverage
from ..agenda import build_overview_agenda
from ..backlog import build_overview_backlog
from ..calendar import build_overview_calendar
from ..calendar_models import OverviewCalendarRange
from ..coverage import (
    AdvisedObligation,
    CoverageAdviceReason,
    ObligationCoverageReport,
    build_obligation_coverage,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


_TODAY = date(2026, 7, 1)


def _paying_autonomo() -> TaxpayerProfile:
    """An autónomo who pays withholding-subject income (has employees)."""
    return TaxpayerProfile(
        tax_id="A45678901",
        entity_type=EntityType.NATURAL_PERSON,
        irpf_income_categories=frozenset({IrpfIncomeCategory.ACTIVIDAD_ECONOMICA}),
        irpf_estimation_regime=IrpfEstimationRegime.DIRECTA_NORMAL,
        iva_regime=IVARegime.GENERAL,
        has_employees=True,
    )


def _landlord() -> TaxpayerProfile:
    return TaxpayerProfile(
        tax_id="X1234567L",
        entity_type=EntityType.NATURAL_PERSON,
        irpf_income_categories=frozenset({IrpfIncomeCategory.CAPITAL_INMOBILIARIO}),
        iva_regime=IVARegime.EXENTO,
    )


def _sociedad_limitada() -> TaxpayerProfile:
    return TaxpayerProfile(
        tax_id="B12345674",
        entity_type=EntityType.LEGAL_ENTITY,
        legal_entity_form=LegalEntityForm.SL,
        iva_regime=IVARegime.GENERAL,
    )


_PERSONAS = pytest.mark.parametrize(
    "profile_factory",
    [_paying_autonomo, _landlord, _sociedad_limitada],
    ids=["paying_autonomo", "landlord", "sociedad_limitada"],
)


def _universe(unmodeled: Mapping[Modelo, str] = UNMODELED_OBLIGATIONS) -> set[str]:
    """The AEAT obligation universe: registry plus recognized-unmodeled plus out-of-scope.

    ``unmodeled`` is a parameter rather than a fixed read of
    :data:`~core.UNMODELED_OBLIGATIONS` so the partition invariant can be checked
    against a declaration the builder was actually given, which is how the
    registry-unmodeled disposition gets exercised while the real declaration is
    still empty.
    """
    return (
        set(registry_modelo_codes())
        | {str(code) for code in unmodeled}
        | {str(code) for code in OUT_OF_SCOPE_OBLIGATIONS}
    )


def _assert_total_partition(
    report: ObligationCoverageReport,
    *,
    unmodeled: Mapping[Modelo, str] = UNMODELED_OBLIGATIONS,
) -> None:
    surfaced = set(report.surfaced)
    excluded = set(report.confidently_excluded)
    advised = set(report.advised_modelos)
    out_of_scope = set(report.out_of_scope)
    buckets = [surfaced, excluded, advised, out_of_scope]

    # Every obligation in the AEAT universe lands in at least one bucket: the
    # invariant binds to AEAT reality (registry + recognized-unmodeled), not to
    # the registry's current contents, so nothing can be silently absent.
    union = surfaced | excluded | advised | out_of_scope
    assert union == _universe(unmodeled)

    # The buckets are pairwise disjoint (each modelo has exactly one disposition).
    for i, left in enumerate(buckets):
        for right in buckets[i + 1 :]:
            assert not (left & right), f"disposition overlap: {left & right}"


def test_report_refuses_a_modelo_filed_under_two_dispositions() -> None:
    """The canonical report refuses a partition that contradicts itself.

    The four tuples are a partition, so a modelo cannot be simultaneously
    confidently excluded (an answered "no") and advised (an open question the
    operator must investigate). The refusal lives on the model rather than on
    any one consumer, so a caller that never renders JSON inherits it too, and
    the message must name the modelo and both dispositions it was filed under.
    """
    with pytest.raises(ValidationError) as excinfo:
        ObligationCoverageReport(
            confidently_excluded=("303",),
            advised=(AdvisedObligation(modelo="303", reason=CoverageAdviceReason.APPLICABILITY_UNDETERMINED),),
        )

    message = str(excinfo.value)
    assert "'303'" in message
    assert "confidently_excluded" in message
    assert "advised" in message


def test_report_refuses_one_modelo_repeated_inside_a_disposition() -> None:
    """One disposition cannot list the same modelo twice.

    A repeated code inflates every count taken off the report -- the advised
    count the operator reads as "obligations to investigate" above all -- so the
    partition is enforced by multiplicity, not merely by set overlap.
    """
    with pytest.raises(ValidationError) as excinfo:
        ObligationCoverageReport(surfaced=("303", "303"))

    message = str(excinfo.value)
    assert "'303'" in message
    assert "surfaced" in message


def test_a_real_built_report_satisfies_the_partition_invariant() -> None:
    """The production builder produces a report the invariant accepts.

    The refusal above is only worth having if the live path clears it: this
    proves the enforcement is not merely unreachable, running the real
    registry-backed build rather than a hand-built fixture.
    """
    report = build_obligation_coverage(_paying_autonomo(), {"100", "303"}, today=_TODAY)
    _assert_total_partition(report)


@_PERSONAS
def test_coverage_partitions_full_registry_set(profile_factory: Callable[[], TaxpayerProfile]) -> None:
    """No registry modelo is silently absent from the coverage report."""
    profile = profile_factory()
    surfaced = {"100", "130", "303"}  # an illustrative surfaced subset
    report = build_obligation_coverage(profile, surfaced, today=_TODAY)
    _assert_total_partition(report)


def test_out_of_scope_bucket_matches_central_declaration() -> None:
    """The out-of-scope bucket is exactly the central declaration."""
    report = build_obligation_coverage(_paying_autonomo(), set(), today=_TODAY)
    assert set(report.out_of_scope) == {str(code) for code in OUT_OF_SCOPE_OBLIGATIONS}


def test_out_of_scope_entries_carry_a_recorded_reason() -> None:
    """Every out-of-scope declaration carries a non-empty recorded reason.

    The out-of-scope bucket is the only way a supported obligation becomes
    invisible; the recorded reason is the guardrail that keeps that a documented
    product decision, not a silent omission.
    """
    for modelo, reason in OUT_OF_SCOPE_OBLIGATIONS.items():
        assert reason.strip(), f"out-of-scope modelo {modelo} has no recorded reason"


def test_out_of_scope_cannot_silence_a_positively_decidable_obligation() -> None:
    """Out-of-scope may not cover a modelo the applicability table can decide.

    A modelo with a seed applicability rule can be positively resolved to
    applies / does-not-apply per profile, so it must never be silenced via the
    out-of-scope escape hatch. This gate makes misuse of the hatch a hard failure
    rather than a silent under-scoping.
    """
    for modelo in OUT_OF_SCOPE_OBLIGATIONS:
        assert not has_applicability_rule(str(modelo)), (
            f"out-of-scope modelo {modelo} has a seed applicability rule; "
            "resolve it through applicability instead of silencing it"
        )


def test_applicable_but_unsurfaced_modelo_is_advised_not_silently_absent() -> None:
    """An applicable modelo missing from the surfaced set must be advised.

    The report receives the actual surface rows from calendar construction. If a
    positively applicable modelo is absent from that set, the coverage layer must
    classify it as an applicable-window gap rather than letting it disappear.
    M190 remains a useful seeded example for this diagnostic, even though the
    real calendar now surfaces it.
    """
    report = build_obligation_coverage(_paying_autonomo(), {"111", "100", "303"}, today=_TODAY)
    advised = {item.modelo: item.reason for item in report.advised}
    assert "190" in advised
    assert advised["190"] is CoverageAdviceReason.APPLICABLE_WINDOW_MISSING


def test_every_declared_unmodeled_obligation_surfaces_as_advised() -> None:
    """Whatever the real declaration holds reaches the report as registry-unmodeled.

    The external-universe guarantee, asserted against the live declaration in
    both directions so it cannot drift: no declared obligation is missing from
    the registry-unmodeled bucket, and nothing else is in it. The declaration is
    EMPTY today, so this holds trivially — the discriminating power lives in
    `test_a_recognized_unmodeled_obligation_is_advised_not_invisible`, which
    exercises the same disposition over a non-empty declaration.
    """
    report = build_obligation_coverage(_paying_autonomo(), {"100", "303"}, today=_TODAY)
    _assert_total_partition(report)

    registry_unmodeled_advised = {
        item.modelo for item in report.advised if item.reason is CoverageAdviceReason.REGISTRY_UNMODELED
    }
    assert registry_unmodeled_advised == {str(modelo) for modelo in UNMODELED_OBLIGATIONS}


def test_a_recognized_unmodeled_obligation_is_advised_not_invisible() -> None:
    """A universe member the registry cannot model lands in advised, never nowhere.

    This is the property the registry-unmodeled disposition exists to guarantee,
    and it is unreachable through the real declaration while that declaration is
    empty — so the declaration the builder reads is substituted for one naming a
    genuinely registry-less obligation (:data:`~core.Modelo.M037`, retired by
    Orden HAC/1526/2024 and therefore absent from every registry directory).
    Only the input data is substituted: registry loading, the universe union and
    the disposition walk all run unmodified.

    The baseline half is what makes it discriminate. The code is proven absent
    from all four buckets before the substitution and present in exactly one
    after, so a filter that stopped classifying it — or a substitution that
    never reached the live holder — fails here rather than reading green.
    """
    unmodelled_code = str(Modelo.M037)
    surfaced_input = {"100", "303"}

    baseline = build_obligation_coverage(_paying_autonomo(), surfaced_input, today=_TODAY)
    assert unmodelled_code not in _dispositions(baseline)

    declared = {Modelo.M037: "censo simplificada suprimida; reconocida sin definicion en el registro"}
    assert _coverage._UNMODELED_OBLIGATIONS is UNMODELED_OBLIGATIONS, (
        "the builder no longer reads the module-level declaration this test rebinds"
    )
    with scoped_attribute(_coverage, "_UNMODELED_OBLIGATIONS", declared):
        report = build_obligation_coverage(_paying_autonomo(), surfaced_input, today=_TODAY)
        _assert_total_partition(report, unmodeled=declared)

        advised = {item.modelo: item.reason for item in report.advised}
        assert advised[unmodelled_code] is CoverageAdviceReason.REGISTRY_UNMODELED
        assert unmodelled_code not in set(report.surfaced) | set(report.confidently_excluded) | set(
            report.out_of_scope,
        )


def _dispositions(report: ObligationCoverageReport) -> set[str]:
    """Every modelo code the report accounts for, in any bucket."""
    return (
        set(report.surfaced) | set(report.confidently_excluded) | set(report.advised_modelos) | set(report.out_of_scope)
    )


def test_calendar_attaches_coverage_by_default() -> None:
    """A default calendar build (show_suppressed=False) still carries coverage.

    The report is populated regardless of the suppressed-entries flag, so the
    default surface always exposes what it could not positively scope.
    """
    calendar = build_overview_calendar(
        _paying_autonomo(),
        OverviewCalendarRange(from_date=date(2026, 1, 1), to_date=date(2026, 12, 31)),
        today=_TODAY,
    )
    _assert_total_partition(calendar.coverage)
    assert calendar.coverage.has_advisories
    assert "190" in {entry.modelo for entry in calendar.entries}
    assert "190" in calendar.coverage.surfaced
    assert "190" not in calendar.coverage.advised_modelos


def test_agenda_and_backlog_inherit_calendar_coverage() -> None:
    """Agenda and backlog compose the calendar, so they inherit its coverage."""
    profile = _paying_autonomo()
    agenda = build_overview_agenda(profile, as_of=_TODAY)
    backlog = build_overview_backlog(profile, as_of=_TODAY)
    _assert_total_partition(agenda.coverage)
    _assert_total_partition(backlog.coverage)
    assert "190" in agenda.coverage.surfaced
    assert "190" in backlog.coverage.surfaced
    assert "190" not in agenda.coverage.advised_modelos
    assert "190" not in backlog.coverage.advised_modelos
