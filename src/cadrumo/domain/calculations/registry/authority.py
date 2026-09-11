"""Validated access point for registry-backed modelo definitions.

:class:`ValidatedRegistryAuthority` is the production boundary for all registry
access. It reconstructs the published, validated authority artifact into typed
:class:`ModeloDefinition` and :class:`ModeloRevision` objects, and produces
:class:`RegistrySnapshot` instances on demand for each filing context.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from secrets import token_bytes
from threading import RLock

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
from .errors import RegistrySnapshotError, RegistryValidationError
from .facts.resolution import GovernedFactQuery, ResolvedGovernedFact, resolve_governed_fact
from .ids import LegalRefId, ModeloId, RevisionId, SourceRefId
from .provenance import NormativeCorpusProvenance
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


_artifact_process_nonce = token_bytes(32)
_artifact_coordinate_domains: set[ContentDigest] = set()


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
        """Require this immutable artifact capture to match its current coordinate."""
        _require_artifact_coordinate_domain(self.comparison_domain)
        current.require_current(self)
        return self


@dataclass(frozen=True, slots=True)
class RegistryAuthorityCurrentCoordinate:
    """Opaque same-process coordinate for one registry authority owner scope."""

    comparison_domain: ContentDigest
    generation: int

    def require_current(self, captured: RegistryAuthorityCapture) -> RegistryAuthorityCurrentCoordinate:
        """Require a capture from this exact artifact/process coordinate."""
        _require_artifact_coordinate_domain(self.comparison_domain)
        _require_artifact_coordinate_domain(captured.comparison_domain)
        if self.comparison_domain != captured.comparison_domain:
            raise RegistrySnapshotError(
                "registry authority coordinates can compare only within one artifact process domain"
            )
        if self.generation != captured.generation:
            raise RegistrySnapshotError("registry authority capture is no longer current")
        return self


def _artifact_coordinate_domain(identity_digest: str) -> ContentDigest:
    """Mint an opaque coordinate for one signed artifact in this process."""
    domain = content_hash_hex(
        {
            "schema": "published-authority-artifact-coordinate/v1",
            "artifact_identity_digest": identity_digest,
            "process_incarnation": _artifact_process_nonce.hex(),
        }
    )
    _artifact_coordinate_domains.add(domain)
    return domain


def _require_artifact_coordinate_domain(domain: ContentDigest) -> None:
    """Refuse a capture coordinate minted by another process incarnation."""
    if domain not in _artifact_coordinate_domains:
        raise RegistrySnapshotError("registry authority coordinate belongs to another process incarnation")


@dataclass(slots=True)
class ValidatedRegistryAuthority:
    """Load, validate, and cache registry material behind one access point."""

    modelos: tuple[ModeloDefinition, ...]
    catalogues: RegistryCatalogues
    _modelos_by_id: dict[str, ModeloDefinition]
    _snapshots: dict[_SnapshotKey, RegistrySnapshot]
    _identity_digest: str = ""
    evidence: AuthorityEvidenceProjection = field(default_factory=AuthorityEvidenceProjection)
    _capture_comparison_domain: ContentDigest | None = field(default=None, init=False, repr=False)
    _state_lock: RLock = field(default_factory=RLock, init=False, repr=False)

    @classmethod
    def from_validated_components(
        cls,
        *,
        modelos: tuple[ModeloDefinition, ...],
        catalogues: RegistryCatalogues,
        identity_digest: str,
        evidence: AuthorityEvidenceProjection | None = None,
    ) -> ValidatedRegistryAuthority:
        """Construct an immutable runtime projection after development validation.

        This boundary accepts models, catalogues, identity, and optional
        published evidence only. It has no authoring-root or validator input.
        """
        authority = cls(
            modelos=modelos,
            catalogues=catalogues,
            _modelos_by_id={modelo.id: modelo for modelo in modelos},
            _snapshots={},
            _identity_digest=identity_digest,
            evidence=AuthorityEvidenceProjection() if evidence is None else evidence,
        )
        authority._bind_published_artifact_incarnation()
        return authority

    def _bind_published_artifact_incarnation(self) -> None:
        """Bind a fresh artifact graph to this process without a mutable root slot."""
        self._capture_comparison_domain = _artifact_coordinate_domain(self._identity_digest)

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

        The publisher's validated evidence projection is the sole runtime
        provenance authority; product code never resolves a corpus path.
        """
        with self._state_lock:
            return self.evidence.legal_provenance(str(legal_ref_id))

    def resolve_governed_fact(self, query: GovernedFactQuery) -> ResolvedGovernedFact:
        """Resolve one typed governed-fact query through this validated authority."""
        with self._state_lock:
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
            modelo = self.modelo(modelo_id)
            revision = select_revision(modelo, filing_year=filing_year, period=period, on=on)
            return RegistryRevisionInspection.from_revision(
                modelo=modelo,
                revision=revision,
                source_root=None,
                sources=self.catalogues.sources,
                legal_ref_ids=frozenset(self.catalogues.legal),
            )

    def validate_registry(self) -> None:
        """Assert that this already-published authority is available."""
        return None

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
        with self._state_lock:
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

    def read_current_coordinate(self) -> RegistryAuthorityCurrentCoordinate:
        """Return the typed current coordinate for same-domain capture validation."""
        with self._state_lock:
            return self._current_coordinate()

    def _current_coordinate(self) -> RegistryAuthorityCurrentCoordinate:
        comparison_domain = self._capture_comparison_domain
        if comparison_domain is None:
            raise RegistrySnapshotError("registry authority has no published capture coordinate")
        return RegistryAuthorityCurrentCoordinate(
            comparison_domain=comparison_domain,
            generation=0,
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


def bundled_authority() -> ValidatedRegistryAuthority:
    """Return a fresh authority reconstructed from the bundled published artifact.

    Publication validates authoring inputs before producing this artifact.  A
    product process never recompiles those inputs: a missing, corrupt, or
    unsupported-version publication is refused here before a calculation or
    filing can begin. Each call returns distinct authority state around a
    deeply immutable, file-identity-cached artifact graph, so consumers cannot
    mutate the authority subsequently observed by another consumer.
    """
    artifact_path = bundled_authority_artifact_path()
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
    return ValidatedRegistryAuthority.from_validated_components(
        modelos=artifact.modelos,
        catalogues=artifact.catalogues,
        identity_digest=artifact.identity_digest,
        evidence=artifact.evidence,
    )
