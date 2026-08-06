"""Coverage-completeness invariant: no registry modelo is silently absent.

The ``overview`` surface answers "what must this taxpayer file?". A filing
obligation reaches the default calendar only when it has BOTH a deadline window
AND a positive applicability verdict; a modelo failing either was historically
dropped without a trace, so an operator would under-file. These tests pin the
invariant that closes that gap: every
:func:`~cadrumo.application.modelo.registry_modelo_codes` code is partitioned into
exactly one disposition — surfaced, confidently excluded, advised (investigate),
or explicitly out of scope — so nothing can vanish silently.

The original Modelo-190 regression is the canonical shape: an applicable
obligation was missing from the surfaced calendar and therefore had to be
advised rather than silently absent. Current Modelo 190 is now window-backed and
must surface on the real calendar; the coverage diagnostic still protects the
same failure mode for any applicable obligation omitted from the surfaced set.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date

import pytest

from ....core import (
    OUT_OF_SCOPE_OBLIGATIONS,
    UNMODELED_OBLIGATIONS,
)
from ....domain.calculations.registry.applicability import has_applicability_rule
from ....domain.deadlines import (
    EntityType,
    IrpfEstimationRegime,
    IrpfIncomeCategory,
    IVARegime,
    LegalEntityForm,
    TaxpayerProfile,
)
from ...modelo import registry_modelo_codes
from .._agenda import build_overview_agenda
from .._backlog import build_overview_backlog
from .._calendar import build_overview_calendar
from .._calendar_models import OverviewCalendarRange
from .._coverage import CoverageAdviceReason, ObligationCoverageReport, build_obligation_coverage

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_TODAY = date(2026, 7, 1)


def _paying_autonomo() -> TaxpayerProfile:
    """An autónomo who pays withholding-subject income (has employees)."""
    return TaxpayerProfile(
        tax_id="A4567890A",
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


def _universe() -> set[str]:
    """The AEAT obligation universe: registry plus recognized-unmodeled plus out-of-scope."""
    return (
        set(registry_modelo_codes())
        | {str(code) for code in UNMODELED_OBLIGATIONS}
        | {str(code) for code in OUT_OF_SCOPE_OBLIGATIONS}
    )


def _assert_total_partition(report: ObligationCoverageReport) -> None:
    surfaced = set(report.surfaced)
    excluded = set(report.confidently_excluded)
    advised = set(report.advised_modelos)
    out_of_scope = set(report.out_of_scope)
    buckets = [surfaced, excluded, advised, out_of_scope]

    # Every obligation in the AEAT universe lands in at least one bucket: the
    # invariant binds to AEAT reality (registry + recognized-unmodeled), not to
    # the registry's current contents, so nothing can be silently absent.
    union = surfaced | excluded | advised | out_of_scope
    assert union == _universe()

    # The buckets are pairwise disjoint (each modelo has exactly one disposition).
    for i, left in enumerate(buckets):
        for right in buckets[i + 1 :]:
            assert not (left & right), f"disposition overlap: {left & right}"


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


def test_unmodeled_universe_obligations_surface_as_advised() -> None:
    """Recognized AEAT obligations the registry does not model are advised.

    The external-universe gate: an obligation AEAT expects (in
    `UNMODELED_OBLIGATIONS`) but the registry never modeled must surface as
    advised with the registry-unmodeled reason, never invisible. This is what
    binds the guarantee to AEAT reality rather than the registry's contents.
    When the authoritative declaration is empty, the registry-unmodeled bucket
    is empty too; the total-partition assertion remains the load-bearing guard.
    """
    report = build_obligation_coverage(_paying_autonomo(), {"100", "303"}, today=_TODAY)
    _assert_total_partition(report)

    registry_unmodeled_advised = {
        item.modelo for item in report.advised if item.reason is CoverageAdviceReason.REGISTRY_UNMODELED
    }
    assert registry_unmodeled_advised == {str(modelo) for modelo in UNMODELED_OBLIGATIONS}


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
