"""Stage the declared user-documentation roots as one structure, each language's text, and a manifest."""

from __future__ import annotations

import argparse
import hashlib
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

from . import docs_scan
from .assembly_transaction import AssemblyReuse
from .build_directory import require_enrolled_build
from .build_log import BuildLog, display_path
from .build_paths import build_paths
from .docs_errors import DocsPackagingError
from .docs_scan import Refusal, ServedMediaTypes, csp_hash, scan_page, scan_stylesheet, served_media_types
from .hashing import digest
from .layout import load_layout
from .package_inventory import checked_member

# Sphinx build state inside each language root: the doctree cache, the build
# fingerprint and the copied page sources. None of it is read by a reader.
BUILD_STATE = frozenset({".doctrees", ".buildinfo", "_sources"})
STAGED_PAYLOAD = "user"
# Beside the payload: the next payload while it is checked, and the scan findings it reuses.
CANDIDATE = "next"
SCAN_CACHE = "scan-cache.json"
SCAN_CACHE_SCHEMA = 1
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


def _cached_refusals(value: object) -> list[Refusal] | None:
    """Decode refusal reasons and source lines from a previous scan."""
    if not isinstance(value, list):
        return None
    decoded: list[Refusal] = []
    for item in value:
        if not isinstance(item, list) or len(item) != 2 or not isinstance(item[0], str) or type(item[1]) is not int:
            return None
        decoded.append(Refusal(item[0], item[1]))
    return decoded


def _cached_findings(value: object) -> tuple[list[str], list[Refusal]] | None:
    """Accept only well-formed cached findings; malformed entries must be rescanned."""
    if not isinstance(value, list) or len(value) != 2:
        return None
    hashes, raw_refusals = value
    if not isinstance(hashes, list) or not all(isinstance(item, str) for item in hashes):
        return None
    decoded = _cached_refusals(raw_refusals)
    if decoded is None:
        return None
    return list(hashes), decoded


class _ScanMemo:
    """Each page's and stylesheet's scan findings, keyed by its bytes and by what judged them.

    A rebuild of the documentation rewrites every file but changes few, so a file
    whose bytes were already judged by this scanner under this media-type table is
    not parsed again. Only entries a run looked up are written back.
    """

    def __init__(self, path: Path, declaration: Mapping[str, object]) -> None:
        self.path = path
        judge = hashlib.sha256(Path(docs_scan.__file__).read_bytes())
        judge.update(json.dumps(declaration["media_types"], sort_keys=True).encode("utf-8"))
        self.judge = judge.hexdigest()
        self.read = 0
        self.scanned = 0
        self.current: dict[str, list[object]] = {}
        self.previous: dict[str, object] = {}
        try:
            stored: object = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            stored = None
        if isinstance(stored, dict):
            record = cast(dict[str, object], stored)
            findings = record.get("findings")
            if record.get("schema") == SCAN_CACHE_SCHEMA and record.get("judge") == self.judge:
                self.previous = cast(dict[str, object], findings) if isinstance(findings, dict) else {}

    def findings(self, kind: str, source: Path, media_types: ServedMediaTypes) -> tuple[list[str], list[Refusal]]:
        """Return a file's inline-script hashes and refusals, scanning it only when its bytes are new."""
        content = source.read_bytes()
        self.read += 1
        key = f"{kind}:{hashlib.blake2b(content, digest_size=32).hexdigest()}"
        known = _cached_findings(self.previous.get(key))
        if known is not None:
            result = known
        else:
            # Universal newlines, exactly as reading the file as text gives it.
            text = content.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")
            if kind == "text/html":
                page = scan_page(text, media_types)
                result = ([csp_hash(script) for script in page.inline_scripts], page.refused)
            else:
                result = (list[str](), scan_stylesheet(text, media_types))
            self.scanned += 1
        self.current[key] = [result[0], [[refusal.reason, refusal.line] for refusal in result[1]]]
        return result

    def save(self) -> None:
        """Write back the findings this run used."""
        record = {"schema": SCAN_CACHE_SCHEMA, "judge": self.judge, "findings": self.current}
        self.path.write_text(json.dumps(record, sort_keys=True) + "\n", encoding="utf-8")


def _inspect_language_files(
    language: str,
    root: Path,
    files: list[Path],
    media_types: ServedMediaTypes,
    memo: _ScanMemo,
    hashes: set[str],
    refused: dict[str, list[str]],
) -> None:
    for source in files:
        kind = (media_types.of(source.name) or "").split(";")[0]
        if kind not in {"text/html", "text/css"}:
            continue
        script_hashes, refusals = memo.findings(kind, source, media_types)
        hashes.update(script_hashes)
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
    memo: _ScanMemo,
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
    _inspect_language_files(language, root, selected[language], media_types, memo, hashes, refused)


