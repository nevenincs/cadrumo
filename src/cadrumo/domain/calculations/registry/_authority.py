"""Validated access point for registry-backed modelo definitions.

:class:`ValidatedRegistryAuthority` is the production boundary for all registry
access. It loads TOML sources via the compiler in ``_loader``, compiles them
into :class:`ModeloDefinition` and :class:`ModeloRevision` objects, and
produces :class:`RegistrySnapshot` instances on demand for each filing context.
"""

from __future__ import annotations

import hashlib
from collections.abc import Generator
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from threading import Condition, RLock
from typing import Protocol, override

from .... import __version__
from ....core import RegistryAuthorityGrade
from ....core.access_gate import (
    AuthorizationManifest,
    ModeloAuthorization,
    derive_modelo_authorization,
    load_authorization_manifest,
)
from ....core.resources import bundled_path as _bundled_path
from ._convenio import collect_convenio_fingerprints, load_convenio_authority, validate_convenio_legal_refs
from ._errors import RegistrySnapshotError, RegistryValidationError
from ._identity import (
    FingerprintTuples,
    RegistryIdentity,
    registry_identity_stamp_location,
    resolve_registry_identity,
    write_registry_identity_stamp,
)
from ._ids import ModeloId, RevisionId
from ._loader import collect_registry_tree_fingerprints, load_registry_tree
from ._schema import (
    DeadlineWindowDefinition,
    ModeloDefinition,
    ModeloRevision,
    RegistryCatalogues,
    RegistrySnapshot,
)
from ._snapshot import (
    _build_validated_snapshot,  # pyright: ignore[reportPrivateUsage]  # the registry authority owns snapshot admission
)
from ._source_evidence_fingerprint import collect_source_evidence_fingerprints
from ._static_inspection import RegistryRevisionInspection
from ._supplementary_orden import collect_supplementary_orden_fingerprints, compile_supplementary_ordenes
from ._supported_filing_years import SupportedFilingYearGap, audit_supported_filing_years
from ._temporal import coverage_assessment_horizon, revision_selection_coordinates, select_revision
from ._validate import RegistryValidator
from ._validate_evidence import flush_corpus_text_cache
from ._verdict_cache import (
    certify_registry_validation,
    compute_verdict_key,
    registry_validation_is_certified,
    shipped_verdict_location,
    stamp_bundled_verdict,
)


def collect_registry_identity_fingerprints(resolved_root: Path) -> FingerprintTuples:
    """Collect every fingerprint group that constitutes registry-tree identity.

    The tree itself, the convenio treaty tree, and the supplementary annual
    Orden set -- the three groups the authority compiles from. Kept as one named
    collector rather than an inline concatenation so the release stamper and the
    runtime walk provably fingerprint the SAME groups: a stamp computed over a
    narrower set than the runtime walks would certify a tree nobody checked.

    Returns:
        The concatenated fingerprint tuples for ``resolved_root``.
    """
    return (
        collect_registry_tree_fingerprints(resolved_root)
        + collect_convenio_fingerprints(resolved_root)
        + collect_supplementary_orden_fingerprints(resolved_root)
    )


_SnapshotKey = tuple[str, int, str, date | None, str | None, RegistryAuthorityGrade]
_DeadlineWindow = tuple[str, ModeloRevision, DeadlineWindowDefinition]
_RegistryFingerprints = tuple[tuple[str, int, int, str], ...]
_SourceEvidenceFingerprints = tuple[tuple[str, int, int], ...]


type RegistryAuthorityProjection = RegistryRevisionInspection | RegistrySnapshot


class RegistryAuthorityLifecycleObserver(Protocol):
    """Observe authority construction, publication, and cache-reset transitions."""

    def authority_construction_started(self, *, root: Path, source_root: Path) -> None:
        """Observe a cold construction after the owner identity is selected."""
        ...

    def authority_published(self, *, root: Path, source_root: Path, generation: int) -> None:
        """Observe publication of one current authority incarnation."""
        ...

    def registry_cache_reset_requested(self) -> None:
        """Observe a reset request before it waits for active authority readers."""
        ...

    def registry_cache_reset_acquired(self) -> None:
        """Observe a reset after it exclusively owns the authority lifecycle."""
        ...


