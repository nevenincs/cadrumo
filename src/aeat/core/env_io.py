"""Read and rewrite simple ``KEY=VALUE`` ``.env`` files in place.

The bootstrap workflow needs to persist resource IDs (Drive folder,
Sheets ID, Docs ID) back into ``env/.env`` after authenticated API
calls create them. This module provides a tiny, dependency-free reader
and writer that preserves comments, blank lines, and key ordering so
hand-edited annotations survive automated rewrites.

The implementation is intentionally minimal: it does not interpret
quoting, variable expansion, or multi-line values. ``env/.env`` is a
flat key/value file in this project and any deviation from that shape
is treated as an error.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path


def _atomic_write_text(path: Path, text: str, *, encoding: str = "utf-8") -> None:
    """Atomically write ``text`` to ``path`` via tempfile + os.replace.

    Mirrors the substrate's atomic-write discipline at
    :func:`aeat.adapters.persistence.storage._master_key.atomic_write_secure_bytes`. The
    plaintext ``env/.env`` payload is operator-controlled
    configuration, not a secret — but the durability story matters:
    a ``path.write_text`` call truncates the existing inode in-place
    before writing, and a power-loss / SIGKILL between the truncate
    and the write completion leaves ``env/.env`` zero-length. The
    operator's certificate path / database URL / live-tests-flag /
    storage roots silently revert to defaults, surfacing as an
    apparently-unprovisioned installation. Use tempfile +
    ``os.replace`` so a crash leaves either the old or the new file
    on disk, never a torn write.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    # Initialise tmp_path to None BEFORE the try so the finally
    # cleanup never hits an UnboundLocalError if NamedTemporaryFile
    # itself raises. Use try/finally (not try/except OSError) so a
    # KeyboardInterrupt or any other BaseException mid-write also
    # unlinks the orphan tempfile. Issue #469 gemini-review MEDIUM
    # on PR #470: the previous narrow ``except OSError`` arm leaked
    # the tempfile on non-OSError exceptions.
    tmp_path: Path | None = None
    try:
        handle = tempfile.NamedTemporaryFile(  # noqa: SIM115 - context-managed via `with handle:` below
            mode="w",
            encoding=encoding,
            dir=path.parent,
            prefix=f"{path.name}.",
            suffix=".tmp",
            delete=False,
        )
        tmp_path = Path(handle.name)
        with handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, path)
        # On a successful os.replace the tempfile no longer exists
        # under tmp_path (it was renamed to ``path``). Clear the
        # local so the finally cleanup is a no-op.
        tmp_path = None
        # Best-effort parent-dir fsync. POSIX-only — the helper
        # imports lazily to avoid a hard dependency on the storage
        # substrate when env_io is used outside of a provisioned
        # install. Suppress every exception: directory fsync is a
        # durability hardening, not a correctness gate, and the
        # storage package may be unimportable in minimal install
        # contexts where env_io still runs.
        import contextlib

        with contextlib.suppress(Exception):  # pragma: no cover - defensive
            from ..adapters.persistence.storage._lock import fsync_parent_dir

            fsync_parent_dir(path)
    finally:
        if tmp_path is not None:
            tmp_path.unlink(missing_ok=True)


def read_env_file(path: Path) -> dict[str, str]:
    """Parse ``KEY=VALUE`` lines from an env file into a flat mapping.

    Comments and blank lines are skipped. Trailing newlines on values
    are stripped. Lines that look like ``KEY=`` (empty value) yield an
    empty string.

    Args:
        path: Filesystem path to the env file.

    Returns:
        Mapping of variable name to its raw string value. Returns an
        empty mapping if the file does not exist.
    """
    if not path.exists():
        return {}

    result: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            msg = f"Malformed env line in {path}: {raw_line!r}"
            raise ValueError(msg)
        key, _, value = line.partition("=")
        result[key.strip()] = value.strip()
    return result


def write_env_var(path: Path, key: str, value: str) -> None:
    """Write or update a single ``KEY=VALUE`` entry in an env file.

    Existing comments and blank lines are preserved. If the key already
    exists, its line is rewritten in place. Otherwise the new entry is
    appended to the end of the file.

    Args:
        path: Filesystem path to the env file. Created if missing.
        key: Variable name to write.
        value: String value to assign.
    """
    write_env_vars(path, {key: value})


def write_env_vars(path: Path, mapping: dict[str, str]) -> None:
    """Write or update multiple ``KEY=VALUE`` entries in an env file.

    Existing keys are rewritten in place; new keys are appended in the
    order given. Comments and blank lines in the existing file are
    preserved verbatim.

    Args:
        path: Filesystem path to the env file. Created if missing along
            with parent directories.
        mapping: Mapping of variable name to value to write.
    """
    path.parent.mkdir(parents=True, exist_ok=True)

    existing_lines: list[str] = []
    if path.exists():
        existing_lines = path.read_text(encoding="utf-8").splitlines()

    remaining = dict(mapping)
    rewritten: list[str] = []
    for raw_line in existing_lines:
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            rewritten.append(raw_line)
            continue
        key, _, _old_value = stripped.partition("=")
        key = key.strip()
        if key in remaining:
            rewritten.append(f"{key}={remaining.pop(key)}")
        else:
            rewritten.append(raw_line)

    for key, value in remaining.items():
        rewritten.append(f"{key}={value}")

    text = "\n".join(rewritten)
    if text and not text.endswith("\n"):
        text += "\n"
    _atomic_write_text(path, text)
