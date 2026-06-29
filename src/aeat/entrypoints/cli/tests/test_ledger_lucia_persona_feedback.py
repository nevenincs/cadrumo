"""Focused Lucia persona feedback coverage for manual ledger CLI rows."""

from __future__ import annotations

import json
from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from ....core.config import override_settings
from ....tests.cli_runner import invoke_cached_cli
from ....tests.secure_sql import isolated_profile_storage_root

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


@pytest.fixture(autouse=True)
def _isolated_backend(tmp_path: Path) -> Iterator[None]:
    with (
        isolated_profile_storage_root(tmp_path=tmp_path),
        override_settings(
            aeat_auth_provider=None,
            aeat_certificate_path=None,
            aeat_certificate_password_secret=None,
            aeat_clave_movil_dni_nie=None,
            aeat_clave_movil_dni_fecha=None,
            aeat_clave_movil_nie_soporte=None,
        ),
    ):
        yield


def _invoke(args: list[str]):
    return invoke_cached_cli(args)


def _json(result) -> dict[str, Any]:
    payload = json.loads(result.output)
    if isinstance(payload, dict) and "result" in payload and "schema_version" in payload:
        inner = payload["result"]
        assert isinstance(inner, dict), result.output
        return inner
    assert isinstance(payload, dict), result.output
    return payload


def _create_active_profile() -> None:
    result = _invoke(
        [
            "config",
            "profile",
            "create",
            "lucia",
            "--quiet",
            "--tax-id",
            "12345678Z",
            "--entity-type",
            "natural_person",
            "--name",
            "Lucia",
            "--surnames",
            "Example",
            "--activity",
            "Test",
        ],
    )
    assert result.exit_code == 0, result.output


def test_ledger_add_accepts_and_persists_iva_category() -> None:
    _create_active_profile()

    added = _invoke(
        [
            "--format",
            "json",
            "app",
            "ledger",
            "add",
            "--date",
            "2025-01-01",
            "--amount",
            "121",
            "--direction",
            "OUTGOING",
            "--description",
            "test",
            "--classification",
            "BUSINESS",
            "--category-id",
            "material_oficina",
            "--taxable-base",
            "100",
            "--iva-rate",
            "0.21",
            "--iva-amount",
            "21",
            "--iva-category",
            "domestic_general_21",
        ],
    )

    assert added.exit_code == 0, added.output
    added_payload = _json(added)
    transaction = added_payload["transaction"]
    assert transaction["iva_category"] == "domestic_general_21"

    viewed = _invoke(["--format", "json", "app", "ledger", "view", added_payload["transaction_id"]])
    assert viewed.exit_code == 0, viewed.output
    viewed_transaction = _json(viewed)["transaction"]
    assert viewed_transaction["iva_category"] == "domestic_general_21"


def test_ledger_add_accepts_and_persists_counterparty_eu_member_state() -> None:
    _create_active_profile()

    added = _invoke(
        [
            "--format",
            "json",
            "app",
            "ledger",
            "add",
            "--date",
            "2025-01-01",
            "--amount",
            "1000",
            "--direction",
            "INCOMING",
            "--description",
            "intra-community supply",
            "--classification",
            "BUSINESS",
            "--taxable-base",
            "1000",
            "--iva-rate",
            "0",
            "--iva-amount",
            "0",
            "--iva-category",
            "intra_community_supply",
            "--counterparty-eu-member-state",
            "de",
            "--source-jurisdiction",
            "DE",
        ],
    )

    assert added.exit_code == 0, added.output
    transaction = _json(added)["transaction"]
    assert transaction["iva_category"] == "intra_community_supply"
    assert transaction["counterparty_eu_member_state"] == "de"
    assert transaction["source_jurisdiction"] == "DE"


def test_ledger_view_text_shows_usage_ratio_id_when_present() -> None:
    _create_active_profile()

    ratios_set = _invoke(["app", "ledger", "ratios", "set", "telefonia_movil", "0.60"])
    assert ratios_set.exit_code == 0, ratios_set.output

    added = _invoke(
        [
            "--format",
            "json",
            "app",
            "ledger",
            "add",
            "--date",
            "2025-01-01",
            "--amount",
            "60.50",
            "--direction",
            "OUTGOING",
            "--description",
            "phone bill",
            "--classification",
            "MIXED",
            "--business-pct",
            "0.60",
            "--category-id",
            "telefonia_movil",
            "--usage-ratio-id",
            "telefonia_movil",
            "--taxable-base",
            "50.00",
            "--iva-rate",
            "0.21",
            "--iva-amount",
            "10.50",
        ],
    )
    assert added.exit_code == 0, added.output
    transaction = _json(added)["transaction"]
    assert Decimal(transaction["business_pct"]) == Decimal("0.60")
    assert transaction["usage_ratio_id"] == "telefonia_movil"

    viewed = _invoke(["app", "ledger", "view", _json(added)["transaction_id"]])
    assert viewed.exit_code == 0, viewed.output
    assert "Usage ratio id\ttelefonia_movil" in viewed.output
