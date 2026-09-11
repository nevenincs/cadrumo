"""Public compiled-registry cache operations for the development loader."""

from __future__ import annotations

from functools import cache
from pathlib import Path

from cadrumo.domain.calculations.registry.schema import ModeloDefinition, RegistryCatalogues

from ._compiled_cache import (
    _LOGGER,
    _decode_and_validate,
    _delete_cache_file,
    _encode_frame,
    _evict_stale_registry_pickles,
    _loader_code_fingerprint,
    _read_cache_bytes,
    _registry_disk_cache_key,
)
from .loader_cache import registry_disk_cache_dir

type CompiledRegistryPayload = tuple[tuple[ModeloDefinition, ...], RegistryCatalogues]
type FingerprintTuples = tuple[tuple[str, int, int, str], ...]


@cache
def loader_code_fingerprint() -> str:
    """Return the loader-source fingerprint, computed once on first use."""
    return _loader_code_fingerprint()


def compiled_cache_path(root: Path, fingerprints: FingerprintTuples) -> Path:
    """Return the compiled-cache file for ``root`` at the current fingerprint key."""
    key_hash = _registry_disk_cache_key(str(root), fingerprints)
    return registry_disk_cache_dir() / f"cadrumo_registry_{key_hash}.pkl"


def load_compiled_registry_cache(root: Path, fingerprints: FingerprintTuples) -> CompiledRegistryPayload | None:
    """Load a strictly validated compiled payload, or ``None`` to recompile."""
    path = compiled_cache_path(root, fingerprints)
    if not path.is_file():
        return None
    raw = _read_cache_bytes(path)
    if raw is None:
        return None
    payload = _decode_and_validate(raw)
    if payload is None:
        _delete_cache_file(path)
        return None
    return payload


def store_compiled_registry_cache(
    root: Path,
    fingerprints: FingerprintTuples,
    payload: CompiledRegistryPayload,
) -> None:
    """Persist a compiled payload at the current tree and loader-code key."""
    path = compiled_cache_path(root, fingerprints)
    frame = _encode_frame(payload)
    try:
        from cadrumo.core.atomic_write import atomic_write_best_effort_bytes

        atomic_write_best_effort_bytes(path, frame)
        _evict_stale_registry_pickles(path.parent, logger=_LOGGER)
    except Exception:
        _LOGGER.debug("Could not write compiled registry cache at %s", path, exc_info=True)


__all__ = [
    "CompiledRegistryPayload",
    "FingerprintTuples",
    "compiled_cache_path",
    "load_compiled_registry_cache",
    "loader_code_fingerprint",
    "store_compiled_registry_cache",
]
