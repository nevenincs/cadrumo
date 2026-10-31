"""Load the pinned locale dictionaries used by the locale quality signal.

The dictionaries are pinned Hunspell data while the checker is the pure-Python
``spylls`` engine. Keeping discovery and validation here
gives the signal one deterministic boundary for setup failures: a missing
Python package, a partial ``node_modules`` tree, or a manually replaced
dictionary cannot become an unclassified import error or a silent change of
language data.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import TYPE_CHECKING, Final

from cadrumo.core.toml import parse_toml
from dev._paths import REPO_ROOT

if TYPE_CHECKING:
    from spylls.hunspell import Dictionary


@dataclass(frozen=True)
class DictionarySpec:
    """Describe one locale dictionary package declared by the repository."""

    locale: str
    package: str | None


# The first three are locked npm packages. Hungarian uses the pinned original
# source data: the npm normalization merges distinct words with morphology.
DICTIONARY_SPECS: Final[tuple[DictionarySpec, ...]] = (
    DictionarySpec("ca", "dictionary-ca"),
    DictionarySpec("en", "dictionary-en-gb"),
    DictionarySpec("es", "dictionary-es"),
    DictionarySpec("hu", None),
)


class SpellingToolError(RuntimeError):
    """Describe a spell-check setup or dictionary-load failure."""

    def __init__(self, *, kind: str, detail: str, next_action: str) -> None:
        super().__init__(detail)
        self.kind = kind
        self.detail = detail
        self.next_action = next_action


def dictionary_roots(repository: Path) -> dict[str, Path]:
    """Return the Hunspell file stems for every supported locale."""
    return {
        spec.locale: (
            repository / "node_modules" / spec.package / "index"
            if spec.package is not None
            else repository / "dev" / "locales" / "data" / "hunspell-hu" / "hu_HU"
        )
        for spec in DICTIONARY_SPECS
    }


def _manifest_versions(repository: Path) -> dict[str, str]:
    """Read exact dictionary versions from the repository npm manifest."""
    manifest = repository / "package.json"
    try:
        payload = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as exc:
        raise SpellingToolError(
            kind="spelling_tool_unavailable",
            detail=f"cannot read the pinned dictionary manifest {manifest}: {exc}",
            next_action="restore package.json and run just setup-locale-spelling",
        ) from exc
    dependencies = payload.get("devDependencies") if isinstance(payload, dict) else None
    if not isinstance(dependencies, dict):
        raise SpellingToolError(
            kind="spelling_tool_unavailable",
            detail=f"{manifest} has no devDependencies for the pinned locale dictionaries",
            next_action="restore package.json and run just setup-locale-spelling",
        )
    versions: dict[str, str] = {}
    missing = [
        spec.package
        for spec in DICTIONARY_SPECS
        if spec.package is not None and not isinstance(dependencies.get(spec.package), str)
    ]
    if missing:
        names = ", ".join(sorted(missing))
        raise SpellingToolError(
            kind="spelling_tool_unavailable",
            detail=f"{manifest} does not declare {names}",
            next_action="restore package.json and run just setup-locale-spelling",
        )
    for spec in DICTIONARY_SPECS:
        if spec.package is not None:
            versions[spec.package] = dependencies[spec.package]
    return versions


def _validate_dictionary_installation(repository: Path, roots: dict[str, Path]) -> None:
    """Reject absent, partial, or manifest-inconsistent dictionary packages."""
    declared_versions = _manifest_versions(repository)
    problems: list[str] = []
    for spec in DICTIONARY_SPECS:
        root = roots[spec.locale]
        if not root.with_suffix(".aff").is_file() or not root.with_suffix(".dic").is_file():
            problems.append(f"{spec.locale} dictionary is missing its affix or word data")
            continue
        if spec.package is None:
            _validate_vendored_dictionary(root, problems)
            continue
        _validate_package_metadata(root, spec.package, declared_versions[spec.package], problems)
    if problems:
        raise SpellingToolError(
            kind="spelling_tool_unavailable",
            detail="; ".join(problems),
            next_action="restore the tracked Hungarian data and run just setup-locale-spelling",
        )


def _validate_package_metadata(root: Path, package: str, declared_version: str, problems: list[str]) -> None:
    """Check that an installed npm dictionary is the declared package version."""
    try:
        payload = json.loads((root.parent / "package.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as exc:
        problems.append(f"{package} metadata cannot be read: {exc}")
        return
    actual_name = payload.get("name") if isinstance(payload, dict) else None
    actual_version = payload.get("version") if isinstance(payload, dict) else None
    if actual_name != package or actual_version != declared_version:
        problems.append(
            f"{package} metadata is {actual_name!r}@{actual_version!r}, "
            f"but package.json declares {package!r}@{declared_version!r}"
        )


def _validate_vendored_dictionary(root: Path, problems: list[str]) -> None:
    """Require both original data files to match their tracked source receipt."""
    try:
        receipt = json.loads((root.parent / "source.json").read_text(encoding="utf-8"))
        for suffix in ("aff", "dic"):
            expected = receipt[f"{suffix}_sha256"]
            actual = hashlib.sha256(root.with_suffix(f".{suffix}").read_bytes()).hexdigest()
            if not isinstance(expected, str) or actual != expected:
                problems.append(f"Hungarian {suffix} data does not match its source receipt")
    except (OSError, UnicodeError, ValueError, KeyError, TypeError) as exc:
        problems.append(f"Hungarian dictionary source receipt cannot be read: {exc}")


def locked_spylls_version() -> str:
    """Return the ``spylls`` version this checkout's lock resolved; the project declares only a range."""
    lock = parse_toml((REPO_ROOT / "uv.lock").read_text(encoding="utf-8"))
    versions = {str(entry["version"]) for entry in lock.get("package", ()) if entry.get("name") == "spylls"}
    if len(versions) != 1:
        raise SpellingToolError(
            kind="spelling_tool_unavailable",
            detail=f"uv.lock must resolve exactly one spylls version, found {sorted(versions)}",
            next_action="run uv lock to resolve the declared spell-check engine",
        )
    return versions.pop()


