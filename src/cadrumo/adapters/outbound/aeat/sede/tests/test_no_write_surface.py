"""Write-surface checks for cadrumo.adapters.outbound.aeat.sede.

The sede adapter is a read-only boundary. These checks reject mutation
verbs in call contexts and reject non-read boundary record modes while
allowing browser events used to open selectors and read document links.
"""

from __future__ import annotations

import ast
import re
from collections import Counter
from collections.abc import Iterator
from pathlib import Path, PurePosixPath

import pytest

from ......core.directory_scan import scan_directory

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


_SEDE_ROOT = Path(__file__).resolve().parent.parent
_SEDE_PACKAGE = "cadrumo.adapters.outbound.aeat.sede"
_FIXTURE = _SEDE_ROOT / "_no_write_surface_fixture.txt"

_OBSERVATION_STORE_MODULE = "observation_store.py"
_PORT_ADAPTER_MODULE = "filed_observation_persistence.py"
_OPERATION_SUBMISSION_TEST = "tests/test_filed_history_operation.py"

_PROFILE_PERSISTENCE_PACKAGE = "cadrumo.adapters.persistence.profile"
_STORAGE_PERSISTENCE_PACKAGE = "cadrumo.adapters.persistence.storage"
_OPERATION_SUPERVISOR_MODULE = "cadrumo.application.operations.supervisor"

_DYNAMIC_ATTRIBUTE_WRITERS = frozenset({"setattr", "delattr", "__setattr__", "__delattr__"})


def _load_forbidden_verbs() -> tuple[str, ...]:
    """Return the forbidden-verb list with comments + blanks stripped."""
    lines = _FIXTURE.read_text(encoding="utf-8").splitlines()
    return tuple(line.strip() for line in lines if line.strip() and not line.strip().startswith("#"))


def _iter_sede_sources() -> tuple[Path, ...]:
    """Every .py file under cadrumo.adapters.outbound.aeat.sede (includes this test module)."""
    return tuple(p for p in scan_directory(_SEDE_ROOT, pattern="*.py", recursive=True) if "__pycache__" not in p.parts)


def _iter_sede_production_sources() -> tuple[Path, ...]:
    """Every production .py file under the sede boundary, excluding tests."""
    return tuple(source for source in _iter_sede_sources() if "tests" not in source.parts)


def _relative_key(source: Path) -> str:
    """The source's POSIX path relative to the sede package root."""
    return source.relative_to(_SEDE_ROOT).as_posix()


def _package_of(relative_path: str) -> str:
    """The dotted package that owns ``relative_path`` inside the sede package."""
    parent = PurePosixPath(relative_path).parent.parts
    return ".".join((_SEDE_PACKAGE, *(part for part in parent if part != ".")))


def _absolute_import_module(node: ast.ImportFrom, package: str) -> str:
    """Resolve an ``ImportFrom`` module against the importing package."""
    if node.level == 0:
        return node.module or ""
    base = package.split(".")[: len(package.split(".")) - node.level + 1]
    return ".".join((*base, node.module)) if node.module else ".".join(base)


def _walk_scope(node: ast.AST) -> Iterator[ast.AST]:
    """Yield the descendants of ``node`` without entering the body of a nested class."""
    for child in ast.iter_child_nodes(node):
        yield child
        if not isinstance(child, ast.ClassDef):
            yield from _walk_scope(child)


def _top_level_classes(tree: ast.Module) -> tuple[ast.ClassDef, ...]:
    return tuple(node for node in tree.body if isinstance(node, ast.ClassDef))


def _bound_names(node: ast.AST) -> tuple[str, ...]:
    """Names that ``node`` itself binds, rebinds, deletes or redirects in its scope."""
    if isinstance(node, (ast.Import, ast.ImportFrom)):
        return tuple((alias.asname or alias.name).split(".")[0] for alias in node.names)
    if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
        return (node.name,)
    if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
        return (node.id,)
    if isinstance(node, ast.ExceptHandler) and node.name:
        return (node.name,)
    if isinstance(node, (ast.Global, ast.Nonlocal)):
        return tuple(node.names)
    if isinstance(node, (ast.MatchAs, ast.MatchStar)) and node.name:
        return (node.name,)
    if isinstance(node, ast.MatchMapping) and node.rest:
        return (node.rest,)
    return ()