def _collect_roots(
    roots: dict[str, Path], entry: str, search: str, media_types: ServedMediaTypes, memo: _ScanMemo
) -> tuple[dict[str, list[Path]], set[str]]:
    selected: dict[str, list[Path]] = {}
    hashes: set[str] = set()
    problems: list[str] = []
    refused: dict[str, list[str]] = {}
    for required in (entry, search):
        if media_types.of(PurePosixPath(required).name) is None:
            problems.append(f"the documentation scheme does not serve {required}")
    for language, root in roots.items():
        _collect_language(language, root, entry, search, media_types, memo, selected, hashes, problems, refused)
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
    destination.mkdir(parents=True, exist_ok=True)
    # Until this run publishes, the stage is not a complete payload.
    (destination / "ready").unlink(missing_ok=True)
    payload = destination / STAGED_PAYLOAD
    candidate = destination / CANDIDATE
    if candidate.exists():
        shutil.rmtree(candidate)
    media_types = served_media_types(declaration)
    entry, search = declaration["entry"], declaration["search"]
    memo = _ScanMemo(destination / SCAN_CACHE, declaration)
    try:
        selected, hashes = _collect_roots(roots, entry, search, media_types, memo)
    finally:
        # Findings describe the built bytes alone, so a refused run's are as reusable as any.
        memo.save()
    built = {
        language: {source.relative_to(roots[language]).as_posix(): source for source in files}
        for language, files in selected.items()
    }
    stored, inventory = _factor_and_inventory(candidate, built)
    manifest_name = cast(str, declaration["manifest"])
    kept, replaced, removed = _publish(candidate, payload, inventory, manifest_name)
    shutil.rmtree(candidate)
    built_size = sum(source.stat().st_size for files in selected.values() for source in files)
    stored_size = sum(file.stat().st_size for file in payload.rglob("*") if file.is_file())
    BuildLog("user_docs_stage").status(
        f"staged user documentation in {len(languages)} languages: {sum(map(len, selected.values()))} built "
        f"files, {built_size / 1_000_000:.1f} MB, stored as {len(inventory)} files, "
        f"{stored_size / 1_000_000:.1f} MB ({len(stored.pages)} pages composed per language) -> "
        f"{display_path(payload)}; {kept} kept, {replaced} replaced, {removed} removed; "
        f"{memo.scanned} of {memo.read} pages and stylesheets scanned"
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
    (payload / manifest_name).write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (destination / "ready").write_text("complete\n", encoding="utf-8")


def _clear_ancestors(payload: Path, target: Path) -> None:
    """Remove a file standing where ``target`` needs a directory, so a renamed tree can replace it."""
    for ancestor in reversed(target.relative_to(payload).parents[:-1]):
        if (payload / ancestor).is_file():
            (payload / ancestor).unlink()


def _publish(candidate: Path, payload: Path, inventory: Mapping[str, str], manifest_name: str) -> tuple[int, int, int]:
    """Make ``payload`` hold exactly the candidate's inventory, keeping every file it already holds byte for byte.

    A kept file is one the previous manifest records with the new digest and whose
    bytes still match that record; it is neither rewritten nor moved, so whatever
    keys on it downstream stays current. Every other member is moved in from the
    candidate, and a file the inventory no longer names is removed. Returns the
    kept, replaced and removed counts.
    """
    try:
        reuse = AssemblyReuse(payload, candidate, manifest_name)
    except ValueError as error:
        raise DocsPackagingError(str(error)) from None
    previous = cast(dict[str, object], reuse.manifest.get("files", {}))
    kept = replaced = 0
    for member, expected in inventory.items():
        if previous.get(member) == expected and reuse.verified(member) is not None:
            kept += 1
            continue
        target = payload / member
        _clear_ancestors(payload, target)
        if target.is_dir():
            shutil.rmtree(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        os.replace(candidate / member, target)
        replaced += 1
    removed = _remove_obsolete_members(payload, inventory, manifest_name)
    return kept, replaced, removed


def _remove_obsolete_members(payload: Path, inventory: Mapping[str, str], manifest_name: str) -> int:
    """Remove stale files and empty directories after candidate files have been published."""
    removed = 0
    for path in sorted(payload.rglob("*"), key=lambda entry: len(entry.parts), reverse=True):
        relative = path.relative_to(payload).as_posix()
        if path.is_file() and relative not in inventory and relative != manifest_name:
            path.unlink()
            removed += 1
        elif path.is_dir() and not any(path.iterdir()):
            path.rmdir()
    return removed


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
