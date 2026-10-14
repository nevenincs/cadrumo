"""Cross-product proof that tax authentication administration belongs to its runtime owner."""

from __future__ import annotations

from collections.abc import Callable

import pytest
from click.testing import Result

from cadrumo.entrypoints.cli import command_specs as _command_specs

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def test_tax_graph_keeps_direct_auth_entrypoints_and_drops_moved_auth_verbs() -> None:
    keys = set(_command_specs.COMMAND_GRAPH.by_key())
    assert {"config_login", "config_logout", "config_profile_create", "config_profile_list"} <= keys
    assert not keys.intersection(
        {
            "config_auth",
            "config_auth_providers",
            "config_auth_diagnostics",
            "config_auth_diagnostics_list",
            "config_auth_diagnostics_report",
            "config_auth_apoderado",
            "config_auth_apoderado_status",
            "config_auth_apoderado_configure",
            "config_auth_apoderado_clear",
            "config_auth_apoderado_check",
            "config_auth_apoderado_scopes",
            "config_auth_apoderado_scopes_list",
            "config_auth_certificate",
            "config_auth_certificate_register",
            "config_auth_certificate_list",
            "config_auth_certificate_select",
            "config_auth_certificate_remove",
            "config_auth_certificate_check",
            "config_auth_certificate_secret",
            "config_auth_certificate_secret_set",
            "config_auth_certificate_secret_remove",
            "config_auth_configure",
            "config_auth_status",
            "config_auth_test",
            "config_auth_login",
            "config_auth_logout",
            "config_auth_reset",
            "config_auth_diagnostics_view",
            "config_google_login",
            "config_google_status",
            "config_google_logout",
            "config_sign_in_status",
            "config_passphrase",
            "config_passphrase_change",
            "config_passphrase_reset",
            "config_profile_recovery",
            "config_profile_recovery_enable",
            "config_profile_recovery_disable",
            "config_profile_recovery_status",
            "config_profile_disclosures",
            "config_profile_sessions",
            "config_profile_lock",
            "config_profile_resume",
            "config_profile_automation",
            "config_profile_automation_list",
            "config_profile_automation_create",
            "config_profile_automation_change",
            "config_profile_automation_disclosures",
            "config_profile_automation_inspect",
            "config_profile_automation_approve",
            "config_profile_automation_decline",
            "config_profile_automation_deny",
        }
    )


@pytest.mark.parametrize(
    "arguments",
    (
        ("config", "auth", "configure", "--help"),
        ("config", "auth", "certificate", "list", "--help"),
        ("config", "google", "login", "--help"),
        ("config", "sign-in-status"),
        ("config", "passphrase", "change", "--help"),
        ("config", "profile", "recovery", "status"),
        ("config", "profile", "sessions", "--help"),
        ("config", "profile", "lock", "--help"),
        ("config", "profile", "resume", "--help"),
        ("config", "profile", "automation", "list", "--help"),
    ),
)
def test_moved_auth_doors_are_not_registered_on_aeat_parser(
    arguments: tuple[str, ...], run_cadrumo_cli: Callable[..., Result]
) -> None:
    result = run_cadrumo_cli(arguments)
    assert result.exit_code != 0
