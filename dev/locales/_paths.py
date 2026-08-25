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

from .._paths import REPO_ROOT

SRC_DIR: Final[Path] = REPO_ROOT / "src" / "cadrumo"
LOCALES_DIR: Final[Path] = SRC_DIR / "locales"

#: Roots outside the package that legitimately reference catalogue keys.
#:
#: The documentation generators render taxpayer-facing prose -- the chrome
#: around a casilla card, a legal provision and a glossary term -- so their
#: strings are product text and belong in the one catalogue authority, not in a
#: second store. They live under ``dev/`` only because the generators are build
#: tooling, and a scan that stopped at the package would report every one of
#: their keys as an extra key absent from the codebase.
#:
#: Scoped to ``dev/docs`` rather than ``dev``: the rest of the harness is
#: developer-facing, and its strings have no business in a catalogue that ships.
DOCS_SRC_DIR: Final[Path] = REPO_ROOT / "dev" / "docs"

#: The MCP harness (``cadrumo-mcp``) is a separate distribution living beside
#: ``src/cadrumo`` rather than inside it, but its operator-facing elicitation
#: prompts and refusal messages render through the same shared ``tr()``
#: catalogue (only its model-facing tool names and descriptions stay
#: deliberately unlocalized English). A scan that stopped at ``src/cadrumo``
#: would report every one of its catalogue keys as an extra key with no
#: codebase site, for exactly the reason :data:`DOCS_SRC_DIR` exists.
HARNESS_SRC_DIR: Final[Path] = REPO_ROOT / "src" / "cadrumo-harness" / "src" / "cadrumo_harness"
