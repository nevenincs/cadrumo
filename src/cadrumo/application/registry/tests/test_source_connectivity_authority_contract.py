"""Focused contracts for live source-connectivity authority dependencies."""

from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from pydantic import ValidationError

from ....core import (
    BindingSourceKind,
    CalculationSourceLineageRole,
    SourceConnectivityConnectionIdentity,
    SourceConnectivityExecutableEvidence,
    SourceConnectivityExecutableEvidenceRole,
    SourceConnectivityGrounding,
    SourceConnectivityGroundingLocatorKind,
    SourceConnectivityOperatorReachabilityProof,
)
from ....core.identity import CalculationRevisionId
from ....domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionCatalogue,
    CalculationRevisionState,
    CalculationSourceRef,
)
from ...aggregation import BindingSourceDisposition
from ...modelo.calculation_route import CALCULATION_ROUTE_SOURCE_DISPOSITIONS
from ...operator_surface.calculation_workflows import ModeloCalculationRouteId, SupportedModeloCalculationWorkflow, SupportedModeloCalculationWorkflowCatalogue, build_supported_modelo_calculation_workflow_catalogue
from ...operator_surface.manifest import LiveLeafInventoryRow, OperatorSurfaceReconciliation, ReconciledOperatorLeaf
from ..source_connectivity_authority import (
    CalculationRouteResolverSourceOwnership,
    CalculationRouteSourceOwnershipCatalogue,
    LiveSourceConnectivityProofAuthority,
    RepositoryEvidenceDigestVerifier,
    RepositoryRootEvidenceDigestVerifier,
    build_calculation_route_source_ownership_catalogue,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_source_ownership_catalogue_is_an_exact_projection_not_free_enrollment() -> None:
    catalogue = build_calculation_route_source_ownership_catalogue()
    collectible = catalogue.ownership_for(BindingSourceKind.COLLECTIBLE_INVOICE)
    assert isinstance(collectible, CalculationRouteResolverSourceOwnership)
    assert catalogue.manual_input.source_kind is BindingSourceKind.MANUAL_INPUT

    with pytest.raises(ValidationError, match="exactly project"):
        CalculationRouteSourceOwnershipCatalogue(
            resolver_sources=catalogue.resolver_sources[:-1],
            manual_input=catalogue.manual_input,
            design_constant=catalogue.design_constant,
        )
    with pytest.raises(ValidationError, match="exactly project"):
        CalculationRouteSourceOwnershipCatalogue(
            resolver_sources=(
                catalogue.resolver_sources[0].model_copy(update={"resolver_id": "invented-resolver"}),
                *catalogue.resolver_sources[1:],
            ),
            manual_input=catalogue.manual_input,
            design_constant=catalogue.design_constant,
        )
    with pytest.raises(ValidationError, match="exactly project"):
        CalculationRouteSourceOwnershipCatalogue(
            resolver_sources=catalogue.resolver_sources,
            manual_input=catalogue.manual_input.model_copy(update={"owner_id": "invented-manual-owner"}),
            design_constant=catalogue.design_constant,
        )


def test_workflow_catalogue_refuses_directly_authored_command_path_cross_pair() -> None:
    with pytest.raises(ValidationError, match="command and canonical path must agree"):
        SupportedModeloCalculationWorkflow(
            command_id="modelo.work.calculate",
            route_id=ModeloCalculationRouteId.MODELO_WORK_CALCULATION,
            canonical_cli_path=_WORKFLOW_PATHS["quickfile"],
        )


@pytest.mark.parametrize(
    "disposition",
    (BindingSourceDisposition.DEFERRED, BindingSourceDisposition.RESERVED),
)
def test_source_ownership_catalogue_refuses_non_enrolled_sources(
    disposition: BindingSourceDisposition,
) -> None:
    catalogue = build_calculation_route_source_ownership_catalogue()
    source_kind = next(
        source for source, declared in CALCULATION_ROUTE_SOURCE_DISPOSITIONS.items() if declared is disposition
    )
    invented = catalogue.resolver_sources[0].model_copy(update={"source_kind": source_kind})
    with pytest.raises(ValidationError, match="exactly project"):
        CalculationRouteSourceOwnershipCatalogue(
            resolver_sources=(*catalogue.resolver_sources, invented),
            manual_input=catalogue.manual_input,
            design_constant=catalogue.design_constant,
        )


def test_repository_digest_verifier_hashes_real_file_and_detects_changed_bytes(tmp_path: Path) -> None:
    repository_root = tmp_path / "repository"
    evidence_path = repository_root / "src" / "cadrumo" / "tests" / "test_evidence.py"
    evidence_path.parent.mkdir(parents=True)
    evidence_bytes = b"def test_evidence():\n    assert True\n"
    evidence_path.write_bytes(evidence_bytes)
    outside_path = tmp_path / "outside.py"
    outside_path.write_bytes(b"outside")
    verifier = RepositoryRootEvidenceDigestVerifier(repository_root=repository_root)

    expected = sha256(evidence_bytes).hexdigest()
    assert verifier.digest("src/cadrumo/tests/test_evidence.py") == expected
    assert verifier.digest("src/cadrumo/tests/test_evidence.py:1") == expected
    evidence_path.write_bytes(b"def test_evidence():\n    assert False\n")
    assert verifier.digest("src/cadrumo/tests/test_evidence.py") != expected
    assert verifier.digest("../outside.py") is None
    assert verifier.digest(str(outside_path)) is None
    assert verifier.digest("src/cadrumo/tests/missing.py") is None


@pytest.mark.parametrize(
    "malformed_reference",
    (
        "C:/Windows/win.ini",
        "C:relative.py",
        "src/file.py:ads",
        "src/file.py:1:2",
        "src//file.py",
        "src/./file.py",
        "src/../file.py",
        "src\\file.py",
        "/src/file.py",
    ),
)
def test_repository_digest_verifier_rejects_malformed_repository_references(
    tmp_path: Path,
    malformed_reference: str,
) -> None:
    repository_root = tmp_path / "repository"
    repository_root.mkdir()
    verifier = RepositoryRootEvidenceDigestVerifier(repository_root=repository_root)

    assert verifier.digest(malformed_reference) is None


def test_repository_digest_verifier_rejects_descriptor_path_replacement(
    tmp_path: Path,
) -> None:
    repository_root = tmp_path / "repository"
    target = repository_root / "src" / "cadrumo" / "tests" / "test_target.py"
    replacement = repository_root / "src" / "cadrumo" / "tests" / "test_replacement.py"
    target.parent.mkdir(parents=True)
    replacement.write_bytes(b"replacement")
    verifier = RepositoryRootEvidenceDigestVerifier(repository_root=repository_root)

    # A substituted in-root path has a different opened-descriptor identity.
    target.symlink_to(replacement)
    assert verifier.digest("src/cadrumo/tests/test_target.py") is None


def test_repository_digest_verifier_rejects_directory_as_nonregular_descriptor(tmp_path: Path) -> None:
    repository_root = tmp_path / "repository"
    evidence_dir = repository_root / "src" / "cadrumo" / "tests" / "test_directory"
    evidence_dir.mkdir(parents=True)
    verifier = RepositoryRootEvidenceDigestVerifier(repository_root=repository_root)
    assert verifier.digest("src/cadrumo/tests/test_directory") is None


def test_repository_digest_verifier_rejects_symlink_escape(tmp_path: Path) -> None:
    repository_root = tmp_path / "repository"
    evidence_dir = repository_root / "src" / "cadrumo" / "tests"
    evidence_dir.mkdir(parents=True)
    outside = tmp_path / "outside.py"
    outside.write_bytes(b"outside")
    symlink = evidence_dir / "test_symlink.py"
    symlink.symlink_to(outside)

    verifier = RepositoryRootEvidenceDigestVerifier(repository_root=repository_root)
    assert verifier.digest("src/cadrumo/tests/test_symlink.py") is None

    outside_directory = tmp_path / "outside"
    outside_directory.mkdir()
    (outside_directory / "test_evidence.py").write_bytes(b"outside intermediate")
    intermediate_symlink = repository_root / "src" / "linked"
    intermediate_symlink.symlink_to(outside_directory, target_is_directory=True)
    assert verifier.digest("src/linked/test_evidence.py") is None


def test_canonical_module_exposes_authority_and_injected_verifier_port() -> None:
    """The public contracts are declared by their DEFINING module, not by a package facade.

    This assertion used to read the package root's ``__all__``. That map is gone:
    ``application.registry``'s namespace is inert, so a facade assertion passes
    only while a forbidden re-export survives and reds the moment the boundary is
    correct -- which is the wrong way round. The contract worth pinning is that
    each name is public ON ITS CANONICAL MODULE, and that the package namespace
    stays inert rather than growing a second home for it.
    """
    from importlib import import_module

    from .. import source_connectivity_authority

    # The package OBJECT is the subject here, not a symbol drawn through it:
    # the assertion below is that this namespace re-exports nothing.
    registry_package = import_module("cadrumo.application.registry")

    exported = {
        "CalculationRouteDesignConstantSourceOwnership",
        "CalculationRouteResolverSourceOwnership",
        "CalculationRouteSourceOwnershipCatalogue",
        "LiveSourceConnectivityProofAuthority",
        "RepositoryEvidenceDigestVerifier",
        "RepositoryRootEvidenceDigestVerifier",
        "build_calculation_route_source_ownership_catalogue",
    }
    assert exported <= set(source_connectivity_authority.__all__)
    for name in exported:
        assert hasattr(source_connectivity_authority, name), name
    assert registry_package.__all__ == []
    assert isinstance(RepositoryRootEvidenceDigestVerifier, type)
    assert isinstance(LiveSourceConnectivityProofAuthority, type)
    assert RepositoryEvidenceDigestVerifier.__name__ == "RepositoryEvidenceDigestVerifier"


class _RevisionRepository:
    def __init__(self, revision: CalculationRevision) -> None:
        self._revision = revision

    def exists(self) -> bool:
        return True

    def load(self) -> CalculationRevisionCatalogue:
        return CalculationRevisionCatalogue.model_construct(
            revisions={self._revision.calculation_revision_id: self._revision},
        )


_REVISION_CREATED_AT = datetime(2026, 8, 25, tzinfo=UTC)


def _revision(
    *,
    calculation_revision_id: CalculationRevisionId,
    source_provenance: tuple[CalculationSourceRef, ...] = (),
) -> CalculationRevision:
    return CalculationRevision.model_construct(
        calculation_revision_id=calculation_revision_id,
        work_unit_id="a" * 64,
        state=CalculationRevisionState.BORRADOR,
        filing_instance_evidence=None,
        source_provenance=source_provenance,
        created_at=_REVISION_CREATED_AT,
        updated_at=_REVISION_CREATED_AT,
    )


_WORKFLOW_PATHS = {
    "modelo.work.calculate": ("app", "modelo", "work", "calculate"),
    "modelo.work.wizard": ("app", "modelo", "work", "wizard"),
    "quickfile": ("app", "quickfile"),
}


def _workflow_catalogue(*command_ids: str) -> SupportedModeloCalculationWorkflowCatalogue:
    leaves = tuple(
        ReconciledOperatorLeaf(
            live_leaf=LiveLeafInventoryRow(
                subject_leaf_key=command_id,
                canonical_cli_path=_WORKFLOW_PATHS[command_id],
                provenance="resolved Click command tree",
            ),
            result_schema=None,
            input_schema=None,
            mounted_family=None,
            profile_policy=None,
            surface_exposure=None,
            exclusions=(),
        )
        for command_id in command_ids
    )
    return build_supported_modelo_calculation_workflow_catalogue(
        OperatorSurfaceReconciliation(leaves=leaves),
    )


def _operator_proof(
    connection: SourceConnectivityConnectionIdentity,
    command_id: str,
) -> SourceConnectivityOperatorReachabilityProof:
    grounding = SourceConnectivityGrounding(
        locator_kind=SourceConnectivityGroundingLocatorKind.REPOSITORY,
        reference="src/cadrumo/application/registry/tests/test_source_connectivity_authority_contract.py:1",
        summary="Executable workflow-to-source authority proof.",
    )
    evidence = SourceConnectivityExecutableEvidence(
        evidence_id="operator-reachability",
        role=SourceConnectivityExecutableEvidenceRole.OPERATOR_REACHABILITY,
        connection=connection,
        locator=grounding,
        content_digest="b" * 64,
    )
    return SourceConnectivityOperatorReachabilityProof(
        connection=connection,
        entrypoint_id="cli",
        command_id=command_id,
        route_id=ModeloCalculationRouteId.MODELO_WORK_CALCULATION,
        canonical_cli_path=_WORKFLOW_PATHS[command_id],
        resolver_observed=True,
        evidence=(evidence,),
    )


@pytest.mark.parametrize("command_id", tuple(_WORKFLOW_PATHS))
def test_live_workflow_authority_joins_each_reviewed_workflow_to_route_ownership(
    tmp_path: Path,
    command_id: str,
) -> None:
    source_ownership = build_calculation_route_source_ownership_catalogue()
    owner = source_ownership.ownership_for(BindingSourceKind.COLLECTIBLE_INVOICE)
    assert isinstance(owner, CalculationRouteResolverSourceOwnership)
    connection = SourceConnectivityConnectionIdentity(
        candidate_id="invoice.collectible",
        source_kind=BindingSourceKind.COLLECTIBLE_INVOICE,
        source_ref="collectible_invoice:inv-0001",
        resolver_id=owner.resolver_id,
        calculation_revision_id="a" * 64,
    )
    authority = LiveSourceConnectivityProofAuthority(
        source_ownership=source_ownership,
        workflows=_workflow_catalogue(*_WORKFLOW_PATHS),
        calculation_revisions=cast(
            Any,
            _RevisionRepository(
                _revision(calculation_revision_id=connection.calculation_revision_id),
            ),
        ),
        evidence_verifier=RepositoryRootEvidenceDigestVerifier(repository_root=tmp_path),
    )
    proof = _operator_proof(connection, command_id)
    assert authority.operator_workflow_reaches_source(connection, proof)
    assert not authority.operator_workflow_reaches_source(
        connection.model_copy(update={"source_ref": "collectible_invoice:inv-0002"}),
        proof,
    )


def test_live_workflow_authority_refuses_cross_paired_route_workflow_and_owner_axes(tmp_path: Path) -> None:
    source_ownership = build_calculation_route_source_ownership_catalogue()
    owner = source_ownership.ownership_for(BindingSourceKind.COLLECTIBLE_INVOICE)
    assert isinstance(owner, CalculationRouteResolverSourceOwnership)
    connection = SourceConnectivityConnectionIdentity(
        candidate_id="invoice.collectible",
        source_kind=BindingSourceKind.COLLECTIBLE_INVOICE,
        source_ref="collectible_invoice:inv-0001",
        resolver_id=owner.resolver_id,
        calculation_revision_id="a" * 64,
    )
    authority = LiveSourceConnectivityProofAuthority(
        source_ownership=source_ownership,
        workflows=_workflow_catalogue("modelo.work.calculate"),
        calculation_revisions=cast(
            Any,
            _RevisionRepository(_revision(calculation_revision_id=connection.calculation_revision_id)),
        ),
        evidence_verifier=RepositoryRootEvidenceDigestVerifier(repository_root=tmp_path),
    )
    proof = _operator_proof(connection, "modelo.work.calculate")

    assert not authority.operator_workflow_reaches_source(
        connection,
        proof.model_copy(update={"route_id": "phantom_calculation_route"}),
    )
    assert not authority.operator_workflow_reaches_source(
        connection,
        proof.model_copy(update={"canonical_cli_path": _WORKFLOW_PATHS["quickfile"]}),
    )
    assert not authority.operator_workflow_reaches_source(
        connection,
        proof.model_copy(update={"command_id": "modelo.work.wizard"}),
    )
    assert not authority.operator_workflow_reaches_source(
        connection.model_copy(update={"resolver_id": "renamed-resolver"}),
        proof.model_copy(update={"connection": connection.model_copy(update={"resolver_id": "renamed-resolver"})}),
    )
    assert not authority.operator_workflow_reaches_source(
        connection.model_copy(update={"source_kind": BindingSourceKind.FOREIGN_ASSET}),
        proof.model_copy(
            update={"connection": connection.model_copy(update={"source_kind": BindingSourceKind.FOREIGN_ASSET})},
        ),
    )


def test_encrypted_revision_match_is_not_tautological_over_resolver_identity() -> None:
    revision_id = "a" * 64
    persisted = CalculationSourceRef(
        resolver_id="invoice-source-resolver",
        resolved_binding_source=BindingSourceKind.COLLECTIBLE_INVOICE,
        contributor_source_kind=BindingSourceKind.COLLECTIBLE_INVOICE.value,
        contributor_binding_source=BindingSourceKind.COLLECTIBLE_INVOICE,
        lineage_role=CalculationSourceLineageRole.PRIMARY,
        source_ref="collectible_invoice:inv-0001",
        parent_source_ref=None,
        fingerprint="sha256:" + "b" * 64,
    )
    revision = _revision(calculation_revision_id=revision_id, source_provenance=(persisted,))
    authority = LiveSourceConnectivityProofAuthority(
        source_ownership=build_calculation_route_source_ownership_catalogue(),
        workflows=cast(Any, object()),
        calculation_revisions=cast(Any, _RevisionRepository(revision)),
        evidence_verifier=cast(Any, object()),
    )
    connection = SourceConnectivityConnectionIdentity(
        candidate_id="invoice.collectible",
        source_kind=BindingSourceKind.COLLECTIBLE_INVOICE,
        source_ref=persisted.source_ref,
        resolver_id=persisted.resolver_id,
        calculation_revision_id=revision_id,
    )

    def proof(asserted_connection: SourceConnectivityConnectionIdentity) -> object:
        return SimpleNamespace(
            connection=asserted_connection,
            persisted_source_identity=persisted.source_ref,
            persisted_source_fingerprint=persisted.fingerprint,
        )

    assert authority.encrypted_revision_matches(cast(Any, proof(connection)))
    assert not authority.encrypted_revision_matches(
        cast(Any, proof(connection.model_copy(update={"resolver_id": "wrong-resolver"}))),
    )

    rival = persisted.model_copy(update={"resolver_id": "rival-resolver"})
    ambiguous_revision = _revision(
        calculation_revision_id=revision_id,
        source_provenance=(persisted, rival),
    )
    ambiguous_authority = LiveSourceConnectivityProofAuthority(
        source_ownership=build_calculation_route_source_ownership_catalogue(),
        workflows=cast(Any, object()),
        calculation_revisions=cast(Any, _RevisionRepository(ambiguous_revision)),
        evidence_verifier=cast(Any, object()),
    )
    assert not ambiguous_authority.encrypted_revision_matches(cast(Any, proof(connection)))

    incoherent = persisted.model_copy(update={"resolved_binding_source": BindingSourceKind.PAYABLE_INVOICE})
    incoherent_revision = _revision(
        calculation_revision_id=revision_id,
        source_provenance=(incoherent,),
    )
    incoherent_authority = LiveSourceConnectivityProofAuthority(
        source_ownership=build_calculation_route_source_ownership_catalogue(),
        workflows=cast(Any, object()),
        calculation_revisions=cast(Any, _RevisionRepository(incoherent_revision)),
        evidence_verifier=cast(Any, object()),
    )
    assert not incoherent_authority.encrypted_revision_matches(cast(Any, proof(connection)))

    contributor_only = persisted.model_copy(
        update={
            "lineage_role": CalculationSourceLineageRole.CONTRIBUTOR,
            "parent_source_ref": "missing-primary",
        },
    )
    contributor_authority = LiveSourceConnectivityProofAuthority(
        source_ownership=build_calculation_route_source_ownership_catalogue(),
        workflows=cast(Any, object()),
        calculation_revisions=cast(
            Any,
            _RevisionRepository(
                _revision(calculation_revision_id=revision_id, source_provenance=(contributor_only,)),
            ),
        ),
        evidence_verifier=cast(Any, object()),
    )
    assert not contributor_authority.encrypted_revision_matches(cast(Any, proof(connection)))
