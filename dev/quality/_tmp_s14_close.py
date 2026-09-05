from __future__ import annotations

import json
from datetime import datetime

from dev.quality import clitui_ledger_capability_matrix as matrix_module
from dev.quality.clitui_ledger_capability_matrix import (
    EvidenceCoordinateV1,
    EvidenceKind,
    EvidenceRole,
    EvidenceSubjectSnapshotV1,
    LedgerAcceptanceRecordAnchorV1,
    LedgerCapabilityMatrixV1,
    LedgerGate,
    LedgerGateClosureReceiptV1,
    LedgerMatrixAcceptanceAttestationV1,
    ReviewRuling,
    build_ledger_capability_matrix,
    evaluate_ledger_capability_gate,
    ledger_gate_closure_receipt_id,
)


RULING_DATE = datetime.fromisoformat("2026-09-05T00:00:00+02:00")
G0 = LedgerGate.G0_DENOMINATOR_AND_OWNERSHIP_FREEZE


candidate = build_ledger_capability_matrix()
receipt_identity = ((ledger_gate_closure_receipt_id(G0), G0),)
attestation = LedgerMatrixAcceptanceAttestationV1(
    attestation_id="attestation.ledger.g0",
    reviewer="primary-independent-review",
    ruling=ReviewRuling.ACCEPT,
    plan_owner=candidate.controls.sole_ledger_parity_plan_owner,
    matrix_digest=candidate.attestation_matrix_basis_digest,
    denominator_digest=candidate.current_denominator.digest,
    denominator_revision=candidate.current_denominator.revision,
    union_review=candidate.current_union_review,
    review_subject_id=candidate.current_subjects[0].subject_id,
    review_subject_revision=candidate.current_subjects[0].revision,
    review_subject_digest=candidate.current_subjects[0].digest,
    review_subject_observed_at=candidate.current_subjects[0].observed_at,
    attested_at=RULING_DATE,
    closure_receipt_set_digest=LedgerCapabilityMatrixV1.calculate_gate_closure_receipt_set_digest(receipt_identity),
)
attested = candidate.model_copy(update={"acceptance_attestation": attestation})
receipt = LedgerGateClosureReceiptV1(
    receipt_id=ledger_gate_closure_receipt_id(G0),
    gate=G0,
    matrix_closure_basis_digest=attested.gate_closure_basis_digest(G0),
    acceptance_attestation_digest=attestation.calculated_digest,
)
accepted_unbound = attested.model_copy(update={"accepted_gate_closure_receipts": (receipt,)})
accepted = LedgerCapabilityMatrixV1.model_validate(
    accepted_unbound.model_copy(update={"matrix_digest": accepted_unbound.calculated_matrix_digest}).model_dump(
        mode="python"
    )
)

subject_id = "subject.ledger.acceptance_record.g0"
subject_revision = "g0-acceptance-2026-09-05"
locator = "reference://clitui-ledger/g0-acceptance-record"
provisional_subject = EvidenceSubjectSnapshotV1(
    subject_id=subject_id,
    locator=locator,
    revision=subject_revision,
    digest="sha256:" + "0" * 64,
    observed_at=RULING_DATE,
)


def coordinate(subject: EvidenceSubjectSnapshotV1) -> EvidenceCoordinateV1:
    return EvidenceCoordinateV1(
        evidence_id="evidence.acceptance_record.g0_independent_review",
        kind=EvidenceKind.REVIEW,
        role=EvidenceRole.INDEPENDENT_ENGINEERING_REVIEW,
        axes=frozenset(matrix_module.LedgerCapabilityAxis),
        subject_id=subject.subject_id,
        subject_revision=subject.revision,
        subject_digest=subject.digest,
        observed_at=subject.observed_at,
        locator=subject.locator,
        claim="The external acceptance record freezes the independently accepted G0 authority.",
    )


anchor_fields = {
    "acceptance_attestation_digest": attestation.calculated_digest,
    "attestation_id": attestation.attestation_id,
    "reviewer": attestation.reviewer,
    "attested_at": attestation.attested_at,
    "matrix_basis_digest": attestation.matrix_digest,
    "denominator_digest": attestation.denominator_digest,
    "denominator_revision": attestation.denominator_revision,
    "union_review": attestation.union_review,
    "review_subject_id": attestation.review_subject_id,
    "review_subject_revision": attestation.review_subject_revision,
    "review_subject_digest": attestation.review_subject_digest,
    "review_subject_observed_at": attestation.review_subject_observed_at,
}
draft = LedgerAcceptanceRecordAnchorV1.model_construct(coordinate=coordinate(provisional_subject), **anchor_fields)
acceptance_subject = provisional_subject.model_copy(update={"digest": draft.calculated_subject_digest})
anchor = LedgerAcceptanceRecordAnchorV1(coordinate=coordinate(acceptance_subject), **anchor_fields)

