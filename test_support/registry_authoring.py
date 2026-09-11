"""Test-only access to registry authoring and publication operations.

The product package consumes only the published registry authority.  Tests that
exercise a deliberately mutable authoring candidate cross into development
tooling here, outside the distributable source tree.
"""

from __future__ import annotations

from dev.registry.compiler.authority import (
    compile_registry_tree,
    compile_validated_authority,
    compiled_bundled_authority,
)
from dev.registry.compiler.fact_loader import load_governed_facts
from dev.registry.compiler.fact_providers import compile_registered_fact_providers
from dev.registry.compiler.identity import (
    REGISTRY_IDENTITY_SCHEMA_VERSION,
    RegistryIdentityStamp,
    read_registry_identity_stamp,
    registry_identity_stamp_location,
)
from dev.registry.compiler.loader import load_catalogue_file, load_modelo_directory, load_registry_tree
from dev.registry.compiler.loader_fingerprints import clear_fingerprint_cache
from dev.registry.compiler.m303_orden_manifest import load_m303_annual_orden_authority
from dev.registry.compiler.validator import RegistryValidator
from dev.registry.pipeline.authority_publication import publish_authority_candidate


def reset_registry_authoring_caches() -> None:
    """Clear compiler process caches at a pytest-session boundary."""
    from dev.registry.compiler import loader as registry_loader

    registry_loader._load_registry_tree_cached.cache_clear()
    clear_fingerprint_cache()

__all__ = [
    "REGISTRY_IDENTITY_SCHEMA_VERSION",
    "RegistryIdentityStamp",
    "RegistryValidator",
    "clear_fingerprint_cache",
    "compile_registered_fact_providers",
    "compile_registry_tree",
    "compile_validated_authority",
    "compiled_bundled_authority",
    "load_catalogue_file",
    "load_governed_facts",
    "load_m303_annual_orden_authority",
    "load_modelo_directory",
    "load_registry_tree",
    "publish_authority_candidate",
    "read_registry_identity_stamp",
    "reset_registry_authoring_caches",
    "registry_identity_stamp_location",
]
