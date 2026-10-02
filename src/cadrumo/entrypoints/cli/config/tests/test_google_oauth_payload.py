"""Contract tests for the canonical protected OAuth client JSON decoder."""

from pathlib import Path

import pytest

from .....adapters.outbound.google.errors import GoogleAuthValidationError
from .....adapters.outbound.google.google_configuration_inputs import decode_google_client_json
from .....core.hashing import sha256_hex

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _desktop_client_json() -> bytes:
    return (
        b'{"installed":{"client_id":"123-abc.apps.googleusercontent.com",'
        b'"client_secret":"synthetic-secret","project_id":"synthetic-project",'
        b'"redirect_uris":["http://localhost"],'
        b'"auth_uri":"https://accounts.google.com/o/oauth2/auth",'
        b'"auth_provider_x509_cert_url":"https://www.googleapis.com/oauth2/v1/certs",'
        b'"token_uri":"https://oauth2.googleapis.com/token"}}'
    )


def test_canonical_decoder_accepts_valid_desktop_payload(tmp_path: Path) -> None:
    encoded = _desktop_client_json()
    client = decode_google_client_json(
        memoryview(encoded),
        source=tmp_path / "desktop-client.json",
        expected_sha256=sha256_hex(encoded),
    )

    assert client.client_id == "123-abc.apps.googleusercontent.com"
    assert client.project_id == "synthetic-project"


def test_canonical_decoder_rejects_non_desktop_payload(tmp_path: Path) -> None:
    encoded = b'{"web":{"client_id":"456"}}'

    with pytest.raises(GoogleAuthValidationError) as caught:
        decode_google_client_json(
            memoryview(encoded),
            source=tmp_path / "web-client.json",
            expected_sha256=sha256_hex(encoded),
        )

    assert caught.value.translated_message == "cli.config.google.detail.client_json_not_desktop"


def test_canonical_decoder_rejects_non_mapping_json(tmp_path: Path) -> None:
    encoded = b'"not a mapping"'

    with pytest.raises(GoogleAuthValidationError) as caught:
        decode_google_client_json(
            memoryview(encoded),
            source=tmp_path / "invalid-client.json",
            expected_sha256=sha256_hex(encoded),
        )

    assert caught.value.translated_message == "cli.config.google.detail.client_json_not_desktop"
