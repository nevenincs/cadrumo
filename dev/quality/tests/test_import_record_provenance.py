"""Dynamic imports follow their record sources and resolver composition."""

from __future__ import annotations

import configparser
from pathlib import Path

import pytest

from dev.quality.import_binding_inventory import read_modules
from dev.quality.import_check_models import Authority, ForbiddenContract, RootPackage
from dev.quality.import_dynamic_checks import check_dynamic_imports
from dev.quality.import_occurrences import collect_import_occurrences
from dev.quality.import_record_provenance import RecordTargetProvenance

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_RECORDS = """from dataclasses import dataclass
@dataclass
class Target:
    module: str
    qualname: str = "value"
    package: str | None = None
@dataclass
class Graph:
    declared: tuple[Target, ...]
    families: tuple[Target, ...] = ()
    resolver: object = None
"""


def _check(tmp_path: Path, sources: dict[str, str]) -> tuple[list[str], set[tuple[str, str]]]:
    root = tmp_path / "sample"
    root.mkdir()
    (root / "__init__.py").write_text("")
    for name, source in {"records": _RECORDS, "allowed": "value = 1", "forbidden": "value = 2", **sources}.items():
        (root / f"{name}.py").write_text(source)
    authority = Authority(
        tmp_path,
        tmp_path / "authority.ini",
        configparser.ConfigParser(),
        ("sample",),
        (RootPackage("sample", root),),
        (),
        (ForbiddenContract("boundary", "boundary", ("sample.loader",), ("sample.forbidden",)),),
    )
    modules, findings = read_modules(authority)
    provenance = RecordTargetProvenance(modules)
    check_dynamic_imports(authority, modules, findings, provenance)
    occurrences = collect_import_occurrences(authority, modules, provenance)
    return [finding.category for finding in findings], {
        (item.source_module, item.target_module) for item in occurrences
    }


def test_receiver_excludes_unrelated_record_sources(tmp_path: Path) -> None:
    categories, edges = _check(
        tmp_path,
        {
            "loader": """from importlib import import_module
from sample.records import Target
unrelated = Target("sample.forbidden")
selected = Target("sample.allowed")
import_module(selected.module)
"""
        },
    )
    assert categories == []
    assert edges == set()


def test_mixed_receiver_keeps_forbidden_edge(tmp_path: Path) -> None:
    categories, edges = _check(
        tmp_path,
        {
            "loader": """from importlib import import_module
from sample.records import Target
records = (Target("sample.allowed"), Target("sample.forbidden"))
for record in records:
    import_module(record.module)
"""
        },
    )
    assert categories == []
    assert edges == {("sample.loader", "sample.forbidden")}


@pytest.mark.parametrize("expression", ("Target(unknown)", 'unknown_factory("sample.allowed")'))
def test_unknown_constructor_cannot_borrow_known_neighbor(tmp_path: Path, expression: str) -> None:
    categories, _ = _check(
        tmp_path,
        {
            "loader": f"""from importlib import import_module
from sample.records import Target
known = Target("sample.allowed")
records = (known, {expression})
for record in records:
    import_module(record.module)
"""
        },
    )
    assert categories == ["UNRESOLVED_DYNAMIC_TARGET"]


def test_unknown_parameter_cannot_borrow_other_record_class(tmp_path: Path) -> None:
    categories, _ = _check(
        tmp_path,
        {
            "loader": """from importlib import import_module
from sample.records import Target
known = Target("sample.allowed")
def load(unrelated):
    return import_module(unrelated.module)
"""
        },
    )
    assert categories == ["UNRESOLVED_DYNAMIC_TARGET"]


def test_callback_uses_only_its_actual_graph_sources(tmp_path: Path) -> None:
    categories, edges = _check(
        tmp_path,
        {
            "loader": """from importlib import import_module
def resolve(target):
    return import_module(target.module)
""",
            "composition": """from sample.loader import resolve
from sample.records import Graph, Target
unrelated = Target("sample.forbidden")
graph = Graph((Target("sample.allowed"),), resolver=resolve)
""",
        },
    )
    assert categories == []
    assert edges == set()


@pytest.mark.parametrize("value, expected", [('"sample.forbidden"', set()), ("unknown", {"UNRESOLVED_DYNAMIC_TARGET"})])
def test_callback_mixed_and_unknown_sources_fail_safely(tmp_path: Path, value: str, expected: set[str]) -> None:
    categories, edges = _check(
        tmp_path,
        {
            "loader": """from importlib import import_module
def resolve(target):
    return import_module(target.module)
""",
            "composition": f"""from sample.loader import resolve
from sample.records import Graph, Target
graph = Graph((Target("sample.allowed"), Target({value})), resolver=resolve)
""",
        },
    )
    assert set(categories) == expected
    assert edges == ({("sample.loader", "sample.forbidden")} if not expected else set())


def test_callback_direct_unknown_call_is_not_hidden_by_graph(tmp_path: Path) -> None:
    categories, _ = _check(
        tmp_path,
        {
            "loader": """from importlib import import_module
def resolve(target):
    return import_module(target.module)
""",
            "composition": """from sample.loader import resolve
from sample.records import Graph, Target
graph = Graph((Target('sample.allowed'),), resolver=resolve)
resolve(unknown)
""",
        },
    )
    assert categories == ["UNRESOLVED_DYNAMIC_TARGET"]


