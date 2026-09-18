"""Real-behaviour tests for the declared-code selection probe.

The module exists because three investigations in this project reached a wrong
conclusion by asking a revision with a period code it does not declare. These
tests pin the corrected answers and the property that produces them.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass

import pytest

from cadrumo.core.authority_grade import RegistryAuthorityGrade
from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority
from cadrumo.domain.calculations.registry.errors import AmbiguousRevisionSelectionError

from ..analysis.revision_selection_probe import declared_period_codes, probe_modelo
from ..compiler.authority import admitted_revision_id, compiled_bundled_authority
from ..maintenance_support import coverage_assessment_floor, coverage_assessment_horizon

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@pytest.fixture(scope="module")
def authority() -> ValidatedRegistryAuthority:
    return compiled_bundled_authority()


@dataclass(frozen=True, slots=True)
class MidYearSplit:
    """One live coordinate where two revisions divide a single supported year."""

    modelo: str
    year: int
    opens_on: datetime.date
    earlier: str
    later: str
    shared_periods: tuple[str, ...]


def _discovered_mid_year_split(authority: ValidatedRegistryAuthority) -> MidYearSplit | None:
    """Find a revision pair splitting inside one year the support envelope covers.

    Discovered rather than named. The pair this file first used was modelo 308's
    2011 change, which the envelope no longer reaches: every coordinate below the
    floor is refused for being out of support, so the pin proved nothing about
    the ambiguity it was written for. A split is only ambiguous to a year-only
    question when both windows accept the same period code, so a shared code is
    part of what is discovered rather than assumed.
    """
    floor = coverage_assessment_floor(authority.catalogues)
    horizon = coverage_assessment_horizon(authority.catalogues)
    for definition in authority.modelos:
        for later_id, later in definition.revisions.items():
            opens = later.valid_from
            if opens.month == 1 and opens.day == 1:
                continue
            if not floor <= opens.year <= horizon:
                continue
            day_before = opens - datetime.timedelta(days=1)
            for earlier_id, earlier in definition.revisions.items():
                if earlier_id == later_id:
                    continue
                if earlier.valid_from > day_before:
                    continue
                if earlier.valid_to is not None and earlier.valid_to < day_before:
                    continue
                shared = tuple(
                    code for code in declared_period_codes(later) if code in set(declared_period_codes(earlier))
                )
                if not shared:
                    continue
                return MidYearSplit(
                    modelo=str(definition.id),
                    year=opens.year,
                    opens_on=opens,
                    earlier=str(earlier_id),
                    later=str(later_id),
                    shared_periods=shared,
                )
    return None


@pytest.fixture(scope="module")
def mid_year_split(authority: ValidatedRegistryAuthority) -> MidYearSplit:
    """The live split the ambiguity tests below exercise.

    A corpus with no such pair leaves the probe's ambiguity retry unexercised,
    which is a gap in the evidence rather than a passing test, so its absence
    fails here and says what to author instead.
    """
    split = _discovered_mid_year_split(authority)
    if split is None:
        raise AssertionError(
            "no revision pair splits inside a supported year sharing a period code, so the probe's "
            "ambiguity retry is unproven; author a pair on an isolated tree rather than dropping these tests"
        )
    return split


def test_the_three_one_stop_shop_schemes_each_resolve_to_themselves(
    authority: ValidatedRegistryAuthority,
) -> None:
    """Modelo 369's regimes are disambiguated by period family, not left ambiguous.

    Asked with a quarterly code, all three appear to collapse into the union
    scheme, which reads as selection unable to tell them apart. Asked with the
    codes each declares - monthly for the import scheme, ``EXT``-prefixed for the
    exterior scheme - every one resolves to itself.
    """
    probes = probe_modelo(authority, "369", filing_year=2024)

    assert probes, "the probe returned nothing, so the assertions below would hold vacuously"
    assert {probe.revision for probe in probes} >= {"esquema-importacion", "esquema-union"}
    assert [probe for probe in probes if not probe.resolves_to_itself] == []


def test_each_scheme_declares_its_own_period_family(authority: ValidatedRegistryAuthority) -> None:
    """The axis is declared in the selector, which is why the name carries no year."""
    revisions = authority.modelo("369").revisions

    assert declared_period_codes(revisions["esquema-union"]) == ("1T", "2T", "3T", "4T")
    assert declared_period_codes(revisions["esquema-exterior"]) == ("EXT-1T", "EXT-2T", "EXT-3T", "EXT-4T")
    assert len(declared_period_codes(revisions["esquema-importacion"])) == 12


def test_a_revision_declaring_no_codes_reports_none_rather_than_a_default() -> None:
    """A default code is how the wrong question gets asked, so none is supplied.

    Constructed rather than pinned. The first version of this test asserted the
    corpus contains revisions declaring no period codes, and it does not: modelo
    100 declares ``0A`` on every revision. What modelo 100 lacks is
    ``year_from`` and ``year_to``, a different field on the same selector, and
    the two were conflated while writing the test.

    The contract is what matters and it holds regardless of the corpus: a
    revision whose selector declares nothing yields no codes, and a missing
    selector yields none either, so no probe can be built from a guess.
    """

    class _NoSelector:
        period_selector = None

    class _EmptySelector:
        class _PeriodSelector:
            periods: tuple[str, ...] = ()

        period_selector = _PeriodSelector

    assert declared_period_codes(_NoSelector()) == ()
    assert declared_period_codes(_EmptySelector()) == ()
    assert declared_period_codes(object()) == ()


def test_a_year_outside_the_declared_window_is_reported_as_a_named_refusal(
    authority: ValidatedRegistryAuthority,
) -> None:
    """A refusal of a well-formed question is a finding, and is reported as one.

    Modelo 322's ``2008-2022`` names a fourteen-year span and declares
    ``valid_from`` 2022, so asked with its own monthly code it serves 2022 and
    refuses 2015. That is the disagreement between name and window, established
    without the wrong-code artefact that first appeared to show it.
    """
    serves = probe_modelo(authority, "322", filing_year=2022)
    refuses = probe_modelo(authority, "322", filing_year=2015)

    # The presence guard and the claim are asserted separately. ``all`` over an
    # empty list is TRUE, so the guard is what stops a vacuous pass -- and
    # conjoining the two makes a vacuous pass and a real resolution failure read
    # identically. That matters here more than usual: an empty selection means
    # the revision id stopped being returned at all, which is the wrong-artefact
    # reading this test was written to replace, not the name-versus-window
    # disagreement it exists to hold. Live each selection carries 12 probes of
    # 48.
    named = [probe for probe in serves if probe.revision == "2008-2022"]
    assert named, "no probe named revision 2008-2022 for 2022, so the resolution claim below is vacuous"
    unresolved = [probe for probe in named if not probe.resolves_to_itself]
    assert not unresolved, f"revision 2008-2022 serves 2022, so every probe must resolve to itself: {unresolved}"

    blocked = [probe for probe in refuses if probe.revision == "2008-2022"]
    assert blocked, "no probe named revision 2008-2022 for 2015, so the refusal claim below is vacuous"
    served = [probe for probe in blocked if probe.resolved is not None or not probe.refusal]
    assert not served, f"2015 is outside the declared window, so every probe must refuse by name: {served}"


def test_a_mid_year_split_resolves_rather_than_reporting_the_probes_own_ambiguity(
    authority: ValidatedRegistryAuthority, mid_year_split: MidYearSplit
) -> None:
    """Every probe of a modelo whose revisions divide one year still resolves to itself.

    Asked for that filing year alone, the registry refuses as ambiguous, and it
    is right to: two revisions cover parts of the year and the year does not say
    which. Reporting that refusal would have been this module doing exactly what
    it exists to prevent - reading an under-specified question as a registry
    defect.
    """
    probes = probe_modelo(authority, mid_year_split.modelo)

    assert probes, f"modelo {mid_year_split.modelo} produced no probes, so the claim below is vacuous"
    assert {probe.revision for probe in probes} >= {mid_year_split.earlier, mid_year_split.later}
    assert [probe for probe in probes if not probe.resolves_to_itself] == []


def test_the_registry_still_refuses_a_genuinely_ambiguous_coordinate(
    authority: ValidatedRegistryAuthority, mid_year_split: MidYearSplit
) -> None:
    """The retry must not hide the refusal that a caller asking by year gets.

    A date inside one window is what disambiguates. Without it the coordinate is
    genuinely undecidable, and the registry refusing it is the behaviour the
    no-silent-under-declaration rule requires. This pins that the refusal is
    still there for anyone who asks the ambiguous question.
    """
    period = mid_year_split.shared_periods[0]

    # `Exception` accepted any error at all - a TypeError from a changed
    # signature would have satisfied it while the ambiguity check never ran.
    with pytest.raises(AmbiguousRevisionSelectionError, match=r"[Aa]mbiguous"):
        admitted_revision_id(
            authority,
            mid_year_split.modelo,
            filing_year=mid_year_split.year,
            period=period,
            grade=RegistryAuthorityGrade.APPLICABILITY,
        )

    before = admitted_revision_id(
        authority,
        mid_year_split.modelo,
        filing_year=mid_year_split.year,
        period=period,
        on=mid_year_split.opens_on - datetime.timedelta(days=1),
        grade=RegistryAuthorityGrade.APPLICABILITY,
    )
    after = admitted_revision_id(
        authority,
        mid_year_split.modelo,
        filing_year=mid_year_split.year,
        period=period,
        on=mid_year_split.opens_on,
        grade=RegistryAuthorityGrade.APPLICABILITY,
    )
    assert str(before) == mid_year_split.earlier
    assert str(after) == mid_year_split.later


def test_a_year_that_cannot_choose_between_split_windows_is_recorded_not_erased(
    authority: ValidatedRegistryAuthority, mid_year_split: MidYearSplit
) -> None:
    """The retry that rescues the answer must not hide that the year alone failed.

    Both windows of the discovered split cover the same filing year and share a
    period code, so the year alone cannot choose. The probe asks again with a
    date inside the revision's own window, which answers correctly - and that
    retry used to clear the refusal and leave the row indistinguishable from one
    the year decided outright. The single coordinate this screen was built to
    show was therefore invisible in its own output.

    The flag is asserted where the split is, not where a previous corpus state
    put it: every flagged row must name the later window at the split year, and
    no other row may carry the flag.
    """
    probes = probe_modelo(authority, mid_year_split.modelo)
    ambiguous = [probe for probe in probes if probe.year_alone_ambiguous]

    assert ambiguous, "the split year must reach the probe as an ambiguity, or the flag is never exercised"
    assert {(probe.revision, probe.filing_year) for probe in ambiguous} == {(mid_year_split.later, mid_year_split.year)}
    assert all(probe.resolved == mid_year_split.later for probe in ambiguous), "the date retry must still answer"
    assert all(probe.refusal is None for probe in ambiguous), "a rescued coordinate is not a refusal"
