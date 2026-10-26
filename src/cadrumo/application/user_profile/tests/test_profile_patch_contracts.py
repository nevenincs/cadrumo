"""Atomic patch requests preserve explicit answer identity and private input."""

from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import ValidationError

from cadrumo.application.user_profile.profile_operation_contracts import (
    ProfilePatchOperationRequest,
    ProfilePatchValue,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_patch_rejects_duplicate_question_even_when_values_differ() -> None:
    """A repeated question cannot silently overwrite an earlier answer."""
    with pytest.raises(ValidationError, match="must not repeat a question"):
        ProfilePatchOperationRequest(
            profile_id=uuid4(),
            expected_revision=1,
            expected_content_digest="0" * 64,
            values=(
                ProfilePatchValue(question_id="name", value="First private value"),
                ProfilePatchValue(question_id="name", value="Second private value"),
            ),
        )


def test_patch_repr_excludes_private_answers() -> None:
    """Request and answer reprs cannot disclose supplied profile facts."""
    private_value = "private-taxpayer-answer"
    request = ProfilePatchOperationRequest(
        profile_id=uuid4(),
        expected_revision=1,
        expected_content_digest="0" * 64,
        values=(ProfilePatchValue(question_id="name", value=private_value),),
    )
    assert private_value not in repr(request)
    assert private_value not in repr(request.values[0])
