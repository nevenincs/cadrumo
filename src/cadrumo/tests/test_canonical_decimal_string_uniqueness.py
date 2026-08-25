"""canonical_decimal_string financial alias invariant.

Asserts:
1. The old duplicate name ``canonical_decimal`` in
   ``cadrumo.adapters.inbound.financial._decimal`` no longer exists as a
   module and package facade is deleted.
"""

import pytest

from ._inventory import SRC_CADRUMO

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_financial_decimal_module_is_deleted() -> None:
    """cadrumo.adapters.inbound.financial._decimal must not exist as a file."""
    decimal_module_path = SRC_CADRUMO / "adapters" / "inbound" / "financial" / "_decimal.py"
    assert not decimal_module_path.exists(), (
        f"Duplicate _decimal.py still present at {decimal_module_path}; "
        "delete the file and migrate callers to cadrumo.domain.identifiers."
    )


def test_financial_package_does_not_alias_canonical_decimal() -> None:
    """The financial package must not redeclare the domain-owned helper."""
    from ..adapters.inbound import financial

    assert "canonical_decimal" not in vars(financial)
