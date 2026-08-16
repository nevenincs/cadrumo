"""Focused Lucia persona feedback coverage for manual ledger CLI rows."""

from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path

import pytest

from ....core.config import override_settings
from ....tests.cli_envelope import unwrap_cli_result as _json
from ....tests.cli_runner import invoke_cached_cli
from ....tests.secure_sql import isolated_profile_storage_root
from ....tests.user_profile import register_cli_profile

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


@pytest.fixture(autouse=True)
def _isolated_backend(tmp_path: Path) -> Iterator[None]:
    with (
        isolated_profile_storage_root(tmp_path=tmp_path),
        override_settings(
            cadrumo_auth_provider=None,
            cadrumo_certificate_path=None,
            cadrumo_certificate_password_secret=None,
            cadrumo_clave_movil_dni_nie=None,
            cadrumo_clave_movil_dni_fecha=None,
            cadrumo_clave_movil_nie_soporte=None,
        ),
    ):
        yield


def _invoke(args: list[str]):
    return invoke_cached_cli(args)


def _create_active_profile() -> None:
    """Register the profile through the shared CLI registration door."""
    register_cli_profile(
        label="lucia",
        facts={
            "identity.tax_id": "12345678Z",
            "taxpayer_type.entity_type": "natural_person",
            "identity.name": "Lucia",
            "identity.surnames": "Example",
            "activities.description": "Test",
        },
    )


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
            "domestic_general",
        ],
    )

    assert added.exit_code == 0, added.output
    added_payload = _json(added)
    transaction = added_payload["transaction"]
    assert transaction["iva_category"] == "domestic_general"

    viewed = _invoke(["--format", "json", "app", "ledger", "view", added_payload["transaction_id"]])
    assert viewed.exit_code == 0, viewed.output
    viewed_transaction = _json(viewed)["transaction"]
    assert viewed_transaction["iva_category"] == "domestic_general"


def test_ledger_add_accepts_and_persists_counterparty_country() -> None:
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
            "--counterparty-country",
            "DE",
            "--source-jurisdiction",
            "DE",
        ],
    )

    assert added.exit_code == 0, added.output
    transaction = _json(added)["transaction"]
    assert transaction["iva_category"] == "intra_community_supply"
    assert transaction["counterparty_country"] == "DE"
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
