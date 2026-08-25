"""Chunk-to-target resolution map: raw RAG hits to typed linkable targets.

The build-time RAG sweep returns raw chunk hits -- a source file path, a line
range, a relevance score. Output wrangling is a typed transformation layer,
not ad-hoc filtering: each hit is resolved, by its path, to a typed, linkable
target across the five grounding surfaces the operator named: modelo
casillas, the CLI surface, generated legal-reference pages with BOE provenance,
the codebase API reference, and the built docs pages. A hit with no resolvable
target is DROPPED and REPORTED (a typed dropped-hit report), never shipped
half-mapped.

The five resolution rules (by source path):

* ``src/cadrumo/_data/registry/.../casillas/*.toml`` -> the individual
  :class:`~dev.docs.terminology._search_record.CasillaSearchRecord` named by
  the hit's source section (the CASILLA grounding surface). A line range that
  is ambiguous or cannot be read is dropped rather than mapped to a namespace
  representative.
* a Disenos de Registro source workbook or PDF
  (``.../disenos_registro/.../*.{xlsx,xls,pdf}``, indexed through the
  preprocess-hook rules) -> an individual casilla only when the hit carries
  such a locator; a modelo-only source path is not enough to fabricate one.
* a normatives source page (``.../normatives/.../*.html``, hook-indexed) or a
  legal catalogue TOML (``.../registry/aeat/legal/*.toml``) -> the generated
  legal-reference page/anchor target, resolved through the same projection and
  renderer authority as the injected LEGAL records; the BOE permalink remains
  typed destination provenance.
* ``src/cadrumo/**/*.py`` -> the generated API stub
  (``docs/api/cadrumo.<dotted.module>.html`` -- the CODEBASE grounding surface).
* ``docs/**/*.md`` / ``*.rst`` -> the built page anchor (the DOCS surface).
* a CLI module path -> the generated CLI-reference page (the CLI surface),
  resolved against the projected CLI records.

The registry lookup goes through ``ValidatedRegistryAuthority`` /
``bundled_authority()`` (never a raw TOML re-parse, per
``aeat-registry-authority-flow``). Legal hits use the generated legal-reference
projection for their site-relative target while carrying the BOE permalink as
typed provenance (``aeat-calculation-grounding``).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import PurePosixPath
from typing import TYPE_CHECKING, Final

from pydantic import BaseModel, ConfigDict, Field

from cadrumo.core.external_constants import OutputLanguage
from cadrumo.domain.calculations.registry.authority import (
    ValidatedRegistryAuthority,
    bundled_authority,
)

from ..._paths import REPO_ROOT, UTF_8
from ._casilla_projection import project_casilla_search_records
from ._concept_cards import ConceptCardRecord
from ._legal_projection import project_legal_search_records
from ._search_record import SearchRecordKind
from ._unified_record import SearchRecord, to_search_record

if TYPE_CHECKING:
    from ..pagefind_inject import SearchRecordProjection

# Dev tooling runs from a source checkout by definition, so it owns its own
# repo-root anchor. Production code has no repository concept and must never
# export one (see cadrumo.core._config_state_root for the runtime data root).
_REPO_ROOT = REPO_ROOT

__all__ = [
    "ChunkHit",
    "DropReason",
    "DroppedHit",
    "GroundingSurface",
    "ResolutionResult",
    "ResolvedTarget",
    "TargetResolver",
    "resolve_chunk_hits",
]

_STRICT_FROZEN = ConfigDict(strict=True, frozen=True, extra="forbid")
_UTF_8: Final[str] = UTF_8


class GroundingSurface(StrEnum):
    """The grounding surfaces a chunk hit can resolve onto.

    The five operator-named surfaces (casilla, legal/BOE, codebase, docs, CLI)
    plus the Handbook concept surface: a sweep hit landing on a concept
    authoring fragment resolves to that concept's card, the first-class palette
    result.
    """

    CASILLA = "casilla"
    LEGAL = "legal"
    CODEBASE = "codebase"
    DOCS = "docs"
    CLI = "cli"
    CONCEPT = "concept"


class DropReason(StrEnum):
    """Why a chunk hit could not be resolved to a target."""

    #: The path matched no resolution rule (unknown source surface).
    UNKNOWN_PATH = "unknown_path"
    #: The path matched a rule but the referenced entity was not in the index
    #: (e.g. a casilla TOML for a modelo with no projected records).
    NO_TARGET_ENTITY = "no_target_entity"
    #: The path is an excluded surface (test/fixture/scratch -- never indexed).
    EXCLUDED_SURFACE = "excluded_surface"


class ChunkHit(BaseModel):
    """One raw RAG sweep hit: a source path, a line range, a relevance score."""

    model_config = _STRICT_FROZEN

    path: str = Field(min_length=1, max_length=512)
    line_start: int = Field(ge=0)
    line_end: int = Field(ge=0)
    score: float = Field(ge=0.0, le=1.0)

    @property
    def posix_path(self) -> PurePosixPath:
        """The hit path as a POSIX path (sweep paths are project-relative POSIX)."""
        return PurePosixPath(self.path.replace("\\", "/"))


class ResolvedTarget(BaseModel):
    """A chunk hit resolved to a typed, linkable target."""

    model_config = _STRICT_FROZEN

    surface: GroundingSurface
    #: The unified search record the hit resolves to (its ``target`` is the
    #: deep link, its ``ranking_weight`` is modulated by the hit score).
    record: SearchRecord
    #: The originating sweep hit, retained for provenance / auditing.
    source_hit: ChunkHit


@dataclass(frozen=True, slots=True)
class DroppedHit:
    """A chunk hit that could not be resolved -- reported, never shipped."""

    hit: ChunkHit
    reason: DropReason
    detail: str


@dataclass(frozen=True, slots=True)
class ResolutionResult:
    """The outcome of resolving a batch of chunk hits."""

    resolved: tuple[ResolvedTarget, ...]
    dropped: tuple[DroppedHit, ...] = field(default=())

    @property
    def resolved_count(self) -> int:
        """How many hits resolved to a target."""
        return len(self.resolved)

    @property
    def dropped_count(self) -> int:
        """How many hits were dropped and reported."""
        return len(self.dropped)


# ---------------------------------------------------------------------------
# Path rules
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class _CasillaSourceSection:
    """One casilla declaration and its inclusive source line span."""

    casilla_id: str
    start_line: int
    end_line: int


@dataclass(frozen=True, slots=True)
class _LegalSourceSection:
    """One legal catalogue provision and its inclusive source line span."""

    legal_id: str
    start_line: int
    end_line: int


@dataclass(frozen=True, slots=True)
class _CliSourceLocator:
    """One generated CLI command or parameter locator and its source span."""

    command_path: str
    start_line: int
    end_line: int
    #: Empty for the command-path locator; populated for one parameter line.
    option_names: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class _CliSourceLocators:
    """Parsed CLI locators together with the source file's line count."""

    line_count: int
    locators: tuple[_CliSourceLocator, ...]


