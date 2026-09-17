"""Unrouted registry sources are refused without development classifications."""

from __future__ import annotations

import pytest

from ....core.aggregation import BindingSourceKind
from ....domain.calculations.registry.binding_provider_registration import BINDING_PROVIDER_REGISTRATIONS
from ....domain.calculations.registry.schema import ModeloRevision
from ....domain.calculations.registry.tests.published_authority import published_revision_definitions
from ..action_errors import ModeloAggregationBindingError
from ..calculation_actions import assert_no_novel_source_kinds
from ..calculation_route import CALCULATION_ROUTE_ENROLLED_SOURCES

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _declared_off_route(source: BindingSourceKind) -> bool:
    """Kinds registered deferred or non-runtime surface at resolution, not at this gate."""
    registration = BINDING_PROVIDER_REGISTRATIONS.get(source)
    return registration is not None and registration.disposition in ("deferred", "non_runtime")


def _derived_gaps(revision: ModeloRevision) -> tuple[str, ...]:
    return tuple(
        sorted(
            {
                binding.source.value
                for binding in revision.bindings
                if binding.source not in CALCULATION_ROUTE_ENROLLED_SOURCES and not _declared_off_route(binding.source)
            }
        )
    )


def test_every_live_revision_meets_the_gate_with_its_derived_gap_set() -> None:
    """The runtime guard refuses exactly the mechanically derived gap set, which may be empty."""
    revisions = [revision for modelo in published_revision_definitions() for revision in modelo.revisions.values()]
    assert revisions, "the published authority carries no revisions; the walk would be vacuous"

    for revision in revisions:
        expected_gaps = _derived_gaps(revision)
        if not expected_gaps:
            assert_no_novel_source_kinds(revision)
            continue
        with pytest.raises(ModeloAggregationBindingError) as exc_info:
            assert_no_novel_source_kinds(revision)
        assert exc_info.value.context is not None
        novel_source_kinds = exc_info.value.context["novel_source_kinds"]
        assert isinstance(novel_source_kinds, list)
        assert tuple(novel_source_kinds) == expected_gaps, revision.id
