"""Secure persistence adapter for the operator tax-residence profile.

Persists :class:`aeat.domain.profile.TaxResidenceProfile` as IDENTITY-class
secure objects in the primary database. The path APIs remain as logical
profile identifiers for callers that choose alternate profile names.
"""

from __future__ import annotations

import contextlib
import json
import os
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path

from pydantic import ValidationError

from ....domain.profile import TaxResidenceProfile
from ....domain.profile._errors import ProfileNotConfiguredError, TaxResidenceProfileError
from ..storage import SensitivityClass
from ..storage.sql import SecureObjectRepository

_PROFILE_FILENAME = "tax-residence.json"
_PROFILE_DIRNAME = "aeat"
_SCHEMA_VERSION = "1"
_SECURE_OBJECT_VERSION = 1
_TAX_RESIDENCE_NAMESPACE = "aeat.persistence.profile.tax_residence"


def default_path() -> Path:
    """Return the OS-appropriate path for the tax-residence profile JSON.

    Honours :attr:`aeat.core.config.Settings.aeat_tax_residence_profile_path`
    when configured; otherwise resolves :envvar:`AEAT_TAX_RESIDENCE_PROFILE_PATH`,
    :envvar:`APPDATA` on Windows, and :envvar:`XDG_CONFIG_HOME` on POSIX in
    that order before falling back to ``~/.config/aeat/tax-residence.json``.

    Returns:
        Filesystem path for the profile JSON file.
    """

    configured: Path | None = None
    # Broad suppress: load_settings() can raise ValidationError, OSError,
    # ValueError, or any .env-parser error; every failure means "use OS default".
    with contextlib.suppress(Exception):
        from ....core.config import load_settings

        configured = load_settings().aeat_tax_residence_profile_path
    if configured is not None:
        return configured
    return _default_path(os.environ, os.name)


def load_json(path: Path | None = None) -> dict[str, object] | None:
    """Load raw profile JSON from the secure object backend.

    Args:
        path: Override for the profile file path; defaults to
            :func:`default_path`.

    Returns:
        Parsed JSON object, or ``None`` when the file does not exist.

    Raises:
        :exc:`aeat.domain.profile._errors.TaxResidenceProfileError`: When the
            file cannot be read, contains invalid JSON, is not an object, or
            carries an unsupported schema version.
    """

    target = _logical_path(path)
    try:
        record = SecureObjectRepository().load(
            _TAX_RESIDENCE_NAMESPACE,
            _object_key(target),
            expected_class=SensitivityClass.IDENTITY,
            max_supported_version=_SECURE_OBJECT_VERSION,
        )
        if record is None:
            return None
        payload = json.loads(record.payload.decode("utf-8"))
    except ValueError as exc:
        raise TaxResidenceProfileError(f"invalid tax-residence profile JSON: {target}") from exc
    if not isinstance(payload, dict):
        raise TaxResidenceProfileError(f"tax-residence profile must be a JSON object: {target}")
    version = payload.get("schema_version")
    if version != _SCHEMA_VERSION:
        raise TaxResidenceProfileError(
            f"unsupported tax-residence profile schema_version={version!r}; expected {_SCHEMA_VERSION!r}"
        )
    return dict(payload)


def save_json(payload: Mapping[str, object], path: Path | None = None) -> None:
    """Persist ``payload`` as an IDENTITY-class secure object.

    Args:
        payload: Mapping to serialize.
        path: Override for the profile file path; defaults to
            :func:`default_path`.

    Raises:
        :exc:`aeat.domain.profile._errors.TaxResidenceProfileError`: When the
            payload cannot be serialized or the file cannot be written.
    """

    target = _logical_path(path)
    try:
        data = json.dumps(dict(payload), ensure_ascii=False, sort_keys=True).encode("utf-8")
        SecureObjectRepository().save(
            namespace=_TAX_RESIDENCE_NAMESPACE,
            object_key=_object_key(target),
            classification=SensitivityClass.IDENTITY,
            schema_version=_SECURE_OBJECT_VERSION,
            written_at=datetime.now(UTC),
            payload=data,
        )
    except (OSError, TypeError, ValueError, ValidationError) as exc:
        raise TaxResidenceProfileError(f"could not write tax-residence profile: {target}") from exc


