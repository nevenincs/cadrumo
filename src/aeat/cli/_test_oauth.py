"""Unit tests for the pure parser in :mod:`aeat.cli.oauth`."""

from __future__ import annotations

import pytest

from .oauth import parse_oauth_client_json


@pytest.mark.unit
class TestParseOauthClientJson:
    """Behaviour of ``parse_oauth_client_json``."""

    def test_installed_shape(self) -> None:
        payload = {
            "installed": {
                "client_id": "abc.apps.googleusercontent.com",
                "client_secret": "xyz",
                "redirect_uris": ["http://localhost"],
            }
        }
        assert parse_oauth_client_json(payload) == ("abc.apps.googleusercontent.com", "xyz")

    def test_web_shape_fallback(self) -> None:
        payload = {
            "web": {
                "client_id": "abc",
                "client_secret": "xyz",
            }
        }
        assert parse_oauth_client_json(payload) == ("abc", "xyz")

    def test_missing_block_raises(self) -> None:
        with pytest.raises(ValueError, match="installed/web"):
            parse_oauth_client_json({"other": {}})

    def test_missing_client_id_raises(self) -> None:
        with pytest.raises(ValueError, match="installed/web"):
            parse_oauth_client_json({"installed": {"client_secret": "xyz"}})

    def test_missing_client_secret_raises(self) -> None:
        with pytest.raises(ValueError, match="installed/web"):
            parse_oauth_client_json({"installed": {"client_id": "abc"}})
