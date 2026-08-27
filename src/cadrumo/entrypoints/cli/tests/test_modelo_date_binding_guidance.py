"""Date-binding facts stay factual at the CLI transport boundary."""

from __future__ import annotations

import pytest

from ....domain.calculations.registry.authority import bundled_authority
from ....domain.calculations.registry.runtime_graph import revision_date_binding_ids
from .._modelo_behavior_support import _date_binding_profile_requirements

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_missing_date_binding_fallback_is_a_fact_not_a_cli_recovery() -> None:
    """An unresolved date binding names only its registry fact, never a command."""

    snapshot = bundled_authority().snapshot("100", filing_year=2025, period="0A")
    binding_id = "renta-2025-profile-taxpayer-birth-date"
    assert binding_id in revision_date_binding_ids(snapshot.revision)

    fact = _date_binding_profile_requirements(None, binding_id)

    assert fact == binding_id
    assert "aeat" not in fact.casefold()
