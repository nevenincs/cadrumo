"""Minimal dotenv-style parser used by the pytest collection hook.

This module is test-infrastructure (not a production module) and is
imported by the repo-root ``conftest.py`` to populate ``os.environ``
from ``env/.env`` so the ``AEAT_LIVE_TESTS_ENABLED`` gate matches the
value the rest of the project's pydantic-settings stack reads.

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


__all__ = ["load_env_file", "parse_env_text"]
