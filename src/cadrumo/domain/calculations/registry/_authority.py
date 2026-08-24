"""Validated access point for registry-backed modelo definitions.

:class:`ValidatedRegistryAuthority` is the production boundary for all registry
access. It loads TOML sources via the compiler in ``_loader``, compiles them
into :class:`ModeloDefinition` and :class:`ModeloRevision` objects, and
produces :class:`RegistrySnapshot` instances on demand for each filing context.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from pathlib import Path

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
from ._ids import RevisionId
from ._loader import collect_registry_tree_fingerprints, load_registry_tree
from ._schema import DeadlineWindowDefinition, ModeloDefinition, ModeloRevision, RegistryCatalogues, RegistrySnapshot
from ._snapshot import _build_validated_snapshot
from ._source_evidence_fingerprint import collect_source_evidence_fingerprints
from ._static_inspection import RegistryRevisionInspection
from ._supplementary_orden import collect_supplementary_orden_fingerprints, compile_supplementary_ordenes
from ._supported_filing_years import SupportedFilingYearGap, audit_supported_filing_years
from ._temporal import select_revision
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

    def __hash__(self) -> int:
        return hash(self.digest)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, _FingerprintKey) and self.digest == other.digest


def _fingerprint_key[T: tuple[tuple[object, ...], ...]](fingerprints: T) -> _FingerprintKey[T]:
    """Digest one fingerprint tuple set into an O(1)-hashable cache key."""
    digest = hashlib.sha256()
    for entry in fingerprints:
        for field in entry:
            digest.update(str(field).encode("utf-8"))
            digest.update(b"\x1f")
        digest.update(b"\x1e")
    return _FingerprintKey(digest=digest.hexdigest(), fingerprints=fingerprints)


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

    @classmethod
    def load(cls, root: Path, *, source_root: Path) -> ValidatedRegistryAuthority:
        """Load registry TOML and construct a reusable :class:`ValidatedRegistryAuthority` instance."""
        resolved_root = root.expanduser().resolve()
        resolved_source_root = source_root.expanduser().resolve()
        return _load_authority(
            resolved_root,
            resolved_source_root,
            resolve_registry_identity(
                resolved_root,
                collect_fingerprints=collect_registry_identity_fingerprints,
            ),
            _fingerprint_key(collect_source_evidence_fingerprints(resolved_source_root)),
        )

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
        """Return a cached validated :class:`RegistrySnapshot` for one filing context.

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
    is backed by :func:`_load_authority`'s LRU cache, so repeated calls
    within one process are free.

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


#: Refusals from :func:`_load_authority`, keyed exactly as its ``lru_cache`` is.
#:
#: ``lru_cache`` memoises returns and NOT exceptions, so a registry that refuses
#: re-runs the whole multi-second validation for every caller. That is invisible
#: while the tree is green and pathological the moment it is not: with validation
#: failing, a full test collection re-validated per module and stopped terminating.
#: Caching the refusal changes nothing about the verdict -- the same error, with
#: the same enumeration, is raised on every call -- it is computed once.
_AUTHORITY_LOAD_FAILURES: dict[
    tuple[Path, Path, RegistryIdentity, _FingerprintKey[_SourceEvidenceFingerprints]],
    Exception,
] = {}


def _load_authority(
    root: Path,
    source_root: Path,
    identity: RegistryIdentity,
    source_evidence_key: _FingerprintKey[_SourceEvidenceFingerprints],
) -> ValidatedRegistryAuthority:
    """Load and validate one authority, memoising refusal as well as success."""
    failure_key = (root, source_root, identity, source_evidence_key)
    cached_failure = _AUTHORITY_LOAD_FAILURES.get(failure_key)
    if cached_failure is not None:
        raise cached_failure
    try:
        return _load_validated_authority(root, source_root, identity, source_evidence_key)
    except Exception as exc:
        _AUTHORITY_LOAD_FAILURES[failure_key] = exc
        raise


def _clear_authority_load_caches() -> None:
    """Drop both memoised outcomes, successes and refusals together.

    Clearing only the success cache would leave a refusal from a previous tree
    state answering for a tree that has since been repaired, which is the exact
    staleness a cache clear exists to remove.
    """
    _load_validated_authority.cache_clear()
    _AUTHORITY_LOAD_FAILURES.clear()


_load_authority.cache_clear = _clear_authority_load_caches  # type: ignore[attr-defined]


@lru_cache(maxsize=16)
def _load_validated_authority(
    root: Path,
    source_root: Path,
    identity: RegistryIdentity,
    source_evidence_key: _FingerprintKey[_SourceEvidenceFingerprints],
) -> ValidatedRegistryAuthority:
    _source_evidence_fingerprint = source_evidence_key.fingerprints
    authority = _construct_authority(root, source_root, _source_evidence_fingerprint, identity=identity)
    # A persisted green verdict keyed by the same tree identity this lru_cache
    # keys on lets an immutable tree skip the multi-second re-validation. The
    # build and continuous integration are the validation gate; the runtime
    # asserts identity only. A mismatch or a foreign verdict re-validates in
    # full and rewrites the verdict.
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
    if catalogues.supported_filing_years is None:
        raise RegistryValidationError("registry has no supported_filing_years catalogue")
    supplementary_ordenes = compile_supplementary_ordenes(
        root,
        source_root=source_root,
        modelos=modelos,
        sources=catalogues.sources,
        supported_filing_years=catalogues.supported_filing_years.years,
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
        # so this lru_cache invalidates when the manifest changes on disk.
        _authorization_manifest=load_authorization_manifest(root),
        _supported_filing_year_gaps=audit_supported_filing_years(
            modelos,
            catalogue=catalogues.supported_filing_years,
            sources=catalogues.sources,
        ),
    )
    return authority


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
