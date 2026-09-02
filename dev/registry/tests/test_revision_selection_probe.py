"""Real-behaviour tests for the declared-code selection probe.

The module exists because three investigations in this project reached a wrong
conclusion by asking a revision with a period code it does not declare. These
tests pin the corrected answers and the property that produces them.
"""

from __future__ import annotations

import pytest

from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority, bundled_authority
from dev.registry.analysis.revision_selection_probe import declared_period_codes, probe_modelo

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


def test_a_revision_declaring_no_codes_yields_no_probe_rather_than_a_guessed_one(
    authority: ValidatedRegistryAuthority,
) -> None:
    """A default code is how the wrong question gets asked, so none is supplied.

    Modelo 100's revisions declare no period codes. The probe reports nothing for
    them, which is honest: it has not been told what to ask.
    """
    revisions = authority.modelo("100").revisions
    without_codes = [rid for rid, rev in revisions.items() if not declared_period_codes(rev)]

    assert without_codes, "the corpus is expected to contain revisions declaring no period codes"
    probes = probe_modelo(authority, "100")
    assert [probe.revision for probe in probes if probe.revision in without_codes] == []


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
