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

from ..core.auth_provider import AuthProviderKind
from ..core.config import Settings, reset_settings_cache
from ..core.external_constants import OutputLanguage
from ..core.i18n.render import OUTPUT_LANGUAGE_ENV_VAR, clear_output_language_cache
from .collection_storage_root import SETTINGS_STEM

_SETTINGS_STORAGE_DIRECTORIES: list[TemporaryDirectory[str]] = []
"""Temporary storage roots minted for returned Settings instances, held open.

The strong reference is deliberate: a returned :class:`Settings` names this
directory, so it has to outlive the call that produced it. What it must NOT do
is outlive the session, and for a long time it did -- nothing dropped these and
no sweep covered the prefix, so a measured 457 of them had accumulated in the
operator's temp directory, the oldest three weeks old. Each is empty; the cost
is in directory entries rather than bytes, which is why byte-oriented
measurement never noticed.

:func:`release_settings_storage_directories` is what ends the lifetime, and
``cadrumo/conftest.py`` calls it once per session.
"""


def release_settings_storage_directories() -> None:
    """Remove every temporary storage root this module minted.

    Called at session teardown. Safe to call more than once, and safe to call
    when nothing was minted.

    Best-effort per directory: teardown must not fail a passing session nor
    mask a failing one, and a root a test deliberately made unreadable is a
    legitimate reason for cleanup to fail. The reference is dropped either way,
    so a directory that resists removal is not retried forever.
    """
    while _SETTINGS_STORAGE_DIRECTORIES:
        directory = _SETTINGS_STORAGE_DIRECTORIES.pop()
        try:
            directory.cleanup()
        except OSError:
            continue


__all__ = [
    "activate_output_language",
    "isolated_aeat_env",
    "output_language_scope",
    "ready_clave_settings",
    "release_settings_storage_directories",
    "scoped_cwd",
    "scoped_env_var",
    "scoped_sys_argv",
    "settings_without_env_file",
]


class _EnvFileFreeSettings(Settings):
    """A :class:`~cadrumo.core.config.Settings` subclass that never reads a real ``.env`` file.

    ``pydantic_settings.BaseSettings.__init__`` accepts a real, documented
    ``_env_file=None`` per-instance override, but both ``pyrefly`` and ``ty``
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
        temporary_directory = TemporaryDirectory(prefix=SETTINGS_STEM)
        _SETTINGS_STORAGE_DIRECTORIES.append(temporary_directory)
        overrides = {**overrides, "cadrumo_local_storage_root": temporary_directory.name}
    return _EnvFileFreeSettings(**overrides)


def ready_clave_settings(tax_id: str) -> Settings:
    return settings_without_env_file(
        cadrumo_auth_provider=AuthProviderKind.CLAVE_MOVIL,
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
        ...     assert settings.cadrumo_auth_provider is AuthProviderKind.CLAVE_MOVIL
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


def activate_output_language(language: OutputLanguage | None) -> None:
    """Set the output language and make the change observable, without restoring it.

    ``load_settings()`` holds a process-wide :class:`Settings` singleton cached
    by the active-profile pointer rather than by env var, so a bare
    ``os.environ`` write is invisible to it once that singleton exists, and
    :func:`clear_output_language_cache` alone only invalidates the
    output-language memo layered on top. Both caches are dropped here so the
    new value is the one production code reads.

    This is the mid-block STIMULUS, not a scope: it never restores. Call it
    only inside :func:`output_language_scope`, which owns the restore. It
    exists because the language switch under test sometimes happens inside a
    Textual message-pump callback, a different asyncio Context from the test's
    own coroutine — ``override_settings``'s contextvar Token cannot be reset
    across that boundary, while these plain caches have no such constraint.

    Arguments:
        language: Output-language token to activate, or ``None`` to unset the
            variable and fall back to the configured default.
    """
    if language is None:
        os.environ.pop(OUTPUT_LANGUAGE_ENV_VAR, None)
    else:
        os.environ[OUTPUT_LANGUAGE_ENV_VAR] = language
    reset_settings_cache()
    clear_output_language_cache()


@contextmanager
def output_language_scope(language: OutputLanguage | None) -> Iterator[None]:
    """Pin the output language for the with-block and restore it on exit.

    Restores the prior value even when the block mutates the variable partway
    through — via :func:`activate_output_language` or from inside a callback
    the block cannot lexically wrap — because the restore reads the value
    captured on entry, not the one left behind. The settings and
    output-language caches are dropped on both edges, so neither the pinned
    value nor the restored one is masked by a stale singleton.

    Arguments:
        language: Output-language token to pin, or ``None`` to ensure the
            variable is absent for the block.

    Examples:
        >>> with output_language_scope("en"):
        ...     assert tr("some.key") == "English copy"
        ...     activate_output_language("es")
        ...     assert tr("some.key") == "Spanish copy"
    """
    try:
        with scoped_env_var(OUTPUT_LANGUAGE_ENV_VAR, language):
            reset_settings_cache()
            clear_output_language_cache()
            yield
    finally:
        reset_settings_cache()
        clear_output_language_cache()


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
