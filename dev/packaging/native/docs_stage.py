"""Stage the declared user-documentation roots as the package's shippable subset and manifest."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import shutil
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path, PurePosixPath
from typing import Any, override
from urllib.parse import unquote

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
# Attributes whose URL the browser fetches, submits to or navigates to without the reader choosing a link.
_RESOURCE_ATTRIBUTES = {
    "script": ("src",),
    "link": ("href", "imagesrcset"),
    "img": ("src", "srcset"),
    "source": ("src", "srcset"),
    "iframe": ("src",),
    "embed": ("src",),
    "object": ("data",),
    "audio": ("src",),
    "video": ("src", "poster"),
    "track": ("src",),
    "form": ("action",),
    "button": ("formaction",),
    "input": ("formaction",),
}
# Attributes holding a comma-separated image candidate list rather than one URL.
_CANDIDATE_LISTS = frozenset({"srcset", "imagesrcset"})
# Links the reader follows. One may leave the package, since the shell opens it
# externally, but a link inside the package must name a file the scheme serves.
_FOLLOWED_ATTRIBUTES = {"a": ("href",), "area": ("href",)}
_HTML_SPACE = " \t\n\f\r"
_URL_SCHEME = re.compile(r"[A-Za-z][A-Za-z0-9+.-]*:")
# Browsers drop tabs and newlines anywhere in a URL before parsing it.
_URL_IGNORED = re.compile(r"[\t\n\r]")
_URL_TRIMMED = "".join(map(chr, range(0x21)))
_REFRESH_DELAY = re.compile(r"[ \t\n\f\r]*[0-9.]*[ \t\n\f\r]*(?:[;,][ \t\n\f\r]*)?")
_REFRESH_URL = re.compile(r"url[ \t\n\f\r]*=[ \t\n\f\r]*", re.IGNORECASE)

# CSS Syntax Level 3 tokens, far enough to tell a loaded URL from comments, strings and other values.
_CSS_ESCAPE_BODY = r"\\(?:[0-9A-Fa-f]{1,6}[ \t\n\r\f]?|[^\n0-9A-Fa-f])"
_CSS_IDENTIFIER = re.compile(
    rf"(?:--|-?(?:[A-Za-z_\u0080-\U0010ffff]|{_CSS_ESCAPE_BODY}))(?:[A-Za-z0-9_\-\u0080-\U0010ffff]|{_CSS_ESCAPE_BODY})*"
)
_CSS_ESCAPE = re.compile(r"\\(?:([0-9A-Fa-f]{1,6})[ \t\n\r\f]?|(.))", re.DOTALL)
_CSS_COMMENT = re.compile(r"/\*.*?(?:\*/|\Z)", re.DOTALL)
# A string ends at its quote, before an unescaped newline (a bad string) or at the end of input.
_CSS_STRINGS = {
    quote: re.compile(rf"{quote}((?:[^{quote}\\\n]|\\.)*)(?:{quote}|(?=\n)|\Z)", re.DOTALL) for quote in "\"'"
}
_CSS_SPACE = re.compile(r"[ \t\n\r\f]*")
_CSS_UNQUOTED_URL = re.compile(r"((?:[^)\\]|\\.)*)(?:\)|\Z)", re.DOTALL)
# Functions whose string arguments are URLs; local(), format() and the rest take names.
_CSS_URL_FUNCTIONS = frozenset({"url", "src", "image-set", "-webkit-image-set"})


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


@dataclass(frozen=True)
class ServedMediaTypes:
    """The documentation scheme's closed media-type table, as the package layout declares it."""

    names: Mapping[str, str]
    extensions: Mapping[str, str]

    def of(self, name: str) -> str | None:
        """Return the media type a file name is served as, or None when the scheme refuses to serve it."""
        if name in self.names:
            return self.names[name]
        _, dot, extension = name.rpartition(".")
        return self.extensions.get(extension) if dot else None


