"""canonical_decimal_string financial alias invariant.

Asserts:
1. The old duplicate name ``canonical_decimal`` in
   ``cadrumo.adapters.inbound.financial._decimal`` no longer exists as a
   module (the file is deleted); any surviving ``canonical_decimal`` name
   in the financial package re-exports from ``cadrumo.domain._identifiers``.
"""

import pytest

from ._inventory import SRC_CADRUMO

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_financial_decimal_module_is_deleted() -> None:
    """cadrumo.adapters.inbound.financial._decimal must not exist as a file."""
    decimal_module_path = SRC_CADRUMO / "adapters" / "inbound" / "financial" / "_decimal.py"
    assert not decimal_module_path.exists(), (
        f"Duplicate _decimal.py still present at {decimal_module_path}; "
        "delete the file and migrate callers to cadrumo.domain._identifiers."
    )


def test_financial_package_canonical_decimal_delegates_to_domain() -> None:
    """The name canonical_decimal re-exported by the financial package must
    be the same object as canonical_decimal_string from cadrumo.domain._identifiers.
    """
    from ..adapters.inbound.financial import canonical_decimal
    from ..domain import canonical_decimal_string

    assert canonical_decimal is canonical_decimal_string, (
        "cadrumo.adapters.inbound.financial.canonical_decimal must be the same "
        "object as cadrumo.domain._identifiers.canonical_decimal_string; "
        "check the __init__.py import alias."
    )
