"""A live-grounded profile key keeps the legal citation its registry binding carries."""

from __future__ import annotations

import pytest

from cadrumo.domain.calculations.registry.profile_grounding import build_profile_grounding_index
from cadrumo.domain.user_profile.errors import UserProfileNotFoundError
from dev.registry.compiler.authority import compiled_bundled_authority
from dev.registry.tests.profile_schema_support import load_user_profile_schema

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_no_grounded_profile_key_regresses_to_a_schema_field_with_no_legal_refs() -> None:
    """A live-grounded profile key must not silently lose its schema citation.

    Computed against the LIVE registry authority, not a hardcoded snapshot -
    fails the moment a new ``source = "profile"`` binding is added for a
    field whose schema entry is never updated to carry the same citation.

    Two fields with a deliberately unreconciled two-way citation divergence
    (``iva.autoconsumo_promotor_base``, ``taxpayer_type.irpf_income_categories``)
    are excluded from this check: both already carry non-empty schema
    ``legal_refs``, so they are a different situation - a disagreement
    between two non-empty citation sets - not the "schema carries nothing"
    gap this test guards.
    """
    authority = compiled_bundled_authority()
    index = build_profile_grounding_index(authority)
    schema = load_user_profile_schema()

    regressed: list[str] = []
    for key, grounding in index.items():
        if not grounding.legal_refs:
            continue
        try:
            field = schema.field(key)
        except UserProfileNotFoundError:
            continue
        if not field.legal_refs:
            regressed.append(key)

    assert not regressed, (
        "these profile keys carry a live registry legal_ref but their schema field carries none - "
        f"carry the citation onto the schema field: {sorted(regressed)}"
    )
