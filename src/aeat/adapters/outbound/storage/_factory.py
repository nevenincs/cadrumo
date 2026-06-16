"""`get_storage_provider` factory keyed on `ProviderKind`.

The factory is the single entry point upper layers (sync coordinator,
CLI commands, application services) call to obtain a `StorageProvider`
configured for the active profile. Settings drive the choice:

- `aeat_storage_provider_kind` selects the backend.
- `aeat_local_storage_root` chooses the root directory for the local
  backend.
- `aeat_google_drive_root_folder_id` + the per-profile OAuth client +
  token (loaded via `aeat.adapters.outbound.google._session_store`)
  parameterise the Drive backend.

Composition order:

1. Resolve the active profile via `_active_profile.resolve_active_profile`.
2. Read settings via `load_settings()`.
3. Dispatch on `ProviderKind`. ``LOCAL_FILESYSTEM`` builds a
   ``LocalFileSystemProvider`` rooted at ``aeat_local_storage_root / profile``;
   ``GOOGLE_DRIVE`` loads the per-profile ``oauth-client`` and ``oauth-token``,
   builds ``Credentials``, and instantiates a ``GoogleDriveProvider`` keyed on
   ``aeat_google_drive_root_folder_id``.
4. Refuse unknown kinds with `OutboundStorageValidationError`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from google.oauth2.credentials import Credentials

from ....core.config import Settings, load_settings
from ._errors import OutboundStorageError, OutboundStorageValidationError
from ._protocol import StorageProvider
from ._records import ProviderKind


def _parse_kind(raw: str) -> ProviderKind:
    cleaned = raw.strip().lower()
    if not cleaned:
        raise OutboundStorageValidationError(
            "aeat_storage_provider_kind is empty",
            context={"value": raw},
            translated_message="adapters.outbound.storage.factory.errors.kind_empty",
        )
    try:
        return ProviderKind(cleaned)
    except ValueError as exc:
        valid = sorted(kind.value for kind in ProviderKind)
        raise OutboundStorageValidationError(
            "aeat_storage_provider_kind is not a recognised ProviderKind",
            context={"value": raw, "expected": ", ".join(valid)},
            translated_message="adapters.outbound.storage.factory.errors.kind_unknown",
        ) from exc


def _build_google_credentials(*, profile: str) -> Credentials:
    """Hydrate `google.oauth2.credentials.Credentials` from the per-profile records.

    Imports the upstream library lazily so unit tests for the local /
    in-memory backends do not pay the cost.
    """
    from ..google._session_store import load_client, load_token

    client = load_client(profile)
    if client is None:
        raise OutboundStorageValidationError(
            "no Google OAuth client registered for this profile",
            context={"profile": profile},
            suggestion="aeat config google register --client-json <path>",
            translated_message="adapters.outbound.storage.factory.errors.google_client_missing",
        )
    token = load_token(profile)
    if token is None:
        raise OutboundStorageValidationError(
            "no Google OAuth token persisted for this profile",
            context={"profile": profile},
            suggestion="aeat config google login",
            translated_message="adapters.outbound.storage.factory.errors.google_token_missing",
        )
    try:
        from google.oauth2.credentials import Credentials
    except ImportError as exc:
        raise OutboundStorageError(
            "google-auth is not importable",
            context={"dependency": "google-auth"},
            suggestion="pip install aeat[google]",
            translated_message="adapters.outbound.storage.factory.errors.google_auth_import_failed",
        ) from exc
    return Credentials(
        token=None,  # access token is rebuilt by first refresh
        refresh_token=token.refresh_token,
        token_uri=token.token_uri,
        client_id=client.client_id,
        client_secret=client.client_secret,
        scopes=list(_required_scopes()),
    )


def _required_scopes() -> tuple[str, ...]:
    from ..google._records import REQUIRED_SCOPES

    return REQUIRED_SCOPES


def _resolve_profile() -> str:
    from ..google._active_profile import resolve_active_profile

    return resolve_active_profile()


def _resolve_drive_root_folder_id(*, profile: str, settings: Settings) -> str:
    """Resolve the Drive root folder id with the canonical precedence.

    1. `AEAT_GOOGLE_DRIVE_ROOT_FOLDER_ID` env var / `.env` value
       (Settings.aeat_google_drive_root_folder_id; overrides for
       one-off / CI / debugging without persisting state)
    2. Per-profile persisted `DriveConfig` record (canonical operator
       enrolment via `aeat config google folder set <id>`)

    Returns the empty string when neither source is configured.
    """
    from ..google._session_store import load_drive_config

    if settings.aeat_google_drive_root_folder_id:
        return str(settings.aeat_google_drive_root_folder_id).strip()
    config = load_drive_config(profile)
    if config is not None:
        return config.root_folder_id.strip()
    return ""


def get_storage_provider(
    *,
    settings: Settings | None = None,
) -> StorageProvider:
    """Build a `StorageProvider` for the active AEAT profile.

    Args:
        settings: Optional pre-built `Settings`. Defaults to
            `load_settings()`.

    Returns:
        A concrete :class:`StorageProvider` already wired with credentials and
        root directory or folder ID for the resolved profile.

    Raises:
        OutboundStorageValidationError: When the settings value is unknown, the
            Drive backend is selected without `aeat_google_drive_root_folder_id`,
            or the profile lacks the records the chosen backend needs.
    """
    settings_resolved = settings if settings is not None else load_settings()
    kind = _parse_kind(settings_resolved.aeat_storage_provider_kind)
    profile = _resolve_profile()

    if kind is ProviderKind.LOCAL_FILESYSTEM:
        from ...persistence.storage.bucket import bucket_paths
        from ._local import LocalFileSystemProvider

        root = bucket_paths(settings_resolved.aeat_local_storage_root, profile).blobs_dir
        return LocalFileSystemProvider(root)

    if kind is ProviderKind.GOOGLE_DRIVE:
        from ._google_drive import GoogleDriveProvider

        root_folder_id = _resolve_drive_root_folder_id(profile=profile, settings=settings_resolved)
        if not root_folder_id:
            raise OutboundStorageValidationError(
                "no Drive root folder id is configured for this profile",
                context={"profile": profile},
                suggestion="aeat config google folder set <id>",
                translated_message="adapters.outbound.storage.factory.errors.drive_root_missing",
            )
        credentials = _build_google_credentials(profile=profile)
        return GoogleDriveProvider(
            credentials=credentials,
            root_folder_id=root_folder_id,
            vault_folder_name=settings_resolved.aeat_google_drive_vault_folder_name,
        )

    # Should never be reached — _parse_kind already refused unknown kinds.
    raise OutboundStorageValidationError(
        "unhandled ProviderKind",
        context={"kind": kind.value},
        translated_message="adapters.outbound.storage.factory.errors.kind_unhandled",
    )


__all__ = ["get_storage_provider"]
