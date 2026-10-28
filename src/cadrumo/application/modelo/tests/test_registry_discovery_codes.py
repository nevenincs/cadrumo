"""Registry modelo codes read from the pinned authority's modelo directories."""

from __future__ import annotations

import pytest

from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ..registry_discovery import registry_list_modelos, registry_modelo_codes

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_codes_are_exactly_the_list_reports_codes_in_its_order(authority_operation: PinnedAuthorityOperation) -> None:
    listed = tuple(row.code for row in registry_list_modelos(operation=authority_operation).modelos)

    codes = registry_modelo_codes(operation=authority_operation)

    assert listed, "the published authority lists no modelo, so the parity proves nothing"
    assert codes == listed


def test_codes_name_each_published_modelo_once(authority_operation: PinnedAuthorityOperation) -> None:
    codes = registry_modelo_codes(operation=authority_operation)

    assert len(set(codes)) == len(codes)
    assert set(codes) == set(authority_operation.modelo_ids())
