"""Calendar gating keys come from directory metadata, equal to hydrated revisions.

The warning surface needs only the profile fields named by deadline-window
conditions. The modelo directory carries every revision's windows, so reading
it must answer exactly what hydrating each complete revision answers.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from ....domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from ....domain.calculations.registry.schema import ModeloRevision
from ..calendar_warnings import (
    _deadline_window_profile_keys_by_modelo,
    _derive_gating_fields,
    calendar_applicability_profile_keys_for_modelo,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@pytest.fixture
def operation() -> Iterator[PinnedAuthorityOperation]:
    with bundled_indexed_authority().operation() as leased:
        yield leased


def _hydrated_inventory(operation: PinnedAuthorityOperation) -> tuple[tuple[str, ModeloRevision], ...]:
    return tuple(
        (modelo, operation.revision(modelo, str(metadata.id)))
        for modelo in operation.modelo_ids()
        for metadata in operation.modelo_directory(modelo).revisions
    )


def test_directory_gating_fields_equal_the_hydrated_inventory(operation: PinnedAuthorityOperation) -> None:
    inventory = _hydrated_inventory(operation)
    from_revisions = _derive_gating_fields(operation=operation, revision_inventory=inventory)
    from_directory = _derive_gating_fields(operation=operation)

    assert from_directory == from_revisions
    assert _deadline_window_profile_keys_by_modelo(operation=operation, revision_inventory=inventory), (
        "the bundled registry must gate some deadline window on a profile field, or equality proves nothing"
    )


def test_each_modelo_reads_the_same_keys_from_its_directory(operation: PinnedAuthorityOperation) -> None:
    inventory = _hydrated_inventory(operation)
    for modelo in operation.modelo_ids():
        assert calendar_applicability_profile_keys_for_modelo(
            modelo,
            operation=operation,
        ) == calendar_applicability_profile_keys_for_modelo(
            modelo,
            operation=operation,
            revision_inventory=inventory,
        ), modelo
