from __future__ import annotations

from collections.abc import Callable

import pytest

from ....core.errors import ProfileAnswerTypeError
from ..ccaa import CCAA
from ..descendant_facts import parse_descendiente_flag
from ..marriage_facts import parse_marriage_date_flag

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def parse_descendiente_discapacidad_with_wrong_type() -> None:
    parse_descendiente_flag("NACIMIENTO=2010-01-01,DISCAPACIDAD=50")


def parse_marriage_date_with_wrong_type() -> None:
    parse_marriage_date_flag("not-a-date")


def parse_ccaa_label_with_unknown_value() -> None:
    CCAA.from_label("xyzzy")


@pytest.mark.parametrize(
    "call",
    (
        parse_descendiente_discapacidad_with_wrong_type,
        parse_marriage_date_with_wrong_type,
        parse_ccaa_label_with_unknown_value,
    ),
)
def test_profile_answer_type_error_raise_sites(call: Callable[[], object]) -> None:
    with pytest.raises(ProfileAnswerTypeError) as raised:
        call()

    assert raised.type is ProfileAnswerTypeError
