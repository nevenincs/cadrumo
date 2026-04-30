"""Step 7 keystone driver — execute the hexagonal layout move.

Per the restructure ADR (`.vault/adr/2026-04-30-aeat-restructure-adr.md`)
this is the one-shot mechanical relocator that:

1. Materialises the new package directory tree.
2. Moves every old subpackage / top-level file to its destination
   per `scripts/restructure_rewrite_map.json`.
3. Rewrites every absolute import path via `rebase_imports.py`.
4. Fixes relative imports inside moved files via
   `fix_relative_imports.py`.
5. Authors re-export shim ``__init__.py`` files at the OLD canonical
   public-surface locations so existing consumers keep working.

Self-protection: the rewriter is configured to skip the literal
strings inside this driver script's own constant tables — those
must stay in OLD form so the driver remains correct after the move.

Usage:

    uv run --no-sync python scripts/run_layout_move.py [--apply]
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PKG_ROOT = REPO_ROOT / "src" / "aeat"
REWRITE_MAP_PATH = REPO_ROOT / "scripts" / "restructure_rewrite_map.json"
REBASE_SCRIPT = REPO_ROOT / "scripts" / "rebase_imports.py"
FIX_RELATIVE_SCRIPT = REPO_ROOT / "scripts" / "fix_relative_imports.py"

NEW_PACKAGE_DIRS = (
    "core",
    "domain",
    "adapters",
    "adapters/inbound",
    "adapters/outbound",
    "adapters/outbound/aeat",
    "adapters/persistence",
    "application",
    "entrypoints",
)

TOP_LEVEL_FILE_MOVES: dict[str, str] = {
    "_click_context.py": "core/click_context.py",
    "_json_contract.py": "core/json_contract.py",
    "_paths.py": "core/paths.py",
    "_test_paths.py": "core/_test_paths.py",
    "config.py": "core/config.py",
    "env_io.py": "core/env_io.py",
    "logging.py": "core/logging.py",
    "test_logging.py": "core/test_logging.py",
    "_test_auth.py": "core/_test_auth.py",
    "_test_env_io.py": "core/_test_env_io.py",
}

SUBPACKAGE_MOVES: dict[str, str] = {
    "errors": "core/errors",
    "i18n": "core/i18n",
    "observability": "core/observability",
    "_pdf_import": "adapters/inbound/pdf",
    "borrador": "adapters/inbound/borrador",
    "declaracion": "adapters/inbound/declaracion",
    "identity": "adapters/inbound/identity",
    "sanitizer": "adapters/inbound/sanitizer",
    "casillas": "domain/casillas",
    "deadlines": "domain/deadlines",
    "formulas": "domain/formulas",
    "manuals": "domain/manuals",
    "models": "domain/modelos",
    "normatives": "domain/normatives",
    "portals": "domain/portals",
    "profile": "domain/profile",
    "rental": "domain/rental",
    "testing": "domain/testing",
    "justificante": "domain/justificante",
    "schema": "domain/schema",
    "auth": "adapters/outbound/aeat/auth",
    "browser": "adapters/outbound/aeat/browser",
    "sede": "adapters/outbound/aeat/sede",
    "submission": "adapters/outbound/aeat/export",
    "llm": "adapters/outbound/llm",
    "storage": "adapters/persistence/storage",
    "filing": "application/filing",
    "review": "application/review",
    "setup": "application/setup",
    "sync": "application/sync",
    "verification": "application/verification",
    "workflow": "application/workflow",
    "financial": "domain/financial",
    "cli": "entrypoints/cli",
    "mcp": "entrypoints/mcp",
}

# Public-surface shim destinations declared as a list of (OLD, NEW) tuples
# rather than dict-with-aeat-prefixed-strings so the rewriter cannot misfire
# on the dict literal. The OLD subpackage name is the first segment of the
# OLD dotted path; the rewriter does not match short subpackage names without
# the "aeat." prefix.
SHIM_TARGETS: tuple[tuple[str, str], ...] = (
    ("errors", "aeat.core.errors"),
    ("auth", "aeat.adapters.outbound.aeat.auth"),
    ("submission", "aeat.adapters.outbound.aeat.export"),
    ("formulas", "aeat.domain.formulas"),
)


def materialise_new_dirs(*, apply: bool) -> list[str]:
    created: list[str] = []
    for rel in NEW_PACKAGE_DIRS:
        target = PKG_ROOT / rel
        init = target / "__init__.py"
        if not target.exists():
            if apply:
                target.mkdir(parents=True, exist_ok=True)
            created.append(f"  mkdir {target.relative_to(REPO_ROOT)}")
        if not init.exists():
            if apply:
                init.write_text(f'"""Layered package marker — see {rel}/."""\n', encoding="utf-8")
            created.append(f"  init  {init.relative_to(REPO_ROOT)}")
    return created


def move_top_level_files(*, apply: bool) -> list[str]:
    moves: list[str] = []
    for old_name, new_rel in TOP_LEVEL_FILE_MOVES.items():
        old_path = PKG_ROOT / old_name
        new_path = PKG_ROOT / new_rel
        if not old_path.exists():
            continue
        if apply:
            new_path.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run(  # noqa: S603
                ["git", "mv", str(old_path), str(new_path)],  # noqa: S607
                cwd=REPO_ROOT,
                check=True,
            )
        moves.append(f"  mv {old_path.relative_to(REPO_ROOT)} -> {new_path.relative_to(REPO_ROOT)}")
    return moves


def move_subpackages(*, apply: bool) -> list[str]:
    moves: list[str] = []
    for old_name, new_rel in SUBPACKAGE_MOVES.items():
        old_path = PKG_ROOT / old_name
        new_path = PKG_ROOT / new_rel
        if not old_path.exists() or not old_path.is_dir():
            continue
        if apply:
            new_path.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run(  # noqa: S603
                ["git", "mv", str(old_path), str(new_path)],  # noqa: S607
                cwd=REPO_ROOT,
                check=True,
            )
        moves.append(f"  mv {old_path.relative_to(REPO_ROOT)} -> {new_path.relative_to(REPO_ROOT)}")
    return moves


def rewrite_absolute_imports(*, apply: bool) -> list[str]:
    if not apply:
        return ["  (skipped — dry-run)"]
    targets = [
        REPO_ROOT / "src" / "aeat",
        REPO_ROOT / "tests",
        REPO_ROOT / "pyproject.toml",
        REPO_ROOT / "justfile",
        REPO_ROOT / ".mcp.json",
    ]
    cmd = [sys.executable, str(REBASE_SCRIPT), "--apply", *[str(t) for t in targets if t.exists()]]
    result = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True, check=False)  # noqa: S603
    return [f"  exit={result.returncode}", *(result.stdout or "").splitlines()[-5:]]


def fix_relative_imports(*, apply: bool) -> list[str]:
    if not apply:
        return ["  (skipped — dry-run)"]
    cmd = [sys.executable, str(FIX_RELATIVE_SCRIPT), "--apply", str(PKG_ROOT)]
    result = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True, check=False)  # noqa: S603
    return [f"  exit={result.returncode}", *(result.stdout or "").splitlines()[-5:]]


def write_shims(*, apply: bool) -> list[str]:
    written: list[str] = []
    for old_subpkg, new_dotted in SHIM_TARGETS:
        old_path = PKG_ROOT / old_subpkg
        if old_path.exists():
            continue
        if apply:
            old_path.mkdir(parents=True, exist_ok=True)
            old_dotted = "aeat." + old_subpkg
            shim_body = (
                f'"""Public-surface re-export shim for the {old_subpkg} package.\n'
                "\n"
                f"Canonical location moved to :mod:`{new_dotted}` per the\n"
                "aeat-restructure ADR (Public surface and semver).\n"
                '"""\n'
                "from __future__ import annotations\n"
                "\n"
                "import warnings as _warnings\n"
                "\n"
                f"_warnings.warn(\n"
                f'    "Importing from `{old_dotted}` is deprecated; use `{new_dotted}` instead.",\n'
                "    DeprecationWarning,\n"
                "    stacklevel=2,\n"
                ")\n"
                "\n"
                f"from {new_dotted} import *  # noqa: F401, F403\n"
                f"from {new_dotted} import __all__  # noqa: F401\n"
            )
            (old_path / "__init__.py").write_text(shim_body, encoding="utf-8")
        written.append(f"  shim {old_path.relative_to(REPO_ROOT)} -> {new_dotted}")
    return written


def report(title: str, lines: list[str]) -> None:
    print(f"\n=== {title} ({len(lines)} entries) ===")  # noqa: T201
    for line in lines:
        print(line)  # noqa: T201


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Execute the move (default: dry-run).")
    args = parser.parse_args(argv)

    if not REWRITE_MAP_PATH.exists():
        print(f"ERROR: rewrite map missing at {REWRITE_MAP_PATH}", file=sys.stderr)  # noqa: T201
        return 1

    mode = "APPLY" if args.apply else "DRY-RUN"
    print(f"Step 7 layout-move driver — mode={mode}")  # noqa: T201

    report("1. Materialise new package directories", materialise_new_dirs(apply=args.apply))
    report("2. Move top-level files", move_top_level_files(apply=args.apply))
    report("3. Move subpackages", move_subpackages(apply=args.apply))
    report("4. Rewrite absolute imports", rewrite_absolute_imports(apply=args.apply))
    report("5. Fix relative imports inside moved files", fix_relative_imports(apply=args.apply))
    report("6. Author public-surface shims", write_shims(apply=args.apply))

    return 0


if __name__ == "__main__":
    sys.exit(main())
