"""Google OAuth client payload validation contracts."""

import pytest
from pydantic import ValidationError

from ... import OAuthClientPayload
from ..google import _OAuthClientWrapper

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_oauth_client_payload_typeddict_importable() -> None:
    assert hasattr(OAuthClientPayload, "__annotations__")
    assert "installed" in OAuthClientPayload.__required_keys__


def test_oauth_client_wrapper_accepts_valid_desktop_payload() -> None:
    valid = {
        "installed": {
            "client_id": "123-abc.apps.googleusercontent.com",
            "client_secret": "GOCSPX-secret",
            "redirect_uris": ["http://localhost"],
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        },
    }
    wrapper = _OAuthClientWrapper.model_validate(valid)
    assert wrapper.installed["client_id"] == "123-abc.apps.googleusercontent.com"


def test_oauth_client_wrapper_rejects_missing_installed() -> None:
    with pytest.raises(ValidationError):
        _OAuthClientWrapper.model_validate({"web": {"client_id": "456"}})


def test_oauth_client_wrapper_rejects_non_dict_payload() -> None:
    with pytest.raises(ValidationError):
        _OAuthClientWrapper.model_validate("not a dict")
