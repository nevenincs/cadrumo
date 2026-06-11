"""Chunk-to-target resolution map: raw RAG hits to typed linkable targets (ADR D6).

The build-time RAG sweep returns raw chunk hits -- a source file path, a line
range, a relevance score. ADR D6's "output wrangling is a typed transformation
layer, not ad-hoc filtering" sub-decision requires resolving each hit, by its
path, to a typed, linkable target across the five grounding surfaces the
operator named: modelo casillas, the CLI surface, BOE legal grounding, the
codebase API reference, and the built docs pages. A hit with no resolvable
target is DROPPED and REPORTED (a typed dropped-hit report), never shipped
half-mapped.

The five resolution rules (by source path):

* ``src/aeat/_data/registry/.../casillas/*.toml`` -> the modelo's
  :class:`~dev.docs.terminology._search_record.CasillaSearchRecord` set (the
  CASILLA grounding surface).
* a Disenos de Registro sidecar
  (``.../disenos_registro/.../*.extracted.md``) -> the modelo's casilla target
  (the Diseno is the casilla-to-field authority).
* a normatives sidecar (``.../normatives/.../*.extracted.md``) or a legal
  catalogue TOML (``.../registry/aeat/legal/*.toml``) -> the legal-grounding
  target (the BOE permalink + ``#aN`` article anchor, resolved through the
  legal catalogue's ``corpus_ref`` -- the BOE grounding surface).
* ``src/aeat/**/*.py`` -> the generated API stub
  (``docs/api/aeat.<dotted.module>.html`` -- the CODEBASE grounding surface).
* ``docs/**/*.md`` / ``*.rst`` -> the built page anchor (the DOCS surface).
* a CLI module path -> the generated CLI-reference page (the CLI surface),
  resolved against the projected CLI records.

The registry and legal lookups go through ``ValidatedRegistryAuthority`` /
``bundled_authority()`` (never a raw TOML re-parse, per
``aeat-registry-authority-flow``); the legal-grounding link carries the
permalink and corpus anchor so provenance survives into the resolved target
(``aeat-calculation-grounding``).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import PurePosixPath

from pydantic import BaseModel, ConfigDict, Field

from aeat.core.external_constants import OutputLanguage
from aeat.domain.calculations.registry import ValidatedRegistryAuthority, bundled_authority

from ._casilla_projection import project_casilla_search_records
from ._search_record import SearchRecordKind
from ._unified_record import SearchRecord, to_search_record

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


class GroundingSurface(StrEnum):
    """The five grounding surfaces a chunk hit can resolve onto (ADR D6)."""

    CASILLA = "casilla"
    LEGAL = "legal"
    CODEBASE = "codebase"
    DOCS = "docs"
    CLI = "cli"


class DropReason(StrEnum):
    """Why a chunk hit could not be resolved to a target (ADR D6)."""

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
    """A chunk hit resolved to a typed, linkable target (ADR D6)."""

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

_CASILLA_PATH_RE = re.compile(
    r"^src/aeat/_data/registry/aeat/modelos/(?P<modelo>[^/]+)/revisions/[^/]+/casillas/.+\.toml$",
)
_DISENO_PATH_RE = re.compile(
    r"^src/aeat/_data/corpus/aeat_official/disenos_registro/modelo_(?P<modelo>[^/]+)/.+\.extracted\.md$",
)
_NORMATIVES_PATH_RE = re.compile(
    r"^src/aeat/_data/corpus/normatives/.+\.extracted\.md$",
)
_LEGAL_TOML_RE = re.compile(
    r"^src/aeat/_data/registry/aeat/legal/[^/]+\.toml$",
)
_CLI_REFERENCE_RE = re.compile(
    r"^docs/cli/(?P<family>[^/]+)\.rst$",
)
_CODE_MODULE_RE = re.compile(
    r"^src/aeat/.+\.py$",
)
_DOCS_PAGE_RE = re.compile(
    r"^docs/(?P<rel>.+)\.(?:md|rst)$",
)

#: Surfaces that are never indexed (tests, fixtures, scratch). A hit on one is
#: dropped as EXCLUDED, distinct from an UNKNOWN_PATH so the report is precise.
_EXCLUDED_SEGMENTS: frozenset[str] = frozenset({"tests", "test", "fixtures", "scratch", "__pycache__"})


class TargetResolver:
    """Resolves chunk hits to typed targets across the five grounding surfaces.

    Holds the projected casilla records (indexed by modelo) and the legal
    catalogue's ``corpus_ref`` reverse index, both built once from the
    validated authority, so a batch of hits resolves without re-projecting or
    re-parsing per hit.
    """

    def __init__(self, authority: ValidatedRegistryAuthority | None = None) -> None:
        """Build the resolver's indices from the validated authority.

        Args:
            authority: The registry authority to read through; defaults to the
                bundled authority. Injectable so a test can drive a narrowed
                authority deterministically.
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
        # Reverse index: a normatives corpus html path -> the legal id whose
        # corpus_ref points at it (carries the BOE permalink + #aN anchor).
        self._legal_by_corpus_path: dict[str, str] = {}
        for legal_id, entry in self._authority.catalogues.legal.items():
            corpus_ref = getattr(entry, "corpus_ref", None)
            if corpus_ref:
                corpus_path = corpus_ref.split("#", 1)[0]
                self._legal_by_corpus_path.setdefault(corpus_path, legal_id)
        # The set of legal ids the authority knows, for cross-checking a
        # file-declared id against the validated catalogue.
        self._known_legal_ids: frozenset[str] = frozenset(self._authority.catalogues.legal)

    def resolve(self, hit: ChunkHit) -> ResolvedTarget | DroppedHit:
        """Resolve one chunk hit to a typed target, or drop and report it."""
        path = hit.posix_path.as_posix()
        if self._is_excluded(hit):
            return DroppedHit(hit=hit, reason=DropReason.EXCLUDED_SURFACE, detail=f"excluded surface: {path}")

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
            return self._resolve_cli_reference(hit, cli_ref_match.group("family"))

        docs_match = _DOCS_PAGE_RE.match(path)
        if docs_match:
            return self._resolve_docs(hit, docs_match.group("rel"))

        return DroppedHit(hit=hit, reason=DropReason.UNKNOWN_PATH, detail=f"no resolution rule for {path}")

    def _is_excluded(self, hit: ChunkHit) -> bool:
        return any(part in _EXCLUDED_SEGMENTS for part in hit.posix_path.parts)

    def _resolve_casilla(self, hit: ChunkHit, modelo: str) -> ResolvedTarget | DroppedHit:
        records = self._casillas_by_modelo.get(modelo)
        if not records:
            return DroppedHit(
                hit=hit,
                reason=DropReason.NO_TARGET_ENTITY,
                detail=f"no projected casilla records for modelo {modelo!r}",
            )
        # The fragment groups many casillas; the modelo's record set is the
        # casilla-namespace target. Use the first record's namespace target,
        # re-weighted by the hit score so a stronger hit ranks higher.
        base = records[0]
        record = base.model_copy(
            update={"ranking_weight": _reweight(SearchRecordKind.CASILLA, hit.score)},
        )
        return ResolvedTarget(surface=GroundingSurface.CASILLA, record=record, source_hit=hit)

    def _resolve_normatives(self, hit: ChunkHit) -> ResolvedTarget | DroppedHit:
        # Strip the .extracted.md sidecar suffix to recover the origin html path
        # relative to src/aeat/_data/, then to the corpus/-rooted corpus_ref form.
        path = hit.posix_path.as_posix()
        origin = path.removesuffix(".extracted.md")
        corpus_rel = _to_corpus_relative(origin)
        if corpus_rel is None:
            return DroppedHit(
                hit=hit,
                reason=DropReason.NO_TARGET_ENTITY,
                detail=f"normatives sidecar outside the corpus root: {path}",
            )
        legal_id = self._legal_by_corpus_path.get(corpus_rel)
        if legal_id is None:
            return DroppedHit(
                hit=hit,
                reason=DropReason.NO_TARGET_ENTITY,
                detail=f"no legal catalogue entry references corpus path {corpus_rel!r}",
            )
        return self._legal_target(hit, legal_id)

    def _resolve_legal_toml(self, hit: ChunkHit) -> ResolvedTarget | DroppedHit:
        # A legal TOML file declares many provisions grouped under
        # ``[legal."<id>"]`` headers. The catalogue is keyed by id, not file, and
        # the authority exposes no per-entry source-file, so the file's declared
        # ids are discovered by scanning its table headers, then cross-checked
        # against the validated catalogue (the authority stays the value
        # authority; this only learns WHICH ids the file declares). The first
        # known id is the representative legal-grounding target; precise
        # per-line resolution is the wrangling layer's concern.
        declared = _declared_legal_ids(hit.path, self._known_legal_ids)
        if not declared:
            return DroppedHit(
                hit=hit,
                reason=DropReason.NO_TARGET_ENTITY,
                detail=f"no catalogue-known legal id declared in {hit.posix_path.name!r}",
            )
        return self._legal_target(hit, declared[0])

    def _legal_target(self, hit: ChunkHit, legal_id: str) -> ResolvedTarget | DroppedHit:
        entry = self._authority.catalogues.legal.get(legal_id)
        permalink = getattr(entry, "permalink", None) if entry is not None else None
        if not permalink:
            return DroppedHit(
                hit=hit,
                reason=DropReason.NO_TARGET_ENTITY,
                detail=f"legal entry {legal_id!r} has no permalink",
            )
        from ._unified_record import RankingTier, SearchRecordMetadata

        title = f"BOE · {legal_id}"
        record = SearchRecord(
            id=f"legal:{legal_id}",
            kind=SearchRecordKind.PAGE,
            tier=RankingTier.FULLTEXT,
            title=title,
            descriptions=_legal_descriptions(entry),
            target=str(permalink),
            ranking_weight=_reweight(SearchRecordKind.PAGE, hit.score),
            metadata=SearchRecordMetadata(legal_refs=(legal_id,)),
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

    def _resolve_cli_reference(self, hit: ChunkHit, family: str) -> ResolvedTarget:
        from ._unified_record import RankingTier, SearchRecordMetadata

        # docs/cli/app.rst -> the generated CLI-reference family page (the CLI
        # grounding surface). This resolves WITHOUT the live CLI tree walk: the
        # reference page is a generated docs surface, so a hit there links to
        # the family page where every command's section lives.
        target = f"cli/{family}.html"
        record = SearchRecord(
            id=f"cli-ref:{family}",
            kind=SearchRecordKind.CLI,
            tier=RankingTier.NAVIGATION,
            title=f"aeat {family} command reference",
            descriptions=_plain_descriptions(f"aeat {family} command reference"),
            target=target,
            ranking_weight=_reweight(SearchRecordKind.CLI, hit.score),
            metadata=SearchRecordMetadata(command_path=f"aeat {family}"),
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
        ``dropped``, never silently mapped (ADR D6).
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


def _to_corpus_relative(origin_path: str) -> str | None:
    """Map a ``src/aeat/_data/<rest>`` path to the ``<rest>`` corpus-ref form.

    The legal catalogue's ``corpus_ref`` is rooted at ``corpus/...`` (relative
    to ``src/aeat/_data/``), so an origin html path under ``_data`` maps by
    stripping the ``src/aeat/_data/`` prefix.
    """
    prefix = "src/aeat/_data/"
    if not origin_path.startswith(prefix):
        return None
    return origin_path[len(prefix) :]


_LEGAL_HEADER_RE = re.compile(r'^\[legal\."(?P<id>[^"]+)"\]', re.MULTILINE)


def _declared_legal_ids(project_relpath: str, known_ids: frozenset[str]) -> tuple[str, ...]:
    """Return the catalogue-known legal ids a legal TOML file declares.

    Resolves the project-relative path to an absolute one under the project
    root, scans the file for ``[legal."<id>"]`` table headers, and keeps only
    the ids the validated catalogue knows. This is build-time discovery of
    WHICH ids a file declares -- the authority remains the value authority for
    every provision. Returns an empty tuple when the file is unreadable or
    declares no catalogue-known id.
    """
    from aeat.core.config import PROJECT_ROOT

    absolute = PROJECT_ROOT / PurePosixPath(project_relpath.replace("\\", "/"))
    try:
        text = absolute.read_text(encoding="utf-8")
    except OSError:
        return ()
    found = [match.group("id") for match in _LEGAL_HEADER_RE.finditer(text)]
    return tuple(legal_id for legal_id in found if legal_id in known_ids)


def _module_to_dotted(path: str) -> str | None:
    """Map ``src/aeat/foo/bar.py`` (or ``__init__.py``) to its dotted module name.

    Mirrors the apidocs stub-naming convention: a module file maps to
    ``aeat.foo.bar`` and a package ``__init__.py`` to ``aeat.foo`` -- the stub
    filename (and built ``docs/api/<dotted>.html`` page) is named from this.
    """
    if not path.startswith("src/aeat/") or not path.endswith(".py"):
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


def _legal_descriptions(entry: object) -> dict[OutputLanguage, str]:
    notes = getattr(entry, "notes", None)
    text = str(notes).strip() if notes else "BOE legal provision"
    return {OutputLanguage.ES: text[:240]}


def _plain_descriptions(text: str) -> dict[OutputLanguage, str]:
    return {OutputLanguage.ES: (text or "documentation").strip()[:240] or "documentation"}
