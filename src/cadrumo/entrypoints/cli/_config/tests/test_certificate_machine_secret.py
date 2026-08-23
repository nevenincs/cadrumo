"""Certificate secret-set conformance with the canonical machine channels."""

from __future__ import annotations

import pytest
from pydantic import SecretStr
from pydantic_core import ValidationError

from ..._command_spec import OptionSpec
from .._auth_command_specs import AUTH_COMMAND_SPECS
from .._certificate import CertificateSecretSetSecrets

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_certificate_payload_exposes_the_hard_cut_field() -> None:
    assert tuple(CertificateSecretSetSecrets.model_fields) == ("certificate_passphrase",)
    payload = CertificateSecretSetSecrets(certificate_passphrase=SecretStr("not-a-real-passphrase"))
    assert "not-a-real-passphrase" not in repr(payload)

    with pytest.raises(ValidationError):
        CertificateSecretSetSecrets.model_validate({"secret": "retired-field"})


def test_certificate_secret_set_declares_the_canonical_channel_pair_once() -> None:
    (spec,) = (row for row in AUTH_COMMAND_SPECS if row.key == "config_auth_certificate_secret_set")
    channel_parameters = [
        (parameter.name, parameter.declarations)
        for parameter in spec.parameters
        if isinstance(parameter, OptionSpec) and parameter.name in {"secrets_stdin", "secrets_fd"}
    ]

    assert channel_parameters == [
        ("secrets_stdin", ("--secrets-stdin",)),
        ("secrets_fd", ("--secrets-fd",)),
    ]
