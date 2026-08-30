"""Real encrypted integration proof for connected source-census rows."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime
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
    SourceConnectivityProofFailureCause,
    SourceConnectivityResolverOwnershipProof,
)
from ....domain.modelos import CalculationRevisionPersistenceError
from ....domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionCatalogue,
    CalculationRevisionState,
    CalculationSourceRef,
    derive_calculation_revision_id,
)
from ....entrypoints.cli import current_operator_surface_reconciliation
from ...aggregation import BindingSourceDisposition
from ...modelo.calculation_route import CALCULATION_ROUTE_SOURCE_DISPOSITIONS
from ...operator_surface.calculation_workflows import build_supported_modelo_calculation_workflow_catalogue
from ..source_connectivity import SourceConnectivityCensusEntry, load_source_connectivity_census
from ..source_connectivity_authority import (
    CalculationRouteResolverSourceOwnership,
    CalculationRouteSourceOwnershipCatalogue,
    LiveSourceConnectivityProofAuthority,
    LiveSourceConnectivityProofExpectation,
    RepositoryRootEvidenceDigestVerifier,
    build_calculation_route_source_ownership_catalogue,
)
from ..source_connectivity_coverage import compose_source_connectivity_coverage

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
    return build_supported_modelo_calculation_workflow_catalogue(current_operator_surface_reconciliation())


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
    loaded = repository.load().revisions[revision_id]
    assert loaded == revision
    assert loaded.source_provenance == provenance
    return loaded


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


def test_independent_expectation_rejects_census_owned_workflow_and_destination_mutations(
    tmp_path: Path,
    secure_objects: SecureObjectRepository,
) -> None:
    authority, connection, proof, _ = _composition(tmp_path, secure_objects)
    expectation = LiveSourceConnectivityProofExpectation(
        connection=connection,
        entrypoint_id=proof.operator_reachability.entrypoint_id,
        command_id=proof.operator_reachability.command_id,
        route_id=proof.operator_reachability.route_id,
        canonical_cli_path=proof.operator_reachability.canonical_cli_path,
        destination_identities=(("casilla_semantic_role", "100", "2025", "2025", "0A", "inventory.increase"),),
    )
    constrained = replace(authority, independent_expectations=(expectation,))

    SourceConnectivityCensusRow.validate_with_authority(
        _payload(connection, proof),
        authority=constrained,
    )
    mutated_operator = proof.operator_reachability.model_copy(
        update={"command_id": "modelo.work.wizard"},
    )
    with pytest.raises(ValidationError, match="workflow is not supported"):
        SourceConnectivityCensusRow.validate_with_authority(
            _payload(connection, proof.model_copy(update={"operator_reachability": mutated_operator})),
            authority=constrained,
        )
    assert constrained.destinations_match(connection, expectation.destination_identities)
    assert not constrained.destinations_match(
        connection,
        (("casilla_semantic_role", "100", "2025", "2025", "0A", "inventory.decrease"),),
    )


def test_real_live_authority_encrypted_payload_roundtrip_and_raw_lineage_deletion(
    tmp_path: Path,
    secure_objects: SecureObjectRepository,
) -> None:
    import json

    from ....adapters.persistence.profile.modelos_calculation import (
        _CALCULATION_CATALOGUE_VERSION,
        _CALCULATION_NAMESPACE,
        _CALCULATION_OBJECT_KEY,
    )
    from ....adapters.persistence.storage import SensitivityClass

    authority, connection, proof, _ = _composition(tmp_path, secure_objects)
    repository = authority.calculation_revisions
    assert isinstance(repository, CalculationRevisionCatalogueRepository)
    loaded = repository.load().revisions[connection.calculation_revision_id]
    persisted = loaded.source_provenance[0]
    assert persisted.resolver_id == connection.resolver_id
    assert persisted.resolved_binding_source is connection.source_kind
    assert persisted.source_ref == proof.encrypted_revision.persisted_source_identity
    assert persisted.fingerprint == proof.encrypted_revision.persisted_source_fingerprint

    record = secure_objects.load(
        _CALCULATION_NAMESPACE,
        _CALCULATION_OBJECT_KEY,
        expected_class=SensitivityClass.FINANCIAL,
        max_supported_version=_CALCULATION_CATALOGUE_VERSION,
    )
    assert record is not None
    envelope = json.loads(record.payload.decode("utf-8"))
    raw_row = envelope["payload"]["revisions"][connection.calculation_revision_id]["source_provenance"][0]
    assert raw_row == persisted.model_dump(mode="json")
    assert raw_row.pop("lineage_role") == CalculationSourceLineageRole.PRIMARY.value
    secure_objects.save(
        namespace=_CALCULATION_NAMESPACE,
        object_key=_CALCULATION_OBJECT_KEY,
        classification=record.classification,
        schema_version=record.schema_version,
        written_at=record.written_at,
        payload=json.dumps(envelope).encode("utf-8"),
    )

    with pytest.raises(CalculationRevisionPersistenceError, match="payload is invalid") as error:
        repository.load()
    assert error.value.context == {"reason": "invalid_payload"}


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
    with pytest.raises(ValidationError) as wrong_digest_error:
        SourceConnectivityCensusRow.validate_with_authority(
            _payload(connection, proof.model_copy(update={"operator_reachability": changed_operator})),
            authority=authority,
        )
    assert wrong_digest_error.value.errors(include_url=False)[0]["type"] == (
        SourceConnectivityProofFailureCause.EXECUTABLE_EVIDENCE_DIGEST_MISMATCH.value
    )

    (root / evidence.locator.reference).write_bytes(b"changed after proof")
    with pytest.raises(ValidationError) as drift_error:
        SourceConnectivityCensusRow.validate_with_authority(_payload(connection, proof), authority=authority)
    assert drift_error.value.errors(include_url=False)[0]["type"] == (
        SourceConnectivityProofFailureCause.EXECUTABLE_EVIDENCE_DIGEST_MISMATCH.value
    )

    (root / evidence.locator.reference).unlink()
    with pytest.raises(ValidationError) as deletion_error:
        SourceConnectivityCensusRow.validate_with_authority(_payload(connection, proof), authority=authority)
    assert deletion_error.value.errors(include_url=False)[0]["type"] == (
        SourceConnectivityProofFailureCause.EXECUTABLE_EVIDENCE_MISSING.value
    )

    wrong_role = evidence.model_copy(update={"role": SourceConnectivityExecutableEvidenceRole.ENCRYPTED_REVISION})
    with pytest.raises(ValidationError, match="must carry role"):
        SourceConnectivityOperatorReachabilityProof.model_validate(
            proof.operator_reachability.model_dump() | {"evidence": (wrong_role,)},
        )


@pytest.mark.parametrize(
    ("mutation", "expected_reason", "expected_detail"),
    (
        ("digest_drift", "conflicting_evidence", "digest does not match"),
        ("evidence_deletion", "missing_evidence", "evidence is missing"),
    ),
)
def test_coverage_composer_classifies_live_executable_evidence_failures(
    tmp_path: Path,
    secure_objects: SecureObjectRepository,
    registry_authority,
    mutation: str,
    expected_reason: str,
    expected_detail: str,
) -> None:
    """Live proof deletion and digest drift must refuse through different closed causes."""
    authority, connection, proof, root = _composition(tmp_path, secure_objects)
    census = load_source_connectivity_census()
    inventory = next(entry for entry in census.entries if entry.candidate_id == "inventory.stock-valuation")
    connected = inventory.model_copy(
        update={
            "candidate_id": connection.candidate_id,
            "disposition": SourceConnectivityDisposition.CONNECTED,
            "connected_proof": proof,
            "review_condition": None,
            "bounded_follow_up": None,
        },
    )
    connected_census = census.model_copy(
        update={
            "entries": tuple(
                connected if entry.candidate_id == inventory.candidate_id else entry for entry in census.entries
            ),
        },
    )

    before_drift = compose_source_connectivity_coverage(
        authority=registry_authority,
        census=connected_census,
        as_of=date(2026, 8, 24),
        proof_authority=authority,
    )
    before_limb = next(limb for limb in before_drift.limbs if (limb.modelo, limb.revision) == ("100", "2025"))
    assert (before_limb.outcome, before_limb.refusal) == ("satisfied", None)

    evidence = proof.operator_reachability.evidence[0]
    evidence_path = root / evidence.locator.reference
    if mutation == "digest_drift":
        evidence_path.write_bytes(b"changed after initial census validation")
    else:
        evidence_path.unlink()

    after_drift = compose_source_connectivity_coverage(
        authority=registry_authority,
        census=connected_census,
        as_of=date(2026, 8, 24),
        proof_authority=authority,
    )
    after_limb = next(limb for limb in after_drift.limbs if (limb.modelo, limb.revision) == ("100", "2025"))

    assert after_limb.refusal is not None
    assert (after_limb.outcome, after_limb.refusal.reason) == ("refused", expected_reason)
    assert expected_detail in after_limb.refusal.detail


@pytest.mark.parametrize(
    ("failure", "expected_cause", "expected_detail"),
    (
        (
            "source_enrollment",
            SourceConnectivityProofFailureCause.SOURCE_NOT_ENROLLED,
            "source is not enrolled",
        ),
        (
            "operator_workflow",
            SourceConnectivityProofFailureCause.OPERATOR_WORKFLOW_UNSUPPORTED,
            "workflow is not supported",
        ),
        (
            "encrypted_provenance",
            SourceConnectivityProofFailureCause.ENCRYPTED_PROVENANCE_MISMATCH,
            "does not match persisted source provenance",
        ),
    ),
)
def test_coverage_composer_classifies_structured_live_proof_failures(
    tmp_path: Path,
    secure_objects: SecureObjectRepository,
    registry_authority,
    failure: str,
    expected_cause: SourceConnectivityProofFailureCause,
    expected_detail: str,
) -> None:
    """Every non-digest live-proof cause is a missing-evidence closure refusal."""
    authority, connection, proof, _ = _composition(tmp_path, secure_objects)
    if failure == "source_enrollment":
        connection = connection.model_copy(update={"resolver_id": "rival-resolver"})
        proof = _proof(tmp_path / "evidence-repository", connection)
    elif failure == "operator_workflow":
        operator = proof.operator_reachability.model_copy(update={"command_id": "modelo.work.wizard"})
        proof = proof.model_copy(update={"operator_reachability": operator})
    else:
        encrypted_revision = proof.encrypted_revision.model_copy(
            update={"persisted_source_fingerprint": "sha256:" + "d" * 64},
        )
        proof = proof.model_copy(update={"encrypted_revision": encrypted_revision})

    with pytest.raises(ValidationError) as error:
        SourceConnectivityCensusRow.validate_with_authority(_payload(connection, proof), authority=authority)
    assert error.value.errors(include_url=False)[0]["type"] == expected_cause.value

    census = load_source_connectivity_census()
    inventory = next(entry for entry in census.entries if entry.candidate_id == "inventory.stock-valuation")
    connected = inventory.model_copy(
        update={
            "candidate_id": connection.candidate_id,
            "disposition": SourceConnectivityDisposition.CONNECTED,
            "connected_proof": proof,
            "review_condition": None,
            "bounded_follow_up": None,
        },
    )
    connected_census = census.model_copy(
        update={
            "entries": tuple(
                connected if entry.candidate_id == inventory.candidate_id else entry for entry in census.entries
            ),
        },
    )

    report = compose_source_connectivity_coverage(
        authority=registry_authority,
        census=connected_census,
        as_of=date(2026, 8, 24),
        proof_authority=authority,
    )
    limb = next(limb for limb in report.limbs if (limb.modelo, limb.revision) == ("100", "2025"))

    assert limb.refusal is not None
    assert (limb.outcome, limb.refusal.reason) == ("refused", "missing_evidence")
    assert expected_detail in limb.refusal.detail


def test_coverage_composer_fails_closed_on_generic_live_proof_validation_error(
    tmp_path: Path,
    secure_objects: SecureObjectRepository,
    registry_authority,
) -> None:
    """A malformed admitted proof must reach the fallback as a refused source limb."""
    authority, connection, proof, _ = _composition(tmp_path, secure_objects)
    census = load_source_connectivity_census()
    inventory = next(entry for entry in census.entries if entry.candidate_id == "inventory.stock-valuation")
    connected = inventory.model_copy(
        update={
            "candidate_id": connection.candidate_id,
            "disposition": SourceConnectivityDisposition.CONNECTED,
            "connected_proof": proof,
            "review_condition": None,
            "bounded_follow_up": None,
        },
    )
    assert (
        SourceConnectivityCensusEntry.validate_with_authority(
            connected.model_dump(mode="python"),
            authority=authority,
        )
        == connected
    )

    # Model a corrupted in-memory census record after its initial admission.
    # The composer must revalidate rather than trusting this frozen-model instance.
    object.__setattr__(connected, "connected_proof", None)
    with pytest.raises(ValidationError) as validation_error:
        SourceConnectivityCensusEntry.validate_with_authority(
            connected.model_dump(mode="python"),
            authority=authority,
        )
    error_type = validation_error.value.errors(include_url=False)[0]["type"]
    assert error_type == "value_error"
    assert (
        SourceConnectivityProofFailureCause.from_validation_error_type(error_type)
        is SourceConnectivityProofFailureCause.LIVE_PROOF_VALIDATION_FAILED
    )

    connected_census = census.model_copy(
        update={
            "entries": tuple(
                connected if entry.candidate_id == inventory.candidate_id else entry for entry in census.entries
            ),
        },
    )
    report = compose_source_connectivity_coverage(
        authority=registry_authority,
        census=connected_census,
        as_of=date(2026, 8, 24),
        proof_authority=authority,
    )
    limb = next(limb for limb in report.limbs if (limb.modelo, limb.revision) == ("100", "2025"))

    assert limb.refusal is not None
    assert (limb.outcome, limb.refusal.reason) == ("refused", "missing_evidence")
    assert "connected connectivity row requires complete connected_proof" in limb.refusal.detail


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
        {"resolved_binding_source": BindingSourceKind.PAYABLE_INVOICE},
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

    with pytest.raises(ValidationError, match="primary reference is ambiguous"):
        _persisted_revision(
            repository,
            (persisted, persisted.model_copy(update={"resolver_id": "rival-resolver"})),
        )


def test_legacy_revision_payloads_missing_resolver_or_provenance_are_refused() -> None:
    source_payload = {
        "resolved_binding_source": BindingSourceKind.FOREIGN_ASSET,
        "contributor_source_kind": BindingSourceKind.FOREIGN_ASSET.value,
        "contributor_binding_source": BindingSourceKind.FOREIGN_ASSET,
        "lineage_role": CalculationSourceLineageRole.PRIMARY,
        "source_ref": "foreign_asset:AD-ACCOUNT-001",
        "parent_source_ref": None,
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
