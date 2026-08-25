"""Profile flow copy-source resolvers over the real bundled sources.

Every scenario drives the two profile resolvers against the real
singleton profile schema and the real shipped Terminology Handbook
loader — no mocks. Assertions read the resolver's returned strings,
their namespace behaviour, and their ``None`` refusals; they never assert
localized prose content beyond the presence of a schema field's declared
citation token (a stable identifier, not translatable prose).
"""

from __future__ import annotations

import pytest

from ....domain.user_profile.loader import load_user_profile_schema
from ..copy_sources import (
    register_profile_copy_sources,
    resolve_profile_schema_copy,
    resolve_profile_terminology_copy,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _first_field_with_legal_refs() -> tuple[str, tuple[str, ...]]:
    schema = load_user_profile_schema()
    for section in schema.sections:
        for field in section.fields:
            if field.legal_refs:
                return f"{section.key}.{field.key}", tuple(field.legal_refs)
    raise AssertionError("expected at least one schema field with legal_refs")


def test_schema_resolver_projects_description_and_citations() -> None:
    """A profile-schema ref renders the field description plus its citation tokens."""
    path, legal_refs = _first_field_with_legal_refs()
    field = load_user_profile_schema().field(path)
    rendered = resolve_profile_schema_copy(f"profile-schema:{path}")
    assert rendered is not None
    assert field.description in rendered
    for ref in legal_refs:
        assert ref in rendered


def test_schema_resolver_returns_none_outside_namespace() -> None:
    """A SCHEMA_FIELD ref outside the profile-schema namespace is not this resolver's."""
    assert resolve_profile_schema_copy("modelo-work:some.casilla") is None
    assert resolve_profile_schema_copy("identity.tax_id") is None


def test_schema_resolver_returns_none_for_unknown_path() -> None:
    """An in-namespace ref naming no schema field resolves to None, never raises."""
    assert resolve_profile_schema_copy("profile-schema:no_such_section.no_such_field") is None
    assert resolve_profile_schema_copy("profile-schema:nodot") is None


def test_terminology_resolver_projects_approved_concept() -> None:
    """An approved concept renders its locale-matched short description and definition."""
    concept = _lookup("censo")
    rendered = resolve_profile_terminology_copy("profile-terminology:censo")
    assert rendered is not None
    assert concept.short_description in rendered
    assert concept.definition in rendered


def test_terminology_resolver_returns_none_outside_namespace() -> None:
    """A TERMINOLOGY_CONCEPT ref outside the profile-terminology namespace is not ours."""
    assert resolve_profile_terminology_copy("other:censo") is None


def test_terminology_resolver_returns_none_for_unknown_concept() -> None:
    """An unknown concept id resolves to None rather than raising."""
    assert resolve_profile_terminology_copy("profile-terminology:no-such-concept-xyz") is None
    assert resolve_profile_terminology_copy("profile-terminology:") is None


def test_terminology_resolver_excludes_non_approved_concept() -> None:
    """A draft/deprecated concept never renders as taxpayer-facing copy.

    The bundled Handbook always carries non-approved concepts — internal
    machinery concepts are deprecated rather than deleted — so an empty
    sweep would mean the corpus or the lifecycle read drifted, which this
    test must surface rather than skip.
    """
    non_approved = _first_non_approved_concept_id()
    assert non_approved is not None, "the bundled Handbook lost its deprecated internal concepts"
    assert resolve_profile_terminology_copy(f"profile-terminology:{non_approved}") is None


def test_register_profile_copy_sources_is_idempotent() -> None:
    """Re-registration is a guarded no-op — the process-global registry never double-adds."""
    register_profile_copy_sources()
    register_profile_copy_sources()


def _lookup(concept_id: str):
    from ...corpus_search import lookup_terminology

    return lookup_terminology(concept_id)


def _first_non_approved_concept_id() -> str | None:
    from ...corpus_search import load_terminology_concepts

    for concept in load_terminology_concepts():
        if concept.lifecycle != "approved":
            return concept.concept_id
    return None
