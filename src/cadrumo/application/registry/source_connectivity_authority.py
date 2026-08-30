"""Live application authority for admitting connected source-census claims."""

from __future__ import annotations

import os
import stat
import sys
from contextlib import suppress
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path, PurePosixPath
from typing import Literal, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ...core import (
    BindingSourceKind,
    CalculationSourceLineageRole,
    ModeloCalculationRouteId,
    SourceConnectivityConnectionIdentity,
    SourceConnectivityEncryptedRevisionProof,
    SourceConnectivityExecutableEvidence,
    SourceConnectivityGroundingLocatorKind,
    SourceConnectivityOperatorReachabilityProof,
)
from ...domain.modelos import CalculationRevisionCatalogueRepositoryProtocol
from ..aggregation import BindingSourceDisposition
from ..modelo.calculation_route import (
    CALCULATION_ROUTE_ID,
    CALCULATION_ROUTE_RESOLVER_OWNERSHIP,
    CALCULATION_ROUTE_SOURCE_DISPOSITIONS,
    DESIGN_CONSTANT_RESOLVER_ID,
    MANUAL_INPUT_RESOLVER_ID,
    CalculationRouteDesignConstantOwnership,
    CalculationRouteManualOwnership,
)
from ..operator_surface.calculation_workflows import SupportedModeloCalculationWorkflowCatalogue

_STRICT_FROZEN = ConfigDict(frozen=True, strict=True, validate_assignment=True, extra="forbid")


class CalculationRouteResolverSourceOwnership(BaseModel):
    """One real resolver's canonical source ownership on the production route."""

    model_config = _STRICT_FROZEN

    route_id: ModeloCalculationRouteId
    stage: Literal["pre_mesh", "mesh", "conditional", "post_mesh"]
    source_kind: BindingSourceKind
    resolver_id: str = Field(min_length=1, max_length=128, pattern=r"^[a-z0-9][a-z0-9._:-]*$")


class CalculationRouteManualSourceOwnership(BaseModel):
    """The sole typed manual-input pseudo-owner on the production route."""

    model_config = _STRICT_FROZEN

    route_id: ModeloCalculationRouteId
    stage: Literal["manual"]
    source_kind: Literal[BindingSourceKind.MANUAL_INPUT]
    owner_id: Literal["manual_input"]


class CalculationRouteDesignConstantSourceOwnership(BaseModel):
    """The sole typed design-constant pseudo-owner on the production route.

    A SIBLING of :class:`CalculationRouteManualSourceOwnership`, projecting the
    sibling the route itself declares. Admitting the design constant by relaxing
    the manual row's ``Literal`` pins would have been the widen-the-matcher move
    the route's own owner refuses, and it would have made the two pseudo-owners
    indistinguishable at exactly the boundary that has to tell them apart: a
    manual value arrives from the operator, a design constant is already carried
    on its binding selector because AEAT's diseno fixes it.
    """

    model_config = _STRICT_FROZEN

    route_id: ModeloCalculationRouteId
    stage: Literal["manual"]
    source_kind: Literal[BindingSourceKind.DESIGN_CONSTANT]
    owner_id: Literal["design_constant"]


type CalculationRouteSourceOwnership = (
    CalculationRouteResolverSourceOwnership
    | CalculationRouteManualSourceOwnership
    | CalculationRouteDesignConstantSourceOwnership
)


