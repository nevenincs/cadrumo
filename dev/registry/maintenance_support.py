"""Development-owned registry maintenance implementations."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Iterable, Iterator, Mapping
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Final, Literal, Protocol

from pydantic import Field, TypeAdapter, ValidationError

from cadrumo import __version__
from cadrumo.core.atomic_write import atomic_write_best_effort_text
from cadrumo.core.directory_scan import scan_directory
from cadrumo.core.hashing import blake2b_hex
from cadrumo.core.period import RegistrySelectorPeriodCode
from cadrumo.core.prose_elision import ElidedProse
from cadrumo.core.resources import bundled_path
from cadrumo.domain.calculations.registry import authority as _authority
from cadrumo.domain.calculations.registry.authority import (
    _authority_load_barrier,
    _authority_load_states,
    _authority_state_lock,
    _guard_authority_process,
)
from cadrumo.domain.calculations.registry.condition_mode import ConditionModeField
from cadrumo.domain.calculations.registry.errors import RegistryLoadError
from cadrumo.domain.calculations.registry.export import (
    CasillaId,
    ExportFieldDefinition,
    ModeloRevision,
    ResolvedExportEndpointPath,
    derive_export_layouts_from_bindings,
)
from cadrumo.domain.calculations.registry.ids import CrossReferenceId, OracleId
from cadrumo.domain.calculations.registry.schema import ModeloDefinition, RegistryCatalogues
from cadrumo.domain.calculations.registry.static_inspection import (
    BindingId,
    LegalRefId,
    ModeloId,
    ProjectionEndpointDeclaration,
    RevisionId,
)
from dev.registry.compiler.authority_lifecycle import (
    SILENT_REGISTRY_AUTHORITY_LIFECYCLE_OBSERVER,
    RegistryAuthorityLifecycleObserver,
)
from dev.registry.compiler.fact_providers import reset_registered_fact_providers
from dev.registry.compiler.identity import (
    _LOGGER,
    REGISTRY_IDENTITY_SCHEMA_VERSION,
    FingerprintTuples,
    RegistryIdentityStamp,
    registry_identity_stamp_location,
)
from dev.registry.compiler.loader import (
    collect_registry_tree_fingerprints as collect_registry_identity_fingerprints,
)
from dev.registry.compiler.loader import (
    load_modelo_directory,
    load_modelo_file,
)
from dev.registry.compiler.m303_orden_census_artefact import (
    EXTRACTOR_VERSION,
    M303_ORDEN_CENSUS_SCHEMA_VERSION,
    M303AnnualOrdenCensusArtefact,
    M303AnnualOrdenSourceCensus,
)
from dev.registry.compiler.m303_orden_manifest import (
    UTF_8_ENCODING,
    M303AnnualOrdenGeneratedManifest,
    SourceReference,
    SourceRefId,
    _check_manifest_with_censuses,
    _generate_manifest_with_censuses,
    _render_generated_manifest,
)
from dev.registry.compiler.verdict_cache import (
    VERDICT_OUTCOME_GREEN,
    RegistryValidationVerdict,
    compute_shipped_verdict_key,
    shipped_verdict_location,
    write_verdict,
)
from dev.registry.parity.external_grounding import (
    ExternalGroundingModel,
    ExternalOracleCorpus,
    FilingYear,
    ManualWorkedExamplePayload,
    OraclePayload,
    RentaWebOpenReplayPayload,
)
from dev.registry.parity.live_parity import LiveParityOracle, _ParityModel
from dev.registry.parity.renta_web_open_replay_corpus import replay_corpus_directory

from .compiler.corpus_catalogue import (
    GeneratedArtifactSource,
    RegistrySourceKind,
    RegistryValidationError,
    verify_source_file,
)


class OracleEnvironment(StrEnum):
    """Runtime environment classification for oracle catalogue entries.

    ``PRODUCTION`` � the oracle is safe to call against the live AEAT surface.
    ``TEST_ENVIRONMENT`` � the oracle targets a sandboxed / integration-test
    surface only and must not be invoked from production callers.
    ``BOTH`` � the oracle is safe under either classification (e.g., public
    read-only surfaces that carry no production-state side-effect).
    """

    PRODUCTION = "production"
    TEST_ENVIRONMENT = "test_environment"
    BOTH = "both"


def reset_registry_caches(
    *, lifecycle_observer: RegistryAuthorityLifecycleObserver = SILENT_REGISTRY_AUTHORITY_LIFECYCLE_OBSERVER
) -> None:
    """Drop every memoised registry layer so the next read recompiles from disk.

    The compiled-tree lru, the authority load caches and the tree-fingerprint
    cache are one staleness surface: clearing a subset leaves a later layer
    answering from a tree state an earlier layer has already forgotten. Callers
    that swap the registry root or rewrite bundled TOML need all three, so the
    package exposes the whole reset rather than its parts.
    """
    _guard_authority_process()
    from dev.registry.compiler.loader import _load_registry_tree_cached
    from dev.registry.compiler.loader_fingerprints import clear_fingerprint_cache

    lifecycle_observer.registry_cache_reset_requested()
    with _authority_load_barrier.reset():
        lifecycle_observer.registry_cache_reset_acquired()
        _invalidate_authority_generations()
        _load_registry_tree_cached.cache_clear()
        clear_fingerprint_cache()
        reset_registered_fact_providers()


def stamp_bundled_registry_release(
    registry_root: Path, *, package_version: str = __version__
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
        registry_fingerprints=fingerprints, registry_root=resolved, package_version=package_version
    )
    verdict_path = shipped_verdict_location(resolved)
    stamp_bundled_verdict(identity_digest=stamp.tree_digest, output_path=verdict_path, package_version=package_version)
    return StampedRegistryRelease(identity_path=registry_identity_stamp_location(resolved), verdict_path=verdict_path)


def resolve_record_design_binary(
    root: Path, sources: Mapping[str, GeneratedArtifactSource], *, source_ref: str, filing_year: int, design_epoch: str
) -> ResolvedRecordDesignBinary:
    """Select and verify one exact official binary for a filing-year design epoch.

    The caller supplies the authored source reference and design epoch; this
    function deliberately does not infer either from a revision id, filename,
    or neighbouring export tree. The source catalogue remains the sole place
    that records which bundled official binary is authoritative. A selection
    without an explicit epoch, a complete applicability claim, or a matching
    byte-exact binary is refused before a parser can consume it.
    """
    if not design_epoch.strip():
        raise RegistryValidationError("record-design selection requires a non-blank design epoch")
    source = sources.get(source_ref)
    if source is None:
        raise RegistryValidationError(f"record-design source {source_ref!r} is not declared in the source catalogue")
    if source.id != source_ref:
        raise RegistryValidationError(f"source catalogue key {source_ref!r} does not match source id {source.id!r}")
    if source.kind is not RegistrySourceKind.RECORD_DESIGN:
        raise RegistryValidationError(f"source {source_ref!r} is not a record-design binary")
    if source.record_design_epoch is None:
        raise RegistryValidationError(f"record-design source {source_ref!r} does not declare a design epoch")
    if source.record_design_epoch != design_epoch:
        raise RegistryValidationError(
            f"record-design source {source_ref!r} declares design epoch "
            f"{source.record_design_epoch!r}, not requested {design_epoch!r}"
        )
    if source.applies_from is None:
        raise RegistryValidationError(f"record-design source {source_ref!r} does not declare applies_from")
    if not source.applies_across(date(filing_year, 1, 1), date(filing_year, 12, 31)):
        raise RegistryValidationError(
            f"record-design source {source_ref!r} does not apply to filing year {filing_year}"
        )
    return ResolvedRecordDesignBinary(source=source, path=verify_source_file(root, source))


def resolved_export_casillas(revision: ModeloRevision) -> frozenset[CasillaId]:
    """Return the complete set of casillas the resolved layouts of ``revision`` carry."""
    return frozenset(endpoint.casilla_id for endpoint in resolved_export_endpoints(revision))


def resolved_export_fields(revision: ModeloRevision) -> tuple[ResolvedExportField, ...]:
    """Return every field the resolved layouts of ``revision`` carry, in record order.

    Use this where the question is about FIELDS - their widths, types, declared
    scales, or how a field compares with the ones beside it in its record.
    :func:`resolved_export_endpoints` answers the question about CASILLAS and
    silently omits every field that carries none, so a completeness measurement
    over fields cannot be taken from it.

    Resolved through the same binding derivation the endpoint walk resolves
    through, so a binding-derived record's fields are present here exactly as
    they are there. That derivation is called HERE rather than by the caller:
    three linkage paths reach a casilla on this surface, a walk that knows only
    some of them under-reports it, and the walk is written once.
    """
    return tuple(
        ResolvedExportField(
            layout_id=str(layout.id),
            record_id=str(record.id),
            casilla_id=field.casilla_id if field.casilla_id is not None else field.endpoint_casilla_id,
            field=field,
        )
        for layout in derive_export_layouts_from_bindings(revision)
        for record in layout.records
        for field in record.fields
    )


def load_bundled_external_oracle_inventory() -> ExternalOracleInventory:
    """Inventory every external-oracle payload across both corpora.

    The two corpora no longer share a root -- the manual worked examples are
    packaged data, the Renta WEB Open replays are repository-only development
    artefacts -- so each is located through its own entry in
    :data:`_ORACLE_CORPUS_DIRECTORIES`.

    Returns:
        An :class:`ExternalOracleInventory` carrying the attributed evidence
        and every payload whose evidence could not be attributed.

    Raises:
        RegistryValidationError: When a corpus directory is absent. An empty
            inventory and a clean one are indistinguishable downstream, so a
            missing corpus fails loudly rather than reporting nothing to check.
    """
    evidence: list[ExternalOracleEvidence] = []
    unattributed: list[UnattributedOraclePayload] = []
    for corpus, locate_directory in _ORACLE_CORPUS_DIRECTORIES.items():
        for payload_path in scan_directory(locate_directory(), pattern="modelo-*.json"):
            record = _read_oracle_payload(corpus, payload_path)
            if isinstance(record, UnattributedOraclePayload):
                unattributed.append(record)
            else:
                evidence.append(record)
    return ExternalOracleInventory(evidence=tuple(evidence), unattributed_payloads=tuple(unattributed))


def collect_applicability_declarations(
    modelos: Iterable[ModeloDefinition],
) -> tuple[CrossReferenceApplicabilityDeclaracion, ...]:
    """Return :class:`CrossReferenceApplicabilityDeclaracion` items for every cross-reference with predicates.

    Pure registry-data introspection: never reads profile facts, never
    invokes the evaluator. Cross-references with no predicates are
    omitted (the unconditionally-applicable default). Order is
    ``(modelo_id, revision_id, cross_reference_id)`` for deterministic
    audit output.

    Args:
        modelos: Iterable of :class:`ModeloDefinition` entries to scan.
    """
    declarations: list[CrossReferenceApplicabilityDeclaracion] = []
    for modelo in modelos:
        for revision in modelo.revisions.values():
            for cross_reference in revision.live_cross_references:
                if not cross_reference.applicability_predicates:
                    continue
                declarations.append(
                    CrossReferenceApplicabilityDeclaracion(
                        modelo_id=modelo.id,
                        revision_id=revision.id,
                        cross_reference_id=cross_reference.id,
                        applicability_condition_mode=cross_reference.applicability_condition_mode,
                        predicate_fields=tuple(
                            predicate.field for predicate in cross_reference.applicability_predicates
                        ),
                    )
                )
    return tuple(declarations)


def collect_orphan_oracle_ids(
    modelos: Iterable[ModeloDefinition], catalogue: LiveParityCatalogue
) -> tuple[OracleId, ...]:
    """Return catalogue oracle ids that no cross-reference binds.

    A registered-but-unused oracle indicates one of:

    - the oracle was registered for a future binding still in flight,
    - a cross-reference's oracle_id was renamed without updating the
      catalogue,
    - the binding was retired but the catalogue registration stayed.

    The audit surfaces the set so CI / dashboards can flag drift.
    Order is the catalogue's lexicographic order for deterministic
    output.

    Args:
        modelos: Iterable of :class:`ModeloDefinition` instances whose
            cross-reference bindings determine which oracle ids are in use.
        catalogue: The live parity catalogue to check for orphaned entries.
    """
    bound: set[OracleId] = set()
    modelo_tuple = tuple(modelos)
    for modelo in modelo_tuple:
        for revision in modelo.revisions.values():
            for cross_reference in revision.live_cross_references:
                if cross_reference.oracle_id is not None:
                    bound.add(cross_reference.oracle_id)
    return tuple(sorted(set(catalogue.ids()) - bound))


def audit_registry_oracle_bindings(
    modelos: Iterable[ModeloDefinition],
    catalogue: LiveParityCatalogue,
    *,
    environment: OracleEnvironment = OracleEnvironment.PRODUCTION,
) -> tuple[str, ...]:
    """Aggregate ``audit_oracle_bindings`` over an iterable of modelos.

    Application bootstrap calls this once per startup to surface every
    binding-vs-catalogue mismatch in a single report alongside the
    registry-validator's own failures. The function preserves the order
    of the input iterable so the report is deterministic.

    Args:
        modelos: Iterable of :class:`ModeloDefinition` instances to audit.
        catalogue: The live parity catalogue to validate against.
        environment: Target oracle environment classification.
    """
    failures: list[str] = []
    for modelo in modelos:
        failures.extend(audit_oracle_bindings(modelo, catalogue, environment=environment))
    return tuple(failures)


def load_modelo_path(path: Path) -> ModeloDefinition:
    """Load a :class:`ModeloDefinition` from either supported on-disk layout."""
    resolved = path.resolve()
    if resolved.is_file():
        return load_modelo_file(resolved)
    if resolved.is_dir():
        return load_modelo_directory(resolved)
    raise RegistryLoadError(f"{resolved}: modelo source does not exist")


def render_m303_annual_orden_manifest(*, source_root: Path, sources: Mapping[SourceRefId, SourceReference]) -> str:
    """Render the generated registry artefact in canonical TOML order."""
    return _render_generated_manifest(generate_m303_annual_orden_manifest(source_root=source_root, sources=sources))


def check_m303_annual_orden_census_artefact(
    *, artefact_path: Path, source_root: Path, sources: Mapping[SourceRefId, SourceReference]
) -> None:
    """Refuse a missing, hand-edited, or stale committed census artefact.

    The build-side half of the annual-Orden proof. It re-extracts from the pinned
    BOE corpus and compares against the committed bytes, so it is the only thing
    standing between a stale census and every runtime that now trusts one. The
    runtime cannot perform this check itself without paying the parse this
    artefact exists to remove, which is exactly why it is a build and
    continuous-integration gate.

    Raises:
        RegistryLoadError: When the artefact is absent, unreadable, or does not
            equal a fresh extraction.
    """
    if not artefact_path.is_file():
        raise RegistryLoadError(f"annual Orden census artefact is missing: {artefact_path}")
    expected = render_m303_annual_orden_census_artefact(source_root=source_root, sources=sources)
    try:
        actual = artefact_path.read_text(encoding=UTF_8_ENCODING)
    except OSError as exc:
        raise RegistryLoadError(f"annual Orden census artefact cannot be read: {artefact_path}") from exc
    if actual != expected:
        raise RegistryLoadError(f"annual Orden census artefact is stale: regenerate {artefact_path}")


def check_m303_annual_orden_manifest(
    *, manifest_path: Path, source_root: Path, sources: Mapping[SourceRefId, SourceReference]
) -> M303AnnualOrdenGeneratedManifest:
    """Refuse a missing, manually edited, or stale generated annual Orden artefact."""
    return _check_manifest_with_censuses(manifest_path=manifest_path, source_root=source_root, sources=sources)[0]


class GeneratedArtifactInspection(Protocol):
    """The static revision facts required to verify a generated artefact."""

    @property
    def modelo_id(self) -> ModeloId:
        """Return the modelo identity."""
        ...

    @property
    def revision_id(self) -> RevisionId:
        """Return the revision identity."""
        ...

    @property
    def revision_source_refs(self) -> tuple[SourceRefId, ...]:
        """Return the revision's source references."""
        ...

    @property
    def legal_ref_ids(self) -> frozenset[LegalRefId]:
        """Return the revision's legal-reference identities."""
        ...

    @property
    def casilla_ids(self) -> frozenset[CasillaId]:
        """Return the declared casilla identities."""
        ...

    @property
    def binding_ids(self) -> frozenset[BindingId]:
        """Return the declared binding identities."""
        ...

    @property
    def projection_endpoints(self) -> tuple[ProjectionEndpointDeclaration, ...]:
        """Return the declared projection endpoints."""
        ...

    @property
    def sources(self) -> Mapping[SourceRefId, GeneratedArtifactSource]:
        """The sources this revision cites, read-only.

        Declared as a property rather than an attribute so the protocol matches
        covariantly. A mutable attribute is invariant, which made a carrier
        holding a richer source type fail to satisfy this protocol even though
        every value satisfies :class:`GeneratedArtifactSource`. The verifier
        only reads these, so read-only is the honest declaration.
        """
        ...


