"""Stage the declared user-documentation roots as one structure, each language's text, and a manifest."""

from __future__ import annotations

import argparse
import json
import os
import shutil
from collections.abc import Mapping
from pathlib import Path, PurePosixPath
from typing import cast

from cadrumo.core.external_constants import OutputLanguage
from dev._paths import REPO_ROOT
from dev.docs.build_paths import DOCS_BUILD_ROOT_ENV, docs_html_root
from dev.docs.language_roots import (
    LANGUAGES_DIRECTORY,
    LAYOUT_FILE,
    STRUCTURE_DIRECTORY,
    Layout,
    differences,
    factor_roots,
    text_file,
)

from .build_directory import require_enrolled_build
from .build_log import BuildLog, display_path
from .build_paths import build_paths
from .docs_errors import DocsPackagingError
from .docs_scan import ServedMediaTypes, csp_hash, scan_page, scan_stylesheet, served_media_types
from .hashing import digest
from .layout import load_layout
from .package_inventory import checked_member

# Sphinx build state inside each language root: the doctree cache, the build
# fingerprint and the copied page sources. None of it is read by a reader.
BUILD_STATE = frozenset({".doctrees", ".buildinfo", "_sources"})
STAGED_PAYLOAD = "user"
# The owner's language switcher links the default language at the site apex and every
# other language one directory down, so those stay the addresses the package answers.
# What it stores is one structure and each language's text; the manifest says which
# address is served from which.
SITE_ROOTS = frozenset(member.value for member in OutputLanguage)
MANIFEST_SCHEMA = 2
RECONFIGURE = (
    "The user_docs target has not run for this CMake binary directory. Reconfigure it from the current "
    "native/cmake sources so package assembly depends on user_docs, then build again."
)


def declared_languages(layout: Mapping[str, object]) -> tuple[str, ...]:
    """Return the package's documentation languages in declared order."""
    languages = cast(Mapping[str, object], layout["user_docs"])["languages"]
    supported = {member.value for member in OutputLanguage}
    if not isinstance(languages, list) or not languages:
        raise DocsPackagingError("The package layout must declare at least one documentation language")
    typed_languages: list[str] = []
    for language in cast(list[object], languages):
        if not isinstance(language, str):
            raise DocsPackagingError("Documentation languages must be strings")
        typed_languages.append(language)
    if len(set(typed_languages)) != len(typed_languages) or not set(typed_languages) <= supported:
        raise DocsPackagingError(f"Documentation languages must be unique members of {sorted(supported)}: {languages}")
    if OutputLanguage.EN.value not in typed_languages:
        raise DocsPackagingError(f"Documentation languages must include the apex language {OutputLanguage.EN.value}")
    return tuple(typed_languages)


def package_prefix(language: str) -> str:
    """Return a language's directory inside the packaged documentation, empty at the apex."""
    return "" if language == OutputLanguage.EN.value else f"{language}/"


def language_roots(build_root: Path, languages: tuple[str, ...]) -> dict[str, Path]:
    """Resolve each language root through the documentation build-path owner."""
    html_root = docs_html_root(REPO_ROOT, environ={DOCS_BUILD_ROOT_ENV: str(build_root)})
    if not html_root.is_relative_to(build_root.resolve()):
        raise DocsPackagingError(f"Documentation output escapes its build directory: {html_root}")
    return {language: html_root / language for language in languages}


def _reject_linked_docs(current: Path, names: list[str]) -> None:
    for name in names:
        member = current / name
        if member.is_symlink() or member.is_junction():
            raise DocsPackagingError(f"Linked documentation entry: {member}")


def _shippable_files(root: Path) -> list[Path]:
    """List a language root's reader-facing files, refusing links that could leave it.

    Directories named for a site language are other roots nested in the owner's apex
    layout; each language is staged from its own root, so they are never copied twice.
    """
    files: list[Path] = []
    for directory, names, filenames in os.walk(root):
        current = Path(directory)
        if current == root:
            names[:] = [name for name in names if name not in BUILD_STATE | SITE_ROOTS]
            filenames = [name for name in filenames if name not in BUILD_STATE]
        _reject_linked_docs(current, [*names, *filenames])
        files.extend(current / name for name in filenames)
    return sorted(files)