class _SilentRegistryAuthorityLifecycleObserver:
    """Production default for callers that do not consume lifecycle telemetry."""

    __slots__ = ()

    def authority_construction_started(self, *, root: Path, source_root: Path) -> None:
        del root, source_root

    def authority_published(self, *, root: Path, source_root: Path, generation: int) -> None:
        del root, source_root, generation

    def registry_cache_reset_requested(self) -> None:
        return

    def registry_cache_reset_acquired(self) -> None:
        return


_SILENT_AUTHORITY_LIFECYCLE_OBSERVER = _SilentRegistryAuthorityLifecycleObserver()


@dataclass(frozen=True, slots=True)
class RegistryAuthorityCapture:
    """One isolated law-selected registry projection with its native generation."""

    projection: RegistryAuthorityProjection
    generation: int


@dataclass(frozen=True, slots=True)
class RegistryDiagnosticFilingRevision:
    """Static filing-revision facts admitted for diagnostic classification.

    This projection carries no :class:`RegistrySnapshot` and no authority
    capability.  Its optional inspection is the existing static-only
    projection used by generated-artifact verification.
    """

    modelo: ModeloId
    revision: RevisionId
    selection_coordinates: tuple[tuple[int, str], ...]
    layout_ids: tuple[str, ...]
    layout_json: str | None
    inspection_json: str | None
    refusal_reason: str | None = None
    refusal_detail: str | None = None


@dataclass(frozen=True, slots=True)
class UnvalidatedRegistryClassification:
    """Narrow, read-only classification capability after strict loading fails.

    It intentionally exposes only static, per-revision classification facts.
    It cannot snapshot, calculate, render, or act as a runtime registry
    authority.
    """

    strict_validation_error: str
    filing_revisions: tuple[RegistryDiagnosticFilingRevision, ...]


