"""Stage the declared user-documentation roots as the package's shippable subset and manifest."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import shutil
from collections.abc import Mapping
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, override
from urllib.parse import urlsplit

from cadrumo.core.external_constants import OutputLanguage
from dev._paths import REPO_ROOT
from dev.docs.build_paths import DOCS_BUILD_ROOT_ENV, docs_html_root

from .build_paths import build_paths
from .hashing import digest
from .layout import load_layout
from .package_inventory import checked_member

# Sphinx build state inside each language root: the doctree cache, the build
# fingerprint and the copied page sources. None of it is read by a reader.
BUILD_STATE = frozenset({".doctrees", ".buildinfo", "_sources"})
STAGED_PAYLOAD = "user"
# The owner's language switcher links the default language at the site apex and every
# other language one directory down, so the package keeps that one published layout.
APEX_LANGUAGE = OutputLanguage.EN.value
SITE_ROOTS = frozenset(member.value for member in OutputLanguage)
MANIFEST_SCHEMA = 1
RECONFIGURE = (
    "The user_docs target has not run for this CMake binary directory. Reconfigure it from the current "
    "native/cmake sources so package assembly depends on user_docs, then build again."
)

# Script types the browser executes or interprets under script-src; every other
# type, such as application/json, is an inert data block.
_JAVASCRIPT_TYPES = frozenset(
    {
        "application/ecmascript",
        "application/javascript",
        "application/x-ecmascript",
        "application/x-javascript",
        "text/ecmascript",
        "text/javascript",
        "text/javascript1.0",
        "text/javascript1.1",
        "text/javascript1.2",
        "text/javascript1.3",
        "text/javascript1.4",
        "text/javascript1.5",
        "text/jscript",
        "text/livescript",
        "text/x-ecmascript",
        "text/x-javascript",
    }
)
_SCRIPT_SRC_TYPES = frozenset({"", "module", "importmap", "speculationrules"}) | _JAVASCRIPT_TYPES
_RESOURCE_ATTRIBUTES = {
    "script": ("src",),
    "link": ("href",),
    "img": ("src", "srcset"),
    "source": ("src", "srcset"),
    "iframe": ("src",),
    "embed": ("src",),
    "object": ("data",),
    "audio": ("src",),
    "video": ("src", "poster"),
    "track": ("src",),
}


class DocsPackagingError(RuntimeError):
    """A documentation root cannot enter the package."""


def declared_languages(layout: Mapping[str, Any]) -> tuple[str, ...]:
    """Return the package's documentation languages in declared order."""
    languages = layout["user_docs"]["languages"]
    supported = {member.value for member in OutputLanguage}
    if not isinstance(languages, list) or not languages:
        raise DocsPackagingError("The package layout must declare at least one documentation language")
    typed_languages: list[str] = []
    for language in languages:
        if not isinstance(language, str):
            raise DocsPackagingError("Documentation languages must be strings")
        typed_languages.append(language)
    if len(set(typed_languages)) != len(typed_languages) or not set(typed_languages) <= supported:
        raise DocsPackagingError(f"Documentation languages must be unique members of {sorted(supported)}: {languages}")
    if APEX_LANGUAGE not in typed_languages:
        raise DocsPackagingError(f"Documentation languages must include the apex language {APEX_LANGUAGE}")
    return tuple(typed_languages)


def package_prefix(language: str) -> str:
    """Return a language's directory inside the packaged documentation, empty at the apex."""
    return "" if language == APEX_LANGUAGE else f"{language}/"


def language_roots(build_root: Path, languages: tuple[str, ...]) -> dict[str, Path]:
    """Resolve each language root through the documentation build-path owner."""
    html_root = docs_html_root(REPO_ROOT, environ={DOCS_BUILD_ROOT_ENV: str(build_root)})
    if not html_root.is_relative_to(build_root.resolve()):
        raise DocsPackagingError(f"Documentation output escapes its build directory: {html_root}")
    return {language: html_root / language for language in languages}


@dataclass
class PageFindings:
    """Executing inline scripts and package-refused references of one page."""

    inline_scripts: list[str] = field(default_factory=list)
    refused: list[str] = field(default_factory=list)


