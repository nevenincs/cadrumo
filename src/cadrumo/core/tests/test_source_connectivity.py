"""Fail-closed contract tests for the source-connectivity census."""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from ...domain.modelos.calculation_revision import CalculationSourceRef
from ..aggregation import BindingSourceKind, CalculationSourceLineageRole
from ..calculation_route import ModeloCalculationRouteId
from ..source_connectivity import (
    SourceConnectivityCandidateIdentity,
    SourceConnectivityCensusRow,
    SourceConnectivityConnectedProof,
    SourceConnectivityConnectionIdentity,
    SourceConnectivityDisposition,
    SourceConnectivityEncryptedRevisionProof,
    SourceConnectivityExecutableEvidence,
    SourceConnectivityExecutableEvidenceRole,
    SourceConnectivityExpiryPosture,
    SourceConnectivityFollowUp,
    SourceConnectivityGrounding,
    SourceConnectivityGroundingLocatorKind,
    SourceConnectivityOperatorReachabilityProof,
    SourceConnectivityProofAuthority,
    SourceConnectivityProofFailureCause,
    SourceConnectivityResolverOwnershipProof,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_REVISION_ID = "a" * 64
_EVIDENCE_DIGEST = "b" * 64
_FINGERPRINT = "sha256:" + "c" * 64
_TEST_LOCATOR = "src/cadrumo/core/tests/test_source_connectivity.py:1"
_ENTRYPOINT_ID = "modelo-work-calculate"
_COMMAND_ID = "app.modelo.work.calculate"


class _CoreProtocolTestAuthority:
    """Core-only protocol probe; production authority behavior is tested in application."""

    def __init__(
        self,
        *,
        enrolled: frozenset[BindingSourceKind] = frozenset({BindingSourceKind.COLLECTIBLE_INVOICE}),
        workflows: frozenset[tuple[str, str]] = frozenset({(_ENTRYPOINT_ID, _COMMAND_ID)}),
        evidence_digests: dict[str, str] | None = None,
    ) -> None:
        self._enrolled = enrolled
        self._workflows = workflows
        self._evidence_digests = evidence_digests or {
            "resolver-enrollment": _EVIDENCE_DIGEST,
            "encrypted-revision": _EVIDENCE_DIGEST,
            "operator-reachability": _EVIDENCE_DIGEST,
        }

    def source_is_enrolled(self, connection: SourceConnectivityConnectionIdentity) -> bool:
        return connection.source_kind in self._enrolled

    def operator_workflow_reaches_source(
        self,
        connection: SourceConnectivityConnectionIdentity,
        proof: SourceConnectivityOperatorReachabilityProof,
    ) -> bool:
        return proof.connection == connection and (proof.entrypoint_id, proof.command_id) in self._workflows

    def executable_evidence_digest(
        self,
        evidence: SourceConnectivityExecutableEvidence,
    ) -> str | None:
        return self._evidence_digests.get(evidence.evidence_id)

    def encrypted_revision_matches(
        self,
        proof: SourceConnectivityEncryptedRevisionProof,
    ) -> bool:
        return (
            proof.persisted_source_identity == proof.connection.source_ref
            and proof.persisted_source_fingerprint == _FINGERPRINT
        )


class _WorkflowAuthorityWithoutConnection:
    """Deliberately stale implementation of the earlier workflow seam."""

    def __init__(self) -> None:
        self._authority = _CoreProtocolTestAuthority()

    def source_is_enrolled(self, connection: SourceConnectivityConnectionIdentity) -> bool:
        return self._authority.source_is_enrolled(connection)

    def operator_workflow_reaches_source(
        self,
        proof: SourceConnectivityOperatorReachabilityProof,
    ) -> bool:
        return (proof.entrypoint_id, proof.command_id) in self._authority._workflows

    def executable_evidence_digest(
        self,
        evidence: SourceConnectivityExecutableEvidence,
    ) -> str | None:
        return self._authority.executable_evidence_digest(evidence)

    def encrypted_revision_matches(
        self,
        proof: SourceConnectivityEncryptedRevisionProof,
    ) -> bool:
        return self._authority.encrypted_revision_matches(proof)


def _grounding(
    reference: str = _TEST_LOCATOR,
    *,
    kind: SourceConnectivityGroundingLocatorKind = SourceConnectivityGroundingLocatorKind.REPOSITORY,
) -> SourceConnectivityGrounding:
    return SourceConnectivityGrounding(
        locator_kind=kind,
        reference=reference,
        summary="Independent evidence for the asserted census fact.",
    )


def _connection(
    *,
    candidate_id: str = "invoice.collectible",
    source_kind: BindingSourceKind = BindingSourceKind.COLLECTIBLE_INVOICE,
    source_ref: str = "collectible_invoice:inv-0001",
    resolver_id: str = "invoice-source-resolver",
    revision_id: str = _REVISION_ID,
) -> SourceConnectivityConnectionIdentity:
    return SourceConnectivityConnectionIdentity(
        candidate_id=candidate_id,
        source_kind=source_kind,
        source_ref=source_ref,
        resolver_id=resolver_id,
        calculation_revision_id=revision_id,
    )


def _executable_evidence(
    connection: SourceConnectivityConnectionIdentity,
    *,
    evidence_id: str,
    role: SourceConnectivityExecutableEvidenceRole,
    reference: str = _TEST_LOCATOR,
    digest: str = _EVIDENCE_DIGEST,
) -> SourceConnectivityExecutableEvidence:
    return SourceConnectivityExecutableEvidence(
        evidence_id=evidence_id,
        role=role,
        connection=connection,
        locator=_grounding(reference),
        content_digest=digest,
    )


def _connected_proof(
    connection: SourceConnectivityConnectionIdentity,
    *,
    command_id: str = _COMMAND_ID,
    operator_reference: str = _TEST_LOCATOR,
) -> SourceConnectivityConnectedProof:
    resolver_evidence = _executable_evidence(
        connection,
        evidence_id="resolver-enrollment",
        role=SourceConnectivityExecutableEvidenceRole.RESOLVER_ENROLLMENT,
    )
    revision_evidence = _executable_evidence(
        connection,
        evidence_id="encrypted-revision",
        role=SourceConnectivityExecutableEvidenceRole.ENCRYPTED_REVISION,
    )
    operator_evidence = _executable_evidence(
        connection,
        evidence_id="operator-reachability",
        role=SourceConnectivityExecutableEvidenceRole.OPERATOR_REACHABILITY,
        reference=operator_reference,
    )
    return SourceConnectivityConnectedProof(
        resolver_ownership=SourceConnectivityResolverOwnershipProof(
            connection=connection,
            owner="calculation architecture",
            enrollment_evidence=(resolver_evidence,),
        ),
        encrypted_revision=SourceConnectivityEncryptedRevisionProof(
            connection=connection,
            persisted_source_identity=connection.source_ref,
            persisted_source_fingerprint=_FINGERPRINT,
            strict_round_trip=True,
            encrypted_at_rest=True,
            anti_tautology_mutation=True,
            evidence=(revision_evidence,),
        ),
        operator_reachability=SourceConnectivityOperatorReachabilityProof(
            connection=connection,
            entrypoint_id=_ENTRYPOINT_ID,
            command_id=command_id,
            route_id=ModeloCalculationRouteId.MODELO_WORK_CALCULATION,
            canonical_cli_path=("app", "modelo", "work", "calculate"),
            resolver_observed=True,
            evidence=(operator_evidence,),
        ),
    )


def _connected_payload(
    *,
    connection: SourceConnectivityConnectionIdentity | None = None,
    proof: SourceConnectivityConnectedProof | None = None,
) -> dict[str, object]:
    selected_connection = connection or _connection()
    selected_proof = proof or _connected_proof(selected_connection)
    return {
        "candidate_id": selected_connection.candidate_id,
        "disposition": SourceConnectivityDisposition.CONNECTED,
        "grounding": (_grounding(),),
        "owner": "calculation architecture",
        "connected_proof": selected_proof,
    }


def _basic_row_payload(disposition: SourceConnectivityDisposition) -> dict[str, object]:
    return {
        "candidate_id": "inventory.stock",
        "disposition": disposition,
        "grounding": (_grounding(),),
        "owner": "calculation architecture",
    }


def test_every_connectivity_owner_is_public_on_its_defining_module() -> None:
    """Every connectivity owner stays publicly enrolled where it is defined.

    This pinned the core facade's exported set. The facade is now an inert
    namespace, so the same enrolment is asserted one layer in, against the
    module that actually defines these types.
    """
    from .. import source_connectivity

    exposed = {name for name in source_connectivity.__all__ if name.startswith("SourceConnectivity")}
    assert exposed == {
        "SourceConnectivityCandidateId",
        "SourceConnectivityCandidateIdentity",
        "SourceConnectivityCensusRow",
        "SourceConnectivityConnectedProof",
        "SourceConnectivityConnectionIdentity",
        "SourceConnectivityDisposition",
        "SourceConnectivityEncryptedRevisionProof",
        "SourceConnectivityExecutableEvidence",
        "SourceConnectivityExecutableEvidenceRole",
        "SourceConnectivityExpiryPosture",
        "SourceConnectivityFollowUp",
        "SourceConnectivityGrounding",
        "SourceConnectivityGroundingLocatorKind",
        "SourceConnectivityOperatorReachabilityProof",
        "SourceConnectivityProofAuthority",
        "SourceConnectivityProofFailureCause",
        "SourceConnectivityResolverOwnershipProof",
    }
    assert exposed <= set(dir(source_connectivity))
    assert isinstance(_CoreProtocolTestAuthority(), SourceConnectivityProofAuthority)


def test_workflow_authority_without_connection_fails_at_protocol_usage() -> None:
    with pytest.raises(TypeError, match="positional argument"):
        SourceConnectivityCensusRow.model_validate(
            _connected_payload(),
            context={"source_connectivity_proof_authority": _WorkflowAuthorityWithoutConnection()},
        )


def test_workflow_authority_can_refuse_a_cross_connection_proof() -> None:
    authority = _CoreProtocolTestAuthority()
    connection = _connection()
    rival_connection = _connection(source_ref="collectible_invoice:inv-0002")
    rival_proof = _connected_proof(rival_connection).operator_reachability

    assert not authority.operator_workflow_reaches_source(connection, rival_proof)


@pytest.mark.parametrize("candidate_id", ["", "Inventory", "inventory stock", "inventory/stock"])
def test_candidate_identity_refuses_noncanonical_ids(candidate_id: str) -> None:
    with pytest.raises(ValidationError):
        SourceConnectivityCandidateIdentity(candidate_id=candidate_id)


def test_census_row_refuses_an_unknown_disposition() -> None:
    with pytest.raises(ValidationError):
        SourceConnectivityCensusRow.model_validate(
            _basic_row_payload(SourceConnectivityDisposition.NOT_APPLICABLE) | {"disposition": "invented"},
        )


@pytest.mark.parametrize(
    ("kind", "reference"),
    [
        (SourceConnectivityGroundingLocatorKind.HTTPS, "http://example.test/evidence"),
        (SourceConnectivityGroundingLocatorKind.HTTPS, "https://user@example.test/evidence"),
        (SourceConnectivityGroundingLocatorKind.LEGAL_REFERENCE, "Not Canonical"),
        (SourceConnectivityGroundingLocatorKind.SOURCE_REFERENCE, "source/ref"),
        (SourceConnectivityGroundingLocatorKind.REPOSITORY, "outside/repository.txt"),
        (SourceConnectivityGroundingLocatorKind.REPOSITORY, "src/../secret.txt"),
    ],
)
def test_grounding_refuses_unfetchable_locator_shapes(
    kind: SourceConnectivityGroundingLocatorKind,
    reference: str,
) -> None:
    with pytest.raises(ValidationError):
        _grounding(reference, kind=kind)


@pytest.mark.parametrize(
    "disposition",
    [
        SourceConnectivityDisposition.GROUNDING_BLOCKED,
        SourceConnectivityDisposition.INGRESS_BLOCKED,
        SourceConnectivityDisposition.REGISTRY_BLOCKED,
    ],
)
def test_blocked_rows_require_review_expiry_and_bounded_follow_up(
    disposition: SourceConnectivityDisposition,
) -> None:
    with pytest.raises(ValidationError, match="blocked connectivity row requires"):
        SourceConnectivityCensusRow.model_validate(_basic_row_payload(disposition))


def test_candidate_and_manual_rows_require_their_actionability_fields() -> None:
    with pytest.raises(ValidationError, match="connectivity candidate requires"):
        SourceConnectivityCensusRow.model_validate(
            _basic_row_payload(SourceConnectivityDisposition.CONNECT_CANDIDATE),
        )
    with pytest.raises(ValidationError, match="manual-by-design"):
        SourceConnectivityCensusRow.model_validate(
            _basic_row_payload(SourceConnectivityDisposition.MANUAL_BY_DESIGN),
        )


def test_expiry_posture_is_deterministic_at_the_explicit_boundary() -> None:
    row = SourceConnectivityCensusRow.model_validate(
        _basic_row_payload(SourceConnectivityDisposition.GROUNDING_BLOCKED)
        | {
            "review_condition": "Official evidence settles the target.",
            "expires_on": date(2026, 9, 1),
            "bounded_follow_up": SourceConnectivityFollowUp(
                action_id="inventory-grounding",
                deadline=date(2026, 9, 1),
                completion_criterion="The official destination is adjudicated.",
            ),
        },
    )
    assert row.expiry_posture(as_of=date(2026, 8, 31)) is SourceConnectivityExpiryPosture.CURRENT
    assert row.expiry_posture(as_of=date(2026, 9, 1)) is SourceConnectivityExpiryPosture.EXPIRED
    assert row.expiry_posture(as_of=date(2027, 1, 1)) is SourceConnectivityExpiryPosture.EXPIRED


def test_follow_up_deadline_cannot_outlive_review_and_owner_is_explicit_or_inherited() -> None:
    base = _basic_row_payload(SourceConnectivityDisposition.GROUNDING_BLOCKED) | {
        "review_condition": "Official evidence settles the target.",
        "expires_on": date(2026, 9, 1),
    }
    with pytest.raises(ValidationError, match="must not outlive"):
        SourceConnectivityCensusRow.model_validate(
            base
            | {
                "bounded_follow_up": SourceConnectivityFollowUp(
                    action_id="late-action",
                    deadline=date(2026, 9, 2),
                    completion_criterion="Close the evidence gap.",
                ),
            },
        )
    inherited = SourceConnectivityCensusRow.model_validate(
        base
        | {
            "bounded_follow_up": SourceConnectivityFollowUp(
                action_id="inherited-action",
                deadline=date(2026, 9, 1),
                completion_criterion="Close the evidence gap.",
            ),
        },
    )
    explicit = inherited.model_copy(
        update={
            "bounded_follow_up": SourceConnectivityFollowUp(
                action_id="explicit-action",
                owner="registry architecture",
                deadline=date(2026, 9, 1),
                completion_criterion="Close the registry gap.",
            ),
        },
    )
    assert inherited.follow_up_owner() == "calculation architecture"
    assert explicit.follow_up_owner() == "registry architecture"


def test_connected_claim_cannot_be_constructed_from_shape_without_authority() -> None:
    with pytest.raises(ValidationError, match="live proof authority"):
        SourceConnectivityCensusRow.model_validate(_connected_payload())


def test_authority_admits_a_complete_supported_connected_claim() -> None:
    row = SourceConnectivityCensusRow.validate_with_authority(
        _connected_payload(),
        authority=_CoreProtocolTestAuthority(),
    )
    assert row.disposition is SourceConnectivityDisposition.CONNECTED
    assert row.connected_proof is not None
    assert row.connected_proof.connection == _connection()


@pytest.mark.parametrize(
    "source_ref",
    [
        "percepcion:12345678Z:A:-",
        "invoice:INV-2026/0001",
        # Foreign-asset aggregation emits the actual contributing source kind
        # and object id, not a synthetic foreign_asset envelope.
        "payable_invoice:INV-2025-0007",
        " invoice:Case-And-Space/0002 ",
        "R" * 256,
    ],
)
def test_connectivity_source_reference_acceptance_matches_persisted_model_exactly(source_ref: str) -> None:
    persisted = CalculationSourceRef(
        resolver_id="invoice-source-resolver",
        resolved_binding_source=BindingSourceKind.COLLECTIBLE_INVOICE,
        contributor_source_kind=BindingSourceKind.COLLECTIBLE_INVOICE.value,
        contributor_binding_source=BindingSourceKind.COLLECTIBLE_INVOICE,
        lineage_role=CalculationSourceLineageRole.PRIMARY,
        source_ref=source_ref,
        parent_source_ref=None,
        fingerprint=_FINGERPRINT,
    )
    connection = _connection(source_ref=source_ref)
    proof = _connected_proof(connection).encrypted_revision
    assert connection.source_ref == persisted.source_ref == source_ref
    assert proof.persisted_source_identity == source_ref


@pytest.mark.parametrize("source_ref", ["", "R" * 257])
def test_connectivity_source_reference_rejection_matches_persisted_model(source_ref: str) -> None:
    with pytest.raises(ValidationError):
        CalculationSourceRef(
            resolver_id="invoice-source-resolver",
            resolved_binding_source=BindingSourceKind.COLLECTIBLE_INVOICE,
            contributor_source_kind=BindingSourceKind.COLLECTIBLE_INVOICE.value,
            contributor_binding_source=BindingSourceKind.COLLECTIBLE_INVOICE,
            lineage_role=CalculationSourceLineageRole.PRIMARY,
            parent_source_ref=None,
            source_ref=source_ref,
            fingerprint=_FINGERPRINT,
        )
    with pytest.raises(ValidationError):
        _connection(source_ref=source_ref)


@pytest.mark.parametrize(
    "mutated_field",
    ["candidate_id", "source_kind", "source_ref", "resolver_id", "calculation_revision_id"],
)
def test_connected_proof_refuses_every_cross_component_identity_mismatch(mutated_field: str) -> None:
    connection = _connection()
    proof = _connected_proof(connection)
    mutations: dict[str, object] = {
        "candidate_id": "different.candidate",
        "source_kind": BindingSourceKind.PROFILE,
        "source_ref": "foreign_asset:asset-0002",
        "resolver_id": "different-resolver",
        "calculation_revision_id": "d" * 64,
    }
    different = connection.model_copy(update={mutated_field: mutations[mutated_field]})
    with pytest.raises(
        ValidationError,
        match=r"same connection|asserted connection|persisted source identity",
    ):
        SourceConnectivityConnectedProof.model_validate(
            {
                "resolver_ownership": proof.resolver_ownership,
                "encrypted_revision": proof.encrypted_revision.model_copy(update={"connection": different}),
                "operator_reachability": proof.operator_reachability,
            },
        )


def test_role_specific_proof_refuses_unrelated_or_wrong_role_evidence() -> None:
    connection = _connection()
    unrelated = _connection(source_ref="foreign_asset:asset-0002")
    evidence = _executable_evidence(
        unrelated,
        evidence_id="wrong-evidence",
        role=SourceConnectivityExecutableEvidenceRole.OPERATOR_REACHABILITY,
    )
    with pytest.raises(ValidationError, match="asserted connection"):
        SourceConnectivityOperatorReachabilityProof(
            connection=connection,
            entrypoint_id=_ENTRYPOINT_ID,
            command_id=_COMMAND_ID,
            route_id=ModeloCalculationRouteId.MODELO_WORK_CALCULATION,
            canonical_cli_path=("app", "modelo", "work", "calculate"),
            resolver_observed=True,
            evidence=(evidence,),
        )
    wrong_role = evidence.model_copy(update={"connection": connection})
    with pytest.raises(ValidationError, match="must carry role"):
        SourceConnectivityEncryptedRevisionProof(
            connection=connection,
            persisted_source_identity=connection.source_ref,
            persisted_source_fingerprint=_FINGERPRINT,
            strict_round_trip=True,
            encrypted_at_rest=True,
            anti_tautology_mutation=True,
            evidence=(wrong_role,),
        )


@pytest.mark.parametrize("truthy", [1, "true", "1"])
def test_proof_truth_claims_reject_coercible_substitutes(truthy: object) -> None:
    connection = _connection()
    evidence = _executable_evidence(
        connection,
        evidence_id="encrypted-revision",
        role=SourceConnectivityExecutableEvidenceRole.ENCRYPTED_REVISION,
    )
    with pytest.raises(ValidationError):
        SourceConnectivityEncryptedRevisionProof.model_validate(
            {
                "connection": connection,
                "persisted_source_identity": connection.source_ref,
                "persisted_source_fingerprint": _FINGERPRINT,
                "strict_round_trip": truthy,
                "encrypted_at_rest": truthy,
                "anti_tautology_mutation": truthy,
                "evidence": (evidence,),
            },
        )


def test_false_strict_proof_assertion_is_refused() -> None:
    connection = _connection()
    evidence = _executable_evidence(
        connection,
        evidence_id="encrypted-revision",
        role=SourceConnectivityExecutableEvidenceRole.ENCRYPTED_REVISION,
    )
    with pytest.raises(ValidationError, match="every strict proof assertion"):
        SourceConnectivityEncryptedRevisionProof(
            connection=connection,
            persisted_source_identity=connection.source_ref,
            persisted_source_fingerprint=_FINGERPRINT,
            strict_round_trip=True,
            encrypted_at_rest=False,
            anti_tautology_mutation=True,
            evidence=(evidence,),
        )


@pytest.mark.parametrize(
    "persisted_source_identity",
    [
        "inv-0001",
        "collectible_invoice:inv-00001",
        "foreign_asset:inv-0001",
    ],
)
def test_encrypted_revision_proof_refuses_raw_or_normalised_source_reference_drift(
    persisted_source_identity: str,
) -> None:
    connection = _connection()
    proof = _connected_proof(connection).encrypted_revision
    with pytest.raises(ValidationError, match="persisted source identity"):
        SourceConnectivityEncryptedRevisionProof.model_validate(
            proof.model_dump() | {"persisted_source_identity": persisted_source_identity},
        )


def test_authority_refuses_persisted_source_fingerprint_drift() -> None:
    connection = _connection()
    connected_proof = _connected_proof(connection)
    changed_revision_proof = connected_proof.encrypted_revision.model_copy(
        update={"persisted_source_fingerprint": "sha256:" + "d" * 64},
    )
    changed_proof = connected_proof.model_copy(update={"encrypted_revision": changed_revision_proof})
    with pytest.raises(ValidationError, match="does not match persisted source provenance"):
        SourceConnectivityCensusRow.validate_with_authority(
            _connected_payload(connection=connection, proof=changed_proof),
            authority=_CoreProtocolTestAuthority(),
        )


def test_authority_refuses_a_deferred_source_kind() -> None:
    connection = _connection(source_kind=BindingSourceKind.RELATED_PARTY_OPERATION)
    with pytest.raises(ValidationError, match="not enrolled"):
        SourceConnectivityCensusRow.validate_with_authority(
            _connected_payload(connection=connection),
            authority=_CoreProtocolTestAuthority(),
        )


def test_authority_refuses_an_arbitrary_operator_command_identity() -> None:
    connection = _connection()
    proof = _connected_proof(connection, command_id="anything")
    with pytest.raises(ValidationError, match="workflow is not supported"):
        SourceConnectivityCensusRow.validate_with_authority(
            _connected_payload(connection=connection, proof=proof),
            authority=_CoreProtocolTestAuthority(),
        )


@pytest.mark.parametrize(
    ("failure", "expected_cause"),
    (
        ("source_enrollment", SourceConnectivityProofFailureCause.SOURCE_NOT_ENROLLED),
        ("operator_workflow", SourceConnectivityProofFailureCause.OPERATOR_WORKFLOW_UNSUPPORTED),
        ("encrypted_provenance", SourceConnectivityProofFailureCause.ENCRYPTED_PROVENANCE_MISMATCH),
    ),
)
def test_connected_proof_failures_emit_their_structured_pydantic_cause(
    failure: str,
    expected_cause: SourceConnectivityProofFailureCause,
) -> None:
    """Classified live-proof failures must not collapse to Pydantic's ``value_error`` fallback."""
    connection = _connection()
    proof = _connected_proof(connection)
    authority = _CoreProtocolTestAuthority()
    if failure == "source_enrollment":
        authority = _CoreProtocolTestAuthority(enrolled=frozenset())
    elif failure == "operator_workflow":
        authority = _CoreProtocolTestAuthority(workflows=frozenset())
    else:
        encrypted_revision = proof.encrypted_revision.model_copy(
            update={"persisted_source_fingerprint": "sha256:" + "d" * 64},
        )
        proof = proof.model_copy(update={"encrypted_revision": encrypted_revision})

    with pytest.raises(ValidationError) as error:
        SourceConnectivityCensusRow.validate_with_authority(
            _connected_payload(connection=connection, proof=proof),
            authority=authority,
        )

    error_type = error.value.errors(include_url=False)[0]["type"]
    assert error_type == expected_cause.value
    assert error_type != "value_error"
    assert (
        SourceConnectivityProofFailureCause.from_validation_error_type("value_error")
        is SourceConnectivityProofFailureCause.LIVE_PROOF_VALIDATION_FAILED
    )
    assert SourceConnectivityProofFailureCause.from_validation_error_type(error_type) is expected_cause


def test_authority_refuses_missing_or_changed_executable_evidence() -> None:
    connection = _connection()
    missing_proof = _connected_proof(
        connection,
        operator_reference="src/cadrumo/fake/tests/test_does_not_exist.py:999",
    )
    with pytest.raises(ValidationError) as missing_error:
        SourceConnectivityCensusRow.validate_with_authority(
            _connected_payload(connection=connection, proof=missing_proof),
            authority=_CoreProtocolTestAuthority(
                evidence_digests={
                    "resolver-enrollment": _EVIDENCE_DIGEST,
                    "encrypted-revision": _EVIDENCE_DIGEST,
                },
            ),
        )
    assert missing_error.value.errors(include_url=False)[0]["type"] == (
        SourceConnectivityProofFailureCause.EXECUTABLE_EVIDENCE_MISSING.value
    )
    with pytest.raises(ValidationError) as digest_mismatch_error:
        SourceConnectivityCensusRow.validate_with_authority(
            _connected_payload(connection=connection),
            authority=_CoreProtocolTestAuthority(
                evidence_digests={
                    "resolver-enrollment": _EVIDENCE_DIGEST,
                    "encrypted-revision": _EVIDENCE_DIGEST,
                    "operator-reachability": "e" * 64,
                },
            ),
        )
    assert digest_mismatch_error.value.errors(include_url=False)[0]["type"] == (
        SourceConnectivityProofFailureCause.EXECUTABLE_EVIDENCE_DIGEST_MISMATCH.value
    )
    assert (
        SourceConnectivityProofFailureCause.from_validation_error_type(
            digest_mismatch_error.value.errors(include_url=False)[0]["type"],
        )
        is SourceConnectivityProofFailureCause.EXECUTABLE_EVIDENCE_DIGEST_MISMATCH
    )


def test_connected_proof_rejects_non_test_executable_evidence_shape() -> None:
    connection = _connection()
    with pytest.raises(ValidationError, match="test module"):
        _executable_evidence(
            connection,
            evidence_id="implementation-only",
            role=SourceConnectivityExecutableEvidenceRole.RESOLVER_ENROLLMENT,
            reference="src/cadrumo/application/aggregation/_source_mesh.py:1",
        )
