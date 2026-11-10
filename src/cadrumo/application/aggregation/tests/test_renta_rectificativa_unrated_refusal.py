"""A correction with no EUR value cannot be netted, so it refuses instead of reducing by a guess."""

from __future__ import annotations

import pytest

from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.invoices.models import Invoice
from .test_renta_imputation_criterion import BASE as _GROSS
from .test_renta_imputation_criterion import INCOME_0171
from .test_renta_rectificativa_income import (
    _ACCRUAL_YEAR,
    _F1_DATE,
    _R1_DATE,
    _blocked_because,
    _rectificativa,
    _unretained,
    issued,
    resolve,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]


def _unrated(invoice: Invoice) -> Invoice:
    """Return the invoice restated in a foreign currency that carries no rate."""
    return Invoice.model_validate({**invoice.model_dump(exclude={"invoice_id"}), "currency": "USD"})


def test_a_correction_with_no_eur_value_refuses_and_leaves_the_invoice_whole(
    operation: PinnedAuthorityOperation,
) -> None:
    correction = _unrated(_rectificativa(_R1_DATE))
    assert correction.base_total_eur is None
    resolution = resolve(operation, _ACCRUAL_YEAR, invoices=(_unretained(issued(_F1_DATE)), correction))
    assert resolution.binding_values[INCOME_0171] == _GROSS
    assert _blocked_because(resolution, "eur_value_unknown")
