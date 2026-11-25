"""A client holds no authority: its models stand on their technical bounds, and nothing leases one."""

from __future__ import annotations

import pytest

from .....core.errors.hierarchy import InternalInvariantError
from ....contribuyente.family_types import RentaAscendantProfile
from ..form_codes import exceeds_form_bound, form_codes_in_scope, form_for_role, require_form_fit, require_form_width

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_a_validator_outside_a_scope_has_no_form_fact_to_read() -> None:
    assert form_codes_in_scope() is None
    assert not exceeds_form_bound(10**6, "m100.ascendant_cohabiting_descendants_max")


def test_a_runtime_result_validates_in_a_client_with_no_authority() -> None:
    assert require_form_width("12345", "m210.tipo_renta_digits") == "12345"
    assert require_form_fit("x" * 64, "withholding.subclave_max") == "x" * 64


def test_a_model_with_a_registry_bound_validates_in_a_client_with_no_authority() -> None:
    profile = RentaAscendantProfile.model_validate({"birth_date": "1940-01-01", "cohabiting_descendant_count": 3})
    assert profile.cohabiting_descendant_count == 3


def test_code_that_needs_the_value_refuses_outside_a_scope() -> None:
    with pytest.raises(InternalInvariantError, match="generation-pinned"):
        form_for_role("any-role")
