"""Default elision is schema-driven and preserves every non-default declaration."""

from typing import Literal

import pytest
from pydantic import BaseModel, Field

from dev.registry.default_elision import complete_value, elide_text

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


class Row(BaseModel):
    id: str
    kind: Literal["row"] = "row"
    required: bool = False
    count: int = 0
    locale_key: str = Field(default="label", exclude=True)


def test_defaults_removed_without_changing_comments_or_discriminator() -> None:
    text = '# explanation\nid = "A"\nkind = "row"\nrequired = false\ncount = 3\n'
    after, removed = elide_text(text, {})
    assert (after, removed) == (text, 0)
    wrapped = "[row]\n" + text
    after, removed = elide_text(wrapped, {"row": Row(id="A", count=3)})
    assert removed == 1
    assert after == wrapped.replace("required = false\n", "")


def test_comment_on_elided_field_keeps_its_context() -> None:
    text = '[row]\nid = "A"\nrequired = false # explicit explanation\n'
    after, removed = elide_text(text, {"row": Row(id="A")})
    assert removed == 1
    assert "# Implicit schema default: required = false # explicit explanation" in after


def test_inline_or_ambiguous_omissions_are_not_guessed() -> None:
    text = 'row = {id = "A", required = false}\n'
    assert elide_text(text, {"row": Row(id="A")}) == (text, 0)


def test_dump_excluded_fields_are_included_in_complete_proof() -> None:
    left = Row(id="A", locale_key="one")
    right = Row(id="A", locale_key="two")
    assert left.model_dump() == right.model_dump()
    assert complete_value(left) != complete_value(right)


def test_required_true_is_not_omitted() -> None:
    text = '[row]\nid = "A"\nrequired = true\n'
    assert elide_text(text, {"row": Row(id="A", required=True)}) == (text, 0)
