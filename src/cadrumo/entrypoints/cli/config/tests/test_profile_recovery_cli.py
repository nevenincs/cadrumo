"""Real-behaviour tests for optional recovery through the CLI.

Recovery is off by default and enrolled after the profile exists: ``config
profile recovery enable`` proves the passphrase, hands the minted code over
exactly once through the two-descriptor channel, and installs the wrapper
only after the exact code comes back. ``config passphrase reset NAME`` is the
one thing the code is good for. These cases drive the real verbs in process
against a real storage root, through the real registration and custody
doors, with the operator's part of the handoff played by a relay thread.
No mocks, no stubs.
"""

from __future__ import annotations

import json
import os
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager, suppress
from dataclasses import replace
from pathlib import Path
from typing import Any, cast

import pytest
from click.testing import Result

from .....adapters.persistence.storage.recovery_key import (
    RECOVERY_CODE_ALPHABET,
    RECOVERY_CODE_GROUP_COUNT,
    RECOVERY_CODE_GROUP_LENGTH,
    RECOVERY_CODE_SEPARATOR,
)
from .....adapters.persistence.storage.tests.secure_sql import isolated_profile_storage_root
from .....core.i18n.render import tr
from ... import command_specs as _command_specs
from ...command_spec import ArgumentSpec
from ...tests.cli_runner import invoke_cached_cli
from ...tests.scripted_registration_channels import scripted_registration_descriptors
from ...verb_input_schema import build_verb_input_schemas, project_recovery_handoff_contract

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_CREDENTIAL_INPUT = "a-sufficiently-long-operator-passphrase"
_ROTATED_CREDENTIAL_INPUT = "a-replacement-passphrase-after-reset"
_PROFILE = "Recovery Operator"


def _creation_payload(credential: str = _CREDENTIAL_INPUT) -> str:
    return json.dumps({"passphrase": credential, "passphrase_confirmation": credential})


def _create_profile(name: str = _PROFILE) -> Result:
    """Create a profile the scripted way and open its session, as every profile-read verb requires."""
    created = invoke_cached_cli(
        ("--format", "json", "config", "profile", "create", name, "--quiet", "--secrets-stdin"),
        input=_creation_payload(),
    )
    assert created.exit_code == 0, created.output
    session = _login(name, credential=_CREDENTIAL_INPUT)
    assert session.exit_code == 0, session.output
    return created


def _logout() -> None:
    """Close the process-scoped session so a later login proves the passphrase afresh."""
    result = invoke_cached_cli(("--format", "json", "config", "logout"))
    assert result.exit_code == 0, result.output


def _status() -> dict[str, Any]:
    result = invoke_cached_cli(("--format", "json", "config", "profile", "recovery", "status"))
    assert result.exit_code == 0, result.output
    document = json.loads(result.stdout)
    assert document["command"] == "config.profile.recovery.status"
    return document["result"]


def _enable(handoff: int, verification: int, *, credential: str = _CREDENTIAL_INPUT) -> Result:
    return invoke_cached_cli(
        (
            "--format",
            "json",
            "config",
            "profile",
            "recovery",
            "enable",
            "--secrets-stdin",
            "--recovery-handoff-fd",
            str(handoff),
            "--recovery-verification-fd",
            str(verification),
        ),
        input=json.dumps({"passphrase": credential}),
    )


def _disable(*, credential: str = _CREDENTIAL_INPUT) -> Result:
    return invoke_cached_cli(
        ("--format", "json", "config", "profile", "recovery", "disable", "--secrets-stdin"),
        input=json.dumps({"passphrase": credential}),
    )


def _reset(name: str, *, code: str, replacement: str = _ROTATED_CREDENTIAL_INPUT) -> Result:
    return invoke_cached_cli(
        ("--format", "json", "config", "passphrase", "reset", name, "--secrets-stdin"),
        input=json.dumps(
            {
                "recovery_code": code,
                "new_passphrase": replacement,
                "new_passphrase_confirmation": replacement,
            }
        ),
    )


def _login(name: str, *, credential: str) -> Result:
    return invoke_cached_cli(
        ("--format", "json", "config", "login", name, "--secrets-stdin"),
        input=json.dumps({"passphrase": credential}),
    )


