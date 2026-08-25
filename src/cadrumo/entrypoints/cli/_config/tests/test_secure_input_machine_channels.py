"""Contract tests for the canonical scalar-secret machine channels."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from typing import cast

import pytest
from pydantic import BaseModel, SecretStr, ValidationError

from ...errors import CliRefusedBoundaryError
from .._secure_input import (
    _MAX_SECRETS_BYTES,
    MachineSecretChannel,
    MachineSecretPayload,
    MachineSecretSelection,
    _validate_secrets_payload,
    read_machine_secret_payload,
    select_machine_secret_channel,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_SUPPLIED_VALUE = "machine-channel-value-must-never-escape"


class _ProbeSecrets(MachineSecretPayload):
    """A representative command-owned strict payload."""

    passphrase: SecretStr
    passphrase_confirmation: SecretStr


def _payload(*, secret: str = _SUPPLIED_VALUE) -> bytes:
    return ('{"passphrase":"' + secret + '","passphrase_confirmation":"' + secret + '"}').encode()


def _pipe_with(payload: bytes) -> int:
    """Return a real readable descriptor whose writer has reached EOF."""
    reader, writer = os.pipe()
    try:
        os.write(writer, payload)
    finally:
        os.close(writer)
    return reader


def _file_with(payload: bytes) -> int:
    """Return an independent descriptor over real temporary storage."""
    with tempfile.TemporaryFile() as stream:
        stream.write(payload)
        stream.flush()
        stream.seek(0)
        return os.dup(stream.fileno())


def _assert_closed(descriptor: int) -> None:
    with pytest.raises(OSError):
        os.fstat(descriptor)


@contextmanager
def _stdin_from(payload: bytes) -> Iterator[None]:
    """Temporarily bind fd 0 to a real bounded source without replacing streams."""
    original_stdin = os.dup(0)
    reader = _file_with(payload)
    try:
        os.dup2(reader, 0)
        os.close(reader)
        yield
    finally:
        os.dup2(original_stdin, 0)
        os.close(original_stdin)


def _validation_refusal(raw: bytes) -> CliRefusedBoundaryError:
    with pytest.raises(CliRefusedBoundaryError) as caught:
        _validate_secrets_payload(
            raw,
            _ProbeSecrets,
            invalid_json_key="cli.config.custody.errors.secrets_stdin_invalid_json",
            missing_fields_key="cli.config.custody.errors.secrets_stdin_missing_fields",
        )
    return caught.value


def test_payload_base_is_strict_and_frozen() -> None:
    payload = _ProbeSecrets(
        passphrase=SecretStr("first"),
        passphrase_confirmation=SecretStr("second"),
    )
    with pytest.raises(ValidationError):
        _ProbeSecrets.model_validate(
            {
                "passphrase": "first",
                "passphrase_confirmation": "second",
                "surplus": "refuse-me",
            },
        )
    with pytest.raises(ValidationError):
        payload.__setattr__("passphrase", SecretStr("replacement"))


def test_selector_represents_absence_and_each_channel_without_reading() -> None:
    descriptor = _pipe_with(_payload())
    try:
        assert select_machine_secret_channel(secrets_stdin=False, secrets_fd=None) is None
        assert select_machine_secret_channel(
            secrets_stdin=True,
            secrets_fd=None,
        ) == MachineSecretSelection(MachineSecretChannel.STDIN)
        assert select_machine_secret_channel(
            secrets_stdin=False,
            secrets_fd=descriptor,
        ) == MachineSecretSelection(MachineSecretChannel.FILE_DESCRIPTOR, descriptor)
        os.fstat(descriptor)
    finally:
        os.close(descriptor)


def test_selection_rejects_an_unknown_runtime_channel_before_reading() -> None:
    descriptor = _pipe_with(_payload())
    try:
        with pytest.raises(TypeError, match="known channel"):
            MachineSecretSelection(cast(MachineSecretChannel, "unknown"), descriptor)
        assert os.read(descriptor, _MAX_SECRETS_BYTES) == _payload()
    finally:
        os.close(descriptor)


def test_channel_conflict_refuses_before_reading_either_source() -> None:
    descriptor = _pipe_with(_payload())
    try:
        with pytest.raises(CliRefusedBoundaryError) as caught:
            select_machine_secret_channel(secrets_stdin=True, secrets_fd=descriptor)
        assert caught.value.translated_message == "cli.config.custody.errors.secrets_channel_conflict"
        assert os.read(descriptor, _MAX_SECRETS_BYTES) == _payload()
    finally:
        os.close(descriptor)


@pytest.mark.parametrize(
    "raw",
    [
        b"\xff",
        b"not-json",
        b"[]",
        b'{"passphrase":"first","passphrase":"second","passphrase_confirmation":"third"}',
        b'{"passphrase":"first","passphrase_confirmation":{"nested":"one","nested":"two"}}',
    ],
    ids=["invalid-utf8", "invalid-json", "non-object", "top-level-duplicate", "recursive-duplicate"],
)
def test_parser_refuses_invalid_encoding_json_shape_and_duplicates(raw: bytes) -> None:
    refusal = _validation_refusal(raw)
    assert refusal.translated_message == "cli.config.custody.errors.secrets_stdin_invalid_json"
    assert _SUPPLIED_VALUE not in str(refusal)
    assert _SUPPLIED_VALUE not in repr(refusal.context)


@pytest.mark.parametrize(
    "raw",
    [
        b'{"passphrase":"only"}',
        b'{"passphrase":"first","passphrase_confirmation":"second","surplus":"third"}',
    ],
    ids=["missing", "extra"],
)
def test_parser_refuses_missing_and_extra_fields_without_values(raw: bytes) -> None:
    refusal = _validation_refusal(raw)
    assert refusal.translated_message == "cli.config.custody.errors.secrets_stdin_missing_fields"
    assert refusal.context == {"expected_fields": "passphrase, passphrase_confirmation"}
    for supplied_value in ("only", "first", "second", "third"):
        assert supplied_value not in str(refusal)
        assert supplied_value not in repr(refusal.context)


def _run_stdin_reader(payload: bytes) -> subprocess.CompletedProcess[bytes]:
    code = """