report = matrix_module._matrix_live_report(accepted.live_union)
exact = evaluate_ledger_capability_gate(
    accepted,
    G0,
    observed_census=report,
    observed_subjects=accepted.current_subjects,
    observed_union=accepted.live_union,
    acceptance_record_anchor=anchor,
    observed_acceptance_subjects=(acceptance_subject,),
)
missing = evaluate_ledger_capability_gate(
    accepted,
    G0,
    observed_census=report,
    observed_subjects=accepted.current_subjects,
    observed_union=accepted.live_union,
)
stale_subject = acceptance_subject.model_copy(update={"revision": "stale"})
stale = evaluate_ledger_capability_gate(
    accepted,
    G0,
    observed_census=report,
    observed_subjects=accepted.current_subjects,
    observed_union=accepted.live_union,
    acceptance_record_anchor=anchor,
    observed_acceptance_subjects=(stale_subject,),
)

second_receipt_payload = {
    "schema_version": 1,
    "receipt_id": "receipt.ledger.independent_review.second",
    "reviewer": "second-independent-review",
    "ruling": "accept",
    "ruling_date": "2026-09-05",
    "candidate_commit": "f9580577ffcb1d730c6459c73ff209e3ea3412bc",
    "candidate_tree": "4db16a09813d8f41702b8779881f3996e9f8de39",
    "source_digest": "sha256:18e201e66d73b883ad015aff966a8255febeffbac7b04e923d278d2b02adce58",
    "union_digest": "sha256:8a158b5cc4c8e6c3035dc272999af61ac6cb080af8c208eccc8d28e4105a7575",
    "union_review_basis_digest": "sha256:f1fb6a15d1d93188ae50abc0ff76f6846723e71450f01173d76ea03be946212a",
    "row_review_digest": "sha256:4e42e5e04ccfd7a8654e629933698e141033b0767d0f94ec5433619400203ff8",
    "row_attestation_digest": "sha256:fc15a433ad145832934cbe894d3d0b875d27e9a54ed1a70ae271c16ff81aedf7",
    "denominator_revision": "row-review-v1",
    "denominator_digest": "sha256:48c2c800faa2c9932811678fc16c8caff2cae89bcdaf81512e7ae7aa29d5d140",
    "candidate_matrix_digest": "sha256:c4a210bbd5410a3b6f7630262277b0cfc780d278815cc7a58da66dccd265c30a",
    "pre_receipt_basis_digest": "sha256:a8cd7cb17aea3d508459423c708b596d8931c76660fee6abf987c2c6fe21d7bd",
    "pending_attestation_digest": "sha256:01eee26b8be50f485801e15271361cc1bcd76de562cc8aa4c2e7066f6fc75d7",
    "observations": {"raw": 760, "selections": 769, "identities": 693},
    "verification": {"matrix_tests_passed": 297, "static_checks": "pass", "vault_checks": "pass"},
    "blockers": [],
}
second_receipt_digest = matrix_module._canonical_digest(second_receipt_payload)

output = {
    "candidate_matrix_digest": candidate.matrix_digest,
    "pre_receipt_basis_digest": candidate.attestation_matrix_basis_digest,
    "acceptance_attestation": attestation.model_dump(mode="json"),
    "acceptance_attestation_digest": attestation.calculated_digest,
    "g0_receipt": receipt.model_dump(mode="json"),
    "accepted_matrix_digest": accepted.matrix_digest,
    "external_subject": acceptance_subject.model_dump(mode="json"),
    "external_anchor": anchor.model_dump(mode="json"),
    "external_anchor_subject_digest": anchor.calculated_subject_digest,
    "second_review_receipt_payload": second_receipt_payload,
    "second_review_receipt_digest": second_receipt_digest,
    "g0_exact": exact.model_dump(mode="json"),
    "g0_missing_anchor": missing.model_dump(mode="json"),
    "g0_stale_anchor_subject": stale.model_dump(mode="json"),
}
print(json.dumps(output, indent=2, sort_keys=True))
