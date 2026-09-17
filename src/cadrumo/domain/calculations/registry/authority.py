"""Generation-pinned access to compiled registry authority components.

:class:`IndexedRegistryAuthority` is the production boundary.  It admits the
descriptor-selected SQLite generation and loads typed components through one
leased :class:`PinnedAuthorityOperation`.  The eager
:class:`ValidatedRegistryAuthority` remains only for development validation and
the paired pre-cutover JSON benchmark.
"""

from __future__ import annotations

import hmac
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from secrets import token_bytes
from threading import RLock
from typing import TYPE_CHECKING

from ....core.authority_grade import RegistryAuthorityGrade
from ....core.hashing import content_hash_hex, sha256_hex
from ....core.identity.digest import ContentDigest
from ....core.modelo import Modelo
from ....core.resources.bundled_data import bundled_path as _bundled_path
from ....core.tax_domain import TaxDomain
from ....core.time.clock import today_madrid
from .authority_artifact import (
    AuthorityComponentKind,
    AuthorityComponentQuery,
    AuthorityComponentReader,
    AuthorityEvidenceProjection,
    AuthorityGenerationPin,
    EvidenceComponentQuery,
    ExportLayoutComponentQuery,
    GovernedFactComponentQuery,
    ModeloDirectoryComponentQuery,
    ModeloRevisionComponentQuery,
    ProfileCreateContext,
    ProfileDecodeContext,
    ProfileSchemaComponentQuery,
    PublishedLegalEvidence,
    PublishedSourceEvidence,
    ReferenceComponentQuery,
    RuntimeCatalogueComponentQuery,
    SnapshotGlobalsComponentQuery,
)
from .authority_store import SQLiteAuthorityReader
from .errors import RegistrySnapshotError, RegistryValidationError
from .facts.resolution import (
    GovernedFactQuery,
    MappingFactQuery,
    ResolvedGovernedFact,
    ResolvedMappingFact,
    resolve_governed_fact,
    resolve_validated_governed_fact,
)
from .facts.schema import GovernedFact
from .governed_fact_scope import validating_governed_facts
from .ids import LegalRefId, RevisionId
from .schema import (
    ModeloDefinition,
    ModeloRevision,
    RegistryCatalogues,
    RegistrySnapshot,
    SnapshotGlobalCatalogues,
    SupportedFilingYearsCatalogue,
)
from .schema_base import DateAxis
from .schema_deadlines import DeadlineWindowDefinition
from .schema_exports import ExportLayoutDefinition
from .schema_references import LegalReference, SourceReference
from .snapshot import build_validated_snapshot, collect_snapshot_ref_ids
from .static_inspection import RegistryRevisionInspection
from .temporal import ModeloRevisionDirectory, select_revision, select_revision_metadata

if TYPE_CHECKING:
    from ...user_profile.schema import ProfileSchemaDefinition

_SnapshotKey = tuple[str, int, str, date | None, str | None, RegistryAuthorityGrade]
_DeadlineWindow = tuple[str, ModeloRevision, DeadlineWindowDefinition]


type RegistryAuthorityProjection = RegistryRevisionInspection | RegistrySnapshot


_artifact_process_nonce = token_bytes(32)


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
    """Mint an opaque coordinate for one constructed artifact incarnation."""
    nonce = content_hash_hex({"identity": identity_digest, "incarnation": token_bytes(32).hex()})[:32]
    signature = hmac.digest(_artifact_process_nonce, nonce.encode("ascii"), "sha256").hex()[:32]
    return nonce + signature


def _require_artifact_coordinate_domain(domain: ContentDigest) -> None:
    """Authenticate a process-local coordinate without retaining past owners."""
    if len(domain) != 64 or not domain.isascii():
        raise RegistrySnapshotError("registry authority coordinate belongs to another process incarnation")
    nonce, signature = domain[:32], domain[32:]
    expected = hmac.digest(_artifact_process_nonce, nonce.encode("ascii"), "sha256").hex()[:32]
    if not hmac.compare_digest(signature, expected):
        raise RegistrySnapshotError("registry authority coordinate belongs to another process incarnation")


