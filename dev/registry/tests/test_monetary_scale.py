"""Real-behaviour tests for the monetary scale screen.

The detector cases mutate a copy of a real revision through the typed model the
loader produces, so the screen walks the same objects it walks in production.
"""

from __future__ import annotations

import pytest

from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority, bundled_authority
from dev.registry.analysis.monetary_scale import scale_findings, screen_authority

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@pytest.fixture(scope="module")
def authority() -> ValidatedRegistryAuthority:
    return bundled_authority()


def test_a_money_wire_type_is_not_reported_as_unscaled(authority: ValidatedRegistryAuthority) -> None:
    """The money wire type scales inside the codec, so it settles the question itself.

    Reporting it would be reporting a rule that already exists, and would have
    inflated this screen's finding count roughly twentyfold.
    """
    revision = authority.modelo("303").revisions["2025"]
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
    from dev.registry.analysis.monetary_scale import scale_outcome, sibling_findings

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
    from dev.registry.analysis.monetary_scale import sibling_findings

    revision = authority.modelo("303").revisions["2025"]
    assert sibling_findings(revision, modelo_id="303") == ()


def test_the_sibling_comparison_is_proven_by_a_live_defect_not_a_fixture(
    authority: ValidatedRegistryAuthority,
) -> None:
    """The corpus itself supplies this screen's detector evidence.

    Most screens here construct a defect because the condition they guard does
    not occur. This one does occur: exactly one field in the shipped registry
    disagrees with its siblings, so the screen is proven against a real defect
    rather than a synthetic one. When that field is corrected this test must be
    replaced by a constructed case, and the screen becomes gateable at zero.
    """
    from cadrumo.application.modelo.registry_discovery import registry_modelo_codes
    from dev.registry.analysis.monetary_scale import screen_authority as scale_screen

    modelo_ids = tuple(sorted(str(code) for code in registry_modelo_codes()))
    disagreements = [item for item in scale_screen(authority, modelo_ids) if item.kind == "sibling_scale_disagrees"]
    assert len(disagreements) == 1
    assert disagreements[0].modelo == "353"
    assert str(disagreements[0].casilla_id) == "10"
