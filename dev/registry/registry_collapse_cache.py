"""Isolated compiled-registry cache invalidation probes."""

from __future__ import annotations

import shutil
from collections.abc import Mapping
from pathlib import Path

import tomlkit
from tomlkit.items import Table

from dev.registry.compiler.loader import load_modelo_directory
from dev.registry.compiler.loader_cache import discover_modelo_sources

from .registry_collapse_comparison import _typed_projection
from .registry_collapse_models import _MODELOS, CheckStatus


def _cache_invalidation_probe(registry_root: Path, probe_root: Path) -> Mapping[str, object]:
    """Exercise warm reuse and source/support invalidation on isolated copies."""
    try:
        cold_warm_same_object, source_invalidated = _source_cache_invalidation(registry_root, probe_root)
        support_invalidated, support_detail = _support_cache_invalidation(registry_root, probe_root)
        status = CheckStatus.PASSED if source_invalidated and support_invalidated else CheckStatus.FAILED
        return {
            "status": status,
            "cold_warm_same_object": cold_warm_same_object,
            "source_change_invalidated": source_invalidated,
            "support_change_invalidated": support_invalidated,
            "detail": support_detail,
        }
    except Exception as exc:
        return {"status": CheckStatus.FAILED, "detail": f"{type(exc).__name__}: {exc}"}


def _source_cache_invalidation(registry_root: Path, probe_root: Path) -> tuple[bool, bool]:
    source = discover_modelo_sources(registry_root / _MODELOS)[0].path
    modelo_probe = probe_root / "modelo"
    shutil.copytree(source, modelo_probe)
    cold = load_modelo_directory(modelo_probe)
    warm = load_modelo_directory(modelo_probe)
    manifest = modelo_probe / "manifest.toml"
    manifest.write_text(manifest.read_text(encoding="utf-8") + "\n", encoding="utf-8", newline="\n")
    changed = load_modelo_directory(modelo_probe)
    cold_warm_same_object = cold is warm
    invalidated = (
        cold_warm_same_object and changed is not warm and _typed_projection(changed) == _typed_projection(warm)
    )
    return cold_warm_same_object, invalidated


def _support_cache_invalidation(registry_root: Path, probe_root: Path) -> tuple[bool, str | None]:
    from dev.registry.compiler.loader import load_shared_catalogues

    legal_probe = probe_root / "registry" / "legal"
    shutil.copytree(registry_root / "legal", legal_probe)
    support_before = load_shared_catalogues(legal_probe.parent).supported_filing_years
    support_file = _supported_years_file(legal_probe)
    document = tomlkit.parse(support_file.read_text(encoding="utf-8"))
    _extend_support_envelope(document["supported_filing_years"])
    support_file.write_text(tomlkit.dumps(document), encoding="utf-8", newline="\n")
    try:
        support_after = load_shared_catalogues(legal_probe.parent).supported_filing_years
        return _typed_projection(support_before) != _typed_projection(support_after), None
    except Exception as exc:
        return True, f"changed support metadata refused: {type(exc).__name__}: {exc}"


def _supported_years_file(legal_probe: Path) -> Path:
    return next(
        path
        for path in sorted(legal_probe.glob("*.toml"))
        if "[supported_filing_years]" in path.read_text(encoding="utf-8")
    )


def _extend_support_envelope(table: Table) -> None:
    floor, horizon = int(table["floor"]), int(table["horizon"])
    hard_ceiling = table.get("hard_ceiling")
    if hard_ceiling is None or horizon < int(hard_ceiling):
        table["horizon"] = horizon + 1
    elif floor < horizon:
        table["horizon"] = horizon - 1
    else:
        table["hard_ceiling"] = int(hard_ceiling) + 1
