"""Real-entrypoint custody coverage for the profile lifecycle surface.

The ``"buckets"`` literal below is not arbitrary
injected values: the subprocess CLI harness sets no bucket-root or
keystore-dir override, so ``tmp_path / "buckets"`` and
``tmp_path / "keystore"`` check production's real DEFAULT-derived
locations -- the on-disk shape the CLI must actually produce for the
profile lifecycle to be filing-grade. Re-deriving either side from the
taxonomy accessor would make the assertion agree unconditionally with
the code path it exists to independently confirm.

Profiles are registered in-process and the storage root is handed to the
subprocess CLI. That is the only available shape rather than a convenience:
credential registration is the sole creation door and it takes a passphrase
as an argument, so no CLI verb -- and therefore no subprocess -- can mint a
profile. Everything after the seed still runs through the real console
script, which is what these tests exist to cover.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Final
from uuid import UUID

import pytest

from ....core import DirectoryEntryKind, scan_directory
from ....core.config import load_settings, override_settings
from ....tests import REPO_ROOT
from ....tests.subprocess_cli import run_cadrumo_subprocess
from ....tests.user_profile import register_cli_profile

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

PINNED_TAXONOMY_LITERALS: Final[frozenset[str]] = frozenset({"buckets"})
"""Taxonomy-vocabulary literals this module deliberately pins. See the module docstring."""


def _run_cadrumo(
    storage_root: Path,
    args: tuple[str, ...],
    *,
    passphrase: str | None = None,
    extra_env: dict[str, str] | None = None,
    stdin_payload: str | None = None,
) -> subprocess.CompletedProcess[str]:
    resolved_passphrase = passphrase or load_settings().cadrumo_dev_test_database_password.get_secret_value()
    return run_cadrumo_subprocess(
        args,
        settings={
            "cadrumo_local_storage_root": storage_root,
            "cadrumo_secret_store_dir": storage_root / "fallback-store",
            "cadrumo_secret_store_backend": "auto",
            "cadrumo_secret_passphrase": resolved_passphrase,
            "cadrumo_output_language": "en",
        },
        env_strip_prefixes=("AEAT_", "PYTEST_"),
        extra_env=extra_env,
        stdin_payload=stdin_payload,
        timeout=45.0,
    )


def _combined_output(result: subprocess.CompletedProcess[str]) -> str:
    return f"{result.stdout}\n{result.stderr}"


def _register_profile(storage_root: Path, label: str, **facts: str) -> str:
    """Register one profile in-process against ``storage_root``, and return its id.

    Credential registration is the only creation door and it takes a passphrase
    as an argument rather than a flag, so a subprocess cannot mint a profile.
    The sanctioned shape is to create in-process and hand the storage root to
    the child, which then reaches the profile through its own login.
    """
    with override_settings(
        cadrumo_local_storage_root=storage_root,
        cadrumo_secret_passphrase=load_settings().cadrumo_dev_test_database_password,
        cadrumo_active_profile=None,
    ):
        return register_cli_profile(label=label, facts=facts)


@pytest.mark.os_keychain  # cross-process resumption needs a minted acceleration receipt
def test_registered_profile_custody_survives_logout_and_reopens_on_login(tmp_path: Path) -> None:
    """Profile lifecycle is the custody surface; no legacy bootstrap command is reintroduced.

    The profile is registered in-process and the storage root is handed to the
    subprocess CLI, which is the only shape available: credential registration
    takes a passphrase as an argument and no CLI verb creates a profile.

    The file-fallback secret-store assertions this test carried (``master.key``
    and ``master.kdf`` under the configured secret directory) were dropped
    rather than moved. No live door writes that store any more -- a registered
    profile's custody rides its own capsule envelope, and the whole lifecycle
    below runs against a root that has no secrets directory at all -- so the
    assertions described an artefact of the retired creation path, not a
    property of custody.
    """

    _register_profile(
        tmp_path,
        "custody",
        **{
            "identity.tax_id": "12345678Z",
            "taxpayer_type.entity_type": "natural_person",
            "identity.name": "Custody Operator",
            "identity.surnames": "Operator",
            "activities.description": "design",
            "iva.regime": "GENERAL",
        },
    )

    bucket_dirs = scan_directory(tmp_path / "buckets", select=DirectoryEntryKind.DIRECTORIES)
    assert len(bucket_dirs) == 1

    # The plaintext bucket manifest this test used to read is retired: every
    # resolution path projects committed custody capsules and none reads a
    # manifest, so the label is asserted through the operator-facing listing,
    # which is the surface an operator actually reconciles against.
    listed = _run_cadrumo(tmp_path, ("config", "profile", "list"))
    assert listed.returncode == 0, _combined_output(listed)
    assert "custody" in listed.stdout

    logged_out = _run_cadrumo(tmp_path, ("config", "logout"))
    assert logged_out.returncode == 0, _combined_output(logged_out)
    assert "logged_out_profile\tcustody" in logged_out.stdout

    switched = _run_cadrumo(tmp_path, ("config", "login", "custody"))
    assert switched.returncode == 0, _combined_output(switched)
    assert "active_profile\tcustody" in switched.stdout

    deleted = _run_cadrumo(tmp_path, ("config", "profile", "delete", "custody", "--yes"))
    assert deleted.returncode == 0, _combined_output(deleted)
    assert "status\ttombstoned" in deleted.stdout
    assert "active_profile\t<none>" in deleted.stdout

    retired = _run_cadrumo(tmp_path, ("config", "init", "--help"))
    assert retired.returncode != 0
    assert "config.init" not in _combined_output(retired)


def test_profile_logout_is_the_only_strong_logout_before_switch(tmp_path: Path) -> None:
    """Strong profile logout replaces the duplicate root lock door."""

    _register_profile(
        tmp_path,
        "custody",
        **{
            "identity.tax_id": "12345678Z",
            "taxpayer_type.entity_type": "natural_person",
            "identity.name": "Custody Operator",
            "identity.surnames": "Operator",
            "activities.description": "design",
            "iva.regime": "GENERAL",
        },
    )

    logged_out = _run_cadrumo(tmp_path, ("config", "logout"))
    assert logged_out.returncode == 0, _combined_output(logged_out)
    assert "logged_out_profile\tcustody" in logged_out.stdout

    removed_lock = _run_cadrumo(tmp_path, ("config", "lock"))
    assert removed_lock.returncode != 0
    assert "No such command 'lock'" in _combined_output(removed_lock)

    missing_default = _run_cadrumo(tmp_path, ("config", "login"))
    assert missing_default.returncode != 0
    assert "No active profile" in _combined_output(missing_default) or "active profile" in _combined_output(
        missing_default,
    )

    switched_by_name = _run_cadrumo(tmp_path, ("config", "login", "custody"))
    assert switched_by_name.returncode == 0, _combined_output(switched_by_name)
    assert "active_profile\tcustody" in switched_by_name.stdout

    switched_default = _run_cadrumo(tmp_path, ("config", "login"))
    assert switched_default.returncode == 0, _combined_output(switched_default)
    assert "active_profile\tcustody" in switched_default.stdout


def test_config_passphrase_change_self_authenticates_without_a_keychain(tmp_path: Path) -> None:
    """The rotation leaf proves custody itself and survives a failing keychain.

    This is the root-gate regression for `W02.P11.S21`: the command's current
    passphrase is already the exact active profile's proof, so a keychain-free
    process must reach the leaf rather than demand a separate root credential.
    """
    _register_profile(
        tmp_path,
        "custody",
        **{
            "identity.tax_id": "12345678Z",
            "taxpayer_type.entity_type": "natural_person",
            "identity.name": "Custody Operator",
            "identity.surnames": "Operator",
            "activities.description": "design",
            "iva.regime": "GENERAL",
        },
    )
    provisioning_passphrase = load_settings().cadrumo_dev_test_database_password.get_secret_value()
    rotated_value = "correct horse battery staple"
    failing_keychain = {"PYTHON_KEYRING_BACKEND": "keyring.backends.fail.Keyring"}

    changed = _run_cadrumo(
        tmp_path,
        ("config", "passphrase", "change", "--secrets-stdin"),
        extra_env=failing_keychain,
        stdin_payload=json.dumps(
            {
                "current_passphrase": provisioning_passphrase,
                "new_passphrase": rotated_value,
                "new_passphrase_confirmation": rotated_value,
            }
        ),
    )
    assert changed.returncode == 0, _combined_output(changed)
    assert "changed\tyes" in changed.stdout
    assert provisioning_passphrase not in _combined_output(changed)
    assert rotated_value not in _combined_output(changed)

    refused_old_proof = _run_cadrumo(
        tmp_path,
        ("config", "passphrase", "change", "--secrets-stdin"),
        extra_env=failing_keychain,
        stdin_payload=json.dumps(
            {
                "current_passphrase": provisioning_passphrase,
                "new_passphrase": "irrelevant replacement value",
                "new_passphrase_confirmation": "irrelevant replacement value",
            }
        ),
    )
    assert refused_old_proof.returncode == 2, _combined_output(refused_old_proof)

    rotated_again = _run_cadrumo(
        tmp_path,
        ("config", "passphrase", "change", "--secrets-stdin"),
        extra_env=failing_keychain,
        stdin_payload=json.dumps(
            {
                "current_passphrase": rotated_value,
                "new_passphrase": "second rotated passphrase value",
                "new_passphrase_confirmation": "second rotated passphrase value",
            }
        ),
    )
    assert rotated_again.returncode == 0, _combined_output(rotated_again)


def test_profile_root_secret_authenticates_keychain_free_read_in_process(tmp_path: Path) -> None:
    """A parsed resume-fallback leaf can authenticate and continue in one process."""
    _register_profile(
        tmp_path,
        "custody",
        **{
            "identity.tax_id": "12345678Z",
            "taxpayer_type.entity_type": "natural_person",
            "identity.name": "Custody Operator",
            "identity.surnames": "Operator",
            "activities.description": "design",
            "iva.regime": "GENERAL",
        },
    )
    passphrase = load_settings().cadrumo_dev_test_database_password.get_secret_value()

    shown = _run_cadrumo(
        tmp_path,
        ("--profile-secrets-stdin", "config", "profile", "show", "custody"),
        extra_env={"PYTHON_KEYRING_BACKEND": "keyring.backends.fail.Keyring"},
        stdin_payload=json.dumps({"profile_passphrase": passphrase}),
    )

    assert shown.returncode == 0, _combined_output(shown)
    assert "display_name\tcustody" in shown.stdout
    assert "config.login.session_not_persisted" in shown.stdout
    assert passphrase not in _combined_output(shown)

    for command in (("config", "profile", "validate", "custody"), ("config", "profile", "history", "custody")):
        result = _run_cadrumo(
            tmp_path,
            ("--profile-secrets-stdin", *command),
            extra_env={"PYTHON_KEYRING_BACKEND": "keyring.backends.fail.Keyring"},
            stdin_payload=json.dumps({"profile_passphrase": passphrase}),
        )
        assert result.returncode == 0, _combined_output(result)
        assert passphrase not in _combined_output(result)


def test_keychain_free_root_login_notice_survives_a_real_leaf_refusal(tmp_path: Path) -> None:
    """A refusal after real Argon2 login carries the staged Notice on stderr."""
    _register_profile(tmp_path, "custody")
    passphrase = load_settings().cadrumo_dev_test_database_password.get_secret_value()

    refused = _run_cadrumo(
        tmp_path,
        (
            "--format",
            "json",
            "--profile-secrets-stdin",
            "app",
            "ledger",
            "view",
            "transaction-does-not-exist",
        ),
        extra_env={"PYTHON_KEYRING_BACKEND": "keyring.backends.fail.Keyring"},
        stdin_payload=json.dumps({"profile_passphrase": passphrase}),
    )

    output = _combined_output(refused)
    assert refused.returncode != 0, output
    envelope = json.loads(refused.stderr)
    assert envelope["command"] == "ledger.view"
    assert [notice["code"] for notice in envelope["notices"]] == [
        "config.login.session_not_persisted"
    ]
    assert passphrase not in output


def test_root_and_leaf_stdin_collision_refuses_before_fresh_tree_mutation(tmp_path: Path) -> None:
    """Parsed cross-scope collision wins before profile lookup, reads, or setup writes."""
    result = _run_cadrumo(
        tmp_path,
        ("--profile-secrets-stdin", "config", "passphrase", "change", "--secrets-stdin"),
        stdin_payload="must-remain-unread",
    )

    output = _combined_output(result)
    assert result.returncode == 2, output
    assert "collision" in output.lower()
    assert "json" not in output.lower()
    assert not tmp_path.exists() or tuple(tmp_path.iterdir()) == ()


@pytest.mark.parametrize("command", [("app",), ("config",), ("app", "diagnostics")])
def test_terminal_introspection_groups_leave_a_fresh_root_state_free(
    tmp_path: Path, command: tuple[str, ...]
) -> None:
    result = _run_cadrumo(tmp_path, command)

    assert result.returncode in {0, 2}, _combined_output(result)
    assert not tmp_path.exists() or tuple(tmp_path.iterdir()) == ()


def test_terminal_executable_group_preserves_root_secret_source_for_parsed_gate(
    tmp_path: Path,
) -> None:
    result = _run_cadrumo(
        tmp_path,
        (
            "--profile-secrets-stdin",
            "app",
            "quickfile",
            "--modelo",
            "303",
            "--year",
            "2025",
            "--period",
            "1T",
        ),
        stdin_payload="must-remain-unread",
    )

    output = _combined_output(result)
    assert result.returncode == 2, output
    assert "target" in output.lower()
    assert "json" not in output.lower()


def test_blank_explicit_profile_target_refuses_before_root_secret_read(tmp_path: Path) -> None:
    _register_profile(tmp_path, "ambient")
    result = _run_cadrumo(
        tmp_path,
        ("--profile-secrets-stdin", "config", "profile", "show", ""),
        stdin_payload="must-remain-unread",
    )

    output = _combined_output(result)
    assert result.returncode == 2, output
    assert "json" not in output.lower()


def test_self_authenticating_leaf_refuses_root_source_unread(tmp_path: Path) -> None:
    result = _run_cadrumo(
        tmp_path,
        ("--profile-secrets-stdin", "config", "passphrase", "change"),
        stdin_payload="must-remain-unread",
    )

    output = _combined_output(result)
    assert result.returncode == 2, output
    assert "inapplicable" in output.lower()
    assert "json" not in output.lower()


@pytest.mark.os_keychain
def test_valid_resumed_session_refuses_root_source_unread(tmp_path: Path) -> None:
    bucket_id = _register_profile(tmp_path, "custody")
    passphrase = load_settings().cadrumo_dev_test_database_password.get_secret_value()
    logged_in = _run_cadrumo(
        tmp_path,
        ("config", "login", "custody", "--secrets-stdin"),
        stdin_payload=json.dumps({"passphrase": passphrase}),
    )
    assert logged_in.returncode == 0, _combined_output(logged_in)
    from ....adapters.persistence.storage.custody import profile_session_path

    if not profile_session_path(storage_root=tmp_path, profile_id=UUID(bucket_id)).is_file():
        pytest.skip("host OS keychain cannot persist the cross-process profile session")

    refused = _run_cadrumo(
        tmp_path,
        ("--profile-secrets-stdin", "config", "profile", "show", "custody"),
        stdin_payload="must-remain-unread",
    )
    output = _combined_output(refused)
    assert refused.returncode == 2, output
    assert "unused" in output.lower()
    assert "json" not in output.lower()


def test_passphrase_change_resolves_target_before_reading_machine_secrets(tmp_path: Path) -> None:
    """An absent active target refuses without parsing the supplied payload."""
    result = _run_cadrumo(
        tmp_path,
        ("config", "passphrase", "change", "--secrets-stdin"),
        extra_env={"PYTHON_KEYRING_BACKEND": "keyring.backends.fail.Keyring"},
        stdin_payload="not-json-and-must-remain-unread",
    )
    output = _combined_output(result)
    assert result.returncode == 2, output
    assert "No active profile" in output or "active profile" in output
    assert "JSON" not in output


def test_config_help_exposes_first_class_custody_verbs(tmp_path: Path) -> None:
    """The accepted custody verbs are mounted, and the retired ones are not.

    ``login`` and ``logout`` are the canonical profile-session doors. Retired
    spellings are asserted ABSENT in the same pass, because each cutover was a
    deletion rather than a rename: an alias or a hidden registration would
    satisfy a mounted-verb check while reinstating the door the ruling removed.

    This list previously asserted ``recover`` and ``recovery`` were mounted.
    Both had been retired by an accepted ruling, so the assertion outlived the
    decision it was written under and failed against a tree that was correct --
    the mirror of the repair that fixed gates asserting removed verbs were
    absent. They are now checked in the retired direction, which is the claim
    that is actually true and which still catches a silent reinstatement.

    ``passphrase change`` is the sole credential-rotation door. Its presence is
    asserted beside login/logout while the older ambiguous custody spellings
    remain physically absent.
    """

    for verb in ("login", "logout", "passphrase"):
        help_result = _run_cadrumo(tmp_path, ("config", verb, "--help"))
        assert help_result.returncode == 0, _combined_output(help_result)
        assert verb in _combined_output(help_result)

    for retired_verb in ("switch", "recover", "recovery"):
        retired = _run_cadrumo(tmp_path, ("config", retired_verb, "--help"))
        assert retired.returncode != 0, _combined_output(retired)
        assert f"No such command '{retired_verb}'" in _combined_output(retired)


def test_profile_selection_precedence_uses_explicit_flag_then_pointer(tmp_path: Path) -> None:
    """CLI profile reads resolve explicit name, then --profile, then the pointer.

    The environment holds no rung of this chain. A stale exported
    ``CADRUMO_ACTIVE_PROFILE`` is carried through every invocation below
    precisely to prove it is inert: selection comes from ``--profile`` or the
    pointer file, never from the shell.
    """

    alpha_id = _register_profile(
        tmp_path,
        "alpha",
        **{
            "identity.tax_id": "12345678Z",
            "taxpayer_type.entity_type": "natural_person",
            "identity.name": "Alpha Operator",
            "identity.surnames": "Operator",
            "activities.description": "consulting",
            "iva.regime": "GENERAL",
        },
    )
    beta_id = _register_profile(
        tmp_path,
        "beta",
        **{
            "identity.tax_id": "87654321X",
            "taxpayer_type.entity_type": "natural_person",
            "identity.name": "Beta Operator",
            "identity.surnames": "Operator",
            "activities.description": "design",
            "iva.regime": "GENERAL",
        },
    )

    # The registration door returns the minted identity, so the ids are known
    # without reading the retired plaintext bucket manifest.
    # ``profile show`` does not render the manifest label across a process
    # boundary, so selection is observed through a per-profile FACT instead.
    # Alpha and Beta carry distinct ``identity.name`` values for exactly that
    # purpose, and the assertion is the same claim: which profile resolved.
    labels_by_id = {alpha_id: "alpha", beta_id: "beta"}
    assert set(labels_by_id) == {
        entry.name for entry in scan_directory(tmp_path / "buckets", select=DirectoryEntryKind.DIRECTORIES)
    }

    pointer_default = _run_cadrumo(tmp_path, ("config", "profile", "show"))
    assert pointer_default.returncode == 0, _combined_output(pointer_default)
    assert "identity.name\tBeta Operator" in pointer_default.stdout

    # A set environment variable cannot displace the pointer: the pointer
    # still selects beta even while the shell names alpha.
    env_inert = _run_cadrumo(
        tmp_path,
        ("config", "profile", "show"),
        extra_env={"CADRUMO_ACTIVE_PROFILE": alpha_id},
    )
    assert env_inert.returncode == 0, _combined_output(env_inert)
    assert "identity.name\tBeta Operator" in env_inert.stdout

    # The flag is the selection channel that does win over the pointer.
    flag_default = _run_cadrumo(tmp_path, ("--profile", "alpha", "config", "profile", "show"))
    assert flag_default.returncode == 0, _combined_output(flag_default)
    assert "identity.name\tAlpha Operator" in flag_default.stdout

    # An explicit NAME outranks ``--profile``. The record itself is NOT
    # readable here and that is custody working, not a defect: each profile's
    # record is sealed under its own capsule key, and the live session belongs
    # to alpha. What the precedence claim needs is which profile the verb
    # RESOLVED to, and the refusal names it -- beta, not the alpha the flag and
    # the environment both asked for. A precedence regression would name alpha.
    explicit_name = _run_cadrumo(
        tmp_path,
        ("--profile", "alpha", "config", "profile", "show", "beta"),
        extra_env={"CADRUMO_ACTIVE_PROFILE": alpha_id},
    )
    resolved_explicit_name = _combined_output(explicit_name)
    assert "display_name\tbeta" in resolved_explicit_name, resolved_explicit_name
    assert "display_name\talpha" not in resolved_explicit_name, resolved_explicit_name

    explicit_root = _run_cadrumo(
        tmp_path,
        ("--profile", "alpha", "config", "profile", "show"),
        extra_env={
            "CADRUMO_ACTIVE_PROFILE": next(bucket_id for bucket_id, label in labels_by_id.items() if label == "beta"),
        },
    )
    assert explicit_root.returncode == 0, _combined_output(explicit_root)
    assert "identity.name\tAlpha Operator" in explicit_root.stdout

    explicit_root_by_id = _run_cadrumo(
        tmp_path,
        ("--profile", alpha_id, "config", "profile", "show"),
        extra_env={"CADRUMO_ACTIVE_PROFILE": alpha_id},
    )
    assert explicit_root_by_id.returncode == 0, _combined_output(explicit_root_by_id)
    assert "identity.name\tAlpha Operator" in explicit_root_by_id.stdout

    # Write-side precedence: configure-auth writes an
    # ``AUTH_PROVIDER_CONFIGURED`` event into the resolved bucket's
    # event history. The configure verb's stdout redacts the bucket id
    # to a literal ``<profile-id>`` placeholder (security: bucket ids
    # are sha256 fingerprints that must never reach stdout), so the
    # stdout cannot distinguish alpha from beta. Read each bucket's
    # event history via ``config profile history`` to count writes per
    # bucket; the bucket whose count increases by 1 is the one the
    # configure verb resolved to.

    def _auth_event_counts() -> dict[str, int]:
        counts: dict[str, int] = {}
        for bucket_id in (alpha_id, beta_id):
            profile_name = labels_by_id[bucket_id]
            result = _run_cadrumo(
                tmp_path,
                (
                    "--profile",
                    bucket_id,
                    "config",
                    "profile",
                    "history",
                    profile_name,
                    "--event-type",
                    "auth.provider.configured",
                ),
            )
            assert result.returncode == 0, _combined_output(result)
            assert f"profile\t{profile_name}" in result.stdout
            assert f"bucket_id\t{bucket_id}" not in result.stdout
            counts[bucket_id] = sum(1 for line in result.stdout.splitlines() if "\tauth.provider.configured\t" in line)
        return counts

    before = _auth_event_counts()

    # Pointer-default precedence: pointer points at beta (last create wins).
    pointer_write = _run_cadrumo(tmp_path, ("config", "auth", "configure", "--provider", "clave_movil"))
    assert pointer_write.returncode == 0, _combined_output(pointer_write)
    assert "No active profile" not in _combined_output(pointer_write)
    after_pointer = _auth_event_counts()
    assert after_pointer[beta_id] == before[beta_id] + 1, (
        f"pointer default should resolve to beta; counts before={before}, after={after_pointer}"
    )
    assert after_pointer[alpha_id] == before[alpha_id], (
        f"pointer default should not write to alpha; counts before={before}, after={after_pointer}"
    )

    # The environment is INERT: a stale exported CADRUMO_ACTIVE_PROFILE naming
    # alpha must not redirect the write, so it still lands in the pointer's
    # beta. This is the write-side half of the retired env precedence, and it
    # is asserted rather than deleted because a selection mechanism that
    # silently redirected WRITES is the failure worth guarding against.
    env_write = _run_cadrumo(
        tmp_path,
        ("config", "auth", "configure", "--provider", "clave_movil"),
        extra_env={"CADRUMO_ACTIVE_PROFILE": alpha_id},
    )
    assert env_write.returncode == 0, _combined_output(env_write)
    assert "No active profile" not in _combined_output(env_write)
    after_env = _auth_event_counts()
    assert after_env[beta_id] == after_pointer[beta_id] + 1, (
        f"a set environment variable must not displace the pointer; counts before={after_pointer}, after={after_env}"
    )
    assert after_env[alpha_id] == after_pointer[alpha_id], (
        f"a set environment variable must not redirect the write to alpha; "
        f"counts before={after_pointer}, after={after_env}"
    )

    # Flag precedence: --profile IS the surviving override and does win.
    flag_write = _run_cadrumo(
        tmp_path,
        ("--profile", "alpha", "config", "auth", "configure", "--provider", "clave_movil"),
    )
    assert flag_write.returncode == 0, _combined_output(flag_write)
    assert "No active profile" not in _combined_output(flag_write)
    after_flag = _auth_event_counts()
    assert after_flag[alpha_id] == after_env[alpha_id] + 1, (
        f"--profile should resolve to alpha; counts before={after_env}, after={after_flag}"
    )
    assert after_flag[beta_id] == after_env[beta_id], (
        f"--profile should not write to beta; counts before={after_env}, after={after_flag}"
    )

    # The flag still decides even while a contradicting variable is exported:
    # --profile names beta, the environment names alpha, and beta wins.
    explicit_write = _run_cadrumo(
        tmp_path,
        ("--profile", "beta", "config", "auth", "configure", "--provider", "clave_movil"),
        extra_env={"CADRUMO_ACTIVE_PROFILE": alpha_id},
    )
    assert explicit_write.returncode == 0, _combined_output(explicit_write)
    assert "No active profile" not in _combined_output(explicit_write)
    after_explicit = _auth_event_counts()
    assert after_explicit[beta_id] == after_flag[beta_id] + 1, (
        f"--profile flag should resolve to beta; counts before={after_flag}, after={after_explicit}"
    )
    assert after_explicit[alpha_id] == after_flag[alpha_id], (
        f"--profile flag should not write to alpha; counts before={after_flag}, after={after_explicit}"
    )


def test_profile_lifecycle_storage_spans_are_application_owned() -> None:
    """CLI and wizard code delegate custody spans to application profile lifecycle operations."""

    scanned = {
        "src/cadrumo/entrypoints/cli/_config/__init__.py": (
            "activate_master_key_provider",
            "get_master_key_provider",
            "_write_active_profile_pointer",
            "_clear_active_profile_pointer",
            "capture_active_profile_pointer",
            "restore_active_profile_pointer",
            "override_settings(cadrumo_active_profile",
        ),
        "src/cadrumo/application/wizard/_commands.py": (
            "activate_master_key_provider",
            "get_master_key_provider",
            "_write_active_profile_pointer",
            "_clear_active_profile_pointer",
            "capture_active_profile_pointer",
            "restore_active_profile_pointer",
            "override_settings(cadrumo_active_profile",
        ),
    }
    offenders: list[str] = []
    for relative_path, forbidden_tokens in scanned.items():
        text = (REPO_ROOT / relative_path).read_text(encoding="utf-8")
        for token in forbidden_tokens:
            if token in text:
                offenders.append(f"{relative_path}: {token}")

    assert offenders == []