def _binding_sites(root: ast.AST, name: str) -> list[ast.AST]:
    """Every node under ``root`` (excluding parameters) that binds ``name``."""
    return [node for node in ast.walk(root) if name in _bound_names(node)]


def _names_imported_only_from(tree: ast.Module, package: str, prefix: str) -> frozenset[str]:
    """Names whose single binding anywhere in the module is an import from a module under ``prefix``.

    A name imported twice, rebound, shadowed by a local definition, or imported
    from any other module is not trusted.
    """
    trusted: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom):
            continue
        module = _absolute_import_module(node, package)
        if module != prefix and not module.startswith(f"{prefix}."):
            continue
        for alias in node.names:
            name = alias.asname or alias.name
            if len(_binding_sites(tree, name)) == 1:
                trusted.add(name)
    return frozenset(trusted)


def _is_self_attribute(node: ast.expr, attribute: str) -> bool:
    return (
        isinstance(node, ast.Attribute)
        and node.attr == attribute
        and isinstance(node.value, ast.Name)
        and node.value.id == "self"
    )


def _is_dynamic_attribute_write(node: ast.AST, attribute: str) -> bool:
    """A ``setattr``-family call naming ``attribute`` or computing the attribute name."""
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    called = func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else None
    if called not in _DYNAMIC_ATTRIBUTE_WRITERS:
        return False
    literal_names = [arg.value for arg in node.args if isinstance(arg, ast.Constant) and isinstance(arg.value, str)]
    return attribute in literal_names or not literal_names


def _touches_instance_namespace(node: ast.AST) -> bool:
    """Any reach into ``__dict__`` or ``vars(...)``, through which attributes can be written by key."""
    if isinstance(node, ast.Attribute) and node.attr == "__dict__":
        return True
    return isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "vars"


def _attribute_write_sites(tree: ast.Module, attribute: str) -> list[ast.AST]:
    """Every construct in the module that writes, deletes or could write ``attribute`` on any object.

    Store and delete contexts cover plain, tuple, starred, annotated, augmented,
    ``for`` and ``with`` targets on any receiver, inside or outside the class.
    """
    return [
        node
        for node in ast.walk(tree)
        if (isinstance(node, ast.Attribute) and node.attr == attribute and isinstance(node.ctx, (ast.Store, ast.Del)))
        or _is_dynamic_attribute_write(node, attribute)
        or _touches_instance_namespace(node)
    ]


def _annotation_name(annotation: ast.expr | None) -> str | None:
    return annotation.id if isinstance(annotation, ast.Name) else None


def _method(cls: ast.ClassDef, name: str) -> ast.FunctionDef | None:
    return next((item for item in cls.body if isinstance(item, ast.FunctionDef) and item.name == name), None)


def _save_calls(cls: ast.ClassDef, accessors: frozenset[str]) -> list[ast.Call]:
    """``self.<accessor>.save(...)`` calls in the class's own scope, nested classes excluded."""
    return [
        node
        for node in _walk_scope(cls)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "save"
        and any(_is_self_attribute(node.func.value, accessor) for accessor in accessors)
    ]


def _call_line(node: ast.Call) -> int:
    return node.func.end_lineno or node.lineno


def _sanctioned_repository_bind(init: ast.FunctionDef, profile_types: frozenset[str]) -> ast.Assign | None:
    """The single ``self._repository = <profile parameter>`` statement directly in ``__init__``.

    The parameter must still hold its argument at the bind: any other binding of
    that name anywhere in ``__init__`` disqualifies it.
    """
    profile_parameters = {
        argument.arg
        for argument in (*init.args.posonlyargs, *init.args.args, *init.args.kwonlyargs)
        if _annotation_name(argument.annotation) in profile_types
    }
    binds = [
        statement
        for statement in init.body
        if isinstance(statement, ast.Assign)
        and len(statement.targets) == 1
        and _is_self_attribute(statement.targets[0], "_repository")
    ]
    if len(binds) != 1:
        return None
    value = binds[0].value
    if not isinstance(value, ast.Name) or value.id not in profile_parameters or _binding_sites(init, value.id):
        return None
    return binds[0]


