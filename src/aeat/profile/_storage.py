"""JSON persistence for Kent's tax-residence profile."""

from __future__ import annotations

import os
import tempfile
from collections.abc import Mapping
from contextlib import suppress
from pathlib import Path

from pydantic import ValidationError

from ._errors import TaxResidenceProfileError

_PROFILE_FILENAME = "tax-residence.json"
_PROFILE_DIRNAME = "aeat"
_SCHEMA_VERSION = "1"


def default_path() -> Path:
    """Return the OS config path for the tax-residence profile JSON."""

    try:
        from ..config import load_settings

        configured = load_settings().aeat_tax_residence_profile_path
    except Exception:
        configured = None
    if configured is not None:
        return configured
    return _default_path(os.environ, os.name)


def load_json(path: Path | None = None) -> dict[str, object] | None:
    """Load raw profile JSON from ``path``.

    Args:
        path: Optional explicit JSON path. Defaults to :func:`default_path`.

    Returns:
        Parsed JSON object, or ``None`` when the file is absent.

    Raises:
        TaxResidenceProfileError: If the file is malformed or uses an
            unsupported schema version.
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
    """Atomically persist ``payload`` as UTF-8 JSON.

    Args:
        payload: JSON-compatible profile payload.
        path: Optional explicit JSON path. Defaults to :func:`default_path`.

    Raises:
        TaxResidenceProfileError: If the payload cannot be written.
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
    """Remove the tax-residence profile file if it exists."""

    target = path or default_path()
    try:
        target.unlink(missing_ok=True)
    except OSError as exc:
        raise TaxResidenceProfileError(f"could not remove tax-residence profile: {target}") from exc


def _default_path(environ: Mapping[str, str], os_name: str) -> Path:
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
    "default_path",
    "load_json",
    "save_json",
]
