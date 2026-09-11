"""Development compilation of mutable registry inputs into validated artifacts."""

from __future__ import annotations

from pathlib import Path

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority
from cadrumo.domain.calculations.registry.convenio import ConvenioAuthority
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.schema import ModeloDefinition, RegistryCatalogues
from cadrumo.domain.iva.compilation_catalogues import compiling_catalogues

from . import fact_providers
from .authority_state import (
    authoring_root_pair,
    cached_compilation,
    canonical_authoring_root_pair,
    register_authoring_authority,
    source_evidence_receipt,
)
from .convenio import convenio_authority_from_facts
from .fact_providers import compile_registered_fact_providers, validate_fact_provider_directory_ownership
from .identity import RegistryIdentity, resolve_registry_identity
from .loader import load_registry_tree
from .loader_fingerprints import collect_registry_tree_fingerprints
from .source_evidence_fingerprint import collect_source_evidence_fingerprints
from .supplementary_orden import compile_supplementary_ordenes
from .validator import RegistryValidator


def _compile_validated_authority_uncached(
    registry_root: Path,
    source_root: Path,
    *,
    identity: RegistryIdentity | None = None,
) -> ValidatedRegistryAuthority:
    """Compile and validate a source candidate; never used by product runtime.

    ``identity`` defaults to the identity resolved for ``registry_root`` the
    same way :func:`load_registry_tree` resolves it. A caller that must pin the
    identity it captured earlier, such as publication, passes it explicitly.
    """
    root, sources_root = canonical_authoring_root_pair(registry_root, source_root)
    if identity is None:
        identity = resolve_registry_identity(root, collect_fingerprints=collect_registry_tree_fingerprints)
    modelos, catalogues = compile_registry_tree(root, sources_root, identity=identity)
    source_evidence_fingerprint = collect_source_evidence_fingerprints(sources_root)
    RegistryValidator(
        catalogues,
        source_root=sources_root,
        source_evidence_fingerprint=source_evidence_fingerprint,
    ).validate_registry(modelos)
    return ValidatedRegistryAuthority.from_validated_components(
        modelos=modelos,
        catalogues=catalogues,
        identity_digest=identity.digest,
    )


def compile_validated_authority(
    registry_root: Path,
    source_root: Path,
    *,
    identity: RegistryIdentity | None = None,
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
    source_receipt = source_evidence_receipt(collect_source_evidence_fingerprints(pair.source_root))
    authority = cached_compilation(
        pair,
        registry_identity_digest=identity.digest,
        source_receipt=source_receipt,
        build=lambda: _compile_validated_authority_uncached(
            pair.registry_root,
            pair.source_root,
            identity=identity,
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
    modelos, catalogues = load_registry_tree(root, identity=identity)
    validate_fact_provider_directory_ownership(root)
    with compiling_catalogues(catalogues.legal, catalogues.sources, sources_root):
        facts = compile_registered_fact_providers(root, modelos=modelos)
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
            "legal": {**catalogues.legal, **supplementary_ordenes.legal},
            "facts": facts,
            "convenio": convenio,
            "supplementary_ordenes": supplementary_ordenes.authorities,
        }
    )
    return modelos, catalogues


def construct_unvalidated_authority(
    registry_root: Path,
    source_root: Path,
    *,
    identity: RegistryIdentity,
) -> ValidatedRegistryAuthority:
    """Build a diagnostic-only projection without granting publication validity."""
    root, _sources_root = canonical_authoring_root_pair(registry_root, source_root)
    modelos, catalogues = load_registry_tree(root, identity=identity)
    return ValidatedRegistryAuthority.from_validated_components(
        modelos=modelos,
        catalogues=catalogues,
        identity_digest=identity.digest,
    )


def compiled_bundled_authority() -> ValidatedRegistryAuthority:
    """Compile the bundled registry sources for development tooling.

    Runtime reads only the signed published artifact, which a development
    checkout does not have and cannot sign. Development tools, screens and tests
    compile the same sources instead. The result is cached by registry identity,
    so an unchanged tree compiles once per process and any change to the sources
    compiles afresh.
    """
    registry_root, source_root = canonical_authoring_root_pair(bundled_path("registry", "aeat"), bundled_path())
    return compile_validated_authority(registry_root, source_root)