def served_media_types(declaration: Mapping[str, Any]) -> ServedMediaTypes:
    """Read the documentation scheme's media-type table from the user_docs declaration."""
    table = declaration.get("media_types")
    if not isinstance(table, dict) or set(table) != {"names", "extensions"}:
        raise DocsPackagingError("user_docs.media_types must declare exactly names and extensions")
    sections: dict[str, dict[str, str]] = {}
    for section, forbidden in (("names", "/\\"), ("extensions", "./\\")):
        entries = table[section]
        if not isinstance(entries, dict):
            raise DocsPackagingError(f"user_docs.media_types.{section} must map keys to media types")
        typed: dict[str, str] = {}
        for key, media in entries.items():
            if not key or any(character in key for character in forbidden) or not isinstance(media, str) or not media:
                raise DocsPackagingError(f"user_docs.media_types.{section} has an invalid entry: {key!r}")
            typed[key] = media
        sections[section] = typed
    if not sections["extensions"]:
        raise DocsPackagingError("user_docs.media_types.extensions must not be empty")
    return ServedMediaTypes(names=sections["names"], extensions=sections["extensions"])


@dataclass(frozen=True)
class Refusal:
    """One reference the package refuses and the 1-based line it appears on."""

    reason: str
    line: int


@dataclass
class PageFindings:
    """Executing inline scripts and package-refused references of one page."""

    inline_scripts: list[str] = field(default_factory=list)
    refused: list[Refusal] = field(default_factory=list)


def _normalized_url(url: str) -> str:
    # Browsers strip leading and trailing C0 controls and spaces, drop tabs and
    # newlines anywhere, and read a backslash as a slash under an http(s) base.
    return _URL_IGNORED.sub("", url.strip(_URL_TRIMMED)).replace("\\", "/")


def _is_remote(url: str) -> bool:
    normalized = _normalized_url(url)
    scheme = _URL_SCHEME.match(normalized)
    return normalized.startswith("//") or (scheme is not None and scheme.group().lower() in {"http:", "https:"})


def _requested_name(url: str) -> str | None:
    """Return the file name a package-relative reference requests, or None when it names no package file.

    Other schemes and same-document references request nothing from the package,
    and a directory reference is served as its index page.
    """
    normalized = _normalized_url(url)
    if normalized.startswith("//") or _URL_SCHEME.match(normalized):
        return None
    path = re.split(r"[?#]", normalized, maxsplit=1)[0]
    name = unquote(path.rpartition("/")[2])
    return None if name in {"", ".", ".."} else name


def _refusal(context: str, url: str, media_types: ServedMediaTypes, *, followed: bool = False) -> str | None:
    """Return why the package refuses one reference, or None when it stays inside the served package."""
    if _is_remote(url):
        return None if followed else f"{context} {url.strip()}"
    name = _requested_name(url)
    if name is not None and media_types.of(name) is None:
        return f"{context} {url.strip()}: the documentation scheme does not serve this file type"
    return None


def _srcset_urls(value: str) -> list[str]:
    """Return the candidate URLs of a srcset value, following the HTML srcset parsing algorithm."""
    urls: list[str] = []
    position, end = 0, len(value)
    while True:
        while position < end and value[position] in _HTML_SPACE + ",":
            position += 1
        if position >= end:
            return urls
        start = position
        while position < end and value[position] not in _HTML_SPACE:
            position += 1
        url = value[start:position]
        if url.endswith(","):
            urls.append(url.rstrip(","))
            continue
        urls.append(url)
        parenthesized = False
        while position < end:
            character = value[position]
            position += 1
            if character == "(":
                parenthesized = True
            elif character == ")":
                parenthesized = False
            elif character == "," and not parenthesized:
                break


def _matched(pattern: re.Pattern[str], text: str, position: int) -> re.Match[str]:
    """Match a pattern its caller knows applies at this position."""
    match = pattern.match(text, position)
    if match is None:
        raise DocsPackagingError(f"Reference scanner pattern {pattern.pattern!r} did not apply at {position}")
    return match


