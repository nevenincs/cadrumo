"""Synthetic publisher metadata for native build-contract tests."""

from __future__ import annotations

import json

PUBLISHER_CLIENT_JSON = json.dumps(
    {
        "installed": {
            "client_id": "synthetic-native-publisher.apps.googleusercontent.com",
            "client_secret": "synthetic-native-public-client-secret",
            "project_id": "synthetic-native-publisher",
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "redirect_uris": ["http://localhost"],
        }
    }
)