def _assert_recovery_code_shape(code: str) -> None:
    groups = code.split(RECOVERY_CODE_SEPARATOR)
    assert len(groups) == RECOVERY_CODE_GROUP_COUNT
    assert all(len(group) == RECOVERY_CODE_GROUP_LENGTH for group in groups)
    assert all(symbol in RECOVERY_CODE_ALPHABET for group in groups for symbol in group)


@contextmanager
def _capturing_descriptors(
    respond: Callable[[bytes], bytes] = lambda document: document,
) -> Iterator[tuple[int, int, list[str]]]:
    """Play the operator's part of the handoff while keeping the code for a later reset.

    ``scripted_registration_descriptors`` only echoes the document back; a
    reset needs the code itself, so this relay records it before answering.
    ``respond`` transforms the answer so a wrong proof can be exercised.
    """
    handoff_reader, handoff_writer = os.pipe()
    verification_reader, verification_writer = os.pipe()
    codes: list[str] = []

    def relay() -> None:
        document = bytearray()
        try:
            while not document.endswith(b"\n"):
                chunk = os.read(handoff_reader, 8193 - len(document))
                if not chunk:
                    break
                document.extend(chunk)
            if document:
                codes.append(json.loads(bytes(document))["recovery_code"])
                with suppress(OSError):
                    os.write(verification_writer, respond(bytes(document)))
        finally:
            document[:] = b"\x00" * len(document)
            with suppress(OSError):
                os.close(verification_writer)

    worker = threading.Thread(target=relay, daemon=True)
    worker.start()
    try:
        yield handoff_writer, verification_reader, codes
    finally:
        for descriptor in (handoff_writer, verification_reader):
            with suppress(OSError):
                os.close(descriptor)
        worker.join(timeout=5)
        with suppress(OSError):
            os.close(handoff_reader)
    assert not worker.is_alive()


def test_create_never_asks_a_machine_caller_about_recovery(tmp_path: Path) -> None:
    """A scripted create reports the skipped enrolment; the console offer never appears."""
    with isolated_profile_storage_root(tmp_path=tmp_path):
        created = _create_profile()
        document = json.loads(created.stdout)
        codes = [notice["code"] for notice in document["notices"]]
        assert "PROFILE_RECOVERY_NOT_ENROLLED" in codes
        assert "PROFILE_RECOVERY_ENABLED" not in codes
        assert tr("cli.config.profile.create_recovery_skipped") in [n["message"] for n in document["notices"]]
        assert tr("cli.config.profile.create_recovery_offer_prompt") not in created.stdout + created.stderr
        assert _status()["enrolled"] is False


def test_status_reports_enrolment_before_and_after_a_headless_enable(tmp_path: Path) -> None:
    with isolated_profile_storage_root(tmp_path=tmp_path):
        _create_profile()
        assert _status()["enrolled"] is False

        with scripted_registration_descriptors() as (handoff, verification):
            enabled = _enable(handoff, verification)

        assert enabled.exit_code == 0, enabled.output
        document = json.loads(enabled.stdout)
        assert document["command"] == "config.profile.recovery.enable"
        assert document["result"]["enrolled"] is True
        assert document["result"]["changed"] is True
        assert [notice["code"] for notice in document["notices"]] == ["PROFILE_RECOVERY_ENABLED"]
        assert "recovery_code" not in enabled.stdout + enabled.stderr
        assert _status()["enrolled"] is True


def test_a_second_enable_refuses_while_recovery_is_enrolled(tmp_path: Path) -> None:
    with isolated_profile_storage_root(tmp_path=tmp_path):
        _create_profile()
        with scripted_registration_descriptors() as (handoff, verification):
            assert _enable(handoff, verification).exit_code == 0

        with scripted_registration_descriptors() as (handoff, verification):
            refused = _enable(handoff, verification)

        assert refused.exit_code != 0
        assert json.loads(refused.stderr)["error"]["message"] == tr(
            "application.user_profile.errors.recovery_already_enrolled"
        )
        assert _status()["enrolled"] is True


def test_enable_hands_over_a_grouped_code_that_never_reaches_the_streams(tmp_path: Path) -> None:
    with isolated_profile_storage_root(tmp_path=tmp_path):
        _create_profile()
        with _capturing_descriptors() as (handoff, verification, codes):
            enabled = _enable(handoff, verification)

        assert enabled.exit_code == 0, enabled.output
        assert len(codes) == 1
        _assert_recovery_code_shape(codes[0])
        assert codes[0] not in enabled.stdout + enabled.stderr
        assert _status()["enrolled"] is True


