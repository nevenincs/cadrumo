"""Fixtures shared by the session authority tests."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from cadrumo.adapters.persistence.storage.custody.tests.enrollment_support import (
    administration_subject,
    changed,
)

from ._session_authority_support import Recovery, Subject


@pytest.fixture
def subject(tmp_path: Path) -> Iterator[Subject]:
    with administration_subject(tmp_path) as enrollment:
        # Consent explicitly includes delegation; no test-only bypass of scope policy.
        scope = changed(enrollment.proposal.scope, allow_delegation=True)
        enrollment.proposal = changed(enrollment.proposal, scope=scope)
        facts = enrollment.owner.current
        assert facts.session is not None
        enrollment.owner.current = changed(
            facts, profile=changed(facts.profile, scope=scope), session=changed(facts.session, scope=scope)
        )
        yield Subject(enrollment)


@pytest.fixture
def recovery(subject: Subject) -> Recovery:
    return Recovery(subject)
