"""The method-asset fixture names a real ledger payment and hands it across the process boundary."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from dev.acceptance.assets.installed_method_fixture import (
    method_correction_json,
    method_revision_json,
    read_acquisition_sidecar,
    write_acquisition_sidecar,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_PAYMENT = "0123456789abcdef" * 4


def test_revision_and_correction_name_the_given_payment() -> None:
    first = json.loads(method_revision_json(acquisition_transaction_id=_PAYMENT))
    corrected = json.loads(method_correction_json(supersedes_revision_id="f" * 64, acquisition_transaction_id=_PAYMENT))

    assert first["acquisition"]["observed_transaction_id"] == _PAYMENT
    assert corrected["acquisition"]["observed_transaction_id"] == _PAYMENT
    assert corrected["basis"]["basis_amount"] == "1800.00"


def test_the_sidecar_round_trips_a_payment_and_refuses_anything_else(tmp_path: Path) -> None:
    write_acquisition_sidecar(tmp_path / "child", _PAYMENT)

    assert read_acquisition_sidecar(tmp_path / "child") == _PAYMENT
    with pytest.raises(ValueError, match="ledger transaction identity"):
        write_acquisition_sidecar(tmp_path / "other", "a" * 63)
