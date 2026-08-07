"""Canonical roots the locale tooling reads, resolved from the repository checkout.

The tooling lives outside the package it maintains, so neither root can be
derived from this module's own parent. Both the catalogue YAML and the ``tr()``
call sites the key scan walks stay under ``src/cadrumo``, and every consumer --
the CLI and the tooling's own suites -- resolves them here rather than
re-deriving a parent count locally. A wrong count does not raise: the scan
returns an empty key set, which reads exactly like a clean tree.

``importlib.resources`` would reach the catalogues but not the source tree, so a
single checkout-relative derivation covers both.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[2]
SRC_DIR: Final[Path] = REPO_ROOT / "src" / "cadrumo"
LOCALES_DIR: Final[Path] = SRC_DIR / "locales"