_CONCEPT_TOML_RE = re.compile(
    r"^src/cadrumo/_data/terminology/concepts/(?P<concept_id>[^/]+)\.toml$",
)
_CASILLA_PATH_RE = re.compile(
    r"^src/cadrumo/_data/registry/aeat/modelos/(?P<modelo>[^/]+)/revisions/[^/]+/casillas/.+\.toml$",
)
# Corpus hits arrive under SOURCE file paths: the dev index reads the corpus
# through the .vaultragpreprocess.toml hook rules, and the extraction sidecars
# are .vaultragignore-excluded (they remain the committed product payload).
_DISENO_PATH_RE = re.compile(
    r"^src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_(?P<modelo>[^/]+)/.+\.(?:xlsx|xls|pdf)$",
)
_NORMATIVES_PATH_RE = re.compile(
    r"^src/cadrumo/_data/corpus/normatives/.+\.html$",
)
_LEGAL_TOML_RE = re.compile(
    r"^src/cadrumo/_data/registry/aeat/legal/[^/]+\.toml$",
)
_CLI_REFERENCE_RE = re.compile(
    r"^docs/cli/(?P<page>.+)\.rst$",
)
_CLI_COMMAND_PATH_RE = re.compile(r"^\*\*Command path:\*\* ``(?P<path>[^`]+)``\s*$")
_CLI_PARAMETERS_HEADER_RE = re.compile(r"^\*\*Parameters\*\*\s*$")
_CLI_OUTPUT_SCHEMA_HEADER_RE = re.compile(r"^\*\*Output schema\*\*\s*$")
_CLI_PARAMETER_LINE_RE = re.compile(r"^\s*``[^`]+``(?:\s*,\s*``[^`]+``)*\s*$")
_CLI_INLINE_CODE_RE = re.compile(r"``([^`]+)``")
_CODE_MODULE_RE = re.compile(
    r"^src/cadrumo/.+\.py$",
)
_DOCS_PAGE_RE = re.compile(
    r"^docs/(?P<rel>.+)\.(?:md|rst)$",
)
_CASILLA_TABLE_RE = re.compile(
    r'^\[\[revisions\.(?:"[^"]+"|[A-Za-z0-9_-]+)\.casillas\]\]\s*$',
)
_CASILLA_ID_RE = re.compile(r'^\s*id\s*=\s*"(?P<id>[^"]+)"\s*$')

