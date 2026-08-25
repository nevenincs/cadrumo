"""A socio's country is owed under one clave and prohibited under the other two.

Modelo 184's declarado record fills positions 79-80 with the member's country
of residence ONLY for clave 2 -- no residente sin establecimiento permanente.
For clave 1 (residente) and clave 3 (no residente con establecimiento
permanente) the layout requires BLANCOS there.

So the country is not a field that happens to be optional. It is a field the
record layout FORBIDS on two of its three claves, and the profile could not
represent it at all until the clave was captured beside it. That absence is why
the M184 member row had to stay country-optional while its siblings were made
required: the producer had no territory to supply, and demanding one would have
refused every profile-resolved row while naming a fact no surface recorded.

Both directions are enforced at the write door. A rule that only asks for the
value when it is due leaves the prohibited case to whatever the operator typed,
which is exactly what a Spanish default did -- writing a value the layout
forbids, on the majority case, where it was least likely to be noticed.
"""

from __future__ import annotations

import pytest

from cadrumo.application.user_profile.validation import (
    CONDITIONAL_REQUIRED_FIELD_MISSING_CODE,
    CONDITIONALLY_FORBIDDEN_FIELD_CODE,
    ProfileValidationService,
)

from ....domain.user_profile import UserProfileFact, load_user_profile_schema

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE_ID = "00000000-0000-4000-8000-000000000000"
_CLAVE_PATH = "attribution_entity_socios.0.participe_clave"
_COUNTRY_PATH = "attribution_entity_socios.0.country_of_residence"

_RESIDENTE = "1"
_NO_RESIDENTE_SIN_EP = "2"
_NO_RESIDENTE_CON_EP = "3"


def _codes_at_socio_paths(*, clave: str | None, country: str | None) -> set[str]:
    """Return the issue codes raised against this socio's own two paths.

    Scoped to the two paths under test because the row's siblings -- nif, name,
    share and base -- are required and absent here, and their issues would
    otherwise drown the one being asserted.
    """
    facts = []
    if clave is not None:
        facts.append(UserProfileFact(path=_CLAVE_PATH, value=clave))
    if country is not None:
        facts.append(UserProfileFact(path=_COUNTRY_PATH, value=country))
    service = ProfileValidationService(schema=load_user_profile_schema())
    report = service.validate_facts(_PROFILE_ID, tuple(facts))
    return {issue.code for issue in report.issues if issue.path in {_CLAVE_PATH, _COUNTRY_PATH}}


@pytest.mark.parametrize("clave", (_RESIDENTE, _NO_RESIDENTE_CON_EP))
def test_a_country_stated_under_a_blancos_clave_is_refused(clave: str) -> None:
    """The direction a conditional rule usually omits, and the one that cost money.

    Both of these claves require BLANCOS at positions 79-80, so a country here
    is not an extra fact -- it is a value the record layout prohibits.
    """
    codes = _codes_at_socio_paths(clave=clave, country="US")

    assert CONDITIONALLY_FORBIDDEN_FIELD_CODE in codes, (
        f"clave {clave} requires BLANCOS at positions 79-80, yet a stated country was accepted"
    )


def test_a_country_is_required_under_the_clave_that_carries_one() -> None:
    """The other half: clave 2 is the one clave whose record states a country."""
    codes = _codes_at_socio_paths(clave=_NO_RESIDENTE_SIN_EP, country=None)

    assert CONDITIONAL_REQUIRED_FIELD_MISSING_CODE in codes


def test_the_clave_that_carries_a_country_accepts_one() -> None:
    """The positive control.

    Without it the refusals above cannot be told apart from a rule that refuses
    every country, or from one that refuses nothing and is reporting some other
    field. This is the only combination the layout actually fills.
    """
    codes = _codes_at_socio_paths(clave=_NO_RESIDENTE_SIN_EP, country="US")

    assert CONDITIONALLY_FORBIDDEN_FIELD_CODE not in codes
    assert CONDITIONAL_REQUIRED_FIELD_MISSING_CODE not in codes


@pytest.mark.parametrize("clave", (_RESIDENTE, _NO_RESIDENTE_CON_EP))
def test_a_blancos_clave_with_no_country_is_clean(clave: str) -> None:
    """The majority case must not be made harder to state.

    A resident socio states a clave and no country, which is exactly what the
    layout asks for. If this raised, the fix would have replaced a silent wrong
    value with a refusal on the population that was never wrong.
    """
    codes = _codes_at_socio_paths(clave=clave, country=None)

    assert CONDITIONALLY_FORBIDDEN_FIELD_CODE not in codes
    assert CONDITIONAL_REQUIRED_FIELD_MISSING_CODE not in codes


def test_a_row_with_no_clave_is_not_told_about_its_country() -> None:
    """One unfinished row must not be reported twice, naming the wrong field second.

    The clave is required in its own right and its absence is reported as such.
    Refusing the country as well would send the operator to clear a field whose
    correctness is not yet decidable -- it depends on the clave they have not
    supplied.
    """
    codes = _codes_at_socio_paths(clave=None, country="US")

    assert CONDITIONALLY_FORBIDDEN_FIELD_CODE not in codes
    assert CONDITIONAL_REQUIRED_FIELD_MISSING_CODE not in codes


def test_the_two_codes_are_distinct_so_the_operator_is_sent_the_right_way() -> None:
    """A prohibited value reported as a missing one inverts the instruction.

    Told a field is missing, an operator supplies more of exactly what the form
    does not allow. The codes are asserted different here because the whole
    value of the second code is that it does not read as the first.
    """
    assert CONDITIONALLY_FORBIDDEN_FIELD_CODE != CONDITIONAL_REQUIRED_FIELD_MISSING_CODE

    forbidden = _codes_at_socio_paths(clave=_RESIDENTE, country="US")
    missing = _codes_at_socio_paths(clave=_NO_RESIDENTE_SIN_EP, country=None)

    assert CONDITIONAL_REQUIRED_FIELD_MISSING_CODE not in forbidden
    assert CONDITIONALLY_FORBIDDEN_FIELD_CODE not in missing
