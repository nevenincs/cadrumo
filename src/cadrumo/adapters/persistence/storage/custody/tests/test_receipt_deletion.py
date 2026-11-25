"""What a receipt deletion reports about the on-disk receipt and the keychain key."""

from __future__ import annotations

import pytest

from ..acceleration_receipt import ReceiptDeletion

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]


@pytest.mark.parametrize(
    ("deletion", "receipt_removed", "keychain_removed"),
    [
        (ReceiptDeletion.DELETED, True, True),
        (ReceiptDeletion.NOT_REQUIRED, True, True),
        (ReceiptDeletion.KEYCHAIN_ENTRY_RETAINED, True, False),
        (ReceiptDeletion.RECEIPT_RETAINED, False, False),
    ],
)
def test_each_deletion_state_reports_what_was_removed(
    deletion: ReceiptDeletion, receipt_removed: bool, keychain_removed: bool
) -> None:
    assert deletion.receipt_removed is receipt_removed
    assert deletion.keychain_removed is keychain_removed