def derive_filing_revision_classifications(
    authority: ValidatedRegistryAuthority,
) -> tuple[RegistryDiagnosticFilingRevision, ...]:
    """Copy every filing revision into static law-selection classification facts.

    The supplied authority is used only while this function runs.  Returned
    facts contain immutable coordinates, error text, and serialized static
    layout/inspection projections; they retain no authority, snapshot, or
    service object.
    """
    assessment_horizon = coverage_assessment_horizon(authority.catalogues)
    classified: list[RegistryDiagnosticFilingRevision] = []
    for modelo in sorted(authority.modelos, key=lambda item: item.id):
        for revision in sorted(modelo.revisions.values(), key=lambda item: item.id):
            if revision.authority_grade is not RegistryAuthorityGrade.FILING:
                continue
            try:
                selection_coordinates = revision_selection_coordinates(
                    revision,
                    assessment_horizon=assessment_horizon,
                )
            except ValueError as error:
                classified.append(
                    RegistryDiagnosticFilingRevision(
                        modelo=modelo.id,
                        revision=revision.id,
                        selection_coordinates=(),
                        layout_ids=(),
                        layout_json=None,
                        inspection_json=None,
                        refusal_reason="law_selection_failed",
                        refusal_detail=str(error),
                    )
                )
                continue
            try:
                inspection = RegistryRevisionInspection.from_revision(
                    modelo=modelo,
                    revision=revision,
                    source_root=authority.source_root,
                    sources=authority.catalogues.sources,
                    legal_ref_ids=frozenset(authority.catalogues.legal),
                )
                inspection_json = inspection.model_dump_json()
            except ValueError as error:
                classified.append(
                    RegistryDiagnosticFilingRevision(
                        modelo=modelo.id,
                        revision=revision.id,
                        selection_coordinates=selection_coordinates,
                        layout_ids=tuple(str(layout.id) for layout in revision.export_layouts),
                        layout_json=None,
                        inspection_json=None,
                        refusal_reason="revision_validation_failed",
                        refusal_detail=str(error),
                    )
                )
                continue
            try:
                snapshots = tuple(
                    authority.snapshot(
                        modelo.id,
                        filing_year=filing_year,
                        period=period,
                        grade=RegistryAuthorityGrade.FILING,
                    )
                    for filing_year, period in selection_coordinates
                )
            except RegistryValidationError as error:
                layout = revision.export_layouts[0] if len(revision.export_layouts) == 1 else None
                classified.append(
                    RegistryDiagnosticFilingRevision(
                        modelo=modelo.id,
                        revision=revision.id,
                        selection_coordinates=selection_coordinates,
                        layout_ids=tuple(str(item.id) for item in revision.export_layouts),
                        layout_json=None if layout is None else layout.model_dump_json(),
                        inspection_json=inspection_json,
                        refusal_reason="revision_validation_failed",
                        refusal_detail=str(error),
                    )
                )
                continue
            except RegistrySnapshotError as error:
                classified.append(
                    RegistryDiagnosticFilingRevision(
                        modelo=modelo.id,
                        revision=revision.id,
                        selection_coordinates=selection_coordinates,
                        layout_ids=(),
                        layout_json=None,
                        inspection_json=inspection_json,
                        refusal_reason="law_selection_failed",
                        refusal_detail=str(error),
                    )
                )
                continue
            if any(snapshot.revision.id != revision.id for snapshot in snapshots):
                classified.append(
                    RegistryDiagnosticFilingRevision(
                        modelo=modelo.id,
                        revision=revision.id,
                        selection_coordinates=selection_coordinates,
                        layout_ids=(),
                        layout_json=None,
                        inspection_json=inspection_json,
                        refusal_reason="law_selection_failed",
                        refusal_detail="a filing-grade snapshot selected a different revision",
                    )
                )
                continue
            layout_ids = tuple(str(layout.id) for layout in snapshots[0].revision.export_layouts)
            if not layout_ids or any(
                tuple(str(layout.id) for layout in snapshot.revision.export_layouts) != layout_ids
                for snapshot in snapshots
            ):
                classified.append(
                    RegistryDiagnosticFilingRevision(
                        modelo=modelo.id,
                        revision=revision.id,
                        selection_coordinates=selection_coordinates,
                        layout_ids=layout_ids,
                        layout_json=None,
                        inspection_json=inspection_json,
                        refusal_reason="layout_unavailable",
                        refusal_detail=(
                            "the filing revision has no stable single layout across its selected coordinates"
                        ),
                    )
                )
                continue
            if len(layout_ids) != 1:
                classified.append(
                    RegistryDiagnosticFilingRevision(
                        modelo=modelo.id,
                        revision=revision.id,
                        selection_coordinates=selection_coordinates,
                        layout_ids=layout_ids,
                        layout_json=None,
                        inspection_json=inspection_json,
                        refusal_reason="layout_unavailable",
                        refusal_detail="conformance supports exactly one generated filing layout per revision",
                    )
                )
                continue
            classified.append(
                RegistryDiagnosticFilingRevision(
                    modelo=modelo.id,
                    revision=revision.id,
                    selection_coordinates=selection_coordinates,
                    layout_ids=layout_ids,
                    layout_json=snapshots[0].revision.export_layouts[0].model_dump_json(),
                    inspection_json=inspection_json,
                )
            )
    return tuple(classified)


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


def _fingerprint_key[T: tuple[tuple[object, ...], ...]](fingerprints: T) -> _FingerprintKey[T]:
    """Digest one fingerprint tuple set into an O(1)-hashable cache key."""
    digest = hashlib.sha256()
    for entry in fingerprints:
        for fingerprint_field in entry:
            digest.update(str(fingerprint_field).encode("utf-8"))
            digest.update(b"\x1f")
        digest.update(b"\x1e")
    return _FingerprintKey(digest=digest.hexdigest(), fingerprints=fingerprints)


