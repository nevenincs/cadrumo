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

1. Resolve the active profile via `_profile_binding.resolve_active_profile`.
2. Read settings via `load_settings()`.
3. Dispatch on `ProviderKind`:
   - `LOCAL_FILESYSTEM` → `LocalFileSystemProvider(root=settings.aeat_local_storage_root / profile)`
   - `GOOGLE_DRIVE` → loads `oauth-client` + `oauth-token` for profile, builds `Credentials`,
     instantiates `GoogleDriveProvider(credentials=..., root_folder_id=settings.aeat_google_drive_root_folder_id)`.
4. Refuse unknown kinds with `StorageValidationError`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from google.oauth2.credentials import Credentials

from ....core.config import Settings, load_settings
from ._errors import StorageError, StorageValidationError
from ._google_drive import GoogleDriveProvider
from ._local import LocalFileSystemProvider
from ._protocol import StorageProvider
from ._records import ProviderKind


def _parse_kind(raw: str) -> ProviderKind:
    cleaned = raw.strip().lower()
    if not cleaned:
        raise StorageValidationError(
            "aeat_storage_provider_kind is empty",
            context={"value": raw},
        )
    try:
        return ProviderKind(cleaned)
    except ValueError as exc:
        valid = sorted(kind.value for kind in ProviderKind)
        raise StorageValidationError(
            f"aeat_storage_provider_kind={raw!r} is not a recognised ProviderKind; expected one of {valid!r}",
            context={"value": raw, "expected": valid},
        ) from exc


def _build_google_credentials(*, profile: str) -> Credentials:
    """Hydrate `google.oauth2.credentials.Credentials` from the per-profile records.

    Imports the upstream library lazily so unit tests for the local /
    in-memory backends do not pay the cost.
    """

    from ..google._session_store import load_client, load_token

    client = load_client(profile)
    if client is None:
        raise StorageValidationError(
            f"no Google OAuth client registered for profile {profile!r}; "
            "run `aeat config google register --client-json <path>` first",
            context={"profile": profile},
        )
    token = load_token(profile)
    if token is None:
        raise StorageValidationError(
            f"no Google OAuth token persisted for profile {profile!r}; run `aeat config google login` first",
            context={"profile": profile},
        )
    try:
        from google.oauth2.credentials import Credentials
    except ImportError as exc:
        raise StorageError(
            f"google-auth not importable: {exc}",
            suggestion="uv sync",
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
    from ..google._profile_binding import resolve_active_profile

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
        A concrete `StorageProvider` already wired with credentials +
        root directory / folder ID for the resolved profile.

    Raises:
        StorageValidationError: When the settings value is unknown, the
            Drive backend is selected without `aeat_google_drive_root_folder_id`,
            or the profile lacks the records the chosen backend needs.
        GoogleAuthProfileUnboundError: When no profile is bound.
    """

    settings_resolved = settings if settings is not None else load_settings()
    kind = _parse_kind(settings_resolved.aeat_storage_provider_kind)
    profile = _resolve_profile()

    if kind is ProviderKind.LOCAL_FILESYSTEM:
        root = settings_resolved.aeat_local_storage_root / profile
        return LocalFileSystemProvider(root)

    if kind is ProviderKind.GOOGLE_DRIVE:
        root_folder_id = _resolve_drive_root_folder_id(profile=profile, settings=settings_resolved)
        if not root_folder_id:
            raise StorageValidationError(
                "no Drive root folder id is configured for this profile; "
                "set it via `aeat config google folder set <id>` "
                "(or the AEAT_GOOGLE_DRIVE_ROOT_FOLDER_ID env var for one-off runs)",
                context={"profile": profile},
            )
        credentials = _build_google_credentials(profile=profile)
        return GoogleDriveProvider(credentials=credentials, root_folder_id=root_folder_id)

    # Should never be reached — _parse_kind already refused unknown kinds.
    raise StorageValidationError(
        f"unhandled ProviderKind {kind!r}",
        context={"kind": kind.value},
    )


__all__ = ["get_storage_provider"]
