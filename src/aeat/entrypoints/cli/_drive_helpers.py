"""Pure helpers for the Google Drive CLI sub-app.

Anything in this module must be unit-testable without touching the
Google Drive API. Helpers that need a live service belong in
:mod:`aeat.entrypoints.cli.drive` directly.

The helpers here cover query-string escaping, MIME-type guessing,
Application Default Credentials (ADC) discovery and identity parsing,
and user-facing share-instruction text used by the Drive ingest flow.
"""

from __future__ import annotations

import mimetypes
from pathlib import Path

from ...core.logging import get_logger

_logger = get_logger(__name__)


def escape_drive_query_literal(value: str) -> str:
    """Escape a string literal for inclusion in a Drive ``q=`` parameter.

    Drive query syntax uses single-quoted strings. Inner single quotes
    must be escaped as ``\\'`` and inner backslashes as ``\\\\``. The
    Google client library does not perform this escaping for callers.

    Args:
        value: Raw string to embed inside a ``'...'`` literal.

    Returns:
        The escaped string, ready to drop into a Drive query expression.
    """
    return value.replace("\\", "\\\\").replace("'", "\\'")


def guess_mime_type(path: Path) -> str:
    """Guess the MIME type for a local file path.

    Falls back to ``application/octet-stream`` for unknown extensions
    so callers can always feed the result into a ``MediaFileUpload``.

    Args:
        path: Path to a local file.

    Returns:
        Best-effort MIME type string.
    """
    guess, _ = mimetypes.guess_type(path.as_posix())
    return guess or "application/octet-stream"


def adc_default_path() -> Path:
    """Return the platform-canonical Application Default Credentials path.

    Mirrors gcloud's resolution rule: ``GOOGLE_APPLICATION_CREDENTIALS`` env
    override (caller's responsibility), else ``%APPDATA%/gcloud/...`` on
    Windows, else ``$HOME/.config/gcloud/...`` everywhere else.

    Returns:
        Filesystem path to the default ADC file location.
    """
    import os
    import sys

    if sys.platform.startswith("win"):
        appdata = os.environ.get("APPDATA")
        if appdata:
            return Path(appdata) / "gcloud" / "application_default_credentials.json"
    return Path.home() / ".config" / "gcloud" / "application_default_credentials.json"


def parse_adc_identity(adc_path: Path) -> dict[str, str | None]:
    """Inspect an ADC JSON file and return a small identity dictionary.

    Pure: no API calls, no I/O beyond reading ``adc_path``. Returns
    ``{"type": "missing"}`` when the file does not exist; never raises.

    Args:
        adc_path: Filesystem path to an Application Default Credentials
            JSON file (typically the result of :func:`adc_default_path`).

    Returns:
        A dictionary with three keys:

        - ``type``: One of ``authorized_user``,
          ``impersonated_service_account``, ``service_account``,
          ``unknown``, or ``missing``.
        - ``email``: For ``service_account`` and
          ``impersonated_service_account``, the service-account email
          parsed from ``client_email`` or the impersonation URL.
          Otherwise :data:`None`.
        - ``impersonates``: Same service-account email when ``type`` is
          ``impersonated_service_account``, else :data:`None`.
    """
    import json
    import re

    if not adc_path.exists():
        return {"type": "missing", "email": None, "impersonates": None}
    try:
        data = json.loads(adc_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        _logger.warning(
            "parse_adc_identity: could not read or parse ADC file %s; returning unknown",
            adc_path,
            exc_info=True,
        )
        return {"type": "unknown", "email": None, "impersonates": None}
    cred_type = str(data.get("type", "unknown"))
    if cred_type == "service_account":
        return {
            "type": cred_type,
            "email": data.get("client_email"),
            "impersonates": None,
        }
    if cred_type == "impersonated_service_account":
        url = str(data.get("service_account_impersonation_url", ""))
        match = re.search(r"/serviceAccounts/([^:]+):generateAccessToken", url)
        sa_email = match.group(1) if match else None
        return {
            "type": cred_type,
            "email": sa_email,
            "impersonates": sa_email,
        }
    if cred_type == "authorized_user":
        return {"type": cred_type, "email": None, "impersonates": None}
    return {"type": "unknown", "email": None, "impersonates": None}


def format_share_instructions(*, file_name: str, identity_email: str | None) -> str:
    """Compose a user-facing share-this-file message.

    The message names the exact Drive filename, the exact identity that
    needs view access, the precise permission level, and a stable URL
    where the share can be performed. When ``identity_email`` is
    :data:`None` (user-mode auth), the share step is unnecessary and
    that fact is stated explicitly.

    Args:
        file_name: Exact Drive file name the operator must locate.
        identity_email: Service-account email that must be granted
            viewer access, or :data:`None` when the active credentials
            are a personal user account.

    Returns:
        Multi-line, copy-paste-ready instruction text.
    """
    if identity_email is None:
        return (
            f"No access-grant needed: the active credential is your own user "
            f"account. If '{file_name}' is in your Drive but not visible, the "
            "ADC token is probably stale — refresh with "
            "`gcloud auth application-default login`."
        )
    return (
        f"To grant access to '{file_name}':\n"
        f"  1. Open https://drive.google.com (the recipe will open it for you).\n"
        f"  2. Locate '{file_name}'.\n"
        f"  3. Right-click → Share → enter exactly:\n"
        f"        {identity_email}\n"
        f"  4. Set permission to 'Viewer' and click 'Send' (no notification needed).\n"
        f"  5. The fetch command keeps polling — it will pick the file up "
        f"within seconds."
    )


def build_name_query(name: str) -> str:
    """Compose a Drive ``q=`` filter for an exact-name lookup.

    Returns a query that matches non-trashed files whose ``name`` field
    equals ``name`` exactly. Used by ``aeat drive fetch`` to locate a
    single file by a stable filename.

    Args:
        name: Exact Drive file name to look up.

    Returns:
        Drive query string.
    """
    return f"name = '{escape_drive_query_literal(name)}' and trashed=false"


def build_listing_query(folder_id: str | None) -> str:
    """Compose a Drive ``q=`` filter for listing inside an optional folder.

    The filter always excludes trashed files. When ``folder_id`` is
    given the filter scopes the listing to direct children of that
    folder; otherwise it lists everything visible to the caller.

    Args:
        folder_id: Drive folder ID to scope the listing to.

    Returns:
        Drive query string.
    """
    if folder_id:
        return f"'{escape_drive_query_literal(folder_id)}' in parents and trashed=false"
    return "trashed=false"
