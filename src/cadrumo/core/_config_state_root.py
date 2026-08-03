"""Installed-vs-checkout detection and the platform user-data storage root.

The central settings facade (:class:`~core.config.Settings`) roots the
encrypted profile store at ``cadrumo_local_storage_root``, from which the token,
log, secret, blob and audit roots derive. A source checkout uses
the checkout's ``var/storage``. That location is wrong for an installed
distribution. Under a wheel it can resolve inside the virtualenv; under ``uvx``
it can resolve inside uv's ephemeral cache. A cache prune could silently destroy
the taxpayer's encrypted store.

This module owns the two decisions that fix that defect without disturbing the
dev loop: whether the process runs from a source checkout or an installed
distribution (:func:`detect_run_mode`), and where the platform user-data base
lives per operating system (:func:`platform_user_data_root`). A checkout keeps
the the checkout's ``var/storage`` default; an installed run lands under
the platform user-data directory (``%LOCALAPPDATA%`` on Windows,
``$XDG_DATA_HOME`` with the ``~/.local/share`` fallback on Linux,
``~/Library/Application Support`` on macOS).

Every input the resolution reads — the project-root candidate, the platform
string, the environment mapping, and the home directory — is captured in the
frozen :class:`StateRootInputs` seam so the detection is deterministic and
testable without mutating the ambient process. :func:`default_storage_root` is
the live entry point :class:`~core.config.Settings` binds as its
``cadrumo_local_storage_root`` default factory.

See Also:
    :class:`~core.config.Settings`
        Central settings aggregate whose storage-root default is resolved here.
    :class:`StateRootInputs`
        Frozen seam that captures every environmental input used by resolution.
    :func:`detect_run_mode`
        Checkout-versus-installed classifier used before selecting a root.
    :func:`resolve_state_root`
        Pure resolver that returns the effective storage root.
    :func:`default_storage_root`
        Live default factory bound into the settings model.
"""

from __future__ import annotations

import os
import sys
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel

from ._models import STRICT_FROZEN_CONFIG
from .product_identity import PRODUCT_IDENTITY

# Project-root candidate: four levels up from this module
# (file → core/ → cadrumo/ → src/ → REPO_ROOT), mirroring
# the historical checkout-root walk exactly, so the checkout default is
# byte-identical to the historical value.
_CHECKOUT_ROOT = Path(__file__).resolve().parent.parent.parent.parent

_WINDOWS_PLATFORM = "win32"
_MACOS_PLATFORM = "darwin"

#: Vendor/application directory name appended to the platform user-data base.
_APP_DIRNAME = PRODUCT_IDENTITY.python_package
#: Retired ``aeat`` directory inspected only to refuse implicit state adoption.
_FORMER_PRODUCT_APP_DIRNAME = "aeat"
#: Storage substrate subdirectory under the resolved installed state root.
_STORAGE_DIRNAME = "storage"
#: Canonical SQLite filename for Cadrumo-owned application state.
PRODUCT_DATABASE_FILENAME = f"{PRODUCT_IDENTITY.python_package}.db"
#: Retired ``aeat`` database filename inspected only for refusal.
FORMER_PRODUCT_DATABASE_FILENAME = "aeat.db"
#: Checkout state-root layout: the checkout's ``var/storage``.
_CHECKOUT_STATE_SUBDIRS = ("var", "storage")


class RunMode(StrEnum):
    """Whether the process runs from a source checkout or an installed build.

    :func:`detect_run_mode` returns a member; :func:`resolve_state_root`
    branches on it to pick the checkout ``var/storage`` default or the
    platform user-data directory.
    """

    CHECKOUT = "checkout"
    INSTALLED = "installed"


class FormerProductStateError(RuntimeError):
    """Raised when installed Cadrumo detects a retired ``aeat`` state root.

    Detection is refusal-only. The resolver does not open, read, move, re-key,
    delete, or adopt anything below the retired ``aeat`` application directory.
    """


def refuse_former_product_database(storage_root: Path, *, bucket_id: str | None = None) -> None:
    """Refuse a recognizable retired ``aeat`` database without opening it.

    Only filesystem metadata is inspected. The retired database is never
    connected to, read, copied, moved, deleted, or adopted.
    """
    parent = storage_root
    if bucket_id:
        parent = parent / "buckets" / bucket_id / "db"
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
    :func:`detect_run_mode` and :func:`platform_user_data_root` pure functions
    of their argument, so tests construct an ``installed`` or ``checkout``
    context deterministically rather than mutating ``os.environ`` or patching
    ``sys.platform``.
    """

    model_config = STRICT_FROZEN_CONFIG

    project_root_candidate: Path
    platform: str
    environ: dict[str, str]
    home: Path


class StateRootResolution(BaseModel):
    """Typed outcome of resolving the storage state root.

    Carries the decided :class:`RunMode`, the project-root candidate it was
    decided from, the platform user-data base, and the effective
    ``storage_root`` that :class:`~core.config.Settings` should default
    ``cadrumo_local_storage_root`` to.
    """

    model_config = STRICT_FROZEN_CONFIG

    run_mode: RunMode
    project_root: Path
    platform_user_data_root: Path
    storage_root: Path


def live_state_root_inputs() -> StateRootInputs:
    """Capture the running process's state-root inputs.

    Snapshots the module-derived project-root candidate, :data:`~sys.platform`,
    a copy of ``os.environ``, and the user's home directory into a frozen
    :class:`StateRootInputs` for :func:`resolve_state_root`.
    """
    return StateRootInputs(
        project_root_candidate=_CHECKOUT_ROOT,
        platform=sys.platform,
        environ=dict(os.environ),
        home=Path.home(),
    )


def detect_run_mode(inputs: StateRootInputs) -> RunMode:
    """Classify the run as a source checkout or an installed distribution.

    A source checkout carries the repository markers at its project root: a
    ``pyproject.toml`` file and a ``.git`` entry (a directory in a normal
    clone, a pointer *file* inside a git worktree — so presence, not
    directory-ness, is the test). An installed wheel resolves the candidate
    under ``site-packages`` where neither marker exists, so the absence of
    either marker classifies the run as installed.
    """
    root = inputs.project_root_candidate
    has_pyproject = (root / "pyproject.toml").is_file()
    has_git_marker = (root / ".git").exists()
    if has_pyproject and has_git_marker:
        return RunMode.CHECKOUT
    return RunMode.INSTALLED


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
    """Resolve the effective storage state root for the given inputs.

    A checkout keeps the historical the checkout's ``var/storage``
    default; an installed run lands at ``<platform-user-data>/cadrumo/storage`` so
    the encrypted store never resolves inside a virtualenv or uv cache.
    """
    run_mode = detect_run_mode(inputs)
    user_data_root = platform_user_data_root(inputs)
    if run_mode is RunMode.CHECKOUT:
        storage_root = inputs.project_root_candidate.joinpath(*_CHECKOUT_STATE_SUBDIRS)
    else:
        _refuse_former_product_state(user_data_root)
        storage_root = user_data_root / _STORAGE_DIRNAME
    return StateRootResolution(
        run_mode=run_mode,
        project_root=inputs.project_root_candidate,
        platform_user_data_root=user_data_root,
        storage_root=storage_root,
    )


def default_storage_root() -> Path:
    """Return the ``cadrumo_local_storage_root`` default for the live process.

    Bound as the :class:`~core.config.Settings` ``cadrumo_local_storage_root``
    default factory: a checkout resolves to the checkout's ``var/storage``
    (unchanged), an installed run to the platform user-data storage directory.
    """
    return resolve_state_root(live_state_root_inputs()).storage_root
