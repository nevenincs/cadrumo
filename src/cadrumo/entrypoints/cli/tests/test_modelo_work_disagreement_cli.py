"""Native CLI acceptance for the commands that accept, revoke and list disputed Modelo figures.

Every identifier is synthetic. The commands answer a finding of a persisted
calculation, so a profile with no declaration cannot be answered: the commands
refuse before storing anything, and a blank reason is refused at the boundary.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import date
from pathlib import Path

import pytest
from click.testing import Result

from cadrumo.adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope, newest_authored_edition

from .cli_fixture_worlds import RegisteredCliProfile, cli_world_provider, invoke_joined_cli

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint, pytest.mark.usefixtures("operation")]

_FINDING_ID = "0123456789abcdef"
_REASON = "Synthetic reason: the payer's own copy states this amount."
_PROFILE_FACTS = {
    "taxpayer_type.entity_type": "natural_person",
    "identity.name": "Native",
    "identity.surnames": "Disagreements",
    "identity.tax_id": "12345678Z",
    "activities.description": "synthetic disagreement profile",
    "censo.activity_start_date": date(filing_year_envelope().floor, 1, 1).isoformat(),
    "tax_residence.jurisdiction_scope": "common_regime",
    "iva.regime": "GENERAL",
    "iva.m303_regime_composition": "general",
    "iva.redeme_enrolled": "false",
    "iva.cash_accounting_regime_enrolled": "false",
    "iva.voluntary_sii_enrolled": "false",
    "iva.hydrocarbon_deposit_advance_payment_deduction_entitled": "false",
}


@pytest.fixture
def native_profile(tmp_path: Path) -> Iterator[RegisteredCliProfile]:
    """Register one encrypted profile and supervise its native runtime worker."""
    with cli_world_provider().native_profile(tmp_path) as profile:
        profile.register(label="native-disagreements", facts=_PROFILE_FACTS)
        yield profile


def _invoke(profile: RegisteredCliProfile, *command: str) -> Result:
    if profile.label is None:
        raise AssertionError("native profile must be registered before invocation")
    close_active_bucket_session()
    result = invoke_joined_cli(
        (
            "--language",
            "en",
            "--format",
            "json",
            "--profile",
            profile.label,
            "--profile-secrets-stdin",
            "app",
            "modelo",
            "work",
            *command,
        ),
        input=json.dumps({"profile_passphrase": profile.passphrase}),
    )
    assert profile.passphrase not in result.output
    return result


@pytest.mark.windows_only
def test_native_commands_refuse_where_there_is_no_calculation_to_answer(native_profile: RegisteredCliProfile) -> None:
    address = ("--modelo", "100", "--year", str(newest_authored_edition("100")), "--period", "0A")

    accepted = _invoke(native_profile, "accept-disagreement", _FINDING_ID, *address, "--reason", _REASON)
    revoked = _invoke(native_profile, "revoke-disagreement", _FINDING_ID, *address, "--expected-revision", "e" * 64)
    listed = _invoke(native_profile, "disagreements", *address)

    for result in (accepted, revoked, listed):
        assert result.exit_code != 0, result.output
        assert _REASON not in result.output


@pytest.mark.windows_only
def test_native_accept_needs_a_reason_and_revoke_needs_the_stored_revision(
    native_profile: RegisteredCliProfile,
) -> None:
    blank = _invoke(native_profile, "accept-disagreement", _FINDING_ID, "--reason", "   ")
    unguarded = _invoke(native_profile, "revoke-disagreement", _FINDING_ID)

    assert blank.exit_code != 0 and unguarded.exit_code != 0
    assert "--reason" in blank.output
    assert "--expected-revision" in unguarded.output
