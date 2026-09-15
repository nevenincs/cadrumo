"""The workspace capture port answered from one published authority operation."""

from __future__ import annotations

import pytest

from ....core.authority_grade import RegistryAuthorityGrade
from ....domain.calculations.registry.authority import bundled_indexed_authority
from ....domain.calculations.registry.schema import RegistrySnapshot
from ....domain.calculations.registry.static_inspection import RegistryRevisionInspection
from ..registry_authority_capture import PinnedRegistryAuthorityCapture
from ..workspace_producers import RegistryAuthorityCapturePort

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_an_ungraded_capture_is_the_law_selected_static_inspection() -> None:
    with bundled_indexed_authority().operation() as operation:
        port: RegistryAuthorityCapturePort = PinnedRegistryAuthorityCapture(operation)
        capture = port.capture_law_selected_projection("130", filing_year=2026, period="1T")
        selected = operation.revision_for_context("130", filing_year=2026, period="1T")

    assert isinstance(capture.projection, RegistryRevisionInspection)
    assert capture.projection.revision_id == selected.id


def test_a_graded_capture_is_the_admitted_snapshot_of_the_same_revision() -> None:
    with bundled_indexed_authority().operation() as operation:
        capture = PinnedRegistryAuthorityCapture(operation).capture_law_selected_projection(
            "130",
            filing_year=2026,
            period="1T",
            grade=RegistryAuthorityGrade.CALCULATION,
        )
        expected = operation.snapshot("130", filing_year=2026, period="1T", grade=RegistryAuthorityGrade.CALCULATION)

    assert isinstance(capture.projection, RegistrySnapshot)
    assert capture.projection.revision.id == expected.revision.id
    assert capture.projection.snapshot_ref == expected.snapshot_ref


def test_a_capture_compares_current_against_its_own_published_generation() -> None:
    with bundled_indexed_authority().operation() as operation:
        port = PinnedRegistryAuthorityCapture(operation)
        capture = port.capture_law_selected_projection("130", filing_year=2026, period="1T")
        current = port.read_current_coordinate()

    assert capture.comparison_domain == operation.generation.logical_generation
    assert current.comparison_domain == capture.comparison_domain
    assert capture.require_current(current) is capture