def _profile_repository_forwarding_lines(tree: ast.Module, package: str) -> list[int]:
    """Port adapters whose ``_repository`` is only ever the profile repository they were given.

    A top-level class qualifies when its ``__init__`` holds the module's only
    sanctioned bind of ``self._repository``, from a parameter annotated with a
    trusted profile persistence type. Any other write to ``_repository``
    anywhere in the module, or any rebinding of ``self``, withdraws the
    exemption from every class. A qualifying class's own-scope
    ``self._repository.save(...)`` calls and its ``save`` definition are local
    encrypted persistence, not a Sede write. The parameter annotation is trusted
    as declared; the object actually passed at runtime is not checked.
    """
    if _binding_sites(tree, "self"):
        return []
    profile_types = _names_imported_only_from(tree, package, _PROFILE_PERSISTENCE_PACKAGE)
    qualifying: list[tuple[ast.ClassDef, ast.Assign]] = []
    for cls in _top_level_classes(tree):
        init = _method(cls, "__init__")
        bind = _sanctioned_repository_bind(init, profile_types) if init is not None else None
        if bind is not None:
            qualifying.append((cls, bind))
    sanctioned_targets = [bind.targets[0] for _, bind in qualifying]
    if any(
        not any(site is target for target in sanctioned_targets) for site in _attribute_write_sites(tree, "_repository")
    ):
        return []
    lines: list[int] = []
    for cls, _ in qualifying:
        lines.extend(_call_line(call) for call in _save_calls(cls, frozenset({"_repository"})))
        save_method = _method(cls, "save")
        if save_method is not None:
            lines.append(save_method.lineno)
    return lines


def _is_property(item: ast.stmt) -> bool:
    return isinstance(item, ast.FunctionDef) and any(
        isinstance(decorator, ast.Name) and decorator.id == "property" for decorator in item.decorator_list
    )


def _storage_property_save_lines(tree: ast.Module, package: str) -> list[int]:
    """``self.<property>.save(...)`` where the property returns a secure-storage repository.

    A property qualifies when its return annotation names a trusted type imported
    from the secure storage package, or a module class derived from one; when it
    is the only member of its class with that name; and when nothing in the
    module writes that attribute. The return annotation is trusted as declared;
    what the accessor returns at runtime is not checked.
    """
    if _binding_sites(tree, "self"):
        return []
    storage_types = set(_names_imported_only_from(tree, package, _STORAGE_PERSISTENCE_PACKAGE))
    for cls in _top_level_classes(tree):
        base_names = {
            base.value.id
            if isinstance(base, ast.Subscript) and isinstance(base.value, ast.Name)
            else _annotation_name(base)
            for base in cls.bases
        }
        if base_names & storage_types and len(_binding_sites(tree, cls.name)) == 1:
            storage_types.add(cls.name)
    lines: list[int] = []
    for cls in _top_level_classes(tree):
        member_names = Counter(
            item.name for item in cls.body if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
        )
        accessors = frozenset(
            item.name
            for item in cls.body
            if isinstance(item, ast.FunctionDef)
            and _is_property(item)
            and _annotation_name(item.returns) in storage_types
            and member_names[item.name] == 1
            and not _attribute_write_sites(tree, item.name)
        )
        lines.extend(_call_line(call) for call in _save_calls(cls, accessors))
    return lines


