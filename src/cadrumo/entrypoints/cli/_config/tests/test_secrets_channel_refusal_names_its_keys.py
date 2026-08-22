"""A machine-channel secrets refusal names the keys it would have accepted.

``--secrets-stdin`` and ``--secrets-fd`` are the channels a caller with NO
terminal must use, and for this CLI that caller is the ordinary one: an
autonomous agent cannot be prompted. Both refused a malformed payload with
"not a valid JSON object" and stopped there, which tells the one operator who
cannot be prompted nothing it can act on.

The CLI-boundary contract is that a refusal names what it would accept rather
than only what it rejected. The accepted set is the strict model's own declared
fields, so it is read from the model rather than restated -- a restatement is
how the message and the validation drift into disagreeing.

Asserted against the real parser and real strict models, including the negative
direction: naming keys must not become naming a VALUE, on a channel whose whole
purpose is carrying secrets.
"""

from __future__ import annotations

import pytest
from pydantic import BaseModel, ConfigDict, SecretStr

from ..._errors import CliRefusedBoundaryError
from .._secure_input import _validate_secrets_payload

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


class _ProbeSecrets(BaseModel):
    """A strict two-field payload, shaped like the real custody models."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    password: SecretStr
    confirmation: SecretStr


def _refusal_for(payload: str) -> CliRefusedBoundaryError:
    """Put ``payload`` through the real validator and return its refusal.

    Addressed at the validation seam rather than at ``read_secrets_stdin``,
    which reaches ``sys.stdin.buffer`` directly and could only be driven by
    substituting that stream -- monkeypatch machinery this project forbids in a
    deterministic test. Nothing is lost by entering one call lower: the stdin
    reader's own contribution is the size bound, and every refusal asserted
    here (malformed JSON, wrong shape, and the value that must not be echoed)
    is decided inside this function. The refusal keys are the ones the stdin
    channel passes, so the messages under test are the stdin channel's.
    """
    with pytest.raises(CliRefusedBoundaryError) as caught:
        _validate_secrets_payload(
            payload.encode("utf-8"),
            _ProbeSecrets,
            invalid_json_key="cli.config.custody.errors.secrets_stdin_invalid_json",
            missing_fields_key="cli.config.custody.errors.secrets_stdin_missing_fields",
        )
    return caught.value


def test_a_malformed_payload_names_every_accepted_key() -> None:
    """DISCRIMINATING: the refusal an unpromptable caller has to act on."""
    refusal = _refusal_for("this is not json")

    context = refusal.context or {}
    assert context.get("expected_fields") == "password, confirmation"


def test_a_wrong_shaped_object_names_every_accepted_key() -> None:
    """The likelier mistake: valid JSON, wrong keys.

    A caller that sent an object at all needs the key set even more than one
    that sent nothing parseable, because it believes it is close.
    """
    refusal = _refusal_for('{"passphrase": "x"}')

    context = refusal.context or {}
    assert context.get("expected_fields") == "password, confirmation"


def test_the_refusal_never_carries_a_supplied_value() -> None:
    """ANTI-TAUTOLOGY, and the direction that would be a leak.

    Naming the accepted KEYS must not drift into echoing what was SENT. This is
    a secrets channel: a refusal that quoted the payload back would put the
    secret into an error envelope, a log, and whatever the operator pastes.
    """
    # Named for what it is to the code under test -- a payload value that must
    # not survive into any refusal surface -- rather than to a scanner.
    sent_value = "correct-horse-battery-staple"
    refusal = _refusal_for(f'{{"password": "{sent_value}", "surplus": "x"}}')

    assert sent_value not in str(refusal)
    assert sent_value not in repr(refusal.context)