def _refresh_url(content: str) -> str:
    """Return the URL a refresh meta's content attribute names, empty when it reloads the page itself."""
    rest = content[_matched(_REFRESH_DELAY, content, 0).end() :]
    if prefix := _REFRESH_URL.match(rest):
        rest = rest[prefix.end() :]
    if rest[:1] in {'"', "'"}:
        rest = rest[1:].split(rest[0], 1)[0]
    return rest.strip()


def _css_unescape(value: str) -> str:
    def replace(match: re.Match[str]) -> str:
        if match.group(1) is None:
            # An escaped newline continues a string; any other escaped character is itself.
            character = str(match.group(2))
            return "" if character == "\n" else character
        code = int(match.group(1), 16)
        return chr(code) if 0 < code <= 0x10FFFF and not 0xD800 <= code <= 0xDFFF else "\N{REPLACEMENT CHARACTER}"

    return _CSS_ESCAPE.sub(replace, value)


def css_references(text: str) -> Iterator[tuple[str, str, int]]:
    """Yield each URL a stylesheet or declaration block loads, as its syntax, the URL and its 1-based line.

    Comments and strings are consumed whole, so a URL-shaped comment or string
    value is not a load. A URL is an unquoted ``url(...)`` token, a string inside
    ``url()``, ``src()`` or ``image-set()``, or the string an ``@import`` names.
    ``@namespace`` names an identifier, not a resource, and is not a load.
    """
    functions: list[str] = []
    at_rule: str | None = None
    position, end = 0, len(text)

    def line(offset: int) -> int:
        return text.count("\n", 0, offset) + 1

    while position < end:
        character = text[position]
        if text.startswith("/*", position):
            position = _matched(_CSS_COMMENT, text, position).end()
            continue
        if character in _CSS_STRINGS:
            string = _matched(_CSS_STRINGS[character], text, position)
            if at_rule == "import" and functions in ([], ["url"]):
                yield "@import", _css_unescape(string.group(1)), line(position)
                at_rule = None
            elif at_rule != "namespace" and functions and functions[-1] in _CSS_URL_FUNCTIONS:
                yield f"{functions[-1]}()", _css_unescape(string.group(1)), line(position)
            position = string.end()
            continue
        if character == "@" and (keyword := _CSS_IDENTIFIER.match(text, position + 1)):
            at_rule = _css_unescape(keyword.group()).lower()
            position = keyword.end()
            continue
        if identifier := _CSS_IDENTIFIER.match(text, position):
            position = identifier.end()
            if position < end and text[position] == "(":
                name = _css_unescape(identifier.group()).lower()
                position += 1
                argument = _matched(_CSS_SPACE, text, position).end()
                if name == "url" and (argument >= end or text[argument] not in _CSS_STRINGS):
                    unquoted = _matched(_CSS_UNQUOTED_URL, text, argument)
                    if at_rule != "namespace":
                        syntax = "@import" if at_rule == "import" and not functions else "url()"
                        yield syntax, _css_unescape(unquoted.group(1)).strip(_HTML_SPACE), line(argument)
                    position = unquoted.end()
                    continue
                functions.append(name)
            continue
        if character == "(":
            functions.append("")
        elif character == ")":
            if functions:
                functions.pop()
        elif character in ";{}":
            at_rule = None
            functions.clear()
        position += 1


def _css_refusals(text: str, context: str, first_line: int, media_types: ServedMediaTypes) -> list[Refusal]:
    refused: list[Refusal] = []
    for syntax, url, line in css_references(text):
        if (reason := _refusal(f"{context}{syntax}", url, media_types)) is not None:
            refused.append(Refusal(reason, first_line + line - 1))
    return refused