#: Surfaces that are never indexed (tests, fixtures, scratch). A hit on one is
#: dropped as EXCLUDED, distinct from an UNKNOWN_PATH so the report is precise.
_EXCLUDED_SEGMENTS: frozenset[str] = frozenset({"tests", "test", "fixtures", "scratch", "__pycache__"})


class TargetResolver:
    """Resolves chunk hits to typed targets across the five grounding surfaces.

    Holds the projected casilla records (indexed by modelo), the legal
    catalogue's ``corpus_ref`` reverse index, and the generated legal search
    records, all built once so a batch of hits resolves without re-projecting
    or re-parsing per hit.
    """

    def __init__(
        self,
        authority: ValidatedRegistryAuthority | None = None,
        *,
        search_record_projection: SearchRecordProjection | None = None,
    ) -> None:
        """Build the resolver's indices from the validated authority.

        Args:
            authority: The registry authority to read through; defaults to the
                bundled authority. Injectable so a test can drive a narrowed
                authority deterministically.
            search_record_projection: The complete Pagefind/Rung-2 projection
                to use for CLI records. Supplying it lets a caller share one
                authoritative projection between resolution and target
                filtering; when omitted, the projection is materialised here
                for backwards-compatible standalone resolver construction.
        """
        self._authority = authority if authority is not None else bundled_authority()
        records, _stats = project_casilla_search_records(self._authority)
        # Index casilla records by modelo for the casilla / diseno rules.
        self._casillas_by_modelo: dict[str, tuple[SearchRecord, ...]] = {}
        for record in records:
            unified = to_search_record(record)
            modelo = record.modelo.value
            self._casillas_by_modelo.setdefault(modelo, ())
            self._casillas_by_modelo[modelo] = (*self._casillas_by_modelo[modelo], unified)
        # Index the same generated legal-reference projection that the
        # Pagefind injector emits. Its target is the renderer's site-relative
        # page/anchor; BOE remains typed provenance on the unified record.
        self._legal_by_id: dict[str, SearchRecord] = {
            record.legal_id: to_search_record(record) for record in project_legal_search_records(_REPO_ROOT)
        }
        # Index the exact unified records consumed by Pagefind injection. A
        # CLI family source page may resolve only to an actually emitted
        # record; the resolver must not invent a family-level record.
        if search_record_projection is None:
            from ..pagefind_inject import materialise_search_records

            cli_projection = materialise_search_records(_REPO_ROOT)
        else:
            cli_projection = search_record_projection
        self._cli_records_by_locator: dict[tuple[str, tuple[str, ...]], tuple[SearchRecord, ...]] = {}
        for record in cli_projection.records:
            if record.kind is not SearchRecordKind.CLI:
                continue
            command_path = record.metadata.command_path
            if command_path is None:
                continue
            locator = (command_path, record.metadata.option_names)
            locator_records = self._cli_records_by_locator.get(locator, ())
            self._cli_records_by_locator[locator] = (*locator_records, record)
        self._cli_projection_skipped_reason = cli_projection.cli_skipped_reason

        # Reverse index: a normatives corpus html path -> every legal id whose
        # corpus_ref points at it. The anchor is not present in a source hit,
        # so it is removed only from the lookup key, never used to discard
        # competing legal ids.
        self._legal_by_corpus_path: dict[str, tuple[str, ...]] = {}
        for legal_id, entry in self._authority.catalogues.legal.items():
            corpus_ref = getattr(entry, "corpus_ref", None)
            if corpus_ref:
                corpus_path = corpus_ref.split("#", 1)[0]
                legal_ids = self._legal_by_corpus_path.get(corpus_path, ())
                self._legal_by_corpus_path[corpus_path] = (*legal_ids, legal_id)
        # The set of legal ids the authority knows, for cross-checking a
        # file-declared id against the validated catalogue.
        self._known_legal_ids: frozenset[str] = frozenset(self._authority.catalogues.legal)
        # Index the Handbook concept cards by concept_id (the fragment stem), so
        # a sweep hit on a concept authoring fragment resolves to its card. Only
        # APPROVED concepts are indexed: a draft concept is absent from the
        # approved-only generated glossary, so its
        # ``#term-<id>`` deep link would be dead. Resolving a RAG hit on a draft
        # fragment (or seeding a draft card) would ship a dead link, so drafts
        # are excluded here exactly as they are from the Pagefind injection.
        self._concept_by_id: dict[str, SearchRecord] = {}
        for card in _load_concept_cards():
            if not card.is_approved:
                continue
            self._concept_by_id[card.concept_id] = to_search_record(card)

    def concept_record(self, concept_id: str) -> SearchRecord | None:
        """Return the unified concept-card record for ``concept_id``, if enrolled.

        The concept card is the first-class palette result. The sweep
        uses this to seed a query's originating concept card as a guaranteed
        target: a closed-vocabulary term is, by construction, a label *of* that
        concept, so its card is the canonical top result regardless of whether
        RAG re-discovered the concept's own authoring fragment.
        """
        return self._concept_by_id.get(concept_id)

    def resolve(self, hit: ChunkHit) -> ResolvedTarget | DroppedHit:
        """Resolve one chunk hit to a typed target, or drop and report it."""
        path = hit.posix_path.as_posix()
        if self._is_excluded(hit):
            return DroppedHit(hit=hit, reason=DropReason.EXCLUDED_SURFACE, detail=f"excluded surface: {path}")

        concept_match = _CONCEPT_TOML_RE.match(path)
        if concept_match:
            return self._resolve_concept(hit, concept_match.group("concept_id"))

        casilla_match = _CASILLA_PATH_RE.match(path) or _DISENO_PATH_RE.match(path)
        if casilla_match:
            return self._resolve_casilla(hit, casilla_match.group("modelo"))

        if _NORMATIVES_PATH_RE.match(path):
            return self._resolve_normatives(hit)

        if _LEGAL_TOML_RE.match(path):
            return self._resolve_legal_toml(hit)

        if _CODE_MODULE_RE.match(path):
            return self._resolve_codebase(hit, surface=GroundingSurface.CODEBASE)

        cli_ref_match = _CLI_REFERENCE_RE.match(path)
        if cli_ref_match:
            return self._resolve_cli_reference(hit, cli_ref_match.group("page"))

        docs_match = _DOCS_PAGE_RE.match(path)
        if docs_match:
            return self._resolve_docs(hit, docs_match.group("rel"))

        return DroppedHit(hit=hit, reason=DropReason.UNKNOWN_PATH, detail=f"no resolution rule for {path}")

    def _is_excluded(self, hit: ChunkHit) -> bool:
        return any(part in _EXCLUDED_SEGMENTS for part in hit.posix_path.parts)

    def _resolve_concept(self, hit: ChunkHit, concept_id: str) -> ResolvedTarget | DroppedHit:
        record = self._concept_by_id.get(concept_id)
        if record is None:
            return DroppedHit(
                hit=hit,
                reason=DropReason.NO_TARGET_ENTITY,
                detail=f"no concept card for fragment {concept_id!r}",
            )
        reweighted = record.model_copy(update={"ranking_weight": _reweight(SearchRecordKind.CONCEPT, hit.score)})
        return ResolvedTarget(surface=GroundingSurface.CONCEPT, record=reweighted, source_hit=hit)

    def _resolve_casilla(self, hit: ChunkHit, modelo: str) -> ResolvedTarget | DroppedHit:
        records = self._casillas_by_modelo.get(modelo)
        if not records:
            return DroppedHit(
                hit=hit,
                reason=DropReason.NO_TARGET_ENTITY,
                detail=f"no projected casilla records for modelo {modelo!r}",
            )

        path = hit.posix_path.as_posix()
        if not path.endswith(".toml"):
            return DroppedHit(
                hit=hit,
                reason=DropReason.NO_TARGET_ENTITY,
                detail=(
                    f"casilla source {path!r} identifies modelo {modelo!r} only; "
                    "no individual casilla locator is available"
                ),
            )
        if hit.line_start < 1 or hit.line_end < hit.line_start:
            return DroppedHit(
                hit=hit,
                reason=DropReason.NO_TARGET_ENTITY,
                detail=f"invalid casilla source line range {hit.line_start}-{hit.line_end} for {path!r}",
            )

        sections = _read_casilla_source_sections(path)
        if sections is None:
            return DroppedHit(
                hit=hit,
                reason=DropReason.NO_TARGET_ENTITY,
                detail=f"cannot read casilla source {path!r} to identify an individual record",
            )
        matching = tuple(
            section for section in sections if section.start_line <= hit.line_end and hit.line_start <= section.end_line
        )
        if not matching:
            return DroppedHit(
                hit=hit,
                reason=DropReason.NO_TARGET_ENTITY,
                detail=f"source lines {hit.line_start}-{hit.line_end} identify no casilla in {path!r}",
            )
        if len(matching) != 1:
            ids = ", ".join(repr(section.casilla_id) for section in matching)
            return DroppedHit(
                hit=hit,
                reason=DropReason.NO_TARGET_ENTITY,
                detail=(f"source lines {hit.line_start}-{hit.line_end} overlap multiple casillas ({ids}) in {path!r}"),
            )

        casilla_id = matching[0].casilla_id
        matching_records = tuple(record for record in records if str(record.metadata.casilla_id) == casilla_id)
        if len(matching_records) != 1:
            return DroppedHit(
                hit=hit,
                reason=DropReason.NO_TARGET_ENTITY,
                detail=(f"source casilla {casilla_id!r} for modelo {modelo!r} has no unique projected search record"),
            )

        (base,) = matching_records
        record = base.model_copy(
            update={"ranking_weight": _reweight(SearchRecordKind.CASILLA, hit.score)},
        )
        return ResolvedTarget(surface=GroundingSurface.CASILLA, record=record, source_hit=hit)

    def _resolve_normatives(self, hit: ChunkHit) -> ResolvedTarget | DroppedHit:
        # The hit path IS the origin html source (hook-indexed); reduce it to
        # the corpus/-rooted corpus_ref form the legal catalogue cites.
        path = hit.posix_path.as_posix()
        corpus_rel = _to_corpus_relative(path)
        if corpus_rel is None:
            return DroppedHit(
                hit=hit,
                reason=DropReason.NO_TARGET_ENTITY,
                detail=f"normatives source outside the corpus root: {path}",
            )
        legal_ids = self._legal_by_corpus_path.get(corpus_rel)
        if not legal_ids:
            return DroppedHit(
                hit=hit,
                reason=DropReason.NO_TARGET_ENTITY,
                detail=f"no legal catalogue entry references corpus path {corpus_rel!r}",
            )
        if len(legal_ids) != 1:
            ids = ", ".join(repr(legal_id) for legal_id in legal_ids)
            return DroppedHit(
                hit=hit,
                reason=DropReason.NO_TARGET_ENTITY,
                detail=(
                    f"normatives source path {corpus_rel!r} maps to multiple legal provisions "
                    f"({ids}); no unambiguous provision locator is available"
                ),
            )
        return self._legal_target(hit, legal_ids[0])

    def _resolve_legal_toml(self, hit: ChunkHit) -> ResolvedTarget | DroppedHit:
        path = hit.posix_path.as_posix()
        if hit.line_start < 1 or hit.line_end < hit.line_start:
            return DroppedHit(
                hit=hit,
                reason=DropReason.NO_TARGET_ENTITY,
                detail=f"invalid legal source line range {hit.line_start}-{hit.line_end} for {path!r}",
            )

        sections = _read_legal_source_sections(path)
        if sections is None:
            return DroppedHit(
                hit=hit,
                reason=DropReason.NO_TARGET_ENTITY,
                detail=f"cannot read legal source {path!r} to identify an individual provision",
            )
        matching = tuple(
            section for section in sections if section.start_line <= hit.line_end and hit.line_start <= section.end_line
        )
        if not matching:
            return DroppedHit(
                hit=hit,
                reason=DropReason.NO_TARGET_ENTITY,
                detail=f"source lines {hit.line_start}-{hit.line_end} identify no legal provision in {path!r}",
            )
        if len(matching) != 1:
            ids = ", ".join(repr(section.legal_id) for section in matching)
            return DroppedHit(
                hit=hit,
                reason=DropReason.NO_TARGET_ENTITY,
                detail=(
                    f"source lines {hit.line_start}-{hit.line_end} overlap multiple legal provisions "
                    f"({ids}) in {path!r}"
                ),
            )

        legal_id = matching[0].legal_id
        if legal_id not in self._known_legal_ids:
            return DroppedHit(
                hit=hit,
                reason=DropReason.NO_TARGET_ENTITY,
                detail=f"legal provision {legal_id!r} is not in the validated catalogue",
            )
        return self._legal_target(hit, legal_id)

    def _legal_target(self, hit: ChunkHit, legal_id: str) -> ResolvedTarget | DroppedHit:
        base = self._legal_by_id.get(legal_id)
        if base is None:
            return DroppedHit(
                hit=hit,
                reason=DropReason.NO_TARGET_ENTITY,
                detail=f"legal entry {legal_id!r} has no generated legal-reference target",
            )
        record = base.model_copy(
            update={"ranking_weight": _reweight(SearchRecordKind.LEGAL, hit.score)},
        )
        return ResolvedTarget(surface=GroundingSurface.LEGAL, record=record, source_hit=hit)

    def _resolve_codebase(self, hit: ChunkHit, *, surface: GroundingSurface) -> ResolvedTarget | DroppedHit:
        dotted = _module_to_dotted(hit.posix_path.as_posix())
        if dotted is None:
            return DroppedHit(
                hit=hit,
                reason=DropReason.NO_TARGET_ENTITY,
                detail=f"cannot derive a module name from {hit.path!r}",
            )
        from ._unified_record import RankingTier, SearchRecordMetadata

        title = dotted
        target = f"api/{dotted}.html"
        record = SearchRecord(
            id=f"code:{dotted}",
            kind=SearchRecordKind.PAGE,
            tier=RankingTier.FULLTEXT,
            title=title,
            descriptions=_plain_descriptions(dotted),
            target=target,
            ranking_weight=_reweight(SearchRecordKind.PAGE, hit.score),
            metadata=SearchRecordMetadata(),
        )
        return ResolvedTarget(surface=surface, record=record, source_hit=hit)

    def _resolve_cli_reference(self, hit: ChunkHit, page: str) -> ResolvedTarget | DroppedHit:
        """Resolve one generated CLI page only through a unique source locator.

        The generated reference page is the source evidence boundary. A
        ``Command path`` line identifies one command record; a parameter name
        line identifies one option record. A family/navigation page, an
        unbounded range, or a range spanning more than one locator is not an
        entity and therefore remains dropped.
        """
        source_path = hit.posix_path.as_posix()
        if hit.line_start < 1 or hit.line_end < hit.line_start:
            return DroppedHit(
                hit=hit,
                reason=DropReason.NO_TARGET_ENTITY,
                detail=f"invalid CLI source line range {hit.line_start}-{hit.line_end} for {source_path!r}",
            )

        expected_page = f"cli/{page}"
        locators = _read_cli_source_locators(source_path)
        if locators is None:
            return DroppedHit(
                hit=hit,
                reason=DropReason.NO_TARGET_ENTITY,
                detail=f"cannot read CLI reference source {source_path!r} to identify a command or option",
            )
        if hit.line_end > locators.line_count:
            return DroppedHit(
                hit=hit,
                reason=DropReason.NO_TARGET_ENTITY,
                detail=(
                    f"CLI source line range {hit.line_start}-{hit.line_end} exceeds the {source_path!r} "
                    f"source length of {locators.line_count} lines"
                ),
            )
        matching_locators = tuple(
            locator
            for locator in locators.locators
            if locator.start_line <= hit.line_end and hit.line_start <= locator.end_line
        )
        if not matching_locators:
            target = f"{expected_page}.html"
            detail = (
                f"source lines {hit.line_start}-{hit.line_end} identify no CLI command or option "
                f"locator in {source_path!r}; no authoritative CLI search record was emitted for exact target "
                f"{target!r}"
            )
            if self._cli_projection_skipped_reason is not None:
                detail += f" (CLI projection skipped: {self._cli_projection_skipped_reason})"
            return DroppedHit(hit=hit, reason=DropReason.NO_TARGET_ENTITY, detail=detail)
        if len(matching_locators) != 1:
            descriptions = ", ".join(
                f"{locator.command_path!r}{locator.option_names!r}" for locator in matching_locators
            )
            return DroppedHit(
                hit=hit,
                reason=DropReason.NO_TARGET_ENTITY,
                detail=(
                    f"source lines {hit.line_start}-{hit.line_end} overlap multiple CLI source locators "
                    f"({descriptions}) in {source_path!r}; no unambiguous command or option is available"
                ),
            )

        (locator,) = matching_locators
        command_path = tuple(locator.command_path.split())
        from ..cli_reference import cli_reference_page_for_command

        try:
            routed_page = cli_reference_page_for_command(command_path)
        except ValueError as exc:
            return DroppedHit(
                hit=hit,
                reason=DropReason.NO_TARGET_ENTITY,
                detail=f"CLI source locator has no valid routed page: {exc}",
            )
        if routed_page != expected_page:
            return DroppedHit(
                hit=hit,
                reason=DropReason.NO_TARGET_ENTITY,
                detail=(
                    f"CLI command {locator.command_path!r} routes to {routed_page!r}, not source page {expected_page!r}"
                ),
            )

        matching = tuple(
            record
            for record in self._cli_records_by_locator.get((locator.command_path, locator.option_names), ())
            if record.target.partition("#")[0] == f"{routed_page}.html" and record.target.partition("#")[2]
        )
        target = f"{routed_page}.html"
        if not matching:
            detail = (
                f"no authoritative CLI search record was emitted for source locator "
                f"{locator.command_path!r}{locator.option_names!r} at exact target page {target!r}"
            )
            if self._cli_projection_skipped_reason is not None:
                detail += f" (CLI projection skipped: {self._cli_projection_skipped_reason})"
            return DroppedHit(hit=hit, reason=DropReason.NO_TARGET_ENTITY, detail=detail)
        if len(matching) != 1:
            ids = ", ".join(repr(record.id) for record in matching)
            return DroppedHit(
                hit=hit,
                reason=DropReason.NO_TARGET_ENTITY,
                detail=(
                    f"multiple authoritative CLI records were emitted for source locator "
                    f"{locator.command_path!r}{locator.option_names!r} at exact target page {target!r} ({ids})"
                ),
            )
        (base,) = matching
        record = base.model_copy(
            update={"ranking_weight": _reweight(SearchRecordKind.CLI, hit.score)},
        )
        return ResolvedTarget(surface=GroundingSurface.CLI, record=record, source_hit=hit)

    def _resolve_docs(self, hit: ChunkHit, rel: str) -> ResolvedTarget:
        from ._unified_record import RankingTier, SearchRecordMetadata

        # docs/how-to/foo.md -> how-to/foo.html (the built page).
        target = f"{rel}.html"
        title = rel.rsplit("/", 1)[-1].replace("-", " ").replace("_", " ")
        record = SearchRecord(
            id=f"page:{rel}",
            kind=SearchRecordKind.PAGE,
            tier=RankingTier.FULLTEXT,
            title=title or rel,
            descriptions=_plain_descriptions(title or rel),
            target=target,
            ranking_weight=_reweight(SearchRecordKind.PAGE, hit.score),
            metadata=SearchRecordMetadata(),
        )
        return ResolvedTarget(surface=GroundingSurface.DOCS, record=record, source_hit=hit)