def _only_bound_as_supervisor(function: ast.AST, name: str, supervisor_types: frozenset[str]) -> bool:
    """Whether every binding of ``name`` in ``function`` is ``name = OperationSupervisor(...)``.

    Parameters, walrus, loop, ``with``, tuple, augmented, import, ``global`` and
    nested-definition bindings all disqualify the name.
    """
    arguments = function.args if isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef)) else None
    if arguments is not None and name in {
        argument.arg
        for argument in (
            *arguments.posonlyargs,
            *arguments.args,
            *arguments.kwonlyargs,
            *(item for item in (arguments.vararg, arguments.kwarg) if item is not None),
        )
    }:
        return False
    sanctioned_targets = [
        statement.targets[0]
        for statement in ast.walk(function)
        if isinstance(statement, ast.Assign)
        and len(statement.targets) == 1
        and isinstance(statement.targets[0], ast.Name)
        and statement.targets[0].id == name
        and isinstance(statement.value, ast.Call)
        and isinstance(statement.value.func, ast.Name)
        and statement.value.func.id in supervisor_types
    ]
    sites = [site for site in _binding_sites(function, name) if site is not function]
    return bool(sanctioned_targets) and all(any(site is target for target in sanctioned_targets) for site in sites)


def _operation_supervisor_submit_lines(tree: ast.Module, package: str) -> list[int]:
    """``<name>.submit(...)`` where ``<name>`` is only ever an ``OperationSupervisor`` in its function."""
    supervisor_types = _names_imported_only_from(tree, package, _OPERATION_SUPERVISOR_MODULE) & {"OperationSupervisor"}
    exempt: dict[int, int] = {}
    for function in (node for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))):
        for node in _walk_scope(function):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "submit"
                and isinstance(node.func.value, ast.Name)
                and _only_bound_as_supervisor(function, node.func.value.id, supervisor_types)
            ):
                exempt[id(node)] = _call_line(node)
    return list(exempt.values())


def _exempt_call_lines(relative_path: str, tree: ast.Module, verb: str) -> Counter[int]:
    """Lines holding sanctioned local calls of ``verb`` in ``relative_path``, with multiplicity.

    Local encrypted persistence and the in-process operation queue are allowed;
    this guard exists for REMOTE Sede mutation verbs. Every exemption is keyed
    on the exact path relative to the sede root and on the typed binding of the
    receiver, so the same text elsewhere, or a receiver rebound to anything
    else, is still refused.
    """
    package = _package_of(relative_path)
    if verb == "save" and relative_path == _OBSERVATION_STORE_MODULE:
        return Counter(_storage_property_save_lines(tree, package))
    if verb == "save" and relative_path == _PORT_ADAPTER_MODULE:
        return Counter(_profile_repository_forwarding_lines(tree, package))
    if verb == "submit" and relative_path == _OPERATION_SUBMISSION_TEST:
        return Counter(_operation_supervisor_submit_lines(tree, package))
    return Counter()


def _offending_lines(relative_path: str, source_text: str, verb: str) -> tuple[int, ...]:
    """Line numbers in ``source_text`` that call ``verb`` outside a sanctioned exemption."""
    exempt = _exempt_call_lines(relative_path, ast.parse(source_text), verb)
    pattern = re.compile(rf"\b{re.escape(verb)}\s*\(", re.IGNORECASE)
    return tuple(
        line_no
        for line_no, line in enumerate(source_text.splitlines(), start=1)
        if len(pattern.findall(line)) > exempt[line_no]
    )


class TestNoCallContextWriteVerbs:
    """Forbidden verbs must never appear as a call-site in cadrumo.adapters.outbound.aeat.sede."""

    @pytest.mark.parametrize("verb", _load_forbidden_verbs())
    def test_verb_never_called(self, verb: str) -> None:
        offenders: list[str] = []
        own_key = _relative_key(Path(__file__).resolve())
        for source in _iter_sede_sources():
            relative_path = _relative_key(source)
            if relative_path == own_key:
                # The guard test references the verbs as fixture strings,
                # not as calls — skip its own body.
                continue
            source_text = source.read_text(encoding="utf-8")
            lines = source_text.splitlines()
            offenders.extend(
                f"{relative_path}:{line_no}: {lines[line_no - 1].strip()}"
                for line_no in _offending_lines(relative_path, source_text, verb)
            )
        assert not offenders, (
            f"Forbidden write verb {verb!r} used in a call context inside cadrumo.adapters.outbound.aeat.sede:\n"
            + "\n".join(offenders)
        )


