"""Pytest controls for the development registry compiler.

The mutable registry compiler has process-local loader and fingerprint caches.
Their session boundary belongs to this development-only tree: shipped Cadrumo
tests consume the published authority and must not import the authoring
compiler merely to clear its caches. Application-backed fixtures are discovered
from the repository-root test host and are not forwarded through this conftest.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority

    from .filing_export_proof_authority import CanonicalTwoChannelFilingExportProofAuthority
    from .tests.committed_authority_publication import RunPublishedAuthority


@pytest.fixture(scope="session", autouse=True)
def _isolate_registry_caches() -> Iterator[None]:
    """Clear development compiler caches at each pytest session boundary."""
    from .compiler.loader import load_registry_tree_cached
    from .compiler.loader_fingerprints import clear_fingerprint_cache

    def _reset() -> None:
        load_registry_tree_cached.cache_clear()
        clear_fingerprint_cache()

    _reset()
    yield
    _reset()


@pytest.fixture
def authored_history_fact_scope() -> Iterator[None]:
    """Scope governed facts against the AUTHORED history rather than the filing span."""
    from cadrumo.domain.calculations.registry.governed_fact_scope import validating_governed_facts

    from .tests.profile_schema_support import authored_history_authority

    with validating_governed_facts(authored_history_authority()):
        yield


@pytest.fixture(scope="session")
def _worker_compiled_authority() -> ValidatedRegistryAuthority:
    """Compile the bundled authority once per worker.

    A test may not edit the bundled tree, so this snapshot stays correct for the
    whole session; asking the compiler per test re-hashes the source tree each
    time its fingerprint lapses. A test whose subject is recompilation asks the
    compiler itself.
    """
    from .compiler.authority import compiled_bundled_authority

    return compiled_bundled_authority()


@pytest.fixture(scope="session")
def committed_published_authority() -> RunPublishedAuthority:
    """The one publication of the committed sources, shared by every worker and kept across runs.

    Published by the first worker that asks while its inputs are unpublished,
    then admitted by digest. A test reads it in place; one that must write gets
    a file copy, never a republication. A test whose subject is a different
    candidate publishes that candidate itself.
    """
    from .tests.committed_authority_publication import committed_authority_publication

    return committed_authority_publication()


@pytest.fixture
def governed_fact_scope(_worker_compiled_authority: ValidatedRegistryAuthority) -> Iterator[None]:
    """Resolve registry tokens in one requesting test against the compiled authored facts.

    Governed-fact resolvers refuse to run without an explicit authority scope.
    Only a test whose body constructs registry-validated values requests this
    fixture, and the scope ends with that test, so no other test inherits it.
    """
    from cadrumo.domain.calculations.registry.governed_fact_scope import validating_governed_facts

    with validating_governed_facts(_worker_compiled_authority):
        yield


@pytest.fixture(scope="session")
def canonical_filing_export_proof(
    _worker_compiled_authority: ValidatedRegistryAuthority,
) -> CanonicalTwoChannelFilingExportProofAuthority:
    """Compose the canonical two-channel filing-export proof once per worker.

    Composition derives the strict conformance enrollment over every filing
    revision, which costs tens of seconds, and several modules assert against
    the same composition of the committed tree. Consumers only read it; a test
    whose subject is composing a different candidate composes its own.
    """
    from cadrumo.core.resources.bundled_data import bundled_path

    from .._paths import REPO_ROOT
    from .filing_export_proof_authority import canonical_two_channel_filing_export_proof_authority

    return canonical_two_channel_filing_export_proof_authority(
        workspace_root=REPO_ROOT,
        registry_root=bundled_path("registry", "aeat"),
        source_root=bundled_path(),
        authority=_worker_compiled_authority,
        secure_replay_source=None,
        secure_replay_custody=None,
    )
