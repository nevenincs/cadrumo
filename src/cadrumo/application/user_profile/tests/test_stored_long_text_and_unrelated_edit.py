"""A stored text past a record's capacity refuses the write that touches it, and only that write."""

from __future__ import annotations

import tomllib

import pytest

from ....core.resources.bundled_data import bundled_path
from ....core.text_bounds import FILING_TEXT_CAPACITY
from ....domain.calculations.registry.tests.published_authority import published_profile_schema
from ....domain.user_profile.errors import ProfileSchemaValidationError
from ....domain.user_profile.values import UserProfileFact
from ..validation import reject_invalid_profile_facts

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_BUCKET = "51300000-0000-4000-8000-000000000514"
_FACTS = (
    UserProfileFact(path="identity.name", value="N" * (FILING_TEXT_CAPACITY + 1)),
    UserProfileFact(path="identity.surnames", value="Gil"),
)


def _check(changed_paths: frozenset[str] | None) -> None:
    reject_invalid_profile_facts(
        _BUCKET,
        _FACTS,
        require_complete=False,
        schema=published_profile_schema(),
        changed_paths=changed_paths,
    )


def test_editing_another_field_is_not_refused_for_a_stored_long_name() -> None:
    _check(frozenset({"identity.phone"}))


@pytest.mark.parametrize("touched", ["identity.name", "identity.surnames"])
def test_writing_either_part_of_the_name_is_refused(touched: str) -> None:
    with pytest.raises(ProfileSchemaValidationError) as refused:
        _check(frozenset({touched}))

    assert refused.value.translated_message == "application.user_profile.errors.profile_text_too_long"


def test_a_check_of_the_whole_record_still_refuses() -> None:
    with pytest.raises(ProfileSchemaValidationError):
        _check(None)


def test_the_capacity_lives_in_code_and_the_schema_only_says_which_fields_it_binds() -> None:
    schema_path = bundled_path("registry", "cadrumo", "user_profile", "schema.toml")
    authored = tomllib.loads(schema_path.read_text(encoding="utf-8"))

    def declared(node: object) -> bool:
        if isinstance(node, dict):
            return "max_length" in node or any(declared(child) for child in node.values())
        return isinstance(node, list) and any(declared(child) for child in node)

    assert not declared(authored)
    [identity] = [section for section in published_profile_schema().sections if section.key == "identity"]
    [name] = [field for field in identity.fields if field.key == "name"]
    assert name.max_length == FILING_TEXT_CAPACITY