def stamp_bundled_verdict(
    *, identity_digest: str, output_path: Path, package_version: str = __version__
) -> RegistryValidationVerdict:
    """Write the install-stable bundled-tree verdict at ``output_path``.

    Called by the release build against the tree it is packaging, immediately
    after that tree's identity stamp is written, so the first end-user touch of
    this release skips validation. The caller supplies the identity digest so
    this module adds no loader import edge and derives no identity of its own.

    Returns:
        The written :class:`RegistryValidationVerdict`.
    """
    key = compute_shipped_verdict_key(identity_digest=identity_digest, package_version=package_version)
    verdict = RegistryValidationVerdict(verdict_key=key, package_version=package_version, outcome=VERDICT_OUTCOME_GREEN)
    write_verdict(output_path, verdict)
    return verdict


def _invalidate_authority_generations() -> None:
    """Invalidate all authority incarnations as one exclusive reset transition."""
    with _authority_state_lock:
        _authority._authority_generation += 1
        _authority._authority_reset_epoch = int(_authority._authority_reset_epoch) + 1
        _authority_load_states.clear()


@dataclass(frozen=True, slots=True)
class StampedRegistryRelease:
    """The two records the release build stamps beside a packaged registry tree."""

    identity_path: Path
    verdict_path: Path


@dataclass(frozen=True)
class ResolvedRecordDesignBinary:
    """One verified official binary selected for a target design epoch."""

    source: GeneratedArtifactSource
    path: Path