class TestNoWriteModeLiteral:
    """No boundary-crossing record may declare a mode other than 'read'."""

    def test_no_write_mode_literal(self) -> None:
        # Compose the forbidden literal at runtime so neither this test
        # file nor any source matching the fixture path trips the guard.
        mode_char = "w"
        forbidden = f'mode: Literal["{mode_char + "rite"}"]'
        for source in _iter_sede_sources():
            content = source.read_text(encoding="utf-8")
            assert forbidden not in content, (
                f"{source.relative_to(_SEDE_ROOT)}: boundary-crossing record declares a non-read mode literal"
            )


class TestReadPostCanary:
    """The only raw POST is the legally guarded already-read document retrieval."""

    def test_only_the_guarded_notification_detail_post_exists(self) -> None:
        post_sites: list[tuple[Path, int]] = []
        sources: dict[Path, str] = {}
        for source in _iter_sede_production_sources():
            content = source.read_text(encoding="utf-8")
            sources[source] = content
            for line_number, line in enumerate(content.splitlines(), start=1):
                if re.search(r"\.post\s*\(", line):
                    post_sites.append((source, line_number))

        assert len(post_sites) == 1, f"unexpected raw POST call sites: {post_sites}"
        source, _ = post_sites[0]
        assert source.name == "notifications.py"

        content = sources[source]
        function_start = content.index("async def fetch_notification_document")
        function_end = content.index("\n\nasync def fetch_notifications_query", function_start)
        function = content[function_start:function_end]
        post_index = function.index(".post(")

        assert function.count(".post(") == 1
        assert function.index("assert_notification_content_readable(row)") < post_index
        assert function.index('_assert_read_http("GET", url)') < post_index
        assert function.index('assert_read_http_for(READ_GUARD_POLICY, "POST", url)') < post_index


_OBSERVATION_STORE_SOURCE = """\
from ....persistence.storage.envelope.secure_bound_repository import SecureBoundRepository
from ....persistence.storage.sql.secure_objects import SecureObjectRepository


class ObservationRepository(SecureBoundRepository[object]):
    pass


class Store:
    def __init__(self, objects: SecureObjectRepository) -> None:
        self._objects = objects

    @property
    def _repository(self) -> SecureObjectRepository:
        return self._objects

    @property
    def _observations(self) -> ObservationRepository:
        return ObservationRepository(objects=self._repository)

    def persist(self, record: object) -> None:
        self._repository.save(record)
        self._observations.save(record)
"""

_PORT_ADAPTER_SOURCE = """\
from ....persistence.profile.justificante import JustificanteRepository
from .client import SedeClient


class JustificanteRepositoryAdapter:
    def __init__(self, *, repository: JustificanteRepository) -> None:
        self._repository = repository

    def save(self, justificante: object, /) -> None:
        _call_adapter("save_justificante", lambda: self._repository.save(justificante))
"""

_SUBMISSION_TEST_SOURCE = """\
from ......application.operations.supervisor import OperationSupervisor


async def test_flow(request, page, form):
    supervisor = OperationSupervisor(store=None)
    operation_id = await supervisor.submit(request, operation_id="3" * 64)
    await page.submit(form)
"""


def _line_of(source_text: str, fragment: str) -> int:
    """The single 1-based line of ``source_text`` containing ``fragment``."""
    matches = [line_no for line_no, line in enumerate(source_text.splitlines(), start=1) if fragment in line]
    assert len(matches) == 1, f"fragment {fragment!r} must occur exactly once, found {matches}"
    return matches[0]


def _port_adapter_save_lines(source_text: str) -> tuple[int, int]:
    """The adapter's ``save`` definition line and its forwarding call line."""
    return (
        _line_of(source_text, "def save(self, justificante"),
        _line_of(source_text, "lambda: self._repository.save(justificante)"),
    )


def _supervisor_submit_lines(source_text: str) -> tuple[int, int]:
    """The supervisor enqueue line and the page submit line."""
    return (
        _line_of(source_text, "await supervisor.submit("),
        _line_of(source_text, "await page.submit(form)"),
    )


