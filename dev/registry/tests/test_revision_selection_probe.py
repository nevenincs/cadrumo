"""Real-behaviour tests for the declared-code selection probe.

The module exists because three investigations in this project reached a wrong
conclusion by asking a revision with a period code it does not declare. These
tests pin the corrected answers and the property that produces them.
"""

from __future__ import annotations

import pytest

from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority, bundled_authority

from ..analysis.revision_selection_probe import declared_period_codes, probe_modelo

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@pytest.fixture(scope="module")
def authority() -> ValidatedRegistryAuthority:
    return bundled_authority()


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
        class period_selector:  # noqa: N801 - a stand-in shape, not a public type
            periods: tuple[str, ...] = ()

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

    named = [probe for probe in serves if probe.revision == "2008-2022"]
    assert named and all(probe.resolves_to_itself for probe in named)

    blocked = [probe for probe in refuses if probe.revision == "2008-2022"]
    assert blocked and all(probe.resolved is None and probe.refusal for probe in blocked)


def test_a_mid_year_split_resolves_rather_than_reporting_the_probes_own_ambiguity(
    authority: ValidatedRegistryAuthority,
) -> None:
    """Modelo 308 changes revision at the end of June 2011 and every probe still resolves.

    Asked for filing year 2011 alone, the registry refuses as ambiguous, and it
    is right to: two revisions cover parts of that year and the year does not
    say which. Reporting that refusal would have been this module doing exactly
    what it exists to prevent - reading an under-specified question as a
    registry defect.
    """
    probes = probe_modelo(authority, "308")

    assert len(probes) == 4
    assert [probe for probe in probes if not probe.resolves_to_itself] == []


def test_the_registry_still_refuses_a_genuinely_ambiguous_coordinate(
    authority: ValidatedRegistryAuthority,
) -> None:
    """The retry must not hide the refusal that a caller asking by year gets.

    A date inside one window is what disambiguates. Without it the coordinate is
    genuinely undecidable, and the registry refusing it is the behaviour the
    no-silent-under-declaration rule requires. This pins that the refusal is
    still there for anyone who asks the ambiguous question.
    """
    import datetime

    from cadrumo.core.authority_grade import RegistryAuthorityGrade

    with pytest.raises(Exception, match=r"[Aa]mbiguous"):
        authority.admitted_revision_id(
            "308", filing_year=2011, period="AD-HOC", grade=RegistryAuthorityGrade.APPLICABILITY
        )

    before = authority.admitted_revision_id(
        "308",
        filing_year=2011,
        period="AD-HOC",
        on=datetime.date(2011, 3, 1),
        grade=RegistryAuthorityGrade.APPLICABILITY,
    )
    after = authority.admitted_revision_id(
        "308",
        filing_year=2011,
        period="AD-HOC",
        on=datetime.date(2011, 9, 1),
        grade=RegistryAuthorityGrade.APPLICABILITY,
    )
    assert str(before) == "2009-2011-junio"
    assert str(after) == "2011-julio-2015"