_REGISTRY_CAPTURE_GENERATION = 1
"""The one generation a registry capture comparison domain ever holds.

A domain is minted per immutable authority incarnation -- an admitted
generation pin, or one constructed validated authority -- so every capture
under that domain observes the same content. A new generation arrives as a new
incarnation and therefore a new domain; it is never a successor generation
inside an old one.
"""
_PUBLISHED_CAPTURE_DOMAIN_LIMIT = 16
_published_capture_domains: dict[AuthorityGenerationPin, ContentDigest] = {}
_published_capture_domains_lock = RLock()


def _published_capture_domain(pin: AuthorityGenerationPin) -> ContentDigest:
    """Return the process-authenticated comparison domain shared by every lease of one pin."""
    with _published_capture_domains_lock:
        domain = _published_capture_domains.get(pin)
        if domain is None:
            domain = _artifact_coordinate_domain(f"{pin.logical_generation}:{pin.reader_incarnation}")
            if len(_published_capture_domains) >= _PUBLISHED_CAPTURE_DOMAIN_LIMIT:
                _published_capture_domains.pop(next(iter(_published_capture_domains)))
            _published_capture_domains[pin] = domain
        return domain


@dataclass(frozen=True, slots=True, weakref_slot=True)
class ValidatedRegistryAuthority:
    """Load, validate, and cache registry material behind one access point."""

    modelos: tuple[ModeloDefinition, ...]
    catalogues: RegistryCatalogues
    _modelos_by_id: dict[str, ModeloDefinition]
    _snapshots: dict[_SnapshotKey, RegistrySnapshot]
    _identity_digest: str = ""
    evidence: AuthorityEvidenceProjection = field(default_factory=AuthorityEvidenceProjection)
    _profile_schema: ProfileSchemaDefinition | None = field(default=None, repr=False)
    _capture_comparison_domain: ContentDigest | None = field(default=None, init=False, repr=False)
    _state_lock: RLock = field(default_factory=RLock, init=False, repr=False)
    _fact_resolutions: dict[GovernedFactQuery, ResolvedGovernedFact] = field(
        default_factory=dict, init=False, repr=False
    )

    @classmethod
    def from_validated_components(
        cls,
        *,
        modelos: tuple[ModeloDefinition, ...],
        catalogues: RegistryCatalogues,
        identity_digest: str,
        evidence: AuthorityEvidenceProjection | None = None,
        profile_schema: ProfileSchemaDefinition | None = None,
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
            _profile_schema=profile_schema,
        )
        authority._bind_published_artifact_incarnation()
        return authority

    def profile_schema(self) -> ProfileSchemaDefinition:
        """Return the profile declaration captured in this authority generation."""
        if self._profile_schema is None:
            raise RegistryValidationError("published authority generation contains no profile schema component")
        return self._profile_schema

    def profile_create_context(self) -> ProfileCreateContext:
        """Bind development profile creation to this immutable compiled generation."""
        generation = AuthorityGenerationPin(self._identity_digest, self._identity_digest)
        return ProfileCreateContext(self.profile_schema(), generation)

    def profile_decode_context(self) -> ProfileDecodeContext:
        """Bind development secure decode to this immutable compiled generation."""
        generation = AuthorityGenerationPin(self._identity_digest, self._identity_digest)
        return ProfileDecodeContext(self.profile_schema(), generation)

    def _bind_published_artifact_incarnation(self) -> None:
        """Bind a fresh artifact graph to this process without a mutable root slot."""
        object.__setattr__(self, "_capture_comparison_domain", _artifact_coordinate_domain(self._identity_digest))

    def modelo(self, modelo_id: str | Modelo) -> ModeloDefinition:
        """Return a modelo definition by id.

        Returns:
            The :class:`ModeloDefinition` for ``modelo_id``.
        """
        normalized = Modelo(modelo_id)
        try:
            return self._modelos_by_id[normalized.value]
        except KeyError as exc:
            raise RegistrySnapshotError(
                f"modelo {normalized.value!r} is not present in the calculation registry"
            ) from exc

    def project_filing_year(self, filing_year: int) -> int:
        """Project an admitted filing year onto the authority's authored horizon."""
        support = self.catalogues.supported_filing_years
        if support is None:
            raise RegistrySnapshotError("the calculation registry declares no supported filing years")
        projected = support.projection_coordinate(filing_year)
        if projected is None:
            ceiling = support.hard_ceiling
            span = f"{support.floor} and later" if ceiling is None else f"{support.floor}..{ceiling}"
            raise RegistrySnapshotError(
                f"filing year {filing_year} is outside the calculation registry's supported span {span}"
            )
        return projected

    def tax_domain(
        self,
        tax_domain: str | TaxDomain,
        *,
        effective_date: date | None = None,
    ) -> TaxDomain:
        """Return a syntax-valid tax domain only when this authority declares it."""
        normalized = TaxDomain(tax_domain)
        resolved = self.resolve_governed_fact(
            MappingFactQuery(
                fact_id="tax-domain-catalogue",
                date_axis=DateAxis.FILING_PERIOD,
                effective_date=effective_date or today_madrid(),
            )
        )
        if not isinstance(resolved, ResolvedMappingFact):
            raise RegistrySnapshotError("tax-domain catalogue did not resolve as a mapping")
        declarations = {str(entry.key): str(entry.value) for entry in resolved.payload.entries}
        declared = {code.strip() for code in declarations.get("catalogue.codes", "").split(",") if code.strip()}
        if normalized.value not in declared:
            raise RegistrySnapshotError(f"tax domain {normalized.value!r} is not present in the calculation registry")
        return normalized

    def resolve_governed_fact(self, query: GovernedFactQuery) -> ResolvedGovernedFact:
        """Resolve one typed governed-fact query through this validated authority."""
        with self._state_lock:
            if not self._identity_digest:
                raise RegistryValidationError("governed fact resolution requires an authority identity digest")
            cached = self._fact_resolutions.get(query)
            if cached is not None:
                return cached
            resolved = resolve_governed_fact(
                self.catalogues.facts,
                query,
                authority_digest=self._identity_digest,
                support=self.catalogues.require_supported_filing_years(),
            )
            if len(self._fact_resolutions) >= 1024:
                self._fact_resolutions.pop(next(iter(self._fact_resolutions)))
            self._fact_resolutions[query] = resolved
            return resolved

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
            revision = select_revision(
                modelo,
                filing_year=filing_year,
                period=period,
                on=on,
                support=self.catalogues.supported_filing_years,
            )
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
        """Return the shared immutable snapshot for one admitted filing context.

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
        """Share an admitted immutable projection within the bounded context cache."""
        normalized_modelo_id = Modelo(modelo_id).value
        key = (normalized_modelo_id, filing_year, period, on, revision_id, grade)
        cached = self._snapshots.get(key)
        if cached is not None:
            return cached
        modelo = self.validate_modelo(normalized_modelo_id)
        with validating_governed_facts(self):
            snapshot = build_validated_snapshot(
                modelo,
                self.catalogues,
                filing_year=filing_year,
                period=period,
                on=on,
                revision_id=revision_id,
                grade=grade,
            )
        if len(self._snapshots) >= 1024:
            self._snapshots.pop(next(iter(self._snapshots)))
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
        returned projection is deeply immutable and belongs to this generation.
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
                projection=projection,
                comparison_domain=self._current_coordinate().comparison_domain,
                generation=_REGISTRY_CAPTURE_GENERATION,
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
            generation=_REGISTRY_CAPTURE_GENERATION,
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
                    support=self.catalogues.supported_filing_years,
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


@dataclass(frozen=True, slots=True, weakref_slot=True)
class PinnedAuthorityOperation:
    """Typed component access confined to one leased authority generation."""

    _reader: AuthorityComponentReader
    generation: AuthorityGenerationPin
    _state_lock: RLock = field(default_factory=RLock, init=False, repr=False, compare=False)
    _fact_resolutions: dict[GovernedFactQuery, ResolvedGovernedFact] = field(
        default_factory=dict, init=False, repr=False, compare=False
    )

    def pin(self) -> AuthorityGenerationPin:
        """Return this operation's already-leased generation pin."""
        return self.generation

    def load(self, query: AuthorityComponentQuery, *, pin: AuthorityGenerationPin) -> object:
        """Load an addressed component only through this operation's generation."""
        if pin != self.generation:
            raise RegistrySnapshotError("authority component query crossed an operation generation boundary")
        return self._reader.load(query, pin=self.generation)

    def governed_fact(self, fact_id: str) -> GovernedFact:
        """Load one raw governed fact by canonical identity."""
        value = self.load(GovernedFactComponentQuery(fact_id), pin=self.generation)
        if not isinstance(value, GovernedFact):
            raise RegistryValidationError("governed fact component decoded to an unexpected type")
        return value

    def snapshot_globals(self) -> SnapshotGlobalCatalogues:
        """Load the registry-wide globals published with this generation."""
        value = self.load(SnapshotGlobalsComponentQuery(), pin=self.generation)
        if not isinstance(value, SnapshotGlobalCatalogues):
            raise RegistryValidationError("snapshot globals component decoded to an unexpected type")
        return value

    def supported_filing_years(self) -> SupportedFilingYearsCatalogue:
        """Return the generation's single filing-year support envelope."""
        return self.snapshot_globals().supported_filing_years

    def profile_schema(self, schema_id: str = "cadrumo.user_profile") -> ProfileSchemaDefinition:
        """Load the profile declaration used by this exact operation generation."""
        # The profile schema model tree is only needed by profile-bound operations.
        from ...user_profile.schema import ProfileSchemaDefinition

        value = self._reader.load(ProfileSchemaComponentQuery(schema_id), pin=self.generation)
        if not isinstance(value, ProfileSchemaDefinition):
            raise RegistryValidationError("profile schema component decoded to an unexpected type")
        return value

    def profile_create_context(self) -> ProfileCreateContext:
        """Return the required context for constructing new taxpayer profile values."""
        return ProfileCreateContext(self.profile_schema(), self.generation)

    def profile_decode_context(self) -> ProfileDecodeContext:
        """Return the required context for decoding encrypted taxpayer profile values."""
        return ProfileDecodeContext(self.profile_schema(), self.generation)

    def revision(self, modelo_id: str | Modelo, revision_id: str) -> ModeloRevision:
        """Load one typed base revision without separately addressed export layouts."""
        normalized = Modelo(modelo_id).value
        try:
            value = self._reader.load(ModeloRevisionComponentQuery(normalized, revision_id), pin=self.generation)
        except LookupError as exc:
            if normalized not in self.modelo_ids():
                raise RegistrySnapshotError.for_modelo_not_registered(modelo_id=normalized) from exc
            raise RegistrySnapshotError(
                f"modelo {normalized!r} has no revision {revision_id!r}",
                context={"modelo_id": normalized, "revision_id": revision_id},
            ) from exc
        if not isinstance(value, ModeloRevision):
            raise RegistryValidationError("modelo revision component decoded to an unexpected type")
        return value

    def revision_with_export_layouts(self, modelo_id: str | Modelo, revision_id: str) -> ModeloRevision:
        """Compose one revision with only its separately addressed export layouts."""
        normalized = Modelo(modelo_id).value
        revision = self.revision(normalized, revision_id)
        layouts = tuple(
            self.export_layout(normalized, revision_id, query.layout_id)
            for query in self._reader.component_queries()
            if isinstance(query, ExportLayoutComponentQuery)
            and query.modelo_id == normalized
            and query.revision_id == revision_id
        )
        return revision.model_copy(update={"export_layouts": layouts})

    def modelo_directory(self, modelo_id: str | Modelo) -> ModeloRevisionDirectory:
        """Load the small selector-complete directory for one modelo."""
        normalized = Modelo(modelo_id).value
        try:
            value = self.load(ModeloDirectoryComponentQuery(normalized), pin=self.generation)
        except LookupError as exc:
            raise RegistrySnapshotError.for_modelo_not_registered(modelo_id=normalized) from exc
        if not isinstance(value, ModeloRevisionDirectory):
            raise RegistryValidationError("modelo directory component decoded to an unexpected type")
        return value

    def modelo_ids(self) -> tuple[str, ...]:
        """Return deterministic modelo identities without hydrating directories."""
        return tuple(
            query.modelo_id
            for query in self._reader.component_queries()
            if isinstance(query, ModeloDirectoryComponentQuery)
        )

    def revision_ids(self) -> tuple[tuple[str, str], ...]:
        """Return deterministic modelo/revision identities without hydrating payloads."""
        return tuple(
            (query.modelo_id, query.revision_id)
            for query in self._reader.component_queries()
            if isinstance(query, ModeloRevisionComponentQuery)
        )

    def revision_for_context(
        self,
        modelo_id: str | Modelo,
        *,
        filing_year: int,
        period: str,
        on: date | None = None,
        revision_id: RevisionId | None = None,
    ) -> ModeloRevision:
        """Select by complete metadata, then load exactly one complete revision."""
        normalized = Modelo(modelo_id).value
        selected = select_revision_metadata(
            self.modelo_directory(normalized),
            filing_year=filing_year,
            period=period,
            on=on,
            revision_id=revision_id,
        )
        return self.revision(normalized, str(selected.id))

    def snapshot(
        self,
        modelo_id: str | Modelo,
        *,
        filing_year: int,
        period: str,
        on: date | None = None,
        revision_id: RevisionId | None = None,
        grade: RegistryAuthorityGrade = RegistryAuthorityGrade.FILING,
    ) -> RegistrySnapshot:
        """Build one validated snapshot from same-generation point components."""
        normalized = Modelo(modelo_id).value
        directory = self.modelo_directory(normalized)
        selected = select_revision_metadata(
            directory,
            filing_year=filing_year,
            period=period,
            on=on,
            revision_id=revision_id,
        )
        revision = self.revision_with_export_layouts(normalized, str(selected.id))
        modelo = directory.materialize(revision)
        legal_ids, source_ids = collect_snapshot_ref_ids(modelo, revision)
        globals_value = self.snapshot_globals()
        catalogues = RegistryCatalogues(
            legal={reference_id: self.legal_reference(reference_id) for reference_id in sorted(legal_ids)},
            sources={reference_id: self.source_reference(reference_id) for reference_id in sorted(source_ids)},
            convenio=globals_value.convenio,
            supplementary_ordenes=globals_value.supplementary_ordenes,
            supported_filing_years=directory.supported_filing_years,
        )
        return build_validated_snapshot(
            modelo,
            catalogues,
            filing_year=filing_year,
            period=period,
            on=on,
            revision_id=revision_id,
            grade=grade,
            revision_directory=directory,
        )

    def resolve_governed_fact(self, query: GovernedFactQuery) -> ResolvedGovernedFact:
        """Resolve one fact once per query without revalidating its static component."""
        with self._state_lock:
            cached = self._fact_resolutions.get(query)
            if cached is not None:
                return cached
            value = self.governed_fact(str(query.fact_id))
            resolved = resolve_validated_governed_fact(
                value,
                query,
                authority_digest=self.generation.logical_generation,
                support=self.supported_filing_years(),
            )
            if len(self._fact_resolutions) >= 1024:
                self._fact_resolutions.pop(next(iter(self._fact_resolutions)))
            self._fact_resolutions[query] = resolved
            return resolved

    def runtime_catalogue(self, family: str) -> object:
        """Load one named runtime catalogue family."""
        return self._reader.load(RuntimeCatalogueComponentQuery(family), pin=self.generation)

    def legal_reference(self, reference_id: str) -> LegalReference:
        """Load one legal declaration by canonical identity."""
        value = self.load(
            ReferenceComponentQuery(reference_id, AuthorityComponentKind.LEGAL_REFERENCE),
            pin=self.generation,
        )
        if not isinstance(value, LegalReference):
            raise RegistryValidationError("legal reference component decoded to an unexpected type")
        return value

    def source_reference(self, reference_id: str) -> SourceReference:
        """Load one public-source declaration by canonical identity."""
        value = self.load(
            ReferenceComponentQuery(reference_id, AuthorityComponentKind.SOURCE_REFERENCE),
            pin=self.generation,
        )
        if not isinstance(value, SourceReference):
            raise RegistryValidationError("source reference component decoded to an unexpected type")
        return value

    def export_layout(
        self,
        modelo_id: str | Modelo,
        revision_id: str,
        layout_id: str,
    ) -> ExportLayoutDefinition:
        """Load one separately addressable export layout."""
        value = self._reader.load(
            ExportLayoutComponentQuery(Modelo(modelo_id).value, revision_id, layout_id),
            pin=self.generation,
        )
        if not isinstance(value, ExportLayoutDefinition):
            raise RegistryValidationError("export layout component decoded to an unexpected type")
        return value

    def legal_evidence(self, legal_reference_id: str) -> PublishedLegalEvidence:
        """Load one publisher-captured legal evidence projection."""
        value = self._reader.load(
            EvidenceComponentQuery(legal_reference_id, AuthorityComponentKind.LEGAL_EVIDENCE),
            pin=self.generation,
        )
        if not isinstance(value, PublishedLegalEvidence):
            raise RegistryValidationError("legal evidence component decoded to an unexpected type")
        return value

    def legal_reference_ids(self) -> tuple[str, ...]:
        """Return every published legal declaration identity without hydrating payloads."""
        return tuple(
            query.reference_id
            for query in self._reader.component_queries()
            if isinstance(query, ReferenceComponentQuery) and query.kind is AuthorityComponentKind.LEGAL_REFERENCE
        )

    def legal_quotation_is_grounded(self, legal_ref_id: LegalRefId, quotation: str) -> bool:
        """Answer one citation query from this generation's published legal evidence."""
        evidence = self.legal_evidence(str(legal_ref_id))
        return AuthorityEvidenceProjection(legal=(evidence,)).quotation_is_grounded(str(legal_ref_id), quotation)

    def capture_law_selected_projection(
        self,
        modelo_id: str,
        *,
        filing_year: int,
        period: str,
        on: date | None = None,
        grade: RegistryAuthorityGrade | None = None,
    ) -> RegistryAuthorityCapture:
        """Capture a law-selected inspection or grade-admitted snapshot from this generation.

        ``grade=None`` selects the static inspection; supplying a grade selects
        the snapshot admission path. The capture compares current against every
        coordinate read from the same admitted generation in this process.
        """
        normalized = Modelo(modelo_id).value
        projection: RegistryAuthorityProjection
        if grade is None:
            directory = self.modelo_directory(normalized)
            selected = select_revision_metadata(directory, filing_year=filing_year, period=period, on=on)
            revision = self.revision(normalized, str(selected.id))
            modelo = directory.materialize(revision)
            legal_ids, source_ids = collect_snapshot_ref_ids(modelo, revision)
            projection = RegistryRevisionInspection.from_revision(
                modelo=modelo,
                revision=revision,
                source_root=None,
                sources={source_id: self.source_reference(source_id) for source_id in source_ids},
                legal_ref_ids=frozenset(legal_ids),
            )
        else:
            projection = self.snapshot(normalized, filing_year=filing_year, period=period, on=on, grade=grade)
        return RegistryAuthorityCapture(
            projection=projection,
            comparison_domain=_published_capture_domain(self.generation),
            generation=_REGISTRY_CAPTURE_GENERATION,
        )

    def read_current_coordinate(self) -> RegistryAuthorityCurrentCoordinate:
        """Return the current coordinate captures from this generation compare against."""
        return RegistryAuthorityCurrentCoordinate(
            comparison_domain=_published_capture_domain(self.generation),
            generation=_REGISTRY_CAPTURE_GENERATION,
        )

    def source_evidence(self, source_reference_id: str) -> PublishedSourceEvidence:
        """Load one publisher-captured public source payload."""
        value = self._reader.load(
            EvidenceComponentQuery(source_reference_id, AuthorityComponentKind.SOURCE_EVIDENCE),
            pin=self.generation,
        )
        if not isinstance(value, PublishedSourceEvidence):
            raise RegistryValidationError("source evidence component decoded to an unexpected type")
        return value


