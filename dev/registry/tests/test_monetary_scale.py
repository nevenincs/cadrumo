"""Real-behaviour tests for the monetary scale screen.

The detector cases mutate a copy of a real revision through the typed model the
loader produces, so the screen walks the same objects it walks in production.
"""

from __future__ import annotations

import pytest

from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority, bundled_authority
from cadrumo.domain.calculations.registry.export import resolved_export_endpoints

from ..analysis.monetary_scale import _SELF_SCALING_WIRE_TYPES, scale_findings, screen_authority

#: Floor for the monetary endpoints the absence claim below is measured over.
#: Live m303's 2025 revision resolves 150 of 174 endpoints to a monetary
#: casilla; two thirds of that, so ordinary revision movement never fires it.
_MINIMUM_MONETARY_ENDPOINTS = 100

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@pytest.fixture(scope="module")
def authority() -> ValidatedRegistryAuthority:
    return bundled_authority()


def test_a_self_scaling_wire_type_is_not_reported_as_unscaled(authority: ValidatedRegistryAuthority) -> None:
    """A self-scaling wire type settles the scale question itself, so it is not reported.

    Reporting one would be reporting a rule that already exists, and would have
    inflated this screen's finding count roughly twentyfold.

    The claim is an ABSENCE, so it needs the population it is absent from. This
    revision yields zero findings of ANY kind, and a screen that had stopped
    reading it would yield zero too -- the assertion below cannot tell those
    apart on its own. So the monetary endpoints are counted first: live m303's
    2025 revision carries 150 of them, every one on the ``decimal`` wire.

    Named for the self-scaling family rather than for ``money``. The test read
    ``a_money_wire_type`` while the revision it loads carries no ``money`` wire
    at all; both types are self-scaling so the assertion passed either way, and
    the name described a case it never exercised.
    """
    revision = authority.modelo("303").revisions["2025"]
    declared = {casilla.id: str(casilla.data_type) for casilla in revision.casillas}
    monetary = [
        endpoint
        for endpoint in resolved_export_endpoints(revision)
        if endpoint.field is not None and declared.get(endpoint.casilla_id) == "money"
    ]
    assert len(monetary) >= _MINIMUM_MONETARY_ENDPOINTS, (
        f"only {len(monetary)} monetary endpoint(s) resolved for m303 2025; below this the screen "
        "examined almost nothing and the absence below says nothing about scaling"
    )
    unscaled_wires = {str(endpoint.field.data_type) for endpoint in monetary} - _SELF_SCALING_WIRE_TYPES
    assert not unscaled_wires, f"this revision no longer exercises a self-scaling wire: {sorted(unscaled_wires)}"

    findings = scale_findings(revision, modelo_id="303")
    assert not [item for item in findings if item.kind == "money_without_scale"]


def test_money_rendered_by_an_unscaled_wire_type_is_reported(authority: ValidatedRegistryAuthority) -> None:
    """A monetary casilla rendered as an integer or text has no scale anywhere."""
    revision = authority.modelo("184").revisions["2025-y-siguientes"]
    findings = [item for item in scale_findings(revision, modelo_id="184") if item.kind == "money_without_scale"]
    assert findings
    assert all("applies no scale" in item.detail for item in findings)


def test_the_unusual_decimal_count_is_reported_as_an_exception(authority: ValidatedRegistryAuthority) -> None:
    """A money field rendered at four decimals is surfaced, not accepted silently."""
    revision = authority.modelo("189").revisions["2025"]
    kinds = {item.kind for item in scale_findings(revision, modelo_id="189")}
    assert "money_unexpected_scale" in kinds


def test_the_unscaled_fields_are_concentrated_and_bounded(authority: ValidatedRegistryAuthority) -> None:
    """The condition is a bounded work item, not a corpus-wide property.

    This pins the shape of the finding rather than its count: if it ever spreads
    beyond a handful of modelos the remedy stops being per-field review.
    """
    from cadrumo.application.modelo.registry_discovery import registry_modelo_codes

    modelo_ids = tuple(sorted(str(code) for code in registry_modelo_codes()))
    unscaled = [item for item in screen_authority(authority, modelo_ids) if item.kind == "money_without_scale"]
    assert unscaled
    assert len({item.modelo for item in unscaled}) <= 6