def resolve_chunk_hits(
    hits: tuple[ChunkHit, ...],
    *,
    authority: ValidatedRegistryAuthority | None = None,
    resolver: TargetResolver | None = None,
) -> ResolutionResult:
    """Resolve a batch of chunk hits to typed targets, dropping+reporting failures.

    Args:
        hits: The raw sweep hits to resolve.
        authority: The registry authority for the default resolver (ignored
            when ``resolver`` is given).
        resolver: A pre-built resolver (reuse across batches to avoid
            re-projecting the casilla records each call).

    Returns:
        A :class:`ResolutionResult` partitioning resolved targets from
        dropped+reported hits. A hit with no resolvable target is in
        ``dropped``, never silently mapped.
    """
    target_resolver = resolver if resolver is not None else TargetResolver(authority)
    resolved: list[ResolvedTarget] = []
    dropped: list[DroppedHit] = []
    for hit in hits:
        outcome = target_resolver.resolve(hit)
        if isinstance(outcome, ResolvedTarget):
            resolved.append(outcome)
        else:
            dropped.append(outcome)
    return ResolutionResult(resolved=tuple(resolved), dropped=tuple(dropped))


# ---------------------------------------------------------------------------
# Path / description helpers
# ---------------------------------------------------------------------------


def _reweight(kind: SearchRecordKind, score: float) -> float:
    from ._unified_record import normalise_ranking_weight

    return normalise_ranking_weight(kind, score)


