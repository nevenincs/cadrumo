""":func:`get_storage_provider` factory keyed on :class:`ProviderKind`.

The factory is the single entry point upper layers (sync coordinator,
CLI commands, application services) call to obtain a
:class:`adapters.outbound.storage.StorageProvider` configured for the
active profile. :class:`core.config.Settings` drives the choice:

- ``cadrumo_storage_provider_kind`` selects the backend.
- ``cadrumo_local_storage_root`` chooses the root directory for the local
  backend.
- ``cadrumo_google_drive_root_folder_id`` plus the per-profile persisted
  :class:`~core.GoogleCredentialSourceKind` selection
  (:class:`~adapters.outbound.google.GoogleCredentialSourceSelection`,
  loaded via :mod:`adapters.outbound.google.session_store`) parameterise
  the Drive backend's credentials — either the default per-profile
  :class:`~adapters.outbound.google.OAuthClient` /
  :class:`~adapters.outbound.google.OAuthToken` records, or a
  service-account impersonation grant resolved via
  :func:`~adapters.outbound.google.resolve_impersonated_credentials`.

Composition order:

1. Resolve the active profile via
   :func:`adapters.outbound.google.active_profile.resolve_active_profile`.
2. Read settings via :func:`~core.config.load_settings`.
3. Dispatch on :class:`ProviderKind`. ``LOCAL_FILESYSTEM`` builds a
   :class:`adapters.outbound.storage._local.LocalFileSystemProvider`
   rooted at ``cadrumo_local_storage_root / profile``; ``GOOGLE_DRIVE`` calls
   :func:`build_google_credentials`, which reads the profile's persisted
   :class:`~adapters.outbound.google.GoogleCredentialSourceSelection` (a
   missing selection defaults to
   :attr:`~core.GoogleCredentialSourceKind.OAUTH_DESKTOP`, preserving the
   existing default byte-for-byte) and dispatches to either the
   OAuth-Desktop hydration or
   :func:`~adapters.outbound.google.resolve_impersonated_credentials`, then
   instantiates
   :class:`adapters.outbound.storage._google_drive.GoogleDriveProvider`
   keyed on ``cadrumo_google_drive_root_folder_id``.
4. Refuse unknown kinds with :class:`OutboundStorageValidationError`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from google.auth.credentials import Credentials

from ....application.operator_actions import no_action_precondition_verdict
from ....core import ActionEvidenceProvenance, GoogleCredentialSourceKind, NoRecoveryOutcome
from ....core.config import Settings, load_settings
from ._protocol import StorageProvider
from ._records import ProviderKind
from .errors import OutboundStorageError, OutboundStorageValidationError


def _configuration_validation_verdict(
    condition_id: str,
    *,
    field: str,
    backend: str | None = None,
):
    facts: dict[str, str | bool] = {"field": field, "valid": False}
    if backend is not None:
        facts["backend"] = backend
    return no_action_precondition_verdict(
        condition_id=condition_id,
        facts=facts,
        provenance=ActionEvidenceProvenance.APPLICATION_STATE,
        outcome=NoRecoveryOutcome.OPERATOR_DECISION,
    )


def _parse_kind(raw: str) -> ProviderKind:
    cleaned = raw.strip().lower()
    if not cleaned:
        raise OutboundStorageValidationError(
            "cadrumo_storage_provider_kind is empty",
            context={"value": raw},
            translated_message="adapters.outbound.storage.factory.errors.kind_empty",
            precondition_verdict=_configuration_validation_verdict(
                "storage.factory.provider_kind.valid",
                field="cadrumo_storage_provider_kind",
            ),
        )
    try:
        return ProviderKind(cleaned)
    except ValueError as exc:
        valid = sorted(kind.value for kind in ProviderKind)
        raise OutboundStorageValidationError(
            "cadrumo_storage_provider_kind is not a recognised ProviderKind",
            context={"value": raw, "expected": ", ".join(valid)},
            translated_message="adapters.outbound.storage.factory.errors.kind_unknown",
            precondition_verdict=_configuration_validation_verdict(
                "storage.factory.provider_kind.valid",
                field="cadrumo_storage_provider_kind",
            ),
        ) from exc


def build_google_credentials(*, profile: str) -> Credentials:
    """Resolve Google ``Credentials`` for the profile's chosen credential source.

    Reads the profile's persisted
    :class:`~adapters.outbound.google.GoogleCredentialSourceSelection`
    (:func:`~adapters.outbound.google.load_credential_source_selection`). A
    missing selection defaults to
    :attr:`~core.GoogleCredentialSourceKind.OAUTH_DESKTOP`, so a profile that has
    never opted into service-account impersonation gets byte-for-byte the same
    behaviour as before this dispatch existed.

    - ``OAUTH_DESKTOP`` (the default): hydrates ``Credentials`` from the
      per-profile :class:`~adapters.outbound.google.OAuthClient` and
      :class:`~adapters.outbound.google.OAuthToken` records via
      :func:`_build_oauth_desktop_credentials`.
    - ``SERVICE_ACCOUNT_IMPERSONATION``: delegates to
      :func:`~adapters.outbound.google.resolve_impersonated_credentials`
      with the persisted
      :class:`~adapters.outbound.google.GoogleImpersonationConfig`
      (per ``aeat-architecture-boundaries``: this factory
      never re-implements ADC discovery or impersonation wrapping).

    Imports the upstream Google libraries lazily so unit tests for the
    local backend do not pay the cost.
    """
    from ..google.session_store import load_credential_source_selection

    selection = load_credential_source_selection(profile)
    kind = selection.kind if selection is not None else GoogleCredentialSourceKind.OAUTH_DESKTOP

    if kind is GoogleCredentialSourceKind.SERVICE_ACCOUNT_IMPERSONATION:
        # The selection validator (`GoogleCredentialSourceSelection`)
        # guarantees `impersonation` is populated whenever `kind` is
        # `SERVICE_ACCOUNT_IMPERSONATION`.
        assert selection is not None and selection.impersonation is not None
        from ..google.impersonation import resolve_impersonated_credentials

        return resolve_impersonated_credentials(selection.impersonation)

    return _build_oauth_desktop_credentials(profile=profile)


def _build_oauth_desktop_credentials(*, profile: str) -> Credentials:
    """Hydrate Google ``Credentials`` from the per-profile OAuth records.

    Loads :class:`~adapters.outbound.google.OAuthClient` and
    :class:`~adapters.outbound.google.OAuthToken` through
    :func:`adapters.outbound.google.session_store.load_client` and
    :func:`adapters.outbound.google.session_store.load_token`. Imports the
    upstream library lazily so unit tests for the local backend do not pay the
    cost.
    """
    from ..google.session_store import load_client, load_token

    client = load_client(profile)
    if client is None:
        raise OutboundStorageValidationError(
            "no Google OAuth client registered for this profile",
            context={"profile": profile},
            translated_message="adapters.outbound.storage.factory.errors.google_client_missing",
            precondition_verdict=_configuration_validation_verdict(
                "storage.factory.google_oauth_client.present",
                field="google_oauth_client",
                backend="google_drive",
            ),
        )
    token = load_token(profile)
    if token is None:
        raise OutboundStorageValidationError(
            "no Google OAuth token persisted for this profile",
            context={"profile": profile},
            translated_message="adapters.outbound.storage.factory.errors.google_token_missing",
            precondition_verdict=_configuration_validation_verdict(
                "storage.factory.google_oauth_token.present",
                field="google_oauth_token",
                backend="google_drive",
            ),
        )
    try:
        from google.oauth2.credentials import Credentials
    except ImportError as exc:
        raise OutboundStorageError(
            "google-auth is not importable",
            context={"dependency": "google-auth"},
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
    from ..google.records import REQUIRED_SCOPES

    return REQUIRED_SCOPES


def _resolve_profile() -> str:
    from ..google.active_profile import resolve_active_profile

    return resolve_active_profile()


def resolve_drive_root_folder_id(*, profile: str, settings: Settings) -> str:
    """Resolve the Drive root folder id with the canonical precedence.

    1. ``CADRUMO_GOOGLE_DRIVE_ROOT_FOLDER_ID`` env var / ``.env`` value
       (:class:`core.config.Settings`
       ``cadrumo_google_drive_root_folder_id``; overrides for one-off / CI /
       debugging without persisting state)
    2. Per-profile persisted
       :class:`adapters.outbound.google.DriveConfig` record (canonical
       operator enrolment state)

    Returns the empty string when neither source is configured.
    """
    from ..google.session_store import load_drive_config

    override = str(settings.cadrumo_google_drive_root_folder_id or "").strip()
    if override:
        return override
    config = load_drive_config(profile)
    if config is not None:
        return config.root_folder_id.strip()
    return ""


def get_storage_provider(
    *,
    settings: Settings | None = None,
) -> StorageProvider:
    """Build a :class:`StorageProvider` for the active AEAT profile.

    Args:
        settings: Optional pre-built :class:`core.config.Settings`.
            Defaults to :func:`core.config.load_settings`.

    Returns:
        A concrete :class:`StorageProvider` already wired with credentials and
        root directory or folder ID for the resolved profile.

    Raises:
        :class:`OutboundStorageValidationError`: When the settings value is
            unknown, the Drive backend is selected without
            ``cadrumo_google_drive_root_folder_id``, or the profile lacks the
            records the chosen backend needs.
    """
    settings_resolved = settings if settings is not None else load_settings()
    kind = _parse_kind(settings_resolved.cadrumo_storage_provider_kind)
    profile = _resolve_profile()

    if kind is ProviderKind.LOCAL_FILESYSTEM:
        from ...persistence.storage.bucket import bucket_paths
        from ._local import LocalFileSystemProvider

        root = bucket_paths(settings_resolved.cadrumo_local_storage_root, profile).blobs_dir
        return LocalFileSystemProvider(root)

    if kind is ProviderKind.GOOGLE_DRIVE:
        from ._google_drive import GoogleDriveProvider

        root_folder_id = resolve_drive_root_folder_id(profile=profile, settings=settings_resolved)
        if not root_folder_id:
            raise OutboundStorageValidationError(
                "no Drive root folder id is configured for this profile",
                context={"profile": profile},
                translated_message="adapters.outbound.storage.factory.errors.drive_root_missing",
                precondition_verdict=_configuration_validation_verdict(
                    "storage.factory.google_drive_root_folder_id.present",
                    field="google_drive_root_folder_id",
                    backend="google_drive",
                ),
            )
        credentials = build_google_credentials(profile=profile)
        return GoogleDriveProvider(
            credentials=credentials,
            root_folder_id=root_folder_id,
            vault_folder_name=settings_resolved.cadrumo_google_drive_vault_folder_name,
        )

    # Should never be reached — _parse_kind already refused unknown kinds.
    raise OutboundStorageValidationError(
        "unhandled ProviderKind",
        context={"kind": kind.value},
        translated_message="adapters.outbound.storage.factory.errors.kind_unhandled",
    )


__all__ = ["get_storage_provider"]