_AuthorityRootKey = tuple[Path, Path]
_AuthorityLoadKey = tuple[RegistryIdentity, _FingerprintKey[_SourceEvidenceFingerprints]]


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


_AUTHORITY_STATE_LOCK = RLock()
_AUTHORITY_LOAD_BARRIER = _AuthorityLoadBarrier()
_AUTHORITY_LOAD_STATES: dict[_AuthorityRootKey, _AuthorityLoadState] = {}
_authority_generation = 0
_authority_reset_epoch = 0


def _authority_root_key(root: Path, source_root: Path) -> _AuthorityRootKey:
    """Return the exact owner scope whose projections a load can change."""
    return root, source_root


def _authority_load_state(root_key: _AuthorityRootKey) -> _AuthorityLoadState:
    """Return the one transition state for an authority owner scope."""
    with _AUTHORITY_STATE_LOCK:
        return _AUTHORITY_LOAD_STATES.setdefault(root_key, _AuthorityLoadState())


def _begin_authority_transition(state: _AuthorityLoadState, key: _AuthorityLoadKey) -> None:
    """Invalidate a root's prior authority before building the observed state."""
    global _authority_generation
    with _AUTHORITY_STATE_LOCK:
        _authority_generation += 1
        state.current_key = key
        state.current_authority = None
        state.current_failure = None
        state.generation = _authority_generation
        state.reset_epoch = _authority_reset_epoch


def _publish_authority(state: _AuthorityLoadState, authority: ValidatedRegistryAuthority) -> None:
    """Publish the one constructed authority for the already-observed state."""
    with _AUTHORITY_STATE_LOCK:
        authority._bind_capture_incarnation(  # pyright: ignore[reportPrivateUsage]  # owner-controlled publication binds a new private instance
            state=state,
            generation=state.generation,
            reset_epoch=state.reset_epoch,
        )
        state.current_authority = authority


def _publish_authority_failure(state: _AuthorityLoadState, failure: Exception) -> None:
    """Publish a deterministic refusal for the already-observed state."""
    with _AUTHORITY_STATE_LOCK:
        state.current_failure = failure


def _invalidate_authority_generations() -> None:
    """Invalidate all authority incarnations as one exclusive reset transition."""
    global _authority_generation, _authority_reset_epoch
    with _AUTHORITY_STATE_LOCK:
        _authority_generation += 1
        _authority_reset_epoch += 1
        _AUTHORITY_LOAD_STATES.clear()


