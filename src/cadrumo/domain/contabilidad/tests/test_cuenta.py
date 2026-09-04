"""PGC account-code shape and hierarchy."""

from __future__ import annotations

import pytest

from ...errors import DomainValidationError
from ..cuenta import CuentaPgc

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@pytest.mark.parametrize("code", ["280", "2801", "11450", "600", "7634"])
def test_observed_manual_shapes_are_accepted(code: str) -> None:
    """Every shape the Equivalencias tables actually use must construct."""
    assert str(CuentaPgc(code)) == code


@pytest.mark.parametrize(
    "code",
    ["", "6", "60", "0600", "600000", "60a", "6 00", "-600", "6.00"],
)
def test_non_account_shapes_are_refused(code: str) -> None:
    with pytest.raises(DomainValidationError):
        CuentaPgc(code)


def test_grupo_and_subgrupo_are_the_numbering_prefixes() -> None:
    cuenta = CuentaPgc("6001")

    assert cuenta.grupo == "6"
    assert cuenta.subgrupo == "60"


def test_is_within_walks_the_numbering_hierarchy() -> None:
    cuenta = CuentaPgc("6001")

    assert cuenta.is_within("6")
    assert cuenta.is_within("60")
    assert cuenta.is_within("600")
    assert cuenta.is_within("6001")
    assert not cuenta.is_within("7")
    assert not cuenta.is_within("601")


def test_is_within_refuses_a_non_numeric_prefix() -> None:
    with pytest.raises(DomainValidationError):
        CuentaPgc("6001").is_within("6a")


def test_subgroup_tokens_are_recognised_but_are_not_accounts() -> None:
    """The Manual writes some equivalencias against a two-digit subgrupo."""
    assert CuentaPgc.is_subgroup_token("60")
    assert not CuentaPgc.is_subgroup_token("600")
    with pytest.raises(DomainValidationError):
        CuentaPgc("60")


def test_a_code_behaves_as_its_own_text() -> None:
    assert CuentaPgc("600") == "600"
    assert sorted({CuentaPgc("601"), CuentaPgc("600")}) == ["600", "601"]
