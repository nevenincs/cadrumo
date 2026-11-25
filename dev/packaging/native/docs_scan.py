"""Scan documentation resources and calculate inline script policy hashes."""

from __future__ import annotations

import base64
import hashlib
import re
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import cast, override
from urllib.parse import unquote

from .docs_errors import DocsPackagingError

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


def _is_header_value(value: str) -> bool:
    # The scheme sends the type as a Content-Type header, which admits only
    # visible ASCII, space and tab.
    return all(character == "	" or " " <= character <= "~" for character in value)


def _media_type_section(table: dict[str, object], section: str, forbidden: str) -> dict[str, str]:
    entries = table[section]
    if not isinstance(entries, dict):
        raise DocsPackagingError(f"user_docs.media_types.{section} must map keys to media types")
    typed: dict[str, str] = {}
    for key, media in cast(dict[str, object], entries).items():
        if (
            not key
            or any(character in key for character in forbidden)
            or not isinstance(media, str)
            or not media
            or not _is_header_value(media)
        ):
            raise DocsPackagingError(f"user_docs.media_types.{section} has an invalid entry: {key!r}")
        typed[key] = media
    return typed


def served_media_types(declaration: Mapping[str, object]) -> ServedMediaTypes:
    """Read the documentation scheme's media-type table from the user_docs declaration."""
    table = declaration.get("media_types")
    if not isinstance(table, dict) or set(cast(dict[str, object], table)) != {"names", "extensions"}:
        raise DocsPackagingError("user_docs.media_types must declare exactly names and extensions")
    table = cast(dict[str, object], table)
    sections: dict[str, dict[str, str]] = {}
    for section, forbidden in (("names", "/\\"), ("extensions", "./\\")):
        sections[section] = _media_type_section(table, section, forbidden)
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


def _skip_srcset_descriptor(value: str, position: int) -> int:
    end = len(value)
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
    return position


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
        position = _skip_srcset_descriptor(value, position)


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


class _CssScanner:
    """Consume CSS tokens while retaining function and at-rule context."""

    def __init__(self, text: str) -> None:
        self.text = text
        self.functions: list[str] = []
        self.at_rule: str | None = None
        self.position = 0

    def _line(self, offset: int) -> int:
        return self.text.count("\n", 0, offset) + 1

    def _string(self, character: str) -> tuple[str, str, int] | None:
        string = _matched(_CSS_STRINGS[character], self.text, self.position)
        found = None
        if self.at_rule == "import" and self.functions in ([], ["url"]):
            found = ("@import", _css_unescape(string.group(1)), self._line(self.position))
            self.at_rule = None
        elif self.at_rule != "namespace" and self.functions and self.functions[-1] in _CSS_URL_FUNCTIONS:
            found = (f"{self.functions[-1]}()", _css_unescape(string.group(1)), self._line(self.position))
        self.position = string.end()
        return found

    def _identifier(self, identifier: re.Match[str]) -> tuple[str, str, int] | None:
        self.position = identifier.end()
        if self.position >= len(self.text) or self.text[self.position] != "(":
            return None
        name = _css_unescape(identifier.group()).lower()
        self.position += 1
        argument = _matched(_CSS_SPACE, self.text, self.position).end()
        if name != "url" or (argument < len(self.text) and self.text[argument] in _CSS_STRINGS):
            self.functions.append(name)
            return None
        unquoted = _matched(_CSS_UNQUOTED_URL, self.text, argument)
        found = None
        if self.at_rule != "namespace":
            syntax = "@import" if self.at_rule == "import" and not self.functions else "url()"
            found = (syntax, _css_unescape(unquoted.group(1)).strip(_HTML_SPACE), self._line(argument))
        self.position = unquoted.end()
        return found

    def _punctuation(self, character: str) -> None:
        if character == "(":
            self.functions.append("")
        elif character == ")":
            if self.functions:
                self.functions.pop()
        elif character in ";{}":
            self.at_rule = None
            self.functions.clear()
        self.position += 1

    def step(self) -> tuple[str, str, int] | None:
        character = self.text[self.position]
        if self.text.startswith("/*", self.position):
            self.position = _matched(_CSS_COMMENT, self.text, self.position).end()
            return None
        if character in _CSS_STRINGS:
            return self._string(character)
        if character == "@" and (keyword := _CSS_IDENTIFIER.match(self.text, self.position + 1)):
            self.at_rule = _css_unescape(keyword.group()).lower()
            self.position = keyword.end()
            return None
        if identifier := _CSS_IDENTIFIER.match(self.text, self.position):
            return self._identifier(identifier)
        self._punctuation(character)
        return None


def css_references(text: str) -> Iterator[tuple[str, str, int]]:
    """Yield resource URLs in CSS while ignoring comments and inert strings."""
    scanner = _CssScanner(text)
    while scanner.position < len(text):
        found = scanner.step()
        if found is not None:
            yield found


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

    def _check_followed(self, tag: str, values: dict[str, str]) -> None:
        for name in _FOLLOWED_ATTRIBUTES.get(tag, ()):
            if name in values:
                self._check(f"<{tag} {name}>", values[name], followed=True)

    def _check_resources(self, tag: str, values: dict[str, str], line: int) -> None:
        for name in _RESOURCE_ATTRIBUTES.get(tag, ()):
            if name in values:
                for url in _srcset_urls(values[name]) if name in _CANDIDATE_LISTS else [values[name]]:
                    self._check(f"<{tag} {name}>", url)
        self._check_followed(tag, values)
        refresh = tag == "meta" and values.get("http-equiv", "").strip().lower() == "refresh"
        if refresh and (url := _refresh_url(values.get("content", ""))):
            self._check("<meta refresh>", url)
        if "style" in values:
            self.findings.refused += _css_refusals(values["style"], f"<{tag} style> ", line, self._media_types)

    def _check_active_attributes(self, tag: str, values: dict[str, str], line: int) -> None:
        for name, value in values.items():
            if name.startswith("on"):
                self.findings.refused.append(Refusal(f"<{tag} {name}> inline event handler", line))
            elif value.strip().lower().startswith("javascript:"):
                self.findings.refused.append(Refusal(f"<{tag} {name}> javascript: URL", line))

    def _begin_body(self, tag: str, values: dict[str, str], line: int) -> None:
        if tag == "script" and "src" not in values:
            kind = values.get("type", "").split(";")[0].strip().lower()
            self._script = [] if kind in _SCRIPT_SRC_TYPES else None
        elif tag == "style":
            self._style, self._style_line = [], line

    @override
    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {name: value or "" for name, value in attrs}
        line = self.getpos()[0]
        self._check_resources(tag, values, line)
        self._check_active_attributes(tag, values, line)
        self._begin_body(tag, values, line)

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
