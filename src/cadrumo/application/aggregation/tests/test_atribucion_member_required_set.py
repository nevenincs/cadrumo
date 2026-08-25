"""Real-behavior tests: the M184 member reader demands exactly what it consumes.

A resolver enforces what its row model consumes; the profile schema declares
what the profile must hold. Those are legitimately different sets, and this
module asserts the resolver's half of that rule rather than the agreement of
the two. Asserting agreement is what these tests deliberately do *not* do:
making the reader follow the schema would let a field the schema requires for
some other consumer refuse a socio row for Modelo 184, which carries no such
field.

The distinction is not academic, because both directions have a cost and they
are not symmetric.

Demanding a field nothing reads shipped once. Every socio row was made to
answer for a legal member role, which Modelo 184 records at entity level and
not per member: no row model here carries it, and nothing in this tree reads
it. The row was refused for a missing answer no form asks for.

Demanding one field *fewer* than the builders consume is the louder failure. A
row would clear the completeness check and then raise ``KeyError`` midway
through being built, turning a diagnosed and skipped row into a crash.

So the property is bidirectional and neither direction pins a field list.
Both are measured by dropping one field from a complete row and observing what
the real builders do with what is left.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal

import pytest

from ....domain.user_profile.loader import load_user_profile_schema
from .._atribucion_member import (
    _REQUIRED_FIELDS,
    _detail_row_from_socio,
    _missing_field_diagnostic,
    _missing_fields,
    _observation_from_socio,
    _SocioFacts,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_SECTION = "attribution_entity_socios"
_FILING_YEAR = 2024

# Fixture data, not a restatement of the required set: the properties below
# derive their field sets from the resolver and the schema, and read this only
# for a value to put in each slot. Coverage of it is asserted rather than
# assumed, so a newly declared field cannot slip past the properties unnoticed.
_SAMPLE_ROW: Mapping[str, object] = {
    "nif": "22222222B",
    "name": "Member Two",
    "share_pct": Decimal("40"),
    "base_imponible_assigned": Decimal("4000"),
    # Clave 2 is the one clave whose Modelo 184 record carries a country, so it
    # is the only combination that exercises both fields at once. A resident
    # sample would leave the country slot legitimately empty and the row would
    # stop covering it.
    "participe_clave": "2",
    "country_of_residence": "US",
    "role": "comunero",
}


def _declared_fields() -> frozenset[str]:
    schema = load_user_profile_schema()
    section = next(candidate for candidate in schema.sections if candidate.key == _SECTION)
    return frozenset(field.key for field in section.fields)


def _socio_without(field: str) -> _SocioFacts:
    return _SocioFacts(index=0, values={key: value for key, value in _SAMPLE_ROW.items() if key != field})


def _builders_refusing(socio: _SocioFacts) -> set[str]:
    """Names of the row builders that cannot build this row.

    Both builders are exercised because they read the profile row
    independently, so a field can be consumed by one and not the other.
    """
    refusing: set[str] = set()
    for name, build in (
        ("observation", lambda: _observation_from_socio(socio, filing_year=_FILING_YEAR)),
        ("detail_row", lambda: _detail_row_from_socio(socio)),
    ):
        try:
            build()
        except KeyError:
            refusing.add(name)
    return refusing


def test_the_sample_row_covers_every_declared_field() -> None:
    """Anti-rot: a newly declared field must reach the properties below.

    Both properties iterate over field sets taken from the resolver and the
    schema, but draw their values from the sample row. A field declared in the
    schema and missing here would be dropped from a row that never carried it,
    so its property would pass without exercising anything.
    """

    assert set(_SAMPLE_ROW) == _declared_fields(), (
        "the sample row and the schema section have diverged; add the new field to "
        "_SAMPLE_ROW so the required-set properties exercise it"
    )


def test_every_required_field_is_one_the_row_builders_consume() -> None:
    """Nothing is demanded that nothing reads.

    Dropping a required field must stop a builder. A field whose absence
    leaves both builders working is being demanded and not used, which is the
    shape of the member-role defect: the row is refused for an answer no form
    asks for and no code reads.
    """

    for field in sorted(_REQUIRED_FIELDS):
        socio = _socio_without(field)
        assert _builders_refusing(socio), (
            f"{field!r} is required by the reader but both row builders build without it. "
            "A resolver enforces what its row model consumes; drop it from the required "
            "set, or route it into the row that needs it."
        )


def test_no_field_the_builders_consume_is_left_optional() -> None:
    """The inverse: a row that passes the completeness check must actually build.

    A consumed field outside the required set would let a row clear
    ``_missing_fields`` and then raise ``KeyError`` while being built - a crash
    where the design calls for a diagnostic and a skipped row.
    """

    for field in sorted(_declared_fields() - _REQUIRED_FIELDS):
        socio = _socio_without(field)
        assert not _missing_fields(socio), f"{field!r} is outside the required set but was reported missing"
        assert not _builders_refusing(socio), (
            f"{field!r} is consumed by a row builder but is not in the required set, so a row "
            "missing it passes the completeness check and then raises KeyError. Add it to the "
            "required set, or give the builder a default."
        )


def test_a_required_field_is_reported_missing_and_named_to_the_operator() -> None:
    """The completeness check binds, and its diagnostic says which field is absent.

    Asserted here because the readiness gate refuses an incomplete profile
    earlier, which shadows this path in the end-to-end tests and would let it
    rot unnoticed.
    """

    for field in sorted(_REQUIRED_FIELDS):
        socio = _socio_without(field)
        assert _missing_fields(socio) == frozenset({field})
        assert field in _missing_field_diagnostic(socio).message
