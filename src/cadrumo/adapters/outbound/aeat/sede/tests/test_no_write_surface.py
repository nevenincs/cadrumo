"""Write-surface checks for cadrumo.adapters.outbound.aeat.sede.

The sede adapter is a read-only boundary. These checks reject mutation
verbs in call contexts and reject non-read boundary record modes while
allowing browser events used to open selectors and read document links.
"""

from __future__ import annotations

import ast
import re
from collections import Counter
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


def _names_imported_from(tree: ast.Module, package: str, prefix: str) -> frozenset[str]:
    """Local names bound by imports from modules under ``prefix``."""
    names: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom):
            continue
        module = _absolute_import_module(node, package)
        if module == prefix or module.startswith(f"{prefix}."):
            names.update(alias.asname or alias.name for alias in node.names)
    return frozenset(names)


def _is_self_attribute(node: ast.expr, attribute: str) -> bool:
    return (
        isinstance(node, ast.Attribute)
        and node.attr == attribute
        and isinstance(node.value, ast.Name)
        and node.value.id == "self"
    )


def _self_attribute_assignments(cls: ast.ClassDef) -> list[tuple[str, ast.expr | None, ast.AST]]:
    """Every ``self.<name> = value`` in ``cls`` as (name, value, enclosing statement)."""
    assignments: list[tuple[str, ast.expr | None, ast.AST]] = []
    for node in ast.walk(cls):
        targets: list[ast.expr] = []
        value: ast.expr | None = None
        if isinstance(node, ast.Assign):
            targets.extend(node.targets)
            value = node.value
        elif isinstance(node, (ast.AnnAssign, ast.AugAssign)):
            targets.append(node.target)
            value = node.value
        for target in targets:
            if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name) and target.value.id == "self":
                assignments.append((target.attr, value, node))
    return assignments


def _annotation_name(annotation: ast.expr | None) -> str | None:
    return annotation.id if isinstance(annotation, ast.Name) else None


def _method(cls: ast.ClassDef, name: str) -> ast.FunctionDef | None:
    return next((item for item in cls.body if isinstance(item, ast.FunctionDef) and item.name == name), None)


def _save_call_lines(cls: ast.ClassDef, accessors: frozenset[str]) -> list[int]:
    """Lines of ``self.<accessor>.save(...)`` calls inside ``cls``."""
    lines: list[int] = []
    for node in ast.walk(cls):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "save"
            and any(_is_self_attribute(node.func.value, accessor) for accessor in accessors)
        ):
            lines.append(node.func.end_lineno or node.lineno)
    return lines


def _profile_repository_forwarding_lines(tree: ast.Module, package: str) -> list[int]:
    """Port adapters whose ``_repository`` is only ever the profile repository they were given.

    A class qualifies when its ``__init__`` binds ``self._repository`` exactly
    once, from a parameter annotated with a type imported from the profile
    persistence package, and nothing else in the class rebinds it. Its
    ``self._repository.save(...)`` calls and its own ``save`` method definition
    are then local encrypted persistence, not a Sede write.
    """
    profile_types = _names_imported_from(tree, package, _PROFILE_PERSISTENCE_PACKAGE)
    lines: list[int] = []
    for cls in (node for node in tree.body if isinstance(node, ast.ClassDef)):
        init = _method(cls, "__init__")
        if init is None:
            continue
        profile_parameters = {
            argument.arg
            for argument in (*init.args.args, *init.args.kwonlyargs)
            if _annotation_name(argument.annotation) in profile_types
        }
        bindings = [(value, node) for name, value, node in _self_attribute_assignments(cls) if name == "_repository"]
        if len(bindings) != 1:
            continue
        value, statement = bindings[0]
        if statement not in init.body or not (isinstance(value, ast.Name) and value.id in profile_parameters):
            continue
        lines.extend(_save_call_lines(cls, frozenset({"_repository"})))
        save_method = _method(cls, "save")
        if save_method is not None:
            lines.append(save_method.lineno)
    return lines


def _storage_property_save_lines(tree: ast.Module, package: str) -> list[int]:
    """``self.<property>.save(...)`` where the property returns a secure-storage repository.

    A property qualifies when it is never assigned as an attribute and its
    return annotation names a type imported from the secure storage package, or
    a class in the same module derived from one.
    """
    storage_types = set(_names_imported_from(tree, package, _STORAGE_PERSISTENCE_PACKAGE))
    for cls in (node for node in tree.body if isinstance(node, ast.ClassDef)):
        base_names = {
            base.value.id
            if isinstance(base, ast.Subscript) and isinstance(base.value, ast.Name)
            else _annotation_name(base)
            for base in cls.bases
        }
        if base_names & storage_types:
            storage_types.add(cls.name)
    lines: list[int] = []
    for cls in (node for node in tree.body if isinstance(node, ast.ClassDef)):
        assigned = {name for name, _, _ in _self_attribute_assignments(cls)}
        accessors = frozenset(
            item.name
            for item in cls.body
            if isinstance(item, ast.FunctionDef)
            and any(isinstance(decorator, ast.Name) and decorator.id == "property" for decorator in item.decorator_list)
            and _annotation_name(item.returns) in storage_types
            and item.name not in assigned
        )
        if accessors:
            lines.extend(_save_call_lines(cls, accessors))
    return lines


