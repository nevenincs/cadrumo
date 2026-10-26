"""Read-only installed CLI continuation over persisted canonical IVA fields."""

from __future__ import annotations

import json
from pathlib import Path

from cadrumo.core.hashing import sha256_hex
from dev.acceptance.installed_cli import InstalledCli

from .iva_tui_contracts import IvaInstalledTuiError
from .iva_tui_projection import _canonical_ledger_decimal_text, _object
from .iva_tui_scenario import _SyntheticIvaRow


def _observe_public_canonical_transaction(
    cli: InstalledCli, transaction_id: str, expected_fields: dict[str, str]
) -> tuple[str, str, str, str, str, str]:
    """Read one persisted transaction and require every submitted canonical field."""
    document = cli.run(("app", "ledger", "view", transaction_id))
    result = _object(document.get("result"), label="installed public ledger view result")
    transaction = _object(result.get("transaction"), label="installed public ledger transaction")
    if result.get("transaction_id") != transaction_id:
        raise IvaInstalledTuiError("installed public ledger view returned a different transaction identity")
    for field_name, expected_value in expected_fields.items():
        if transaction.get(field_name) != expected_value:
            raise IvaInstalledTuiError(
                f"installed public Ledger view did not preserve submitted canonical field {field_name!r}"
            )
    return (
        transaction_id,
        expected_fields["business_classification"],
        expected_fields["taxable_base"],
        expected_fields["iva_rate"],
        expected_fields["iva_amount"],
        expected_fields["iva_category"],
    )


def _readback_canonical_fields(
    *,
    executable: Path,
    storage_root: Path,
    authority_root: Path,
    passphrase: str,
    transaction_ids: tuple[str, str],
    synthetic_rows: tuple[_SyntheticIvaRow, ...],
) -> tuple[str, tuple[str, ...]]:
    """Read public persisted fields in fresh installed CLI processes, without writes.

    This is intentionally a ``tui_to_cli`` continuation.  It is not claimed as
    part of the TUI-only capture/reopen path.
    """
    from dev.acceptance.installed_cli import InstalledCli, InstalledCliError

    expected = tuple(
        (
            transaction_id,
            {
                "business_classification": "BUSINESS",
                "taxable_base": _canonical_ledger_decimal_text(scenario_row.taxable_base),
                "iva_rate": "0.21",
                "iva_amount": _canonical_ledger_decimal_text(scenario_row.iva_amount),
                "iva_category": "domestic_general",
            },
        )
        for transaction_id, scenario_row in zip(transaction_ids, synthetic_rows, strict=True)
    )
    cli = InstalledCli(
        executable,
        storage_root=storage_root,
        authority_root=authority_root,
        passphrase=passphrase,
    )
    observed: list[tuple[str, str, str, str, str, str]] = []
    try:
        for transaction_id, expected_fields in expected:
            observed.append(_observe_public_canonical_transaction(cli, transaction_id, expected_fields))
    except InstalledCliError as exc:
        raise IvaInstalledTuiError("installed read-only CLI continuation refused Ledger readback") from exc
    if len(cli.commands) != 2 or any(command.returncode != 0 for command in cli.commands):
        raise IvaInstalledTuiError(
            "installed read-only CLI continuation did not produce two successful fresh-process reads"
        )
    fingerprint = sha256_hex(json.dumps(observed, separators=(",", ":"), ensure_ascii=True).encode("utf-8"))
    return fingerprint, tuple("app.ledger.view" for _ in cli.commands)
