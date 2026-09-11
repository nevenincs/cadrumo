"""Validated access point for registry-backed modelo definitions.

:class:`ValidatedRegistryAuthority` is the production boundary for all registry
access. It reconstructs the published, validated authority artifact into typed
:class:`ModeloDefinition` and :class:`ModeloRevision` objects, and produces
:class:`RegistrySnapshot` instances on demand for each filing context.
"""

from __future__ import annotations

import os
from collections.abc import Generator, Mapping
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from secrets import token_bytes
from threading import Condition, RLock
from typing import Protocol, override

from ....core.authority_grade import RegistryAuthorityGrade
from ....core.hashing import content_hash_hex
from ....core.identity import ContentDigest
from ....core.resources.bundled_data import bundled_path as _bundled_path
from ._snapshot_internals import _build_validated_snapshot
from .authority_artifact import (
    AuthorityArtifact,
    AuthorityEvidenceProjection,
    read_shared_authority_artifact,
)
from .corpus_provenance import NormativeCorpusProvenance, classify_normative_corpus_provenance
from .errors import RegistrySnapshotError, RegistryValidationError
from .facts.resolution import GovernedFactQuery, ResolvedGovernedFact, resolve_governed_fact
from .ids import LegalRefId, ModeloId, RevisionId, SourceRefId
from .schema import (
    ModeloDefinition,
    ModeloRevision,
    RegistryCatalogues,
    RegistrySnapshot,
)
from .schema_deadlines import DeadlineWindowDefinition
from .schema_references import SourceReference
from .schema_verification import LiveCrossReferenceDecision, WorkbookParityReference
from .static_inspection import RegistryRevisionInspection
from .temporal import select_revision

_SnapshotKey = tuple[str, int, str, date | None, str | None, RegistryAuthorityGrade]
_DeadlineWindow = tuple[str, ModeloRevision, DeadlineWindowDefinition]


type RegistryAuthorityProjection = RegistryRevisionInspection | RegistrySnapshot


_authority_process_pid = os.getpid()
_authority_process_nonce = token_bytes(32)
_authority_process_domains: set[ContentDigest] = set()
_authority_state_lock = RLock()
_authority_load_states: dict[object, object] = {}
_authority_generation = 0
_authority_reset_epoch = 0


class RegistryAuthorityLifecycleObserver(Protocol):
    """Development observer retained for compiler-cache reset tooling."""

    def registry_cache_reset_requested(self) -> None:
        """Observe a compiler-cache reset request."""
        ...

    def registry_cache_reset_acquired(self) -> None:
        """Observe exclusive ownership of compiler-cache reset."""
        ...


class _SilentRegistryAuthorityLifecycleObserver:
    def registry_cache_reset_requested(self) -> None:
        pass

    def registry_cache_reset_acquired(self) -> None:
        pass


_SILENT_AUTHORITY_LIFECYCLE_OBSERVER = _SilentRegistryAuthorityLifecycleObserver()


class _DevelopmentCacheResetBarrier:
    """A dev-only synchronization seam; product runtime has no source cache."""

    @contextmanager
    def reset(self) -> Generator[None]:
        with _authority_state_lock:
            yield


_authority_load_barrier = _DevelopmentCacheResetBarrier()


@dataclass(frozen=True, slots=True)
class RegistryCoverageFacts:
    """The isolated facts a model-law coverage ledger reads, without the rest of the snapshot.

    A coverage ledger consumes six things: the coordinate it was built for, and
    four collections of evidence references. It reads no casilla, no formula and
    no binding. Obtaining those six through :meth:`ValidatedRegistryAuthority.snapshot`
    means deep-copying the entire validated projection to look at a hundredth of
    it - against a mid-sized modelo the four collections cost about 1.4 ms to
    isolate and the whole snapshot about 127 ms, and the audit that builds these
    ledgers did it 884 times.

    This carries the same isolation guarantee for the part that is actually read.
    Every collection is copied, so a consumer still cannot reach cached registry
    state through it, and each coordinate still gets its own facts rather than
    sharing one revision's copy - which is what lets the ledger builder keep
    refusing a coordinate that disagrees with the data beside it.
    """

    modelo: ModeloId
    revision: RevisionId
    filing_year: int
    period: str
    legal: tuple[LegalRefId, ...]
    sources: Mapping[SourceRefId, SourceReference]
    workbook_parity_refs: tuple[WorkbookParityReference, ...]
    live_cross_references: tuple[LiveCrossReferenceDecision, ...]


