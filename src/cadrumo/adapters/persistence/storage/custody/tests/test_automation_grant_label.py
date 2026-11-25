"""A key named at issue keeps its name through approval, custody and the inventory."""

from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import ValidationError

from cadrumo.adapters.persistence.storage.custody.tests.enrollment_support import NOW, administration_subject, changed
from cadrumo.application.operations.models import OperationIdentity, OperationTerminalReceipt
from cadrumo.application.user_profile.automation_administration import enrollment_review_digest
from cadrumo.application.user_profile.automation_enrollment import AutomationInventoryProjection
from cadrumo.application.user_profile.automation_operations import project_automation_inventory_result
from cadrumo.core.hashing import canonical_json_bytes, sha256_hex
from cadrumo.core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from cadrumo_client.contracts.access_vocabulary import (
    DisclosureCategory,
    DisclosureCategoryGrant,
    GrantUse,
    grant_use,
)
from cadrumo_client.contracts.enrollment_proposal import GRANT_LABEL_MAXIMUM_LENGTH, EnrollmentKind

pytestmark = [pytest.mark.integration, pytest.mark.hex_persistence_adapter]


def test_a_label_set_at_issue_reaches_the_stored_grant_and_the_public_inventory(tmp_path) -> None:
    with administration_subject(tmp_path) as subject:
        request_id = uuid4()
        subject.service.request(request_id, changed(subject.proposal, label="  Claude on the laptop  "))
        subject.approve(request_id)

        stored = subject.store.enrollment_state().grants[0].grant
        inventory = subject.service.inventory()

    assert stored.label == "Claude on the laptop"
    assert [grant.label for grant in inventory.grants] == ["Claude on the laptop"]


def test_a_key_issued_without_a_label_has_none(tmp_path) -> None:
    with administration_subject(tmp_path) as subject:
        request_id = uuid4()
        subject.service.request(request_id, subject.proposal)
        subject.approve(request_id)

        assert subject.store.enrollment_state().grants[0].grant.label is None
        assert subject.service.inventory().grants[0].label is None


@pytest.mark.parametrize(
    "label",
    ["", "   ", "x" * (GRANT_LABEL_MAXIMUM_LENGTH + 1), "two\nlines", "bell\x07", "zero\u200bwidth"],
    ids=["empty", "blank", "too-long", "newline", "control", "format-character"],
)
def test_a_label_that_is_blank_long_or_not_printable_is_refused(tmp_path, label: str) -> None:
    with administration_subject(tmp_path) as subject, pytest.raises(ValidationError):
        changed(subject.proposal, label=label)


def test_only_an_enrollment_can_name_a_key(tmp_path) -> None:
    with administration_subject(tmp_path) as subject, pytest.raises(ValidationError):
        changed(
            subject.proposal, kind=EnrollmentKind.RENEW, label="renamed", target_grant_id=uuid4(), key_expires_at=None
        )


def test_an_unlabelled_request_keeps_the_review_digest_it_had_before_keys_could_be_named(tmp_path) -> None:
    with administration_subject(tmp_path) as subject:
        request_id = uuid4()
        subject.service.request(request_id, subject.proposal)
        record = next(item for item in subject.store.enrollment_state().requests if item.request_id == request_id)

    proposal = record.proposal.model_dump(mode="json")
    del proposal["label"]
    scope = record.proposal.scope.model_dump(mode="json")
    for name in ("operations", "actions", "disclosures", "disclosure_categories", "periods"):
        if scope[name] is not None:
            scope[name] = sorted(scope[name], key=canonical_json_bytes)
    proposal["scope"] = scope
    earlier = sha256_hex(
        canonical_json_bytes(
            {
                "purpose": "cadrumo.automation-consent/v1",
                "request_id": str(record.request_id),
                "binding": record.binding.model_dump(mode="json"),
                "requester": record.requester.model_dump(mode="json"),
                "proposal": proposal,
                "created_at": record.created_at.isoformat(),
                "expires_at": record.expires_at.isoformat(),
                "grant_id": str(record.grant_id),
            }
        )
    )
    assert enrollment_review_digest(record) == earlier
    named = changed(record, proposal=changed(record.proposal, label="Named"))
    assert enrollment_review_digest(named) != earlier


def test_use_is_agent_when_the_scope_releases_results_to_a_destination_and_other_otherwise(
    tmp_path,
) -> None:
    with administration_subject(tmp_path) as subject:
        bare = subject.proposal.scope
        released = changed(
            bare,
            disclosure_categories=frozenset(
                {DisclosureCategoryGrant(destination_id=uuid4(), category=DisclosureCategory.PROFILE_VALUES)}
            ),
        )
        assert not bare.disclosures
        assert not bare.disclosure_categories
        assert grant_use(bare) is GrantUse.OTHER
        assert grant_use(released) is GrantUse.AGENT


def test_the_projected_inventory_reports_each_grants_use(tmp_path) -> None:
    with administration_subject(tmp_path) as subject:
        request_id = uuid4()
        released = changed(
            subject.proposal.scope,
            disclosure_categories=frozenset(
                {
                    DisclosureCategoryGrant(
                        destination_id=subject.owner.requester().destination_id,
                        category=DisclosureCategory.PROFILE_VALUES,
                    )
                }
            ),
        )
        facts = subject.owner.current
        assert facts.session is not None
        subject.owner.current = changed(
            facts, profile=changed(facts.profile, scope=released), session=changed(facts.session, scope=released)
        )
        subject.service.request(request_id, changed(subject.proposal, scope=released, label="Claude on the laptop"))
        subject.approve(request_id)
        inventory = subject.service.inventory()

    receipt = OperationTerminalReceipt(
        identity=OperationIdentity(
            operation_id="a" * 64,
            definition_id="user-profile.automation-inventory",
            subject_ref=profile_operation_subject(str(subject.store.binding.profile_id)),
        ),
        revision=3,
        condition=OperationTerminalCondition.SUCCEEDED,
        effect=OperationEffect.NONE,
        settled_at=NOW,
        result_ref="inventory:synthetic-label",
    )
    projected = project_automation_inventory_result(inventory, receipt)
    assert isinstance(projected, AutomationInventoryProjection)
    assert [(grant.use, grant.label) for grant in projected.grants] == [(GrantUse.AGENT, "Claude on the laptop")]
