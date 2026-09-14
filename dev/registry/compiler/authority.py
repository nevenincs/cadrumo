"""Development compilation of mutable registry inputs into validated artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from cadrumo.core.frozen_mapping import FrozenMapping
from cadrumo.core.hashing import content_hash_hex, sha256_hex
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority
from cadrumo.domain.calculations.registry.convenio import ConvenioAuthority
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.governed_fact_scope import (
    CandidateFactAuthority,
    validating_governed_facts,
)
from cadrumo.domain.calculations.registry.schema import ModeloDefinition, RegistryCatalogues
from cadrumo.domain.calculations.registry.tax_id_format import tax_id_format_from_catalogue
from cadrumo.domain.iva.compilation_catalogues import compiling_catalogues
from cadrumo.domain.user_profile.schema import ProfileSchemaDefinition

from . import fact_providers
from .authority_state import (
    authoring_root_pair,
    cached_compilation,
    canonical_authoring_root_pair,
    register_authoring_authority,
    source_evidence_receipt,
)
from .build_identity import authority_compiler_identity
from .convenio import convenio_authority_from_facts
from .corpus_catalogue import (
    compile_record_design_manifest_catalogue,
    verify_catalogue_identity_bindings,
    verify_manual_annotation_catalogue,
    verify_source_catalogue,
)
from .fact_providers import (
    compile_authored_fact_catalogue,
    compile_registered_fact_providers,
    validate_fact_provider_directory_ownership,
)
from .identity import RegistryIdentity, resolve_registry_identity
from .loader import load_registry_tree
from .loader_fingerprints import collect_registry_tree_fingerprints
from .profile_schema import (
    CapturedProfileSchema,
    capture_profile_schema,
    capture_profile_schema_source,
    validate_captured_profile_schema,
)
from .runtime_catalogues import compile_runtime_catalogues
from .source_evidence_fingerprint import collect_source_evidence_fingerprints
from .supplementary_orden import compile_supplementary_ordenes


@dataclass(frozen=True, slots=True)
class AuthoritySourceSet:
    """Complete explicit filesystem inputs captured by one authority compilation."""

    registry_root: Path
    source_evidence_root: Path
    profile_schema_path: Path

    @classmethod
    def bundled(cls) -> AuthoritySourceSet:
        """Resolve the three bundled defaults once at the development entrypoint."""
        return cls(
            registry_root=bundled_path("registry", "aeat"),
            source_evidence_root=bundled_path(),
            profile_schema_path=bundled_path("registry", "cadrumo", "user_profile", "schema.toml"),
        )


@dataclass(frozen=True, slots=True)
class StructuralRegistryComponents:
    """Typed compiler output that has not passed registry-wide conformance."""

    modelos: tuple[ModeloDefinition, ...]
    catalogues: RegistryCatalogues
    identity_digest: str
    profile_schema: ProfileSchemaDefinition


def compile_structural_authority(
    registry_root: Path,
    source_root: Path,
    *,
    identity: RegistryIdentity | None = None,
    profile_schema_path: Path | None = None,
    captured_profile_schema: CapturedProfileSchema | None = None,
) -> StructuralRegistryComponents:
    """Compile typed authority components without registry-wide conformance."""
    root, sources_root = canonical_authoring_root_pair(registry_root, source_root)
    if identity is None:
        identity = resolve_registry_identity(root, collect_fingerprints=collect_registry_tree_fingerprints)
    modelos, catalogues = compile_registry_tree(root, sources_root, identity=identity)
    captured = captured_profile_schema or capture_profile_schema_source(
        profile_schema_path or sources_root / "registry" / "cadrumo" / "user_profile" / "schema.toml"
    )
    profile_schema = validate_captured_profile_schema(
        captured,
        legal_reference_ids=frozenset(catalogues.legal),
    )
    verify_source_catalogue(sources_root, catalogues.sources)
    verify_manual_annotation_catalogue(sources_root, catalogues.sources)
    record_design_catalogue = compile_record_design_manifest_catalogue(sources_root, catalogues.sources)
    if record_design_catalogue is not None:
        catalogue, sources = record_design_catalogue
        verify_catalogue_identity_bindings(catalogue, sources)
    return StructuralRegistryComponents(
        modelos=modelos,
        catalogues=catalogues,
        identity_digest=identity.digest,
        profile_schema=profile_schema,
    )


def _compile_validated_authority_uncached(
    registry_root: Path,
    source_root: Path,
    *,
    identity: RegistryIdentity | None = None,
    profile_schema_path: Path | None = None,
    captured_profile_schema: CapturedProfileSchema | None = None,
) -> ValidatedRegistryAuthority:
    """Compile and validate a source candidate; never used by product runtime.

    ``identity`` defaults to the identity resolved for ``registry_root`` the
    same way :func:`load_registry_tree` resolves it. A caller that must pin the
    identity it captured earlier, such as publication, passes it explicitly.
    """
    root, sources_root = canonical_authoring_root_pair(registry_root, source_root)
    if identity is None:
        identity = resolve_registry_identity(root, collect_fingerprints=collect_registry_tree_fingerprints)
    authority = compile_structural_authority(
        root,
        sources_root,
        identity=identity,
        profile_schema_path=profile_schema_path,
        captured_profile_schema=captured_profile_schema,
    )
    modelos, catalogues = authority.modelos, authority.catalogues
    source_evidence_fingerprint = collect_source_evidence_fingerprints(sources_root, use_cache=False)
    # Scope validation re-validates typed members whose field validators read
    # governed vocabulary, exactly as the tree load does, so it needs the same
    # candidate facts in scope. Without them every ledger-IVA binding refuses
    # rather than resolving a rate kind through the artifact this compile
    # replaces.
    with validating_governed_facts(CandidateFactAuthority(catalogues.facts)):
        # Import only after candidate facts are scoped. The validator imports
        # applicability projections whose typed module constants resolve
        # governed vocabulary; importing it at module load would bootstrap a
        # publication through the stale artifact it is meant to replace.
        from .validator import RegistryValidator

        RegistryValidator(
            catalogues,
            source_root=sources_root,
            source_evidence_fingerprint=source_evidence_fingerprint,
            user_profile_schema=authority.profile_schema,
        ).validate_registry(modelos)
    return ValidatedRegistryAuthority.from_validated_components(
        modelos=modelos,
        catalogues=catalogues,
        identity_digest=authority.identity_digest,
        profile_schema=authority.profile_schema,
    )


def compile_validated_authority(
    registry_root: Path,
    source_root: Path,
    *,
    identity: RegistryIdentity | None = None,
    profile_schema_path: Path | None = None,
    captured_profile_schema: CapturedProfileSchema | None = None,
) -> ValidatedRegistryAuthority:
    """Compile one mutable source candidate through the development cache.

    Both registry identity and a byte-accurate source-evidence receipt are
    observed before reuse. This cache is intentionally unavailable to product
    runtime, which only reads a published authority artifact.
    """
    pair = authoring_root_pair(registry_root, source_root)
    if identity is None:
        identity = resolve_registry_identity(
            pair.registry_root,
            collect_fingerprints=collect_registry_tree_fingerprints,
        )
    profile_path = profile_schema_path or pair.source_root / "registry" / "cadrumo" / "user_profile" / "schema.toml"
    captured = captured_profile_schema or capture_profile_schema_source(profile_path)
    if captured.source_path != profile_path.resolve(strict=True):
        raise RegistryValidationError("captured profile schema path differs from the declared compiler input")
    source_receipt = content_hash_hex(
        {
            "evidence": source_evidence_receipt(
                collect_source_evidence_fingerprints(pair.source_root, use_cache=False)
            ),
            "profile_path": profile_path.resolve().as_posix(),
            "profile_sha256": sha256_hex(captured.payload),
        }
    )
    authority = cached_compilation(
        pair,
        registry_identity_digest=identity.digest,
        source_receipt=source_receipt,
        compiler_identity_digest=authority_compiler_identity(),
        build=lambda: _compile_validated_authority_uncached(
            pair.registry_root,
            pair.source_root,
            identity=identity,
            profile_schema_path=profile_path,
            captured_profile_schema=captured,
        ),
    )
    register_authoring_authority(authority, source_root=pair.source_root)
    return authority


def compile_registry_tree(
    registry_root: Path,
    source_root: Path,
    *,
    identity: RegistryIdentity | None = None,
) -> tuple[tuple[ModeloDefinition, ...], RegistryCatalogues]:
    """Load a registry tree and compile every catalogue its validation reads.

    The raw tree load yields the modelos and the hand-authored catalogues only;
    governed facts, the convenio authority and the annual Orden supplements are
    compiled from their own directories. Every validation of a candidate tree
    must see the same compiled catalogues the authority publishes, so this is
    the one place that assembles them. The result is not yet validated.
    """
    root, sources_root = canonical_authoring_root_pair(registry_root, source_root)
    if identity is None:
        identity = resolve_registry_identity(root, collect_fingerprints=collect_registry_tree_fingerprints)
    authored_facts = compile_authored_fact_catalogue(root)
    candidate_tax_id_format = tax_id_format_from_catalogue(authored_facts)
    # A modelo's bindings declare governed vocabulary, so validating them reads
    # facts. They must be the candidate's own facts: the published artifact is
    # what this compile replaces, and reading it here would make the fix for a
    # broken artifact depend on that artifact.
    with validating_governed_facts(CandidateFactAuthority(authored_facts)):
        modelos, catalogues = load_registry_tree(
            root,
            identity=identity,
            tax_id_format=candidate_tax_id_format,
        )
    if fact_providers.FACT_PROVIDER_REGISTRATIONS:
        validate_fact_provider_directory_ownership(root)
    with compiling_catalogues(catalogues.legal, catalogues.sources, sources_root):
        facts = (
            compile_registered_fact_providers(root, modelos=modelos)
            if fact_providers.FACT_PROVIDER_REGISTRATIONS
            else authored_facts
        )
        runtime_catalogues = compile_runtime_catalogues(root)
    # Provider-free isolated candidates are supported by the fact-validation
    # contract. They cannot project a treaty override, but remain useful for
    # exercising compiler and publication mechanics without unrelated facts.
    convenio = (
        convenio_authority_from_facts(facts, catalogues.legal)
        if fact_providers.FACT_PROVIDER_REGISTRATIONS
        else ConvenioAuthority(treaties={})
    )
    supported_filing_years = catalogues.supported_filing_years
    if supported_filing_years is None:
        raise RegistryValidationError("registry has no supported_filing_years catalogue")
    with validating_governed_facts(CandidateFactAuthority(facts)):
        supplementary_ordenes = compile_supplementary_ordenes(
            root,
            source_root=sources_root,
            modelos=modelos,
            sources=catalogues.sources,
            supported_filing_years=supported_filing_years.years,
        )
    duplicate_legal_refs = set(catalogues.legal).intersection(supplementary_ordenes.legal)
    if duplicate_legal_refs:
        raise RegistryValidationError(
            f"annual Orden compiler collided with hand-authored legal refs: {sorted(duplicate_legal_refs)!r}"
        )
    catalogues = catalogues.model_copy(
        update={
            "legal": FrozenMapping({**catalogues.legal, **supplementary_ordenes.legal}),
            "facts": facts,
            "convenio": convenio,
            "supplementary_ordenes": FrozenMapping(supplementary_ordenes.authorities),
            "runtime": runtime_catalogues,
        }
    )
    return modelos, catalogues


def load_unvalidated_components(
    registry_root: Path,
    source_root: Path,
    *,
    identity: RegistryIdentity,
) -> StructuralRegistryComponents:
    """Build a diagnostic-only projection without granting publication validity."""
    root, sources_root = canonical_authoring_root_pair(registry_root, source_root)
    modelos, catalogues = load_registry_tree(root, identity=identity)
    return StructuralRegistryComponents(
        modelos=modelos,
        catalogues=catalogues,
        identity_digest=identity.digest,
        profile_schema=capture_profile_schema(
            sources_root / "registry" / "cadrumo" / "user_profile" / "schema.toml",
        )[1],
    )


def compiled_bundled_authority() -> ValidatedRegistryAuthority:
    """Compile the bundled registry sources for development tooling.

    Runtime reads only the digest-checked published artifact. Development tools, screens and tests
    compile the same sources instead. The result is cached by registry identity,
    so an unchanged tree compiles once per process and any change to the sources
    compiles afresh.
    """
    registry_root, source_root = canonical_authoring_root_pair(bundled_path("registry", "aeat"), bundled_path())
    return compile_validated_authority(registry_root, source_root)


def compile_validated_source_set(source_set: AuthoritySourceSet) -> ValidatedRegistryAuthority:
    """Compile a complete explicit source set, refusing an implicit profile source."""
    roots = canonical_authoring_root_pair(source_set.registry_root, source_set.source_evidence_root)
    expected_profile = source_set.profile_schema_path.resolve(strict=True)
    return compile_validated_authority(*roots, profile_schema_path=expected_profile)