@dataclass(frozen=True, slots=True)
class RegistryAuthorityCapture:
    """One isolated law-selected registry projection and its currentness coordinate."""

    projection: RegistryAuthorityProjection
    comparison_domain: ContentDigest
    generation: int

    def require_current(self, current: RegistryAuthorityCurrentCoordinate) -> RegistryAuthorityCapture:
        """Refuse a currentness comparison outside this physical process domain."""
        _require_authority_process_domain(self.comparison_domain)
        current.require_current(self)
        return self


@dataclass(frozen=True, slots=True)
class RegistryAuthorityCurrentCoordinate:
    """Opaque same-process coordinate for one registry authority owner scope."""

    comparison_domain: ContentDigest
    generation: int

    def require_current(self, captured: RegistryAuthorityCapture) -> RegistryAuthorityCurrentCoordinate:
        """Require a capture from this exact root pair and process incarnation."""
        _require_authority_process_domain(self.comparison_domain)
        _require_authority_process_domain(captured.comparison_domain)
        if self.comparison_domain != captured.comparison_domain:
            raise RegistrySnapshotError(
                "registry authority coordinates can compare only within one physical-root process domain"
            )
        if self.generation != captured.generation:
            raise RegistrySnapshotError("registry authority capture is no longer current")
        return self


@dataclass(frozen=True, slots=True, eq=False)
class _FingerprintKey[T]:
    """Cache key that hashes on a digest while still carrying its fingerprints.

    The authority cache is keyed on the complete fingerprint of every file it
    read, which is what makes a tree edit visible. Hashing those tuples
    directly costs one pass over the whole corpus on every cache lookup, so the
    key hash is taken once over the digest and the tuples ride along for the
    body to read.
    """

    digest: str
    fingerprints: T

    @override
    def __hash__(self) -> int:
        return hash(self.digest)

    @override
    def __eq__(self, other: object) -> bool:
        return isinstance(other, _FingerprintKey) and self.digest == other.digest


def _fingerprint_key_payload(fingerprints: tuple[tuple[object, ...], ...]) -> dict[str, object]:
    """Frame a source-fingerprint corpus for its canonical cache-key digest."""
    return {
        "schema": "registry-authority-fingerprint-key/v1",
        "entries": [[str(fingerprint_field) for fingerprint_field in entry] for entry in fingerprints],
    }


def fingerprint_key[T: tuple[tuple[object, ...], ...]](fingerprints: T) -> _FingerprintKey[T]:
    """Digest one fingerprint tuple set into an O(1)-hashable cache key."""
    return _FingerprintKey(digest=content_hash_hex(_fingerprint_key_payload(fingerprints)), fingerprints=fingerprints)


_PhysicalDirectoryIdentity = tuple[int, int]
_AuthorityRootKey = tuple[_PhysicalDirectoryIdentity, _PhysicalDirectoryIdentity]
_AuthorityLoadKey = tuple[object, _FingerprintKey[tuple[tuple[str, int, int], ...]]]


@dataclass(frozen=True, slots=True)
class _AuthorityRootPairIdentity:
    """Canonical physical identity for one registry and source-root pair."""

    root: Path
    source_root: Path
    key: _AuthorityRootKey


@dataclass(slots=True)
class _AuthorityLoadState:
    """The one live cache slot and transition lock for one registry/source root."""

    lock: AbstractContextManager[object] = field(default_factory=RLock, repr=False)
    current_key: _AuthorityLoadKey | None = None
    current_authority: ValidatedRegistryAuthority | None = None
    current_failure: Exception | None = None
    generation: int = 0
    reset_epoch: int = 0


class _AuthorityLoadBarrier:
    """Allow concurrent root loads while making reset an exclusive transition."""

    def __init__(self) -> None:
        self._condition = Condition(RLock())
        self._active_readers = 0
        self._reset_pending = False

    @contextmanager
    def read(self) -> Generator[None]:
        """Enter one load/capture/read operation that reset must drain."""
        with self._condition:
            while self._reset_pending:
                self._condition.wait()
            self._active_readers += 1
        try:
            yield
        finally:
            with self._condition:
                self._active_readers -= 1
                if self._active_readers == 0:
                    self._condition.notify_all()

    @contextmanager
    def reset(self) -> Generator[None]:
        """Exclude and drain readers while every registry cache is cleared."""
        with self._condition:
            while self._reset_pending:
                self._condition.wait()
            self._reset_pending = True
            while self._active_readers:
                self._condition.wait()
        try:
            yield
        finally:
            with self._condition:
                self._reset_pending = False
                self._condition.notify_all()


