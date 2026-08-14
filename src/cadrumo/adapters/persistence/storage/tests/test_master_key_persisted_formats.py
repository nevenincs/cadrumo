"""Master-key persisted-format contracts."""

import json

import pytest
from pydantic import ValidationError

from .. import LOGIN_THROTTLE_FILENAME
from ..master_key import _login_throttle
from ..master_key._master_key_records import _WrappedBucketDekDocument

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]


def test_login_throttle_sidecar_name_is_declared_once() -> None:
    assert _login_throttle.LOGIN_THROTTLE_FILENAME == LOGIN_THROTTLE_FILENAME


def test_wrapped_bucket_dek_refuses_every_direction_of_drift() -> None:
    current = {
        "schema_version": 1,
        "nonce_b64": "AA==",
        "ciphertext_b64": "AA==",
        "tag_b64": "AA==",
    }
    assert _WrappedBucketDekDocument.model_validate_json(json.dumps(current)).schema_version == 1
    for label, payload in (
        ("a version bump", {**current, "schema_version": 2}),
        ("an added field", {**current, "kdf": "argon2id"}),
        ("a removed field", {key: value for key, value in current.items() if key != "tag_b64"}),
    ):
        with pytest.raises(ValidationError):
            _WrappedBucketDekDocument.model_validate_json(json.dumps(payload))
            pytest.fail(f"wrapped bucket DEK accepted {label}")
