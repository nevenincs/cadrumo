"""The invoice classes the TUI offers are the registry's own tokens."""

from __future__ import annotations

import pytest

from .....domain.calculations.registry.authority import bundled_indexed_authority
from .....domain.calculations.registry.invoice_legal_classification import (
    resolve_invoice_legal_classification_catalogue,
)
from ..models import LedgerInvoiceClassChoice

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_every_offered_invoice_class_is_a_declared_registry_token() -> None:
    # The add path matches the stated class exactly against these tokens, so a
    # choice spelled any other way would be refused at entry.
    with bundled_indexed_authority().operation():
        declared = {str(token) for token in resolve_invoice_legal_classification_catalogue().invoice_class_choices}

    assert {choice.value for choice in LedgerInvoiceClassChoice} <= declared