_authority_state_lock = RLock()
_authority_load_barrier = _AuthorityLoadBarrier()
_authority_load_states: dict[_AuthorityRootKey, _AuthorityLoadState] = {}
_authority_generation: int = 0
_authority_reset_epoch: int = 0


def canonical_authority_root_pair(root: Path, source_root: Path) -> _AuthorityRootPairIdentity:
    """Resolve one physical owner pair with the host filesystem's case policy.

    Strict resolution makes nonexistent or broken aliases a refusal.  Symlinks,
    relative paths, and dot segments collapse before the physical device/inode
    identity applies the filesystem's native case policy.
    """
    try:
        resolved_root = root.expanduser().resolve(strict=True)
        resolved_source_root = source_root.expanduser().resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise RegistrySnapshotError("registry authority roots must resolve to existing physical paths") from exc
    if not resolved_root.is_dir() or not resolved_source_root.is_dir():
        raise RegistrySnapshotError("registry authority roots must resolve to physical directories")
    root_stat = resolved_root.stat()
    source_root_stat = resolved_source_root.stat()
    return _AuthorityRootPairIdentity(
        root=resolved_root,
        source_root=resolved_source_root,
        key=((root_stat.st_dev, root_stat.st_ino), (source_root_stat.st_dev, source_root_stat.st_ino)),
    )


def _authority_comparison_domain_payload(identity: _AuthorityRootPairIdentity) -> dict[str, object]:
    """Frame one private physical-root/process identity for content hashing."""
    return {
        "schema": "registry-authority-comparison-domain/v1",
        "physical_root_pair": [list(item) for item in identity.key],
        "process_incarnation": _authority_process_nonce.hex(),
    }


def _authority_comparison_domain(identity: _AuthorityRootPairIdentity) -> ContentDigest:
    """Return the non-persisted coordinate domain for one resolved root pair."""
    domain = content_hash_hex(_authority_comparison_domain_payload(identity))
    _authority_process_domains.add(domain)
    return domain


def _require_authority_process_domain(domain: ContentDigest) -> None:
    """Refuse a coordinate domain not minted in this process incarnation."""
    _guard_authority_process()
    if domain not in _authority_process_domains:
        raise RegistrySnapshotError("registry authority coordinate belongs to another process incarnation")


def _rebuild_authority_process_state() -> None:
    """Re-key process-local authority state without touching inherited locks."""
    global _authority_process_pid, _authority_process_nonce, _authority_process_domains
    global _authority_state_lock, _authority_load_barrier, _authority_load_states
    global _authority_generation, _authority_reset_epoch
    _authority_process_pid = os.getpid()
    _authority_process_nonce = token_bytes(32)
    _authority_process_domains = set()
    _authority_state_lock = RLock()
    _authority_load_barrier = _AuthorityLoadBarrier()
    _authority_load_states = {}
    _authority_generation = 0
    _authority_reset_epoch = 0


def _guard_authority_process() -> None:
    """Repair process-local state if a fork bypassed the registered callback."""
    if os.getpid() != _authority_process_pid:
        _rebuild_authority_process_state()


if hasattr(os, "register_at_fork"):
    os.register_at_fork(after_in_child=_rebuild_authority_process_state)


def _authority_load_state(root_key: _AuthorityRootKey) -> _AuthorityLoadState:
    """Return the one transition state for an authority owner scope."""
    with _authority_state_lock:
        return _authority_load_states.setdefault(root_key, _AuthorityLoadState())


def _begin_authority_transition(state: _AuthorityLoadState, key: _AuthorityLoadKey) -> None:
    """Invalidate a root's prior authority before building the observed state."""
    global _authority_generation
    with _authority_state_lock:
        _authority_generation += 1
        state.current_key = key
        state.current_authority = None
        state.current_failure = None
        state.generation = _authority_generation
        state.reset_epoch = _authority_reset_epoch


def _publish_authority(
    state: _AuthorityLoadState,
    authority: ValidatedRegistryAuthority,
    root_identity: _AuthorityRootPairIdentity,
) -> None:
    """Publish the one constructed authority for the already-observed state."""
    with _authority_state_lock:
        authority._bind_capture_incarnation(  # pyright: ignore[reportPrivateUsage]  # owner-controlled publication binds a new private instance
            state=state,
            generation=state.generation,
            reset_epoch=state.reset_epoch,
            root_identity=root_identity,
        )
        state.current_authority = authority


def _publish_authority_failure(state: _AuthorityLoadState, failure: Exception) -> None:
    """Publish a deterministic refusal for the already-observed state."""
    with _authority_state_lock:
        state.current_failure = failure


