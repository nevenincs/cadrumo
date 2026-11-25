"""Canonical paths shared by the casilla-lineage analysis tools."""

from __future__ import annotations

from pathlib import Path

UTF_8 = "utf-8"
_ANALYSIS_DIR = Path(__file__).resolve().parent
REPO_ROOT = _ANALYSIS_DIR.parents[2]
DATA_ROOT = REPO_ROOT / "src" / "cadrumo" / "_data"
REGISTRY_ROOT = DATA_ROOT / "registry" / "aeat"
MODELOS_ROOT = REGISTRY_ROOT / "modelos"
RULINGS_PATH = _ANALYSIS_DIR / "casilla_lineage_rulings.toml"
LEDGER_PATH = _ANALYSIS_DIR / "casilla_lineage_ledger.toml"
