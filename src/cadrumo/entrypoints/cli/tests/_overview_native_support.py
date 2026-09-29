"""One genuine profile worker and protected CLI invocation for overview behavior tests."""

from __future__ import annotations

import json
from collections.abc import Iterator, Sequence
from pathlib import Path

import pytest
from click.testing import Result

from ....adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from ....core.config import override_settings
from ._runtime_profile_cli_fixture import NativeCliProfileFixture, native_cli_profile_scope
from .cli_runner import invoke_cached_cli


@pytest.fixture
def native_overview_profile(tmp_path: Path) -> Iterator[NativeCliProfileFixture]:
    """Register a readiness-complete synthetic profile before worker login."""
    with native_cli_profile_scope(tmp_path) as fixture:
        fixture.register(
            label="Native overview operator",
            facts={
                "taxpayer_type.entity_type": "natural_person",
                "identity.tax_id": "12345678Z",
                "identity.name": "Native",
                "identity.surnames": "Overview",
                "activities.description": "design",
                "censo.activity_start_date": "2025-01-01",
                "taxpayer_type.irpf_income_categories": "actividad_economica",
                "irpf.estimation_regime": "directa_normal",
                "taxpayer_type.fiscal_residency": "resident_irpf",
                "tax_residence.ccaa": "madrid",
                "tax_residence.jurisdiction_scope": "common_regime",
                "iva.regime": "GENERAL",
                "iva.m303_regime_composition": "general",
                "iva.redeme_enrolled": "false",
                "iva.cash_accounting_regime_enrolled": "false",
                "iva.voluntary_sii_enrolled": "false",
                "iva.hydrocarbon_deposit_advance_payment_deduction_entitled": "false",
            },
        )
        close_active_bucket_session()
        yield fixture


def invoke_native_overview(fixture: NativeCliProfileFixture, args: Sequence[str]) -> Result:
    """Invoke the installed CLI through password admission without exposing secrets."""
    if fixture.label is None:
        raise ValueError("native profile must be registered before CLI invocation")
    close_active_bucket_session()
    with override_settings(cadrumo_cli_reveal_identifiers=False):
        result = invoke_cached_cli(
            ["--profile", fixture.label, "--profile-secrets-stdin", *args],
            input=json.dumps({"profile_passphrase": fixture.passphrase}),
        )
    assert fixture.passphrase not in result.output
    return result


__all__ = ["invoke_native_overview", "native_overview_profile"]
