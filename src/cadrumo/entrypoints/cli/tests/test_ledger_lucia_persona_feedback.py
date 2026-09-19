"""Focused Lucia persona feedback coverage for manual ledger CLI rows."""

from __future__ import annotations

from decimal import Decimal

import pytest

from ....adapters.persistence.storage.tests.seeded_isolated_backend_fixture import seeded_isolated_backend_fixture
from ....tests.cli_envelope import unwrap_cli_result as _json
from .cli_runner import invoke_cached_cli

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _profile_only() -> None:
    """Nothing beyond the registered profile: each case adds its own rows."""
    return None


#: Every case starts from the same registered profile and writes ledger rows
#: into it, so the profile is published once and each test gets its own
#: filesystem copy of that world.
_seeded_origin, _isolated_backend = seeded_isolated_backend_fixture(
    seed=_profile_only,
    display_name="lucia",
    profile_overrides={
        "identity.tax_id": "12345678Z",
        "taxpayer_type.entity_type": "natural_person",
        "identity.name": "Lucia",
        "identity.surnames": "Example",
        "activities.description": "Test",
    },
    settings_overrides={
        "cadrumo_auth_provider": None,
        "cadrumo_certificate_path": None,
        "cadrumo_certificate_password_secret": None,
        "cadrumo_clave_movil_dni_nie": None,
        "cadrumo_clave_movil_dni_fecha": None,
        "cadrumo_clave_movil_nie_soporte": None,
    },
    name="_isolated_backend",
    origin_name="_seeded_origin",
)
__all__ = ["_isolated_backend", "_seeded_origin"]


def _invoke(args: list[str]):
    return invoke_cached_cli(args)


def test_ledger_add_accepts_and_persists_iva_category() -> None:
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

    viewed = _invoke(["--language", "en", "app", "ledger", "view", _json(added)["transaction_id"]])
    assert viewed.exit_code == 0, viewed.output
    assert "Usage ratio id\ttelefonia_movil" in viewed.output
