"""Recording a foreign-currency invoice without a euro rate says so at capture.

Such an invoice is kept and held back from every euro figure until a rate is
stamped on it. The first sign used to be a refusal at calculation, far from the
capture that could have been corrected; the add verb now warns when it records
one. The rate provider is the production ECB provider over an in-memory
transport that publishes no series, which is how the ECB answers a currency it
has no rate for.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ....adapters.outbound.fx.ecb_provider import EcbReferenceRateProvider
from ....adapters.persistence.storage.tests.active_profile_isolated_backend_fixture import (
    active_profile_isolated_backend_fixture,
)
from ....application.exchange_rate_provider import bind_exchange_rate_provider_factory
from ....tests.cli_envelope import require_schema_envelope, unwrap_envelope_notices
from ....tests.ecb_stub import ecb_csv_fetch
from .cli_runner import invoke_cached_cli

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _invoice_directory_settings(tmp_path: Path) -> dict[str, Path]:
    invoice_directory = tmp_path / "invoices"
    invoice_directory.mkdir()
    return {"cadrumo_invoices_dir": invoice_directory}


_isolated_backend = active_profile_isolated_backend_fixture(
    bucket_id="00000000-0000-4000-8000-000000000000",
    settings_overrides=_invoice_directory_settings,
)


def _add(number: str, currency: str) -> list[str]:
    with bind_exchange_rate_provider_factory(lambda: EcbReferenceRateProvider(fetch=ecb_csv_fetch({}))):
        added = invoke_cached_cli(
            [
                "--format",
                "json",
                "app",
                "ledger",
                "invoice",
                "add",
                "--kind",
                "received",
                "--counterparty-nif",
                "A58818501",
                "--counterparty-name",
                "Proveedor Exterior SL",
                "--invoice-number",
                number,
                "--invoice-date",
                "2026-03-16",
                "--country-code",
                "ES",
                "--taxable-base",
                "100.00",
                "--iva-rate",
                "21",
                "--currency",
                currency,
            ],
        )
    assert added.exit_code == 0, added.output
    assert require_schema_envelope(added.output)["invoice_id"]
    return [str(notice["code"]) for notice in unwrap_envelope_notices(added.output)]


def test_a_foreign_invoice_recorded_without_a_rate_warns_at_capture() -> None:
    assert "ledger.invoice.euro_rate_unavailable" in _add("FX-NO-RATE-001", "USD")


def test_a_euro_invoice_carries_no_rate_warning() -> None:
    assert "ledger.invoice.euro_rate_unavailable" not in _add("FX-EURO-001", "EUR")
