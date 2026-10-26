"""Runtime evidence for LIVA art. 3 assimilation through the public resolver.

Mutable carve-out parsing and assimilation-chain validation belong to the
development registry compiler.  This domain test keeps the runtime contract:
an assimilated territory follows the public country-scope resolver for its
declared parent.
"""

from __future__ import annotations

import pytest

from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority as _indexed_authority_for_test

from ..establishment import territorial_scope_for_country

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_the_bundled_table_resolves_monaco_through_its_parent() -> None:
    """The runtime pointer agrees with France without pinning a literal scope."""
    with _indexed_authority_for_test().operation() as _authority_operation_for_test:
        assert territorial_scope_for_country(
            "MC", operation=_authority_operation_for_test
        ) == territorial_scope_for_country("FR", operation=_authority_operation_for_test)
