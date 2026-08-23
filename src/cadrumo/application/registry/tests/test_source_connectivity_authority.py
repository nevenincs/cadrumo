"""Real encrypted integration proof for connected source-census rows."""

from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

import pytest
from pydantic import ValidationError

from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....adapters.persistence.storage import SecureObjectRepository
from ....core import (
    BindingSourceKind,
    CalculationSourceLineageRole,
    ModeloCalculationRouteId,
    SourceConnectivityCensusRow,
    SourceConnectivityConnectedProof,
    SourceConnectivityConnectionIdentity,
    SourceConnectivityDisposition,
    SourceConnectivityEncryptedRevisionProof,
    SourceConnectivityExecutableEvidence,
    SourceConnectivityExecutableEvidenceRole,
    SourceConnectivityGrounding,
    SourceConnectivityGroundingLocatorKind,
    SourceConnectivityOperatorReachabilityProof,
    SourceConnectivityResolverOwnershipProof,
)
from ....domain.modelos import (
    CalculationRevision,
    CalculationRevisionCatalogue,
    CalculationRevisionState,
    CalculationSourceRef,
    derive_calculation_revision_id,
)
from ...aggregation import BindingSourceDisposition
from ...modelo import CALCULATION_ROUTE_SOURCE_DISPOSITIONS
from ...operator_surface import (
    LiveLeafInventoryRow,
    OperatorSurfaceReconciliation,
    ReconciledOperatorLeaf,
    build_supported_modelo_calculation_workflow_catalogue,
)
from .. import (
    CalculationRouteResolverSourceOwnership,
    CalculationRouteSourceOwnershipCatalogue,
    LiveSourceConnectivityProofAuthority,
    RepositoryRootEvidenceDigestVerifier,
    build_calculation_route_source_ownership_catalogue,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_BUCKET_ID = "13513513-5135-4135-8135-135135135135"
_WORK_UNIT_ID = "a" * 64
_FINGERPRINT = "sha256:" + "b" * 64
_SOURCE_REF = "collectible_invoice:inv-0001"
_COMMAND = "modelo.work.calculate"
_CLI_PATH = ("app", "modelo", "work", "calculate")
_EVIDENCE_REFERENCES = {
    SourceConnectivityExecutableEvidenceRole.RESOLVER_ENROLLMENT: (
        "src/cadrumo/application/registry/tests/test_resolver_enrollment.py"
    ),
    SourceConnectivityExecutableEvidenceRole.ENCRYPTED_REVISION: (
        "src/cadrumo/application/registry/tests/test_encrypted_revision.py"
    ),
    SourceConnectivityExecutableEvidenceRole.OPERATOR_REACHABILITY: (
        "src/cadrumo/application/registry/tests/test_operator_reachability.py"
    ),
}


def _live_workflows():
    leaf = ReconciledOperatorLeaf(
        live_leaf=LiveLeafInventoryRow(
            subject_leaf_key=_COMMAND,
            canonical_cli_path=_CLI_PATH,
            provenance="resolved Click command tree",
        ),
        result_schema=None,
        input_schema=None,
        mounted_family=None,
        profile_policy=None,
        surface_exposure=None,
        exclusions=(),
    )
    return build_supported_modelo_calculation_workflow_catalogue(
        OperatorSurfaceReconciliation(leaves=(leaf,)),
    )


def _persisted_revision(
    repository: CalculationRevisionCatalogueRepository,
    provenance: tuple[CalculationSourceRef, ...],
) -> CalculationRevision:
    revision_id = derive_calculation_revision_id(
        work_unit_id=_WORK_UNIT_ID,
        input_values_by_casilla_id={},
        binding_overrides={},
        casilla_values={},
        filing_instance_evidence=None,
        source_provenance=provenance,
    )
    timestamp = datetime(2026, 8, 22, tzinfo=UTC)
    revision = CalculationRevision(
        calculation_revision_id=revision_id,
        work_unit_id=_WORK_UNIT_ID,
        state=CalculationRevisionState.BORRADOR,
        input_values_by_casilla_id={},
        casilla_values={},
        filing_instance_evidence=None,
        source_provenance=provenance,
        created_at=timestamp,
        updated_at=timestamp,
    )
    repository.save(CalculationRevisionCatalogue(revisions={revision_id: revision}))
    return repository.load().revisions[revision_id]


def _evidence_root(tmp_path: Path) -> Path:
    root = tmp_path / "evidence-repository"
    for index, reference in enumerate(_EVIDENCE_REFERENCES.values(), start=1):
        path = root / reference
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(f"authoritative evidence {index}\n".encode())
    return root


def _evidence(
    root: Path,
    connection: SourceConnectivityConnectionIdentity,
    role: SourceConnectivityExecutableEvidenceRole,
) -> SourceConnectivityExecutableEvidence:
    reference = _EVIDENCE_REFERENCES[role]
    content = (root / reference).read_bytes()
    return SourceConnectivityExecutableEvidence(
        evidence_id=role.value.replace("_", "-"),
        role=role,
        connection=connection,
        locator=SourceConnectivityGrounding(
            locator_kind=SourceConnectivityGroundingLocatorKind.REPOSITORY,
            reference=reference,
            summary="Independent executable evidence stored in the test repository.",
        ),
        content_digest=sha256(content).hexdigest(),
    )


def _proof(root: Path, connection: SourceConnectivityConnectionIdentity) -> SourceConnectivityConnectedProof:
    return SourceConnectivityConnectedProof(
        resolver_ownership=SourceConnectivityResolverOwnershipProof(
            connection=connection,
            owner="calculation architecture",
            enrollment_evidence=(
                _evidence(root, connection, SourceConnectivityExecutableEvidenceRole.RESOLVER_ENROLLMENT),
            ),
        ),
        encrypted_revision=SourceConnectivityEncryptedRevisionProof(
            connection=connection,
            persisted_source_identity=connection.source_ref,
            persisted_source_fingerprint=_FINGERPRINT,
            strict_round_trip=True,
            encrypted_at_rest=True,
            anti_tautology_mutation=True,
            evidence=(_evidence(root, connection, SourceConnectivityExecutableEvidenceRole.ENCRYPTED_REVISION),),
        ),
        operator_reachability=SourceConnectivityOperatorReachabilityProof(
            connection=connection,
            entrypoint_id="cli",
            command_id=_COMMAND,
            route_id=ModeloCalculationRouteId.MODELO_WORK_CALCULATION,
            canonical_cli_path=_CLI_PATH,
            resolver_observed=True,
            evidence=(_evidence(root, connection, SourceConnectivityExecutableEvidenceRole.OPERATOR_REACHABILITY),),
        ),
    )


def _payload(
    connection: SourceConnectivityConnectionIdentity, proof: SourceConnectivityConnectedProof
) -> dict[str, object]:
    return {
        "candidate_id": connection.candidate_id,
        "disposition": SourceConnectivityDisposition.CONNECTED,
        "grounding": (proof.resolver_ownership.enrollment_evidence[0].locator,),
        "owner": "calculation architecture",
        "connected_proof": proof,
    }


def _composition(
    tmp_path: Path,
    secure_objects: SecureObjectRepository,
) -> tuple[
    LiveSourceConnectivityProofAuthority, SourceConnectivityConnectionIdentity, SourceConnectivityConnectedProof, Path
]:
    ownership = build_calculation_route_source_ownership_catalogue()
    owner = ownership.ownership_for(BindingSourceKind.COLLECTIBLE_INVOICE)
    assert isinstance(owner, CalculationRouteResolverSourceOwnership)
    provenance = CalculationSourceRef(
        resolver_id=owner.resolver_id,
        resolved_binding_source=BindingSourceKind.COLLECTIBLE_INVOICE,
        contributor_source_kind=BindingSourceKind.COLLECTIBLE_INVOICE.value,
        contributor_binding_source=BindingSourceKind.COLLECTIBLE_INVOICE,
        lineage_role=CalculationSourceLineageRole.PRIMARY,
        source_ref=_SOURCE_REF,
        parent_source_ref=None,
        fingerprint=_FINGERPRINT,
    )
    repository = CalculationRevisionCatalogueRepository(objects=secure_objects)
    revision = _persisted_revision(repository, (provenance,))
    connection = SourceConnectivityConnectionIdentity(
        candidate_id="invoice.collectible",
        source_kind=BindingSourceKind.COLLECTIBLE_INVOICE,
        source_ref=_SOURCE_REF,
        resolver_id=owner.resolver_id,
        calculation_revision_id=revision.calculation_revision_id,
    )
    root = _evidence_root(tmp_path)
    authority = LiveSourceConnectivityProofAuthority(
        source_ownership=ownership,
        workflows=_live_workflows(),
        calculation_revisions=repository,
        evidence_verifier=RepositoryRootEvidenceDigestVerifier(repository_root=root),
    )
    return authority, connection, _proof(root, connection), root


def test_real_live_authority_admits_coherent_encrypted_connected_row(
    tmp_path: Path,
    secure_objects: SecureObjectRepository,
) -> None:
    authority, connection, proof, _ = _composition(tmp_path, secure_objects)

    row = SourceConnectivityCensusRow.validate_with_authority(
        _payload(connection, proof),
        authority=authority,
    )

    assert row.connected_proof is not None
    assert row.connected_proof.connection == connection


@pytest.mark.parametrize(
    ("axis", "value"),
    (
        ("source_kind", BindingSourceKind.PAYABLE_INVOICE),
        ("source_ref", "collectible_invoice:inv-0002"),
        ("resolver_id", "invented-resolver"),
        ("calculation_revision_id", "f" * 64),
    ),
)
def test_real_live_authority_refuses_each_connection_identity_mutation(
    tmp_path: Path,
    secure_objects: SecureObjectRepository,
    axis: str,
    value: object,
) -> None:
    authority, connection, _, root = _composition(tmp_path, secure_objects)
    mutated = connection.model_copy(update={axis: value})
    proof = _proof(root, mutated)

    with pytest.raises(ValidationError):
        SourceConnectivityCensusRow.validate_with_authority(_payload(mutated, proof), authority=authority)


def test_connected_row_refuses_candidate_mutated_independently_of_proof(
    tmp_path: Path,
    secure_objects: SecureObjectRepository,
) -> None:
    authority, connection, proof, _ = _composition(tmp_path, secure_objects)
    payload = _payload(connection, proof) | {"candidate_id": "invoice.rival"}

    with pytest.raises(ValidationError, match="candidate_id must match"):
        SourceConnectivityCensusRow.validate_with_authority(payload, authority=authority)


@pytest.mark.parametrize(
    ("axis", "value"),
    (
        ("route_id", "invented-route"),
        ("canonical_cli_path", ("app", "quickfile")),
        ("command_id", "modelo.work.wizard"),
    ),
)
def test_real_live_authority_refuses_each_workflow_mutation(
    tmp_path: Path,
    secure_objects: SecureObjectRepository,
    axis: str,
    value: object,
) -> None:
    authority, connection, proof, _ = _composition(tmp_path, secure_objects)
    operator = proof.operator_reachability.model_copy(update={axis: value})
    changed = proof.model_copy(update={"operator_reachability": operator})

    with pytest.raises(ValidationError):
        SourceConnectivityCensusRow.validate_with_authority(_payload(connection, changed), authority=authority)


def test_real_live_authority_refuses_changed_missing_and_wrong_role_evidence(
    tmp_path: Path,
    secure_objects: SecureObjectRepository,
) -> None:
    authority, connection, proof, root = _composition(tmp_path, secure_objects)
    evidence = proof.operator_reachability.evidence[0]
    wrong_digest = evidence.model_copy(update={"content_digest": "e" * 64})
    changed_operator = proof.operator_reachability.model_copy(update={"evidence": (wrong_digest,)})
    with pytest.raises(ValidationError, match="absent or changed"):
        SourceConnectivityCensusRow.validate_with_authority(
            _payload(connection, proof.model_copy(update={"operator_reachability": changed_operator})),
            authority=authority,
        )

    (root / evidence.locator.reference).write_bytes(b"changed after proof")
    with pytest.raises(ValidationError, match="absent or changed"):
        SourceConnectivityCensusRow.validate_with_authority(_payload(connection, proof), authority=authority)

    (root / evidence.locator.reference).unlink()
    with pytest.raises(ValidationError, match="absent or changed"):
        SourceConnectivityCensusRow.validate_with_authority(_payload(connection, proof), authority=authority)

    wrong_role = evidence.model_copy(update={"role": SourceConnectivityExecutableEvidenceRole.ENCRYPTED_REVISION})
    with pytest.raises(ValidationError, match="must carry role"):
        SourceConnectivityOperatorReachabilityProof.model_validate(
            proof.operator_reachability.model_dump() | {"evidence": (wrong_role,)},
        )


def test_real_live_authority_refuses_deferred_reserved_and_missing_revision(
    tmp_path: Path,
    secure_objects: SecureObjectRepository,
) -> None:
    authority, connection, _, root = _composition(tmp_path, secure_objects)
    blocked_sources = tuple(
        source
        for source, disposition in CALCULATION_ROUTE_SOURCE_DISPOSITIONS.items()
        if disposition in {BindingSourceDisposition.DEFERRED, BindingSourceDisposition.RESERVED}
    )
    assert {CALCULATION_ROUTE_SOURCE_DISPOSITIONS[source] for source in blocked_sources} == {
        BindingSourceDisposition.DEFERRED,
        BindingSourceDisposition.RESERVED,
    }
    for source_kind in blocked_sources:
        changed = connection.model_copy(update={"source_kind": source_kind})
        with pytest.raises(ValidationError, match="not enrolled"):
            SourceConnectivityCensusRow.validate_with_authority(
                _payload(changed, _proof(root, changed)),
                authority=authority,
            )

    authority.calculation_revisions.save(CalculationRevisionCatalogue(revisions={}))
    with pytest.raises(ValidationError, match="does not match persisted source provenance"):
        SourceConnectivityCensusRow.validate_with_authority(
            _payload(connection, _proof(root, connection)),
            authority=authority,
        )


def test_canonical_ownership_projection_refuses_partial_and_invented_rows() -> None:
    catalogue = build_calculation_route_source_ownership_catalogue()
    with pytest.raises(ValidationError, match="exactly project"):
        CalculationRouteSourceOwnershipCatalogue(
            resolver_sources=catalogue.resolver_sources[:-1],
            manual_input=catalogue.manual_input,
        )
    with pytest.raises(ValidationError, match="exactly project"):
        CalculationRouteSourceOwnershipCatalogue(
            resolver_sources=(
                catalogue.resolver_sources[0].model_copy(update={"resolver_id": "invented-resolver"}),
                *catalogue.resolver_sources[1:],
            ),
            manual_input=catalogue.manual_input,
        )


def test_real_live_authority_refuses_persisted_provenance_mutations_and_ambiguity(
    tmp_path: Path,
    secure_objects: SecureObjectRepository,
) -> None:
    authority, connection, _, root = _composition(tmp_path, secure_objects)
    repository = authority.calculation_revisions
    assert isinstance(repository, CalculationRevisionCatalogueRepository)
    loaded = repository.load().revisions[connection.calculation_revision_id]
    persisted = loaded.source_provenance[0]

    for mutation in (
        {"resolver_id": "rival-resolver"},
        {"binding_source": BindingSourceKind.PAYABLE_INVOICE, "source_kind": BindingSourceKind.PAYABLE_INVOICE.value},
        {"source_ref": "collectible_invoice:inv-0002"},
        {"fingerprint": "sha256:" + "c" * 64},
    ):
        rival = persisted.model_copy(update=mutation)
        changed_revision = _persisted_revision(repository, (rival,))
        assert changed_revision.calculation_revision_id != connection.calculation_revision_id
        changed_connection = connection.model_copy(
            update={"calculation_revision_id": changed_revision.calculation_revision_id},
        )
        changed_proof = _proof(root, changed_connection)
        with pytest.raises(ValidationError):
            SourceConnectivityCensusRow.validate_with_authority(
                _payload(changed_connection, changed_proof),
                authority=authority,
            )

    ambiguous_revision = _persisted_revision(
        repository,
        (persisted, persisted.model_copy(update={"resolver_id": "rival-resolver"})),
    )
    assert ambiguous_revision.calculation_revision_id != connection.calculation_revision_id
    ambiguous_connection = connection.model_copy(
        update={"calculation_revision_id": ambiguous_revision.calculation_revision_id},
    )
    ambiguous_proof = _proof(root, ambiguous_connection)
    with pytest.raises(ValidationError):
        SourceConnectivityCensusRow.validate_with_authority(
            _payload(ambiguous_connection, ambiguous_proof),
            authority=authority,
        )


def test_legacy_revision_payloads_missing_resolver_or_provenance_are_refused() -> None:
    source_payload = {
        "source_kind": BindingSourceKind.FOREIGN_ASSET.value,
        "binding_source": BindingSourceKind.FOREIGN_ASSET,
        "source_ref": "foreign_asset:AD-ACCOUNT-001",
        "fingerprint": _FINGERPRINT,
    }
    with pytest.raises(ValidationError, match="resolver_id"):
        CalculationSourceRef.model_validate(source_payload)

    timestamp = datetime(2026, 8, 22, tzinfo=UTC)
    legacy_revision = {
        "calculation_revision_id": "d" * 64,
        "work_unit_id": _WORK_UNIT_ID,
        "state": CalculationRevisionState.BORRADOR,
        "input_values_by_casilla_id": {},
        "casilla_values": {},
        "filing_instance_evidence": None,
        "created_at": timestamp,
        "updated_at": timestamp,
    }
    with pytest.raises(ValidationError, match="source_provenance"):
        CalculationRevision.model_validate(legacy_revision)
