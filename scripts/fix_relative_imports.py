"""Post-layout-move relative-import resolver.

Companion to ``scripts/rebase_imports.py``. After the keystone move
has relocated files to their new homes via ``git mv``, every
**relative** ``from .X`` / ``from ..X.Y`` import inside a moved file
still resolves against the file's OLD package home and so points at
modules that no longer exist (or have been renamed).

This script walks every Python source file under ``src/aeat/`` and:

1. Determines the file's NEW dotted package path from its on-disk
   location.
2. Determines its OLD dotted package path by reverse-lookup in the
   rewrite map.
3. For each ``from .X`` / ``from ..X`` import in the file:
   a. Resolves it to an absolute dotted path under the OLD home.
   b. Looks the absolute path up in the forward rewrite map.
   c. If found, computes the new relative path from the file's NEW
      home to the import target's NEW home.
   d. Rewrites the import line in place.

The script is idempotent: if a relative import already resolves
correctly under the NEW layout (no rewrite-map entry hit), it is left
untouched.

Usage:

    uv run --no-sync python scripts/fix_relative_imports.py [--apply]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PKG_ROOT = REPO_ROOT / "src" / "aeat"
REWRITE_MAP_PATH = REPO_ROOT / "scripts" / "restructure_rewrite_map.json"


def load_rewrite_map() -> tuple[dict[str, str], dict[str, str]]:
    """Return (forward, reverse) dotted-path maps."""
    payload = json.loads(REWRITE_MAP_PATH.read_text(encoding="utf-8"))
    forward = payload["rename"]
    reverse = {v: k for k, v in forward.items()}
    return forward, reverse


def file_to_dotted(path: Path) -> str:
    """Return ``aeat.subpkg.module`` for an on-disk source file under PKG_ROOT."""
    rel = path.relative_to(PKG_ROOT.parent)  # under src/, so rel starts with `aeat/`
    parts = list(rel.with_suffix("").parts)
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def resolve_old_dotted(new_dotted: str, reverse: dict[str, str]) -> str:
    """Translate a NEW dotted module path back to its OLD form using reverse map."""
    # Longest-prefix-first match against reverse map keys.
    sorted_keys = sorted(reverse.keys(), key=len, reverse=True)
    for new_prefix in sorted_keys:
        if new_dotted == new_prefix or new_dotted.startswith(new_prefix + "."):
            old_prefix = reverse[new_prefix]
            return old_prefix + new_dotted[len(new_prefix) :]
    return new_dotted


def map_old_to_new(old_dotted: str, forward: dict[str, str]) -> str:
    """Translate an OLD dotted module path to its NEW form using forward map."""
    sorted_keys = sorted(forward.keys(), key=len, reverse=True)
    for old_prefix in sorted_keys:
        if old_dotted == old_prefix or old_dotted.startswith(old_prefix + "."):
            new_prefix = forward[old_prefix]
            return new_prefix + old_dotted[len(old_prefix) :]
    return old_dotted


def resolve_relative_to_absolute(file_dotted: str, dots: int, sub: str) -> str:
    """Compute the absolute dotted path a relative import resolves to.

    Args:
        file_dotted: The package containing the file (e.g. ``aeat.core``
            for a file at ``aeat/core/config.py``).
        dots: Number of leading dots in the relative import.
        sub: The dotted suffix after the dots (may be empty for ``from . import X``).

    Returns:
        The absolute dotted path the relative import resolves to.
    """
    parts = file_dotted.split(".")
    # `dots = 1` means same package; `dots = 2` means parent; etc.
    base = parts[: len(parts) - (dots - 1)] if dots > 1 else parts
    if sub:
        base = base + sub.split(".")
    return ".".join(base)


def absolute_to_relative(target_abs: str, file_dotted: str) -> str | None:
    """Compute a `.x` / `..x.y` form for ``target_abs`` relative to ``file_dotted``.

    Returns the relative form (e.g. ``"..core.paths"``) or None if
    the absolute target cannot be expressed as relative (i.e. they
    share no common ancestor under ``aeat``).
    """
    file_parts = file_dotted.split(".")
    target_parts = target_abs.split(".")
    # Must share at least the `aeat` root.
    if not target_parts or target_parts[0] != "aeat":
        return None
    # Find the longest common prefix.
    common = 0
    for fp, tp in zip(file_parts, target_parts, strict=False):
        if fp == tp:
            common += 1
        else:
            break
    if common == 0:
        return None
    # Number of `..` to climb from file's package to common ancestor.
    up = len(file_parts) - common
    dots = "." * (up + 1)  # +1 because `from .` is one dot for sibling
    suffix = ".".join(target_parts[common:])
    return dots + suffix


_RELATIVE_IMPORT_RE = re.compile(
    r"^(?P<lead>\s*from\s+)(?P<dots>\.+)(?P<sub>[\w.]*)(?P<tail>\s+import\s+.+)$",
    re.MULTILINE,
)


def rewrite_file(path: Path, forward: dict[str, str], reverse: dict[str, str]) -> tuple[bool, str]:
    """Rewrite relative imports in ``path`` per the rewrite map.

    Returns ``(changed, message)``.
    """
    try:
        original = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return False, f"{path}: read error ({exc})"

    new_dotted = file_to_dotted(path)
    is_init = path.name == "__init__.py"
    # For __init__.py the file_to_dotted already returns the package path;
    # otherwise strip the module suffix to get the containing package.
    if is_init:
        new_pkg_dotted = new_dotted
    else:
        new_pkg_dotted = ".".join(new_dotted.split(".")[:-1]) if "." in new_dotted else new_dotted
    old_dotted = resolve_old_dotted(new_dotted, reverse)
    if is_init:
        old_pkg_dotted = old_dotted
    else:
        old_pkg_dotted = ".".join(old_dotted.split(".")[:-1]) if "." in old_dotted else old_dotted

    def _replace(match: re.Match[str]) -> str:
        dots = match.group("dots")
        sub = match.group("sub")
        target_abs_old = resolve_relative_to_absolute(old_pkg_dotted, len(dots), sub)
        target_abs_new = map_old_to_new(target_abs_old, forward)
        # If no rewrite-map hit AND the package is unchanged, leave alone.
        if target_abs_new == target_abs_old and new_pkg_dotted == old_pkg_dotted:
            return match.group(0)
        new_relative = absolute_to_relative(target_abs_new, new_pkg_dotted)
        if new_relative is None:
            return match.group(0)
        return f"{match.group('lead')}{new_relative}{match.group('tail')}"

    rewritten = _RELATIVE_IMPORT_RE.sub(_replace, original)

    if rewritten == original:
        return False, f"{path}: unchanged"
    return True, f"{path}: rewritten"


def iter_python_files(root: Path) -> list[Path]:
    """Walk ``root`` and yield every .py file."""
    return sorted(p for p in root.rglob("*.py") if p.is_file() and "__pycache__" not in p.parts)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Write changes in place.")
    parser.add_argument("paths", nargs="*", type=Path, default=[PKG_ROOT])
    args = parser.parse_args(argv)

    forward, reverse = load_rewrite_map()
    targets: list[Path] = []
    for p in args.paths:
        if p.is_file():
            targets.append(p)
        else:
            targets.extend(iter_python_files(p))

    changed = 0
    for path in targets:
        is_changed, message = rewrite_file(path, forward, reverse)
        if is_changed:
            if args.apply:
                # Re-run with capture-and-write semantics.
                original = path.read_text(encoding="utf-8")
                new_dotted = file_to_dotted(path)
                is_init = path.name == "__init__.py"
                if is_init:
                    new_pkg_dotted = new_dotted
                else:
                    new_pkg_dotted = ".".join(new_dotted.split(".")[:-1]) if "." in new_dotted else new_dotted
                old_dotted = resolve_old_dotted(new_dotted, reverse)
                if is_init:
                    old_pkg_dotted = old_dotted
                else:
                    old_pkg_dotted = ".".join(old_dotted.split(".")[:-1]) if "." in old_dotted else old_dotted

                def _replace2(
                    match: re.Match[str],
                    _old=old_pkg_dotted,
                    _new=new_pkg_dotted,
                ) -> str:
                    dots = match.group("dots")
                    sub = match.group("sub")
                    target_abs_old = resolve_relative_to_absolute(_old, len(dots), sub)
                    target_abs_new = map_old_to_new(target_abs_old, forward)
                    if target_abs_new == target_abs_old and _new == _old:
                        return match.group(0)
                    new_relative = absolute_to_relative(target_abs_new, _new)
                    if new_relative is None:
                        return match.group(0)
                    return f"{match.group('lead')}{new_relative}{match.group('tail')}"

                rewritten = _RELATIVE_IMPORT_RE.sub(_replace2, original)
                path.write_text(rewritten, encoding="utf-8")
            changed += 1
            print(message)  # noqa: T201
    print(f"\nfix_relative_imports: {changed} file(s) changed of {len(targets)}.")  # noqa: T201
    return 0


if __name__ == "__main__":
    sys.exit(main())