class IndexedRegistryAuthority:
    """Own the admitted SQLite reader and issue generation-pinned operation leases."""

    def __init__(self, descriptor_path: Path) -> None:
        """Open one descriptor-selected generation without hydrating components."""
        self._descriptor_path = descriptor_path.resolve()
        self._reader = SQLiteAuthorityReader(self._descriptor_path)
        self._operation = PinnedAuthorityOperation(self._reader, self._reader.pin())
        self._descriptor_digest = sha256_hex(self._descriptor_path.read_bytes())
        self._retired_readers: list[SQLiteAuthorityReader] = []
        self._reader_lock = RLock()

    @contextmanager
    def operation(self) -> Generator[PinnedAuthorityOperation]:
        """Pin one reader incarnation for a complete application operation."""
        reader, operation = self._authority_for_operation()
        try:
            with reader.lease() as generation:
                if generation != operation.generation:
                    raise RegistrySnapshotError("authority operation generation disagrees with its reader lease")
                with validating_governed_facts(operation):
                    yield operation
        finally:
            self._close_retired_readers()

    def close(self) -> None:
        """Close the reader after every operation lease has ended."""
        with self._reader_lock:
            self._reader.close()
            for reader in self._retired_readers:
                reader.close()
            self._retired_readers.clear()

    def _authority_for_operation(self) -> tuple[SQLiteAuthorityReader, PinnedAuthorityOperation]:
        """Return the shared operation cache for the currently admitted reader generation."""
        with self._reader_lock:
            descriptor_digest = sha256_hex(self._descriptor_path.read_bytes())
            if descriptor_digest == self._descriptor_digest:
                return self._reader, self._operation
            replacement = SQLiteAuthorityReader(self._descriptor_path)
            self._retired_readers.append(self._reader)
            self._reader = replacement
            self._operation = PinnedAuthorityOperation(replacement, replacement.pin())
            self._descriptor_digest = descriptor_digest
            return replacement, self._operation

    def _close_retired_readers(self) -> None:
        """Close old generations once their last in-flight operation releases."""
        with self._reader_lock:
            still_leased: list[SQLiteAuthorityReader] = []
            for reader in self._retired_readers:
                if reader.active_leases:
                    still_leased.append(reader)
                else:
                    reader.close()
            self._retired_readers = still_leased


_BUNDLED_AUTHORITY_DESCRIPTOR_PARTS = ("registry", "authority", "authority.current.json")
_bundled_indexed_authority_lock = RLock()
_bundled_indexed_authority: IndexedRegistryAuthority | None = None


def bundled_indexed_authority() -> IndexedRegistryAuthority:
    """Return the process-shared descriptor-following indexed authority owner."""
    global _bundled_indexed_authority
    with _bundled_indexed_authority_lock:
        if _bundled_indexed_authority is None:
            _bundled_indexed_authority = IndexedRegistryAuthority(bundled_authority_descriptor_path())
        return _bundled_indexed_authority


def bundled_authority_descriptor_path() -> Path:
    """Return the installed selector for the content-addressed SQLite generation."""
    return _bundled_path(*_BUNDLED_AUTHORITY_DESCRIPTOR_PARTS)
