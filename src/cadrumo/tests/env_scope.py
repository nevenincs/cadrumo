"""Centralized environment-scope helpers for tests.

The backend's canonical state-mutation surface for AEAT-prefixed config
is :func:`cadrumo.core.config.override_settings`. That ContextVar-backed
helper covers every Settings field and is the right tool for almost
every test that needs to pin or shadow AEAT configuration.

A small set of tests legitimately need to manipulate *real*
``os.environ`` instead of (or in addition to) the ContextVar layer:

* The pydantic-settings env-precedence tests in
  :mod:`aeat-tests.test_config` exercise the env-reading contract
  itself — validators must observe real env values, so a ContextVar
  override above the env layer would defeat the test.
* The model-validator-derives-default tests in
  :mod:`cadrumo.core.test_token_dir_state_root` must observe an unset
  ``CADRUMO_TOKEN_DIR`` so the validator runs.
* CLI runtime infrastructure that AEAT does not own (the pytest
  runner's ``PYTEST_CURRENT_TEST`` flag, Rich's ``COLUMNS`` width
  read, ``sys.argv``) is read directly by tightly scoped helpers in
  :mod:`cadrumo.entrypoints.cli._stdio` and
  :mod:`cadrumo.core.access_gate`. Those production helpers accept
  explicit overrides as kwargs; this module is for the os.environ
  side only.

This module is the single authoritative API tests should call. Test
files MUST NOT roll their own ``os.environ`` save/restore scope; if a
test needs to manipulate env state that no existing API covers, add a
new function here so the surface stays auditable.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from pydantic import SecretStr
from pydantic_settings import SettingsConfigDict

from ..core.config import AuthProviderKindSetting, Settings

_SETTINGS_STORAGE_DIRECTORIES: list[TemporaryDirectory[str]] = []
"""Keep temporary Cadrumo local-storage roots alive for returned Settings instances."""

__all__ = [
    "isolated_aeat_env",
    "ready_clave_settings",
    "scoped_cwd",
    "scoped_env_var",
    "scoped_sys_argv",
    "settings_without_env_file",
]


class _EnvFileFreeSettings(Settings):
    """A :class:`~cadrumo.core.config.Settings` subclass that never reads a real ``.env`` file.

    ``pydantic_settings.BaseSettings.__init__`` accepts a real, documented
    ``_env_file=None`` per-instance override, but both ``pyright`` and ``ty``
    synthesize a subclass ``__init__`` from its declared fields and drop the
    underscore-prefixed init-only kwargs that hand-written signature carries,
    so ``Settings(_env_file=None)`` reports an unknown-argument error under
    both checkers even though the runtime call is valid. Overriding
    ``env_file=None`` at the class level instead achieves the identical
    env-file-free construction without touching that per-instance kwarg;
    pydantic's ``model_config`` merge (child overrides only the keys it
    declares) leaves every other setting (``env_file_encoding``,
    ``env_ignore_empty``, ...) unchanged from :class:`Settings`.
    """

    model_config = SettingsConfigDict(env_file=None)


def settings_without_env_file(**overrides: Any) -> Settings:
    """Construct a :class:`~cadrumo.core.config.Settings` that never reads the real ``.env`` file.

    Equivalent at runtime to ``Settings(_env_file=None)`` — see
    :class:`_EnvFileFreeSettings` for why this factory exists instead of the
    raw keyword form.
    """
    if (
        "cadrumo_local_storage_root" not in overrides
        and "CADRUMO_LOCAL_STORAGE_ROOT" not in os.environ
        and "cadrumo_local_storage_root" not in os.environ
    ):
        temporary_directory = TemporaryDirectory(prefix="cadrumo-settings-")
        _SETTINGS_STORAGE_DIRECTORIES.append(temporary_directory)
        overrides = {**overrides, "cadrumo_local_storage_root": temporary_directory.name}
    return _EnvFileFreeSettings(**overrides)


def ready_clave_settings(tax_id: str) -> Settings:
    return settings_without_env_file(
        cadrumo_auth_provider=AuthProviderKindSetting.CLAVE_MOVIL,
        cadrumo_clave_movil_dni_nie=SecretStr(tax_id),
    )


@contextmanager
def isolated_aeat_env(**overrides: str) -> Iterator[None]:
    """Clear every Settings env slot, apply explicit overrides, restore on exit.

    Despite its historical name, this includes Cadrumo product settings and
    AEAT authority settings.

    Snapshots both the upper-case and lower-case slot for each Settings
    field name (pydantic-settings consults both), pops them from
    ``os.environ``, applies the explicit ``overrides`` mapping, and
    restores the prior values on exit — including on exception.

    Tests use this when they need to construct a ``Settings`` instance
    (or a subclass with a custom ``model_config``) whose values come
    from a known, controlled env baseline rather than the ambient
    operator/CI environment. The ``override_settings`` helper in
    :mod:`cadrumo.core.config` is the right tool when tests need to pin
    Settings field values; this helper is the right tool when tests
    are exercising the env-precedence layer itself.

    Arguments:
        **overrides: Env vars to set within the with-block, by name
            (e.g. ``CADRUMO_AUTH_PROVIDER="clave_movil"``). Pass an empty
            string to test the "explicitly set to blank" path; pass no
            key for that var to test the "unset" path.

    Examples:
        >>> with isolated_aeat_env(CADRUMO_AUTH_PROVIDER="clave_movil"):
        ...     settings = Settings()
        ...     assert settings.cadrumo_auth_provider is AuthProviderKindSetting.CLAVE_MOVIL
    """
    saved: dict[str, str | None] = {}
    for name in Settings.env_var_names():
        saved[name] = os.environ.pop(name, None)
        saved[name.lower()] = os.environ.pop(name.lower(), None)
    for name, value in overrides.items():
        os.environ[name] = value
    try:
        yield
    finally:
        for name in overrides:
            os.environ.pop(name, None)
        for name, value in saved.items():
            if value is not None:
                os.environ[name] = value


@contextmanager
def scoped_sys_argv(argv: list[str]) -> Iterator[None]:
    """Pin ``sys.argv`` for the with-block.

    The CLI startup helpers in :mod:`cadrumo.entrypoints.cli._stdio` (and
    a small set of sibling utilities) inspect ``sys.argv`` to decide
    whether the invocation is a ``--help`` surface. Tests exercising
    those branches need argv pinned to a known value.

    Sys.argv is process infrastructure, not AEAT configuration, so it
    has no Settings equivalent. This helper is the centralized scope
    helper tests must call rather than rebinding ``sys.argv`` in a
    test-local context manager.

    Arguments:
        argv: The argv list to install for the with-block.

    Examples:
        >>> with scoped_sys_argv(["aeat", "--help"]):
        ...     with _ensure_help_render_width():
        ...         ...
    """
    saved = sys.argv
    sys.argv = argv
    try:
        yield
    finally:
        sys.argv = saved


@contextmanager
def scoped_env_var(name: str, value: str | None) -> Iterator[None]:
    """Pin a single ``os.environ`` entry for the with-block.

    Use this for env vars the AEAT backend deliberately reads from
    ``os.environ`` rather than from Settings — pytest infrastructure
    (``PYTEST_CURRENT_TEST``), display-shell variables (``COLUMNS``),
    or any env slot the production code documents as a non-Settings
    surface. For AEAT-prefixed Settings fields, use
    :func:`cadrumo.core.config.override_settings` instead.

    Arguments:
        name: Env var name (case-sensitive).
        value: New value to assign, or ``None`` to ensure the var is
            absent.

    Examples:
        >>> with scoped_env_var("PYTEST_CURRENT_TEST", None):
        ...     snapshot = AeatAccessGate(settings).snapshot_env()
    """
    prior = os.environ.get(name)
    if value is None:
        os.environ.pop(name, None)
    else:
        os.environ[name] = value
    try:
        yield
    finally:
        if prior is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = prior


@contextmanager
def scoped_cwd(path: Path) -> Iterator[None]:
    """Change the process working directory for the with-block.

    The determinism-conformance and CLI path-echo suites need to prove a
    behaviour is genuinely cwd-independent, which means actually running
    code from two different real working directories. The process cwd is
    OS-process infrastructure, not AEAT configuration, so — like
    :func:`scoped_sys_argv` — it has no Settings equivalent; this is the
    centralized scope helper tests must call rather than rebinding
    ``os.getcwd()``/``os.chdir`` in a test-local try/finally.

    Arguments:
        path: The directory to ``chdir`` into for the with-block.

    Examples:
        >>> with scoped_cwd(tmp_path / "cwd-a"):
        ...     result = service.add(source_path=Path("receipt.pdf"), ...)
    """
    prior = os.getcwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(prior)
