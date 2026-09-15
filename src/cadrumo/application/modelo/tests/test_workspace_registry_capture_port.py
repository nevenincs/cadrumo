"""A published authority operation serves the workspace registry capture port itself."""

from __future__ import annotations

import pytest

from ....core.authority_grade import RegistryAuthorityGrade
from ....domain.calculations.registry.authority import bundled_indexed_authority
from ....domain.calculations.registry.schema import RegistrySnapshot
from ....domain.calculations.registry.static_inspection import RegistryRevisionInspection
from ..workspace_producers import ModeloWorkspaceRegistryPortV1, RegistryAuthorityCapturePort

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_an_ungraded_capture_is_the_law_selected_static_inspection() -> None:
    with bundled_indexed_authority().operation() as operation:
        port: RegistryAuthorityCapturePort = operation
        capture = port.capture_law_selected_projection("130", filing_year=2026, period="1T")
        selected = operation.revision_for_context("130", filing_year=2026, period="1T")

    assert isinstance(capture.projection, RegistryRevisionInspection)
    assert capture.projection.revision_id == selected.id


def test_a_graded_capture_is_the_admitted_snapshot_of_the_same_revision() -> None:
    with bundled_indexed_authority().operation() as operation:
        capture = operation.capture_law_selected_projection(
            "130",
            filing_year=2026,
            period="1T",
            grade=RegistryAuthorityGrade.CALCULATION,
        )
        expected = operation.snapshot("130", filing_year=2026, period="1T", grade=RegistryAuthorityGrade.CALCULATION)

    assert isinstance(capture.projection, RegistrySnapshot)
    assert capture.projection.revision.id == expected.revision.id
    assert capture.projection.snapshot_ref == expected.snapshot_ref


def test_captures_from_two_leases_of_one_generation_compare_current() -> None:
    with bundled_indexed_authority().operation() as first:
        capture = first.capture_law_selected_projection("130", filing_year=2026, period="1T")
    with bundled_indexed_authority().operation() as second:
        current = second.read_current_coordinate()

    assert capture.generation >= 1
    assert capture.require_current(current) is capture


def test_a_capture_stamps_a_workspace_epoch_the_workspace_accepts() -> None:
    with bundled_indexed_authority().operation() as operation:
        port = ModeloWorkspaceRegistryPortV1(authority=operation, modelo_id="130", filing_year=2026, period="1T")
        captured = port.capture_projection_with_epoch()
        _stamp, current_epoch = port.read_current_stamp_and_epoch()

    assert captured.epoch.generation >= 1
    assert captured.epoch.require_current(current_epoch) is captured.epoch