def test_enable_refuses_a_wrong_possession_proof_without_enrolling(tmp_path: Path) -> None:
    def swap_first_two_groups(document: bytes) -> bytes:
        parsed = json.loads(document)
        groups = str(parsed["recovery_code"]).split(RECOVERY_CODE_SEPARATOR)
        groups[0], groups[1] = groups[1], groups[0]
        parsed["recovery_code"] = RECOVERY_CODE_SEPARATOR.join(groups)
        return json.dumps(parsed).encode() + b"\n"

    with isolated_profile_storage_root(tmp_path=tmp_path):
        _create_profile()
        with _capturing_descriptors(respond=swap_first_two_groups) as (handoff, verification, codes):
            refused = _enable(handoff, verification)

        assert refused.exit_code != 0
        assert len(codes) == 1
        assert json.loads(refused.stderr)["error"]["message"] == tr("cli.config.profile.recovery.verification_mismatch")
        assert codes[0] not in refused.stdout + refused.stderr
        assert _status()["enrolled"] is False


def test_enable_refuses_a_wrong_passphrase_before_handing_anything_over(tmp_path: Path) -> None:
    with isolated_profile_storage_root(tmp_path=tmp_path):
        _create_profile()
        with _capturing_descriptors() as (handoff, verification, codes):
            refused = _enable(handoff, verification, credential="not-the-operator-passphrase")

        assert refused.exit_code != 0
        assert codes == []
        assert json.loads(refused.stderr)["error"]["message"] == tr(
            "application.user_profile.errors.passphrase_current_rejected"
        )
        assert _status()["enrolled"] is False


def test_headless_enable_without_descriptors_refuses_without_enrolling(tmp_path: Path) -> None:
    """With no terminal and no descriptor pair there is nowhere safe to show the code."""
    with isolated_profile_storage_root(tmp_path=tmp_path):
        _create_profile()
        refused = invoke_cached_cli(
            ("--format", "json", "config", "profile", "recovery", "enable", "--secrets-stdin"),
            input=json.dumps({"passphrase": _CREDENTIAL_INPUT}),
        )
        assert refused.exit_code != 0
        assert json.loads(refused.stderr)["error"]["message"] == tr("cli.config.profile.recovery.channel_absent")
        assert _status()["enrolled"] is False


@pytest.mark.parametrize(
    ("extra", "message_key"),
    (
        (("--recovery-handoff-fd", "9"), "cli.config.profile.recovery.descriptor_pair_required"),
        (("--recovery-verification-fd", "9"), "cli.config.profile.recovery.descriptor_pair_required"),
        (
            ("--recovery-handoff-fd", "-1", "--recovery-verification-fd", "9"),
            "cli.config.profile.recovery.descriptor_reserved",
        ),
        (
            ("--recovery-handoff-fd", "1", "--recovery-verification-fd", "9"),
            "cli.config.profile.recovery.descriptor_reserved",
        ),
        (
            ("--recovery-handoff-fd", "9", "--recovery-verification-fd", "9"),
            "cli.config.profile.recovery.descriptor_collision",
        ),
    ),
)
def test_descriptor_preflight_refuses_before_any_secret_is_read(
    tmp_path: Path, extra: tuple[str, ...], message_key: str
) -> None:
    with isolated_profile_storage_root(tmp_path=tmp_path):
        _create_profile()
        refused = invoke_cached_cli(
            ("--format", "json", "config", "profile", "recovery", "enable", "--secrets-stdin", *extra),
            input=json.dumps({"passphrase": _CREDENTIAL_INPUT}),
        )
        assert refused.exit_code != 0
        assert json.loads(refused.stderr)["error"]["message"] == tr(message_key)
        assert _status()["enrolled"] is False


def test_the_passphrase_descriptor_may_not_double_as_a_recovery_descriptor(tmp_path: Path) -> None:
    reader, writer = os.pipe()
    os.write(writer, json.dumps({"passphrase": _CREDENTIAL_INPUT}).encode())
    os.close(writer)
    try:
        with isolated_profile_storage_root(tmp_path=tmp_path):
            _create_profile()
            refused = invoke_cached_cli(
                (
                    "--format",
                    "json",
                    "config",
                    "profile",
                    "recovery",
                    "enable",
                    "--secrets-fd",
                    str(reader),
                    "--recovery-handoff-fd",
                    str(reader),
                    "--recovery-verification-fd",
                    "9",
                ),
            )
            assert refused.exit_code != 0
            assert json.loads(refused.stderr)["error"]["message"] == tr(
                "cli.config.profile.recovery.descriptor_collision"
            )
            assert _status()["enrolled"] is False
    finally:
        with suppress(OSError):
            os.close(reader)


