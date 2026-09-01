"""Fresh-interpreter subprocess CLI harness for real-entrypoint tests.

``cli_runner.py``'s ``invoke_cached_cli`` drives the CLI in-process through a
cached Click command tree, which is the right tool for the overwhelming
majority of CLI tests. It cannot cover one real class of test: proving that a
storage route, a secret-store backend, or an output language is resolved
correctly from *process state fixed before the interpreter starts* -- an
in-process invocation shares the already-running interpreter's import cache
and any ``Settings`` already constructed in it, so it cannot observe what a
genuinely fresh process does with a clean slate.

This module is the single transport for that class of test: spawn
``sys.executable -c <harness source>`` with a filtered environment, so the
child interpreter constructs its own ``Settings`` from scratch before
``cadrumo.entrypoints.cli.main`` runs.

Two layers, because the callers need two genuinely different things:

- :func:`run_subprocess_cli_harness` is the raw transport -- spawn one
  ``python -c`` child, filter the inherited environment, capture output.
  Every fresh-interpreter CLI test needs exactly this, regardless of how the
  child pins its ``Settings``.
- :func:`run_cadrumo_subprocess` layers the SHARED settings-injection
  mechanism on top: the child constructs an explicit ``Settings(...)`` and
  registers it on ``cadrumo.core.config._settings_override`` before calling
  ``main()``, bypassing the real environment entirely. Three independent
  harnesses converged on this exact mechanism; this is their one home.

A fourth site (``test_s423_selected_language_cli.py``) sets real
``os.environ`` entries before importing ``cadrumo.entrypoints.cli`` instead
of using the ContextVar override, and stays on its own harness source. The
two mechanisms are not interchangeable: the ContextVar override freezes one
``Settings`` instance for the whole child process, while the real-environment
route flows through ``cadrumo.core.config._constructed_settings``, an
``lru_cache`` keyed on the active-profile pointer's fingerprint -- if the
command under test rewrites the pointer file mid-invocation (a profile
create, login, or logout), the real-environment route re-derives ``Settings``
against the new pointer state on the next ``load_settings()`` call, while a
ContextVar override would keep serving the instance captured at process
start. That site still calls :func:`run_subprocess_cli_harness` for the raw
transport, so the environment-filtering and process-spawning plumbing is not
duplicated a fourth time; only its distinct settings-injection source stays
local to it.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from textwrap import dedent
from typing import TYPE_CHECKING

from .inventory import SRC_CADRUMO

if TYPE_CHECKING:
    from ..core.config import StorageRouteKind

__all__ = [
    "run_cadrumo_subprocess",
    "run_subprocess_cli_harness",
    "subprocess_cli_env",
]

#: Harness run by :func:`run_cadrumo_subprocess`. ``sys.argv[1]`` carries a
#: JSON payload (``{"settings": {...}, "expected_storage_route_kind": str |
#: None}``); ``sys.argv[2:]`` is handed to ``main()`` unchanged. Settings
#: values travel as JSON rather than being formatted into the source text, so
#: no caller value is ever interpolated into code the child interpreter
#: executes.
_CONTEXTVAR_HARNESS_SOURCE = dedent(
    """
    from __future__ import annotations

    import json
    import sys

    from cadrumo.core import config as config_module
    from cadrumo.core.config import Settings

    payload = json.loads(sys.argv[1])
    cli_args = sys.argv[2:]
    settings = Settings(_env_file=None, **payload["settings"])
    token = config_module._settings_override.set(settings)
    try:
        expected_route_kind = payload.get("expected_storage_route_kind")
        if expected_route_kind is not None:
            from cadrumo.core.config import StorageRouteKind, classify_storage_route

            route = classify_storage_route()
            assert route.kind is StorageRouteKind[expected_route_kind], route
        sys.argv = ["cadrumo", *cli_args]
        # Mirror the production console bootstrap: importing CLI contracts can
        # acquire loggers, but file handlers are authorized only after parsed
        # secret-source preflight.
        from cadrumo.core.logging import defer_logging_configuration, resume_logging_configuration

        defer_logging_configuration()
        try:
            from cadrumo.entrypoints.cli import main

            main()
        finally:
            resume_logging_configuration()
    finally:
        config_module._settings_override.reset(token)
    """,
)


def subprocess_cli_env(
    *,
    strip_prefixes: Sequence[str] = ("AEAT_", "PYTEST_"),
    extra: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Return a subprocess environment stripped of the given prefixes.

    Every fresh-interpreter CLI harness needs a UTF-8-forced environment, and
    the caller decides which ambient prefixes must not leak into the child --
    ``AEAT_`` and ``PYTEST_`` are pytest/legacy scaffolding never meant to
    reach the CLI, while ``CADRUMO_`` is real product configuration some
    suites deliberately keep out of the child (so a developer's exported
    ``CADRUMO_*`` cannot silently redirect where the test writes) and others
    deliberately let through. There is no single default that is right for
    every caller, so callers name their own set explicitly rather than
    inheriting one that happens to fit some other test.
    """
    env = {key: value for key, value in os.environ.items() if not key.startswith(tuple(strip_prefixes))}
    env.update({"PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"})
    if extra:
        env.update(extra)
    return env