def _operation_supervisor_submit_lines(tree: ast.Module, package: str) -> list[int]:
    """``<name>.submit(...)`` where ``<name>`` is only ever an ``OperationSupervisor`` in that function."""
    supervisor_types = _names_imported_from(tree, package, _OPERATION_SUPERVISOR_MODULE) & {"OperationSupervisor"}
    lines: list[int] = []
    for function in (node for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))):
        bound: dict[str, bool] = {}
        for node in ast.walk(function):
            if isinstance(node, ast.Assign):
                is_supervisor = (
                    isinstance(node.value, ast.Call)
                    and isinstance(node.value.func, ast.Name)
                    and node.value.func.id in supervisor_types
                )
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        bound[target.id] = bound.get(target.id, True) and is_supervisor
        supervisors = {name for name, only_supervisor in bound.items() if only_supervisor}
        for node in ast.walk(function):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "submit"
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id in supervisors
            ):
                lines.append(node.func.end_lineno or node.lineno)
    return lines


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

    def test_the_port_adapter_exemption_applies_to_a_profile_bound_repository(self) -> None:
        """Forwarding to a profile repository bound in ``__init__`` is allowed in its own module."""
        assert _offending_lines(_PORT_ADAPTER_MODULE, _PORT_ADAPTER_SOURCE, "save") == ()

    def test_the_port_adapter_exemption_does_not_leak_to_other_paths(self) -> None:
        """The identical adapter anywhere else is refused, definition and call alike."""
        expected = (
            _line_of(_PORT_ADAPTER_SOURCE, "def save(self, justificante"),
            _line_of(_PORT_ADAPTER_SOURCE, "lambda: self._repository.save(justificante)"),
        )
        assert _offending_lines("_declarations_fetch.py", _PORT_ADAPTER_SOURCE, "save") == expected

    def test_a_sede_client_bound_to_repository_is_refused(self) -> None:
        """A ``_repository`` bound from a non-profile parameter buys no exemption in the port-adapter module."""
        source = _PORT_ADAPTER_SOURCE + (
            "\n\nclass RemoteAdapter:\n"
            "    def __init__(self, *, repository: SedeClient) -> None:\n"
            "        self._repository = repository\n"
            "\n"
            "    def save(self, form: object) -> None:\n"
            "        self._repository.save(form)\n"
        )
        assert _offending_lines(_PORT_ADAPTER_MODULE, source, "save") == (
            _line_of(source, "def save(self, form"),
            _line_of(source, "self._repository.save(form)"),
        )

    def test_a_profile_repository_later_rebound_to_a_sede_client_is_refused(self) -> None:
        """Rebinding ``_repository`` anywhere in the class withdraws the exemption for the whole class."""
        source = _PORT_ADAPTER_SOURCE.replace(
            "        self._repository = repository\n",
            "        self._repository = repository\n\n    def use_remote(self, client: SedeClient) -> None:\n"
            "        self._repository = client\n",
        )
        assert _offending_lines(_PORT_ADAPTER_MODULE, source, "save") == (
            _line_of(source, "def save(self, justificante"),
            _line_of(source, "lambda: self._repository.save(justificante)"),
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
        supervisor_line = _line_of(_SUBMISSION_TEST_SOURCE, "await supervisor.submit(")
        page_line = _line_of(_SUBMISSION_TEST_SOURCE, "await page.submit(form)")
        assert _offending_lines(_OPERATION_SUBMISSION_TEST, _SUBMISSION_TEST_SOURCE, "submit") == (page_line,)
        assert _offending_lines("test_filed_history_operation.py", _SUBMISSION_TEST_SOURCE, "submit") == (
            supervisor_line,
            page_line,
        )
        assert _offending_lines("_declarations_fetch.py", _SUBMISSION_TEST_SOURCE, "submit") == (
            supervisor_line,
            page_line,
        )

    def test_a_supervisor_name_rebound_to_another_object_is_refused(self) -> None:
        """A ``supervisor`` name that is not only ever an ``OperationSupervisor`` buys no exemption."""
        source = _SUBMISSION_TEST_SOURCE.replace(
            "    operation_id = await supervisor.submit(",
            "    supervisor = page\n    operation_id = await supervisor.submit(",
        )
        assert _offending_lines(_OPERATION_SUBMISSION_TEST, source, "submit") == (
            _line_of(source, "await supervisor.submit("),
            _line_of(source, "await page.submit(form)"),
        )
