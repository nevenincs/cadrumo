"""Exact profile and registry-pin binding of ledger action ports."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast

import pytest

from ...user_profile.access_contracts import AccessDenialCode
from ...user_profile.access_errors import ProfileAccessRefusedError
from ..action_ports import LedgerActionPorts, require_exact_ledger_action_ports

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET = "9f0c2a3e-8a52-4c1d-9a51-6d1e2f3a4b5c"
_OTHER_BUCKET = "1b2c3d4e-5f60-4a71-8b92-a3b4c5d6e7f8"


def _ports(
    *,
    operation: object,
    transaction_bucket: str = _BUCKET,
    invoice: object | None = None,
    work_unit: object | None = None,
    calculation: object | None = None,
) -> LedgerActionPorts:
    return LedgerActionPorts(
        operation=cast(Any, operation),
        transaction_repository=cast(Any, SimpleNamespace(bucket_id=transaction_bucket)),
        bucket_event_repository=cast(Any, object()),
        invoice_repository=cast(Any, invoice or SimpleNamespace(bucket_id=_BUCKET)),
        attachment_store=cast(Any, object()),
        usage_ratio_profile=cast(Any, object()),
        usage_ratio_profile_loader=cast(Any, object()),
        work_unit_repository=cast(Any, work_unit or SimpleNamespace(bucket_id=_BUCKET)),
        calculation_repository=cast(Any, calculation or SimpleNamespace(bucket_id=_BUCKET)),
        purchase_invoice_evidence_records=(),
    )


def test_exact_ports_for_the_requested_bucket_and_pin_are_accepted() -> None:
    operation = object()

    require_exact_ledger_action_ports(_ports(operation=operation), bucket_id=_BUCKET, operation=cast(Any, operation))


def test_an_equal_but_different_registry_pin_is_refused() -> None:
    ports = _ports(operation=object())

    with pytest.raises(ProfileAccessRefusedError) as refused:
        require_exact_ledger_action_ports(ports, bucket_id=_BUCKET, operation=cast(Any, object()))

    assert refused.value.reason is AccessDenialCode.PROFILE_MISMATCH


@pytest.mark.parametrize(
    "escaped",
    [
        {"transaction_bucket": _OTHER_BUCKET},
        {"invoice": SimpleNamespace(bucket_id=_OTHER_BUCKET)},
        {"work_unit": SimpleNamespace(bucket_id=_OTHER_BUCKET)},
        {"calculation": SimpleNamespace(bucket_id=_OTHER_BUCKET)},
        {"calculation": SimpleNamespace()},
    ],
    ids=["transactions", "invoices", "work-units", "calculations", "calculations-unbound"],
)
def test_any_repository_outside_the_requested_bucket_is_refused(escaped: dict[str, Any]) -> None:
    operation = object()
    ports = _ports(operation=operation, **escaped)

    with pytest.raises(ProfileAccessRefusedError) as refused:
        require_exact_ledger_action_ports(ports, bucket_id=_BUCKET, operation=cast(Any, operation))

    assert refused.value.reason is AccessDenialCode.PROFILE_MISMATCH
