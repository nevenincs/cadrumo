"""Certificate secret-set conformance with the canonical machine channels."""

from __future__ import annotations

import io
import json
import os
import sys
from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import SecretStr
from pydantic_core import ValidationError

from cadrumo.application import auth as auth_application

from ..._errors import CliRefusedBoundaryError
from ..._machine_secret_contract import registered_machine_secret_payload_models
from .. import _certificate
from .._auth_command_specs import AUTH_COMMAND_SPECS
from .._certificate import _CertificateSecretSetSecrets, certificate_secret_set

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_SUPPLIED_VALUE = "certificate-machine-value-must-not-escape"


def _install_handler_spies(monkeypatch: pytest.MonkeyPatch) -> tuple[list[str], list[dict[str, Any]]]:
    stored: list[str] = []
    emitted: list[dict[str, Any]] = []

    def store(*, name: str, secret: SecretStr) -> SimpleNamespace:
        stored.append(secret.get_secret_value())
        return SimpleNamespace(name=name, has_secret=True, rotated=False)

    monkeypatch.setattr(_certificate, "_activate_subcommand_output_language", lambda *_args: None)
    monkeypatch.setattr(auth_application, "set_operator_certificate_source_secret", store)
    monkeypatch.setattr(_certificate, "_emit_envelope", lambda *_args, **kwargs: emitted.append(kwargs))
    return stored, emitted


def _payload(field: str = "certificate_passphrase") -> bytes:
    return json.dumps({field: _SUPPLIED_VALUE}).encode()


def test_certificate_payload_is_registered_with_the_hard_cut_field() -> None:
    registered = registered_machine_secret_payload_models()

    assert registered["config.auth.certificate.secret.set", "certificate"] is _CertificateSecretSetSecrets
    assert tuple(_CertificateSecretSetSecrets.model_fields) == ("certificate_passphrase",)
    payload = _CertificateSecretSetSecrets(certificate_passphrase=SecretStr("not-a-real-passphrase"))
    assert "not-a-real-passphrase" not in repr(payload)

    with pytest.raises(ValidationError):
        _CertificateSecretSetSecrets.model_validate({"secret": "retired-field"})


def test_certificate_secret_set_declares_the_canonical_channel_pair_once() -> None:
    (spec,) = (row for row in AUTH_COMMAND_SPECS if row.key == "config_auth_certificate_secret_set")
    channel_parameters = [
        (parameter.name, parameter.declarations)
        for parameter in spec.parameters
        if parameter.name in {"secrets_stdin", "secrets_fd"}
    ]

    assert channel_parameters == [
        ("secrets_stdin", ("--secrets-stdin",)),
        ("secrets_fd", ("--secrets-fd",)),
    ]


def test_certificate_handler_routes_stdin_without_rendering_the_passphrase(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stored, emitted = _install_handler_spies(monkeypatch)
    stdin = io.TextIOWrapper(io.BytesIO(_payload()), encoding="utf-8")
    monkeypatch.setattr(sys, "stdin", stdin)

    certificate_secret_set(object(), "operator-cert", secrets_stdin=True)

    assert stored == [_SUPPLIED_VALUE]
    assert len(emitted) == 1
    assert _SUPPLIED_VALUE not in repr(emitted)
    assert emitted[0]["lines"] == ("name\toperator-cert", "rotated\tFalse")


def test_certificate_handler_routes_fd_and_closes_it(monkeypatch: pytest.MonkeyPatch) -> None:
    stored, emitted = _install_handler_spies(monkeypatch)
    reader, writer = os.pipe()
    os.write(writer, _payload())
    os.close(writer)

    certificate_secret_set(object(), "operator-cert", secrets_fd=reader)

    assert stored == [_SUPPLIED_VALUE]
    assert _SUPPLIED_VALUE not in repr(emitted)
    with pytest.raises(OSError):
        os.read(reader, 1)


def test_certificate_handler_refuses_dual_channels_before_read_or_mutation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stored, emitted = _install_handler_spies(monkeypatch)
    reader, writer = os.pipe()
    os.write(writer, _payload())
    os.close(writer)
    try:
        with pytest.raises(CliRefusedBoundaryError) as raised:
            certificate_secret_set(object(), "operator-cert", secrets_stdin=True, secrets_fd=reader)

        assert raised.value.translated_message == "cli.config.custody.errors.secrets_channel_conflict"
        assert os.read(reader, 8192) == _payload()
        assert stored == []
        assert emitted == []
    finally:
        os.close(reader)


def test_certificate_handler_refuses_legacy_field_without_mutation_or_leak(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stored, emitted = _install_handler_spies(monkeypatch)
    stdin = io.TextIOWrapper(io.BytesIO(_payload("secret")), encoding="utf-8")
    monkeypatch.setattr(sys, "stdin", stdin)

    with pytest.raises(CliRefusedBoundaryError) as raised:
        certificate_secret_set(object(), "operator-cert", secrets_stdin=True)

    assert raised.value.translated_message == "cli.config.custody.errors.secrets_stdin_missing_fields"
    assert _SUPPLIED_VALUE not in str(raised.value)
    assert _SUPPLIED_VALUE not in repr(raised.value)
    assert stored == []
    assert emitted == []
