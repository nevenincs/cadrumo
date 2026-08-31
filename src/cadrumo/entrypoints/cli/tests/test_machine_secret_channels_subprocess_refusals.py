"""Refusal matrix for machine-secret subprocess channels."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ._machine_secret_channels_support import (
    _NEW_PROFILE_SECRET,
    _OVERSIZE_SECRET,
    _PROFILE_SECRET,
    _PROMPTS,
    _REFUSAL_SECRET,
    _assert_refused,
    _combined,
    _register,
    _register_certificate_source,
    _restore_material,
    _run,
    _storage_snapshot,
    cleanup_keychain,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


@pytest.fixture(autouse=True)
def _cleanup_keychain(tmp_path: Path) -> None:
    cleanup_keychain(tmp_path)


_FIVE_LEAF_CONFLICT_COMMANDS = (
    ("config", "login", "unread-target"),
    ("config", "profile", "create", "unread-created", "--quiet"),
    ("config", "passphrase", "change"),
    ("config", "profile", "archive", "import", "unread-restored", "--file", "unread-capsule"),
    ("config", "auth", "certificate", "secret", "set", "--name", "unread-certificate"),
)


@pytest.mark.parametrize("command", _FIVE_LEAF_CONFLICT_COMMANDS)
def test_each_leaf_refuses_same_scope_channel_conflict_before_state_or_read(
    tmp_path: Path, command: tuple[str, ...]
) -> None:
    root = tmp_path / "same-scope"
    result = _run(
        root,
        ["--format", "json", *command, "--secrets-stdin", "--secrets-fd", "{fd:0}"],
        stdin=_REFUSAL_SECRET,
        inherited_payloads=(_REFUSAL_SECRET,),
        assert_unread_indices=(0,),
        assert_stdin_unread=True,
    )
    combined = _assert_refused(result, root, before={})
    assert '"status":"error"' in combined
    assert "S14_STDIN_UNREAD" in result.stderr
    assert "S14_DESCRIPTOR_UNREAD" in result.stderr


def test_root_refuses_same_scope_channel_conflict_before_state_or_read(tmp_path: Path) -> None:
    root = tmp_path / "root-same-scope"
    result = _run(
        root,
        [
            "--format",
            "json",
            "--profile-secrets-stdin",
            "--profile-secrets-fd",
            "{fd:0}",
            "config",
            "profile",
            "history",
        ],
        stdin=_REFUSAL_SECRET,
        inherited_payloads=(_REFUSAL_SECRET,),
        assert_unread_indices=(0,),
        assert_stdin_unread=True,
    )
    combined = _assert_refused(result, root, before={})
    assert '"status":"error"' in combined
    assert "S14_STDIN_UNREAD" in result.stderr
    assert "S14_DESCRIPTOR_UNREAD" in result.stderr


@pytest.mark.parametrize("collision", ("two-stdin", "root-fd0", "leaf-fd0", "same-fd"))
def test_cross_scope_collision_refuses_before_read_authentication_or_mutation(tmp_path: Path, collision: str) -> None:
    root = tmp_path / f"cross-scope-{collision}"
    _register(root, label="collision-operator")
    _register_certificate_source(root, name="collision-cert")
    before = _storage_snapshot(root)
    args = ["--format", "json"]
    inherited: tuple[str, ...] = ()
    stdin: str | None = None
    if collision == "two-stdin":
        args.append("--profile-secrets-stdin")
        leaf = ("--secrets-stdin",)
        stdin = _REFUSAL_SECRET
    elif collision == "root-fd0":
        args.extend(("--profile-secrets-fd", "0"))
        leaf = ("--secrets-stdin",)
        stdin = _REFUSAL_SECRET
    elif collision == "leaf-fd0":
        args.append("--profile-secrets-stdin")
        leaf = ("--secrets-fd", "0")
        stdin = _REFUSAL_SECRET
    else:
        args.extend(("--profile-secrets-fd", "{fd:0}"))
        leaf = ("--secrets-fd", "{fd:0}")
        inherited = (_REFUSAL_SECRET,)
    args.extend(
        (
            "config",
            "auth",
            "certificate",
            "secret",
            "set",
            "--name",
            "collision-cert",
            *leaf,
        )
    )
    result = _run(
        root,
        args,
        stdin=stdin,
        inherited_payloads=inherited,
        assert_unread_indices=(0,) if inherited else (),
        assert_stdin_unread=stdin is not None,
    )
    combined = _assert_refused(result, root, before=before)
    assert '"status":"error"' in combined
    if stdin is not None:
        assert "S14_STDIN_UNREAD" in result.stderr
    else:
        assert "S14_DESCRIPTOR_UNREAD" in result.stderr


@pytest.mark.parametrize(
    ("descriptor", "expected"),
    ((-1, "reserved"), (1, "reserved"), (2, "reserved"), (999_999, "Failed to read")),
)
def test_leaf_descriptor_refusals_are_typed_secret_free_and_state_free(
    tmp_path: Path, descriptor: int, expected: str
) -> None:
    root = tmp_path / f"leaf-fd-{descriptor}"
    result = _run(
        root,
        [
            "--format",
            "json",
            "config",
            "profile",
            "create",
            "descriptor-refusal",
            "--quiet",
            "--secrets-fd",
            str(descriptor),
        ],
    )
    assert expected in _assert_refused(result, root, before={})


@pytest.mark.parametrize(
    ("descriptor", "expected"),
    (
        (-1, "cannot be used"),
        (1, "cannot be used"),
        (2, "cannot be used"),
        (999_999, "not an inherited readable"),
    ),
)
def test_root_descriptor_refusals_are_typed_secret_free_and_non_mutating(
    tmp_path: Path, descriptor: int, expected: str
) -> None:
    root = tmp_path / f"root-fd-{descriptor}"
    _register(root, label="root-fd-operator")
    before = _storage_snapshot(root)
    result = _run(
        root,
        [
            "--format",
            "json",
            "--profile-secrets-fd",
            str(descriptor),
            "config",
            "profile",
            "history",
            "root-fd-operator",
        ],
    )
    assert expected in _assert_refused(result, root, before=before)


_MALFORMED_CREATE_PAYLOADS = (
    pytest.param(b"\xff", "invalid", (), id="invalid-utf8"),
    pytest.param(f"{_REFUSAL_SECRET}{{broken", "invalid", (_REFUSAL_SECRET,), id="invalid-json"),
    pytest.param(json.dumps(_REFUSAL_SECRET), "invalid", (_REFUSAL_SECRET,), id="non-object"),
    pytest.param(
        '{"passphrase":"s14-duplicate-first","passphrase":"s14-duplicate-second",'
        '"passphrase_confirmation":"s14-duplicate-second"}',
        "invalid",
        ("s14-duplicate-first", "s14-duplicate-second"),
        id="duplicate-top-level",
    ),
    pytest.param(
        '{"passphrase":"s14-recursive-secret","passphrase_confirmation":"s14-recursive-secret",'
        '"extra":{"nested":"s14-nested-first","nested":"s14-nested-second"}}',
        "invalid",
        ("s14-recursive-secret", "s14-nested-first", "s14-nested-second"),
        id="duplicate-recursive",
    ),
    pytest.param("{}", "fields", (), id="missing-fields"),
    pytest.param(
        '{"passphrase":"s14-extra-secret","passphrase_confirmation":"s14-extra-secret","extra":"s14-forbidden-extra"}',
        "fields",
        ("s14-extra-secret", "s14-forbidden-extra"),
        id="extra-field",
    ),
    pytest.param(
        json.dumps(
            {
                "passphrase": _OVERSIZE_SECRET * 220,
                "passphrase_confirmation": _OVERSIZE_SECRET * 220,
            }
        ),
        "large",
        (_OVERSIZE_SECRET,),
        id="oversize-valid-json",
    ),
    pytest.param("", "invalid", (), id="empty"),
)


@pytest.mark.parametrize(("payload", "diagnostic", "planted_secrets"), _MALFORMED_CREATE_PAYLOADS)
def test_leaf_strict_payload_refusals_close_descriptor_without_mutation(
    tmp_path: Path,
    payload: str | bytes,
    diagnostic: str,
    planted_secrets: tuple[str, ...],
) -> None:
    root = tmp_path / "malformed-leaf"
    result = _run(
        root,
        [
            "--format",
            "json",
            "config",
            "profile",
            "create",
            "malformed-refusal",
            "--quiet",
            "--secrets-fd",
            "{fd:0}",
        ],
        inherited_payloads=(payload,),
        assert_closed_index=0,
    )
    combined = _assert_refused(result, root, before={}, extra_secrets=planted_secrets)
    assert "S13_DESCRIPTOR_CLOSED" in result.stderr
    assert {
        "invalid": "not a valid JSON object",
        "fields": "missing required fields or has unexpected ones",
        "large": "exceeds the maximum allowed size",
    }[diagnostic] in combined


@pytest.mark.parametrize(("payload", "diagnostic", "planted_secrets"), _MALFORMED_CREATE_PAYLOADS)
def test_root_strict_payload_refusals_close_descriptor_without_mutation(
    tmp_path: Path,
    payload: str | bytes,
    diagnostic: str,
    planted_secrets: tuple[str, ...],
) -> None:
    root = tmp_path / "malformed-root"
    _register(root, label="malformed-root-operator")
    before = _storage_snapshot(root)
    result = _run(
        root,
        [
            "--format",
            "json",
            "--profile-secrets-fd",
            "{fd:0}",
            "config",
            "profile",
            "history",
            "malformed-root-operator",
        ],
        inherited_payloads=(payload,),
        assert_closed_index=0,
    )
    combined = _assert_refused(result, root, before=before, extra_secrets=planted_secrets)
    assert "S13_DESCRIPTOR_CLOSED" in result.stderr
    assert {
        "invalid": "one strict UTF-8 JSON object",
        "fields": "contain exactly these fields",
        "large": "exceeds the 8192-byte limit",
    }[diagnostic] in combined


def test_retired_restore_password_field_is_refused_without_publication(tmp_path: Path) -> None:
    capsule, _artifact, _phrase = _restore_material(tmp_path / "legacy-restore-material")
    root = tmp_path / "legacy-restore"
    result = _run(
        root,
        [
            "--format",
            "json",
            "config",
            "profile",
            "archive",
            "import",
            "legacy-restore",
            "--file",
            str(capsule),
            "--secrets-stdin",
        ],
        stdin=json.dumps({"password": _PROFILE_SECRET}),
    )
    assert "unexpected ones" in _assert_refused(result, root, before={})


def test_retired_certificate_secret_field_is_refused_without_mutation(tmp_path: Path) -> None:
    root = tmp_path / "legacy-certificate"
    _register(root, label="legacy-cert-operator")
    _register_certificate_source(root, name="legacy-cert")
    before = _storage_snapshot(root)
    result = _run(
        root,
        [
            "--format",
            "json",
            "--profile-secrets-fd",
            "{fd:0}",
            "config",
            "auth",
            "certificate",
            "secret",
            "set",
            "--name",
            "legacy-cert",
            "--secrets-stdin",
        ],
        stdin=json.dumps({"secret": _REFUSAL_SECRET}),
        inherited_payloads=(json.dumps({"profile_passphrase": _PROFILE_SECRET}),),
        assert_closed_index=0,
    )
    assert "unexpected ones" in _assert_refused(result, root, before=before)


def test_hostile_environment_secret_is_ignored_by_leaf_cli(tmp_path: Path) -> None:
    root = tmp_path / "hostile-environment"
    result = _run(
        root,
        ["--format", "json", "config", "profile", "create", "hostile-env", "--quiet"],
        stdin="",
        hostile_env={"CADRUMO_SECRET_PASSPHRASE": _REFUSAL_SECRET},
    )
    combined = _assert_refused(result, root, before={})
    assert "No passphrase channel is available." in combined


def test_live_session_makes_root_source_unused_and_leaves_it_unread(
    tmp_path: Path,
) -> None:
    root = tmp_path / "live-session-unused"
    _register(root, label="live-session-operator")
    result = _run(
        root,
        [
            "--format",
            "json",
            "--profile-secrets-fd",
            "{fd:0}",
            "config",
            "profile",
            "history",
            "live-session-operator",
        ],
        inherited_payloads=(_REFUSAL_SECRET,),
        preauthenticate_label="live-session-operator",
        assert_dispatch_state_unchanged=True,
        assert_unread_indices=(0,),
    )
    combined = _assert_refused(result, root)
    assert '"status":"error"' in combined
    assert "S14_DESCRIPTOR_UNREAD" in result.stderr
    assert "S14_STATE_UNCHANGED" in result.stderr


@pytest.mark.parametrize(
    ("command", "payload", "consumed", "expected"),
    (
        (
            ("config", "profile", "history", "missing-profile"),
            {"profile_passphrase": _PROFILE_SECRET},
            False,
            "Unknown profile",
        ),
        (
            ("config", "profile", "history", ""),
            {"profile_passphrase": _PROFILE_SECRET},
            False,
            "Unknown profile",
        ),
        (
            ("config", "profile", "history"),
            {"profile_passphrase": _PROFILE_SECRET},
            False,
            "requires an exact profile target",
        ),
        (
            ("config", "profile", "history", "wrong-secret-target"),
            {"profile_passphrase": ""},
            True,
            "The profile password was not accepted.",
        ),
        (
            ("config", "profile", "history", "wrong-nonblank-secret-target"),
            {"profile_passphrase": _REFUSAL_SECRET},
            True,
            "The profile password was not accepted.",
        ),
    ),
    ids=("wrong-target", "blank-target", "no-target", "blank-secret", "wrong-secret"),
)
def test_root_wrong_blank_target_or_secret_refuses_without_secret_disclosure(
    tmp_path: Path,
    command: tuple[str, ...],
    payload: dict[str, str],
    consumed: bool,
    expected: str,
) -> None:
    root = tmp_path / "wrong-blank-root"
    if command[-1] in {"wrong-secret-target", "wrong-nonblank-secret-target"}:
        _register(root, label=command[-1])
    before = _storage_snapshot(root)
    serialized_payload = json.dumps(payload)
    result = _run(
        root,
        ["--format", "json", "--profile-secrets-fd", "{fd:0}", *command],
        inherited_payloads=(serialized_payload,),
        assert_closed_index=0 if consumed else None,
        assert_unread_indices=() if consumed else (0,),
        unread_payload=serialized_payload,
    )
    combined = _assert_refused(result, root, before=before)
    assert ("S13_DESCRIPTOR_CLOSED" if consumed else "S14_DESCRIPTOR_UNREAD") in result.stderr
    if expected:
        assert expected in combined


def test_root_source_is_inapplicable_to_self_authenticating_rotation_and_unread(
    tmp_path: Path,
) -> None:
    root = tmp_path / "self-auth-exemption"
    _register(root, label="self-auth-operator")
    before = _storage_snapshot(root)
    leaf_payload = json.dumps(
        {
            "current_passphrase": _PROFILE_SECRET,
            "new_passphrase": _NEW_PROFILE_SECRET,
            "new_passphrase_confirmation": _NEW_PROFILE_SECRET,
        }
    )
    result = _run(
        root,
        [
            "--format",
            "json",
            "--profile-secrets-fd",
            "{fd:0}",
            "config",
            "passphrase",
            "change",
            "--secrets-stdin",
        ],
        stdin=leaf_payload,
        inherited_payloads=(_REFUSAL_SECRET,),
        assert_unread_indices=(0,),
    )
    combined = _assert_refused(result, root, before=before)
    assert '"status":"error"' in combined
    assert "S14_DESCRIPTOR_UNREAD" in result.stderr


@pytest.mark.parametrize(
    ("command", "expected_code", "expected_diagnostic"),
    (
        (("--help",), 0, "CADRUMO - local-first workflow"),
        (("config", "profile", "history", "--unknown"), 2, "No such option"),
    ),
    ids=("help", "parse-error"),
)
def test_help_and_parse_failures_never_read_root_secret_source(
    tmp_path: Path,
    command: tuple[str, ...],
    expected_code: int,
    expected_diagnostic: str,
) -> None:
    root = tmp_path / "parse-precedence"
    result = _run(
        root,
        ["--profile-secrets-fd", "{fd:0}", *command],
        inherited_payloads=(_REFUSAL_SECRET,),
        assert_unread_indices=(0,),
    )
    combined = _combined(result)
    assert result.returncode == expected_code, combined
    assert expected_diagnostic in combined
    assert "S14_DESCRIPTOR_UNREAD" in result.stderr
    assert not any(prompt in combined.lower() for prompt in _PROMPTS)
    assert _REFUSAL_SECRET not in combined
    assert _storage_snapshot(root) == {}


@pytest.mark.parametrize(
    ("locale", "expected"),
    (
        ("en", "Cannot specify both --secrets-stdin and --secrets-fd."),
        ("es", "No se puede especificar --secrets-stdin y --secrets-fd a la vez."),
        ("ca", "No es pot especificar --secrets-stdin i --secrets-fd alhora."),
        ("hu", "A --secrets-stdin és a --secrets-fd nem adható meg egyszerre."),
    ),
)
def test_four_locale_conflict_snapshots_are_localized_and_secret_free(
    tmp_path: Path, locale: str, expected: str
) -> None:
    root = tmp_path / f"locale-{locale}"
    result = _run(
        root,
        [
            "--format",
            "json",
            "config",
            "profile",
            "create",
            "locale-refusal",
            "--quiet",
            "--secrets-stdin",
            "--secrets-fd",
            "999999",
        ],
        stdin=_REFUSAL_SECRET,
        output_language=locale,
    )
    combined = _assert_refused(result, root, before={})
    assert expected in combined