class _PageScanner(HTMLParser):
    """Collect inline script bodies and resource references that leave the package."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.findings = PageFindings()
        self._script: list[str] | None = None

    @override
    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {name: value or "" for name, value in attrs}
        for name in _RESOURCE_ATTRIBUTES.get(tag, ()):
            if name not in values:
                continue
            candidates = [part.strip().split()[0] for part in values[name].split(",") if part.strip()]
            for url in candidates if name == "srcset" else [values[name].strip()]:
                if _is_remote(url):
                    self.findings.refused.append(f"<{tag} {name}> {url}")
        for name, value in values.items():
            if name.startswith("on"):
                self.findings.refused.append(f"<{tag} {name}> inline event handler")
            elif value.strip().lower().startswith("javascript:"):
                self.findings.refused.append(f"<{tag} {name}> javascript: URL")
        if tag == "script" and "src" not in values:
            kind = values.get("type", "").split(";")[0].strip().lower()
            self._script = [] if kind in _SCRIPT_SRC_TYPES else None

    @override
    def handle_data(self, data: str) -> None:
        if self._script is not None:
            self._script.append(data)

    @override
    def handle_endtag(self, tag: str) -> None:
        if tag == "script" and self._script is not None:
            self.findings.inline_scripts.append("".join(self._script))
            self._script = None


def _is_remote(url: str) -> bool:
    return url.startswith("//") or urlsplit(url).scheme.lower() in {"http", "https"}


def scan_page(text: str) -> PageFindings:
    """Return one page's executing inline scripts and package-escaping references."""
    scanner = _PageScanner()
    scanner.feed(text)
    scanner.close()
    return scanner.findings


def csp_hash(script: str) -> str:
    """Return the CSP source expression body for one inline script as a browser hashes it."""
    # HTML input preprocessing normalizes CRLF and CR to LF before the script text exists.
    normalized = script.replace("\r\n", "\n").replace("\r", "\n")
    return "sha256-" + base64.b64encode(hashlib.sha256(normalized.encode("utf-8")).digest()).decode("ascii")


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
        for name in [*names, *filenames]:
            member = current / name
            if member.is_symlink() or member.is_junction():
                raise DocsPackagingError(f"Linked documentation entry: {member}")
        files.extend(current / name for name in filenames)
    return sorted(files)


def stage_roots(build: Path) -> None:
    """Copy each declared root's shippable subset and write the manifest the package consumes."""
    paths = build_paths(build)
    layout = load_layout()
    declaration = layout["user_docs"]
    languages = declared_languages(layout)
    roots = language_roots(paths["user_docs_build"], languages)
    destination = paths["user_docs_stage"]
    if destination.exists():
        shutil.rmtree(destination)
    payload = destination / STAGED_PAYLOAD
    selected: dict[str, list[Path]] = {}
    hashes: set[str] = set()
    problems: list[str] = []
    refused: dict[str, list[str]] = {}
    for language, root in roots.items():
        for required in (declaration["entry"], declaration["search"]):
            if not (root / required).is_file():
                problems.append(f"{language}: missing {required} in {root}")
        if not root.is_dir():
            continue
        selected[language] = _shippable_files(root)
        if language == APEX_LANGUAGE and (root / declaration["manifest"]) in selected[language]:
            problems.append(f"{language}: the apex root already contains {declaration['manifest']}")
        for page in selected[language]:
            if page.suffix != ".html":
                continue
            findings = scan_page(page.read_text(encoding="utf-8"))
            hashes.update(csp_hash(script) for script in findings.inline_scripts)
            relative = f"{package_prefix(language)}{page.relative_to(root).as_posix()}"
            for reference in findings.refused:
                refused.setdefault(reference, []).append(relative)
    for reference, pages in sorted(refused.items()):
        problems.append(f"{reference}: {len(pages)} page(s), first {pages[0]}")
    if problems:
        raise DocsPackagingError("User documentation cannot be packaged:\n  " + "\n  ".join(problems))
    inventory: dict[str, str] = {}
    for language, files in selected.items():
        root = roots[language]
        for source in files:
            relative = package_prefix(language) + source.relative_to(root).as_posix()
            try:
                checked_member(relative)
            except ValueError as error:
                raise DocsPackagingError(str(error)) from None
            target = payload / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            inventory[relative] = digest(target)
        size = sum(source.stat().st_size for source in files)
        print(f"Staged {language} user documentation: {len(files)} files, {size / 1_000_000:.1f} MB", flush=True)
    manifest = {
        "schema": MANIFEST_SCHEMA,
        "languages": list(languages),
        "apex_language": APEX_LANGUAGE,
        "entries": {language: package_prefix(language) + declaration["entry"] for language in languages},
        "search": {language: package_prefix(language) + declaration["search"] for language in languages},
        "script_hashes": sorted(hashes),
        "files": dict(sorted(inventory.items())),
    }
    (payload / declaration["manifest"]).write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (destination / "ready").write_text("complete\n", encoding="utf-8")


def verified_stage(stage_root: Path, declaration: Mapping[str, Any]) -> Path:
    """Return the staged payload after proving it is exactly its manifest's inventory."""
    payload = stage_root / STAGED_PAYLOAD
    manifest_file = payload / declaration["manifest"]
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
    parser.add_argument("--build", type=Path, required=True)
    arguments = parser.parse_args()
    try:
        stage_roots(arguments.build.resolve(strict=True))
    except DocsPackagingError as error:
        raise SystemExit(str(error)) from None


if __name__ == "__main__":
    main()