@dataclass(slots=True)
class ValidatedRegistryAuthority:
    """Load, validate, and cache registry material behind one access point."""

    root: Path
    source_root: Path
    modelos: tuple[ModeloDefinition, ...]
    catalogues: RegistryCatalogues
    _modelos_by_id: dict[str, ModeloDefinition]
    _validator: object
    _registry_validated: bool
    _validated_modelos: set[str]
    _snapshots: dict[_SnapshotKey, RegistrySnapshot]
    _identity_digest: str = ""
    evidence: AuthorityEvidenceProjection = field(default_factory=AuthorityEvidenceProjection)
    _capture_generation: int = field(default=0, init=False, repr=False)
    _capture_reset_epoch: int = field(default=0, init=False, repr=False)
    _capture_state: _AuthorityLoadState | None = field(default=None, init=False, repr=False)
    _capture_root_key: _AuthorityRootKey | None = field(default=None, init=False, repr=False)
    _capture_comparison_domain: ContentDigest | None = field(default=None, init=False, repr=False)
    _capture_process_pid: int = field(default=0, init=False, repr=False)
    _capture_process_incarnation: bytes = field(default=b"", init=False, repr=False)
    _published_artifact: bool = field(default=False, init=False, repr=False)
    _state_lock: AbstractContextManager[object] = field(default_factory=RLock, init=False, repr=False)

    def _bind_capture_incarnation(
        self,
        *,
        state: _AuthorityLoadState,
        generation: int,
        reset_epoch: int,
        root_identity: _AuthorityRootPairIdentity,
    ) -> None:
        """Bind this newly constructed object to the owner's current generation."""
        self._capture_state = state
        self._capture_root_key = root_identity.key
        self._capture_comparison_domain = _authority_comparison_domain(root_identity)
        self._capture_generation = generation
        self._capture_reset_epoch = reset_epoch
        self._capture_process_pid = _authority_process_pid
        self._capture_process_incarnation = _authority_process_nonce

    def _bind_published_artifact_incarnation(self) -> None:
        """Bind a fresh artifact graph to this process without a mutable root slot."""
        _guard_authority_process()
        domain = content_hash_hex(
            {
                "schema": "published-authority-artifact-coordinate/v1",
                "artifact_identity_digest": self._identity_digest,
                "process_incarnation": _authority_process_nonce.hex(),
            }
        )
        _authority_process_domains.add(domain)
        self._capture_comparison_domain = domain
        self._capture_process_pid = _authority_process_pid
        self._capture_process_incarnation = _authority_process_nonce
        self._published_artifact = True

    def modelo(self, modelo_id: str) -> ModeloDefinition:
        """Return a modelo definition by id.

        Returns:
            The :class:`ModeloDefinition` for ``modelo_id``.
        """
        try:
            return self._modelos_by_id[modelo_id]
        except KeyError as exc:
            raise RegistrySnapshotError(f"modelo {modelo_id!r} is not present in the calculation registry") from exc

    def legal_evidence_text(self, legal_ref_id: LegalRefId) -> str:
        """Return the published anchor text for one runtime legal citation.

        Published authorities answer this without resolving a source root.  A
        development authority has no projection until it passes publication,
        so absence is a refusal rather than a corpus fallback.
        """
        with self._state_lock:
            return self.evidence.legal_text(str(legal_ref_id))

    def legal_quotation_is_grounded(self, legal_ref_id: LegalRefId, quotation: str) -> bool:
        """Answer one citation query entirely from published evidence."""
        with self._state_lock:
            return self.evidence.quotation_is_grounded(str(legal_ref_id), quotation)

    def legal_corpus_provenance(self, legal_ref_id: LegalRefId) -> NormativeCorpusProvenance:
        """Return one legal reference's provenance through this validated authority.

        The authority owns both catalogue selection and validation. This method
        deliberately delegates byte resolution to the canonical classifier,
        rather than reconstructing a second corpus-path convention here.
        """
        with self._state_lock:
            self.validate_registry()
            try:
                reference = self.catalogues.legal[legal_ref_id]
            except KeyError as exc:
                raise RegistrySnapshotError(
                    f"legal reference {legal_ref_id!r} is not present in the catalogue"
                ) from exc
            return classify_normative_corpus_provenance(self.source_root, reference.corpus_ref)

    def resolve_governed_fact(self, query: GovernedFactQuery) -> ResolvedGovernedFact:
        """Resolve one typed governed-fact query through this validated authority."""
        with self._state_lock:
            self.validate_registry()
            if not self._identity_digest:
                raise RegistryValidationError("governed fact resolution requires an authority identity digest")
            return resolve_governed_fact(
                self.catalogues.facts,
                query,
                authority_digest=self._identity_digest,
            )

    def validate_modelo(self, modelo_id: str) -> ModeloDefinition:
        """Validate one modelo once and return its definition.

        Returns:
            The validated :class:`ModeloDefinition` for ``modelo_id``.
        """
        with self._state_lock:
            modelo = self.modelo(modelo_id)
            if not self._registry_validated and modelo_id not in self._validated_modelos:
                try:
                    self._validator.validate_modelo(modelo)  # type: ignore[attr-defined]  # development compiler supplies this validator
                finally:
                    pass
                self._validated_modelos.add(modelo_id)
            return modelo

    def inspect_revision(
        self,
        modelo_id: str,
        *,
        filing_year: int,
        period: str,
        on: date | None = None,
    ) -> RegistryRevisionInspection:
        """Project static admission facts for one canonically selected revision.

        The request coordinate selects one revision through the canonical
        temporal resolver, but the returned projection retains neither filing
        year nor period.  It validates the full registry and never constructs
        a :class:`RegistrySnapshot`; callers that need filing eligibility must
        use :meth:`snapshot` instead.
        """
        with self._state_lock:
            self.validate_registry()
            modelo = self.modelo(modelo_id)
            revision = select_revision(modelo, filing_year=filing_year, period=period, on=on)
            return RegistryRevisionInspection.from_revision(
                modelo=modelo,
                revision=revision,
                source_root=self.source_root,
                sources=self.catalogues.sources,
                legal_ref_ids=frozenset(self.catalogues.legal),
            )

    def validate_registry(self) -> None:
        """Validate the full registry tree once."""
        with self._state_lock:
            if self._registry_validated:
                return
            try:
                # Corpus-text extraction batches its disk-cache write behind a
                # dirty flag; one flush per validation run replaces the per-miss
                # full-file rewrite that was accidentally quadratic.
                self._validator.validate_registry(self.modelos)  # type: ignore[attr-defined]  # development compiler supplies this validator
            finally:
                pass
            self._mark_registry_validated()

    def _mark_registry_validated(self) -> None:
        """Record that the full registry is validated for this instance.

        Shared by the direct validation path and the verdict-skip path in
        :func:`_load_authority`, so a fingerprint-certified load reaches the
        same validated state without re-running validation.
        """
        self._registry_validated = True
        self._validated_modelos.update(modelo.id for modelo in self.modelos)

    def mark_registry_validated(self) -> None:
        """Mark this authority as validated after a certified verdict."""
        with self._state_lock:
            self._mark_registry_validated()

    def modelo_has_engine(self, modelo_id: str) -> bool:
        """Return whether ``modelo_id`` declares a calculation surface.

        A modelo "has an engine" when any of its revisions declares an
        application-link whose ``surface`` is ``"calculation"`` — the
        registry's own marker that a runtime calculation consumer is wired
        for the modelo. Returns ``False`` for an unknown modelo.
        """
        modelo = self._modelos_by_id.get(modelo_id)
        if modelo is None:
            return False
        return any(
            link.surface == "calculation"
            for revision in modelo.revisions.values()
            for link in revision.application_links
        )

    def snapshot(
        self,
        modelo_id: str,
        *,
        filing_year: int,
        period: str,
        on: date | None = None,
        revision_id: RevisionId | None = None,
        grade: RegistryAuthorityGrade = RegistryAuthorityGrade.FILING,
    ) -> RegistrySnapshot:
        """Return an isolated copy of the cached validated snapshot for one filing context.

        ``grade`` names the rung of authority the CALLER needs and defaults to the
        strictest one, so a caller that says nothing is unchanged. It exists because
        this accessor had no way to ask for a lower rung: it always built at FILING,
        so a modelo whose registry declares ``authority_grade = applicability`` --
        modelo 036, whose censal alta/modificacion/baja is filed on AEAT's sede and
        produces no fichero here -- refused every caller that only wanted to know
        which revision governs an event kind.

        The rung is part of the cache key. Without it a snapshot built for one rung
        would be served to a caller asking for another, which is precisely the silent
        capability claim the grade exists to prevent.
        """
        with self._state_lock:
            return self._cached_snapshot(
                modelo_id,
                filing_year=filing_year,
                period=period,
                on=on,
                revision_id=revision_id,
                grade=grade,
            ).model_copy(deep=True)

    def admitted_revision_id(
        self,
        modelo_id: str,
        *,
        filing_year: int,
        period: str,
        on: date | None = None,
        revision_id: RevisionId | None = None,
        grade: RegistryAuthorityGrade = RegistryAuthorityGrade.FILING,
    ) -> str:
        """Return the revision identifier the snapshot boundary admits for one filing context.

        Same selection, same validation and the same refusals as :meth:`snapshot`;
        the difference is what comes back. A caller that only needs to know which
        revision governs a coordinate - and that the boundary admitted it at the
        requested rung - is asking a question whose whole answer is an identifier,
        and it pays for a deep copy of the entire validated projection to read one
        string out of it.

        That copy is what makes :meth:`snapshot` expensive: against the bundled
        registry a cache hit costs no measurable time and the isolating copy costs
        practically the whole call. Returning the identifier is safe precisely
        because a string is not shared mutable state, so this accessor gives up
        nothing the deep copy was protecting. Callers that go on to READ the
        projection must still use :meth:`snapshot` and receive their own isolated
        copy.
        """
        with self._state_lock:
            return str(
                self._cached_snapshot(
                    modelo_id,
                    filing_year=filing_year,
                    period=period,
                    on=on,
                    revision_id=revision_id,
                    grade=grade,
                ).revision.id
            )

    def coverage_facts(
        self,
        modelo_id: str,
        *,
        filing_year: int,
        period: str,
        on: date | None = None,
        revision_id: RevisionId | None = None,
        grade: RegistryAuthorityGrade = RegistryAuthorityGrade.FILING,
    ) -> RegistryCoverageFacts:
        """Return the isolated coverage facts for one filing context.

        Same selection, same validation and the same refusals as :meth:`snapshot`.
        It differs only in isolating the four evidence collections a coverage
        ledger reads instead of the whole validated projection, which is what
        that ledger was paying for and never reading. A caller that needs a
        casilla, a formula or a binding still takes a snapshot.
        """
        import copy

        with self._state_lock:
            snapshot = self._cached_snapshot(
                modelo_id,
                filing_year=filing_year,
                period=period,
                on=on,
                revision_id=revision_id,
                grade=grade,
            )
            return RegistryCoverageFacts(
                modelo=snapshot.modelo.id,
                revision=snapshot.revision.id,
                filing_year=snapshot.filing_year,
                period=snapshot.period,
                legal=tuple(copy.deepcopy(item) for item in snapshot.legal),
                sources=copy.deepcopy(dict(snapshot.sources)),
                workbook_parity_refs=tuple(copy.deepcopy(item) for item in snapshot.workbook_parity_refs.values()),
                live_cross_references=tuple(copy.deepcopy(item) for item in snapshot.live_cross_references.values()),
            )

    def _cached_snapshot(
        self,
        modelo_id: str,
        *,
        filing_year: int,
        period: str,
        on: date | None,
        revision_id: RevisionId | None,
        grade: RegistryAuthorityGrade,
    ) -> RegistrySnapshot:
        """Return the authority-private cache entry used by every snapshot read.

        The cache remains the single native snapshot authority. Its value never
        crosses the public boundary directly because ``RegistrySnapshot`` has
        mutable nested maps; callers receive isolated copies from
        :meth:`snapshot`, while native capture copies this same entry under the
        owner lock.
        """
        key = (modelo_id, filing_year, period, on, revision_id, grade)
        cached = self._snapshots.get(key)
        if cached is not None:
            return cached
        modelo = self.validate_modelo(modelo_id)
        snapshot = _build_validated_snapshot(
            modelo,
            self.catalogues,
            filing_year=filing_year,
            period=period,
            on=on,
            revision_id=revision_id,
            grade=grade,
        )
        self._snapshots[key] = snapshot
        return snapshot

    def capture_law_selected_projection(
        self,
        modelo_id: str,
        *,
        filing_year: int,
        period: str,
        on: date | None = None,
        grade: RegistryAuthorityGrade | None = None,
    ) -> RegistryAuthorityCapture:
        """Atomically capture a law-selected inspection or grade-admitted snapshot.

        ``grade=None`` deliberately selects the static-inspection authority;
        supplying a grade selects the existing snapshot admission path.  The
        returned value is deep-copied so a consumer cannot mutate a cached
        registry projection after the capture has completed.
        """
        self._require_creator_process()
        state = self._capture_state
        if state is None and not self._published_artifact:
            raise RegistrySnapshotError("registry authority has no published capture incarnation")
        if state is None:
            with self._state_lock:
                self._require_current_capture_incarnation()
                projection = (
                    self.inspect_revision(
                        modelo_id,
                        filing_year=filing_year,
                        period=period,
                        on=on,
                    )
                    if grade is None
                    else self._cached_snapshot(
                        modelo_id,
                        filing_year=filing_year,
                        period=period,
                        on=on,
                        revision_id=None,
                        grade=grade,
                    )
                )
                return RegistryAuthorityCapture(
                    projection=projection.model_copy(deep=True),
                    comparison_domain=self._current_coordinate().comparison_domain,
                    generation=0,
                )
        with _authority_load_barrier.read(), state.lock, self._state_lock:
            self._require_current_capture_incarnation()
            projection = (
                self.inspect_revision(
                    modelo_id,
                    filing_year=filing_year,
                    period=period,
                    on=on,
                )
                if grade is None
                else self._cached_snapshot(
                    modelo_id,
                    filing_year=filing_year,
                    period=period,
                    on=on,
                    revision_id=None,
                    grade=grade,
                )
            )
            isolated_projection = projection.model_copy(deep=True)
            self._require_current_capture_incarnation()
            return RegistryAuthorityCapture(
                projection=isolated_projection,
                comparison_domain=self._current_coordinate().comparison_domain,
                generation=self._capture_generation,
            )

    def read_current_coordinate(self) -> RegistryAuthorityCurrentCoordinate:
        """Return the typed current coordinate for same-domain capture validation."""
        self._require_creator_process()
        state = self._capture_state
        if state is None and not self._published_artifact:
            raise RegistrySnapshotError("registry authority has no published capture incarnation")
        if state is None:
            with self._state_lock:
                self._require_current_capture_incarnation()
                return self._current_coordinate()
        with _authority_load_barrier.read(), state.lock:
            self._require_current_capture_incarnation()
            return self._current_coordinate()

    def _current_coordinate(self) -> RegistryAuthorityCurrentCoordinate:
        comparison_domain = self._capture_comparison_domain
        if comparison_domain is None:
            raise RegistrySnapshotError("registry authority has no published capture coordinate")
        return RegistryAuthorityCurrentCoordinate(
            comparison_domain=comparison_domain,
            generation=self._capture_generation,
        )

    def _require_current_capture_incarnation(self) -> None:
        """Refuse capture when reset or an observed identity change made it stale."""
        self._require_creator_process()
        state = self._capture_state
        root_key = self._capture_root_key
        with _authority_state_lock:
            if self._published_artifact:
                return
            if self._capture_reset_epoch != _authority_reset_epoch:
                raise RegistrySnapshotError(
                    "registry authority capture was invalidated by cache reset; load a current authority"
                )
            if (
                state is None
                or root_key is None
                or _authority_load_states.get(root_key) is not state
                or state.current_authority is not self
                or state.generation != self._capture_generation
                or state.reset_epoch != self._capture_reset_epoch
            ):
                raise RegistrySnapshotError(
                    "registry authority capture was invalidated by an observed registry identity transition; "
                    "load a current authority"
                )

    def _require_creator_process(self) -> None:
        """Refuse an authority object inherited from another process incarnation."""
        _guard_authority_process()
        if (
            self._capture_process_pid != _authority_process_pid
            or self._capture_process_incarnation != _authority_process_nonce
        ):
            raise RegistrySnapshotError(
                "registry authority instance belongs to another process incarnation; load a fresh authority"
            )

    def deadline_windows(
        self,
        year: int,
        *,
        modelos: tuple[str, ...] | None = None,
    ) -> tuple[_DeadlineWindow, ...]:
        """Return canonically owned, validated deadline windows for ``year``.

        Window rows retain their containing revision for provenance, but that
        containment does not choose the governing revision.  The filing
        coordinate does, through the same :func:`select_revision` authority
        used by snapshots.  Non-owning historical copies are therefore never
        projected, including when a fingerprint-certified warm load predates a
        stricter corpus validation verdict.  This is selection, not
        deduplication: every row in the selected revision remains observable.
        """
        out: list[_DeadlineWindow] = []
        for modelo in self._selected_modelos(modelos):
            candidates = tuple(
                (revision, window)
                for revision in modelo.revisions.values()
                for window in revision.deadline_windows
                if window.filing_year == year
            )
            if not candidates:
                continue
            try:
                self.validate_modelo(modelo.id)
            except RegistryValidationError:
                raise
            for containing_revision, window in candidates:
                selected_revision = select_revision(
                    modelo,
                    filing_year=window.period.filing_year,
                    period=window.period.registry_token,
                )
                if selected_revision.id != containing_revision.id:
                    continue
                # Cold validation proves this ownership invariant.  Keep the
                # guard at the projection boundary as a defence against a
                # future traversal refactor accidentally returning provenance
                # from a revision other than the canonical selector's result.
                if containing_revision is not modelo.revisions[selected_revision.id]:
                    raise RegistrySnapshotError(
                        f"modelo {modelo.id} deadline provenance names revision "
                        f"{containing_revision.id!r} while the canonical selector resolved "
                        f"{selected_revision.id!r}",
                    )
                out.append((modelo.id, selected_revision, window))
        out.sort(
            key=lambda item: (
                item[2].closes_on,
                item[0],
                *_deadline_window_period_sort_key(item[2]),
                *_deadline_window_qualifier_sort_key(item[2]),
            ),
        )
        return tuple(out)

    def _selected_modelos(self, modelos: tuple[str, ...] | None) -> tuple[ModeloDefinition, ...]:
        if modelos is None:
            return self.modelos
        return tuple(self.modelo(modelo_id) for modelo_id in modelos)


