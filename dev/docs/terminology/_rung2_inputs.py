"""Bind Rung-2 inputs to the project's existing search authorities.

The compiler itself remains model-agnostic.  This module supplies the one
approved input assembly for a future dev-box run:

* the committed, laundered sweep is the query-term authority;
* the Handbook enumeration proves every sweep row is still shippable;
* canonical matrix/query-token vocabularies are derived from those rows; and
* the record manifest source is the same unified projection Pagefind injects.

No provider is imported, no RAG request is made, and no artifact is written by
this module.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Final

from ..terminology_handbook import load_terminology_handbook
from ._miss_rate import load_committed_relevance, load_held_out_query_set
from ._rung2_provenance import Rung2InputProvenance, build_rung2_input_provenance
from ._rung2_query_authority import (
    QUERY_ALIAS_AUTHORITY_RELPATH,
    QueryAliasAuthorityProvenance,
    Rung2QueryAliasAuthority,
    build_query_alias_authority_provenance,
    load_query_alias_authority,
    validate_query_alias_authority,
)
from ._static_matrix import (
    MatrixCompilationError,
    canonical_query_tokens,
    canonical_vocabulary,
    query_token_fingerprint,
    vocabulary_fingerprint,
)
from ._sweep import SweepResult, enumerate_query_vocabulary
from ._unified_record import SearchRecord

__all__ = [
    "QueryAliasAuthorityProvenance",
    "Rung2CompilationInputs",
    "Rung2InputError",
    "Rung2InputProvenance",
    "Rung2QueryAliasAuthority",
    "build_rung2_compilation_inputs",
]

_REPO_ROOT = Path(__file__).resolve().parents[3]
_RELEVANCE_RELPATH: Final[Path] = Path(
    "src",
    "cadrumo",
    "_data",
    "terminology",
    "relevance",
    "relevance.json",
)


class Rung2InputError(MatrixCompilationError):
    """Raised when authoritative Rung-2 input assembly is incomplete."""


@dataclass(frozen=True)
class Rung2CompilationInputs:
    """Validated source inputs ready for the provider-backed compiler."""

    vocabulary: tuple[str, ...]
    query_tokens: tuple[str, ...]
    sweep: SweepResult
    query_alias_authority: Rung2QueryAliasAuthority
    records: tuple[SearchRecord, ...]
    vocabulary_sha256: str
    query_token_sha256: str
    provenance: Rung2InputProvenance

    def __post_init__(self) -> None:
        """Keep the assembled source identity internally self-consistent."""
        if type(self.sweep) is not SweepResult:
            raise Rung2InputError("Rung-2 compilation inputs must carry a validated SweepResult")
        if type(self.provenance) is not Rung2InputProvenance:
            raise Rung2InputError("Rung-2 compilation inputs must carry validated input provenance")
        if type(self.query_alias_authority) is not Rung2QueryAliasAuthority:
            raise Rung2InputError("Rung-2 compilation inputs must carry the validated query alias authority")
        if type(self.records) is not tuple or any(type(record) is not SearchRecord for record in self.records):
            raise Rung2InputError("Rung-2 compilation inputs must carry authoritative SearchRecord instances")
        if not self.records:
            raise Rung2InputError("Rung-2 compilation inputs cannot have an empty record projection")
        if self.sweep.query_count != len(self.sweep.mappings):
            raise Rung2InputError("Rung-2 compilation inputs carry an inconsistent sweep query count")
        if self.sweep.failed_query_count:
            raise Rung2InputError("Rung-2 compilation inputs cannot carry a degraded sweep")
        try:
            canonical_terms = canonical_vocabulary(self.vocabulary)
            canonical_tokens = canonical_query_tokens(self.query_tokens)
            sweep_terms = canonical_vocabulary(mapping.query for mapping in self.sweep.mappings)
            sweep_tokens = canonical_query_tokens(mapping.query for mapping in self.sweep.mappings)
        except MatrixCompilationError as exc:
            raise Rung2InputError(f"Rung-2 compilation inputs are not canonical: {exc}") from exc
        if canonical_terms != self.vocabulary or canonical_tokens != self.query_tokens:
            raise Rung2InputError("Rung-2 compilation inputs must retain canonical vocabulary order")
        if sweep_terms != self.vocabulary:
            raise Rung2InputError("Rung-2 vocabulary must be derived from the committed sweep mappings")
        if sweep_tokens != self.query_tokens:
            raise Rung2InputError("Rung-2 query tokens must be derived from the committed sweep mappings")
        if self.vocabulary_sha256 != vocabulary_fingerprint(canonical_terms):
            raise Rung2InputError("Rung-2 vocabulary fingerprint does not match the assembled vocabulary")
        if self.query_token_sha256 != query_token_fingerprint(canonical_tokens):
            raise Rung2InputError("Rung-2 query-token fingerprint does not match the assembled query tokens")
        if (
            self.provenance.vocabulary_sha256 != self.vocabulary_sha256
            or self.provenance.query_token_sha256 != self.query_token_sha256
        ):
            raise Rung2InputError("Rung-2 input provenance fingerprints do not match the assembled inputs")


def build_rung2_compilation_inputs(
    repo_root: Path | None = None,
    *,
    relevance_path: Path | None = None,
) -> Rung2CompilationInputs:
    """Assemble canonical sweep and Pagefind-projection inputs without runtime RAG.

    The committed relevance file is intentionally loaded rather than regenerated:
    a live sweep is a separate operator action and the bundle compiler must not
    quietly change the shipped relevance authority.  The current Handbook is
    checked against every mapping row so stale or unratified query material fails
    closed before a provider is called.
    """
    root = _require_repo_root(repo_root)
    resolved_relevance = relevance_path if relevance_path is not None else root / _RELEVANCE_RELPATH
    resolved_alias_authority = root / QUERY_ALIAS_AUTHORITY_RELPATH
    source_relpath = _repository_relative_source_path(root, resolved_relevance)
    try:
        alias_authority = load_query_alias_authority(resolved_alias_authority)
        handbook = load_terminology_handbook()
        base_authority = alias_authority.model_copy(update={"entries": ()})
        base_queries = enumerate_query_vocabulary(handbook, query_alias_authority=base_authority)
        validate_query_alias_authority(
            alias_authority,
            handbook=handbook,
            canonical_queries=((query.concept_id, query.language, query.query) for query in base_queries),
            held_out_queries=(case.query for case in load_held_out_query_set().cases),
        )
    except (OSError, ValueError) as exc:
        raise Rung2InputError(
            f"cannot load or validate the committed Rung-2 query alias authority {resolved_alias_authority}: {exc}"
        ) from exc
    try:
        sweep = load_committed_relevance(resolved_relevance)
    except (OSError, ValueError) as exc:
        raise Rung2InputError(f"cannot load committed Rung-2 relevance data {resolved_relevance}: {exc}") from exc
    _require_usable_sweep(sweep)
    _require_current_handbook_vocabulary(sweep, alias_authority)

    try:
        vocabulary = canonical_vocabulary(mapping.query for mapping in sweep.mappings)
        query_tokens = canonical_query_tokens(mapping.query for mapping in sweep.mappings)
    except MatrixCompilationError as exc:
        raise Rung2InputError(f"committed sweep cannot form canonical Rung-2 vocabulary: {exc}") from exc

    # The import is local to keep the terminology package facade independent of
    # Pagefind's optional build module during normal source discovery.
    from ..pagefind_inject import materialise_search_records

    projection = materialise_search_records(root)
    if projection.casillas == 0:
        raise Rung2InputError(
            "the authoritative Pagefind record projection is incomplete because the casilla projection is empty"
        )
    if projection.cli_skipped_reason is not None:
        raise Rung2InputError(
            "the authoritative Pagefind record projection is incomplete because "
            f"the CLI projection was skipped: {projection.cli_skipped_reason}"
        )
    records = tuple(projection.records)
    if not records:
        raise Rung2InputError("the authoritative Pagefind record projection is empty")

    try:
        alias_provenance = build_query_alias_authority_provenance(
            resolved_alias_authority,
            authority=alias_authority,
        )
        provenance = build_rung2_input_provenance(
            source_relpath=source_relpath,
            source_bytes=resolved_relevance.read_bytes(),
            vocabulary=vocabulary,
            query_tokens=query_tokens,
            query_alias_authority=alias_provenance,
        )
    except (OSError, ValueError, TypeError) as exc:
        raise Rung2InputError(f"cannot derive Rung-2 input provenance from {resolved_relevance}: {exc}") from exc

    return Rung2CompilationInputs(
        vocabulary=vocabulary,
        query_tokens=query_tokens,
        sweep=sweep,
        query_alias_authority=alias_authority,
        records=records,
        vocabulary_sha256=vocabulary_fingerprint(vocabulary),
        query_token_sha256=query_token_fingerprint(query_tokens),
        provenance=provenance,
    )


def _require_repo_root(repo_root: object | None) -> Path:
    """Require an existing source checkout root for authoritative inputs."""
    candidate: object = _REPO_ROOT if repo_root is None else repo_root
    if not isinstance(candidate, Path) or not candidate.is_dir():
        raise Rung2InputError(f"Rung-2 repo_root must be an existing pathlib.Path: {candidate!r}")
    return candidate


def _repository_relative_source_path(root: Path, source: Path) -> str:
    """Return the canonical repository-relative identity of the relevance source."""
    try:
        return source.resolve().relative_to(root.resolve()).as_posix()
    except ValueError as exc:
        raise Rung2InputError(
            f"the authoritative Rung-2 relevance source must be inside the repository root: {source}"
        ) from exc


def _require_usable_sweep(sweep: SweepResult) -> None:
    """Reject partial or empty relevance data before any matrix work."""
    if not sweep.mappings:
        raise Rung2InputError("the committed Rung-2 sweep has no mappings")
    if sweep.query_count != len(sweep.mappings):
        raise Rung2InputError("the committed Rung-2 sweep query_count disagrees with its mappings")
    if sweep.failed_query_count:
        raise Rung2InputError("the committed Rung-2 sweep records failed queries")


def _require_current_handbook_vocabulary(
    sweep: SweepResult,
    query_alias_authority: Rung2QueryAliasAuthority,
) -> None:
    """Reject committed rows no longer admitted by the current Handbook."""
    eligible = {
        (query.concept_id, query.query.casefold(), query.language)
        for query in enumerate_query_vocabulary(query_alias_authority=query_alias_authority)
    }
    actual = {(mapping.concept_id, mapping.query.casefold(), mapping.language) for mapping in sweep.mappings}
    if len(actual) != len(sweep.mappings):
        raise Rung2InputError("committed Rung-2 sweep contains duplicate Handbook query rows")
    stale = [
        mapping.query
        for mapping in sweep.mappings
        if (mapping.concept_id, mapping.query.casefold(), mapping.language) not in eligible
    ]
    if stale:
        raise Rung2InputError(
            "committed Rung-2 sweep contains query rows absent from the current Handbook: " + repr(stale[0])
        )
    missing = eligible - actual
    if missing:
        concept_id, query, language = sorted(missing, key=lambda item: (item[0], item[1], item[2].value))[0]
        raise Rung2InputError(
            f"committed Rung-2 sweep is missing a current Handbook query row: {concept_id}:{query}:{language.value}"
        )