class _PageScanner(HTMLParser):
    """Collect inline script bodies and references that leave the package or name an unserved file."""

    def __init__(self, media_types: ServedMediaTypes) -> None:
        super().__init__(convert_charrefs=True)
        self.findings = PageFindings()
        self._media_types = media_types
        self._script: list[str] | None = None
        self._style: list[str] | None = None
        self._style_line = 0

    def _check(self, context: str, url: str, *, followed: bool = False) -> None:
        if (reason := _refusal(context, url, self._media_types, followed=followed)) is not None:
            self.findings.refused.append(Refusal(reason, self.getpos()[0]))

    @override
    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {name: value or "" for name, value in attrs}
        line = self.getpos()[0]
        for name in _RESOURCE_ATTRIBUTES.get(tag, ()):
            if name in values:
                for url in _srcset_urls(values[name]) if name in _CANDIDATE_LISTS else [values[name]]:
                    self._check(f"<{tag} {name}>", url)
        for name in _FOLLOWED_ATTRIBUTES.get(tag, ()):
            if name in values:
                self._check(f"<{tag} {name}>", values[name], followed=True)
        refresh = tag == "meta" and values.get("http-equiv", "").strip().lower() == "refresh"
        if refresh and (url := _refresh_url(values.get("content", ""))):
            self._check("<meta refresh>", url)
        if "style" in values:
            self.findings.refused += _css_refusals(values["style"], f"<{tag} style> ", line, self._media_types)
        for name, value in values.items():
            if name.startswith("on"):
                self.findings.refused.append(Refusal(f"<{tag} {name}> inline event handler", line))
            elif value.strip().lower().startswith("javascript:"):
                self.findings.refused.append(Refusal(f"<{tag} {name}> javascript: URL", line))
        if tag == "script" and "src" not in values:
            kind = values.get("type", "").split(";")[0].strip().lower()
            self._script = [] if kind in _SCRIPT_SRC_TYPES else None
        elif tag == "style":
            self._style, self._style_line = [], line

    @override
    def handle_data(self, data: str) -> None:
        if self._script is not None:
            self._script.append(data)
        elif self._style is not None:
            if not self._style:
                self._style_line = self.getpos()[0]
            self._style.append(data)

    @override
    def handle_endtag(self, tag: str) -> None:
        if tag == "script" and self._script is not None:
            self.findings.inline_scripts.append("".join(self._script))
            self._script = None
        elif tag == "style" and self._style is not None:
            self.findings.refused += _css_refusals(
                "".join(self._style), "<style> ", self._style_line, self._media_types
            )
            self._style = None


def scan_page(text: str, media_types: ServedMediaTypes) -> PageFindings:
    """Return one page's executing inline scripts and its package-escaping or unserved references."""
    scanner = _PageScanner(media_types)
    scanner.feed(text)
    scanner.close()
    return scanner.findings


def scan_stylesheet(text: str, media_types: ServedMediaTypes) -> list[Refusal]:
    """Return one stylesheet's package-escaping or unserved url() and @import references."""
    return _css_refusals(text, "", 1, media_types)


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
    media_types = served_media_types(declaration)
    selected: dict[str, list[Path]] = {}
    hashes: set[str] = set()
    problems: list[str] = []
    refused: dict[str, list[str]] = {}
    for language, root in roots.items():
        for required in (declaration["entry"], declaration["search"]):
            if media_types.of(PurePosixPath(required).name) is None:
                problems.append(f"{language}: the documentation scheme does not serve {required}")
            if not (root / required).is_file():
                problems.append(f"{language}: missing {required} in {root}")
        if not root.is_dir():
            continue
        # The scheme answers any other file type with 404, so it never ships; a
        # page or stylesheet that references one is refused below.
        shippable = _shippable_files(root)
        selected[language] = [file for file in shippable if media_types.of(file.name) is not None]
        excluded = sorted({file.suffix or file.name for file in shippable if media_types.of(file.name) is None})
        if excluded:
            unserved = len(shippable) - len(selected[language])
            print(f"Excluded {unserved} unserved {language} files: {', '.join(excluded)}", flush=True)
        if language == APEX_LANGUAGE and (root / declaration["manifest"]) in selected[language]:
            problems.append(f"{language}: the apex root already contains {declaration['manifest']}")
        for source in selected[language]:
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
    for reason, locations in sorted(refused.items()):
        problems.append(f"{reason}: {len(locations)} location(s), first {locations[0]}")
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
