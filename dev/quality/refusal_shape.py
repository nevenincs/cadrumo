"""Measure the shape of every registered refusal the modelo and filing code builds.

A refusal reaches the operator as served words plus a door: the catalogue
sentence worded in the operator's language, and the next step or terminal
verdict the runtime reads from the error (``error_next_step`` and
``nested_terminal_precondition_verdict`` in the operation error detail). This
module reads the four governed source trees, finds every construction of a
registered error class, and reports for each site whether it gives a door and
whether it hands the renderer free text instead of a catalogue key.

A site passes the door check when it passes ``next_step``, ``precondition_failure``,
``precondition_verdict``, ``profile_precondition_verdict``, ``no_recovery_outcome`` or
``registry_failure`` (the calculation-registry classification its policy maps to a
verdict) as something other than the literal ``None``, spreads a
mapping into the call, or builds a class that carries a class-level default door.

The checked-in ratchet lists the sites that predate the gate. Regenerate it with::

    python -m dev.quality.refusal_shape --write

A call ``Cls.factory(...)`` is also a construction site when ``Cls`` resolves to a
registered error class and ``factory`` is a classmethod of it (or of a base) whose
body returns ``cls(...)``. The site has a door when the call passes a door keyword,
when the factory's own ``cls(...)`` passes one, or when the class carries a default
door. It is free text when the call passes positional arguments, the factory's
``cls(...)`` passes no ``translated_message`` and the code does not take its message
from the registry; a factory whose source cannot be read counts as keyed. Any other
attribute call, including a classmethod that does not return ``cls(...)``, is no site.

Site identity is the repository-relative path, the enclosing qualified name, the
registered code and the ordinal among that function's constructions of that code,
never a line number, so unrelated edits leave the ratchet untouched. Direct and
factory constructions share one ordinal sequence per function and code, in source
order, so a function without factory calls keeps the ordinals it always had.
"""

from __future__ import annotations

import ast
import importlib
import inspect
import json
import sys
import textwrap
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from dev.paths import REPO_ROOT, UTF_8

__all__ = [
    "GOVERNED_TREES",
    "LOCALES",
    "RATCHET_PATH",
    "Site",
    "doorless_site_ids",
    "free_text_site_ids",
    "main",
    "missing_words",
    "read_ratchet",
    "scan_repository",
    "scan_source",
]

GOVERNED_TREES: Final[tuple[str, ...]] = (
    "src/cadrumo/application/modelo",
    "src/cadrumo/application/filing",
    "src/cadrumo/domain/modelos",
    "src/cadrumo/domain/filing",
)
LOCALES: Final[tuple[str, ...]] = ("es", "ca", "en", "hu")
RATCHET_PATH: Final[Path] = REPO_ROOT / "dev/quality/metadata/refusal_shape_ratchet.json"
_DOOR_KEYWORDS: Final[frozenset[str]] = frozenset(
    {
        "next_step",
        "precondition_failure",
        "precondition_verdict",
        "profile_precondition_verdict",
        "no_recovery_outcome",
        "registry_failure",
    }
)
_SRC_ROOT: Final[Path] = REPO_ROOT / "src"


@dataclass(frozen=True)
class Site:
    """One construction of a registered error class."""

    path: str
    qualname: str
    code: str
    ordinal: int
    line: int
    has_door: bool
    free_text: bool
    message_key: str
    translated_keys: tuple[str, ...]

    @property
    def site_id(self) -> str:
        """The stable identity the ratchet records; it carries no line number."""
        return f"{self.path}::{self.qualname}::{self.code}::{self.ordinal}"


def _resolve_relative(module: str, node: ast.ImportFrom, *, is_package: bool) -> str:
    if node.level == 0:
        return node.module or ""
    base = module.split(".")
    if not is_package:
        base = base[:-1]
    base = base[: len(base) - (node.level - 1)]
    return ".".join([*base, *([node.module] if node.module is not None else [])])


def _import_map(tree: ast.AST, module: str, *, is_package: bool) -> dict[str, tuple[str, str]]:
    imports: dict[str, tuple[str, str]] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            target = _resolve_relative(module, node, is_package=is_package)
            for alias in node.names:
                imports[alias.asname or alias.name] = (target, alias.name)
    return imports


def _resolve(expr: ast.expr, module_object: object | None, imports: Mapping[str, tuple[str, str]]) -> object | None:
    if isinstance(expr, ast.Name):
        if module_object is not None and hasattr(module_object, expr.id):
            return getattr(module_object, expr.id)
        if expr.id in imports:
            target, name = imports[expr.id]
            imported = importlib.import_module(target)
            if hasattr(imported, name):
                return getattr(imported, name)
            return importlib.import_module(f"{target}.{name}")
        return None
    if isinstance(expr, ast.Attribute):
        base = _resolve(expr.value, module_object, imports)
        return getattr(base, expr.attr, None) if base is not None else None
    return None


