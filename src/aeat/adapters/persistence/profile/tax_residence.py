"""JSON persistence adapter for the operator tax-residence profile.

Persists :class:`aeat.domain.profile.KentTaxResidence` as schema-versioned
UTF-8 JSON under an OS-appropriate config directory, with atomic write
semantics via :func:`tempfile.mkstemp` and :func:`os.replace`. The default
location honours :envvar:`AEAT_TAX_RESIDENCE_PROFILE_PATH`,
:envvar:`APPDATA` (Windows), and :envvar:`XDG_CONFIG_HOME` (POSIX) in that
order, falling back to ``~/.config/aeat/tax-residence.json``.
"""

from __future__ import annotations

import contextlib
import os
import tempfile
from collections.abc import Mapping
from contextlib import suppress
from pathlib import Path

from pydantic import ValidationError

from ....domain.profile import KentTaxResidence
from ....domain.profile._errors import ProfileNotConfiguredError, TaxResidenceProfileError

_PROFILE_FILENAME = "tax-residence.json"
_PROFILE_DIRNAME = "aeat"
_SCHEMA_VERSION = "1"


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
    """Load raw profile JSON from ``path``.

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

    target = path or default_path()
    if not target.exists():
        return None
    try:
        import json

        payload = json.loads(target.read_text(encoding="utf-8"))
    except OSError as exc:
        raise TaxResidenceProfileError(f"could not read tax-residence profile: {target}") from exc
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
    """Atomically persist ``payload`` as pretty-printed UTF-8 JSON.

    Writes through a sibling tempfile + :func:`os.replace` so a partial
    write never leaves a corrupt profile file in place. The temp file is
    cleaned up on serialization failure.

    Args:
        payload: Mapping to serialize.
        path: Override for the profile file path; defaults to
            :func:`default_path`.

    Raises:
        :exc:`aeat.domain.profile._errors.TaxResidenceProfileError`: When the
            payload cannot be serialized or the file cannot be written.
    """

    target = path or default_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    fd = -1
    raw_temp_path: str | None = None
    try:
        import json

        fd, raw_temp_path = tempfile.mkstemp(
            prefix=f".{target.name}.",
            suffix=".tmp",
            dir=target.parent,
            text=True,
        )
        temp_path = Path(raw_temp_path)
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            fd = -1
            json.dump(dict(payload), handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, target)
    except (OSError, TypeError, ValueError, ValidationError) as exc:
        if fd >= 0:
            os.close(fd)
        if raw_temp_path is not None:
            with suppress(OSError):
                os.unlink(raw_temp_path)
        raise TaxResidenceProfileError(f"could not write tax-residence profile: {target}") from exc


def clear_json(path: Path | None = None) -> None:
    """Remove the tax-residence profile file when present.

    Args:
        path: Override for the profile file path; defaults to
            :func:`default_path`.

    Raises:
        :exc:`aeat.domain.profile._errors.TaxResidenceProfileError`: When the
            file exists but cannot be removed.
    """

    target = path or default_path()
    try:
        target.unlink(missing_ok=True)
    except OSError as exc:
        raise TaxResidenceProfileError(f"could not remove tax-residence profile: {target}") from exc


def load_tax_residence(path: object | None = None) -> KentTaxResidence | None:
    """Load the operator's tax-residence profile.

    Args:
        path: Override for the profile file path; coerced via
            :func:`_coerce_path`.

    Returns:
        Validated :class:`aeat.domain.profile.KentTaxResidence`, or ``None``
        when no profile file exists.

    Raises:
        :exc:`aeat.domain.profile._errors.TaxResidenceProfileError`: When the
            file content fails pydantic validation.
    """

    payload = load_json(_coerce_path(path))
    if payload is None:
        return None
    try:
        return KentTaxResidence.model_validate(payload)
    except ValidationError as exc:
        raise TaxResidenceProfileError("invalid tax-residence profile content") from exc


def require_tax_residence(path: object | None = None) -> KentTaxResidence:
    """Load the operator's tax-residence profile or raise a REFUSED error.

    Args:
        path: Override for the profile file path.

    Returns:
        Validated :class:`aeat.domain.profile.KentTaxResidence`.

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


def save_tax_residence(residence: KentTaxResidence, path: object | None = None) -> None:
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
