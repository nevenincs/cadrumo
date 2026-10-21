"""The deletion preflight is decided once, and ``config profile delete`` reports that decision."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from pathlib import Path
from uuid import uuid4

import pytest
from click.testing import Result

from cadrumo.adapters.persistence.profile.tests.profile_registration import register_cli_profile
from cadrumo.adapters.persistence.storage.profile_custody import build_profile_custody_port
from cadrumo.adapters.persistence.storage.tests.secure_sql import (
    isolated_cli_backend as _isolated_cli_backend,
)
from cadrumo.application.bucket_maintenance.deletion_preflight import (
    ProfileDeletionPreflight,
    ProfileDeletionRefusal,
    assess_named_profile_deletion,
)
from cadrumo.entrypoints.cli.config.profile_delete_commands import _result_and_lines
from cadrumo.entrypoints.cli.tests.cli_fixture_worlds import CliWorldProvider
from cadrumo.tests.command_line_rendering import (
    as_the_command_line_renders,
    command_error,
    command_result,
)

__all__ = ["_isolated_cli_backend"]

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_FACTS = {
    "taxpayer_type.entity_type": "natural_person",
    "identity.name": "Test",
    "identity.surnames": "Operator",
    "activities.description": "Servicios",
    "iva.regime": "GENERAL",
    "tax_residence.jurisdiction_scope": "common_regime",
    "iva.m303_regime_composition": "general",
    "iva.redeme_enrolled": "false",
    "iva.cash_accounting_regime_enrolled": "false",
    "iva.voluntary_sii_enrolled": "false",
    "iva.hydrocarbon_deposit_advance_payment_deduction_entitled": "false",
}


@pytest.fixture(autouse=True)
def _runtime_delete_owner(_isolated_cli_backend: Path, cli_world_provider: CliWorldProvider) -> Iterator[None]:
    _isolated_cli_backend.mkdir(parents=True, exist_ok=True)
    with cli_world_provider.profile_server(_isolated_cli_backend):
        yield


def _preflight(name: str) -> ProfileDeletionPreflight:
    return assess_named_profile_deletion(name, bucket_storage=build_profile_custody_port().bucket_storage())


def test_the_command_prints_the_observation_and_gives_the_refusals_the_preflight_decides(
    run_cadrumo_cli: Callable[..., Result],
) -> None:
    # Registration selects the profile it creates, so the second one leaves the first deletable.
    register_cli_profile(label="doomed", facts={**_FACTS, "identity.tax_id": "00000001R"}, log_in=False)
    register_cli_profile(label="survivor", facts={**_FACTS, "identity.tax_id": "00000002W"}, log_in=False)

    offered = _preflight("doomed")
    printed = command_result("config", "profile", "delete", "doomed", invoke_cli=run_cadrumo_cli)
    selected = _preflight("survivor")
    selected_result = command_result("config", "profile", "delete", "survivor", invoke_cli=run_cadrumo_cli)
    unknown = _preflight("nobody-by-this-name")
    unknown_error = command_error("config", "profile", "delete", "nobody-by-this-name", invoke_cli=run_cadrumo_cli)

    assert offered.refusal is None
    assert offered.assessment is not None and offered.label == "doomed"
    assert offered.assessment.bucket_id == offered.profile_id
    assert offered.assessment.fingerprint is not None and offered.assessment.fingerprint.file_count >= 1
    result, _lines, _notices = _result_and_lines(offered.assessment, label=offered.label, completed_at=None)
    assert printed == as_the_command_line_renders(result)
    assert printed["deleted"] is False

    assert selected.refusal is None
    assert selected.label == "survivor" and selected.assessment is not None
    assert selected_result["deleted"] is False

    assert unknown.refusal is ProfileDeletionRefusal.UNKNOWN_PROFILE
    assert (unknown.profile_id, unknown.label, unknown.assessment) == (None, None, None)
    assert unknown_error["code"] == "REFUSED_PROFILE_NOT_FOUND"
    assert unknown_error["context"] == {"name": "nobody-by-this-name"}


@pytest.mark.parametrize("changed", ["identity", "content", "missing-digest", "unchanged"])
def test_reviewed_delete_is_bound_to_identity_and_content(run_cadrumo_cli: Callable[..., Result], changed: str) -> None:
    register_cli_profile(label="reviewed", facts={**_FACTS, "identity.tax_id": "00000001R"}, log_in=False)
    observed = _preflight("reviewed")
    assert observed.assessment is not None and observed.assessment.fingerprint is not None
    identity = str(uuid4()) if changed == "identity" else str(observed.profile_id)
    digest = "0" * 64 if changed == "content" else observed.assessment.fingerprint.digest
    args = ["config", "profile", "delete", "reviewed", "--yes", "--expected-profile-id", identity]
    if changed != "missing-digest":
        args += ["--expected-digest", digest]
    if changed == "unchanged":
        result = command_result(*args, invoke_cli=run_cadrumo_cli)
        assert result["deleted"] is True and result["completed_at"]
        assert _preflight("reviewed").refusal is ProfileDeletionRefusal.UNKNOWN_PROFILE
    else:
        refused = command_error(*args, invoke_cli=run_cadrumo_cli)
        assert refused["code"] == "REFUSED_CLI_BOUNDARY"
        assert _preflight("reviewed").profile_id == observed.profile_id