def _built(error_type: type, arguments: tuple[str, ...]) -> BaseException | None:
    """Build ``error_type`` from ``arguments``, or ``None`` when it refuses them."""
    try:
        built = error_type(*arguments)
    except Exception:
        return None
    return built if isinstance(built, BaseException) else None


def _bare_instance(error_type: type) -> BaseException | None:
    """Build ``error_type`` with no site arguments, or ``None`` when it cannot be built that way.

    A class whose initializer requires one reason token is tried with a single placeholder.
    """
    for arguments in ((), ("x",)):
        built = _built(error_type, arguments)
        if built is not None:
            return built
    return None


def _carries_step(instance: BaseException) -> bool:
    """Whether the runtime's step reader finds a step on ``instance``; an unreadable step is no door."""
    from cadrumo.application.operations.next_step import error_next_step
    from cadrumo.core.external_constants import OutputLanguage

    try:
        return error_next_step(instance, OutputLanguage.EN) is not None
    except Exception:
        return False


_DEFAULT_DOOR_CACHE: dict[type, bool] = {}


def class_default_door(error_type: type) -> bool:
    """Whether the class itself carries a door the runtime reads without a site argument."""
    cached = _DEFAULT_DOOR_CACHE.get(error_type)
    if cached is not None:
        return cached
    from cadrumo.application.cli_exception_preconditions import nested_terminal_precondition_verdict

    instance = _bare_instance(error_type)
    door = False
    if instance is not None:
        door = nested_terminal_precondition_verdict(instance) is not None
        if not door:
            door = _carries_step(instance)
    _DEFAULT_DOOR_CACHE[error_type] = door
    return door


def _scope_names(tree: ast.AST) -> dict[int, str]:
    """Map each node id to the qualified name of its enclosing class and function chain."""
    scopes: dict[int, str] = {}

    def visit(node: ast.AST, scope: str) -> None:
        for child in ast.iter_child_nodes(node):
            child_scope = scope
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                child_scope = f"{scope}.{child.name}" if scope else child.name
            scopes[id(child)] = child_scope or "<module>"
            visit(child, child_scope)

    visit(tree, "")
    return scopes


def _has_literal_door(call: ast.Call) -> bool:
    for keyword in call.keywords:
        if keyword.arg is None:
            return True
        if keyword.arg in _DOOR_KEYWORDS and not (
            isinstance(keyword.value, ast.Constant) and keyword.value.value is None
        ):
            return True
    return False


def _literal_translated_key(call: ast.Call) -> tuple[bool, str | None]:
    """Whether ``translated_message`` is passed, and its key when that is a string literal."""
    for keyword in call.keywords:
        if keyword.arg == "translated_message":
            value = keyword.value
            literal = value.value if isinstance(value, ast.Constant) and isinstance(value.value, str) else None
            return True, literal
    return False, None


@dataclass(frozen=True)
class _Factory:
    """What a classmethod factory's body does with the ``cls(...)`` it returns."""

    has_door: bool
    passes_translated_message: bool


def _factory_of(target: type, attribute: str) -> _Factory | None:
    """Describe ``target.attribute`` when it is a classmethod returning ``cls(...)``, else ``None``."""
    try:
        member = inspect.getattr_static(target, attribute)
    except AttributeError:
        return None
    if not isinstance(member, classmethod):
        return None
    try:
        tree = ast.parse(textwrap.dedent(inspect.getsource(member.__func__)))
    except (OSError, TypeError, SyntaxError):
        return None
    function = next(
        (node for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))), None
    )
    if function is None or not function.args.args:
        return None
    receiver = function.args.args[0].arg
    built = [
        node.value
        for node in ast.walk(function)
        if isinstance(node, ast.Return)
        and isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Name)
        and node.value.func.id == receiver
    ]
    if not built:
        return None
    return _Factory(
        has_door=any(_has_literal_door(call) for call in built),
        passes_translated_message=any(_literal_translated_key(call)[0] for call in built),
    )