def resolved_export_endpoints(revision: ModeloRevision) -> tuple[ResolvedExportEndpoint, ...]:
    """Return every casilla the resolved layouts of ``revision`` carry, with its path.

    Three linkage paths reach a casilla on the resolved surface and a walk that
    skips any one of them under-reports it:

    - ``field`` - the field names its casilla directly through ``casilla_id``;
    - ``projection`` - the field names a ``projection_ref`` instead, resolved
      through :attr:`~.schema_exports.ExportFieldDefinition.endpoint_casilla_id`;
    - ``row_field`` - the record's ``row_field_casilla_ids`` maps a repeated
      row's slot to its casilla, on the record rather than on any field.

    :func:`fixed_width_record_casilla_ids` deliberately covers a narrower scope
    for the exemption and parity gates that own it.

    What this covers is every CASILLA the resolved layouts carry, by all three
    linkage paths - and nothing more. It is not the whole resolved surface. An
    endpoint IS a casilla, so a field reaching none has no endpoint form here at
    all: :attr:`ResolvedExportEndpoint.casilla_id` is non-optional, and a
    filing-grade amount homed to a producer key carries no casilla. Two such
    amounts on modelo 200's ``DP200014B`` page were invisible to a screen that
    took this function for the whole surface, and sat unscaled beside their
    scaled siblings while that screen reported the modelo clean.

    So a completeness measurement over CASILLAS wants this function, and one
    over FIELDS wants :func:`resolved_export_fields`, which returns every field
    of every resolved record whether or not it reaches a casilla.
    """
    return tuple(_walk_resolved_endpoints(revision))


