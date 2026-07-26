"""The shared test filler must never build a profile the schema refuses.

Twenty test modules fill the fields they are not testing with a
placeholder, and for a long time one sentinel served every field because
the schema's declared value sets constrained nothing. They constrain now.
A sentinel in an enum field asserts a profile that cannot exist, and the
modules using it then fail for a reason unrelated to what they test —
which is what happened, in twenty places at once.

The filler was extracted so that property could be tested rather than
merely repeated. An expression copied into twenty files cannot be
guarded; one named function can, and this is the guard. It sweeps the
whole schema rather than the fields that happen to be required today,
because the twenty-first copy will be written against whatever the schema
declares then.
"""

from __future__ import annotations

import pytest

from ....tests.user_profile import schema_valid_placeholder
from .. import load_user_profile_schema

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_the_filler_is_admissible_for_every_field_the_schema_declares() -> None:
    """Not just the required ones, and not just the enums.

    A field that gains a declared value set later is exactly the case
    this exists to catch, so the sweep is over everything rather than
    over the subset that constrains anything today.
    """
    schema = load_user_profile_schema()

    refused = [
        f"{section.key}.{field.key} -> {schema_valid_placeholder(field)!r} not in {list(field.enum_values)}"
        for section in schema.sections
        for field in section.fields
        if field.enum_values and schema_valid_placeholder(field) not in field.enum_values
    ]

    assert refused == [], "the shared filler emitted a value its own field does not declare:\n" + "\n".join(refused)


def test_an_enum_field_gets_a_declared_value_rather_than_the_sentinel() -> None:
    """The anti-tautology check: the sweep above passes trivially if nothing constrains.

    The schema declares at least one enum field, so the filler has to be
    doing real work for that field rather than returning the sentinel and
    being admitted by a vacuous check.
    """
    schema = load_user_profile_schema()
    enum_fields = [field for section in schema.sections for field in section.fields if field.enum_values]

    assert enum_fields, "the sweep proves nothing unless the schema constrains at least one field"
    assert all(schema_valid_placeholder(field) != "placeholder" for field in enum_fields), (
        "an enum field must get one of its declared values, not the sentinel"
    )


def test_a_field_with_no_declared_set_gets_the_sentinel() -> None:
    """The other half: an unconstrained field needs no special value.

    Deriving from the definition means an unconstrained field is left
    alone rather than given something clever, so the filler stays legible
    where it does not need to be careful.
    """
    schema = load_user_profile_schema()
    plain = [field for section in schema.sections for field in section.fields if not field.enum_values]

    assert plain, "the schema is expected to declare unconstrained fields too"
    assert all(schema_valid_placeholder(field) == "placeholder" for field in plain)