def _deadline_window_period_sort_key(window: DeadlineWindowDefinition) -> tuple[int, str]:
    return window.filing_year, window.period.registry_token


def _deadline_window_qualifier_sort_key(window: DeadlineWindowDefinition) -> tuple[str, tuple[str, ...]]:
    """Order qualified plazo variants without defining another vocabulary."""
    resultado = "" if window.resultado_scope is None else window.resultado_scope.value
    tipo_renta = () if window.tipo_renta_scope is None else tuple(sorted(window.tipo_renta_scope))
    return resultado, tipo_renta


_BUNDLED_AUTHORITY_ARTIFACT_PARTS = ("registry", "authority", "authority.json")


class _PublishedArtifactValidator:
    """Defensive sentinel: product authorities are already publication-validated."""

    def validate_modelo(self, _modelo: ModeloDefinition) -> None:
        raise RegistrySnapshotError("a published authority must not enter source validation")

    def validate_registry(self, _modelos: tuple[ModeloDefinition, ...]) -> None:
        raise RegistrySnapshotError("a published authority must not enter source validation")


def bundled_authority() -> ValidatedRegistryAuthority:
    """Return an authority over the bundled published artifact.

    See :func:`published_authority` for the sharing and refusal contract.
    """
    return published_authority(bundled_authority_artifact_path())