def _inspect_language_files(
    language: str,
    root: Path,
    files: list[Path],
    media_types: ServedMediaTypes,
    hashes: set[str],
    refused: dict[str, list[str]],
) -> None:
    for source in files:
        kind = (media_types.of(source.name) or "").split(";")[0]
        if kind == "text/html":
            findings = scan_page(source.read_text(encoding="utf-8"), media_types)
            hashes.update(csp_hash(script) for script in findings.inline_scripts)
            refusals = findings.refused
        elif kind == "text/css":
            refusals = scan_stylesheet(source.read_text(encoding="utf-8"), media_types)
        else:
            continue
        relative = f"{package_prefix(language)}{source.relative_to(root).as_posix()}"
        for refusal in refusals:
            refused.setdefault(refusal.reason, []).append(f"{relative}:{refusal.line}")


def _check_language_roots(language: str, root: Path, entry: str, search: str, problems: list[str]) -> None:
    if not (root / entry).is_file():
        problems.append(f"{language}: missing {entry} in {root}")
    # The site has one search index, at its apex, which every language's pages load.
    if language == OutputLanguage.EN.value and not (root / search).is_file():
        problems.append(f"{language}: missing {search} in {root}")
    if language != OutputLanguage.EN.value and (root / search).is_file():
        problems.append(
            f"{language}: holds its own {search}; the one search index belongs to {OutputLanguage.EN.value}"
        )


def _collect_language(
    language: str,
    root: Path,
    entry: str,
    search: str,
    media_types: ServedMediaTypes,
    selected: dict[str, list[Path]],
    hashes: set[str],
    problems: list[str],
    refused: dict[str, list[str]],
) -> None:
    _check_language_roots(language, root, entry, search, problems)
    if not root.is_dir():
        return
    # The scheme answers any other file type with 404, so it never ships; a
    # page or stylesheet that references one is refused below.
    shippable = _shippable_files(root)
    selected[language] = [file for file in shippable if media_types.of(file.name) is not None]
    excluded = sorted({file.suffix or file.name for file in shippable if media_types.of(file.name) is None})
    if excluded:
        unserved = len(shippable) - len(selected[language])
        BuildLog("user_docs_stage").verbose(f"excluded {unserved} unserved {language} files: {', '.join(excluded)}")
    _inspect_language_files(language, root, selected[language], media_types, hashes, refused)


def _collect_roots(
    roots: dict[str, Path], entry: str, search: str, media_types: ServedMediaTypes
) -> tuple[dict[str, list[Path]], set[str]]:
    selected: dict[str, list[Path]] = {}
    hashes: set[str] = set()
    problems: list[str] = []
    refused: dict[str, list[str]] = {}
    for required in (entry, search):
        if media_types.of(PurePosixPath(required).name) is None:
            problems.append(f"the documentation scheme does not serve {required}")
    for language, root in roots.items():
        _collect_language(language, root, entry, search, media_types, selected, hashes, problems, refused)
    for reason, locations in sorted(refused.items()):
        problems.append(f"{reason}: {len(locations)} location(s), first {locations[0]}")
    if problems:
        raise DocsPackagingError("User documentation cannot be packaged:\n  " + "\n  ".join(problems))
    return selected, hashes


