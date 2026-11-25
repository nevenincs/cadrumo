"""Parse GNU readelf version sections with fail-closed count and resource checks."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_SECTION = re.compile(r"Version (definition|needs|symbols) section '[^']+' contains (\d+) entr(?:y|ies):")
_DEFINITION = re.compile(
    r"\s*(?:0x)?[0-9a-fA-F]+:\s+Rev: \d+\s+Flags: (.*?)\s+Index: \d+\s+Cnt: \d+\s+Name: ([A-Za-z0-9_.+-]+)"
)
_NEED = re.compile(r"\s*(?:0x)?[0-9a-fA-F]+:\s+Version: \d+\s+File: (\S+)\s+Cnt: (\d+)")
_NAME = re.compile(r"\s*(?:0x)?[0-9a-fA-F]+:\s+Name: ([A-Za-z0-9_.+-]+)\s+Flags: .*?\s+Version: \d+")
_PARENT = re.compile(r"\s*(?:0x)?[0-9a-fA-F]+:\s+Parent \d+: [A-Za-z0-9_.+-]+")
_SYMBOL_ROW = re.compile(r"\s*([0-9a-fA-F]+):(.*)")
_SYMBOL = re.compile(r"\s*[0-9a-fA-F]+h?\s*\(([^()\s]+)\)")


@dataclass(frozen=True)
class ReadelfVersions:
    """Version needs and definitions reported for one ELF image."""

    needs: dict[str, set[str]]
    definitions: set[str]
    bases: set[str]


def parse_readelf_versions(output: str) -> ReadelfVersions:
    """Parse GNU readelf sections, including their declared entry/name counts."""
    parser = _VersionParser()
    for line in output.splitlines():
        parser.accept(line)
    return parser.finish()


@dataclass
class _VersionParser:
    needs: dict[str, set[str]] = field(default_factory=dict)
    definitions: set[str] = field(default_factory=set)
    bases: set[str] = field(default_factory=set)
    symbol_names: set[str] = field(default_factory=set)
    mode: str | None = None
    expected: int = 0
    seen: int = 0
    group_expected: int = 0
    group_seen: int = 0
    dependency: str | None = None
    recognized: bool = False

    def finish_group(self) -> None:
        if self.dependency is not None and self.group_expected != self.group_seen:
            raise ValueError("Truncated readelf version-needs group")

    def finish_section(self) -> None:
        if self.mode is not None:
            self.finish_group()
            if self.expected != self.seen:
                raise ValueError("Truncated readelf version section")

    def accept(self, line: str) -> None:
        if line.startswith("Version "):
            self.start_section(line)
        elif line == "No version information found in this file.":
            self.recognized = True
        elif self.mode is None:
            if "Name: GLIBCXX_" in line or "Name: CXXABI_" in line:
                raise ValueError("C++ ABI name outside a readelf version section")
        elif line.strip() and not line.lstrip().startswith("Addr:"):
            self.accept_row(line)

    def start_section(self, line: str) -> None:
        self.finish_section()
        section = _SECTION.fullmatch(line)
        self.mode = None
        self.dependency = None
        if section:
            self.mode = str(section[1])
            self.expected, self.seen = int(section[2]), 0
            self.recognized = True
        elif line.startswith(("Version definition section", "Version needs section", "Version symbols section")):
            raise ValueError("Malformed readelf version section")

    def accept_row(self, line: str) -> None:
        if self.mode == "symbols":
            self.accept_symbols(line)
        elif self.mode == "definition":
            self.accept_definition(line)
        else:
            self.accept_need(line)

    def accept_symbols(self, line: str) -> None:
        row = _SYMBOL_ROW.fullmatch(line)
        if not row or int(row[1], 16) != self.seen:
            raise ValueError("Malformed readelf version-symbols row")
        entries = _SYMBOL.findall(row[2])
        if not entries or _SYMBOL.sub("", row[2]).strip():
            raise ValueError("Malformed readelf version symbol")
        self.symbol_names.update(name for name in entries if name not in {"*local*", "*global*"})
        self.seen += len(entries)

    def accept_definition(self, line: str) -> None:
        definition = _DEFINITION.fullmatch(line)
        if definition:
            flags, name = definition.groups()
            if name in self.definitions:
                raise ValueError("Duplicate readelf version definition")
            self.definitions.add(name)
            if "BASE" in flags.split():
                self.bases.add(name)
            self.seen += 1
        elif not _PARENT.fullmatch(line):
            raise ValueError("Malformed readelf version definition")

    def accept_need(self, line: str) -> None:
        group = _NEED.fullmatch(line)
        name = _NAME.fullmatch(line)
        if group:
            self.finish_group()
            self.dependency = str(group[1])
            if self.dependency in self.needs:
                raise ValueError("Duplicate readelf version-needs provider")
            self.needs[self.dependency] = set()
            self.group_expected, self.group_seen = int(group[2]), 0
            self.seen += 1
        elif name and self.dependency is not None:
            value = name[1]
            if value in self.needs[self.dependency]:
                raise ValueError("Duplicate readelf required version")
            self.needs[self.dependency].add(value)
            self.group_seen += 1
        else:
            raise ValueError("Malformed readelf version need")

    def finish(self) -> ReadelfVersions:
        self.finish_section()
        if not self.recognized:
            raise ValueError("Missing readelf version information")
        declared = self.definitions.union(*(names for names in self.needs.values()))
        if self.symbol_names - declared:
            raise ValueError("Readelf symbols reference missing version definitions/needs")
        return ReadelfVersions(self.needs, self.definitions, self.bases)
