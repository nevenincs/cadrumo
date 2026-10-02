"""Native CLI attestation stores encrypted M303 evidence without a work unit."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....adapters.persistence.storage.attachment import AttachmentStore
from ....adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from ....application.user_profile.login_session import login_profile
from ....core.period import Period
from ....domain.attachments.m303_filing_evidence import (
    M303Exonerado390ApplicabilityAssertion,
    parse_m303_exonerado_390_applicability_attestation,
)
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....tests.cli_envelope import unwrap_schema_envelope
from .cli_runner import invoke_cached_cli
from .runtime_profile_cli_fixture import native_cli_profile_scope

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers"),
    pytest.mark.usefixtures("authority_operation"),
]


def test_cli_attests_period_before_any_work_unit_and_refuses_other_periods(
    tmp_path: Path, authority_operation: PinnedAuthorityOperation
) -> None:
    with native_cli_profile_scope(tmp_path) as fixture:
        fixture.register(
            label="operator",
            facts={
                "taxpayer_type.entity_type": "natural_person",
                "identity.name": "Operator",
                "identity.surnames": "Operator",
                "activities.description": "design",
                "censo.activity_start_date": "2025-01-01",
                "tax_residence.jurisdiction_scope": "common_regime",
                "iva.regime": "GENERAL",
                "iva.m303_regime_composition": "general",
                "iva.redeme_enrolled": "false",
                "iva.cash_accounting_regime_enrolled": "false",
                "iva.voluntary_sii_enrolled": "false",
                "iva.hydrocarbon_deposit_advance_payment_deduction_entitled": "false",
            },
        )
        assert fixture.label is not None
        label = fixture.label
        close_active_bucket_session()

        def invoke(period: str):
            result = invoke_cached_cli(
                (
                    "--format",
                    "json",
                    "--profile",
                    label,
                    "--profile-secrets-stdin",
                    "app",
                    "modelo",
                    "work",
                    "attest-m303-exonerado-390",
                    "--year",
                    "2025",
                    "--period",
                    period,
                    "--observed-at",
                    "2025-12-31T12:00:00+00:00",
                ),
                input=json.dumps({"profile_passphrase": fixture.passphrase}),
            )
            assert fixture.passphrase not in result.output
            return result

        accepted = invoke("4T")
        assert accepted.exit_code == 0, accepted.output
        payload = unwrap_schema_envelope(accepted.output)
        assert payload["filing_year"] == 2025
        assert payload["attachment_id"] == payload["sha256"]
        rejected = invoke("3T")
        assert rejected.exit_code != 0

        close_active_bucket_session()
        login_profile(
            name=label,
            passphrase_callback=lambda: fixture.passphrase,
            profile_decode_context=authority_operation.profile_decode_context(),
        )
        try:
            assert not WorkUnitCatalogueRepository().load().work_units
            store = AttachmentStore()
            manifests = tuple(store.iter_manifests())
            assert len(manifests) == 1
            evidence = parse_m303_exonerado_390_applicability_attestation(store.read_bytes(payload["attachment_id"]))
            assert evidence.period == Period.from_year_and_code(2025, "4T")
            assert evidence.asserted_value is M303Exonerado390ApplicabilityAssertion.NOT_APPLICABLE
        finally:
            close_active_bucket_session()