def _canonical_route_source_ownership() -> tuple[
    tuple[CalculationRouteResolverSourceOwnership, ...],
    CalculationRouteManualSourceOwnership,
    CalculationRouteDesignConstantSourceOwnership,
]:
    resolver_rows: list[CalculationRouteResolverSourceOwnership] = []
    manual_rows: list[CalculationRouteManualSourceOwnership] = []
    design_constant_rows: list[CalculationRouteDesignConstantSourceOwnership] = []
    for owner in CALCULATION_ROUTE_RESOLVER_OWNERSHIP:
        if isinstance(owner, CalculationRouteManualOwnership):
            source_kind = owner.owned_sources[0]
            if CALCULATION_ROUTE_SOURCE_DISPOSITIONS[source_kind] is not BindingSourceDisposition.ENROLLED:
                raise RuntimeError(f"calculation route owns non-enrolled source {source_kind.value!r}")
            manual_rows.append(
                CalculationRouteManualSourceOwnership(
                    route_id=CALCULATION_ROUTE_ID,
                    stage="manual",
                    source_kind=source_kind,
                    owner_id=MANUAL_INPUT_RESOLVER_ID,
                ),
            )
            continue
        if isinstance(owner, CalculationRouteDesignConstantOwnership):
            source_kind = owner.owned_sources[0]
            if CALCULATION_ROUTE_SOURCE_DISPOSITIONS[source_kind] is not BindingSourceDisposition.ENROLLED:
                raise RuntimeError(f"calculation route owns non-enrolled source {source_kind.value!r}")
            design_constant_rows.append(
                CalculationRouteDesignConstantSourceOwnership(
                    route_id=CALCULATION_ROUTE_ID,
                    stage="manual",
                    source_kind=source_kind,
                    owner_id=DESIGN_CONSTANT_RESOLVER_ID,
                ),
            )
            continue
        for source_kind in owner.owned_sources:
            if CALCULATION_ROUTE_SOURCE_DISPOSITIONS[source_kind] is not BindingSourceDisposition.ENROLLED:
                raise RuntimeError(f"calculation route owns non-enrolled source {source_kind.value!r}")
            resolver_rows.append(
                CalculationRouteResolverSourceOwnership(
                    route_id=CALCULATION_ROUTE_ID,
                    stage=owner.stage,
                    source_kind=source_kind,
                    resolver_id=owner.resolver_id,
                ),
            )
    if len(manual_rows) != 1:
        raise RuntimeError("calculation route requires exactly one manual-input pseudo-owner")
    if len(design_constant_rows) != 1:
        raise RuntimeError("calculation route requires exactly one design-constant pseudo-owner")
    return (
        tuple(sorted(resolver_rows, key=lambda row: row.source_kind.value)),
        manual_rows[0],
        design_constant_rows[0],
    )


class CalculationRouteSourceOwnershipCatalogue(BaseModel):
    """Exact projection of canonical production route ownership and dispositions."""

    model_config = _STRICT_FROZEN

    resolver_sources: tuple[CalculationRouteResolverSourceOwnership, ...] = Field(min_length=1)
    manual_input: CalculationRouteManualSourceOwnership
    design_constant: CalculationRouteDesignConstantSourceOwnership

    @model_validator(mode="after")
    def _require_exact_canonical_projection(self) -> CalculationRouteSourceOwnershipCatalogue:
        expected_resolvers, expected_manual, expected_design_constant = _canonical_route_source_ownership()
        if (
            self.resolver_sources != expected_resolvers
            or self.manual_input != expected_manual
            or self.design_constant != expected_design_constant
        ):
            raise ValueError("source ownership catalogue must exactly project the canonical calculation route")
        return self

    def ownership_for(self, source_kind: BindingSourceKind) -> CalculationRouteSourceOwnership | None:
        """Return the exact canonical route owner for one enrolled source."""
        if source_kind is BindingSourceKind.MANUAL_INPUT:
            return self.manual_input
        if source_kind is BindingSourceKind.DESIGN_CONSTANT:
            return self.design_constant
        return next((row for row in self.resolver_sources if row.source_kind is source_kind), None)


def build_calculation_route_source_ownership_catalogue() -> CalculationRouteSourceOwnershipCatalogue:
    """Project complete source ownership from the validated production route."""
    resolver_sources, manual_input, design_constant = _canonical_route_source_ownership()
    return CalculationRouteSourceOwnershipCatalogue(
        resolver_sources=resolver_sources,
        manual_input=manual_input,
        design_constant=design_constant,
    )


class LiveSourceConnectivityProofExpectation(BaseModel):
    """Independent expected identity for one synthetic production-route proof."""

    model_config = _STRICT_FROZEN

    connection: SourceConnectivityConnectionIdentity
    entrypoint_id: str = Field(min_length=1, max_length=128)
    command_id: str = Field(min_length=1, max_length=128)
    route_id: ModeloCalculationRouteId
    canonical_cli_path: tuple[str, ...] = Field(min_length=1)
    destination_identities: tuple[tuple[str, str, str, str, str, str], ...] = Field(min_length=1)


@runtime_checkable
class RepositoryEvidenceDigestVerifier(Protocol):
    """Injected port that verifies one repository evidence reference."""

    def digest(self, repository_reference: str) -> str | None:
        """Return the deterministic digest only when the reference is safe and readable."""


