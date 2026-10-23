"""A key the person issues with ``automation create`` releases its categories to the runtime-minted destination."""

from __future__ import annotations

import json
import os
from collections.abc import Iterator
from pathlib import Path
from uuid import uuid4

import pytest

from cadrumo.adapters.persistence.storage.custody.tests.enrollment_support import (
    AdministrationSubject,
    administration_subject,
    changed,
)
from cadrumo.application.user_profile.automation_enrollment import EnrollmentStage
from cadrumo_client.commands.secure_input import select_machine_secret_channel
from cadrumo_client.contracts.access_vocabulary import DisclosureCategory, DisclosureCategoryGrant
from cadrumo_runtime.commands.runtime_automation_request import _create_proposal

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_persistence_adapter,
    pytest.mark.usefixtures("authority_operation"),
]


@pytest.fixture
def subject(tmp_path: Path) -> Iterator[AdministrationSubject]:
    with administration_subject(tmp_path) as result:
        yield result


def _profile_grants_categories(subject: AdministrationSubject, grants: frozenset[DisclosureCategoryGrant]) -> None:
    facts = subject.owner.current
    scope = changed(facts.profile.scope, disclosure_categories=grants)
    subject.owner.current = changed(facts, profile=changed(facts.profile, scope=scope))


def test_created_key_names_the_minted_destination_whatever_the_person_wrote(subject: AdministrationSubject) -> None:
    minted = subject.owner.requesting.destination_id
    written = uuid4()
    categories = frozenset({DisclosureCategory.PROFILE_VALUES, DisclosureCategory.OPERATION_METADATA})
    _profile_grants_categories(
        subject, frozenset(DisclosureCategoryGrant(destination_id=minted, category=item) for item in categories)
    )
    person_scope = changed(
        subject.proposal.scope,
        disclosure_categories=frozenset(
            DisclosureCategoryGrant(destination_id=written, category=item) for item in categories
        ),
    )
    document = {"proposal": changed(subject.proposal, scope=person_scope).model_dump(mode="json")}
    read_end, write_end = os.pipe()
    try:
        os.write(write_end, json.dumps(document).encode("utf-8"))
    finally:
        os.close(write_end)
    selection = select_machine_secret_channel(secrets_stdin=False, secrets_fd=read_end)

    proposal = _create_proposal(selection)(minted)

    request_id = uuid4()
    subject.service.request(request_id, proposal)
    completed = subject.approve(request_id)
    assert completed.stage is EnrollmentStage.COMPLETE
    (grant,) = subject.store.snapshot().grants
    assert grant.scope.disclosure_categories == frozenset(
        DisclosureCategoryGrant(destination_id=minted, category=item) for item in categories
    )
    assert str(written) not in subject.store.enrollment_state().model_dump_json()
