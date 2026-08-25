"""Renta code fields declare the value set the runtime actually writes.

The schema declared ``renta_taxpayer.sex`` and ``renta_spouse.sex`` as
``["1", "2"]`` while every writer and reader used ``H`` / ``M``: the
wizard emitted ``RentaSexCode.HOMBRE.value`` and the setup parser coerced
through ``RentaSexCode(value)``, which would have raised on ``"1"``. A
writer satisfying one authority violated the other, and nothing caught it
because a schema ``enum_values`` list is not enforced at write time.

AEAT settles which was right. Its bundled Modelo 100 registro-design
schema declares ``tipo_Sexo`` with exactly ``H`` and ``M``, so the code
was correct and the declaration was wrong. These tests pin the schema to
the runtime enum in both directions, so the two cannot drift apart again
without a failure that names the field.
"""

from __future__ import annotations

import pytest

from ....core import RentaDeclaracionType
from ....domain import contribuyente
from ....domain.contribuyente import RentaMaritalStatus, RentaSexCode
from ..errors import UserProfileNotFoundError
from ..loader import load_user_profile_schema

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

SEX_PATHS: tuple[str, ...] = ("renta_taxpayer.sex", "renta_spouse.sex")


def test_every_sex_field_declares_the_runtime_code_set() -> None:
    """Both sex fields carry exactly the tokens the code reads and writes.

    Asserting set equality rather than membership is deliberate: a
    superset would let the schema admit a value ``RentaSexCode`` refuses,
    which is the failure that was there before in the other direction.
    """

    schema = load_user_profile_schema()
    expected = {member.value for member in RentaSexCode}

    for path in SEX_PATHS:
        assert set(schema.field(path).enum_values) == expected, (
            f"{path} declares a value set the runtime does not use; "
            f"the AEAT registro design types this field as tipo_Sexo ({sorted(expected)})"
        )


def test_the_sex_code_set_is_the_aeat_declared_pair() -> None:
    """Anti-tautology guard for the test above.

    Comparing the schema against the enum alone would keep passing if
    both drifted together, so the enum itself is pinned to the pair the
    AEAT design documents.
    """

    assert {member.value for member in RentaSexCode} == {"H", "M"}


def test_marital_status_declares_the_runtime_code_set() -> None:
    """The sibling field that was already aligned, held in place.

    ``renta_taxpayer.marital_status`` matched its runtime enum before
    this change, which is what made the sex divergence visible as an
    anomaly rather than a convention. Pinning it keeps that contrast
    meaningful.
    """

    schema = load_user_profile_schema()
    expected = {member.value for member in RentaMaritalStatus}

    assert set(schema.field("renta_taxpayer.marital_status").enum_values) == expected


def test_renta_declaration_type_has_one_core_owner_and_canonical_profile_path() -> None:
    schema = load_user_profile_schema()

    assert {member.value for member in RentaDeclaracionType} == {"1", "2"}
    assert not hasattr(contribuyente, "RentaDeclaracionType")
    assert schema.field("renta_filing.declaration_type").key == "declaration_type"
    with pytest.raises(UserProfileNotFoundError):
        schema.field("filing_export.declaration_type")


def test_rental_reduction_tier_refuses_the_legacy_profile_path() -> None:
    schema = load_user_profile_schema()

    assert schema.field("renta_rental.reduccion_art_23_2_tier_2024").enum_values == (
        "tier-50",
        "tier-60",
        "tier-70",
        "tier-90",
    )
    with pytest.raises(UserProfileNotFoundError):
        schema.field("filing_export.rental_reduccion_art_23_2_tier_2024")
