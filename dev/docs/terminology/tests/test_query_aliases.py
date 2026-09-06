"""Real-behaviour tests for the independent search query authority."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

from cadrumo.core.concept_lifecycle import ConceptLifecycle
from cadrumo.core.external_constants import OutputLanguage

from ...terminology_handbook.loader import load_terminology_handbook
from .._query_aliases import (
    QUERY_ALIAS_AUTHORITY_SCHEMA_VERSION,
    QueryAliasAuthority,
    QueryAliasAuthorityError,
    QueryAliasEntry,
    build_query_alias_authority_provenance,
    load_query_alias_authority,
    query_alias_authority_path,
    validate_query_alias_authority,
)
from .._sweep import enumerate_query_vocabulary

pytestmark = [pytest.mark.unit, pytest.mark.hex_core, pytest.mark.docs]


def _entry(**updates: object) -> QueryAliasEntry:
    data: dict[str, object] = {
        "concept_id": "prorrata",
        "language": OutputLanguage.ES,
        "query": "reparto proporcional",
        "canonical_query": "prorrata",
        "status": "ratified",
        "review_reason": "RAG-grounded project wording reviewed for the closed vocabulary.",
        "reviewed_at": date(2026, 8, 6),
    }
    data.update(updates)
    return QueryAliasEntry.model_validate(data)


def _authority(*entries: QueryAliasEntry, **updates: object) -> QueryAliasAuthority:
    data: dict[str, object] = {
        "schema_version": QUERY_ALIAS_AUTHORITY_SCHEMA_VERSION,
        "authority_version": 1,
        "entries": entries,
    }
    data.update(updates)
    return QueryAliasAuthority.model_validate(data)


def _canonical_queries() -> tuple[tuple[str, OutputLanguage, str], ...]:
    return tuple((query.concept_id, query.language, query.query) for query in enumerate_query_vocabulary())


def test_bundled_authority_is_versioned_and_contains_independently_ratified_aliases() -> None:
    authority = load_query_alias_authority()

    assert authority.schema_version == QUERY_ALIAS_AUTHORITY_SCHEMA_VERSION
    assert authority.authority_version == 1
    assert [entry.model_dump(mode="json") for entry in authority.entries] == [
        {
            "concept_id": "modelo-130",
            "language": "es",
            "query": "autonomos",
            "canonical_query": "modelo 130",
            "status": "ratified",
            "review_reason": "Independent RAG grounding and live sweep resolve the user term to Modelo 130.",
            "reviewed_at": "2026-08-06",
        },
        {
            "concept_id": "modelo-303",
            "language": "es",
            "query": "autoliquidacion iva",
            "canonical_query": "modelo 303",
            "status": "ratified",
            "review_reason": "Independent RAG grounding and live sweep resolve the user term to Modelo 303.",
            "reviewed_at": "2026-08-07",
        },
    ]
    assert (
        query_alias_authority_path()
        .as_posix()
        .endswith("dev/docs/terminology/query-aliases/query-alias-authority.json")
    )


def test_authority_provenance_attests_raw_bytes_and_repository_path() -> None:
    authority = load_query_alias_authority()
    provenance = build_query_alias_authority_provenance(authority=authority)

    assert provenance.source_relpath == "dev/docs/terminology/query-aliases/query-alias-authority.json"
    assert provenance.schema_version == authority.schema_version
    assert provenance.authority_version == authority.authority_version
    assert len(provenance.source_sha256) == 64


def test_authority_provenance_rejects_a_model_that_does_not_match_raw_bytes() -> None:
    """A caller cannot pair a stale model with a fresh source digest."""
    authority = load_query_alias_authority()
    tampered = authority.model_copy(update={"authority_version": authority.authority_version + 1})

    with pytest.raises(QueryAliasAuthorityError, match="does not match"):
        build_query_alias_authority_provenance(authority=tampered)


def test_alias_must_anchor_to_an_approved_handbook_query() -> None:
    handbook = load_terminology_handbook()
    alias = _entry()

    validate_query_alias_authority(
        _authority(alias),
        handbook=handbook,
        canonical_queries=_canonical_queries(),
    )


def test_authority_rejects_noncanonical_order_and_duplicate_rows() -> None:
    first = _entry(query="zeta alias")
    second = _entry(query="alpha alias")

    with pytest.raises(ValidationError, match="canonical order"):
        _authority(first, second)

    with pytest.raises(ValidationError, match="duplicate"):
        _authority(first, first)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("schema_version", "old", "schema_version"),
        ("status", "proposed", "status"),
        ("review_reason", "too short", "review_reason"),
    ],
)
def test_authority_rejects_wrong_version_unratified_or_incomplete_rows(
    field: str,
    value: object,
    message: str,
) -> None:
    data: dict[str, object] = _entry().model_dump(mode="python")
    data[field] = value

    if field == "schema_version":
        with pytest.raises(ValidationError, match=message):
            _authority(_entry(), schema_version="old")
    else:
        with pytest.raises(ValidationError, match=message):
            QueryAliasEntry.model_validate(data)


def test_authority_rejects_unknown_or_nonapproved_concepts() -> None:
    handbook = load_terminology_handbook()
    canonical = _canonical_queries()
    unknown = _entry(concept_id="not-a-handbook-concept")
    with pytest.raises(QueryAliasAuthorityError, match="unknown concept"):
        validate_query_alias_authority(_authority(unknown), handbook=handbook, canonical_queries=canonical)

    retired = next(concept for concept in handbook.concepts if concept.lifecycle is not ConceptLifecycle.APPROVED)
    retired_alias = _entry(
        concept_id=retired.concept_id,
        canonical_query="not-current-handbook-query",
    )
    with pytest.raises(QueryAliasAuthorityError, match="non-approved"):
        validate_query_alias_authority(_authority(retired_alias), handbook=handbook, canonical_queries=canonical)


def test_authority_rejects_held_out_aliases_and_surface_collisions() -> None:
    handbook = load_terminology_handbook()
    canonical = _canonical_queries()
    alias = _entry()
    with pytest.raises(QueryAliasAuthorityError, match="held-out"):
        validate_query_alias_authority(
            _authority(alias),
            handbook=handbook,
            canonical_queries=canonical,
            held_out_queries=(alias.query,),
        )

    collision = _entry(
        query=next(query[2] for query in canonical if query[0] == "prorrata" and query[1] is OutputLanguage.ES)
    )
    with pytest.raises(QueryAliasAuthorityError, match="collides with an existing Handbook query"):
        validate_query_alias_authority(_authority(collision), handbook=handbook, canonical_queries=canonical)


def test_authority_refuses_one_query_surface_aliased_to_two_concepts() -> None:
    # The authority model's own duplicate check keys on
    # (concept_id, language, normalised query), so two entries that differ in
    # concept but normalise to the SAME query surface sort to distinct keys and
    # pass it. Only the surface-collision refusal sees them, and an ambiguous
    # alias is what makes a search query resolve to two concepts at once.
    handbook = load_terminology_handbook()
    canonical = _canonical_queries()
    first = _entry()
    other_concept, _, other_canonical = next(
        query for query in canonical if query[1] is OutputLanguage.ES and query[0] != first.concept_id
    )
    second = _entry(
        concept_id=other_concept,
        canonical_query=other_canonical,
        query=first.query.upper().replace(" ", "   "),
    )
    assert second.query != first.query

    ordered = tuple(
        sorted(
            (first, second),
            key=lambda entry: (entry.concept_id, entry.language.value, " ".join(entry.query.split()).casefold()),
        )
    )
    authority = _authority(*ordered)
    assert len(authority.entries) == 2

    with pytest.raises(QueryAliasAuthorityError, match="collides with another authority alias"):
        validate_query_alias_authority(authority, handbook=handbook, canonical_queries=canonical)


def test_authority_rejects_extra_fields_and_mutation() -> None:
    # Two unrelated claims shared one bare refusal, so a model that rejected
    # every payload would have satisfied both. Pinned to pydantic's stable
    # error TYPE rather than its prose: `extra_forbidden` proves the extra
    # key was refused and not, say, the empty entries list supplied with it.
    with pytest.raises(ValidationError, match="extra_forbidden"):
        QueryAliasAuthority.model_validate(
            {
                "schema_version": QUERY_ALIAS_AUTHORITY_SCHEMA_VERSION,
                "authority_version": 1,
                "entries": [],
                "unexpected": True,
            }
        )

    authority = _authority()
    # `frozen_instance` proves immutability held, not merely that assignment
    # raised - a field whose type rejected the value 2 would look identical.
    with pytest.raises(ValidationError, match="frozen_instance"):
        authority.authority_version = 2  # type: ignore[misc]


def test_provenance_rejects_path_escape() -> None:
    with pytest.raises(QueryAliasAuthorityError, match="inside the repository"):
        build_query_alias_authority_provenance(Path("..") / "query-alias-authority.json")
