"""Read-through secret-store adapter for legacy plaintext credential files.

Wave-1 of the secure-persistence-foundation feature shipped the
substrate; this module is the bridge that consumer code (Google
OAuth, AEAT certificate auth, MCP credentials, OAuth token cache,
operator profile) calls instead of reading the legacy plaintext file
directly.

Every consumer migration follows the same shape:

1. The reader (``load_secret_or_legacy``) tries
   :meth:`SecretStore.get` first. On hit, returns the parsed value.
2. On :class:`SecretNotFoundError`, the reader falls back to the
   legacy file path. If the file exists, it reads it and emits a
   one-shot deprecation log so the operator knows to migrate.
3. The migration helper (``migrate_legacy_to_secret_store``) reads
   the legacy file, writes the secret store under the canonical
   natural key, and (optionally) deletes the legacy file. Operators
   typically run this once per credential during the upgrade.

Consumers wrap these primitives behind named helpers
(``load_google_oauth_client``, ``migrate_google_oauth_client_to_secret_store``
and so on); the named helpers pin the natural key, the
classification, and the expiry policy per credential class.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path

from ..logging import get_logger
from ..storage import (
    SecretRecord,
    SensitivityClass,
    get_secret_store,
)
from ..storage.errors import SecretNotFoundError

_log = get_logger(__name__)
_deprecation_warned: set[str] = set()
_DEFAULT_SECRET_TTL_DAYS = 90


# Canonical natural keys for the Wave-2 consumer migrations.
KEY_GOOGLE_OAUTH_CLIENT = "aeat:google:oauth-client"
KEY_GOOGLE_SERVICE_ACCOUNT = "aeat:google:service-account"
KEY_GOOGLE_OAUTH_TOKEN_PREFIX = "aeat:google:oauth-token"  # noqa: S105 — natural-key namespace, not a password
"""Token cache uses ``KEY_GOOGLE_OAUTH_TOKEN_PREFIX:<account>`` so multi-account future support slots in cleanly."""

KEY_MCP_WORKSPACE_CREDENTIALS = "aeat:mcp:workspace-credentials"
KEY_OPERATOR_PROFILE = "aeat:operator:profile"


def google_oauth_token_key(account: str) -> str:
    """Return the canonical natural key for one account's OAuth token cache."""
    return f"{KEY_GOOGLE_OAUTH_TOKEN_PREFIX}:{account}"


def _emit_deprecation(legacy_path: Path) -> None:
    path_key = str(legacy_path.resolve())
    if path_key in _deprecation_warned:
        return
    _deprecation_warned.add(path_key)
    _log.info(
        "DEPRECATION: read-through fallback to legacy plaintext credential at %s. "
        "Run the matching migration helper (e.g. aeat secrets put / migrate_*) to move "
        "this credential into the secret store.",
        legacy_path,
    )


def load_secret_or_legacy[T](
    *,
    key: str,
    legacy_path: Path,
    parser: Callable[[bytes], T],
) -> T:
    """Read-through helper: prefer the secret store; fall back to the legacy file.

    Args:
        key: Canonical natural key in the secret store.
        legacy_path: Path to the legacy plaintext credential file.
        parser: Callable that converts the secret bytes into the
            consumer-shaped value (e.g. ``json.loads`` for OAuth-client
            JSON; ``bytes`` for raw token blobs).

    Returns:
        The parsed value.

    Raises:
        SecretNotFoundError: If the secret store has no record AND the
            legacy file does not exist.
        Exception: Any error raised by ``parser`` propagates unchanged.
    """
    store = get_secret_store()
    try:
        record = store.get(key)
        return parser(record.value)
    except SecretNotFoundError:
        if not legacy_path.exists():
            raise
        _emit_deprecation(legacy_path)
        return parser(legacy_path.read_bytes())


def migrate_legacy_to_secret_store(
    *,
    key: str,
    legacy_path: Path,
    classification: SensitivityClass = SensitivityClass.SECRET,
    expires_in_days: int = _DEFAULT_SECRET_TTL_DAYS,
    delete_legacy: bool = False,
    overwrite: bool = False,
) -> None:
    """Move a legacy plaintext credential file into the secret store.

    Args:
        key: Canonical natural key.
        legacy_path: Path to the legacy plaintext file.
        classification: SECRET or SESSION; defaults to SECRET.
        expires_in_days: TTL applied to the new record. Defaults to 90.
        delete_legacy: When ``True``, unlinks the legacy file after a
            successful write. Defaults to ``False`` so the operator
            can keep the file readable until they have verified the
            migration worked.
        overwrite: When ``True``, replaces an existing secret-store
            record at ``key``. Defaults to ``False`` so a duplicate
            migration is not silently destructive.

    Raises:
        FileNotFoundError: If ``legacy_path`` does not exist.
        SecretAlreadyExistsError: If the key is already taken and
            ``overwrite=False``.
    """
    if not legacy_path.exists():
        raise FileNotFoundError(legacy_path)
    payload = legacy_path.read_bytes()
    expires_at = datetime.now(UTC) + timedelta(days=expires_in_days)
    record = SecretRecord(
        key=key,
        value=payload,
        classification=classification,
        created_at=datetime.now(UTC),
        expires_at=expires_at,
        metadata={"migrated_from": str(legacy_path)},
    )
    store = get_secret_store()
    store.put(record, overwrite=overwrite)
    _log.info(
        "migrated legacy credential %s into secret store under key %r (classification=%s, expires_at=%s)",
        legacy_path,
        key,
        classification.value,
        expires_at.isoformat(),
    )
    if delete_legacy:
        legacy_path.unlink()
        _log.info("removed legacy plaintext file at %s", legacy_path)