def _load_concept_cards() -> tuple[ConceptCardRecord, ...]:
    from ._concept_cards import project_concept_cards

    cards, _stats = project_concept_cards()
    return cards


def _to_corpus_relative(origin_path: str) -> str | None:
    """Map a ``src/cadrumo/_data/<rest>`` path to the ``<rest>`` corpus-ref form.

    The legal catalogue's ``corpus_ref`` is rooted at ``corpus/...`` (relative
    to ``src/cadrumo/_data/``), so an origin html path under ``_data`` maps by
    stripping the ``src/cadrumo/_data/`` prefix.
    """
    prefix = "src/cadrumo/_data/"
    if not origin_path.startswith(prefix):
        return None
    return origin_path[len(prefix) :]


def _read_casilla_source_sections(project_relpath: str) -> tuple[_CasillaSourceSection, ...] | None:
    """Read casilla source section spans without becoming a registry authority.

    The validated registry remains the value and projection authority. This
    helper only reads the source text to learn which individual declaration a
    RAG line range overlaps, preserving the source-hit evidence boundary.
    """
    absolute = _REPO_ROOT / PurePosixPath(project_relpath.replace("\\", "/"))
    try:
        lines = absolute.read_text(encoding=_UTF_8).splitlines()
    except (OSError, UnicodeError):
        return None

    headers = [index for index, line in enumerate(lines) if _CASILLA_TABLE_RE.fullmatch(line)]
    sections: list[_CasillaSourceSection] = []
    for position, header_index in enumerate(headers):
        next_header = headers[position + 1] if position + 1 < len(headers) else len(lines)
        casilla_id = next(
            (
                match.group("id")
                for line in lines[header_index + 1 : next_header]
                if (match := _CASILLA_ID_RE.fullmatch(line)) is not None
            ),
            None,
        )
        if casilla_id is None:
            continue
        sections.append(
            _CasillaSourceSection(
                casilla_id=casilla_id,
                start_line=header_index + 1,
                end_line=next_header,
            ),
        )
    return tuple(sections)


