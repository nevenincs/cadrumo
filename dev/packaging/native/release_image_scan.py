"""Refuse a staged release package that knows about a source checkout, its builder or a retired storage override.

Every image resolves storage from the one storage variable, which names an absolute directory,
or from the per-user default; no build bakes a root in. So no product-owned file of a release
package may name a storage variable the package declaration retired, the former development
default root, the checkout the build ran in or the home directory of the account that built it,
which names that account. Third-party payloads (the Python standard library
and dependencies, the Node runtime and modules) are outside this product's control and are not
scanned.
"""

from __future__ import annotations

import argparse
import sys
import tomllib
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path, PurePath

_PRODUCT_PREFIX = "cadrumo"
# Directories whose members are third-party except the product's own entries.
_VENDORED_PARENTS = frozenset({"site-packages", "node_modules", "packages"})
# Third-party files and trees the package carries verbatim.
_VENDORED_NAMES = frozenset({"python.zip", "node"})
_NATIVE_SUFFIXES = frozenset({".exe", ".dll", ".so", ".dylib", ".pyd"})
# CADRUMO_STORAGE_ROOT is the only variable that places storage. Every other storage variable the
# package once declared is retired for good, whichever surface used to read it.
RETIRED_STORAGE_VARIABLES = tuple(
    tomllib.loads(Path(__file__).with_name("retired_storage_variables.toml").read_text(encoding="utf-8"))[
        "retired_storage_variables"
    ]
)
_DEVELOPMENT_DEFAULT = ("var", "storage")
BUILDER_HOME = "builder home directory"


@dataclass(frozen=True)
class Finding:
    """One product-owned file that spells a development-only fact."""

    path: PurePath
    fact: str


def _path_spellings(path: Path) -> tuple[str, ...]:
    native = str(path)
    return tuple(dict.fromkeys((native, path.as_posix(), native.replace("\\", "\\\\"))))


def _names_an_account(home: Path) -> bool:
    # A home directly beneath a filesystem root, such as a service account's, names no person and
    # is too short a string to tell from ordinary text.
    return home.is_absolute() and len(home.parts) > 2


def development_spellings(checkout: Path, home: Path | None = None) -> dict[str, tuple[str, ...]]:
    """Every development-only fact a release image must not carry, by every spelling it can take.

    ``home`` is the home directory of the account that built the package; without one, or with
    one that names no account, no builder fact is looked for.
    """
    default = _DEVELOPMENT_DEFAULT
    spellings = {
        **{f"retired storage variable {name}": (name,) for name in RETIRED_STORAGE_VARIABLES},
        "development storage default": ("/".join(default), "\\".join(default), "\\\\".join(default)),
        "checkout path": _path_spellings(checkout),
    }
    if home is not None and _names_an_account(home):
        spellings[BUILDER_HOME] = _path_spellings(home)
    return spellings


def _encodings(spelling: str) -> tuple[bytes, ...]:
    # Native images also hold UTF-16 wide strings; paths compare case-insensitively.
    lowered = spelling.lower()
    return (lowered.encode("utf-8"), lowered.encode("utf-16-le"))


def _vendored(relative: PurePath) -> bool:
    parts = relative.parts
    if parts and parts[-1] in _VENDORED_NAMES:
        return True
    for index, part in enumerate(parts[:-1]):
        if part in _VENDORED_NAMES:
            return True
        if part in _VENDORED_PARENTS:
            member = parts[index + 1].lstrip("@")
            return not member.startswith(_PRODUCT_PREFIX)
    # A native library at the package's top levels is the product's only when it says so.
    return relative.suffix.lower() in _NATIVE_SUFFIXES - {".exe"} and not relative.name.startswith(_PRODUCT_PREFIX)


def product_files(package: Path) -> Iterator[Path]:
    """The package's product-owned files, in a stable order."""
    for path in sorted(package.rglob("*")):
        if path.is_file() and not path.is_symlink() and not _vendored(path.relative_to(package)):
            yield path


def scan(package: Path, checkout: Path, home: Path | None = None) -> list[Finding]:
    """Name every product-owned file of ``package`` that spells a development-only fact."""
    needles = {
        fact: tuple(encoded for spelling in spellings for encoded in _encodings(spelling))
        for fact, spellings in development_spellings(checkout, home).items()
    }
    findings: list[Finding] = []
    for path in product_files(package):
        content = path.read_bytes().lower()
        relative = PurePath(path.relative_to(package))
        findings.extend(
            Finding(relative, fact) for fact, encoded in needles.items() if any(needle in content for needle in encoded)
        )
    return findings


def main(argv: list[str] | None = None) -> int:
    """Scan one staged release package; exit 1 when it names a development-only fact."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path, required=True, help="the staged release package root")
    parser.add_argument("--checkout", type=Path, required=True, help="the checkout the package was built from")
    parser.add_argument(
        "--home", type=Path, default=Path.home(), help="the home directory of the account that built the package"
    )
    args = parser.parse_args(argv)
    package = args.package.resolve(strict=True)
    findings = scan(package, args.checkout.resolve(strict=True), args.home)
    for finding in findings:
        print(f"{finding.path.as_posix()}: {finding.fact}")
    if findings:
        print(f"{len(findings)} development-only facts in the release package {package}", file=sys.stderr)
        return 1
    print(f"The release package {package} names no development storage rule, checkout or builder")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