@dataclass(frozen=True, slots=True)
class ResolvedExportField:
    """One field the resolved layouts carry, whether or not it reaches a casilla.

    The sibling of :class:`ResolvedExportEndpoint`, which is keyed on the
    casilla and so cannot represent a field that reaches none: its
    ``casilla_id`` is non-optional by design, because an endpoint IS a casilla
    on the surface. That leaves a real population unrepresentable rather than
    filtered out - a filing-grade amount homed to a producer key carries no
    casilla, which is how the official designs carry several rectificativa
    importes - and a measurement over fields rather than over casillas needs it.

    ``casilla_id`` is the casilla the field reaches by either linkage that
    belongs to a FIELD, direct or projected, and ``None`` when it reaches
    neither. The record-level ``row_field`` linkage has no field of its own and
    is therefore absent here; :func:`resolved_export_endpoints` is what covers
    it.
    """

    layout_id: str
    record_id: str
    casilla_id: CasillaId | None
    field: ExportFieldDefinition


def _manual_worked_example_directory() -> Path:
    """Return the packaged AEAT Manual practico worked-example corpus directory.

    This corpus DOES still ship inside the wheel, so it is located through the
    bundled-resource loader exactly as before.

    Returns:
        The packaged ``corpus/manual_oracles`` path.
    """
    return Path(bundled_path("corpus", "manual_oracles"))


#: Where each oracle corpus lives, resolved on demand.
#:
#: The two corpora deliberately do NOT share a root, and the split is stated
#: here rather than hidden behind one locator:
#:
#: * ``RENTA_WEB_OPEN_REPLAY`` is a repository-only development artefact under
#:   ``dev/registry/parity/parity_replays/renta_web_open``. It does not ship,
#:   and it is reached through the owning module's locator so exactly one place
#:   decides where those captures are and refuses their absence.
#: * ``AEAT_MANUAL_WORKED_EXAMPLE`` is packaged data under ``_data/corpus``
#:   and is reached through the bundled-resource loader.
#:
#: The values are callables rather than paths because the repository locator
#: raises when its directory is missing: resolving at import time would make an
#: absent capture corpus an import failure of this whole module rather than a
#: loud failure of the fold that needs it.
_ORACLE_CORPUS_DIRECTORIES: Final[Mapping[ExternalOracleCorpus, Callable[[], Path]]] = {
    ExternalOracleCorpus.RENTA_WEB_OPEN_REPLAY: replay_corpus_directory,
    ExternalOracleCorpus.AEAT_MANUAL_WORKED_EXAMPLE: _manual_worked_example_directory,
}


class ExternalOracleInventory(ExternalGroundingModel):
    """Every bundled oracle payload, split into attributed evidence and attribution gaps."""

    evidence: tuple[ExternalOracleEvidence, ...]
    unattributed_payloads: tuple[UnattributedOraclePayload, ...]

    def casilla_ids_for(self, modelo: str, filing_year: int, period: str | None = None) -> frozenset[CasillaId]:
        """Return every oracle-grounded casilla id bundled for ``modelo`` and ``filing_year``.

        Unions across corpora: a manual worked-example figure is an equally
        real, independent AEAT authority alongside a simulator replay capture.
        """
        return frozenset(
            casilla_id
            for item in self.evidence
            if item.modelo == modelo and item.filing_year == filing_year and (item.period == period)
            for casilla_id in item.casilla_ids
        )

    @property
    def corpora_for(self) -> Mapping[tuple[str, int, str | None], tuple[ExternalOracleCorpus, ...]]:
        """Map each attributed ``(modelo, filing_year, period)`` to its corpora."""
        grouped: dict[tuple[str, int, str | None], set[ExternalOracleCorpus]] = {}
        for item in self.evidence:
            grouped.setdefault((item.modelo, item.filing_year, item.period), set()).add(item.corpus)
        return {key: tuple(sorted(value)) for key, value in grouped.items()}

    @property
    def attributed_coordinates(self) -> tuple[tuple[str, int, str | None], ...]:
        """Every ``(modelo, filing_year, period)`` carrying bundled evidence."""
        return tuple(sorted({(item.modelo, item.filing_year, item.period) for item in self.evidence}))

    @property
    def attributed_filing_years(self) -> tuple[tuple[str, int], ...]:
        """Every ``(modelo, filing_year)`` carrying bundled oracle evidence."""
        return tuple(sorted({(modelo, year) for modelo, year, _period in self.attributed_coordinates}))


