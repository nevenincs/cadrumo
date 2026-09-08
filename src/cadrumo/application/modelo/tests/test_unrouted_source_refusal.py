"""Unrouted registry sources are refused without development classifications."""

from __future__ import annotations

import pytest

from ....domain.calculations.registry.authority import bundled_authority
from ..action_errors import ModeloAggregationBindingError
from ..calculation_actions import assert_no_novel_source_kinds
from ..calculation_route import CALCULATION_ROUTE_ENROLLED_SOURCES

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _unrouted_revisions():
    for modelo in bundled_authority().modelos:
        for revision in modelo.revisions.values():
            gaps = tuple(
                sorted(
                    {
                        binding.source.value
                        for binding in revision.bindings
                        if binding.source not in CALCULATION_ROUTE_ENROLLED_SOURCES
                    }
                )
            )
            if gaps:
                yield revision, gaps


@pytest.mark.parametrize(("revision", "expected_gaps"), tuple(_unrouted_revisions()))
def test_each_live_unrouted_revision_is_refused(revision, expected_gaps: tuple[str, ...]) -> None:
    """The runtime guard reports its mechanically derived current gap set."""
    with pytest.raises(ModeloAggregationBindingError) as exc_info:
        assert_no_novel_source_kinds(revision)

    assert exc_info.value.context is not None
    assert tuple(exc_info.value.context["novel_source_kinds"]) == expected_gaps