@pytest.mark.parametrize("rebind", ["records = unknown", "if condition:\n    records = (Target('sample.forbidden'),)"])
def test_imported_declaration_rebindings_remain_visible(tmp_path: Path, rebind: str) -> None:
    categories, edges = _check(
        tmp_path,
        {
            "declarations": f"""from sample.records import Target
records = (Target('sample.allowed'),)
{rebind}
""",
            "loader": """from importlib import import_module
from sample.declarations import records
for record in records:
    import_module(record.module)
""",
        },
    )
    if "unknown" in rebind:
        assert categories == ["UNRESOLVED_DYNAMIC_TARGET"]
    else:
        assert categories == []
        assert edges == {("sample.loader", "sample.forbidden")}


def test_custom_constructor_is_not_inferred_from_annotation(tmp_path: Path) -> None:
    categories, _ = _check(
        tmp_path,
        {
            "loader": """from importlib import import_module
class Target:
    module: str
    def __init__(self, value):
        self.module = 'sample.forbidden'
record = Target('sample.allowed')
import_module(record.module)
"""
        },
    )
    assert categories == ["UNRESOLVED_DYNAMIC_TARGET"]


def test_parameter_shadow_does_not_borrow_imported_declaration(tmp_path: Path) -> None:
    categories, _ = _check(
        tmp_path,
        {
            "declarations": "from sample.records import Target\nrecord = Target('sample.allowed')\n",
            "loader": """from importlib import import_module
from sample.declarations import record
def load(record):
    return import_module(record.module)
""",
        },
    )
    assert categories == ["UNRESOLVED_DYNAMIC_TARGET"]


@pytest.mark.parametrize("rebind", ["'sample.forbidden'", "unknown"])
def test_factory_parameter_rebinding_fails_closed(tmp_path: Path, rebind: str) -> None:
    categories, _ = _check(
        tmp_path,
        {
            "loader": f"""from importlib import import_module
from sample.records import Target
def factory(module):
    module = {rebind}
    return Target(module)
record = factory('sample.allowed')
import_module(record.module)
"""
        },
    )
    assert categories == ["UNRESOLVED_DYNAMIC_TARGET"]


def test_post_init_module_rewrite_is_not_accepted_as_constructor_value(tmp_path: Path) -> None:
    categories, _ = _check(
        tmp_path,
        {
            "loader": """from dataclasses import dataclass
from importlib import import_module
@dataclass(frozen=True)
class Target:
    module: str
    def __post_init__(self):
        object.__setattr__(self, 'module', 'sample.forbidden')
record = Target('sample.allowed')
import_module(record.module)
"""
        },
    )
    assert categories == ["UNRESOLVED_DYNAMIC_TARGET"]


def test_bound_graph_resolver_unknown_argument_is_not_hidden(tmp_path: Path) -> None:
    categories, _ = _check(
        tmp_path,
        {
            "loader": """from importlib import import_module
def resolve(target):
    return import_module(target.module)
""",
            "composition": """from sample.loader import resolve
from sample.records import Graph, Target
graph = Graph((Target('sample.allowed'),), resolver=resolve)
graph.resolver(unknown)
""",
        },
    )
    assert categories == ["UNRESOLVED_DYNAMIC_TARGET"]


@pytest.mark.parametrize("injected", [False, True])
def test_read_only_record_walker_keeps_source_and_refuses_injection(tmp_path: Path, injected: bool) -> None:
    extra = "    yield Target(unknown)\n" if injected else ""
    categories, _ = _check(
        tmp_path,
        {
            "loader": """import dataclasses
from importlib import import_module
from sample.records import Target
@dataclasses.dataclass
class Envelope:
    target: Target

def walk(value):
    if isinstance(value, Target):
        yield value
        return
    if dataclasses.is_dataclass(value):
        for field in dataclasses.fields(value):
            yield from walk(getattr(value, field.name))
"""
            + extra
            + """
records = (Envelope(Target('sample.allowed')),)
for record in records:
    for target in walk(record):
        import_module(target.module)
"""
        },
    )
    assert categories == (["UNRESOLVED_DYNAMIC_TARGET"] if injected else [])


def test_standard_relative_module_normalization_keeps_forbidden_edge(tmp_path: Path) -> None:
    records = """from dataclasses import dataclass
from importlib.util import resolve_name
@dataclass(frozen=True)
class Target:
    module: str
    package: str | None = None
    def __post_init__(self):
        if self.module.startswith('.'):
            if self.package is None:
                raise ValueError('missing package')
            object.__setattr__(self, 'module', resolve_name(self.module, self.package))
        object.__setattr__(self, 'package', None)
"""
    categories, edges = _check(
        tmp_path,
        {
            "records": records,
            "loader": """from importlib import import_module
from sample.records import Target
record = Target('.forbidden', package='sample')
import_module(record.module)
""",
        },
    )
    assert categories == []
    assert edges == {("sample.loader", "sample.forbidden")}
