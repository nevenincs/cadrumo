"""Development compilation of mutable registry inputs into validated artifacts."""

from __future__ import annotations

from pathlib import Path

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry._source_evidence_fingerprint import collect_source_evidence_fingerprints
from cadrumo.domain.calculations.registry._supplementary_orden import compile_supplementary_ordenes
from cadrumo.domain.calculations.registry._validate import RegistryValidator
from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority
from cadrumo.domain.calculations.registry.errors import RegistrySnapshotError, RegistryValidationError
from .identity import RegistryIdentity, resolve_registry_identity
from cadrumo.domain.iva.compilation_catalogues import compiling_catalogues

from .convenio import load_convenio_authority, validate_convenio_legal_refs
from .fact_providers import compile_registered_fact_providers, validate_fact_provider_directory_ownership
from .loader import collect_registry_tree_fingerprints, load_registry_tree


def canonical_authoring_root_pair(registry_root: Path, source_root: Path) -> tuple[Path, Path]:
    """Resolve the mutable development inputs before they are compiled."""
    try:
        resolved_registry = registry_root.expanduser().resolve(strict=True)
        resolved_source = source_root.expanduser().resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise RegistrySnapshotError("registry compiler roots must resolve to existing physical paths") from exc
    if not resolved_registry.is_dir() or not resolved_source.is_dir():
        raise RegistrySnapshotError("registry compiler roots must resolve to physical directories")
    return resolved_registry, resolved_source


def compile_validated_authority(
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
    modelos, catalogues = load_registry_tree(root, identity=identity)
    validate_fact_provider_directory_ownership(root)
    with compiling_catalogues(catalogues.legal, catalogues.sources, sources_root):
        facts = compile_registered_fact_providers(root, modelos=modelos)
    convenio = load_convenio_authority(root / "treaties")
    validate_convenio_legal_refs(convenio, frozenset(catalogues.legal))
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
    authority = ValidatedRegistryAuthority(
        root=root,
        source_root=sources_root,
        modelos=modelos,
        catalogues=catalogues,
        _modelos_by_id={modelo.id: modelo for modelo in modelos},
        _validator=RegistryValidator(
            catalogues,
            source_root=sources_root,
            source_evidence_fingerprint=collect_source_evidence_fingerprints(sources_root),
        ),
        _registry_validated=False,
        _validated_modelos=set(),
        _snapshots={},
        _identity_digest=identity.digest,
    )
    authority.validate_registry()
    return authority


_COMPILED_BUNDLED_AUTHORITIES: dict[str, ValidatedRegistryAuthority] = {}


def compiled_bundled_authority() -> ValidatedRegistryAuthority:
    """Compile the bundled registry sources for development tooling.

    Runtime reads only the signed published artifact, which a development
    checkout does not have and cannot sign. Development tools, screens and tests
    compile the same sources instead. The result is cached by registry identity,
    so an unchanged tree compiles once per process and any change to the sources
    compiles afresh.
    """
    registry_root, source_root = canonical_authoring_root_pair(bundled_path("registry", "aeat"), bundled_path())
    identity = resolve_registry_identity(registry_root, collect_fingerprints=collect_registry_tree_fingerprints)
    cached = _COMPILED_BUNDLED_AUTHORITIES.get(identity.digest)
    if cached is None:
        cached = compile_validated_authority(registry_root, source_root, identity=identity)
        _COMPILED_BUNDLED_AUTHORITIES.clear()
        _COMPILED_BUNDLED_AUTHORITIES[identity.digest] = cached
    return cached
