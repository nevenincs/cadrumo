"""The shared minimal-profile filler must stay admissible to the schema.

`register_minimal_profile` fills a profile from a table keyed by path
rather than derived from the field definitions, and that is deliberate:
its values are chosen for MEANING. `common_regime`, `natural_person` and
`actividad_economica` decide which CONDITIONAL requirements apply, so a
profile built from them says something specific, and replacing each with
whatever its field happens to declare first would quietly make those
profiles say something else.

The cost of encoding a choice is that the table restates by path what the
schema declares, and nothing makes the two agree. A field renamed, or a
declared value set narrowed, leaves the table stale — and stale in the
direction that builds a profile the schema refuses, which is exactly the
failure the sentinel used to cause across twenty suites.

So the table keeps its choices and this holds it to the schema. It
asserts admissibility rather than deriving values, which is the whole
distinction: a guard can say "that is not allowed" without claiming to
know what should have been chosen instead.
"""

from __future__ import annotations

import pytest

from ....tests.user_profile import _REQUIRED_PLACEHOLDERS
from ..loader import load_user_profile_schema
from ..schema import ProfileFieldDefinition

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _field_index() -> dict[str, ProfileFieldDefinition]:
    schema = load_user_profile_schema()
    return {f"{section.key}.{field.key}": field for section in schema.sections for field in section.fields}


def test_every_filled_path_is_declared_by_the_schema() -> None:
    """A path the schema no longer declares fills nothing and reads as filled.

    The profile would build, the field would be absent, and the suite
    using it would be asserting against a profile shaped differently from
    the one it thinks it made.
    """
    declared = _field_index()

    undeclared = sorted(path for path in _REQUIRED_PLACEHOLDERS if path not in declared)

    assert undeclared == [], f"the minimal-profile table fills paths the schema does not declare: {undeclared}"


def test_every_filled_value_is_admissible_for_its_field() -> None:
    """The drift that matters: a value the field's own declaration refuses.

    Compared as text because the table holds typed constants - an IVA
    regime member, the manual-CLI provenance token - rather than bare
    strings.
    """
    declared = _field_index()
    assert declared, "the profile field index is empty; no filled value can be judged against nothing"
    assert _REQUIRED_PLACEHOLDERS, "the required-placeholder table is empty; there is nothing to judge"

    refused = [
        f"{path} -> {value!r} not in {list(field.enum_values)}"
        for path, value in _REQUIRED_PLACEHOLDERS.items()
        if (field := declared.get(path)) is not None and field.enum_values and str(value) not in field.enum_values
    ]

    assert refused == [], "the minimal-profile table declares values their fields refuse:\n" + "\n".join(refused)


def test_the_table_constrains_something_so_the_sweep_is_not_vacuous() -> None:
    """Anti-tautology: both checks above pass trivially over an unconstrained table.

    At least one filled path must belong to a field that actually
    declares a value set, or this module proves only that nothing was
    checked.
    """
    declared = _field_index()

    constrained = [
        path for path in _REQUIRED_PLACEHOLDERS if (field := declared.get(path)) is not None and field.enum_values
    ]

    assert constrained, "no filled path belongs to a constrained field; the admissibility sweep would prove nothing"