from pydantic import SecretStr
from cadrumo.entrypoints.cli._config._secure_input import (
    MachineSecretPayload,
    read_machine_secret_payload,
    select_machine_secret_channel,
)
from cadrumo.entrypoints.cli.errors import CliRefusedBoundaryError
class Payload(MachineSecretPayload):
    passphrase: SecretStr
    passphrase_confirmation: SecretStr
try:
    selection = select_machine_secret_channel(secrets_stdin=True, secrets_fd=None)
    assert selection is not None
    read_machine_secret_payload(Payload, selection=selection)
except CliRefusedBoundaryError as exc:
    print(exc.translated_message)
else:
    print("accepted")
"""
    return subprocess.run(  # noqa: S603 - fixed interpreter/code; payload travels only on stdin.
        [sys.executable, "-c", code],
        input=payload,
        capture_output=True,
        check=False,
    )


def test_stdin_reader_accepts_the_bound_channel() -> None:
    result = _run_stdin_reader(_payload())
    assert result.returncode == 0, result.stderr.decode(errors="replace")
    assert result.stdout.strip() == b"accepted"
    assert _SUPPLIED_VALUE.encode() not in result.stdout
    assert _SUPPLIED_VALUE.encode() not in result.stderr


def test_stdin_reader_refuses_payload_above_the_bound_without_leaking_it() -> None:
    oversized = _SUPPLIED_VALUE.encode() + b"x" * _MAX_SECRETS_BYTES
    result = _run_stdin_reader(oversized)
    assert result.returncode == 0, result.stderr.decode(errors="replace")
    assert result.stdout.strip() == b"cli.config.custody.errors.secrets_stdin_too_large"
    assert _SUPPLIED_VALUE.encode() not in result.stdout
    assert _SUPPLIED_VALUE.encode() not in result.stderr


def test_fd_reader_accepts_fd_zero_and_closes_it() -> None:
    with _stdin_from(_payload()):
        parsed = _read_selected_fd(0)
        assert parsed.passphrase.get_secret_value() == _SUPPLIED_VALUE
        _assert_closed(0)


@pytest.mark.parametrize("descriptor", [-1, 1, 2])
def test_fd_reader_refuses_negative_and_output_descriptors_without_closing_outputs(descriptor: int) -> None:
    with pytest.raises(CliRefusedBoundaryError) as caught:
        _read_selected_fd(descriptor)
    assert caught.value.translated_message == "cli.config.custody.errors.secrets_fd_reserved_stream"
    if descriptor >= 0:
        os.fstat(descriptor)


def test_fd_reader_refuses_an_unreadable_descriptor() -> None:
    reader = _pipe_with(_payload())
    os.close(reader)
    with pytest.raises(CliRefusedBoundaryError) as caught:
        _read_selected_fd(reader)
    assert caught.value.translated_message == "cli.config.custody.errors.secrets_fd_unreadable"
    assert caught.value.context == {"descriptor": str(reader)}


def test_fd_reader_closes_after_success_and_second_read_refuses() -> None:
    descriptor = _pipe_with(_payload())
    parsed = _read_selected_fd(descriptor)
    assert parsed.passphrase.get_secret_value() == _SUPPLIED_VALUE
    _assert_closed(descriptor)

    with pytest.raises(CliRefusedBoundaryError) as caught:
        _read_selected_fd(descriptor)
    assert caught.value.translated_message == "cli.config.custody.errors.secrets_fd_unreadable"


@pytest.mark.parametrize("raw", [b"not-json", b"x" * (_MAX_SECRETS_BYTES + 1)])
def test_fd_reader_closes_after_every_payload_refusal(raw: bytes) -> None:
    descriptor = _file_with(raw)
    with pytest.raises(CliRefusedBoundaryError) as caught:
        _read_selected_fd(descriptor)
    _assert_closed(descriptor)
    assert _SUPPLIED_VALUE not in str(caught.value)
    assert _SUPPLIED_VALUE not in repr(caught.value.context)


def test_selected_reader_materialises_exactly_the_selected_descriptor() -> None:
    descriptor = _pipe_with(_payload())
    selection = select_machine_secret_channel(secrets_stdin=False, secrets_fd=descriptor)
    assert selection is not None
    parsed = read_machine_secret_payload(_ProbeSecrets, selection=selection)
    assert parsed.passphrase.get_secret_value() == _SUPPLIED_VALUE
    _assert_closed(descriptor)


def _read_selected_fd(descriptor: int) -> _ProbeSecrets:
    """Drive descriptor behavior through the sole canonical public reader."""
    selection = select_machine_secret_channel(secrets_stdin=False, secrets_fd=descriptor)
    assert selection is not None
    return read_machine_secret_payload(_ProbeSecrets, selection=selection)


def test_selected_reader_rejects_a_model_outside_the_strict_frozen_base_before_reading() -> None:
    class _PermissivePayload(BaseModel):
        passphrase: SecretStr

    raw = b'{"passphrase":"value","surplus":"would-be-accepted"}'
    descriptor = _pipe_with(raw)
    selection = MachineSecretSelection(MachineSecretChannel.FILE_DESCRIPTOR, descriptor)
    try:
        with pytest.raises(TypeError, match="must inherit MachineSecretPayload"):
            read_machine_secret_payload(
                _PermissivePayload,  # type: ignore[type-var]  # ty: ignore[invalid-argument-type]  # reason: passing a permissive model is the refusal under test
                selection=selection,
            )
        assert os.read(descriptor, _MAX_SECRETS_BYTES) == raw
    finally:
        os.close(descriptor)