def _read_oracle_payload(
    corpus: ExternalOracleCorpus, payload_path: Path
) -> ExternalOracleEvidence | UnattributedOraclePayload:
    """Read one bundled payload into typed evidence, attributed to a modelo and year.

    Every payload is parsed through its corpus's strict model first, including
    one that cannot be attributed at all: a file the fold cannot place is still
    a file whose contents must be well-formed, and validating only the
    attributable ones would leave the boundary open exactly where the least is
    known about the payload.

    Attribution reads the DECLARED axes first and falls back to the
    ``modelo-<id>-<year>-<scenario>.json`` naming convention, rather than
    keying on the name alone. Both are real statements of the same fact, and a
    payload declaring its modelo and filing year has said where its figures
    belong whatever it is called; keying solely on the name made a naming slip
    silently demote a fully self-describing payload to an attribution gap, where
    its AEAT figures sit outside both directions of the honesty relation. The
    Renta WEB Open replays declare neither axis, so the name remains the only
    reading for that corpus.

    Where both sources speak, they must agree. A disagreement is refused by
    name, quoting both readings, rather than resolved by preferring one side:
    the two disagree only when one of them is wrong, and which one is wrong is
    not something this function can know. Silently taking the declared value
    would attribute figures to a revision the file's own name denies.
    """
    payload = _parse_oracle_payload(corpus, payload_path)
    name_modelo_id, name_filing_year = _attribution_from_payload_name(payload_path)
    _validate_oracle_payload_name_matches(payload, payload_path, name_modelo_id, name_filing_year)
    return _attribute_oracle_payload(corpus, payload_path, payload, name_modelo_id, name_filing_year)


def write_registry_identity_stamp(
    *, registry_fingerprints: FingerprintTuples, registry_root: Path, package_version: str = __version__
) -> RegistryIdentityStamp:
    """Write the install-stable identity stamp beside ``registry_root``.

    Called by the release build against the tree it is packaging. The caller
    supplies the fingerprints so this module adds no loader import edge, which
    is the same arrangement the verdict stamper uses.

    Returns the stamp rather than its path so the caller can key dependent
    records on the digest it just wrote, instead of re-deriving that digest or
    reading the file back -- either of which would be a second derivation of the
    thing this module exists to own. The path is
    :func:`registry_identity_stamp_location` of the same root.

    Returns:
        The written :class:`RegistryIdentityStamp`.
    """
    resolved = registry_root.resolve()
    stamp = RegistryIdentityStamp(
        schema_version=REGISTRY_IDENTITY_SCHEMA_VERSION,
        package_version=package_version,
        tree_digest=compute_installed_tree_digest(
            registry_fingerprints, registry_root=resolved, package_version=package_version
        ),
        entry_count=len(registry_fingerprints),
    )
    atomic_write_best_effort_text(
        registry_identity_stamp_location(resolved), stamp.model_dump_json(), encoding=UTF_8_ENCODING
    )
    return stamp


def audit_oracle_bindings(
    modelo: ModeloDefinition,
    catalogue: LiveParityCatalogue,
    *,
    environment: OracleEnvironment = OracleEnvironment.PRODUCTION,
) -> tuple[str, ...]:
    """Inspect every cross-reference binding in a modelo against the catalogue.

    Returns a tuple of human-readable failure strings, one per cross-
    reference whose bound oracle id either is not registered in the
    catalogue or is registered under an incompatible environment. Cross-
    references with no binding are skipped silently.

    A declared binding must resolve through the supplied catalogue. An
    empty catalogue is valid only when no cross-reference declares an
    oracle binding.

    The function never raises and never performs any network operation.
    Failure aggregation is the caller's job.

    Args:
        modelo: The :class:`ModeloDefinition` whose cross-reference bindings to audit.
        catalogue: :class:`LiveParityCatalogue` registering known oracles by id
            and environment; bindings unresolved against it produce failures.
        environment: :class:`OracleEnvironment` (defaults to ``PRODUCTION``)
            each binding must be registered under to be considered resolved.
    """
    failures: list[str] = []
    for revision in modelo.revisions.values():
        for cross_reference in revision.live_cross_references:
            oracle_id = cross_reference.oracle_id
            if oracle_id is None:
                continue
            try:
                oracle = catalogue.lookup(oracle_id, environment=environment)
            except RegistryValidationError as exc:
                failures.append(
                    f"modelo {modelo.id} revision {revision.id} cross-reference "
                    f"{cross_reference.id} bound oracle {oracle_id!r}: {exc}"
                )
                continue
            if (cross_reference.surface, oracle.surface_kind) not in _COMPATIBLE_SURFACE_PAIRS:
                failures.append(
                    f"modelo {modelo.id} revision {revision.id} cross-reference {cross_reference.id} "
                    f"surface {str(cross_reference.surface)!r} is not compatible with oracle "
                    f"{oracle_id!r} surface_kind {oracle.surface_kind!r}"
                )
    return tuple(failures)


class CrossReferenceApplicabilityDeclaracion(_ParityModel):
    """A registry-declared applicability shape for one cross-reference.

    The model is a structural read of the registry data � the audit
    surface emits this so CI / dashboards can see which bindings are
    profile-gated without re-evaluating any predicate. Decoupled from
    :class:`CrossReferenceApplicability` (the run-time evaluation
    result).
    """

    modelo_id: str = Field(min_length=1, max_length=128)
    revision_id: RevisionId
    cross_reference_id: CrossReferenceId
    applicability_condition_mode: ConditionModeField
    predicate_fields: tuple[str, ...]


def generate_m303_annual_orden_manifest(
    *, source_root: Path, sources: Mapping[SourceRefId, SourceReference]
) -> M303AnnualOrdenGeneratedManifest:
    """Derive the exact source-integrity manifest from the pinned BOE corpus.

    Takes no ``registry_root``, so it always EXTRACTS. That is what the generator
    needs: an artefact regenerated from a shipped copy of itself would agree with
    that copy by construction and could never detect drift.
    """
    return _generate_manifest_with_censuses(source_root=source_root, sources=sources)[0]


