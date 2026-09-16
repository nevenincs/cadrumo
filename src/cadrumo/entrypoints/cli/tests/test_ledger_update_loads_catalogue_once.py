"""One ``aeat app ledger update`` decrypts the transaction catalogue once.

The verb resolves an id prefix and then replaces the row. Both read the same
snapshot, so the command must not decrypt the whole bucket for each step. The
count is taken on the real encrypted repository behind the real CLI.
"""

from __future__ import annotations

from collections.abc import Sequence

import pytest
from click.testing import Result

from ....adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ....domain.transactions.models import TransactionCatalogue
from ....tests.cli_envelope import unwrap_cli_result
from ._ledger_seeded_profile_fixture import _isolated_backend
from .cli_runner import invoke_cached_cli

__all__ = ["_isolated_backend"]

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _invoke(args: Sequence[str]) -> Result:
    return invoke_cached_cli(args)


def _add_row() -> str:
    result = _invoke(
        [
            "--format",
            "json",
            "app",
            "ledger",
            "add",
            "--date",
            "2026-05-02",
            "--amount",
            "42.00",
            "--direction",
            "OUTGOING",
            "--description",
            "material oficina",
            "--counterparty",
            "Proveedor SL",
            "--idempotency-key",
            "update-loads-once",
        ],
    )
    assert result.exit_code == 0, result.output
    transaction_id = unwrap_cli_result(result)["transaction"]["transaction_id"]
    assert isinstance(transaction_id, str)
    return transaction_id


@pytest.fixture
def catalogue_loads(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Record every whole-catalogue decrypt while still performing it."""
    loads: list[str] = []
    real_load = TransactionCatalogueRepository.load

    def counting_load(self: TransactionCatalogueRepository) -> TransactionCatalogue:
        loads.append(self.bucket_id)
        return real_load(self)

    monkeypatch.setattr(TransactionCatalogueRepository, "load", counting_load)
    return loads


@pytest.mark.usefixtures("_isolated_backend")
def test_a_ledger_update_invocation_loads_the_catalogue_once(catalogue_loads: list[str]) -> None:
    transaction_id = _add_row()
    catalogue_loads.clear()

    result = _invoke(["app", "ledger", "update", transaction_id[:12], "--group", "Cierre 2025"])

    assert result.exit_code == 0, result.output
    assert len(catalogue_loads) == 1, catalogue_loads