def scan_source(source: str, *, path: str, module: str, module_object: object | None = None) -> list[Site]:
    """Return every registered-error construction in ``source``, in source order."""
    from cadrumo.core.errors.error_codes import get_registered_error_code
    from cadrumo.core.errors.hierarchy import CadrumoError

    tree = ast.parse(source)
    imports = _import_map(tree, module, is_package=path.endswith("/__init__.py"))
    scopes = _scope_names(tree)
    calls = sorted(
        (node for node in ast.walk(tree) if isinstance(node, ast.Call)),
        key=lambda node: (node.lineno, node.col_offset),
    )
    ordinals: dict[tuple[str, str], int] = defaultdict(int)
    sites: list[Site] = []
    for call in calls:
        factory: _Factory | None = None
        target = _resolve(call.func, module_object, imports)
        if not (inspect.isclass(target) and issubclass(target, CadrumoError)):
            if not isinstance(call.func, ast.Attribute):
                continue
            target = _resolve(call.func.value, module_object, imports)
            if not (inspect.isclass(target) and issubclass(target, CadrumoError)):
                continue
            factory = _factory_of(target, call.func.attr)
            if factory is None:
                continue
        code = get_registered_error_code(target)
        qualname = scopes.get(id(call), "<module>")
        ordinal = ordinals[(qualname, code.code)]
        ordinals[(qualname, code.code)] += 1
        passed, literal_key = _literal_translated_key(call)
        door = _has_literal_door(call) or class_default_door(target)
        if factory is not None:
            door = door or factory.has_door
            passed = passed or factory.passes_translated_message
        sites.append(
            Site(
                path=path,
                qualname=qualname,
                code=code.code,
                ordinal=ordinal,
                line=call.lineno,
                has_door=door,
                free_text=bool(call.args) and not passed and not code.public_message_from_registry,
                message_key=code.message_key,
                translated_keys=() if literal_key is None else (literal_key,),
            )
        )
    return sites


def _module_name(path: Path) -> tuple[str, bool]:
    parts = list(path.relative_to(_SRC_ROOT).with_suffix("").parts)
    is_package = parts[-1] == "__init__"
    if is_package:
        parts.pop()
    return ".".join(parts), is_package


def scan_repository(root: Path = REPO_ROOT, trees: Sequence[str] = GOVERNED_TREES) -> list[Site]:
    """Scan the governed trees under ``root``; an unimportable module raises."""
    sites: list[Site] = []
    for tree in trees:
        for path in sorted((root / tree).rglob("*.py")):
            if "tests" in path.relative_to(root / tree).parts:
                continue
            module, _ = _module_name(path)
            module_object = importlib.import_module(module)
            sites.extend(
                scan_source(
                    path.read_text(encoding=UTF_8),
                    path=path.relative_to(root).as_posix(),
                    module=module,
                    module_object=module_object,
                )
            )
    return sites


def missing_words(sites: Iterable[Site]) -> list[str]:
    """Return ``locale:key`` for every registered or literal key a locale cannot serve."""
    from cadrumo.core.i18n.render import lookup_translation

    keys = {site.message_key for site in sites} | {key for site in sites for key in site.translated_keys}
    return sorted(
        f"{locale}:{key}" for key in keys for locale in LOCALES if lookup_translation(key, locale=locale) is None
    )


def doorless_site_ids(sites: Iterable[Site]) -> list[str]:
    """Sorted identities of the sites that give no door."""
    return sorted(site.site_id for site in sites if not site.has_door)


def free_text_site_ids(sites: Iterable[Site]) -> list[str]:
    """Sorted identities of the sites that pass free text and no catalogue key."""
    return sorted(site.site_id for site in sites if site.free_text)


def read_ratchet(path: Path = RATCHET_PATH) -> dict[str, list[str]]:
    """Read the checked-in lists."""
    data = json.loads(path.read_text(encoding=UTF_8))
    return {"doorless": list(data["doorless"]), "free_text": list(data["free_text"])}


def _write_ratchet(sites: Sequence[Site], path: Path = RATCHET_PATH) -> None:
    payload = {
        "description": (
            "Refusal-shape ratchet. Regenerate with `python -m dev.quality.refusal_shape --write`; "
            "entries may only be removed by giving the site a door or served words."
        ),
        "doorless": doorless_site_ids(sites),
        "free_text": free_text_site_ids(sites),
    }
    path.write_text(json.dumps(payload, indent=1) + "\n", encoding=UTF_8)


def main(argv: Sequence[str] | None = None) -> int:
    """Print the counts, or rewrite the ratchet with ``--write``."""
    arguments = list(sys.argv[1:] if argv is None else argv)
    sites = scan_repository()
    if "--write" in arguments:
        _write_ratchet(sites)
    print(f"doorless sites: {len(doorless_site_ids(sites))}; free-text sites: {len(free_text_site_ids(sites))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