def render_m303_annual_orden_census_artefact(
    *, source_root: Path, sources: Mapping[SourceRefId, SourceReference]
) -> str:
    """Extract every pinned annual Orden and render the committed census artefact.

    Lives here rather than beside the artefact's other serialisation because it
    is the one direction that needs the EXTRACTOR, and the artefact module is
    deliberately free of that import edge. The rendering itself still belongs to
    the artefact module, so there remains exactly one place that decides what the
    committed bytes look like.

    Returns:
        The artefact text, exactly as the generator commits it.
    """
    _manifest, censuses = _generate_manifest_with_censuses(source_root=source_root, sources=sources)
    return render_m303_annual_orden_censuses(tuple(censuses[key] for key in sorted(censuses)))


def _walk_resolved_endpoints(revision: ModeloRevision) -> Iterator[ResolvedExportEndpoint]:
    for layout in derive_export_layouts_from_bindings(revision):
        for record in layout.records:
            for field in record.fields:
                if field.casilla_id is not None:
                    yield ResolvedExportEndpoint(str(layout.id), str(record.id), field.casilla_id, "field", field)
                    continue
                endpoint = field.endpoint_casilla_id
                if endpoint is not None:
                    yield ResolvedExportEndpoint(str(layout.id), str(record.id), endpoint, "projection", field)
            for casilla_id in record.row_field_casilla_ids.values():
                yield ResolvedExportEndpoint(str(layout.id), str(record.id), casilla_id, "row_field", None)


def _parse_oracle_payload(corpus: ExternalOracleCorpus, payload_path: Path) -> OraclePayload:
    """Parse one bundled payload through its corpus's strict model.

    Two refusals live here, both loud and neither tolerant of a shape nothing
    ships today. The model itself refuses a payload missing a field its corpus
    declares, carrying an undeclared key, or naming a ``source_kind`` outside
    :class:`~dev.registry.parity.external_oracle_corpus.ExternalOracleCorpus`.
    The cross-check then refuses a payload whose declared corpus token
    contradicts the directory it was found in -- the case a directory-keyed
    read would silently reclassify, reporting a provenance the figures do not
    have.

    Args:
        corpus: The corpus the containing directory belongs to, per
            :data:`_ORACLE_CORPUS_DIRECTORIES`.
        payload_path: The payload file to read.

    Raises:
        RegistryValidationError: When the payload violates its corpus's model,
            or declares a corpus token other than ``corpus``.
    """
    model = _ORACLE_PAYLOAD_MODELS[corpus]
    try:
        payload = model.model_validate(json.loads(payload_path.read_text(encoding=UTF_8_ENCODING)))
    except ValidationError as exc:
        raise RegistryValidationError(
            f"{payload_path.name}: bundled oracle payload does not satisfy {model.__name__}: {exc}"
        ) from exc
    if payload.source_kind is not None and payload.source_kind is not corpus:
        raise RegistryValidationError(
            f"{payload_path.name}: declared source_kind {payload.source_kind.value!r} contradicts "
            f"the corpus directory {payload_path.parent.name!r}, which holds the {corpus.value!r} corpus"
        )
    return payload


def _attribution_from_payload_name(payload_path: Path) -> tuple[ModeloId | None, int | None]:
    """Read the ``modelo-<id>-<year>-<scenario>.json`` naming convention off a payload.

    Returns ``(None, None)`` when the name does not follow the convention. The
    two axes are read together because the convention encodes them together: a
    name that fails the shape carries neither, so there is no partial reading to
    salvage.
    """
    parts = payload_path.stem.split("-")
    if len(parts) < 3 or parts[0] != "modelo" or (not parts[1]) or (not parts[2].isdigit()):
        return (None, None)
    return (parts[1], int(parts[2]))


def _validate_oracle_payload_name_matches(
    payload: OraclePayload, payload_path: Path, name_modelo_id: ModeloId | None, name_filing_year: int | None
) -> None:
    """Refuse a payload whose declared attribution contradicts its name."""
    if payload.modelo is not None and name_modelo_id is not None and (payload.modelo != name_modelo_id):
        raise RegistryValidationError(
            f"{payload_path.name}: payload modelo {payload.modelo!r} does not match filename modelo {name_modelo_id!r}"
        )
    if payload.filing_year is not None and name_filing_year is not None and (payload.filing_year != name_filing_year):
        raise RegistryValidationError(
            f"{payload_path.name}: payload filing_year {payload.filing_year!r} "
            f"does not match filename year {name_filing_year!r}"
        )


def _attribute_oracle_payload(
    corpus: ExternalOracleCorpus,
    payload_path: Path,
    payload: OraclePayload,
    name_modelo_id: ModeloId | None,
    name_filing_year: int | None,
) -> ExternalOracleEvidence | UnattributedOraclePayload:
    """Build attributed evidence, or retain an explicit attribution gap."""
    modelo_id = payload.modelo if payload.modelo is not None else name_modelo_id
    filing_year = payload.filing_year if payload.filing_year is not None else name_filing_year
    if modelo_id is None or filing_year is None:
        return UnattributedOraclePayload(
            corpus=corpus,
            payload_name=payload_path.name,
            gap="payload_name_lacks_modelo_and_filing_year",
            detail=(
                f"{payload_path.name}: the payload declares no modelo and filing year and its name does not "
                "encode modelo-<id>-<filing-year>, so its expected values cannot be attributed to a modelo revision"
            ),
        )
    return ExternalOracleEvidence(
        corpus=corpus,
        payload_name=payload_path.name,
        modelo=modelo_id,
        filing_year=filing_year,
        period=payload.period,
        casilla_ids=tuple(sorted(payload.expected_by_casilla_id)),
    )