def test_unwritable_handoff_closes_both_descriptors_without_enrolling(tmp_path: Path) -> None:
    handoff_reader, handoff_writer = os.pipe()
    verification_reader, verification_writer = os.pipe()
    os.close(handoff_writer)
    os.close(verification_writer)
    with isolated_profile_storage_root(tmp_path=tmp_path):
        _create_profile()
        refused = _enable(handoff_reader, verification_reader)
        assert refused.exit_code != 0
        for descriptor in (handoff_reader, verification_reader):
            with pytest.raises(OSError):
                os.fstat(descriptor)
        assert _status()["enrolled"] is False


def test_disable_removes_the_enrolment_and_is_idempotent(tmp_path: Path) -> None:
    with isolated_profile_storage_root(tmp_path=tmp_path):
        _create_profile()
        with scripted_registration_descriptors() as (handoff, verification):
            assert _enable(handoff, verification).exit_code == 0
        assert _status()["enrolled"] is True

        disabled = _disable()
        assert disabled.exit_code == 0, disabled.output
        document = json.loads(disabled.stdout)
        assert document["command"] == "config.profile.recovery.disable"
        assert set(document["result"]) == {"profile_id", "enrolled", "changed"}
        assert document["result"]["enrolled"] is False
        assert document["result"]["changed"] is True
        assert _status()["enrolled"] is False

        again = _disable()
        assert again.exit_code == 0, again.output
        assert json.loads(again.stdout)["result"]["changed"] is False


def test_disable_refuses_a_wrong_passphrase_and_keeps_the_enrolment(tmp_path: Path) -> None:
    with isolated_profile_storage_root(tmp_path=tmp_path):
        _create_profile()
        with scripted_registration_descriptors() as (handoff, verification):
            assert _enable(handoff, verification).exit_code == 0

        refused = _disable(credential="not-the-operator-passphrase")
        assert refused.exit_code != 0
        assert json.loads(refused.stderr)["error"]["message"] == tr(
            "application.user_profile.errors.passphrase_current_rejected"
        )
        assert _status()["enrolled"] is True


def test_reset_replaces_a_forgotten_passphrase_with_the_captured_code(tmp_path: Path) -> None:
    """The whole point of the code: a reset proved by it opens the profile under the new passphrase."""
    with isolated_profile_storage_root(tmp_path=tmp_path):
        _create_profile()
        with _capturing_descriptors() as (handoff, verification, codes):
            assert _enable(handoff, verification).exit_code == 0
        code = codes[0]

        reset = _reset(_PROFILE, code=code)
        assert reset.exit_code == 0, reset.output
        document = json.loads(reset.stdout)
        assert document["command"] == "config.passphrase.reset"
        assert document["result"]["changed"] is True
        assert document["result"]["dek_epoch_preserved"] is True
        assert document["result"]["recovery_enrollment_retained"] is True
        assert document["result"]["password_generation"] == 2
        combined = reset.stdout + reset.stderr
        assert code not in combined
        assert _ROTATED_CREDENTIAL_INPUT not in combined

        # The successful login comes first: a deliberate failed login arms the
        # login throttle, which would then refuse the new passphrase for a
        # reason unrelated to the reset.
        _logout()
        fresh = _login(_PROFILE, credential=_ROTATED_CREDENTIAL_INPUT)
        assert fresh.exit_code == 0, fresh.output
        assert json.loads(fresh.stdout)["command"] == "config.login"
        assert _status()["enrolled"] is True

        _logout()
        stale = _login(_PROFILE, credential=_CREDENTIAL_INPUT)
        assert stale.exit_code != 0, stale.output


def test_reset_accepts_the_code_with_cosmetic_spacing_and_case_differences(tmp_path: Path) -> None:
    with isolated_profile_storage_root(tmp_path=tmp_path):
        _create_profile()
        with _capturing_descriptors() as (handoff, verification, codes):
            assert _enable(handoff, verification).exit_code == 0
        typed = codes[0].replace(RECOVERY_CODE_SEPARATOR, " ").lower()

        reset = _reset(_PROFILE, code=typed)
        assert reset.exit_code == 0, reset.output
        _logout()
        assert _login(_PROFILE, credential=_ROTATED_CREDENTIAL_INPUT).exit_code == 0


