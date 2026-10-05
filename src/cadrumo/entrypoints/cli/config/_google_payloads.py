"""Typed ``--json`` payload schemas for Google config CLI commands.

Each class declared here is a strict
:class:`OutputSchema` subclass and is referenced as a deferred public schema
target by production-authored CommandSpec so the
JSON-contract test suite can enumerate every google-config command surface this
module covers. Validated results enter
:class:`SchemaEnvelope` through
:func:`emit_envelope`.

Field sets match the production payload dicts constructed in ``_google.py``,
and ``_google_folder.py`` at their emit sites. All
sequence fields use ``list`` rather than ``tuple`` because
``model_dump(mode='json')`` serialises pydantic tuples as JSON arrays.

The payload classes document only the CLI transport shapes referenced by
production-authored CommandSpec. OAuth state remains
owned by :mod:`google`, Drive mirror state by
:mod:`storage`, and calc-sheets semantics by
:mod:`calc_sheets`.

See Also:
    :mod:`google`
        Google OAuth, status, and Drive mirror emit sites.
    :mod:`_google_folder`
        Drive root-folder configuration emit sites.
"""

from __future__ import annotations

from ....adapters.outbound.storage.records import ProviderKind
from ....core.json_contract import OutputSchema


class GoogleLoginResult(OutputSchema):
    """JSON envelope for ``aeat config google login``.

    Mirrors the
    :class:`OAuthMetadata` returned with an
    :class:`OAuthToken` by
    :func:`run_login_flow`. The refresh token is never exposed.
    """

    operation: str = "config.google.login"
    profile: str
    account_email: str
    granted_scopes: list[str] = []


class GoogleStatusResult(OutputSchema):
    """JSON envelope for ``aeat config google status``.

    Projects the non-secret
    :class:`OAuthMetadata` audit record. A missing
    session is represented with a ``False`` boolean and ``None`` detail
    fields so status remains a read-only inspection surface.
    """

    operation: str = "config.google.status"
    profile: str
    session_present: bool
    account_email: str | None = None
    granted_scopes: list[str] = []
    issued_at: str | None = None


class GoogleLogoutResult(OutputSchema):
    """JSON envelope for ``aeat config google logout``.

    Reports the result of
    :func:`delete_session`: token
    and metadata removal are surfaced separately.
    """

    operation: str = "config.google.logout"
    profile: str
    token_removed: bool
    metadata_removed: bool


# ---------------------------------------------------------------------------
# Drive sync sub-app
# ---------------------------------------------------------------------------


class GoogleSyncProbeResult(OutputSchema):
    """JSON envelope for ``aeat config google probe``.

    Adapts :class:`ProviderProbeReport` from
    the resolved Google Drive :class:`StorageProvider`.
    ``root_folder_id`` is included from the configured provider so operators
    can line up probe health with the selected Drive root.
    """

    operation: str = "config.google.probe"
    profile: str
    provider_kind: ProviderKind
    reachable: bool
    writable: bool
    read_only: bool
    root_folder_present: bool | None = None
    root_folder_id: str
    detail: str = ""