def published_authority(artifact_path: Path) -> ValidatedRegistryAuthority:
    """Return a fresh authority over the published artifact at ``artifact_path``.

    Publication validates authoring inputs before producing the artifact.  A
    product process never recompiles those inputs: a missing, corrupt, or
    unsupported-version publication is refused here, on every call, before a
    calculation or filing can begin.

    The verified model graph is decoded once per artifact file identity and
    shared, because it is deeply immutable: every model is frozen and every
    mapping is a frozen mapping, so no consumer can change the modelos or
    catalogues another consumer observes.  The authority object itself, with
    its own snapshot cache and validation bookkeeping, is new on every call.
    A republished artifact is detected by its file identity and decoded afresh.
    """
    artifact = read_shared_authority_artifact(artifact_path)
    return _authority_from_published_artifact(artifact, artifact_path=artifact_path)


def bundled_authority_artifact_path() -> Path:
    """Resolve the one package resource that constitutes runtime authority.

    Development publication writes here and its currency check reads here, so
    the product and its tooling cannot disagree about where the artifact lives.
    """
    return _bundled_path(*_BUNDLED_AUTHORITY_ARTIFACT_PARTS)


def _authority_from_published_artifact(
    artifact: AuthorityArtifact,
    *,
    artifact_path: Path,
) -> ValidatedRegistryAuthority:
    """Build an already-validated runtime authority without authoring inputs.

    The published artifact is the validation receipt. The marked-valid state
    ensures no source evidence, compiler, repair, or conformance path is
    reached by a product authority.
    """
    runtime_root = artifact_path.parent
    authority = ValidatedRegistryAuthority(
        root=runtime_root,
        source_root=_bundled_path(),
        modelos=artifact.modelos,
        catalogues=artifact.catalogues,
        _modelos_by_id={modelo.id: modelo for modelo in artifact.modelos},
        _validator=_PublishedArtifactValidator(),
        _registry_validated=True,
        _validated_modelos={modelo.id for modelo in artifact.modelos},
        _snapshots={},
        _identity_digest=artifact.identity_digest,
        evidence=artifact.evidence,
    )
    authority._bind_published_artifact_incarnation()
    return authority
