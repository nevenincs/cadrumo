"""Strict, build-time authority for additional search query aliases.

The Handbook owns the user-facing terminology and its existing query forms.
This module owns only the separately reviewed aliases admitted to the closed
query vocabulary the sweep runs, which produces the committed relevance
mapping that boosts LEXICAL results.  It contains no embeddings, retrieval
output, or runtime search code, and never did -- it outlived the semantic tier
it was first written beside, which is retired.

Its path segment and ``schema_version`` name what the artefact is rather than
the tier it was authored next to. The rename is atomic across the loader, the
committed JSON and the tests, so no reader ever sees the retired name.
"""

from __future__ import annotations

import json
import unicodedata
from collections.abc import Iterable
from datetime import date
from hashlib import sha256
from pathlib import Path
from typing import Annotated, Final, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, PositiveInt, StringConstraints, field_validator, model_validator

from cadrumo.core.concept_lifecycle import ConceptLifecycle
from cadrumo.core.external_constants import OutputLanguage

from ..._paths import REPO_ROOT, UTF_8
from ..terminology_handbook import TerminologyHandbook
from ..terminology_handbook.errors import TerminologyLoadError

__all__ = [
    "QUERY_ALIAS_AUTHORITY_RELPATH",
    "QUERY_ALIAS_AUTHORITY_SCHEMA_VERSION",
    "QueryAliasAuthority",
    "QueryAliasAuthorityError",
    "QueryAliasAuthorityProvenance",
    "QueryAliasEntry",
    "build_query_alias_authority_provenance",
    "load_query_alias_authority",
    "query_alias_authority_path",
    "validate_query_alias_authority",
]

QUERY_ALIAS_AUTHORITY_SCHEMA_VERSION: Final = "cadrumo.docs-search.query-aliases.v1"
QUERY_ALIAS_AUTHORITY_RELPATH: Final[Path] = Path(
    "dev",
    "docs",
    "terminology",
    "query-aliases",
    "query-alias-authority.json",
)

_REPO_ROOT = REPO_ROOT
_UTF_8: Final[str] = UTF_8
_ConceptId = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=64)]
_QueryText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)]
_Reason = Annotated[str, StringConstraints(strip_whitespace=True, min_length=12, max_length=800)]
_Sha256 = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
_RepositoryRelativePath = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=512)]


class QueryAliasAuthorityError(TerminologyLoadError):
    """Raised when the committed alias authority is unusable."""


class QueryAliasEntry(BaseModel):
    """One independently reviewed alias admitted to the closed vocabulary."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    concept_id: _ConceptId
    language: OutputLanguage
    query: _QueryText
    canonical_query: _QueryText
    status: Literal["ratified"]
    review_reason: _Reason
    reviewed_at: date

    @field_validator("language", mode="before")
    @classmethod
    def _parse_language(cls, value: object) -> object:
        if isinstance(value, OutputLanguage):
            return value
        if isinstance(value, str):
            return OutputLanguage(value)
        return value

    @field_validator("reviewed_at", mode="before")
    @classmethod
    def _parse_reviewed_at(cls, value: object) -> object:
        if isinstance(value, date):
            return value
        if isinstance(value, str):
            return date.fromisoformat(value)
        return value


class QueryAliasAuthority(BaseModel):
    """Versioned, ratified-only authority for additional search-query aliases."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    schema_version: Literal["cadrumo.docs-search.query-aliases.v1"]
    authority_version: PositiveInt
    entries: tuple[QueryAliasEntry, ...] = Field(default=())

    @field_validator("entries", mode="before")
    @classmethod
    def _parse_entries(cls, value: object) -> object:
        if isinstance(value, list):
            items = cast(list[object], value)
            return tuple(QueryAliasEntry.model_validate(item) for item in items)
        return value

    @model_validator(mode="after")
    def _require_canonical_order_and_unique_aliases(self) -> QueryAliasAuthority:
        keys = tuple(_entry_sort_key(entry) for entry in self.entries)
        if len(keys) != len(set(keys)):
            raise ValueError("query alias authority contains duplicate entries")
        if keys != tuple(sorted(keys)):
            raise ValueError("query alias authority entries are not in canonical order")
        return self


