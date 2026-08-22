"""Fail-closed contract tests for the source-connectivity census."""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from ... import core

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_REVISION_ID = "a" * 64
_EVIDENCE_DIGEST = "b" * 64
_FINGERPRINT = "sha256:" + "c" * 64
_TEST_LOCATOR = "src/cadrumo/core/tests/test_source_connectivity.py:1"
_ENTRYPOINT_ID = "modelo-work-calculate"
_COMMAND_ID = "app.modelo.work.calculate"


class _ProofAuthority:
    """Deterministic representative of the application-owned authority seam."""

    def __init__(
        self,
        *,
        enrolled: frozenset[core.BindingSourceKind] = frozenset({core.BindingSourceKind.MANUAL_INPUT}),
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

    def source_is_enrolled(self, connection: core.SourceConnectivityConnectionIdentity) -> bool:
        return connection.source_kind in self._enrolled

    def operator_workflow_is_supported(
        self,
        connection: core.SourceConnectivityConnectionIdentity,
        *,
        entrypoint_id: str,
        command_id: str,
    ) -> bool:
        del connection
        return (entrypoint_id, command_id) in self._workflows

    def executable_evidence_digest(
        self,
        evidence: core.SourceConnectivityExecutableEvidence,
    ) -> str | None:
        return self._evidence_digests.get(evidence.evidence_id)

    def encrypted_revision_matches(
        self,
        proof: core.SourceConnectivityEncryptedRevisionProof,
    ) -> bool:
        return (
            proof.persisted_source_identity == proof.connection.source_object_id
            and proof.persisted_source_fingerprint == _FINGERPRINT
        )


def _grounding(
    reference: str = _TEST_LOCATOR,
    *,
    kind: core.SourceConnectivityGroundingLocatorKind = core.SourceConnectivityGroundingLocatorKind.REPOSITORY,
) -> core.SourceConnectivityGrounding:
    return core.SourceConnectivityGrounding(
        locator_kind=kind,
        reference=reference,
        summary="Independent evidence for the asserted census fact.",
    )


def _connection(
    *,
    candidate_id: str = "inventory.stock",
    source_kind: core.BindingSourceKind = core.BindingSourceKind.MANUAL_INPUT,
    source_object_id: str = "inventory-2026",
    resolver_id: str = "inventory-resolver",
    revision_id: str = _REVISION_ID,
) -> core.SourceConnectivityConnectionIdentity:
    return core.SourceConnectivityConnectionIdentity(
        candidate_id=candidate_id,
        source_kind=source_kind,
        source_object_id=source_object_id,
        resolver_id=resolver_id,
        calculation_revision_id=revision_id,
    )


def _executable_evidence(
    connection: core.SourceConnectivityConnectionIdentity,
    *,
    evidence_id: str,
    role: core.SourceConnectivityExecutableEvidenceRole,
    reference: str = _TEST_LOCATOR,
    digest: str = _EVIDENCE_DIGEST,
) -> core.SourceConnectivityExecutableEvidence:
    return core.SourceConnectivityExecutableEvidence(
        evidence_id=evidence_id,
        role=role,
        connection=connection,
        locator=_grounding(reference),
        content_digest=digest,
    )


def _connected_proof(
    connection: core.SourceConnectivityConnectionIdentity,
    *,
    command_id: str = _COMMAND_ID,
    operator_reference: str = _TEST_LOCATOR,
) -> core.SourceConnectivityConnectedProof:
    resolver_evidence = _executable_evidence(
        connection,
        evidence_id="resolver-enrollment",
        role=core.SourceConnectivityExecutableEvidenceRole.RESOLVER_ENROLLMENT,
    )
    revision_evidence = _executable_evidence(
        connection,
        evidence_id="encrypted-revision",
        role=core.SourceConnectivityExecutableEvidenceRole.ENCRYPTED_REVISION,
    )
    operator_evidence = _executable_evidence(
        connection,
        evidence_id="operator-reachability",
        role=core.SourceConnectivityExecutableEvidenceRole.OPERATOR_REACHABILITY,
        reference=operator_reference,
    )
    return core.SourceConnectivityConnectedProof(
        resolver_ownership=core.SourceConnectivityResolverOwnershipProof(
            connection=connection,
            owner="calculation architecture",
            enrollment_evidence=(resolver_evidence,),
        ),
        encrypted_revision=core.SourceConnectivityEncryptedRevisionProof(
            connection=connection,
            persisted_source_identity=connection.source_object_id,
            persisted_source_fingerprint=_FINGERPRINT,
            strict_round_trip=True,
            encrypted_at_rest=True,
            anti_tautology_mutation=True,
            evidence=(revision_evidence,),
        ),
        operator_reachability=core.SourceConnectivityOperatorReachabilityProof(
            connection=connection,
            entrypoint_id=_ENTRYPOINT_ID,
            command_id=command_id,
            resolver_observed=True,
            evidence=(operator_evidence,),
        ),
    )


def _connected_payload(
    *,
    connection: core.SourceConnectivityConnectionIdentity | None = None,
    proof: core.SourceConnectivityConnectedProof | None = None,
) -> dict[str, object]:
    selected_connection = connection or _connection()
    selected_proof = proof or _connected_proof(selected_connection)
    return {
        "candidate_id": selected_connection.candidate_id,
        "disposition": core.SourceConnectivityDisposition.CONNECTED,
        "grounding": (_grounding(),),
        "owner": "calculation architecture",
        "connected_proof": selected_proof,
    }


def _basic_row_payload(disposition: core.SourceConnectivityDisposition) -> dict[str, object]:
    return {
        "candidate_id": "inventory.stock",
        "disposition": disposition,
        "grounding": (_grounding(),),
        "owner": "calculation architecture",
    }


def test_core_facade_exposes_every_connectivity_owner() -> None:
    expected = {
        name for name in core.__all__ if name.startswith("SourceConnectivity")
    }
    assert expected == {
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
        "SourceConnectivityResolverOwnershipProof",
    }
    assert expected <= set(dir(core))
    assert isinstance(_ProofAuthority(), core.SourceConnectivityProofAuthority)


@pytest.mark.parametrize("candidate_id", ["", "Inventory", "inventory stock", "inventory/stock"])
def test_candidate_identity_refuses_noncanonical_ids(candidate_id: str) -> None:
    with pytest.raises(ValidationError):
        core.SourceConnectivityCandidateIdentity(candidate_id=candidate_id)


def test_census_row_refuses_an_unknown_disposition() -> None:
    with pytest.raises(ValidationError):
        core.SourceConnectivityCensusRow.model_validate(
            _basic_row_payload(core.SourceConnectivityDisposition.NOT_APPLICABLE)
            | {"disposition": "invented"},
        )


@pytest.mark.parametrize(
    ("kind", "reference"),
    [
        (core.SourceConnectivityGroundingLocatorKind.HTTPS, "http://example.test/evidence"),
        (core.SourceConnectivityGroundingLocatorKind.HTTPS, "https://user@example.test/evidence"),
        (core.SourceConnectivityGroundingLocatorKind.LEGAL_REFERENCE, "Not Canonical"),
        (core.SourceConnectivityGroundingLocatorKind.SOURCE_REFERENCE, "source/ref"),
        (core.SourceConnectivityGroundingLocatorKind.REPOSITORY, "outside/repository.txt"),
        (core.SourceConnectivityGroundingLocatorKind.REPOSITORY, "src/../secret.txt"),
    ],
)
def test_grounding_refuses_unfetchable_locator_shapes(
    kind: core.SourceConnectivityGroundingLocatorKind,
    reference: str,
) -> None:
    with pytest.raises(ValidationError):
        _grounding(reference, kind=kind)


@pytest.mark.parametrize(
    "disposition",
    [
        core.SourceConnectivityDisposition.GROUNDING_BLOCKED,
        core.SourceConnectivityDisposition.INGRESS_BLOCKED,
        core.SourceConnectivityDisposition.REGISTRY_BLOCKED,
    ],
)
def test_blocked_rows_require_review_expiry_and_bounded_follow_up(
    disposition: core.SourceConnectivityDisposition,
) -> None:
    with pytest.raises(ValidationError, match="blocked connectivity row requires"):
        core.SourceConnectivityCensusRow.model_validate(_basic_row_payload(disposition))


def test_candidate_and_manual_rows_require_their_actionability_fields() -> None:
    with pytest.raises(ValidationError, match="connectivity candidate requires"):
        core.SourceConnectivityCensusRow.model_validate(
            _basic_row_payload(core.SourceConnectivityDisposition.CONNECT_CANDIDATE),
        )
    with pytest.raises(ValidationError, match="manual-by-design"):
        core.SourceConnectivityCensusRow.model_validate(
            _basic_row_payload(core.SourceConnectivityDisposition.MANUAL_BY_DESIGN),
        )


def test_expiry_posture_is_deterministic_at_the_explicit_boundary() -> None:
    row = core.SourceConnectivityCensusRow.model_validate(
        _basic_row_payload(core.SourceConnectivityDisposition.GROUNDING_BLOCKED)
        | {
            "review_condition": "Official evidence settles the target.",
            "expires_on": date(2026, 9, 1),
            "bounded_follow_up": core.SourceConnectivityFollowUp(
                action_id="inventory-grounding",
                deadline=date(2026, 9, 1),
                completion_criterion="The official destination is adjudicated.",
            ),
        },
    )
    assert row.expiry_posture(as_of=date(2026, 8, 31)) is core.SourceConnectivityExpiryPosture.CURRENT
    assert row.expiry_posture(as_of=date(2026, 9, 1)) is core.SourceConnectivityExpiryPosture.EXPIRED
    assert row.expiry_posture(as_of=date(2027, 1, 1)) is core.SourceConnectivityExpiryPosture.EXPIRED


def test_follow_up_deadline_cannot_outlive_review_and_owner_is_explicit_or_inherited() -> None:
    base = _basic_row_payload(core.SourceConnectivityDisposition.GROUNDING_BLOCKED) | {
        "review_condition": "Official evidence settles the target.",
        "expires_on": date(2026, 9, 1),
    }
    with pytest.raises(ValidationError, match="must not outlive"):
        core.SourceConnectivityCensusRow.model_validate(
            base
            | {
                "bounded_follow_up": core.SourceConnectivityFollowUp(
                    action_id="late-action",
                    deadline=date(2026, 9, 2),
                    completion_criterion="Close the evidence gap.",
                ),
            },
        )
    inherited = core.SourceConnectivityCensusRow.model_validate(
        base
        | {
            "bounded_follow_up": core.SourceConnectivityFollowUp(
                action_id="inherited-action",
                deadline=date(2026, 9, 1),
                completion_criterion="Close the evidence gap.",
            ),
        },
    )
    explicit = inherited.model_copy(
        update={
            "bounded_follow_up": core.SourceConnectivityFollowUp(
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
        core.SourceConnectivityCensusRow.model_validate(_connected_payload())


def test_authority_admits_a_complete_supported_connected_claim() -> None:
    row = core.SourceConnectivityCensusRow.validate_with_authority(
        _connected_payload(),
        authority=_ProofAuthority(),
    )
    assert row.disposition is core.SourceConnectivityDisposition.CONNECTED
    assert row.connected_proof is not None
    assert row.connected_proof.connection == _connection()


@pytest.mark.parametrize(
    "mutated_field",
    ["candidate_id", "source_kind", "source_object_id", "resolver_id", "calculation_revision_id"],
)
def test_connected_proof_refuses_every_cross_component_identity_mismatch(mutated_field: str) -> None:
    connection = _connection()
    proof = _connected_proof(connection)
    mutations: dict[str, object] = {
        "candidate_id": "different.candidate",
        "source_kind": core.BindingSourceKind.PROFILE,
        "source_object_id": "different-source",
        "resolver_id": "different-resolver",
        "calculation_revision_id": "d" * 64,
    }
    different = connection.model_copy(update={mutated_field: mutations[mutated_field]})
    with pytest.raises(
        ValidationError,
        match=r"same connection|asserted connection|persisted source identity",
    ):
        core.SourceConnectivityConnectedProof.model_validate(
            {
                "resolver_ownership": proof.resolver_ownership,
                "encrypted_revision": proof.encrypted_revision.model_copy(update={"connection": different}),
                "operator_reachability": proof.operator_reachability,
            },
        )


def test_role_specific_proof_refuses_unrelated_or_wrong_role_evidence() -> None:
    connection = _connection()
    unrelated = _connection(source_object_id="deferred-source")
    evidence = _executable_evidence(
        unrelated,
        evidence_id="wrong-evidence",
        role=core.SourceConnectivityExecutableEvidenceRole.OPERATOR_REACHABILITY,
    )
    with pytest.raises(ValidationError, match="asserted connection"):
        core.SourceConnectivityOperatorReachabilityProof(
            connection=connection,
            entrypoint_id=_ENTRYPOINT_ID,
            command_id=_COMMAND_ID,
            resolver_observed=True,
            evidence=(evidence,),
        )
    wrong_role = evidence.model_copy(update={"connection": connection})
    with pytest.raises(ValidationError, match="must carry role"):
        core.SourceConnectivityEncryptedRevisionProof(
            connection=connection,
            persisted_source_identity=connection.source_object_id,
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
        role=core.SourceConnectivityExecutableEvidenceRole.ENCRYPTED_REVISION,
    )
    with pytest.raises(ValidationError):
        core.SourceConnectivityEncryptedRevisionProof.model_validate(
            {
                "connection": connection,
                "persisted_source_identity": connection.source_object_id,
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
        role=core.SourceConnectivityExecutableEvidenceRole.ENCRYPTED_REVISION,
    )
    with pytest.raises(ValidationError, match="every strict proof assertion"):
        core.SourceConnectivityEncryptedRevisionProof(
            connection=connection,
            persisted_source_identity=connection.source_object_id,
            persisted_source_fingerprint=_FINGERPRINT,
            strict_round_trip=True,
            encrypted_at_rest=False,
            anti_tautology_mutation=True,
            evidence=(evidence,),
        )


def test_encrypted_revision_proof_refuses_source_identity_drift() -> None:
    connection = _connection()
    proof = _connected_proof(connection).encrypted_revision
    with pytest.raises(ValidationError, match="persisted source identity"):
        core.SourceConnectivityEncryptedRevisionProof.model_validate(
            proof.model_dump() | {"persisted_source_identity": "different-source"},
        )


def test_authority_refuses_persisted_source_fingerprint_drift() -> None:
    connection = _connection()
    connected_proof = _connected_proof(connection)
    changed_revision_proof = connected_proof.encrypted_revision.model_copy(
        update={"persisted_source_fingerprint": "sha256:" + "d" * 64},
    )
    changed_proof = connected_proof.model_copy(update={"encrypted_revision": changed_revision_proof})
    with pytest.raises(ValidationError, match="does not match persisted source provenance"):
        core.SourceConnectivityCensusRow.validate_with_authority(
            _connected_payload(connection=connection, proof=changed_proof),
            authority=_ProofAuthority(),
        )


def test_authority_refuses_a_deferred_source_kind() -> None:
    connection = _connection(source_kind=core.BindingSourceKind.RELATED_PARTY_OPERATION)
    with pytest.raises(ValidationError, match="not enrolled"):
        core.SourceConnectivityCensusRow.validate_with_authority(
            _connected_payload(connection=connection),
            authority=_ProofAuthority(),
        )


def test_authority_refuses_an_arbitrary_operator_command_identity() -> None:
    connection = _connection()
    proof = _connected_proof(connection, command_id="anything")
    with pytest.raises(ValidationError, match="workflow is not supported"):
        core.SourceConnectivityCensusRow.validate_with_authority(
            _connected_payload(connection=connection, proof=proof),
            authority=_ProofAuthority(),
        )


def test_authority_refuses_missing_or_changed_executable_evidence() -> None:
    connection = _connection()
    missing_proof = _connected_proof(
        connection,
        operator_reference="src/cadrumo/fake/tests/test_does_not_exist.py:999",
    )
    with pytest.raises(ValidationError, match="absent or changed"):
        core.SourceConnectivityCensusRow.validate_with_authority(
            _connected_payload(connection=connection, proof=missing_proof),
            authority=_ProofAuthority(
                evidence_digests={
                    "resolver-enrollment": _EVIDENCE_DIGEST,
                    "encrypted-revision": _EVIDENCE_DIGEST,
                },
            ),
        )
    with pytest.raises(ValidationError, match="absent or changed"):
        core.SourceConnectivityCensusRow.validate_with_authority(
            _connected_payload(connection=connection),
            authority=_ProofAuthority(
                evidence_digests={
                    "resolver-enrollment": _EVIDENCE_DIGEST,
                    "encrypted-revision": _EVIDENCE_DIGEST,
                    "operator-reachability": "e" * 64,
                },
            ),
        )


def test_connected_proof_rejects_non_test_executable_evidence_shape() -> None:
    connection = _connection()
    with pytest.raises(ValidationError, match="test module"):
        _executable_evidence(
            connection,
            evidence_id="implementation-only",
            role=core.SourceConnectivityExecutableEvidenceRole.RESOLVER_ENROLLMENT,
            reference="src/cadrumo/application/aggregation/_source_mesh.py:1",
        )
