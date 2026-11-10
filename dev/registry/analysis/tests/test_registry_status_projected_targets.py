"""A revision with no record design of its own is projected, not reported as a gap.

The classifier asks the canonical temporal resolver which tree-bearing edition
serves the revision's filing year, so these cases run the real authority and
resolver rather than a stand-in.
"""

from __future__ import annotations

import pytest

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority
from cadrumo.domain.calculations.registry.tests.authored_editions import authored_revisions, open_ended_revision

from ...compiler.authority import compiled_bundled_authority
from ..registry_status import (
    PROJECTED_FROM_NEAREST_EDITION,
    _tree_bearing_revisions,
    classify_projected_target,
    project_target_states,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

# Modelo 296 authors editions of which the newest ships no record-design tree, so the
# newest is projected forward from the one before it and the oldest backward is
# projected to by an edition older than every tree. Modelo 185 authors a span that
# begins below the floor, and modelo 036 an edition citing its own record design.
_NEWEST_296 = str(open_ended_revision("296").id)
_TREE_BEARING_296 = str(authored_revisions("296")[-2].id)
_OLDEST_296 = str(authored_revisions("296")[0].id)
_OLDEST_036 = str(authored_revisions("036")[0].id)
_SPAN_BELOW_FLOOR_185 = str(authored_revisions("185")[0].id)
_NEWEST_185 = str(open_ended_revision("185").id)


@pytest.fixture(scope="module")
def authority() -> ValidatedRegistryAuthority:
    return compiled_bundled_authority()


def _classify(authority: ValidatedRegistryAuthority, modelo_id: str, revision_id: str) -> str | None:
    modelo = authority.modelo(modelo_id)
    return classify_projected_target(
        modelo,
        revision_id,
        authority.catalogues.sources,
        tree_revisions=_tree_bearing_revisions(bundled_path("registry", "aeat"), modelo),
        support=authority.catalogues.require_supported_filing_years(),
    )


def test_a_newer_edition_without_a_design_is_projected_forward_from_the_nearest_tree(
    authority: ValidatedRegistryAuthority,
) -> None:
    reason = _classify(authority, "296", _NEWEST_296)
    assert reason is not None
    assert reason.startswith(PROJECTED_FROM_NEAREST_EDITION)
    assert _TREE_BEARING_296 in reason
    assert "forward" in reason


def test_an_older_edition_without_a_design_is_projected_backward_from_the_oldest_tree(
    authority: ValidatedRegistryAuthority,
) -> None:
    reason = _classify(authority, "296", _OLDEST_296)
    assert reason is not None
    assert "backward" in reason


def test_an_edition_citing_its_own_record_design_stays_a_gap(authority: ValidatedRegistryAuthority) -> None:
    assert _classify(authority, "036", _OLDEST_036) is None


def test_an_edition_already_shipping_a_tree_is_never_projected(authority: ValidatedRegistryAuthority) -> None:
    assert _classify(authority, "296", _TREE_BEARING_296) is None


def test_a_projected_target_is_counted_apart_from_unreadable_ones() -> None:
    projected = project_target_states(
        (),
        (("999", "gap", "999/gap declares no export layout to render"),),
        dispositions=(),
        declared_floor=lambda: 0,
        revision_filing_years=lambda _modelo, _revision: (),
        excluded_count=1,
        projected=(("999", "later", f"{PROJECTED_FROM_NEAREST_EDITION}: earlier (forward)"),),
    )
    counts = dict(projected.counts)
    assert counts["projected"] == 1
    assert counts["unreadable"] == 1


def test_a_span_beginning_below_the_floor_is_projected_from_its_last_declared_year(
    authority: ValidatedRegistryAuthority,
) -> None:
    reason = _classify(authority, "185", _SPAN_BELOW_FLOOR_185)
    assert reason is not None
    assert _NEWEST_185 in reason