class QueryAliasAuthorityProvenance(BaseModel):
    """Raw-byte identity of the committed alias authority."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    source_relpath: _RepositoryRelativePath
    schema_version: Literal["cadrumo.docs-search.query-aliases.v1"]
    authority_version: PositiveInt
    source_sha256: _Sha256

    @field_validator("source_relpath")
    @classmethod
    def _require_repository_relative_path(cls, value: str) -> str:
        return _normalise_relative_path(value)


def query_alias_authority_path() -> Path:
    """Return the dev-local query/alias authority path.

    A reviewed build-time alias vocabulary read by this harness and by no
    runtime consumer - so it lives beside the harness under ``dev/`` rather
    than in the shipped ``_data`` tree.
    """
    return _REPO_ROOT / QUERY_ALIAS_AUTHORITY_RELPATH


def load_query_alias_authority(path: Path | None = None) -> QueryAliasAuthority:
    """Load and validate the committed alias authority from raw JSON."""
    target = path if path is not None else query_alias_authority_path()
    try:
        raw = target.read_bytes()
    except OSError as exc:
        raise QueryAliasAuthorityError(f"{target}: query alias authority cannot be read: {exc}") from exc
    _repository_relative_path(_REPO_ROOT, target)
    try:
        payload = json.loads(raw.decode(_UTF_8))
        return QueryAliasAuthority.model_validate(payload)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise QueryAliasAuthorityError(f"{target}: query alias authority is invalid: {exc}") from exc


def build_query_alias_authority_provenance(
    path: Path | None = None,
    *,
    authority: QueryAliasAuthority | None = None,
) -> QueryAliasAuthorityProvenance:
    """Build raw-byte source identity for the committed authority."""
    target = path if path is not None else query_alias_authority_path()
    relative = _repository_relative_path(_REPO_ROOT, target)
    try:
        raw = target.read_bytes()
    except OSError as exc:
        raise QueryAliasAuthorityError(f"{target}: query alias authority cannot be read: {exc}") from exc
    loaded = load_query_alias_authority(target)
    if authority is not None and authority != loaded:
        raise QueryAliasAuthorityError(
            f"{target}: supplied query alias authority does not match its raw committed bytes"
        )
    resolved = loaded
    return QueryAliasAuthorityProvenance(
        source_relpath=relative,
        schema_version=resolved.schema_version,
        authority_version=resolved.authority_version,
        source_sha256=sha256(raw).hexdigest(),
    )


def validate_query_alias_authority(
    authority: QueryAliasAuthority,
    *,
    handbook: TerminologyHandbook,
    canonical_queries: Iterable[tuple[str, OutputLanguage, str]],
    held_out_queries: Iterable[str] = (),
) -> None:
    """Validate aliases against approved Handbook concepts and query forms.

    ``canonical_queries`` is supplied by the existing sweep enumerator rather
    than recreated here.  That keeps one owner for Handbook query enumeration
    and avoids an import cycle when the sweep later consumes this authority.
    """
    if type(authority) is not QueryAliasAuthority:
        raise QueryAliasAuthorityError("Rung-2 query alias authority must be the validated authority model")
    if authority.schema_version != QUERY_ALIAS_AUTHORITY_SCHEMA_VERSION:
        raise QueryAliasAuthorityError("Rung-2 query alias authority has an unsupported schema version")

    canonical = tuple(canonical_queries)
    canonical_keys = {(_normalise_query(query), language, concept_id) for concept_id, language, query in canonical}
    existing_surface_keys = {_normalise_query(query) for _, _, query in canonical}
    held_out = {_normalise_query(query) for query in held_out_queries}
    seen_surface_keys: set[str] = set()

    for entry in authority.entries:
        concept = handbook.by_id.get(entry.concept_id)
        if concept is None:
            raise QueryAliasAuthorityError(f"alias {entry.query!r} names unknown concept {entry.concept_id!r}")
        if concept.lifecycle is not ConceptLifecycle.APPROVED:
            raise QueryAliasAuthorityError(f"alias {entry.query!r} names non-approved concept {entry.concept_id!r}")
        canonical_key = (_normalise_query(entry.canonical_query), entry.language, entry.concept_id)
        if canonical_key not in canonical_keys:
            raise QueryAliasAuthorityError(
                f"alias {entry.query!r} has no current Handbook canonical query for "
                f"{entry.concept_id}:{entry.language.value}"
            )
        surface_key = _normalise_query(entry.query)
        if surface_key in existing_surface_keys:
            raise QueryAliasAuthorityError(f"alias {entry.query!r} collides with an existing Handbook query")
        if surface_key in seen_surface_keys:
            raise QueryAliasAuthorityError(f"alias {entry.query!r} collides with another authority alias")
        if _normalise_query(entry.query) in held_out:
            raise QueryAliasAuthorityError(f"alias {entry.query!r} is present in the held-out evaluation corpus")
        seen_surface_keys.add(surface_key)


def _entry_sort_key(entry: QueryAliasEntry) -> tuple[str, str, str]:
    return (entry.concept_id, entry.language.value, _normalise_query(entry.query))


def _normalise_query(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).split()).casefold()


def _normalise_relative_path(value: str) -> str:
    normalised = value.replace("\\", "/")
    if normalised.startswith("/") or (len(normalised) >= 2 and normalised[0].isalpha() and normalised[1] == ":"):
        raise ValueError("source_relpath must be repository-relative")
    parts = normalised.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise ValueError("source_relpath must not contain empty, '.' or '..' path segments")
    return normalised


def _repository_relative_path(root: Path, source: Path) -> str:
    try:
        relative = source.resolve().relative_to(root.resolve()).as_posix()
    except ValueError as exc:
        raise QueryAliasAuthorityError(
            f"the query alias authority must be inside the repository root: {source}"
        ) from exc
    try:
        return _normalise_relative_path(relative)
    except ValueError as exc:
        raise QueryAliasAuthorityError(str(exc)) from exc
