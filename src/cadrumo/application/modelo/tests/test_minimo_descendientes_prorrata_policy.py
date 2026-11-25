"""Pure prorrata status-token policy tests.

The status-token partition is application policy and does not need an encrypted
profile capsule. Keep it with the inward Modelo tests; the sibling integration
coverage remains in the persistence-adapter test owner because it proves the
same values survive the profile write path.
"""

from __future__ import annotations

import pytest

from cadrumo.domain.contribuyente.renta_codes import RentaMaritalStatus

from ..profile_derived_facts import (
    married_status_codes,
    partnered_status_codes,
    unmarried_status_codes,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("authority_operation")]


def test_the_partnered_tokens_carry_no_foreign_vocabulary() -> None:
    """The token sets must hold only values this field can store.

    A word form here is not merely dead: it gives a test a way to match on a
    branch no real filer takes, which is exactly how a dropped code went
    unnoticed. Deriving the sets from the enum makes that unrepresentable, and
    this asserts the derivation rather than the current contents.
    """
    storable = set(RentaMaritalStatus.form_codes().values())
    for name, tokens in (
        ("married", married_status_codes()),
        ("partnered", partnered_status_codes()),
        ("unmarried", unmarried_status_codes()),
    ):
        assert tokens <= storable, f"{name} set carries tokens the schema cannot store: {sorted(tokens - storable)}"
    # Married and unmarried partition the enum: no code is both, none is neither.
    assert storable == married_status_codes() | unmarried_status_codes()
    assert not married_status_codes() & unmarried_status_codes()
