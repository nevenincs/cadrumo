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

from datetime import date

import pytest

from ....tests.user_profile import schema_valid_placeholder
from ..loader import load_user_profile_schema
from ..schema import NUMERIC_PROFILE_FIELD_TYPES, ProfileFieldType
from ..values import UserProfileFact

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


def test_a_date_field_gets_a_real_calendar_date_rather_than_the_sentinel() -> None:
    """A date field constrains its value as narrowly as an enum field does.

    The write door enforces :attr:`ProfileFieldType.DATE`: a date-typed
    fact must carry a real ISO-8601 calendar day in the zero-padded
    ``YYYY-MM-DD`` layout, and refuses anything else with an
    ``invalid_date_value`` ERROR. The sentinel is not one, so a filler
    returning it for a date field promises a value the field's own
    declaration admits and hands back one the door rejects.

    Asserted by parsing rather than by matching the constant, so the
    filler stays free to choose a different day without this test having
    an opinion about which.
    """
    schema = load_user_profile_schema()
    date_fields = [
        field for section in schema.sections for field in section.fields if field.type is ProfileFieldType.DATE
    ]

    assert date_fields, "the schema declares no date field; this test would prove nothing"

    refused = []
    for field in date_fields:
        value = schema_valid_placeholder(field)
        try:
            date.fromisoformat(value)
        except ValueError:
            refused.append(f"{field.key} -> {value!r}")

    assert refused == [], "the shared filler emitted a value the date write-door refuses:\n" + "\n".join(refused)


def test_a_boolean_field_gets_a_value_that_survives_as_a_boolean() -> None:
    """The write door admits the sentinel here, which is exactly the risk.

    BOOLEAN is the one declared type the door does not check, so a sentinel
    in a boolean field is accepted and then read as ``False`` by every
    consumer that asks whether the flag is set. Nothing refuses it and
    nothing reports it -- the wrong answer simply arrives quietly, which is
    worse than the loud refusal a date field would have produced.

    Asserted through the fact carrier rather than by matching a token,
    because the property that matters is that the value survives as a
    ``bool``. The carrier promotes ``"true"`` / ``"false"`` back to a real
    boolean on re-parse and leaves anything else a ``str``, so this is the
    check the sentinel actually fails.
    """
    schema = load_user_profile_schema()
    boolean_fields = [
        (section, field)
        for section in schema.sections
        for field in section.fields
        if field.type is ProfileFieldType.BOOLEAN
    ]

    assert boolean_fields, "the schema declares no boolean field; this test would prove nothing"

    not_boolean = []
    for section, field in boolean_fields:
        fact = UserProfileFact(path=f"{section.key}.{field.key}", value=schema_valid_placeholder(field))
        restored = UserProfileFact.model_validate_json(fact.model_dump_json())
        if not isinstance(restored.value, bool):
            not_boolean.append(f"{section.key}.{field.key} -> {restored.value!r} ({type(restored.value).__name__})")

    assert not_boolean == [], (
        "the shared filler emitted a value that does not survive as a boolean, so a consumer "
        "asking whether the flag is set reads it as False with nothing raised:\n" + "\n".join(not_boolean)
    )


def test_a_field_with_no_declared_set_gets_the_sentinel() -> None:
    """The other half: a genuinely unconstrained field needs no special value.

    Deriving from the definition means an unconstrained field is left
    alone rather than given something clever, so the filler stays legible
    where it does not need to be careful.

    The exclusions below are the field classes whose declarations DO
    constrain, each of which the filler answers with a real value: enum
    fields (their declared set), numeric fields (their declared bounds),
    date fields (a calendar day), boolean fields (a boolean token), and
    ``tax_id`` -- whose schema type is a plain string, but whose downstream
    ``SubjectTaxId`` projection enforces the AEAT checksum the schema does
    not express.

    Adding a branch to the filler means adding its class here. That is
    deliberate rather than a maintenance wart: a new branch is a change to
    what "unconstrained" means, and it should have to be stated in the one
    place that asserts the sentinel still reaches anything at all. This
    test was left stale once already, by the numeric branch, and passed
    the staleness on as a failure that looked like the filler's fault.
    """
    schema = load_user_profile_schema()
    plain = [
        field
        for section in schema.sections
        for field in section.fields
        if not field.enum_values
        and field.key != "tax_id"
        and field.type not in NUMERIC_PROFILE_FIELD_TYPES
        and field.type is not ProfileFieldType.DATE
        and field.type is not ProfileFieldType.BOOLEAN
    ]

    assert plain, "no unconstrained field remains; the sentinel reaches nothing and this proves nothing"
    assert all(schema_valid_placeholder(field) == "placeholder" for field in plain)
