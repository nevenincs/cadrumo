"""Verified staged catalogue installation and recovery."""

from __future__ import annotations

import shutil
import time
from collections.abc import Callable
from pathlib import Path
from typing import Final

from cadrumo.core.atomic_write import atomic_write_text

from ._paths import LOCALES_DIR, PENDING_CASILLA_INSTALL_DIR
from .casilla_catalogue_models import CollapseVerificationError

_INSTALL_ATTEMPTS: Final = 60


_INSTALL_BACKOFF_SECONDS: Final = 0.5


def resume_install(locales_dir: Path = LOCALES_DIR, pending_dir: Path = PENDING_CASILLA_INSTALL_DIR) -> None:
    """Install a verified staged catalogue and discard it once every shard is in place.

    Raises:
        CollapseVerificationError: No install is pending, or a shard could not be written.
    """
    staged = pending_dir / "locales"
    if not staged.is_dir():
        raise CollapseVerificationError(f"no install is pending at {pending_dir}")
    failed = _install_shards(staged, locales_dir)
    if failed:
        raise CollapseVerificationError(f"verified shards could not be installed, resume again: {failed}")
    _discard(pending_dir)


def _discard(pending_dir: Path) -> None:
    """Remove a staged catalogue, tolerating lock sidecars that vanish while it is walked."""

    def ignore_vanished(function: Callable[..., object], path: str, error: BaseException) -> None:
        if not isinstance(error, FileNotFoundError):
            raise error

    shutil.rmtree(pending_dir, onexc=ignore_vanished)


def _install_shards(staged: Path, locales_dir: Path) -> tuple[str, ...]:
    """Copy every changed Modelo schema shard from ``staged``; return the ones that failed."""
    failed: list[str] = []
    for source in sorted(staged.glob("*/modelo/schema/*.yml")):
        relative = source.relative_to(staged)
        target = locales_dir / relative
        payload = source.read_bytes()
        if target.is_file() and target.read_bytes() == payload:
            continue
        for _attempt in range(_INSTALL_ATTEMPTS):
            try:
                atomic_write_text(target, payload.decode("utf-8"))
                break
            except OSError:
                time.sleep(_INSTALL_BACKOFF_SECONDS)
        else:
            failed.append(relative.as_posix())
    return tuple(failed)