def _read_cli_source_locators(project_relpath: str) -> _CliSourceLocators | None:
    """Read generated CLI command and parameter locators from one RST page.

    The CLI reference generator writes one explicit ``Command path`` line per
    leaf command and one inline-code definition line per parameter. This helper
    reads only those locator lines; the CLI projection remains the authority for
    record identity, metadata, and the emitted page/anchor target.
    """
    absolute = _REPO_ROOT / PurePosixPath(project_relpath.replace("\\", "/"))
    try:
        lines = absolute.read_text(encoding=_UTF_8).splitlines()
    except (OSError, UnicodeError):
        return None

    command_headers = [
        (index, match.group("path"))
        for index, line in enumerate(lines)
        if (match := _CLI_COMMAND_PATH_RE.fullmatch(line)) is not None
    ]
    locators: list[_CliSourceLocator] = []
    for position, (command_index, command_path) in enumerate(command_headers):
        next_command_index = command_headers[position + 1][0] if position + 1 < len(command_headers) else len(lines)
        # The command locator is deliberately only the explicit command-path
        # line. A range that also overlaps a parameter locator is ambiguous.
        locators.append(
            _CliSourceLocator(
                command_path=command_path,
                start_line=command_index + 1,
                end_line=command_index + 1,
            ),
        )

        parameters_index = next(
            (
                index
                for index in range(command_index + 1, next_command_index)
                if _CLI_PARAMETERS_HEADER_RE.fullmatch(lines[index]) is not None
            ),
            None,
        )
        if parameters_index is None:
            continue
        output_schema_index = next(
            (
                index
                for index in range(parameters_index + 1, next_command_index)
                if _CLI_OUTPUT_SCHEMA_HEADER_RE.fullmatch(lines[index]) is not None
            ),
            next_command_index,
        )
        parameter_lines = [
            (index, tuple(_CLI_INLINE_CODE_RE.findall(line)))
            for index, line in enumerate(
                lines[parameters_index + 1 : output_schema_index],
                start=parameters_index + 1,
            )
            if _CLI_PARAMETER_LINE_RE.fullmatch(line) is not None
        ]
        for parameter_position, (parameter_index, option_names) in enumerate(parameter_lines):
            next_parameter_index = (
                parameter_lines[parameter_position + 1][0]
                if parameter_position + 1 < len(parameter_lines)
                else output_schema_index
            )
            locators.append(
                _CliSourceLocator(
                    command_path=command_path,
                    start_line=parameter_index + 1,
                    end_line=next_parameter_index,
                    option_names=option_names,
                ),
            )
    return _CliSourceLocators(line_count=len(lines), locators=tuple(locators))


