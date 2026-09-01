"""Minimal dotenv-style parser used by the pytest collection hook.

This module is test-infrastructure (not a production module) and is
imported by the repo-root ``conftest.py`` to populate ``os.environ``
from ``env/.env`` so the ``CADRUMO_LIVE_TESTS_ENABLED`` gate (and every
other ``Settings`` field an operator configures for local live-test runs)
matches the value the rest of the project's environment-only ``Settings``
stack reads. Production ``Settings`` carries no dotenv source of its own
(``core.config.Settings.settings_customise_sources`` never returns a
dotenv source); ``env/.env`` is development/test-only configuration, and
this module is the bridge that makes it visible to a process that
constructs ``Settings`` from ``os.environ``.

Pure: no I/O beyond reading the file passed in. No shell expansion,
no substitution, no pyproject magic — by design. The parser deliberately
mirrors the subset of dotenv syntax that ``env/.env.example`` uses:

- ``KEY=value`` pairs, one per line.
- Comments start with ``#`` (full-line or end-of-line, but only when
  preceded by whitespace).
- Blank lines are ignored.
- Surrounding double quotes on the value are stripped (so
  ``KEY="value"`` becomes ``value``).
- Lines without ``=`` are ignored.
- Whitespace around the key and value is trimmed.

Anything more (multiline values, ``$VAR`` substitution, escapes) is
deliberately out of scope; if a future env var needs them we add them
here with a colocated test.
"""

from __future__ import annotations

import os
from pathlib import Path

from ..core.external_constants import UTF_8_ENCODING


def parse_env_text(text: str) -> dict[str, str]:
    """Parse the given text into a ``{KEY: value}`` mapping.

    Pure function — accepts the file contents directly so the test
    suite can exercise it without touching the filesystem.

    Args:
        text: Contents of a dotenv-style file.

    Returns:
        A mapping of recognised ``KEY=value`` pairs, in file order.
    """
    pairs: dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if not key:
            continue
        # Strip a single trailing inline comment (only if the ``#`` is
        # preceded by whitespace and is not inside a quoted value).
        if not value.startswith(('"', "'")):
            hash_idx = value.find(" #")
            if hash_idx != -1:
                value = value[:hash_idx]
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
            value = value[1:-1]
        pairs[key] = value
    return pairs


def load_env_file(path: Path) -> dict[str, str]:
    """Read ``path`` from disk and return its parsed mapping.

    Returns an empty dict if the file does not exist; never raises on
    a missing file. Read errors propagate so the caller (conftest.py)
    sees a clear ``OSError`` rather than a silent skip.
    """
    if not path.exists():
        return {}
    return parse_env_text(path.read_text(encoding=UTF_8_ENCODING))


def bridge_env_file_into_environ(path: Path) -> dict[str, str]:
    """Load ``path`` and apply every pair to ``os.environ`` via ``setdefault``.

    A real ambient environment variable already present in ``os.environ``
    before this call always wins: the dotfile only fills gaps a shell or
    CI environment left unset, it never overrides one. This mirrors the
    precedence pydantic-settings' own ``DotEnvSettingsSource`` gives a
    dotenv file relative to the process environment, so the bridged
    values behave the same way production ``Settings`` used to treat
    ``env/.env`` before dotenv support was removed from production.

    A no-op — returns ``{}``, mutates nothing — when ``path`` does not
    exist (a fresh clone, CI, an installed run). Never raises on a
    missing file; never fabricates a value.

    Returns the full mapping ``path`` declared, regardless of whether a
    given key actually took effect (i.e. even keys shadowed by an
    ambient override are included), so a caller can inspect what the
    file offered without a second parse.
    """
    pairs = load_env_file(path)
    for key, value in pairs.items():
        os.environ.setdefault(key, value)
    return pairs


__all__ = ["bridge_env_file_into_environ", "load_env_file", "parse_env_text"]