def compute_installed_tree_digest(
    fingerprints: FingerprintTuples, *, registry_root: Path, package_version: str = __version__
) -> str:
    """Digest a tree into the install-stable identity the build stamps.

    The walked digest folds absolute paths and ``mtime_ns``, and neither
    survives packaging: the cohort builds the wheel from a snapshot of the
    enumerated source tree and installation rewrites mtimes and directory sizes. This
    derivation keys on the package version plus the sorted
    ``(relative-path, size, content-digest)`` of every registry FILE, all three
    byte-stable from the build machine to every install because the bundled tree
    is identical per release. Directory entries are dropped for the same
    packaging-instability reason.

    The CONTENT digest is what makes this an identity rather than a shape: path
    and size alone cannot separate two files of equal length, so a same-size edit
    anywhere in an installed tree would be invisible to a stamp that omitted it.
    It is not cheap -- measured at roughly 24 seconds over the real 17,548-file
    tree, dominated by first-touch reads rather than by hashing -- and that is
    affordable only because it is paid ONCE on the build machine per release
    while the runtime never pays it at all: a stamped install reads the digest in
    about two milliseconds, and an unstamped tree takes
    :func:`compute_walked_tree_digest`, which folds the tuples the caller already
    collected and reads nothing. The trade works in exactly one direction, which
    is why the walked derivation cannot borrow it and why the per-file bundled
    fingerprint leaves its content slot empty.

    This stats and reads every entry, so it is a BUILD-TIME derivation only.

    Returns:
        The hex SHA-256 install-stable identity of the tree.
    """
    resolved_root = registry_root.resolve()
    entries: list[tuple[str, int, str]] = []
    for path, size, _mtime_ns, _content_digest in fingerprints:
        candidate = Path(path)
        if not candidate.is_file():
            continue
        try:
            relative = candidate.resolve().relative_to(resolved_root).as_posix()
        except ValueError:
            relative = candidate.name
        entries.append((relative, size, _file_content_digest(candidate)))
    hasher = hashlib.sha256()
    hasher.update(_INSTALLED_DIGEST_LABEL)
    hasher.update(package_version.encode("utf-8"))
    for relative, size, content in sorted(entries):
        hasher.update(relative.encode("utf-8"))
        hasher.update(content.encode("utf-8"))
        hasher.update(str(size).encode("utf-8"))
    return hasher.hexdigest()


_COMPATIBLE_SURFACE_PAIRS: frozenset[tuple[str, str]] = frozenset(
    {
        ("open_simulator", "open_simulator"),
        ("integration_test_service", "integration_test_service"),
        ("public_read_surface", "iva_id_check"),
        ("public_read_surface", "file_validator"),
        ("authenticated_read_surface", "pre_filing_validator"),
        ("authenticated_simulator", "iva_id_check"),
    }
)


class LiveParityCatalogue:
    """Registry of live parity oracles keyed by oracle_id.

    Every modelo that wants live conformance verification declares an
    ``oracle_id`` in its registry cross-reference; the runtime looks the
    oracle up here. Catalogue registration is process-wide so adapters
    can self-register at import time.

    Every registration declares an explicit environment classification so
    that adapters targeting AEAT pre-production / test-NIF surfaces cannot
    leak into production code paths. The :func:`lookup` call requires an
    environment context; oracles registered as ``"production"`` only are
    invisible to test-environment lookups and vice versa. ``"both"`` is
    reserved for adapters whose surface is provably safe under either
    classification (e.g., pure read-only public services that never touch
    AEAT NIF state under any environment).
    """

    def __init__(self) -> None:
        """Initialise an empty environment-partitioned oracle registry."""
        self._oracles: dict[OracleId, LiveParityOracle] = {}
        self._environments: dict[OracleId, OracleEnvironment] = {}

    def register(self, oracle: LiveParityOracle, *, environment: OracleEnvironment) -> None:
        """Register an oracle under an explicit environment classification."""
        oracle_id = _validate_oracle_id(oracle.oracle_id)
        if oracle_id in self._oracles:
            raise RegistryValidationError(f"oracle_id {oracle_id!r} already registered")
        self._oracles[oracle_id] = oracle
        self._environments[oracle_id] = environment

    def lookup(
        self, oracle_id: OracleId, *, environment: OracleEnvironment = OracleEnvironment.PRODUCTION
    ) -> LiveParityOracle:
        """Return the registered oracle for the requested environment.

        Raises when the oracle is unknown, or when its declared environment
        does not include the requested context. Production lookups never
        return test-environment-only oracles; test-environment lookups never
        return production-only oracles.

        Returns:
            The :class:`LiveParityOracle` registered under ``oracle_id``.
        """
        oracle_id = _validate_oracle_id(oracle_id)
        try:
            oracle = self._oracles[oracle_id]
        except KeyError as exc:
            raise RegistryValidationError(f"unknown oracle_id {oracle_id!r}") from exc
        declared = self._environments[oracle_id]
        if declared == "both":
            return oracle
        if environment == "both":
            raise RegistryValidationError(
                f"oracle_id {oracle_id!r} declared environment {declared!r}; caller asked for unrestricted "
                "'both' which the catalogue does not vend"
            )
        if declared != environment:
            raise RegistryValidationError(
                f"oracle_id {oracle_id!r} declared environment {declared!r} is not available under requested "
                f"environment {environment!r}"
            )
        return oracle

    def environment_of(self, oracle_id: OracleId) -> OracleEnvironment:
        """Return the declared environment of a registered oracle.

        Returns:
            The :class:`OracleEnvironment` declared for ``oracle_id``.
        """
        oracle_id = _validate_oracle_id(oracle_id)
        try:
            return self._environments[oracle_id]
        except KeyError as exc:
            raise RegistryValidationError(f"unknown oracle_id {oracle_id!r}") from exc

    def is_registered(self, oracle_id: OracleId) -> bool:
        """Report whether an oracle is registered under ``oracle_id``.

        A membership check that ignores environment classification: it returns
        ``True`` for any registered oracle regardless of whether it is
        production-only, test-environment-only, or both. Use ``lookup`` when
        the environment-visibility rules must be enforced.

        Args:
            oracle_id: The catalogue key to test.

        Returns:
            ``True`` if an oracle is registered under ``oracle_id``.
        """
        oracle_id = _validate_oracle_id(oracle_id)
        return oracle_id in self._oracles

    def ids(self, *, environment: OracleEnvironment | None = None) -> tuple[OracleId, ...]:
        """Return oracle ids, optionally filtered to those visible under ``environment``."""
        if environment is None:
            return tuple(sorted(self._oracles))
        return tuple(
            sorted(
                [oracle_id for oracle_id, declared in self._environments.items() if declared in {"both", environment}]
            )
        )