class TestTheGuardCanActuallyFire:
    """Prove this guard is armed, not merely green.

    A scan that matches nothing passes identically whether the tree is clean or
    the matcher is broken, and this guard was briefly disarmed in exactly that
    way: a rewrite added ``save(...)`` call sites, main went red, and the fix
    was to WIDEN the exemption. Widening is the direction that silently turns a
    guard into decoration, so every exemption has to prove it still refuses.

    These cases run :func:`_offending_lines` -- the same function the real scan
    uses -- on synthetic sources, so they never depend on the tree containing a
    violation.
    """

    @pytest.mark.parametrize("verb", _load_forbidden_verbs())
    def test_a_remote_call_of_every_forbidden_verb_is_caught(self, verb: str) -> None:
        """Every verb in the fixture must be detected in a call context."""
        source = f"class Fetch:\n    def run(self, url, payload):\n        self._client.{verb}(url, data=payload)\n"
        assert _offending_lines("_declarations_fetch.py", source, verb) == (3,), (
            f"the guard did not detect a call to forbidden verb {verb!r}"
        )

    def test_the_storage_property_exemption_applies_in_the_observation_store(self) -> None:
        """Saves through storage-typed properties stay allowed in observation_store.py."""
        assert _offending_lines(_OBSERVATION_STORE_MODULE, _OBSERVATION_STORE_SOURCE, "save") == (), (
            "self._repository.save(...) and self._observations.save(...) must remain allowed in observation_store.py"
        )

    def test_the_storage_property_exemption_does_not_leak_to_other_paths(self) -> None:
        """The identical module at any other path, including a nested namesake, is refused."""
        expected = (
            _line_of(_OBSERVATION_STORE_SOURCE, "self._repository.save(record)"),
            _line_of(_OBSERVATION_STORE_SOURCE, "self._observations.save(record)"),
        )
        assert _offending_lines("_declarations_fetch.py", _OBSERVATION_STORE_SOURCE, "save") == expected
        assert _offending_lines("tests/observation_store.py", _OBSERVATION_STORE_SOURCE, "save") == expected

    def test_the_storage_property_exemption_does_not_excuse_a_different_verb(self) -> None:
        """Only ``save`` is exempted on those accessors, not every mutation verb."""
        source = _OBSERVATION_STORE_SOURCE.replace(
            "self._observations.save(record)", "self._observations.submit(record)"
        )
        assert _offending_lines(_OBSERVATION_STORE_MODULE, source, "submit") == (
            _line_of(source, "self._observations.submit(record)"),
        )

    def test_a_property_returning_a_non_storage_type_is_refused(self) -> None:
        """A property typed as a Sede client buys no exemption in observation_store.py."""
        source = _OBSERVATION_STORE_SOURCE.replace(
            "    def _observations(self) -> ObservationRepository:", "    def _observations(self) -> SedeClient:"
        ).replace(
            "from ....persistence.storage.sql", "from .client import SedeClient\nfrom ....persistence.storage.sql"
        )
        assert _offending_lines(_OBSERVATION_STORE_MODULE, source, "save") == (
            _line_of(source, "self._observations.save(record)"),
        )

    def test_a_storage_property_written_through_setattr_is_refused(self) -> None:
        """A ``setattr`` naming the property withdraws that accessor's exemption."""
        source = _OBSERVATION_STORE_SOURCE + (
            '\n    def swap(self, client: object) -> None:\n        setattr(self, "_observations", client)\n'
        )
        assert _offending_lines(_OBSERVATION_STORE_MODULE, source, "save") == (
            _line_of(source, "self._observations.save(record)"),
        )

    def test_a_shadowed_storage_type_is_refused(self) -> None:
        """A local class reusing a storage type name makes that type untrusted."""
        source = _OBSERVATION_STORE_SOURCE + "\n\nclass SecureObjectRepository:\n    pass\n"
        assert _offending_lines(_OBSERVATION_STORE_MODULE, source, "save") == (
            _line_of(source, "self._repository.save(record)"),
        )

    def test_a_storage_property_save_inside_a_nested_class_is_refused(self) -> None:
        """Accessors are scoped per class: a nested class's ``self`` is not the store."""
        source = _OBSERVATION_STORE_SOURCE + (
            "\n    class Inner:\n        def run(self, item: object) -> None:\n            self._observations.save(item)\n"
        )
        assert _offending_lines(_OBSERVATION_STORE_MODULE, source, "save") == (
            _line_of(source, "self._observations.save(item)"),
        )

    def test_the_port_adapter_exemption_applies_to_a_profile_bound_repository(self) -> None:
        """Forwarding to a profile repository bound in ``__init__`` is allowed in its own module."""
        assert _offending_lines(_PORT_ADAPTER_MODULE, _PORT_ADAPTER_SOURCE, "save") == ()

    def test_the_port_adapter_exemption_does_not_leak_to_other_paths(self) -> None:
        """The identical adapter anywhere else is refused, definition and call alike."""
        assert _offending_lines("_declarations_fetch.py", _PORT_ADAPTER_SOURCE, "save") == _port_adapter_save_lines(
            _PORT_ADAPTER_SOURCE
        )

    def test_a_sede_client_bound_to_repository_is_refused(self) -> None:
        """A ``_repository`` bound from a non-profile parameter is an unsanctioned write for the whole module."""
        source = _PORT_ADAPTER_SOURCE + (
            "\n\nclass RemoteAdapter:\n"
            "    def __init__(self, *, repository: SedeClient) -> None:\n"
            "        self._repository = repository\n"
            "\n"
            "    def save(self, form: object) -> None:\n"
            "        self._repository.save(form)\n"
        )
        assert _offending_lines(_PORT_ADAPTER_MODULE, source, "save") == (
            *_port_adapter_save_lines(source),
            _line_of(source, "def save(self, form"),
            _line_of(source, "self._repository.save(form)"),
        )

    @pytest.mark.parametrize(
        ("case", "old", "new"),
        [
            (
                "method-rebinding",
                "        self._repository = repository\n",
                "        self._repository = repository\n\n    def use_remote(self, client: SedeClient) -> None:\n"
                "        self._repository = client\n",
            ),
            (
                "parameter-reassigned-before-bind",
                "        self._repository = repository\n",
                "        repository = SedeClient()\n        self._repository = repository\n",
            ),
            (
                "setattr",
                "        self._repository = repository\n",
                "        self._repository = repository\n        setattr(self, '_repository', SedeClient())\n",
            ),
            (
                "computed-setattr",
                "        self._repository = repository\n",
                "        self._repository = repository\n        setattr(self, name, SedeClient())\n",
            ),
            (
                "instance-dict",
                "        self._repository = repository\n",
                "        self._repository = repository\n        self.__dict__['_repository'] = SedeClient()\n",
            ),
            (
                "tuple-target",
                "        self._repository = repository\n",
                "        self._repository = repository\n        self._repository, self._other = SedeClient(), None\n",
            ),
            (
                "self-rebinding",
                '        _call_adapter("save_justificante"',
                '        self = SedeClient()\n        _call_adapter("save_justificante"',
            ),
            (
                "duplicate-profile-import",
                "from .client import SedeClient\n",
                "from .client import SedeClient\nfrom ....persistence.profile.justificante import JustificanteRepository\n",
            ),
            (
                "non-profile-import",
                "from ....persistence.profile.justificante import JustificanteRepository\n",
                "from .client import JustificanteRepository\n",
            ),
        ],
    )
    def test_an_unsanctioned_repository_binding_withdraws_the_exemption(self, case: str, old: str, new: str) -> None:
        """Every way to put something other than the given profile repository behind ``_repository`` is refused."""
        source = _PORT_ADAPTER_SOURCE.replace(old, new, 1)
        assert source != _PORT_ADAPTER_SOURCE, f"{case}: the synthetic mutation did not apply"
        assert _offending_lines(_PORT_ADAPTER_MODULE, source, "save") == _port_adapter_save_lines(source), case

    def test_an_assignment_from_outside_the_class_withdraws_the_exemption(self) -> None:
        """A module function writing ``_repository`` on an adapter instance is refused."""
        source = _PORT_ADAPTER_SOURCE + (
            "\n\ndef rebind(adapter: JustificanteRepositoryAdapter, client: SedeClient) -> None:\n"
            "    adapter._repository = client\n"
        )
        assert _offending_lines(_PORT_ADAPTER_MODULE, source, "save") == _port_adapter_save_lines(source)

    def test_a_profile_type_shadowed_by_a_local_class_is_refused(self) -> None:
        """A local class reusing the profile type name makes the annotation untrusted."""
        source = _PORT_ADAPTER_SOURCE + "\n\nclass JustificanteRepository:\n    pass\n"
        assert _offending_lines(_PORT_ADAPTER_MODULE, source, "save") == _port_adapter_save_lines(source)

    def test_a_repository_save_inside_a_nested_class_is_refused(self) -> None:
        """A nested class's ``self._repository`` is not the adapter's bound profile repository."""
        source = _PORT_ADAPTER_SOURCE + (
            "\n    class Inner:\n        def run(self, form: object) -> None:\n            self._repository.save(form)\n"
        )
        assert _offending_lines(_PORT_ADAPTER_MODULE, source, "save") == (
            _line_of(source, "self._repository.save(form)"),
        )

    def test_the_port_adapter_exemption_does_not_excuse_a_different_verb(self) -> None:
        """A profile-bound receiver is still refused for any verb other than ``save``."""
        source = _PORT_ADAPTER_SOURCE.replace(
            "self._repository.save(justificante)", "self._repository.submit(justificante)"
        )
        assert _offending_lines(_PORT_ADAPTER_MODULE, source, "submit") == (
            _line_of(source, "self._repository.submit(justificante)"),
        )

    def test_the_operation_submission_exemption_applies_only_to_its_test_path_and_supervisor(self) -> None:
        """Only the supervisor enqueue in the filed-history operation test is excused."""
        supervisor_line, page_line = _supervisor_submit_lines(_SUBMISSION_TEST_SOURCE)
        assert _offending_lines(_OPERATION_SUBMISSION_TEST, _SUBMISSION_TEST_SOURCE, "submit") == (page_line,)
        assert _offending_lines("test_filed_history_operation.py", _SUBMISSION_TEST_SOURCE, "submit") == (
            supervisor_line,
            page_line,
        )
        assert _offending_lines("_declarations_fetch.py", _SUBMISSION_TEST_SOURCE, "submit") == (
            supervisor_line,
            page_line,
        )

    @pytest.mark.parametrize(
        ("case", "old", "new"),
        [
            (
                "assignment",
                "    operation_id = await supervisor.submit(",
                "    supervisor = page\n    operation_id = await supervisor.submit(",
            ),
            (
                "walrus",
                "    operation_id = await supervisor.submit(",
                "    if (supervisor := page):\n        pass\n    operation_id = await supervisor.submit(",
            ),
            (
                "for-loop",
                "    operation_id = await supervisor.submit(",
                "    for supervisor in (page,):\n        pass\n    operation_id = await supervisor.submit(",
            ),
            (
                "with-target",
                "    operation_id = await supervisor.submit(",
                "    with page as supervisor:\n        pass\n    operation_id = await supervisor.submit(",
            ),
            (
                "parameter",
                "async def test_flow(request, page, form):",
                "async def test_flow(request, page, form, supervisor=None):",
            ),
            (
                "duplicate-import",
                "from ......application.operations.supervisor import OperationSupervisor\n",
                "from ......application.operations.supervisor import OperationSupervisor\n"
                "from .fakes import OperationSupervisor\n",
            ),
        ],
    )
    def test_a_supervisor_name_bound_any_other_way_is_refused(self, case: str, old: str, new: str) -> None:
        """A ``supervisor`` name bound other than as ``OperationSupervisor(...)`` buys no exemption."""
        source = _SUBMISSION_TEST_SOURCE.replace(old, new, 1)
        assert source != _SUBMISSION_TEST_SOURCE, f"{case}: the synthetic mutation did not apply"
        assert _offending_lines(_OPERATION_SUBMISSION_TEST, source, "submit") == _supervisor_submit_lines(source), case
