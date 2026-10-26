"""Canonical paths shared by the casilla-lineage analysis tools."""

from __future__ import annotations

from pathlib import Path

_UTF_8 = "utf-8"
_ANALYSIS_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _ANALYSIS_DIR.parents[2]
_DATA_ROOT = _REPO_ROOT / "src" / "cadrumo" / "_data"
_REGISTRY_ROOT = _DATA_ROOT / "registry" / "aeat"
_MODELOS_ROOT = _REGISTRY_ROOT / "modelos"
RULINGS_PATH = _ANALYSIS_DIR / "casilla_lineage_rulings.toml"
LEDGER_PATH = _ANALYSIS_DIR / "casilla_lineage_ledger.toml"