def render_m303_annual_orden_censuses(censuses: tuple[M303AnnualOrdenSourceCensus, ...]) -> str:
    """Render the census artefact's committed bytes.

    Indented and newline-terminated so a regeneration produces a reviewable diff
    rather than one enormous line -- these are regulatory extractions, and a
    reviewer has to be able to see what moved.

    Returns:
        The artefact text, exactly as the build commits it.
    """
    artefact = M303AnnualOrdenCensusArtefact(
        schema_version=M303_ORDEN_CENSUS_SCHEMA_VERSION, extractor_version=EXTRACTOR_VERSION, censuses=censuses
    )
    return artefact.model_dump_json(indent=2) + "\n"


def coverage_assessment_horizon(catalogues: RegistryCatalogues) -> int:
    """Return the current registry-declared horizon for finite coverage work.

    The supported-filing-years catalogue is the registry's sole declaration of
    what the product currently claims to support.  A coverage derivation must
    therefore stop at its latest year, rather than copying a clock year or a
    modelo-specific year list into another authority surface.
    """
    catalogue = catalogues.supported_filing_years
    if catalogue is None:
        raise RegistryValidationError("registry has no supported_filing_years catalogue for coverage assessment")
    return catalogue.years[-1]


def revision_selection_coordinates(
    revision: ModeloRevision, *, assessment_horizon: int
) -> tuple[tuple[int, RegistrySelectorPeriodCode], ...]:
    """Derive every declared selection coordinate through the assessment horizon.

    The expansion has exactly one owner because a single representative year
    can prove neither an open selector's later years nor all of a revision's
    declared period tokens.  It intentionally returns the declared token --
    including ``EVENT-N`` -- rather than expanding aliases or re-implementing
    period grammar.  The canonical selector remains responsible for matching a
    request to that token.
    """
    if not 2000 <= assessment_horizon <= 2099:
        raise ValueError("assessment_horizon must be between 2000 and 2099")
    selector = revision.period_selector
    if selector.years:
        years = tuple(year for year in sorted(selector.years) if year <= assessment_horizon)
    else:
        if selector.year_from is None:
            raise RegistryValidationError(
                f"revision {revision.id!r} declares no selector start for coverage assessment"
            )
        end = min(selector.year_to or assessment_horizon, assessment_horizon)
        years = tuple(range(selector.year_from, end + 1))
    if not years:
        raise RegistryValidationError(
            f"revision {revision.id!r} declares no filing year through coverage horizon {assessment_horizon}"
        )
    return tuple((filing_year, period) for filing_year in years for period in selector.periods)


@dataclass(frozen=True, slots=True)
class ResolvedExportEndpoint:
    """One casilla the resolved export surface carries, and the path carrying it.

    ``field`` is the resolved field for the ``field`` and ``projection`` paths.
    It is ``None`` for ``row_field``: after binding derivation that slot is a
    binding-kind field naming the binding rather than the casilla, so no field
    on the resolved layout carries the casilla's own type.
    """

    layout_id: str
    record_id: str
    casilla_id: CasillaId
    path: ResolvedExportEndpointPath
    field: ExportFieldDefinition | None


_ORACLE_PAYLOAD_MODELS: Final[Mapping[ExternalOracleCorpus, type[OraclePayload]]] = {
    ExternalOracleCorpus.RENTA_WEB_OPEN_REPLAY: RentaWebOpenReplayPayload,
    ExternalOracleCorpus.AEAT_MANUAL_WORKED_EXAMPLE: ManualWorkedExamplePayload,
}


class ExternalOracleEvidence(ExternalGroundingModel):
    """One bundled oracle payload's expected-value inventory, attributed to a filing year.

    Casilla ids renumber across filing years and are scoped per modelo, so a
    captured figure is only a valid grounding claim against its own modelo's
    revision covering its own year. Both axes therefore travel with the
    evidence rather than being inferred at the point of use.
    """

    corpus: ExternalOracleCorpus
    payload_name: str = Field(min_length=1, max_length=255)
    modelo: ModeloId
    filing_year: FilingYear
    period: RegistrySelectorPeriodCode | None = None
    casilla_ids: tuple[CasillaId, ...]


class UnattributedOraclePayload(ExternalGroundingModel):
    """A bundled oracle payload whose evidence reaches no registry revision.

    Recorded rather than skipped. A payload the fold silently dropped would be
    indistinguishable from one it checked and found clean, and the figures it
    carries would sit outside the honesty relation with nothing reporting their
    absence.
    """

    corpus: ExternalOracleCorpus
    payload_name: str = Field(min_length=1, max_length=255)
    gap: OracleAttributionGap
    detail: _GroundingDetail


_INSTALLED_DIGEST_LABEL = b"registry-identity-installed-v1"


def _file_content_digest(path: Path) -> str:
    """Return a content digest for one registry file, or a marker when unreadable.

    An unreadable file yields a stable per-path marker rather than raising: the
    stamp is a description of what the build packaged, and a file it could not
    read is a fact about that tree, not a reason to abort a release. The marker
    differs from any real digest, so such a tree can never match one whose files
    all read cleanly.

    Returns:
        The hex BLAKE2b digest of the file's bytes, or an ``unreadable:`` marker.
    """
    try:
        return blake2b_hex(path.read_bytes())
    except OSError:
        _LOGGER.debug("Registry file %s could not be read while stamping identity", path, exc_info=True)
        return "unreadable"


def _validate_oracle_id(value: str) -> OracleId:
    """Validate a catalogue key against the registry ``OracleId`` contract."""
    try:
        return _ORACLE_ID_ADAPTER.validate_python(value)
    except ValidationError as exc:
        raise RegistryValidationError(f"oracle_id {value!r} is not a valid OracleId: {exc}") from exc


OracleAttributionGap = Literal["payload_name_lacks_modelo_and_filing_year", "no_registry_revision_covers_filing_year"]
_GroundingDetail = Annotated[str, ElidedProse(512)]
_ORACLE_ID_ADAPTER: TypeAdapter[OracleId] = TypeAdapter(OracleId)