@dataclass(frozen=True, slots=True)
class RepositoryRootEvidenceDigestVerifier:
    """SHA-256 verifier confined to one explicitly injected repository root."""

    repository_root: Path

    def digest(self, repository_reference: str) -> str | None:
        """Hash one verified open descriptor, refusing path replacement and escape."""
        relative_text = _repository_path_without_line(repository_reference)
        if relative_text is None:
            return None
        try:
            root = self.repository_root.resolve(strict=True)
        except (OSError, RuntimeError):
            return None
        if not root.is_dir():
            return None
        candidate = root / Path(*PurePosixPath(relative_text).parts)
        flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
        try:
            descriptor = os.open(candidate, flags)
        except OSError:
            return None
        try:
            opened_path = _final_path_from_open_descriptor(descriptor)
            if opened_path is None or not _same_filesystem_path(opened_path, candidate):
                return None
            if not opened_path.is_relative_to(root):
                return None
            if not stat.S_ISREG(os.fstat(descriptor).st_mode):
                return None
            digest = sha256()
            with os.fdopen(descriptor, "rb", closefd=False) as opened_file:
                while chunk := opened_file.read(1024 * 1024):
                    digest.update(chunk)
            return digest.hexdigest()
        except (OSError, RuntimeError, ValueError):
            return None
        finally:
            with suppress(OSError):
                os.close(descriptor)


def _same_filesystem_path(left: Path, right: Path) -> bool:
    """Compare final-handle and requested paths under platform case semantics."""
    return os.path.normcase(os.path.normpath(str(left))) == os.path.normcase(os.path.normpath(str(right)))


def _final_path_from_open_descriptor(descriptor: int) -> Path | None:
    """Return the OS-reported final path for one already-open descriptor."""
    if os.name == "nt":
        return _windows_final_path_from_open_descriptor(descriptor)
    if sys.platform.startswith("linux"):
        try:
            return Path(os.readlink(f"/proc/self/fd/{descriptor}"))
        except OSError:
            return None
    return None


def _windows_final_path_from_open_descriptor(descriptor: int) -> Path | None:
    """Ask Windows for the stable final path bound to an open file handle."""
    try:
        import ctypes
        import msvcrt
        from ctypes import wintypes

        get_final_path = ctypes.WinDLL("kernel32", use_last_error=True).GetFinalPathNameByHandleW
        get_final_path.argtypes = (wintypes.HANDLE, wintypes.LPWSTR, wintypes.DWORD, wintypes.DWORD)
        get_final_path.restype = wintypes.DWORD
        handle = wintypes.HANDLE(msvcrt.get_osfhandle(descriptor))
        required = get_final_path(handle, None, 0, 0)
        if required == 0:
            return None
        buffer = ctypes.create_unicode_buffer(required + 1)
        written = get_final_path(handle, buffer, len(buffer), 0)
        if written == 0 or written >= len(buffer):
            return None
        path = buffer.value
        if path.startswith("\\\\?\\UNC\\"):
            path = "\\\\" + path[8:]
        elif path.startswith("\\\\?\\"):
            path = path[4:]
        return Path(path)
    except (ImportError, OSError, ValueError):
        return None


def _repository_path_without_line(reference: str) -> str | None:
    """Return a safe relative POSIX path from a repository evidence locator."""
    colon_count = reference.count(":")
    if colon_count == 0:
        candidate = reference
    elif colon_count == 1:
        path, line = reference.rsplit(":", 1)
        if not line.isdigit():
            return None
        candidate = path
    else:
        return None
    raw_parts = candidate.split("/")
    pure_path = PurePosixPath(candidate)
    if (
        not candidate
        or "\\" in candidate
        or candidate.startswith("/")
        or pure_path.is_absolute()
        or any(part in {"", ".", ".."} for part in raw_parts)
    ):
        return None
    return candidate