def test_reset_refuses_a_wrong_code_and_keeps_the_current_passphrase(tmp_path: Path) -> None:
    with isolated_profile_storage_root(tmp_path=tmp_path):
        _create_profile()
        with _capturing_descriptors() as (handoff, verification, codes):
            assert _enable(handoff, verification).exit_code == 0
        groups = codes[0].split(RECOVERY_CODE_SEPARATOR)
        groups[0], groups[-1] = groups[-1], groups[0]
        wrong = RECOVERY_CODE_SEPARATOR.join(groups)

        refused = _reset(_PROFILE, code=wrong)
        assert refused.exit_code != 0
        assert json.loads(refused.stderr)["error"]["message"] == tr(
            "application.user_profile.errors.recovery_code_rejected"
        )
        assert wrong not in refused.stdout + refused.stderr
        # Prove the surviving passphrase before the refused one: a failed login
        # arms the throttle and would mask the success it precedes.
        _logout()
        assert _login(_PROFILE, credential=_CREDENTIAL_INPUT).exit_code == 0
        _logout()
        assert _login(_PROFILE, credential=_ROTATED_CREDENTIAL_INPUT).exit_code != 0


def test_reset_refuses_a_malformed_code_without_touching_the_capsule(tmp_path: Path) -> None:
    with isolated_profile_storage_root(tmp_path=tmp_path):
        _create_profile()
        with scripted_registration_descriptors() as (handoff, verification):
            assert _enable(handoff, verification).exit_code == 0

        refused = _reset(_PROFILE, code="not a recovery code at all")
        assert refused.exit_code != 0
        assert "Traceback" not in refused.stdout + refused.stderr
        _logout()
        assert _login(_PROFILE, credential=_CREDENTIAL_INPUT).exit_code == 0


def test_reset_refuses_a_profile_without_recovery(tmp_path: Path) -> None:
    with isolated_profile_storage_root(tmp_path=tmp_path):
        _create_profile()
        refused = _reset(_PROFILE, code="AAAAA-AAAAA-AAAAA-AAAAA-AAAAA-AAAAA")
        assert refused.exit_code != 0
        assert json.loads(refused.stderr)["error"]["message"] == tr(
            "application.user_profile.errors.recovery_not_enrolled"
        )
        _logout()
        assert _login(_PROFILE, credential=_CREDENTIAL_INPUT).exit_code == 0


def test_reset_refuses_a_mismatched_confirmation_without_consulting_the_code(tmp_path: Path) -> None:
    with isolated_profile_storage_root(tmp_path=tmp_path):
        _create_profile()
        with _capturing_descriptors() as (handoff, verification, codes):
            assert _enable(handoff, verification).exit_code == 0

        refused = invoke_cached_cli(
            ("--format", "json", "config", "passphrase", "reset", _PROFILE, "--secrets-stdin"),
            input=json.dumps(
                {
                    "recovery_code": codes[0],
                    "new_passphrase": _ROTATED_CREDENTIAL_INPUT,
                    "new_passphrase_confirmation": "a-different-confirmation-value",
                }
            ),
        )
        assert refused.exit_code != 0
        assert json.loads(refused.stderr)["error"]["message"] == tr(
            "application.user_profile.errors.passphrase_confirmation_mismatch"
        )
        _logout()
        assert _login(_PROFILE, credential=_CREDENTIAL_INPUT).exit_code == 0


def test_reset_refuses_an_unknown_profile_before_reading_the_payload(tmp_path: Path) -> None:
    with isolated_profile_storage_root(tmp_path=tmp_path):
        _create_profile()
        refused = _reset("No Such Profile", code="AAAAA-AAAAA-AAAAA-AAAAA-AAAAA-AAAAA")
        assert refused.exit_code != 0
        assert "Traceback" not in refused.stdout + refused.stderr


def test_recovery_verbs_refuse_without_an_active_profile(tmp_path: Path) -> None:
    with isolated_profile_storage_root(tmp_path=tmp_path):
        status = invoke_cached_cli(("--format", "json", "config", "profile", "recovery", "status"))
        assert status.exit_code != 0
        assert json.loads(status.stderr)["error"]["message"] == tr("cli.config.profile.recovery.no_active_profile")


