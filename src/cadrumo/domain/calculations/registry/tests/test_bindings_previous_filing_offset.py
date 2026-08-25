"""Previous-filing period-offset error-context regression.

Locks the operator-facing error prefix on the previous-filing offset path so a
future consolidation cannot silently degrade it to the bare arithmetic message.
The period-offset arithmetic itself lives in ``_period_offset_math`` and is
shared with ``_relations``; each consumer re-wraps the raised
:class:`RegistryValidationError` with its own context prefix (``previous-filing``
here, ``relation <id>`` in ``_relations``) so an un-interpretable period code is
traceable to the binding family that raised it.
"""

from __future__ import annotations

import pytest

from ..bindings_previous_filing import _derive_offset_source_anchor
from ..errors import RegistryValidationError

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_offset_resolves_recognised_quarterly_period() -> None:
    """A recognised quarterly target resolves to the prior-quarter anchor."""

    assert _derive_offset_source_anchor(-1, target_period="1T") == (-1, "4T")


def test_uninterpretable_period_raises_with_previous_filing_context() -> None:
    """An un-interpretable target period raises with the previous-filing prefix.

    The shared arithmetic raises a bare ``source_period_offset_from_target``
    message; the previous-filing wrapper must restore the ``previous-filing``
    context so the operator can locate which binding family rejected the code.
    """

    with pytest.raises(RegistryValidationError, match="previous-filing source_period_offset_from_target"):
        _derive_offset_source_anchor(-1, target_period="ANUAL")