@dataclass(frozen=True, slots=True)
class LiveSourceConnectivityProofAuthority:
    """Concrete live authority over enrollment, workflows, evidence, and revisions."""

    source_ownership: CalculationRouteSourceOwnershipCatalogue
    workflows: SupportedModeloCalculationWorkflowCatalogue
    calculation_revisions: CalculationRevisionCatalogueRepositoryProtocol
    evidence_verifier: RepositoryEvidenceDigestVerifier
    independent_expectations: tuple[LiveSourceConnectivityProofExpectation, ...] = ()

    def _expectation_for(
        self,
        connection: SourceConnectivityConnectionIdentity,
    ) -> LiveSourceConnectivityProofExpectation | None:
        matches = tuple(
            expectation
            for expectation in self.independent_expectations
            if expectation.connection.candidate_id == connection.candidate_id
        )
        if not self.independent_expectations:
            return None
        if len(matches) != 1 or matches[0].connection != connection:
            return None
        return matches[0]

    def source_is_enrolled(self, connection: SourceConnectivityConnectionIdentity) -> bool:
        """Require exact resolver ownership under an enrolled live disposition."""
        if self.independent_expectations and self._expectation_for(connection) is None:
            return False
        ownership = self.source_ownership.ownership_for(connection.source_kind)
        if isinstance(ownership, CalculationRouteManualSourceOwnership):
            return ownership.owner_id == connection.resolver_id
        return ownership is not None and ownership.resolver_id == connection.resolver_id

    def operator_workflow_reaches_source(
        self,
        connection: SourceConnectivityConnectionIdentity,
        proof: SourceConnectivityOperatorReachabilityProof,
    ) -> bool:
        """Require the exact reviewed live workflow beside exact source enrollment."""
        if proof.connection != connection:
            return False
        expectation = self._expectation_for(connection)
        if self.independent_expectations and (
            expectation is None
            or expectation.entrypoint_id != proof.entrypoint_id
            or expectation.command_id != proof.command_id
            or expectation.route_id is not proof.route_id
            or expectation.canonical_cli_path != proof.canonical_cli_path
        ):
            return False
        ownership = self.source_ownership.ownership_for(connection.source_kind)
        workflows = tuple(
            workflow
            for workflow in self.workflows.workflows
            if workflow.entrypoint_id == proof.entrypoint_id
            and workflow.command_id == proof.command_id
            and workflow.route_id is proof.route_id
            and workflow.canonical_cli_path == proof.canonical_cli_path
        )
        if ownership is None or len(workflows) != 1 or ownership.route_id is not workflows[0].route_id:
            return False
        owner_id = (
            ownership.owner_id
            if isinstance(ownership, CalculationRouteManualSourceOwnership)
            else ownership.resolver_id
        )
        return owner_id == connection.resolver_id

    def encrypted_revision_matches(self, proof: SourceConnectivityEncryptedRevisionProof) -> bool:
        """Match one exact provenance row in the encrypted calculation revision."""
        connection = proof.connection
        try:
            if not self.calculation_revisions.exists():
                return False
            catalogue = self.calculation_revisions.load()
        except Exception:
            return False
        revision = catalogue.revisions.get(connection.calculation_revision_id)
        if revision is None or revision.calculation_revision_id != connection.calculation_revision_id:
            return False
        primary_ref_counts: dict[str, int] = {}
        for row in revision.source_provenance:
            if row.lineage_role is CalculationSourceLineageRole.PRIMARY:
                primary_ref_counts[row.source_ref] = primary_ref_counts.get(row.source_ref, 0) + 1
        if any(
            row.lineage_role is CalculationSourceLineageRole.CONTRIBUTOR
            and (row.parent_source_ref is None or primary_ref_counts.get(row.parent_source_ref) != 1)
            for row in revision.source_provenance
        ):
            return False
        source_identity_rows = tuple(
            row
            for row in revision.source_provenance
            if row.lineage_role is CalculationSourceLineageRole.PRIMARY
            and row.resolved_binding_source is connection.source_kind
            and row.source_ref == proof.persisted_source_identity
        )
        return (
            len(source_identity_rows) == 1
            and source_identity_rows[0].resolver_id == connection.resolver_id
            and source_identity_rows[0].fingerprint == proof.persisted_source_fingerprint
        )

    def executable_evidence_digest(
        self,
        evidence: SourceConnectivityExecutableEvidence,
    ) -> str | None:
        """Verify repository-backed executable evidence through the injected root policy."""
        if evidence.locator.locator_kind is not SourceConnectivityGroundingLocatorKind.REPOSITORY:
            return None
        return self.evidence_verifier.digest(evidence.locator.reference)

    def destinations_match(
        self,
        connection: SourceConnectivityConnectionIdentity,
        destination_identities: tuple[tuple[str, str, str, str, str, str], ...],
    ) -> bool:
        """Match registry destinations against the independently authored fixture."""
        expectation = self._expectation_for(connection)
        return expectation is not None and expectation.destination_identities == destination_identities


__all__ = [
    "CalculationRouteDesignConstantSourceOwnership",
    "CalculationRouteManualSourceOwnership",
    "CalculationRouteResolverSourceOwnership",
    "CalculationRouteSourceOwnershipCatalogue",
    "LiveSourceConnectivityProofAuthority",
    "LiveSourceConnectivityProofExpectation",
    "RepositoryEvidenceDigestVerifier",
    "RepositoryRootEvidenceDigestVerifier",
    "build_calculation_route_source_ownership_catalogue",
]
