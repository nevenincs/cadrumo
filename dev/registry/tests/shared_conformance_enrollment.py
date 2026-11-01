"""The canonical filing-export conformance enrollment of the committed tree, derived once per run.

Deriving the strict conformance enrollment re-verifies every filing revision's
generated export against its semantic map, render profile and official design,
which costs tens of seconds, and every worker that composed the canonical
two-channel proof paid it again for the same answer. The enrollment is a pure
function of:

- the legal inputs, named by the same source identity a publication of them
  records (every registry and source-evidence file);
- the code that compiles and checks them, named by the compiler source-tree
  digest the development compile caches key on (product core, domain and
  application, the compiler and the publication pipeline, and the dependency
  set);
- the development registry tree the verification reads beside them: its
  remaining modules, the semantic maps, the render profiles and the pinned
  conformance vectors.

So it is published once per distinct content of those for the whole run, and
every other worker reads it. The proof composed around it binds the worker's
own compiled authority, which the enrollment does not retain.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Final

from cadrumo.core.directory_scan import scan_directory
from cadrumo.core.hashing import content_hash_hex
from cadrumo.core.resources.bundled_data import bundled_path
from dev._paths import REPO_ROOT
from dev.first_party_source import is_test_source
from dev.quality.shared_scan import shared_scan_result

from ..compiler.compiler_source_tree import compiler_source_tree_digest
from ..filing_export_proof_authority import (
    CanonicalTwoChannelFilingExportProofAuthority,
    canonical_two_channel_filing_export_proof_authority,
)
from ..pipeline.authority_publication import authority_source_identity

if TYPE_CHECKING:
    from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority

    from ..filing_export_conformance_enrollment import FilingExportConformanceEnrollmentReport

__all__ = ["committed_conformance_enrollment", "committed_filing_export_proof", "enrollment_inputs"]

_KIND: Final = "registry-filing-export-conformance-enrollment"
_DEVELOPMENT_REGISTRY: Final = REPO_ROOT / "dev" / "registry"
#: Data trees of the development registry the verification reads, every file of them.
_VERIFICATION_DATA: Final = ("mappings", "render_profiles", "conformance_vectors")


def enrollment_inputs(development_registry: Path = _DEVELOPMENT_REGISTRY) -> tuple[Path, ...]:
    """The development-registry files the enrollment reads beside its legal inputs and compiler code."""
    modules = (
        path
        for path in scan_directory(
            development_registry, pattern="*.py", recursive=True, prune_directories=("__pycache__", "tests")
        )
        if not is_test_source(path, root=development_registry)
    )
    data = (
        path
        for tree in _VERIFICATION_DATA
        if (development_registry / tree).is_dir()
        for path in scan_directory(
            development_registry / tree, pattern="*", recursive=True, prune_directories=("__pycache__",)
        )
        if path.is_file()
    )
    return tuple(sorted({*modules, *data}))


def committed_conformance_enrollment(authority: ValidatedRegistryAuthority) -> FilingExportConformanceEnrollmentReport:
    """Return the enrollment of the committed tree, deriving it with ``authority`` only if no worker has."""
    registry_root = bundled_path("registry", "aeat")
    source_root = bundled_path()
    legal_and_code = content_hash_hex(
        {
            "legal_inputs": authority_source_identity(registry_root=registry_root, source_root=source_root),
            "compiler": compiler_source_tree_digest(),
        }
    )
    return shared_scan_result(
        _KIND,
        root=REPO_ROOT,
        inputs=enrollment_inputs,
        scanner=legal_and_code,
        compute=lambda: (
            canonical_two_channel_filing_export_proof_authority(
                workspace_root=REPO_ROOT,
                registry_root=registry_root,
                source_root=source_root,
                authority=authority,
                secure_replay_source=None,
                secure_replay_custody=None,
            ).conformance_enrollment
        ),
    )


def committed_filing_export_proof(
    authority: ValidatedRegistryAuthority,
) -> CanonicalTwoChannelFilingExportProofAuthority:
    """Compose the canonical two-channel proof of the committed tree around the run's one enrollment.

    The canonical composition derives the enrollment and binds it with its
    materializable vectors; the same binding is made here around the shared one.
    """
    enrollment = committed_conformance_enrollment(authority)
    return CanonicalTwoChannelFilingExportProofAuthority(
        workspace_root=REPO_ROOT,
        registry_root=bundled_path("registry", "aeat"),
        source_root=bundled_path(),
        authority=authority,
        vectors=enrollment.materializable_vectors,
        conformance_enrollment=enrollment,
        secure_replay_source=None,
        secure_replay_custody=None,
    )
