"""Which desktop window types cross the host IPC boundary, found from the window's own source.

A window type is a wire type when a value of it is sent to the Rust host or
received from it. The window reaches the host only through Tauri's ``invoke``,
``listen``, ``emit``, ``emitTo`` and ``once`` and the ``Channel`` frames a
command carries, and only from the modules that import them from
``@tauri-apps/api`` (the IPC modules). The documentation frame's
``postMessage`` bridge (``ipc/docsBridge.ts``) talks to another document in the
window, not to the host, so it is not IPC here. The roots are

* every type an IPC module names: the type arguments of ``invoke<LedgerOutcome>(...)``
  and ``new Channel<Signal>()``, the types a host answer is asserted to, the
  headers and bodies a call sends, and the ports and function types it
  implements, annotates or returns (``tauriLedger(...): LedgerPort``,
  ``HostCall``, which indexes the published command catalogue), under whatever
  local name it imports them;
* the type arguments of every call, wherever it is made, to a generic function
  an IPC module declares (``observedInvoke<Record>(...)``);
* what an IPC module decodes the host's raw channel bytes into: the declared
  result types of the decoders it declares or imports (functions whose first
  parameter is an ``ArrayBuffer``, ``Uint8Array`` or ``DataView``), and every
  type declared in a module whose tag table it matches decoded bytes against
  (``case TerminalFrameTag.data:``), since that module describes the frames;
* every port: a declaration (component props aside) with a method whose
  ``Promise`` result names a type already reached, so a port that another
  module builds over the host calls (``LocalModelHost`` over the agent session)
  counts with everything its member signatures reach.

From the roots every type reference is followed across files: aliases, interface
members and ``extends`` clauses, unions, generic arguments, indexed access
(``T["rows"][number]``), imports under another name, inline ``import("m").T``
references and re-exports. A reference that no import or declaration in its
file explains is matched by name anywhere in the window, so an unusual spelling
over-counts rather than hides a wire type; a declaration's own type parameters
are not references. A type no root reaches (calendar layout, docking,
navigation, component and hook state) is window state, not a wire shape.

A reached alias that writes no field and names only generated-module types,
directly or through other such aliases (``AssetListRow =
NonNullable<ActivityAssetListResult["rows"]>[number]``), is the generated
contract under a window name. It adds no shape of its own, so it is not a wire
type either.

The scan is textual over Prettier-formatted source: comments and string contents
are blanked first, and a top-level declaration runs until the next statement
that starts in the first column.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable, Iterator, Mapping
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Final

from dev.source_tree import repository_files

WINDOW_SOURCE: Final[str] = "native/desktop/frontend/src"

type Site = tuple[str, str]
"""A name as written in one module: ``(module path, name)``."""

_ALIAS_PREFIX: Final[str] = "@/"
_SUFFIXES: Final[tuple[str, ...]] = ("", ".ts", ".tsx", ".d.ts", "/index.ts", "/index.tsx")
_TYPESCRIPT: Final[frozenset[str]] = frozenset({".ts", ".tsx"})
_TAURI_API: Final[str] = "@tauri-apps/api"
_TAURI_NAMESPACE_IMPORT: Final[re.Pattern[str]] = re.compile(
    r"""^import\s+(?:type\s+)?\*\s+as\s+[\w$]+\s+from\s*["']@tauri-apps/api(?:/[^"']*)?["']""", re.MULTILINE
)
_IPC_PRIMITIVES: Final[frozenset[str]] = frozenset({"invoke", "listen", "emit", "emitTo", "once", "Channel"})
_DECLARATION: Final[re.Pattern[str]] = re.compile(
    r"^(?:export\s+)?(?:declare\s+)?(type|interface|enum|class|abstract\s+class)\s+([A-Za-z_$][\w$]*)", re.MULTILINE
)
_IMPORT: Final[re.Pattern[str]] = re.compile(
    r"""^import\s+(?:type\s+)?(?:[\w$]+\s*,\s*)?\{([^}]*)\}\s*from\s*["']([^"']+)["']""", re.MULTILINE
)
_REEXPORT: Final[re.Pattern[str]] = re.compile(
    r"""^export\s+(?:type\s+)?\{([^}]*)\}\s*(?:from\s*["']([^"']+)["'])?""", re.MULTILINE
)
_INLINE_IMPORT: Final[re.Pattern[str]] = re.compile(r"""\bimport\(\s*["']([^"']+)["']\s*\)\s*\.\s*([A-Za-z_$][\w$]*)""")
_INLINE_QUALIFIER: Final[re.Pattern[str]] = re.compile(r"""\bimport\(\s*(["'])\s*\1\s*\)\s*\.""")
_STAR_REEXPORT: Final[re.Pattern[str]] = re.compile(r"""^export\s+\*\s+from\s*["']([^"']+)["']""", re.MULTILINE)
_GENERIC_FUNCTION: Final[re.Pattern[str]] = re.compile(
    r"(?:\bfunction\s+([A-Za-z_$][\w$]*)\s*<|\b(?:const|let)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?<)"
)
_GENERIC_CALL: Final[re.Pattern[str]] = re.compile(r"\b([A-Za-z_$][\w$]*)\s*<")
_FUNCTION_SIGNATURE: Final[re.Pattern[str]] = re.compile(
    r"^(?:export\s+)?(?:async\s+)?function\s+([A-Za-z_$][\w$]*)\s*(?:<[^>]*>)?\s*\(([^)]*)\)\s*:\s*([^{;]+)"
    r"|^(?:export\s+)?const\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?\(([^)]*)\)\s*:\s*([^;]+?)=>",
    re.MULTILINE,
)
_BYTES: Final[re.Pattern[str]] = re.compile(r"^[^,]*:\s*(?:ArrayBuffer|Uint8Array|DataView)\b")
_CASE_LABEL: Final[re.Pattern[str]] = re.compile(r"\bcase\s+([A-Za-z_$][\w$]*)\s*\.")
_TYPE_NAME: Final[re.Pattern[str]] = re.compile(r"(?<![\w$.])([A-Z][\w$]*)")
_PARAMETER_NAME: Final[re.Pattern[str]] = re.compile(r"\s*(?:const\s+)?([A-Za-z_$][\w$]*)")
_PROMISED: Final[re.Pattern[str]] = re.compile(r"\)\s*(?:=>|:)\s*Promise\s*<")
_GENERATED_HEADER_LINES: Final[int] = 6
_STATEMENT_START: Final[re.Pattern[str]] = re.compile(r"^[A-Za-z@/]")
_OPEN: Final[str] = "<([{"
_CLOSE: Final[str] = ">)]}"


def _skip_string(text: str, start: int) -> int:
    quote = text[start]
    index = start + 1
    while index < len(text) and text[index] != quote and (quote == "`" or text[index] != "\n"):
        index += 2 if text[index] == "\\" else 1
    return index + 1


def _skip_comment(text: str, start: int) -> int:
    if text.startswith("//", start):
        end = text.find("\n", start)
        return len(text) if end < 0 else end
    end = text.find("*/", start + 2)
    return len(text) if end < 0 else end + 2


def _scan(text: str, *, keep_strings: bool) -> str:
    """``text`` without comments; string contents are blanked unless ``keep_strings``. Newlines are kept."""
    out: list[str] = []
    index = 0
    while index < len(text):
        if text.startswith(("//", "/*"), index):
            end = _skip_comment(text, index)
            out.append(re.sub(r"[^\n]", " ", text[index:end]))
        elif text[index] in "\"'`":
            end = _skip_string(text, index)
            literal = text[index:end]
            out.append(literal if keep_strings else literal[0] + re.sub(r"[^\n]", " ", literal[1:-1]) + literal[-1])
        else:
            end = index + 1
            out.append(text[index])
        index = end
    return "".join(out)


def _depth_step(text: str, index: int) -> int:
    character = text[index]
    if character == ">" and index and text[index - 1] == "=":
        return 0
    return 1 if character in _OPEN else -1 if character in _CLOSE else 0


def _balanced(text: str, start: int, stops: str = "") -> int:
    """Past the bracketed span opening at ``start``; with ``stops``, at the first stop at depth zero instead."""
    depth = 0
    for index in range(start, len(text)):
        if stops and depth == 0 and text[index] in stops:
            return index
        depth += _depth_step(text, index)
        if depth < 0 or (depth == 0 and not stops):
            return index + (0 if depth < 0 else 1)
    return len(text)


def _names(fragment: str) -> set[str]:
    return set(_TYPE_NAME.findall(fragment))


def _type_parameters(text: str, start: int) -> tuple[set[str], int]:
    """The names a ``<...>`` parameter list at ``start`` introduces, and the index past it."""
    index = len(text) - len(text[start:].lstrip())
    if not text.startswith("<", index):
        return set(), index
    end = _balanced(text, index)
    names: set[str] = set()
    position = index + 1
    while position < end - 1:
        match = _PARAMETER_NAME.match(text, position)
        if match:
            names.add(match.group(1))
        position = _balanced(text, position, ",>") + 1
    return names, end


@dataclass(frozen=True)
class Declaration:
    """One top-level declaration: where it is, the names its body refers to and what its methods promise."""

    path: str
    name: str
    references: frozenset[str]
    promised: frozenset[str]
    writes_fields: bool


@dataclass
class WindowModule:
    """One window source file as the reach needs it."""

    path: str
    text: str
    is_ipc: bool = False
    generated: bool = False
    declarations: dict[str, Declaration] = field(default_factory=dict)
    imports: dict[str, tuple[str, str]] = field(default_factory=dict)
    reexports: dict[str, tuple[str | None, str]] = field(default_factory=dict)
    star_reexports: list[str] = field(default_factory=list)
    value_imports: frozenset[str] = frozenset()
    decoders: dict[str, frozenset[str]] = field(default_factory=dict)


def _declaration_spans(text: str) -> Iterator[tuple[re.Match[str], str]]:
    lines = text.split("\n")
    offsets = [0]
    for line in lines:
        offsets.append(offsets[-1] + len(line) + 1)
    for match in _DECLARATION.finditer(text):
        last = text.count("\n", 0, match.start()) + 1
        while last < len(lines) and not _STATEMENT_START.match(lines[last]):
            last += 1
        yield match, text[match.end() : offsets[last]]


def _promised(body: str) -> frozenset[str]:
    """Type names in the ``Promise<...>`` results of the function members ``body`` declares."""
    names: set[str] = set()
    for match in _PROMISED.finditer(body):
        start = match.end() - 1
        names |= _names(body[start + 1 : _balanced(body, start) - 1])
    return frozenset(names)


def _declaration(path: str, match: re.Match[str], body: str) -> Declaration:
    name = match.group(2)
    introduced, after = _type_parameters(body, 0)
    return Declaration(
        path=path,
        name=name,
        references=frozenset(_names(body) - introduced - {name}),
        promised=frozenset() if name.endswith("Props") else _promised(body) - introduced,
        writes_fields=match.group(1) != "type" or "{" in body[after:],
    )


def is_generated(text: str) -> bool:
    """Whether a module's header says it is generated and not to be edited."""
    head = "\n".join(text.splitlines()[:_GENERATED_HEADER_LINES]).lower()
    return "generated" in head and "do not edit" in head


def _specifiers(clause: str) -> Iterator[tuple[str, str]]:
    """Each ``(name in the source module, name here)`` pair of an import or export clause."""
    for raw in clause.split(","):
        words = raw.replace("type ", " ").split()
        if words:
            yield (words[0], words[2]) if len(words) == 3 and words[1] == "as" else (words[0], words[0])


def _imports(specifiers: str) -> dict[str, tuple[str, str]]:
    """Each imported local name to its module specifier and exported name, inline ``import("m").T`` included."""
    imports: dict[str, tuple[str, str]] = {}
    for match in _IMPORT.finditer(specifiers):
        imports.update((local, (match.group(2), imported)) for imported, local in _specifiers(match.group(1)))
    for match in _INLINE_IMPORT.finditer(specifiers):
        imports.setdefault(match.group(2), (match.group(1), match.group(2)))
    return imports


def _value_imports(specifiers: str) -> frozenset[str]:
    """The local names a module imports as runtime values rather than as types only."""
    names: set[str] = set()
    for match in _IMPORT.finditer(specifiers):
        if not match.group(0).startswith("import type"):
            clause = ",".join(raw for raw in match.group(1).split(",") if not raw.strip().startswith("type "))
            names.update(local for _, local in _specifiers(clause))
    return frozenset(names)


def _decoders(text: str) -> dict[str, frozenset[str]]:
    """Each function whose first parameter is host bytes, to the type names its declared result names."""
    decoders: dict[str, frozenset[str]] = {}
    for match in _FUNCTION_SIGNATURE.finditer(text):
        name, parameters, result = match.group(1, 2, 3) if match.group(1) else match.group(4, 5, 6)
        if _BYTES.match(parameters.strip()):
            decoders[name] = frozenset(_names(result))
    return decoders


def _read_module(path: str, source: str) -> WindowModule:
    """One file's declarations, imports and re-exports."""
    # An inline ``import("m").T`` names ``T``; dropping the qualifier lets it read as a plain reference.
    text = _INLINE_QUALIFIER.sub(lambda match: " " * len(match.group(0)), _scan(source, keep_strings=False))
    specifiers = _scan(source, keep_strings=True)
    module = WindowModule(
        path=path,
        text=text,
        is_ipc=bool(_TAURI_NAMESPACE_IMPORT.search(specifiers)),
        generated=is_generated(source),
    )
    for match, body in _declaration_spans(text):
        declaration = _declaration(path, match, body)
        module.declarations[declaration.name] = declaration
    module.imports = _imports(specifiers)
    module.value_imports = _value_imports(specifiers)
    module.decoders = _decoders(text)
    for clause, target in _REEXPORT.findall(specifiers):
        module.reexports.update((exported, (target or None, local)) for local, exported in _specifiers(clause))
    module.star_reexports = _STAR_REEXPORT.findall(specifiers)
    module.is_ipc = module.is_ipc or any(
        target.startswith(_TAURI_API) and imported in _IPC_PRIMITIVES for target, imported in module.imports.values()
    )
    return module


def _joined(importer: str, specifier: str) -> str | None:
    if specifier.startswith(_ALIAS_PREFIX):
        return f"{WINDOW_SOURCE}/{specifier[len(_ALIAS_PREFIX) :]}"
    if not specifier.startswith("."):
        return None
    parts: list[str] = []
    for part in (*PurePosixPath(importer).parent.parts, *PurePosixPath(specifier).parts):
        if part == "..":
            parts = parts[:-1]
        elif part != ".":
            parts.append(part)
    return "/".join(parts)


class WindowIndex:
    """Every window module, with name resolution across imports and re-exports."""

    def __init__(self, modules: Mapping[str, WindowModule]) -> None:
        """Index ``modules`` by path, and their declarations by name."""
        self.modules = dict(modules)
        self._by_name: dict[str, list[Declaration]] = {}
        for module in self.modules.values():
            for declaration in module.declarations.values():
                self._by_name.setdefault(declaration.name, []).append(declaration)

    def declarations(self) -> Iterator[Declaration]:
        """Every top-level declaration in the window."""
        for module in self.modules.values():
            yield from module.declarations.values()

    def _target(self, importer: str, specifier: str) -> str | None:
        base = _joined(importer, specifier)
        if base is None:
            return None
        return next((base + suffix for suffix in _SUFFIXES if base + suffix in self.modules), None)

    def module_of(self, importer: str, specifier: str) -> WindowModule | None:
        """The window module ``specifier`` names from ``importer``, when it is one."""
        target = self._target(importer, specifier)
        return None if target is None else self.modules[target]

    def _through(self, importer: str, specifier: str, name: str, seen: frozenset[Site]) -> list[Declaration]:
        target = self._target(importer, specifier)
        return [] if target is None else self.exported(target, name, seen)

    def exported(self, path: str, name: str, seen: frozenset[Site] = frozenset()) -> list[Declaration]:
        """What ``name`` exported from ``path`` declares, followed through re-exports."""
        if (path, name) in seen or path not in self.modules:
            return []
        seen = seen | {(path, name)}
        module = self.modules[path]
        if name in module.declarations:
            return [module.declarations[name]]
        if name in module.reexports:
            target, local = module.reexports[name]
            return self.resolve(path, local, seen) if target is None else self._through(path, target, local, seen)
        return [found for target in module.star_reexports for found in self._through(path, target, name, seen)]

    def resolve(self, path: str, name: str, seen: frozenset[Site] = frozenset()) -> list[Declaration]:
        """The declarations ``name`` written in ``path`` refers to; by name across the window when unexplained."""
        module = self.modules.get(path)
        if module is not None and name in module.declarations:
            return [module.declarations[name]]
        if module is not None and name in module.imports:
            specifier, imported = module.imports[name]
            return self._through(path, specifier, imported, seen)
        return list(self._by_name.get(name, ()))


def _type_arguments(text: str, callees: frozenset[str]) -> set[str]:
    """Type names in the type arguments of calls to ``callees``."""
    names: set[str] = set()
    for match in _GENERIC_CALL.finditer(text):
        if match.group(1) not in callees:
            continue
        end = _balanced(text, match.end() - 1)
        if text[end : end + 1] == "(":
            names |= _names(text[match.end() : end - 1])
    return names


def _wrappers(modules: Iterable[WindowModule]) -> frozenset[str]:
    """The generic functions the IPC modules declare."""
    names: set[str] = set()
    for module in modules:
        names.update(match.group(1) or match.group(2) for match in _GENERIC_FUNCTION.finditer(module.text))
    return frozenset(names)


def _frame_roots(index: WindowIndex, module: WindowModule) -> set[Site]:
    """What an IPC module decodes the host's bytes into.

    That is its decoders' results and those of the decoders it imports, and every type a module declares
    whose tag table it matches decoded bytes against (``case FrameTag.data:``).
    """
    roots = {(module.path, name) for names in module.decoders.values() for name in names}
    tag_tables = set(_CASE_LABEL.findall(module.text)) & module.value_imports
    for local, (specifier, imported) in module.imports.items():
        source = index.module_of(module.path, specifier)
        if source is None:
            continue
        roots |= {(source.path, name) for name in source.decoders.get(imported, ())}
        if local in tag_tables:
            roots |= {(source.path, name) for name in source.declarations}
    return roots


def _ipc_roots(index: WindowIndex) -> set[Site]:
    """Each root type an IPC signature names, with the module it is written in."""
    wrappers = _wrappers(module for module in index.modules.values() if module.is_ipc)
    roots: set[Site] = set()
    for module in index.modules.values():
        if module.is_ipc:
            roots |= {(module.path, name) for name in _names(module.text)} | _frame_roots(index, module)
        else:
            roots |= {(module.path, name) for name in _type_arguments(module.text, wrappers)}
    return roots


def _reached(index: WindowIndex, roots: Iterable[Site]) -> set[Site]:
    """Every declaration the roots reach through type references, as ``(declaring path, name)``."""
    found: set[Site] = set()
    pending = list(roots)
    visited: set[Site] = set()
    while pending:
        site = pending.pop()
        if site in visited:
            continue
        visited.add(site)
        for declaration in index.resolve(*site):
            if (declaration.path, declaration.name) not in found:
                found.add((declaration.path, declaration.name))
                pending.extend((declaration.path, reference) for reference in declaration.references)
    return found


def _answers_from_host(index: WindowIndex, declaration: Declaration, reached: set[Site]) -> bool:
    return any(
        (found.path, found.name) in reached
        for name in declaration.promised
        for found in index.resolve(declaration.path, name)
    )


def _with_ports(index: WindowIndex, roots: set[Site]) -> set[Site]:
    """What the roots reach once every port whose methods promise a reached type is a root too."""
    candidates = [declaration for declaration in index.declarations() if declaration.promised]
    reached = _reached(index, roots)
    ports: set[Site] = set()
    while True:
        found = {
            (declaration.path, declaration.name)
            for declaration in candidates
            if (declaration.path, declaration.name) not in ports and _answers_from_host(index, declaration, reached)
        }
        if not found:
            return reached
        ports |= found
        reached = _reached(index, roots | ports)


def _generated_alias(index: WindowIndex, declaration: Declaration, seen: frozenset[Site] = frozenset()) -> bool:
    """Whether a field-less alias names only generated types, directly or through such aliases."""
    site = (declaration.path, declaration.name)
    if declaration.writes_fields or site in seen:
        return False
    resolved = [found for name in declaration.references for found in index.resolve(declaration.path, name)]
    return bool(resolved) and all(
        index.modules[found.path].generated or _generated_alias(index, found, seen | {site}) for found in resolved
    )


def _window_index(root: Path, excluded: Callable[[str], bool]) -> WindowIndex:
    """Every TypeScript module under the window source that ``excluded`` keeps, read once."""
    return WindowIndex(
        {
            relative: _read_module(relative, (root / relative).read_text(encoding="utf-8"))
            for relative in repository_files(root, under=(WINDOW_SOURCE,))
            if PurePosixPath(relative).suffix in _TYPESCRIPT and not excluded(relative)
        }
    )


def wire_declarations(root: Path, excluded: Callable[[str], bool]) -> set[Site]:
    """Every window declaration an IPC signature reaches that adds a field, as ``(declaring path, name)``."""
    index = _window_index(root, excluded)
    return {
        site
        for site in _with_ports(index, _ipc_roots(index))
        if not _generated_alias(index, index.modules[site[0]].declarations[site[1]])
    }