def test_the_official_part_split_is_not_reported_as_missing_scale(
    authority: ValidatedRegistryAuthority,
) -> None:
    """One casilla carried by an integer part and a decimal part is scaled by construction.

    The official design for several informativas splits an amount across two
    positional fields. Neither field declares a decimal count because the split
    is the encoding, so a per-field reading calls both unscaled when the pair is
    complete. This pins the distinction that separates the real defect from the
    shape, and it is why the reported defect count is 24 rather than 156.
    """
    revision = authority.modelo("347").revisions["2025-y-siguientes"]
    findings = scale_findings(revision, modelo_id="347")
    split = [item for item in findings if item.kind == "money_split_representation"]
    assert split, "modelo 347 carries the official part split"
    assert all("part split" in item.detail for item in split)
    assert not {item.casilla_id for item in split} & {
        item.casilla_id for item in findings if item.kind == "money_without_scale"
    }


def test_a_self_scaling_wire_type_wins_over_the_split_shape(
    authority: ValidatedRegistryAuthority,
) -> None:
    """A money-typed field carried by several fields is already scaled by the codec.

    Checking the split before the wire type reported 156 split fields including
    ones the codec already scales; precedence has to put self-scaling first.
    """
    revision = authority.modelo("390").revisions["2025"]
    findings = scale_findings(revision, modelo_id="390")
    assert not [item for item in findings if item.kind == "money_split_representation"]


def test_sibling_amounts_of_one_record_are_compared_by_outcome_not_spelling(
    authority: ValidatedRegistryAuthority,
) -> None:
    """Money and decimal-with-two-places both emit cents and must not read as a disagreement.

    The modelo 353 record carries both spellings among its correct fields. A
    comparison on the declared wire type would report five false positives here
    and bury the one real defect beside them.
    """
    from ..analysis.monetary_scale import scale_outcome, sibling_findings

    assert scale_outcome("money", None) == scale_outcome("decimal", 2) == "cents"
    assert scale_outcome("integer", None) == "unscaled"

    revision = authority.modelo("353").revisions["2026-desde-02"]
    findings = sibling_findings(revision, modelo_id="353")
    assert len(findings) == 1, "only the unscaled field disagrees with its siblings"
    assert findings[0].kind == "sibling_scale_disagrees"
    assert "unscaled" in findings[0].detail
    assert "cents" in findings[0].detail


def test_a_record_whose_amounts_all_scale_alike_reports_nothing(
    authority: ValidatedRegistryAuthority,
) -> None:
    """Consistent sibling amounts are the normal case and yield no finding."""
    from ..analysis.monetary_scale import sibling_findings

    revision = authority.modelo("303").revisions["2025"]
    assert sibling_findings(revision, modelo_id="303") == ()


def test_the_sibling_comparison_is_proven_by_a_live_defect_not_a_fixture(
    authority: ValidatedRegistryAuthority,
) -> None:
    """The corpus itself supplies this screen's detector evidence.

    Most screens here construct a defect because the condition they guard does
    not occur. This one does occur, so the screen is proven against real defects
    rather than synthetic ones.

    Held by identity rather than by count, deliberately. An earlier version
    asserted that exactly one field disagreed, and it broke when a second
    disagreement arrived through somebody else's commit - reporting the screen
    as failing when the screen had just done its job. A count over a live corpus
    is a ratchet: it fails on the arrival of the very condition it exists to
    detect, and the reader who repairs it by bumping the number has been taught
    to silence the finding. So each known coordinate is named, and the closing
    assertion says only that nothing outside the named set is reported - which
    still catches an over-firing comparison without freezing the population.

    Both coordinates are live filing-correctness defects with open Steps. When
    either is corrected this test fails on its own name, which is the correction
    landing; drop that coordinate and keep the rest. When the last one goes,
    replace the whole test with a constructed case, because the screen becomes
    gateable at zero and a detector with no proof is the failure this module
    exists to avoid.
    """
    from cadrumo.application.modelo.registry_discovery import registry_modelo_codes

    from ..analysis.monetary_scale import screen_authority as scale_screen

    modelo_ids = tuple(sorted(str(code) for code in registry_modelo_codes()))
    disagreements = [item for item in scale_screen(authority, modelo_ids) if item.kind == "sibling_scale_disagrees"]
    reported = {(item.modelo, str(item.casilla_id)) for item in disagreements}
    known = {("200", "03594"), ("353", "10")}
    assert known <= reported, f"a pinned live defect stopped being reported: {sorted(known - reported)}"
    assert reported <= known, f"a sibling-scale disagreement outside the known set: {sorted(reported - known)}"