@dataclass(slots=True)
class ValidatedRegistryAuthority:
    """Load, validate, and cache registry material behind one access point."""

    root: Path
    source_root: Path
    modelos: tuple[ModeloDefinition, ...]
    catalogues: RegistryCatalogues
    _modelos_by_id: dict[str, ModeloDefinition]
    _validator: RegistryValidator
    _registry_validated: bool
    _validated_modelos: set[str]
    _snapshots: dict[_SnapshotKey, RegistrySnapshot]
    _authorization_manifest: AuthorizationManifest
    _supported_filing_year_gaps: tuple[SupportedFilingYearGap, ...]
    _capture_generation: int = field(default=0, init=False, repr=False)
    _capture_reset_epoch: int = field(default=0, init=False, repr=False)
    _capture_state: _AuthorityLoadState | None = field(default=None, init=False, repr=False)
    _capture_root_key: _AuthorityRootKey | None = field(default=None, init=False, repr=False)
    _state_lock: AbstractContextManager[object] = field(default_factory=RLock, init=False, repr=False)

    @classmethod
    def load(
        cls,
        root: Path,
        *,
        source_root: Path,
        lifecycle_observer: RegistryAuthorityLifecycleObserver = _SILENT_AUTHORITY_LIFECYCLE_OBSERVER,
    ) -> ValidatedRegistryAuthority:
        """Load registry TOML and construct a reusable :class:`ValidatedRegistryAuthority` instance."""
        resolved_root = root.expanduser().resolve()
        resolved_source_root = source_root.expanduser().resolve()
        return _load_authority(
            resolved_root,
            resolved_source_root,
            lifecycle_observer=lifecycle_observer,
        )

    def _bind_capture_incarnation(
        self,
        *,
        state: _AuthorityLoadState,
        generation: int,
        reset_epoch: int,
    ) -> None:
        """Bind this newly constructed object to the owner's current generation."""
        self._capture_state = state
        self._capture_root_key = _authority_root_key(self.root, self.source_root)
        self._capture_generation = generation
        self._capture_reset_epoch = reset_epoch

    def modelo(self, modelo_id: str) -> ModeloDefinition:
        """Return a modelo definition by id.

        Returns:
            The :class:`ModeloDefinition` for ``modelo_id``.
        """
        try:
            return self._modelos_by_id[modelo_id]
        except KeyError as exc:
            raise RegistrySnapshotError(f"modelo {modelo_id!r} is not present in the calculation registry") from exc

    def validate_modelo(self, modelo_id: str) -> ModeloDefinition:
        """Validate one modelo once and return its definition.

        Returns:
            The validated :class:`ModeloDefinition` for ``modelo_id``.
        """
        with self._state_lock:
            modelo = self.modelo(modelo_id)
            if not self._registry_validated and modelo_id not in self._validated_modelos:
                try:
                    self._validator.validate_modelo(modelo)
                finally:
                    flush_corpus_text_cache()
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
                self._validator.validate_registry(self.modelos)
            finally:
                flush_corpus_text_cache()
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

    @property
    def authorization_manifest(self) -> AuthorizationManifest:
        """Return the loaded multi-year-renta authorization manifest.

        The manifest is the single writable authorization surface; the CI
        meta-test reads it through this accessor to cross-check each
        enrolling claim against the recorder evidence.

        Returns:
            The loaded :class:`AuthorizationManifest` object.
        """
        return self._authorization_manifest

    @property
    def supported_filing_year_gaps(self) -> tuple[SupportedFilingYearGap, ...]:
        """Return the complete advisory gap projection for declared years."""
        return self._supported_filing_year_gaps

    def modelo_has_engine(self, modelo_id: str) -> bool:
        """Return whether ``modelo_id`` declares a calculation surface.

        A modelo "has an engine" when any of its revisions declares an
        application-link whose ``surface`` is ``"calculation"`` — the
        registry's own marker that a runtime calculation consumer is wired
        for the modelo. This drives the authorization gate's
        ADVISORY-vs-refusal split (an unauthorized modelo with an engine
        still computes with an advisory banner; one with no engine is
        refused at ``work create``). Returns ``False`` for an unknown
        modelo rather than raising, so the fleet-wide capability sweep can
        ask about every canonical modelo id including the engine-build
        modelos that do not load yet.
        """
        modelo = self._modelos_by_id.get(modelo_id)
        if modelo is None:
            return False
        return any(
            link.surface == "calculation"
            for revision in modelo.revisions.values()
            for link in revision.application_links
        )

    def authorization(self, modelo_id: str) -> ModeloAuthorization:
        """Return the derived per-modelo authorization capability.

        This is the layer-(b) derivation of the ``modelo-multiyear-renta``
        gate: the capability is *computed* from the manifest (layer a)
        cross-checked against the loaded registry — never an independently
        authored per-revision flag — so it cannot drift from the manifest.
        An unknown / not-yet-loadable modelo derives to ``UNAUTHORIZED``
        with ``has_engine = False``, which is the correct default for the
        engine-build modelos that carry no loadable definition yet.

        Returns:
            The derived :class:`ModeloAuthorization` for ``modelo_id``.
        """
        return derive_modelo_authorization(
            modelo_id,
            manifest=self._authorization_manifest,
            has_engine=self.modelo_has_engine(modelo_id),
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
        state = self._capture_state
        if state is None:
            raise RegistrySnapshotError("registry authority has no published capture incarnation")
        with _AUTHORITY_LOAD_BARRIER.read(), state.lock, self._state_lock:
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
                generation=self._capture_generation,
            )

    def read_current_generation(self) -> int:
        """Return this authority's still-current native capture generation.

        A registry-cache reset invalidates the instance rather than letting an
        old projection claim the next authority incarnation's generation.
        """
        state = self._capture_state
        if state is None:
            raise RegistrySnapshotError("registry authority has no published capture incarnation")
        with _AUTHORITY_LOAD_BARRIER.read(), state.lock:
            self._require_current_capture_incarnation()
            return self._capture_generation

    def _require_current_capture_incarnation(self) -> None:
        """Refuse capture when reset or an observed identity change made it stale."""
        state = self._capture_state
        root_key = self._capture_root_key
        with _AUTHORITY_STATE_LOCK:
            if self._capture_reset_epoch != _authority_reset_epoch:
                raise RegistrySnapshotError(
                    "registry authority capture was invalidated by cache reset; load a current authority"
                )
            if (
                state is None
                or root_key is None
                or _AUTHORITY_LOAD_STATES.get(root_key) is not state
                or state.current_authority is not self
                or state.generation != self._capture_generation
                or state.reset_epoch != self._capture_reset_epoch
            ):
                raise RegistrySnapshotError(
                    "registry authority capture was invalidated by an observed registry identity transition; "
                    "load a current authority"
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
                # assertion at the projection boundary as a defence against a
                # future traversal refactor accidentally returning provenance
                # from a revision other than the canonical selector's result.
                assert containing_revision is modelo.revisions[selected_revision.id]
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


def bundled_authority() -> ValidatedRegistryAuthority:
    """Return an authority loaded from the package-bundled AEAT registry.

    Callers that always load the same default registry path use this
    instead of writing the bundled-path boilerplate inline.  The result
    is backed by the canonical authority owner's current-identity slot, so
    repeated calls within one process share the same published authority.

    Returns:
        A :class:`ValidatedRegistryAuthority` loaded from the bundled registry tree.
    """
    root = _bundled_path("registry", "aeat")
    return ValidatedRegistryAuthority.load(root, source_root=_bundled_path())


def bundled_revision_inspection(
    modelo_id: str,
    *,
    filing_year: int,
    period: str,
    on: date | None = None,
) -> RegistryRevisionInspection:
    """Return a static revision inspection without entering the filing gate.

    The authority fully validates the bundled registry and its supporting
    catalogues, then canonically selects the request's revision.  It
    intentionally does not certify legal-review status or construct a filing
    snapshot, because source-design inspection is not a filing operation and
    must not be represented as one.
    """
    return bundled_authority().inspect_revision(
        modelo_id,
        filing_year=filing_year,
        period=period,
        on=on,
    )


def _load_authority(
    root: Path,
    source_root: Path,
    *,
    lifecycle_observer: RegistryAuthorityLifecycleObserver,
) -> ValidatedRegistryAuthority:
    """Load one root through its sole current-identity authority slot.

    Identity collection, result/failure reuse, construction, and publication
    share one root-scoped lock.  The reset barrier lets unrelated roots proceed
    in parallel but drains this complete protocol before any cache clear.
    """
    root_key = _authority_root_key(root, source_root)
    with _AUTHORITY_LOAD_BARRIER.read():
        state = _authority_load_state(root_key)
        with state.lock:
            identity = resolve_registry_identity(
                root,
                collect_fingerprints=collect_registry_identity_fingerprints,
            )
            source_evidence_key = _fingerprint_key(collect_source_evidence_fingerprints(source_root))
            key = (identity, source_evidence_key)
            if state.current_key == key:
                if state.current_failure is not None:
                    raise state.current_failure
                if state.current_authority is not None:
                    return state.current_authority
                raise RuntimeError("registry authority transition has no published outcome")

            _begin_authority_transition(state, key)
            try:
                lifecycle_observer.authority_construction_started(root=root, source_root=source_root)
                authority = _load_validated_authority(root, source_root, identity, source_evidence_key)
            except Exception as exc:
                _publish_authority_failure(state, exc)
                raise
            _publish_authority(state, authority)
            lifecycle_observer.authority_published(
                root=root,
                source_root=source_root,
                generation=state.generation,
            )
            return authority


def reset_registry_caches(
    *,
    lifecycle_observer: RegistryAuthorityLifecycleObserver = _SILENT_AUTHORITY_LIFECYCLE_OBSERVER,
) -> None:
    """Drop every memoised registry layer so the next read recompiles from disk.

    The compiled-tree lru, the authority load caches and the tree-fingerprint
    cache are one staleness surface: clearing a subset leaves a later layer
    answering from a tree state an earlier layer has already forgotten. Callers
    that swap the registry root or rewrite bundled TOML need all three, so the
    package exposes the whole reset rather than its parts.
    """
    from ._loader import (
        _load_registry_tree_cached,  # pyright: ignore[reportPrivateUsage]  # reset owns the complete registry cache surface
    )
    from ._loader_fingerprints import clear_fingerprint_cache

    lifecycle_observer.registry_cache_reset_requested()
    with _AUTHORITY_LOAD_BARRIER.reset():
        lifecycle_observer.registry_cache_reset_acquired()
        _invalidate_authority_generations()
        _load_registry_tree_cached.cache_clear()
        clear_fingerprint_cache()


def _load_validated_authority(
    root: Path,
    source_root: Path,
    identity: RegistryIdentity,
    source_evidence_key: _FingerprintKey[_SourceEvidenceFingerprints],
) -> ValidatedRegistryAuthority:
    _source_evidence_fingerprint = source_evidence_key.fingerprints
    authority = _construct_authority(root, source_root, _source_evidence_fingerprint, identity=identity)
    # A persisted green verdict keyed by the observed identity lets an
    # immutable tree skip the multi-second re-validation. The build and
    # continuous integration are the validation gate; the runtime asserts
    # identity only. A mismatch or a foreign verdict re-validates in full and
    # rewrites the verdict.
    verdict_key = compute_verdict_key(
        identity_digest=identity.digest,
        source_evidence_fingerprints=_source_evidence_fingerprint,
    )
    if registry_validation_is_certified(
        root,
        verdict_key=verdict_key,
        identity=identity,
    ):
        authority.mark_registry_validated()
    else:
        authority.validate_registry()
        certify_registry_validation(root, verdict_key=verdict_key)
    return authority


def _construct_authority(
    root: Path,
    source_root: Path,
    source_evidence_fingerprint: tuple[tuple[str, int, int], ...],
    *,
    identity: RegistryIdentity,
) -> ValidatedRegistryAuthority:
    """Compile registry material before either filing or inspection admission."""
    modelos, catalogues = load_registry_tree(root, identity=identity)
    # Compile the cross-cutting Convenio doble imposición treaty tree and fold it
    # onto the shared catalogues so every snapshot projects the same authority.
    # Grounding gate: every treaty override must cite a treaty article defined in
    # the shared legal/ catalogue (which resolves to bundled BOE corpus text).
    convenio = load_convenio_authority(root / "treaties")
    validate_convenio_legal_refs(convenio, frozenset(catalogues.legal))
    supported_filing_years = catalogues.supported_filing_years
    if supported_filing_years is None:
        raise RegistryValidationError("registry has no supported_filing_years catalogue")
    supplementary_ordenes = compile_supplementary_ordenes(
        root,
        source_root=source_root,
        modelos=modelos,
        sources=catalogues.sources,
        supported_filing_years=supported_filing_years.years,
    )
    duplicate_legal_refs = set(catalogues.legal).intersection(supplementary_ordenes.legal)
    if duplicate_legal_refs:
        raise RegistryValidationError(
            f"annual Orden compiler collided with hand-authored legal refs: {sorted(duplicate_legal_refs)!r}",
        )
    catalogues = catalogues.model_copy(
        update={
            "legal": {**catalogues.legal, **supplementary_ordenes.legal},
            "convenio": convenio,
            "supplementary_ordenes": supplementary_ordenes.authorities,
        },
    )

    authority = ValidatedRegistryAuthority(
        root=root,
        source_root=source_root,
        modelos=modelos,
        catalogues=catalogues,
        _modelos_by_id={modelo.id: modelo for modelo in modelos},
        _validator=RegistryValidator(
            catalogues,
            source_root=source_root,
            source_evidence_fingerprint=source_evidence_fingerprint,
        ),
        _registry_validated=False,
        _validated_modelos=set(),
        _snapshots={},
        # Authorization is derived at this boundary from the manifest
        # (default-deny-by-absence: an absent manifest authorizes nothing).
        # The manifest is fingerprinted into _collect_registry_tree_fingerprints
        # so the current-identity slot invalidates when the manifest changes on disk.
        _authorization_manifest=load_authorization_manifest(root),
        _supported_filing_year_gaps=audit_supported_filing_years(
            modelos,
            catalogue=supported_filing_years,
            sources=catalogues.sources,
        ),
    )
    return authority


def load_registry_diagnostic_classification(
    root: Path,
    *,
    source_root: Path,
    strict_validation_error: RegistryValidationError,
) -> UnvalidatedRegistryClassification:
    """Create the narrow static classifier after a recorded strict-load failure.

    The returned capability deliberately is not a registry authority.  It can
    only classify independently validated revision facts into diagnostic
    residue; filing, export, and calculation callers must load a validated
    authority through :meth:`ValidatedRegistryAuthority.load`.
    """
    resolved_root = root.expanduser().resolve()
    resolved_source_root = source_root.expanduser().resolve()
    identity = resolve_registry_identity(
        resolved_root,
        collect_fingerprints=collect_registry_identity_fingerprints,
    )
    source_evidence_key = _fingerprint_key(collect_source_evidence_fingerprints(resolved_source_root))
    authority = _construct_authority(
        resolved_root,
        resolved_source_root,
        source_evidence_key.fingerprints,
        identity=identity,
    )
    return UnvalidatedRegistryClassification(
        strict_validation_error=str(strict_validation_error),
        filing_revisions=derive_filing_revision_classifications(authority),
    )


@dataclass(frozen=True, slots=True)
class StampedRegistryRelease:
    """The two records the release build stamps beside a packaged registry tree."""

    identity_path: Path
    verdict_path: Path


def stamp_bundled_registry_release(
    registry_root: Path,
    *,
    package_version: str = __version__,
) -> StampedRegistryRelease:
    """Stamp the install-stable identity and verdict beside ``registry_root``.

    The release build calls this -- and only this -- against the registry tree
    it is packaging. Both records are written here, in this order, from ONE
    fingerprint collection, because they are not independent: the verdict is
    keyed on the identity, so a caller free to write them separately could
    certify one tree with another's identity. Fusing them removes that ordering
    hazard rather than documenting it.

    The fingerprints come from
    :func:`collect_registry_identity_fingerprints`, the same collector the
    runtime walk uses, so the stamp cannot describe a narrower set than the
    runtime would check. The identity states which tree this is; the verdict
    states that the build found it green. A mismatch of either at runtime falls
    back to the full walk and a full re-validation.

    Returns:
        The paths both records were written to.
    """
    resolved = registry_root.expanduser().resolve()
    fingerprints = collect_registry_identity_fingerprints(resolved)
    stamp = write_registry_identity_stamp(
        registry_fingerprints=fingerprints,
        registry_root=resolved,
        package_version=package_version,
    )
    verdict_path = shipped_verdict_location(resolved)
    stamp_bundled_verdict(
        identity_digest=stamp.tree_digest,
        output_path=verdict_path,
        package_version=package_version,
    )
    return StampedRegistryRelease(
        identity_path=registry_identity_stamp_location(resolved),
        verdict_path=verdict_path,
    )
