"""Native CLI attestation stores encrypted M303 evidence without a work unit."""

from __future__ import annotations

import json
import sys
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from cadrumo.adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from cadrumo.adapters.persistence.storage.attachment import AttachmentStore
from cadrumo.adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from cadrumo.application.user_profile.login_session import authenticate_profile_for_invocation
from cadrumo.core.period import Period
from cadrumo.domain.attachments.m303_filing_evidence import (
    M303Exonerado390ApplicabilityAssertion,
    parse_m303_exonerado_390_applicability_attestation,
)
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope
from cadrumo.tests.cli_envelope import unwrap_schema_envelope
from cadrumo_runtime.host.tests.native_commands.runtime_profile_cli_fixture import native_cli_profile_scope

from ...native_profile_facts import native_general_iva_facts
from .cli_runner import invoke_cached_cli

# The attestation is made after the period closes, so it names the last completed exercise.
_ATTESTED_YEAR = filing_year_envelope().horizon - 1

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
                **native_general_iva_facts(),
                "identity.name": "Operator",
                "identity.surnames": "Operator",
                "activities.description": "design",
                "censo.activity_start_date": date(_ATTESTED_YEAR, 1, 1).isoformat(),
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
                    str(_ATTESTED_YEAR),
                    "--period",
                    period,
                    "--observed-at",
                    datetime(_ATTESTED_YEAR, 12, 31, 12, tzinfo=UTC).isoformat(),
                ),
                input=json.dumps({"profile_passphrase": fixture.passphrase}),
            )
            assert fixture.passphrase not in result.output
            return result

        accepted = invoke("4T")
        assert accepted.exit_code == 0, accepted.output
        payload = unwrap_schema_envelope(accepted.output)
        assert payload["filing_year"] == _ATTESTED_YEAR
        assert payload["attachment_id"] == payload["sha256"]
        rejected = invoke("3T")
        assert rejected.exit_code != 0

        close_active_bucket_session()
        authenticate_profile_for_invocation(
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
            assert evidence.period == Period.from_year_and_code(_ATTESTED_YEAR, "4T")
            assert evidence.asserted_value is M303Exonerado390ApplicabilityAssertion.NOT_APPLICABLE
        finally:
            close_active_bucket_session()
