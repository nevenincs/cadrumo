"""Load the pinned locale dictionaries used by the locale quality signal.

The dictionaries are published as npm Hunspell data packages while the checker
is the pure-Python ``spylls`` engine.  Keeping discovery and validation here
gives the signal one deterministic boundary for setup failures: a missing
Python package, a partial ``node_modules`` tree, or a manually replaced
dictionary cannot become an unclassified import error or a silent change of
language data.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from spylls.hunspell import Dictionary


@dataclass(frozen=True)
class DictionarySpec:
    """Describe one locale dictionary package declared by the repository."""

    locale: str
    package: str


# These are package identities, not spelling exceptions.  The product locale
# contract owns the locale set; each locale maps to the upstream Hunspell data
# package that is installed by ``package-lock.json``.
DICTIONARY_SPECS: Final[tuple[DictionarySpec, ...]] = (
    DictionarySpec("ca", "dictionary-ca"),
    DictionarySpec("en", "dictionary-en-gb"),
    DictionarySpec("es", "dictionary-es"),
    DictionarySpec("hu", "dictionary-hu"),
)
SPYLLS_VERSION: Final[str] = "0.1.7"


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
        spec.locale: repository / "node_modules" / spec.package / "index"
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
    missing = [spec.package for spec in DICTIONARY_SPECS if not isinstance(dependencies.get(spec.package), str)]
    if missing:
        names = ", ".join(sorted(missing))
        raise SpellingToolError(
            kind="spelling_tool_unavailable",
            detail=f"{manifest} does not declare {names}",
            next_action="restore package.json and run just setup-locale-spelling",
        )
    for spec in DICTIONARY_SPECS:
        versions[spec.package] = dependencies[spec.package]
    return versions


def _validate_dictionary_installation(repository: Path, roots: dict[str, Path]) -> None:
    """Reject absent, partial, or manifest-inconsistent dictionary packages."""
    declared_versions = _manifest_versions(repository)
    problems: list[str] = []
    for spec in DICTIONARY_SPECS:
        root = roots[spec.locale]
        package_root = root.parent
        if not root.with_suffix(".aff").is_file() or not root.with_suffix(".dic").is_file():
            problems.append(f"{spec.locale} ({spec.package}) is missing index.aff or index.dic")
            continue
        metadata = package_root / "package.json"
        try:
            package_payload = json.loads(metadata.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, ValueError) as exc:
            problems.append(f"{spec.package} metadata cannot be read: {exc}")
            continue
        actual_name = package_payload.get("name") if isinstance(package_payload, dict) else None
        actual_version = package_payload.get("version") if isinstance(package_payload, dict) else None
        declared_version = declared_versions[spec.package]
        if actual_name != spec.package or actual_version != declared_version:
            problems.append(
                f"{spec.package} metadata is {actual_name!r}@{actual_version!r}, "
                f"but package.json declares {spec.package!r}@{declared_version!r}"
            )
    if problems:
        raise SpellingToolError(
            kind="spelling_tool_unavailable",
            detail="; ".join(problems),
            next_action="run just setup-locale-spelling to restore the locked dictionaries",
        )


def load_dictionaries(repository: Path) -> dict[str, Dictionary]:
    """Load every pinned Hunspell dictionary through the pinned Python engine.

    Raises:
        SpellingToolError: if the Python engine or any dictionary package is
            unavailable, inconsistent with the manifest, or unreadable.
    """
    try:
        from importlib.metadata import PackageNotFoundError, version

        installed_version = version("spylls")
    except (ImportError, PackageNotFoundError):
        raise SpellingToolError(
            kind="spelling_tool_unavailable",
            detail=f"spylls=={SPYLLS_VERSION} is not installed in the active Python environment",
            next_action="run just setup-python to install the pinned spell-check engine",
        ) from None
    if installed_version != SPYLLS_VERSION:
        raise SpellingToolError(
            kind="spelling_tool_unavailable",
            detail=f"active spylls is {installed_version}, but the project requires {SPYLLS_VERSION}",
            next_action="run just setup-python to synchronize uv.lock",
        )

    roots = dictionary_roots(repository)
    _validate_dictionary_installation(repository, roots)
    try:
        from spylls.hunspell import Dictionary

        return {locale: Dictionary.from_files(str(root)) for locale, root in roots.items()}
    except Exception as exc:  # The checker must fail closed on malformed upstream data.
        raise SpellingToolError(
            kind="spelling_tool_failure",
            detail=f"spylls=={SPYLLS_VERSION} could not load the pinned Hunspell dictionaries: {exc}",
            next_action="run just setup-locale-spelling; if it persists, inspect the locked dictionary packages",
        ) from exc


__all__ = ["DICTIONARY_SPECS", "SPYLLS_VERSION", "SpellingToolError", "dictionary_roots", "load_dictionaries"]