# --- command-graph declaration of the handoff protocol --------------------


def test_recovery_enable_declares_the_handoff_contract_and_create_does_not() -> None:
    help_result = invoke_cached_cli(("config", "profile", "recovery", "enable", "--help"))
    assert help_result.exit_code == 0, help_result.output
    assert help_result.output.count("--secrets-stdin") == 1
    assert help_result.output.count("--secrets-fd") == 1
    assert help_result.output.count("--recovery-handoff-fd") == 1
    assert help_result.output.count("--recovery-verification-fd") == 1

    schemas = build_verb_input_schemas(("config.profile.recovery.enable", "config.profile.create"))
    enable = schemas["config.profile.recovery.enable"]
    recovery_parameters = {
        parameter.name: parameter.cli_flag
        for parameter in enable.parameters
        if parameter.name in {"recovery_handoff_fd", "recovery_verification_fd"}
    }
    assert recovery_parameters == {
        "recovery_handoff_fd": "--recovery-handoff-fd",
        "recovery_verification_fd": "--recovery-verification-fd",
    }
    contract = enable.recovery_handoff_contract
    assert contract is not None
    assert contract.required_together is True
    assert contract.json_fields == ("recovery_code",)
    assert contract.maximum_bytes == 8192
    assert contract.reserved_descriptors == (0, 1, 2)
    assert contract.descriptors_must_differ is True
    assert contract.collides_with == ("--secrets-fd",)
    assert contract.handoff_direction == "write"
    assert contract.verification_direction == "read"
    assert schemas["config.profile.create"].recovery_handoff_contract is None


def test_recovery_schema_projects_changed_command_graph_metadata() -> None:
    enable = _command_specs.COMMAND_GRAPH.by_key()["config_profile_recovery_enable"]
    assert enable.recovery_handoff is not None
    changed = replace(enable, recovery_handoff=replace(enable.recovery_handoff, maximum_bytes=4096))

    contract = project_recovery_handoff_contract(changed)

    assert contract is not None
    assert contract.maximum_bytes == 4096


def test_recovery_descriptor_parameters_refuse_missing_or_stale_declaration() -> None:
    enable = _command_specs.COMMAND_GRAPH.by_key()["config_profile_recovery_enable"]
    assert enable.recovery_handoff is not None
    with pytest.raises(ValueError, match="require a recovery handoff spec"):
        replace(enable, recovery_handoff=None)
    with pytest.raises(ValueError, match="references a missing command parameter"):
        replace(enable, recovery_handoff=replace(enable.recovery_handoff, handoff_parameter="stale_handoff_fd"))


@pytest.mark.parametrize(
    ("field", "direction"),
    (("handoff_direction", "read"), ("verification_direction", "write"), ("handoff_direction", "sideways")),
)
def test_recovery_handoff_refuses_invalid_runtime_directions(field: str, direction: str) -> None:
    enable = _command_specs.COMMAND_GRAPH.by_key()["config_profile_recovery_enable"]
    assert enable.recovery_handoff is not None
    with pytest.raises(ValueError, match="directions must be write then read"):
        replace(enable.recovery_handoff, **{field: cast(Any, direction)})


def test_recovery_handoff_refuses_integer_argument_in_place_of_descriptor_option() -> None:
    enable = _command_specs.COMMAND_GRAPH.by_key()["config_profile_recovery_enable"]
    handoff = next(parameter for parameter in enable.parameters if parameter.name == "recovery_handoff_fd")
    argument = ArgumentSpec(
        name=handoff.name,
        value=handoff.value,
        default=handoff.default,
        help_key=handoff.help_key,
    )
    parameters = tuple(argument if parameter is handoff else parameter for parameter in enable.parameters)

    with pytest.raises(ValueError, match="must be command options"):
        replace(enable, parameters=parameters)


def test_archive_import_no_longer_takes_a_recovery_artifact() -> None:
    """The portable artifact is gone; the restore verb proves the passphrase and nothing else."""
    schema = build_verb_input_schemas(("config.profile.archive.import",))["config.profile.archive.import"]
    assert [parameter.name for parameter in schema.parameters] == [
        "label",
        "file",
        "secrets_stdin",
        "secrets_fd",
        "output_language",
    ]
    help_result = invoke_cached_cli(("config", "profile", "archive", "import", "--help"))
    assert help_result.exit_code == 0, help_result.output
    assert "--artifact" not in help_result.output
