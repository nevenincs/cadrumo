"""The platform user-data storage root.

The central settings facade (:class:`~core.config.Settings`) roots the
encrypted profile store at ``cadrumo_local_storage_root``, from which the
token, log, secret, blob and audit roots derive. This module resolves that
default, and resolves it to exactly one place: the platform user-data
directory (``%LOCALAPPDATA%`` on Windows, ``$XDG_DATA_HOME`` with the
``~/.local/share`` fallback on Linux, ``~/Library/Application Support`` on
macOS).

It does NOT classify how the process was installed. Cadrumo is a tax-filing
product; a repository is a development artefact with no runtime meaning, so
production code never inspects the filesystem for a ``pyproject.toml`` or a
``.git`` marker. An earlier revision did exactly that and branched on the
answer to choose between a checkout-local ``var/storage`` and the platform
directory — which meant a source-layout guess decided where a taxpayer's
regulated financial state was written. Detection is gone; only the platform
answer remains.

The dev loop is served by configuration, not by detection: a developer who
wants the store inside their checkout sets ``CADRUMO_LOCAL_STORAGE_ROOT``
(the justfile does), and an explicit operator override wins over this
default like any other setting.

Every input the resolution reads — the platform string, the environment
mapping, and the home directory — is captured in the frozen
:class:`StateRootInputs` seam, so resolution is a pure function of its
argument and testable without mutating the ambient process.
:func:`default_storage_root` is the live entry point
:class:`~core.config.Settings` binds as its ``cadrumo_local_storage_root``
default factory.

See Also:
    :class:`~core.config.Settings`
        Central settings aggregate whose storage-root default is resolved here.
    :class:`StateRootInputs`
        Frozen seam that captures every environmental input used by resolution.
    :func:`resolve_state_root`
        Pure resolver that returns the effective storage root.
    :func:`default_storage_root`
        Live default factory bound into the settings model.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import ClassVar

from pydantic import BaseModel

from .models import STRICT_FROZEN_CONFIG
from ._storage_taxonomy import StorageCategory, storage_location
from .product_identity import PRODUCT_IDENTITY

_WINDOWS_PLATFORM = "win32"
_MACOS_PLATFORM = "darwin"

#: Vendor/application directory name appended to the platform user-data base.
_APP_DIRNAME = PRODUCT_IDENTITY.python_package
#: Retired ``aeat`` directory inspected only to refuse implicit state adoption.
_FORMER_PRODUCT_APP_DIRNAME = "aeat"
#: Storage substrate subdirectory under the resolved installed state root.
_STORAGE_DIRNAME = "storage"
#: Bucket container directory name, read from the one core storage authority.
BUCKETS_DIRNAME = storage_location(StorageCategory.BUCKETS).subpath
#: Per-bucket database directory name, read from the one core storage authority.
BUCKET_DB_DIRNAME = storage_location(StorageCategory.BUCKET_DATABASE).subpath
#: Canonical SQLite filename, read from the one core storage authority.
PRODUCT_DATABASE_FILENAME = storage_location(StorageCategory.ROOT_FALLBACK_DATABASE).subpath
#: Retired ``aeat`` database filename inspected only for refusal.
FORMER_PRODUCT_DATABASE_FILENAME = "aeat.db"


class FormerProductStateError(RuntimeError):
    """Raised when installed Cadrumo detects a retired ``aeat`` state root.

    Detection is refusal-only. The resolver does not open, read, move, re-key,
    delete, or adopt anything below the retired ``aeat`` application directory.
    """

    __bare_base_rationale__: ClassVar[str] = (
        "raised from inside Settings/pydantic validation during bootstrap, before the CadrumoError "
        "registry can be relied upon; the CLI boundary explicitly catches it ahead of the "
        "CadrumoError arm and translates it into a registered CliRefusedBoundaryError"
    )


def refuse_former_product_database(storage_root: Path, *, bucket_id: str | None = None) -> None:
    """Refuse a recognizable retired ``aeat`` database without opening it.

    Only filesystem metadata is inspected. The retired database is never
    connected to, read, copied, moved, deleted, or adopted.
    """
    parent = storage_root
    if bucket_id:
        parent = parent / BUCKETS_DIRNAME / bucket_id / BUCKET_DB_DIRNAME
    former_database = parent / FORMER_PRODUCT_DATABASE_FILENAME
    if not former_database.exists():
        return
    raise FormerProductStateError(
        "Cadrumo detected an incompatible retired `aeat` database named "
        f"{FORMER_PRODUCT_DATABASE_FILENAME!r}. Cadrumo will not read, move, "
        "copy, delete, migrate, or adopt that database.",
    )


class StateRootInputs(BaseModel):
    """Injectable, frozen seam for state-root resolution.

    Capturing every environmental input as an explicit field makes both
    :func:`platform_user_data_root` and :func:`resolve_state_root` pure functions
    of its argument, so a test constructs a deterministic platform context
    rather than mutating ``os.environ`` or patching ``sys.platform``.
    """

    model_config = STRICT_FROZEN_CONFIG

    platform: str
    environ: dict[str, str]
    home: Path


class StateRootResolution(BaseModel):
    """Typed outcome of resolving the storage state root.

    Carries the platform user-data base and the effective ``storage_root``
    that :class:`~core.config.Settings` defaults ``cadrumo_local_storage_root``
    to. No run-mode or repository concept appears here: the product does not
    classify its own installation.
    """

    model_config = STRICT_FROZEN_CONFIG

    platform_user_data_root: Path
    storage_root: Path


def live_state_root_inputs() -> StateRootInputs:
    """Capture the running process's state-root inputs.

    Snapshots :data:`~sys.platform`, a copy of ``os.environ``, and the
    user's home directory into a frozen :class:`StateRootInputs` for
    :func:`resolve_state_root`.
    """
    return StateRootInputs(
        platform=sys.platform,
        environ=dict(os.environ),
        home=Path.home(),
    )


def _env_absolute_path(environ: dict[str, str], name: str) -> Path | None:
    """Return an absolute :class:`~pathlib.Path` from ``environ[name]``, or ``None``.

    A blank, unset, or non-absolute value yields ``None`` so the caller falls
    back to the platform default. The absolute-only rule matches the XDG Base
    Directory specification (a relative ``$XDG_DATA_HOME`` is ignored) and is
    applied uniformly to ``%LOCALAPPDATA%`` for the same robustness.
    """
    raw = environ.get(name, "").strip()
    if not raw:
        return None
    candidate = Path(raw)
    return candidate if candidate.is_absolute() else None


def platform_user_data_root(inputs: StateRootInputs) -> Path:
    """Resolve the Cadrumo platform user-data directory for the given inputs.

    Windows resolves under ``%LOCALAPPDATA%`` (``~/AppData/Local`` when the
    variable is unset or not absolute); macOS under
    ``~/Library/Application Support``; every other platform under
    ``$XDG_DATA_HOME`` (``~/.local/share`` when unset or not absolute). The
    canonical product application directory name is appended to the resolved base.
    """
    if inputs.platform == _WINDOWS_PLATFORM:
        base = _env_absolute_path(inputs.environ, "LOCALAPPDATA") or inputs.home / "AppData" / "Local"
    elif inputs.platform == _MACOS_PLATFORM:
        base = inputs.home / "Library" / "Application Support"
    else:
        base = _env_absolute_path(inputs.environ, "XDG_DATA_HOME") or inputs.home / ".local" / "share"
    return base / _APP_DIRNAME


def _refuse_former_product_state(user_data_root: Path) -> None:
    """Refuse a recognizable sibling directory left by retired ``aeat`` state."""
    former_root = user_data_root.parent / _FORMER_PRODUCT_APP_DIRNAME
    if not former_root.exists():
        return
    raise FormerProductStateError(
        "Cadrumo detected incompatible retired `aeat` state at "
        f"{former_root}. Cadrumo will not read, move, re-key, delete, or adopt that state.",
    )


def resolve_state_root(inputs: StateRootInputs) -> StateRootResolution:
    """Resolve the effective storage state root.

    Unconditional: the store always lands under the platform user-data
    directory. Cadrumo is a tax-filing product and is blind to how it was
    installed — it never inspects the filesystem for a ``pyproject.toml``
    or a ``.git`` marker to decide where a taxpayer's encrypted state
    belongs. A repository is a development artefact with no meaning at
    runtime, and branching on one put regulated financial data in a
    location chosen by a source-layout guess.

    A developer who wants the store inside their checkout sets
    ``CADRUMO_LOCAL_STORAGE_ROOT`` (the justfile does this), which wins
    over this default like any other operator override. That keeps the
    dev loop working through the ordinary configuration channel instead
    of through product code that detects its own environment.
    """
    user_data_root = platform_user_data_root(inputs)
    _refuse_former_product_state(user_data_root)
    return StateRootResolution(
        platform_user_data_root=user_data_root,
        storage_root=user_data_root / _STORAGE_DIRNAME,
    )


def default_storage_root() -> Path:
    """Return the ``cadrumo_local_storage_root`` default for the live process.

    Bound as the :class:`~core.config.Settings` ``cadrumo_local_storage_root``
    default factory. Always the platform user-data storage directory — the
    product does not classify its installation. A developer overrides it with
    ``CADRUMO_LOCAL_STORAGE_ROOT``.
    """
    return resolve_state_root(live_state_root_inputs()).storage_root