_LEGAL_HEADER_RE = re.compile(r'^\[legal\."(?P<id>[^"]+)"\]\s*$')
_TOML_TABLE_HEADER_RE = re.compile(r"^(?:\[\[.*\]\]|\[.*\])\s*$")


def _read_legal_source_sections(project_relpath: str) -> tuple[_LegalSourceSection, ...] | None:
    """Read legal catalogue provision spans without parsing catalogue values.

    The validated registry and generated legal-reference projection remain the
    authorities for legal identity and target metadata. This helper only reads
    source text to learn which single ``[legal."<id>"]`` declaration a RAG line
    range overlaps, preserving the source-hit evidence boundary.
    """
    absolute = _REPO_ROOT / PurePosixPath(project_relpath.replace("\\", "/"))
    try:
        lines = absolute.read_text(encoding=_UTF_8).splitlines()
    except (OSError, UnicodeError):
        return None

    table_headers = [index for index, line in enumerate(lines) if _TOML_TABLE_HEADER_RE.fullmatch(line) is not None]
    headers = [
        (index, match.group("id"))
        for index, line in enumerate(lines)
        if (match := _LEGAL_HEADER_RE.fullmatch(line)) is not None
    ]
    sections: list[_LegalSourceSection] = []
    for header_index, legal_id in headers:
        next_header = next(
            (index for index in table_headers if index > header_index),
            len(lines),
        )
        sections.append(
            _LegalSourceSection(
                legal_id=legal_id,
                start_line=header_index + 1,
                end_line=next_header,
            ),
        )
    return tuple(sections)


def _module_to_dotted(path: str) -> str | None:
    """Map ``src/cadrumo/foo/bar.py`` (or ``__init__.py``) to its dotted module name.

    Mirrors the apidocs stub-naming convention: a module file maps to
    ``cadrumo.foo.bar`` and a package ``__init__.py`` to ``cadrumo.foo`` -- the stub
    filename (and built ``docs/api/<dotted>.html`` page) is named from this.
    """
    if not path.startswith("src/cadrumo/") or not path.endswith(".py"):
        return None
    relative = path[len("src/") :]  # aeat/foo/bar.py
    parts = relative.split("/")
    if parts[-1] == "__init__.py":
        parts = parts[:-1]
    else:
        parts[-1] = parts[-1].removesuffix(".py")
    if not parts:
        return None
    return ".".join(parts)


def _plain_descriptions(text: str) -> dict[OutputLanguage, str]:
    return {OutputLanguage.ES: (text or "documentation").strip()[:240] or "documentation"}
