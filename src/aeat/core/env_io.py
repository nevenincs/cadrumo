"""Read and rewrite simple ``KEY=VALUE`` ``.env`` files in place.

The bootstrap workflow persists resource identifiers (Drive folder,
Sheets ID, Docs ID) back into ``env/.env`` after authenticated API
calls create them. This module provides a dependency-free reader and
writer that preserves comments, blank lines, and key ordering so
hand-edited annotations survive automated rewrites.

The implementation is intentionally minimal: it does not interpret
quoting, variable expansion, or multi-line values. ``env/.env`` is a
flat key/value file in this project and any deviation from that shape
is treated as an error.

The boundary is file persistence only. Runtime configuration still flows
through :class:`~aeat.core.config.Settings`, :func:`~aeat.core.config.load_settings`,
and :func:`~aeat.core.config.override_settings`; this module does not inspect or
mutate process environment variables.

The public surface is :func:`read_env_file`, :func:`write_env_var`, and
:func:`write_env_vars`; each takes a :class:`~pathlib.Path` target. Malformed
input raises :class:`~aeat.core.errors.CoreValidationError`, while writers use
:func:`_atomic_write_text` so the ``.env`` file is replaced atomically.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from .errors import CoreValidationError
from .logging import get_logger

_log = get_logger(__name__)


def _atomic_write_text(path: Path, text: str, *, encoding: str = "utf-8") -> None:
    """Atomically write ``text`` to ``path`` via tempfile + :func:`os.replace`.

    Mirrors the substrate's atomic-write discipline at
    :func:`aeat.adapters.persistence.storage.master_key._master_key.atomic_write_secure_bytes`.
    The plaintext ``env/.env`` payload is operator-controlled
    configuration, not a secret — but the durability story matters:
    :meth:`pathlib.Path.write_text` truncates the existing inode in
    place before writing, so a power-loss or ``SIGKILL`` between the
    truncate and the write completion leaves ``env/.env`` zero-length.
    The operator's certificate path / database URL / live-tests flag /
    storage roots silently revert to defaults, surfacing as an
    apparently-unprovisioned installation. Writing to a sibling tempfile
    and then calling :func:`os.replace` guarantees the dirent transition
    is atomic — a crash leaves either the old or the new file on disk,
    never a torn write.

    Args:
        path: Destination file path.
        text: Full file contents to write.
        encoding: Text encoding (defaults to UTF-8).
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    # Initialise tmp_path to None BEFORE the try so the finally
    # cleanup never hits an UnboundLocalError if NamedTemporaryFile
    # itself raises. Use try/finally (not try/except OSError) so a
    # KeyboardInterrupt or any other BaseException mid-write also
    # unlinks the orphan tempfile — a narrow ``except OSError`` arm
    # would leak the tempfile on non-OSError exceptions.
    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding=encoding,
            dir=path.parent,
            prefix=f"{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            tmp_path = Path(handle.name)
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
        try:  # pragma: no cover - defensive
            from .locks import fsync_parent_dir

            fsync_parent_dir(path)
        except Exception as fsync_exc:
            _log.debug(
                "env_io atomic_write: parent-dir fsync skipped for %s (%s)",
                path,
                fsync_exc,
                exc_info=True,
            )
    finally:
        if tmp_path is not None:
            tmp_path.unlink(missing_ok=True)


def read_env_file(path: Path) -> dict[str, str]:
    """Parse ``KEY=VALUE`` lines from an env file into a flat mapping.

    Comments and blank lines are skipped. Trailing newlines on values
    are stripped. Lines that look like ``KEY=`` (empty value) yield an
    empty string. The returned mapping is a file snapshot for setup and
    bootstrap workflows; it is not the effective runtime settings model.

    Args:
        path: Filesystem path to the env file.

    Returns:
        Mapping of variable name to its raw string value. Returns an
        empty mapping if the file does not exist.

    Raises:
        CoreValidationError: When a non-comment, non-blank line does
            not contain an ``=`` separator.
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
            raise CoreValidationError(msg)
        key, _, value = line.partition("=")
        result[key.strip()] = value.strip()
    return result


def write_env_var(path: Path, key: str, value: str) -> None:
    """Write or update a single ``KEY=VALUE`` entry in an env file.

    Existing comments and blank lines are preserved. If the key already
    exists, its line is rewritten in place. Otherwise the new entry is
    appended to the end of the file. The write goes through
    :func:`write_env_vars` so single-key updates share the same atomic file
    replacement path as batch updates.

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
    preserved verbatim. Keys absent from ``mapping`` are left untouched; this
    helper persists setup results without acting as an env-file normalizer or
    deleting operator annotations.

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