def clear_json(path: Path | None = None) -> None:
    """Remove the tax-residence profile object when present.

    Args:
        path: Override for the profile file path; defaults to
            :func:`default_path`.

    Raises:
        :exc:`aeat.domain.profile._errors.TaxResidenceProfileError`: When the
            file exists but cannot be removed.
    """

    target = _logical_path(path)
    try:
        SecureObjectRepository().delete(_TAX_RESIDENCE_NAMESPACE, _object_key(target))
    except OSError as exc:
        raise TaxResidenceProfileError(f"could not remove tax-residence profile: {target}") from exc


def load_tax_residence(path: object | None = None) -> TaxResidenceProfile | None:
    """Load the operator's tax-residence profile.

    Args:
        path: Override for the profile file path; coerced via
            :func:`_coerce_path`.

    Returns:
        Validated :class:`aeat.domain.profile.TaxResidenceProfile`, or ``None``
        when no profile file exists.

    Raises:
        :exc:`aeat.domain.profile._errors.TaxResidenceProfileError`: When the
            file content fails pydantic validation.
    """

    payload = load_json(_coerce_path(path))
    if payload is None:
        return None
    try:
        return TaxResidenceProfile.model_validate(payload)
    except ValidationError as exc:
        raise TaxResidenceProfileError("invalid tax-residence profile content") from exc


def require_tax_residence(path: object | None = None) -> TaxResidenceProfile:
    """Load the operator's tax-residence profile or raise a REFUSED error.

    Args:
        path: Override for the profile file path.

    Returns:
        Validated :class:`aeat.domain.profile.TaxResidenceProfile`.

    Raises:
        :exc:`aeat.domain.profile._errors.ProfileNotConfiguredError`: When
            no profile file exists.
        :exc:`aeat.domain.profile._errors.TaxResidenceProfileError`: When
            the file content fails pydantic validation.
    """

    residence = load_tax_residence(path)
    if residence is None:
        raise ProfileNotConfiguredError()
    return residence


def save_tax_residence(residence: TaxResidenceProfile, path: object | None = None) -> None:
    """Persist ``residence`` as schema-versioned JSON.

    Args:
        residence: Tax-residence profile to persist.
        path: Override for the profile file path.

    Raises:
        :exc:`aeat.domain.profile._errors.TaxResidenceProfileError`: When the
            file cannot be written.
    """

    save_json(residence.model_dump(mode="json"), _coerce_path(path))


def clear_tax_residence(path: object | None = None) -> None:
    """Delete the operator's tax-residence profile when present.

    Args:
        path: Override for the profile file path.
    """

    clear_json(_coerce_path(path))


def _coerce_path(path: object | None):
    """Best-effort coercion of ``path`` to :class:`pathlib.Path` or ``None``."""
    if path is None:
        return None
    if isinstance(path, Path):
        return path
    if isinstance(path, str):
        return Path(path)
    return path


def _logical_path(path: Path | None) -> Path:
    return path or default_path()


def _object_key(path: Path) -> str:
    return Path(path).expanduser().as_posix()


def _default_path(environ: Mapping[str, str], os_name: str) -> Path:
    """Resolve the default profile path for the supplied environment.

    Args:
        environ: Environment mapping to consult (typically :data:`os.environ`).
        os_name: Value of :data:`os.name`; ``"nt"`` selects Windows defaults.

    Returns:
        Resolved profile path according to the env var precedence described
        in the module docstring.
    """
    override = environ.get("AEAT_TAX_RESIDENCE_PROFILE_PATH")
    if override:
        return Path(override).expanduser()
    if os_name == "nt":
        appdata = environ.get("APPDATA")
        if appdata:
            return Path(appdata) / _PROFILE_DIRNAME / _PROFILE_FILENAME
    xdg_config = environ.get("XDG_CONFIG_HOME")
    if xdg_config:
        return Path(xdg_config) / _PROFILE_DIRNAME / _PROFILE_FILENAME
    return Path.home() / ".config" / _PROFILE_DIRNAME / _PROFILE_FILENAME


__all__ = [
    "clear_json",
    "clear_tax_residence",
    "default_path",
    "load_json",
    "load_tax_residence",
    "require_tax_residence",
    "save_json",
    "save_tax_residence",
]