def load_dictionaries(repository: Path) -> dict[str, Dictionary]:
    """Load every pinned Hunspell dictionary through the pinned Python engine.

    Raises:
        SpellingToolError: if the Python engine or any dictionary package is
            unavailable, inconsistent with the manifest, or unreadable.
    """
    locked_version = locked_spylls_version()
    try:
        installed_version = version("spylls")
    except (ImportError, PackageNotFoundError):
        raise SpellingToolError(
            kind="spelling_tool_unavailable",
            detail=f"spylls=={locked_version} is not installed in the active Python environment",
            next_action="run just setup to install the locked spell-check engine",
        ) from None
    if installed_version != locked_version:
        raise SpellingToolError(
            kind="spelling_tool_unavailable",
            detail=f"active spylls is {installed_version}, but uv.lock resolves {locked_version}",
            next_action="run just setup to synchronize uv.lock",
        )

    roots = dictionary_roots(repository)
    _validate_dictionary_installation(repository, roots)
    content_key = _dictionary_content_key(installed_version, roots)
    loaded = _LOADED_DICTIONARIES.get(content_key)
    if loaded is not None:
        return dict(loaded)
    try:
        from spylls.hunspell import Dictionary

        loaded = {locale: Dictionary.from_files(str(root)) for locale, root in roots.items()}
    except Exception as exc:  # The checker must fail closed on malformed upstream data.
        raise SpellingToolError(
            kind="spelling_tool_failure",
            detail=f"spylls=={locked_version} could not load the pinned Hunspell dictionaries: {exc}",
            next_action="run just setup-locale-spelling; if it persists, inspect the locked dictionary packages",
        ) from exc
    _LOADED_DICTIONARIES.clear()
    _LOADED_DICTIONARIES[content_key] = loaded
    return dict(loaded)


# Parsing the four Hunspell packages costs seconds, while hashing their bytes
# costs milliseconds; every spelling signal and test asks for the same pinned
# files. The memo is keyed on the engine version and the exact aff/dic bytes,
# so a replaced or edited dictionary loads afresh, and it holds one generation
# only so temporary repositories cannot accumulate parsed dictionaries.
_LOADED_DICTIONARIES: dict[tuple[str, tuple[tuple[str, str, str], ...]], dict[str, Dictionary]] = {}


def _dictionary_content_key(
    engine_version: str, roots: dict[str, Path]
) -> tuple[str, tuple[tuple[str, str, str], ...]]:
    """Identify one dictionary load by engine version and the bytes it parses."""
    return (
        engine_version,
        tuple(
            (
                locale,
                hashlib.sha256(root.with_suffix(".aff").read_bytes()).hexdigest(),
                hashlib.sha256(root.with_suffix(".dic").read_bytes()).hexdigest(),
            )
            for locale, root in sorted(roots.items())
        ),
    )


__all__ = ["DICTIONARY_SPECS", "SpellingToolError", "dictionary_roots", "load_dictionaries", "locked_spylls_version"]