# ── Per-consumer named helpers ──────────────────────────────────────


def load_google_oauth_client(legacy_path: Path) -> dict[str, object]:
    """Read the Google OAuth client credentials, secret-store-first."""
    return load_secret_or_legacy(
        key=KEY_GOOGLE_OAUTH_CLIENT,
        legacy_path=legacy_path,
        parser=lambda data: json.loads(data.decode("utf-8")),
    )


def migrate_google_oauth_client_to_secret_store(
    legacy_path: Path,
    *,
    delete_legacy: bool = False,
) -> None:
    """Move ``env/oauth-client.json`` into the secret store under the canonical key."""
    migrate_legacy_to_secret_store(
        key=KEY_GOOGLE_OAUTH_CLIENT,
        legacy_path=legacy_path,
        classification=SensitivityClass.SECRET,
        delete_legacy=delete_legacy,
    )


def load_google_service_account(legacy_path: Path) -> dict[str, object]:
    """Read the Google service-account JSON, secret-store-first."""
    return load_secret_or_legacy(
        key=KEY_GOOGLE_SERVICE_ACCOUNT,
        legacy_path=legacy_path,
        parser=lambda data: json.loads(data.decode("utf-8")),
    )


def migrate_google_service_account_to_secret_store(
    legacy_path: Path,
    *,
    delete_legacy: bool = False,
) -> None:
    """Move ``env/service-account.json`` into the secret store."""
    migrate_legacy_to_secret_store(
        key=KEY_GOOGLE_SERVICE_ACCOUNT,
        legacy_path=legacy_path,
        classification=SensitivityClass.SECRET,
        delete_legacy=delete_legacy,
    )


def load_google_oauth_token(legacy_path: Path, *, account: str = "default") -> bytes:
    """Read the Google OAuth refresh-token cache for ``account`` as raw bytes."""
    return load_secret_or_legacy(
        key=google_oauth_token_key(account),
        legacy_path=legacy_path,
        parser=bytes,
    )


def migrate_google_oauth_token_to_secret_store(
    legacy_path: Path,
    *,
    account: str = "default",
    delete_legacy: bool = False,
) -> None:
    """Move the OAuth token cache into the secret store under the per-account key."""
    migrate_legacy_to_secret_store(
        key=google_oauth_token_key(account),
        legacy_path=legacy_path,
        classification=SensitivityClass.SECRET,
        # OAuth refresh tokens rotate frequently — shorter TTL so a
        # forgotten / orphaned cache record expires automatically.
        expires_in_days=30,
        delete_legacy=delete_legacy,
    )


def load_mcp_workspace_credentials(legacy_path: Path) -> bytes:
    """Read the workspace MCP credential cache."""
    return load_secret_or_legacy(
        key=KEY_MCP_WORKSPACE_CREDENTIALS,
        legacy_path=legacy_path,
        parser=bytes,
    )


def migrate_mcp_workspace_credentials_to_secret_store(
    legacy_path: Path,
    *,
    delete_legacy: bool = False,
) -> None:
    """Move ``env/workspace-mcp-credentials`` into the secret store."""
    migrate_legacy_to_secret_store(
        key=KEY_MCP_WORKSPACE_CREDENTIALS,
        legacy_path=legacy_path,
        classification=SensitivityClass.SECRET,
        delete_legacy=delete_legacy,
    )


def load_operator_profile(legacy_path: Path) -> dict[str, object]:
    """Read the operator profile (Cl@ve identity values), secret-store-first."""
    return load_secret_or_legacy(
        key=KEY_OPERATOR_PROFILE,
        legacy_path=legacy_path,
        parser=lambda data: json.loads(data.decode("utf-8")),
    )


def migrate_operator_profile_to_secret_store(
    legacy_path: Path,
    *,
    delete_legacy: bool = False,
) -> None:
    """Move the operator profile JSON into the secret store as IDENTITY-class.

    The operator profile carries Cl@ve identity values (NIF, fecha de
    validez del DNI). Classified as IDENTITY (not SECRET) per the
    Wave-2 ADR; the secret store accepts both.
    """
    migrate_legacy_to_secret_store(
        key=KEY_OPERATOR_PROFILE,
        legacy_path=legacy_path,
        # NB: SecretStore.put refuses non-SECRET/SESSION today. Until
        # the substrate is widened to accept IDENTITY too, this helper
        # writes SESSION (the closest fit — short TTL + ciphertext at
        # rest) and the operator-profile reader is responsible for
        # the IDENTITY-class semantics at the API surface.
        classification=SensitivityClass.SESSION,
        delete_legacy=delete_legacy,
    )


__all__ = [
    "KEY_GOOGLE_OAUTH_CLIENT",
    "KEY_GOOGLE_OAUTH_TOKEN_PREFIX",
    "KEY_GOOGLE_SERVICE_ACCOUNT",
    "KEY_MCP_WORKSPACE_CREDENTIALS",
    "KEY_OPERATOR_PROFILE",
    "google_oauth_token_key",
    "load_google_oauth_client",
    "load_google_oauth_token",
    "load_google_service_account",
    "load_mcp_workspace_credentials",
    "load_operator_profile",
    "load_secret_or_legacy",
    "migrate_google_oauth_client_to_secret_store",
    "migrate_google_oauth_token_to_secret_store",
    "migrate_google_service_account_to_secret_store",
    "migrate_legacy_to_secret_store",
    "migrate_mcp_workspace_credentials_to_secret_store",
    "migrate_operator_profile_to_secret_store",
]