def _factor_and_inventory(payload: Path, built: dict[str, dict[str, Path]]) -> tuple[Layout, dict[str, str]]:
    try:
        for language, site in built.items():
            for path in site:
                checked_member(package_prefix(language) + path)
        stored = factor_roots(built, payload)
        # The stored form is only as good as what it gives back: every file of
        # every language is composed again and compared with the one that was built.
        unequal = differences(payload, built)
    except ValueError as error:
        raise DocsPackagingError(str(error)) from None
    if unequal:
        raise DocsPackagingError(
            f"The stored documentation does not give {len(unequal)} built file(s) back: " + "; ".join(unequal[:5])
        )
    # The manifest below carries what the layout file says, so the package ships one of them.
    (payload / LAYOUT_FILE).unlink()
    inventory: dict[str, str] = {}
    for file in sorted(path for path in payload.rglob("*") if path.is_file()):
        relative = file.relative_to(payload).as_posix()
        try:
            checked_member(relative)
        except ValueError as error:
            raise DocsPackagingError(str(error)) from None
        inventory[relative] = digest(file)
    return stored, inventory


def stage_roots(build: Path, *, target: str | None = None) -> None:
    """Store the declared roots' shippable files once and write the manifest the package consumes."""
    paths = build_paths(build)
    layout = load_layout(target)
    declaration = layout["user_docs"]
    languages = declared_languages(layout)
    roots = language_roots(paths["user_docs_build"], languages)
    destination = paths["user_docs_stage"]
    if destination.exists():
        shutil.rmtree(destination)
    payload = destination / STAGED_PAYLOAD
    media_types = served_media_types(declaration)
    entry, search = declaration["entry"], declaration["search"]
    selected, hashes = _collect_roots(roots, entry, search, media_types)
    built = {
        language: {source.relative_to(roots[language]).as_posix(): source for source in files}
        for language, files in selected.items()
    }
    stored, inventory = _factor_and_inventory(payload, built)
    built_size = sum(source.stat().st_size for files in selected.values() for source in files)
    stored_size = sum(file.stat().st_size for file in payload.rglob("*") if file.is_file())
    BuildLog("user_docs_stage").status(
        f"staged user documentation in {len(languages)} languages: {sum(map(len, selected.values()))} built "
        f"files, {built_size / 1_000_000:.1f} MB, stored as {len(inventory)} files, "
        f"{stored_size / 1_000_000:.1f} MB ({len(stored.pages)} pages composed per language) -> {display_path(payload)}"
    )
    manifest = {
        "schema": MANIFEST_SCHEMA,
        "languages": list(languages),
        "apex_language": OutputLanguage.EN.value,
        "entries": {language: package_prefix(language) + entry for language in languages},
        "search": search,
        "script_hashes": sorted(hashes),
        "stored": {
            "structure": STRUCTURE_DIRECTORY,
            "languages": LANGUAGES_DIRECTORY,
            "text": {language: text_file(language) for language in languages},
        },
        "pages": list(stored.pages),
        "files": dict(sorted(inventory.items())),
    }
    (payload / cast(str, declaration["manifest"])).write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (destination / "ready").write_text("complete\n", encoding="utf-8")


def verified_stage(stage_root: Path, declaration: Mapping[str, object]) -> Path:
    """Return the staged payload after proving it is exactly its manifest's inventory."""
    payload = stage_root / STAGED_PAYLOAD
    manifest_file = payload / cast(str, declaration["manifest"])
    if not manifest_file.is_file():
        raise DocsPackagingError(f"Staged user documentation is missing: {manifest_file}. {RECONFIGURE}")
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    observed = {p.relative_to(payload).as_posix() for p in payload.rglob("*") if p.is_file()} - {
        manifest_file.relative_to(payload).as_posix()
    }
    difference = sorted(observed ^ set(manifest["files"]))
    if difference:
        raise DocsPackagingError(f"Staged documentation differs from its manifest: {difference[:5]}")
    for relative, expected in manifest["files"].items():
        if digest(payload / relative) != expected:
            raise DocsPackagingError(f"Staged documentation file changed after staging: {relative}")
    return payload


def main() -> None:
    """Stage the built roots for the CMake documentation target."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", type=require_enrolled_build, required=True)
    parser.add_argument("--target")
    arguments = parser.parse_args()
    try:
        stage_roots(arguments.build.resolve(strict=True), target=arguments.target)
    except DocsPackagingError as error:
        raise SystemExit(str(error)) from None


if __name__ == "__main__":
    main()