def run_subprocess_cli_harness(
    harness_source: str,
    args: Sequence[str],
    *,
    env_strip_prefixes: Sequence[str] = ("AEAT_", "PYTEST_"),
    extra_env: Mapping[str, str] | None = None,
    cwd: Path | None = None,
    stdin_payload: str | None = None,
    timeout: float = 120.0,
) -> subprocess.CompletedProcess[str]:
    """Run ``harness_source`` as a fresh ``python -c`` child and capture its output.

    The raw transport shared by every fresh-interpreter CLI harness in this
    tree, regardless of how the harness source pins its own ``Settings``.
    ``args`` is appended to argv after the harness source itself, so a
    harness reading ``sys.argv[1:]`` for its own purposes (see
    :data:`_CONTEXTVAR_HARNESS_SOURCE`) controls how those positions are
    interpreted.
    """
    return subprocess.run(
        [sys.executable, "-c", harness_source, *args],
        cwd=cwd or SRC_CADRUMO,
        env=subprocess_cli_env(strip_prefixes=env_strip_prefixes, extra=extra_env),
        input=stdin_payload,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
        timeout=timeout,
    )


def _json_safe(value: object) -> object:
    """Coerce a settings-override value into something ``json.dumps`` accepts.

    Callers build settings overrides the same way they would hand them
    straight to ``Settings(...)`` -- ``Path`` values included -- so this
    converts only what JSON cannot already carry, recursively for nested
    mappings.
    """
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Mapping):
        return {key: _json_safe(item) for key, item in value.items()}
    return value


def run_cadrumo_subprocess(
    args: Sequence[str],
    *,
    settings: Mapping[str, object],
    expected_storage_route_kind: StorageRouteKind | None = None,
    env_strip_prefixes: Sequence[str] = ("AEAT_", "PYTEST_"),
    extra_env: Mapping[str, str] | None = None,
    cwd: Path | None = None,
    stdin_payload: str | None = None,
    timeout: float = 120.0,
) -> subprocess.CompletedProcess[str]:
    """Run one real ``cadrumo`` CLI invocation in a fresh interpreter.

    The child constructs ``Settings(_env_file=None, **settings)`` and
    registers it on the ``_settings_override`` ContextVar before importing
    and calling ``cadrumo.entrypoints.cli.main`` -- the mechanism three
    independent harnesses converged on. ``settings`` takes exactly the
    keyword arguments a caller would otherwise pass to ``Settings(...)``
    directly; ``Path`` values are accepted and stringified for the JSON
    transport.

    When ``expected_storage_route_kind`` is given, the child asserts
    ``classify_storage_route().kind`` equals it BEFORE calling ``main()`` --
    a precondition proving the route the test relies on is the one actually
    in effect, not merely one that happens to produce the same behaviour.

    ``env_strip_prefixes`` and ``extra_env`` are forwarded to
    :func:`subprocess_cli_env` unchanged; callers state their own prefix set
    explicitly (see its docstring for why there is no shared default).
    """
    payload = json.dumps(
        {
            "settings": _json_safe(dict(settings)),
            "expected_storage_route_kind": None
            if expected_storage_route_kind is None
            else expected_storage_route_kind.name,
        },
    )
    return run_subprocess_cli_harness(
        _CONTEXTVAR_HARNESS_SOURCE,
        [payload, *args],
        env_strip_prefixes=env_strip_prefixes,
        extra_env=extra_env,
        cwd=cwd,
        stdin_payload=stdin_payload,
        timeout=timeout,
    )
