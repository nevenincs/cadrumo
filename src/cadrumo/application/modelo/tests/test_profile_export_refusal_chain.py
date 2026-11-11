"""A refused stored profile text never travels with its exception chain."""

from __future__ import annotations

import traceback
from collections.abc import Callable
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from ....core.text_bounds import FILING_TEXT_CAPACITY
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ....domain.calculations.registry.tests.published_authority import leased_profile_create_context
from ....domain.user_profile.errors import ProfileSchemaValidationError
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, create_user_profile_record
from ...filing.producer_snapshot import DeclarationContactFacts, TaxpayerIdentityFacts
from ..profile_export_binding import identity_from_profile_facts, resolve_declaration_contact

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET = "20000000-0000-4000-8000-000000000611"
_CLOCK = datetime(filing_year_envelope().horizon, 7, 9, tzinfo=UTC)
_STORED = "Privada" + "Q" * FILING_TEXT_CAPACITY
_PERSON = {"identity.tax_id": "12345678Z", "taxpayer_type.entity_type": "natural_person"}


def _assert_chain_carries_no_stored_value(refused: ProfileSchemaValidationError) -> None:
    assert refused.__cause__ is None
    assert refused.__context__ is None
    rendered = "".join(traceback.format_exception(refused))
    assert refused.translated_message == "application.user_profile.errors.profile_text_too_long"
    assert _STORED not in rendered
    assert "QQQQ" not in rendered
    assert refused.context is not None
    assert refused.context["limit"] == FILING_TEXT_CAPACITY
    assert "QQQQ" not in str(refused.context)


def test_the_identity_refusal_chain_holds_no_stored_name(operation: PinnedAuthorityOperation) -> None:
    with pytest.raises(ProfileSchemaValidationError) as refused:
        identity_from_profile_facts(
            {**_PERSON, "identity.name": _STORED, "identity.surnames": "Gil"}, schema=operation.profile_schema()
        )

    _assert_chain_carries_no_stored_value(refused.value)


def test_the_contact_refusal_chain_holds_no_stored_name(operation: PinnedAuthorityOperation) -> None:
    record = create_user_profile_record(
        setup_state=ProfileSetupState.COMPLETE,
        profile_id=_BUCKET,
        facts=(
            UserProfileFact(path="contact.contact_person_phone", value="900000000"),
            UserProfileFact(path="contact.contact_person_name", value=_STORED),
        ),
        created_at=_CLOCK,
        updated_at=_CLOCK,
        context=leased_profile_create_context(),
    )

    with pytest.raises(ProfileSchemaValidationError) as refused:
        resolve_declaration_contact(bucket_id=_BUCKET, operation=operation, profile_record=record)

    _assert_chain_carries_no_stored_value(refused.value)


@pytest.mark.parametrize(
    "build",
    [
        lambda: TaxpayerIdentityFacts(legal_name=None, given_name=_STORED, surnames=None, full_name=None),
        lambda: DeclarationContactFacts(full_name=_STORED),
    ],
    ids=["identity", "contact"],
)
def test_a_rejected_producer_fact_is_not_echoed_by_its_validation_error(build: Callable[[], object]) -> None:
    with pytest.raises(ValidationError) as rejected:
        build()

    assert "string_too_long" in {error["type"] for error in rejected.value.errors()}
    assert "QQQQ" not in str(rejected.value)
    assert "QQQQ" not in "".join(traceback.format_exception(rejected.value))
