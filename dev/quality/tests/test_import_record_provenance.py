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


@pytest.mark.parametrize(
    "mutation",
    [
        "",
        "        self.modules[key] = unknown\n",
        "        self.modules.update({'chosen': unknown})\n",
        "        mutate(self)\n",
        "        mutate(receiver=self)\n",
        "        mutate(self.modules)\n",
        "        self.mutate()\n",
        (
            "        for self in [Builder({'chosen': 'sample.forbidden'})]:\n"
            "            return Target(self.modules[key])\n"
        ),
    ],
)
def test_bound_record_factory_preserves_finite_mapping_and_refuses_mutation(tmp_path: Path, mutation: str) -> None:
    categories, edges = _check(
        tmp_path,
        {
            "builder": """from dataclasses import dataclass
from sample.records import Target
@dataclass
class Builder:
    modules: dict[str, str]
    def target(self, key):
"""
            + mutation
            + """        return Target(self.modules[key])
    def leaf(self, key):
        return self.target(key)
""",
            "loader": """from importlib import import_module
from sample.builder import Builder
select = Builder({'chosen': 'sample.forbidden'}).leaf
target = select('chosen')
import_module(target.module)
""",
        },
    )
    assert categories == (["UNRESOLVED_DYNAMIC_TARGET"] if mutation else [])
    if not mutation:
        assert ("sample.loader", "sample.forbidden") in edges


@pytest.mark.parametrize("value", ["Target('sample.forbidden')", "unknown"])
def test_parameterized_record_sources_keep_forbidden_edges_and_refuse_open_values(tmp_path: Path, value: str) -> None:
    categories, edges = _check(
        tmp_path,
        {
            "loader": """import pytest
from importlib import import_module
from sample.records import Target
@pytest.mark.parametrize(('selected', 'unrelated'), (("""
            + value
            + """, 1),))
def test_declared(selected, unrelated):
    import_module(selected.module)
""",
        },
    )
    assert categories == (["UNRESOLVED_DYNAMIC_TARGET"] if value == "unknown" else [])
    if value != "unknown":
        assert ("sample.loader", "sample.forbidden") in edges


@pytest.mark.parametrize("call", ["mutate(receiver=self)", "mutate(self.modules)", "self.mutate()"])
def test_bound_factory_return_refuses_receiver_escapes_and_mutating_siblings(tmp_path: Path, call: str) -> None:
    categories, _edges = _check(
        tmp_path,
        {
            "builder": """from dataclasses import dataclass
from sample.records import Target
def mutate(receiver):
    receiver.modules['chosen'] = 'sample.forbidden'
    return None
@dataclass
class Builder:
    modules: dict[str, str]
    def mutate(self):
        self.modules['chosen'] = 'sample.forbidden'
        return None
    def target(self, key):
        return """
            + call
            + """ or Target(self.modules[key])
""",
            "loader": """from importlib import import_module
from sample.builder import Builder
select = Builder({'chosen': 'sample.allowed'}).target
target = select('chosen')
import_module(target.module)
""",
        },
    )
    assert categories == ["UNRESOLVED_DYNAMIC_TARGET"]


@pytest.mark.parametrize(
    "setup",
    [
        (
            "builder = Builder({'chosen': 'sample.allowed'})\nalias = builder\n"
            "alias.modules['chosen'] = 'sample.forbidden'\nselect = builder.target\n"
        ),
        (
            "select = Builder({'chosen': 'sample.allowed'}).target\n"
            "select.__self__.modules['chosen'] = 'sample.forbidden'\n"
        ),
        (
            "modules = {'chosen': 'sample.allowed'}\nalias = modules\n"
            "alias['chosen'] = 'sample.forbidden'\nselect = Builder(modules).target\n"
        ),
    ],
)
def test_bound_factory_requires_unescaped_receiver_and_mutable_inputs(tmp_path: Path, setup: str) -> None:
    categories, _edges = _check(
        tmp_path,
        {
            "builder": """from dataclasses import dataclass
from sample.records import Target
@dataclass
class Builder:
    modules: dict[str, str]
    def target(self, key):
        return Target(self.modules[key])
""",
            "loader": "from importlib import import_module\nfrom sample.builder import Builder\n"
            + setup
            + "target = select('chosen')\nimport_module(target.module)\n",
        },
    )
    assert categories == ["UNRESOLVED_DYNAMIC_TARGET"]


def test_bound_factory_refuses_post_init_mutation_of_constructor_input(tmp_path: Path) -> None:
    categories, _edges = _check(
        tmp_path,
        {
            "builder": """from dataclasses import dataclass
from sample.records import Target
def mutate(modules):
    modules['chosen'] = 'sample.forbidden'
@dataclass
class Builder:
    modules: dict[str, str]
    def __post_init__(self):
        mutate(self.modules)
    def target(self, key):
        return Target(self.modules[key])
""",
            "loader": """from importlib import import_module
from sample.builder import Builder
select = Builder({'chosen': 'sample.allowed'}).target
target = select('chosen')
import_module(target.module)
""",
        },
    )
    assert categories == ["UNRESOLVED_DYNAMIC_TARGET"]


def test_parameterized_and_direct_record_sources_are_both_retained(tmp_path: Path) -> None:
    categories, edges = _check(
        tmp_path,
        {
            "loader": """import pytest
from importlib import import_module
from sample.records import Target
@pytest.mark.parametrize('selected', [Target('sample.forbidden')])
def test_declared(selected):
    import_module(selected.module)
test_declared(Target('sample.allowed'))
""",
        },
    )
    assert categories == []
    assert ("sample.loader", "sample.forbidden") in edges


@pytest.mark.parametrize("indirect", ["True", "['selected']", "unknown"])
def test_indirect_parameterized_record_sources_refuse_fixture_substitution(tmp_path: Path, indirect: str) -> None:
    categories, _edges = _check(
        tmp_path,
        {
            "loader": """import pytest
from importlib import import_module
from sample.records import Target
@pytest.fixture
def selected(request):
    return Target('sample.forbidden')
@pytest.mark.parametrize('selected', [Target('sample.allowed')], indirect="""
            + indirect
            + """)
def test_declared(selected):
    import_module(selected.module)
test_declared(Target('sample.allowed'))
""",
        },
    )
    assert categories == ["UNRESOLVED_DYNAMIC_TARGET"]


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


@pytest.mark.parametrize(
    "declaration",
    [
        "@pytest.mark.parametrize('selected', cases)",
        "@pytest.mark.parametrize(names, [Target('sample.allowed')])",
        "@pytest.mark.parametrize(argnames='selected', argvalues=cases)",
        "@pytest.mark.parametrize('selected', [selected_case])",
    ],
)
def test_open_decorator_cannot_be_hidden_by_closed_direct_call(tmp_path: Path, declaration: str) -> None:
    categories, _ = _check(
        tmp_path,
        {
            "loader": """import pytest
from importlib import import_module
from sample.records import Target
cases = [Target('sample.forbidden')]
names = 'selected'
selected_case = Target('sample.allowed')
"""
            + declaration
            + """
def test_declared(selected):
    import_module(selected.module)
selected_case.module = 'sample.forbidden'
test_declared(Target('sample.allowed'))
"""
        },
    )
    assert categories == ["UNRESOLVED_DYNAMIC_TARGET"]


def test_keyword_parameterized_records_keep_forbidden_edge(tmp_path: Path) -> None:
    categories, edges = _check(
        tmp_path,
        {
            "loader": """import pytest
from importlib import import_module
from sample.records import Target
@pytest.mark.parametrize(argnames='selected', argvalues=[Target('sample.forbidden')])
def test_declared(selected):
    import_module(selected.module)
"""
        },
    )
    assert categories == []
    assert ("sample.loader", "sample.forbidden") in edges


@pytest.mark.parametrize("decorator", ["", "@replace_selected\n"])
def test_parameterized_function_keeps_external_calls_and_refuses_wrappers(tmp_path: Path, decorator: str) -> None:
    categories, edges = _check(
        tmp_path,
        {
            "loader": """import pytest
from importlib import import_module
from sample.records import Target
def replace_selected(function):
    def wrapped(selected):
        return function(Target('sample.forbidden'))
    return wrapped
"""
            + decorator
            + """@pytest.mark.parametrize('selected', [Target('sample.allowed')])
def test_declared(selected):
    import_module(selected.module)
""",
            "caller": """from sample.loader import test_declared
from sample.records import Target
test_declared(Target('sample.forbidden'))
""",
        },
    )
    assert categories == (["UNRESOLVED_DYNAMIC_TARGET"] if decorator else [])
    if not decorator:
        assert ("sample.loader", "sample.forbidden") in edges


def test_parameterized_records_refuse_mutating_factory(tmp_path: Path) -> None:
    categories, _ = _check(
        tmp_path,
        {
            "loader": """import pytest
from importlib import import_module
from sample.records import Target
def make_case():
    case = Target('sample.allowed')
    case.module = 'sample.forbidden'
    return case
@pytest.mark.parametrize('selected', [make_case()])
def test_declared(selected):
    import_module(selected.module)
"""
        },
    )
    assert categories == ["UNRESOLVED_DYNAMIC_TARGET"]


@pytest.mark.parametrize("argument", ["receiver=self", "receiver=Envelope(self)"])
def test_parameterized_records_refuse_post_init_keyword_receiver_escape(tmp_path: Path, argument: str) -> None:
    categories, _ = _check(
        tmp_path,
        {
            "builder": """from dataclasses import dataclass
def mutate(*, receiver):
    receiver.module = 'sample.forbidden'
@dataclass
class Envelope:
    receiver: object
@dataclass
class Selected:
    module: str
    def __post_init__(self):
        mutate("""
            + argument
            + """)
""",
            "loader": """import pytest
from importlib import import_module
from sample.builder import Selected
@pytest.mark.parametrize('selected', [Selected('sample.allowed')])
def test_declared(selected):
    import_module(selected.module)
""",
        },
    )
    assert categories == ["UNRESOLVED_DYNAMIC_TARGET"]


@pytest.mark.parametrize(
    "effect", ["        mutate(self.target)", "        for victim in [self.target]:\n            mutate(victim)"]
)
def test_parameterized_records_refuse_all_post_init_child_alias_effects(tmp_path: Path, effect: str) -> None:
    categories, _ = _check(
        tmp_path,
        {
            "builder": """from dataclasses import dataclass
from sample.records import Target
def mutate(target):
    target.module = 'sample.forbidden'
@dataclass
class Selected:
    target: Target
    def __post_init__(self):
"""
            + effect
            + "\n",
            "loader": """import pytest
from importlib import import_module
from sample.builder import Selected
from sample.records import Target
@pytest.mark.parametrize('selected', [Selected(Target('sample.allowed'))])
def test_declared(selected):
    import_module(selected.target.module)
""",
        },
    )
    assert categories == ["UNRESOLVED_DYNAMIC_TARGET"]


@pytest.mark.parametrize(
    "method, setup",
    [
        ("    @replace\n    def target(self, key):\n        return Target(self.modules[key])\n", ""),
        (
            "    def identity(self):\n        return self\n"
            "    def target(self, key):\n"
            "        return Target(qualname=mutate(self.identity()), module=self.modules[key])\n",
            "",
        ),
        (
            "    def target(self, key):\n"
            "        return Target(qualname=mutate(Envelope(self)), module=self.modules[key])\n",
            "",
        ),
        (
            "    def target(self, key):\n        return Target(self.modules[key])\n",
            "Builder.target = lambda self, key: Target('sample.forbidden')\n",
        ),
        (
            "    def target(self, key):\n        return Target(self.modules[key])\n",
            "alias = Builder\nalias.target = lambda self, key: Target('sample.forbidden')\n",
        ),
        ("    def target(self, key):\n        return Target(self.modules[key])\n", "mutate(Builder)\n"),
    ],
)
def test_bound_factory_refuses_decorators_computed_escapes_and_class_replacement(
    tmp_path: Path, method: str, setup: str
) -> None:
    categories, _ = _check(
        tmp_path,
        {
            "builder": """from dataclasses import dataclass
from sample.records import Target
def replace(method):
    return lambda self, key: Target('sample.forbidden')
def mutate(receiver):
    receiver.modules['chosen'] = 'sample.forbidden'
    return 'value'
@dataclass
class Envelope:
    receiver: object
@dataclass
class Builder:
    modules: dict[str, str]
"""
            + method,
            "loader": """from importlib import import_module
from sample.builder import Builder, mutate
from sample.records import Target
"""
            + setup
            + """target = Builder({'chosen': 'sample.allowed'}).target('chosen')
import_module(target.module)
""",
        },
    )
    assert categories == ["UNRESOLVED_DYNAMIC_TARGET"]


def test_bound_factory_refuses_nested_mutable_constructor_alias(tmp_path: Path) -> None:
    categories, _ = _check(
        tmp_path,
        {
            "builder": """from dataclasses import dataclass
from sample.records import Target
@dataclass
class Mapping:
    modules: dict[str, str]
@dataclass
class Builder:
    mapping: Mapping
    def target(self, key):
        return Target(self.mapping.modules[key])
""",
            "loader": """from importlib import import_module
from sample.builder import Builder, Mapping
modules = {'chosen': 'sample.allowed'}
mapping = Mapping(modules)
modules['chosen'] = 'sample.forbidden'
target = Builder(mapping).target('chosen')
import_module(target.module)
""",
        },
    )
    assert categories == ["UNRESOLVED_DYNAMIC_TARGET"]


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


@pytest.mark.parametrize("package", ["'sample'", "unknown"])
def test_relative_record_import_uses_only_its_explicit_closed_package(tmp_path: Path, package: str) -> None:
    categories, edges = _check(
        tmp_path,
        {
            "loader": """from importlib import import_module
from sample.records import Target
target = Target('.forbidden', package="""
            + package
            + """)
import_module(target.module, target.package)
"""
        },
    )
    assert categories == (["UNRESOLVED_DYNAMIC_TARGET"] if package == "unknown" else [])
    assert edges == (set() if package == "unknown" else {("sample.loader", "sample.forbidden")})


def test_mixed_known_and_unknown_record_package_cannot_borrow_its_neighbor(tmp_path: Path) -> None:
    categories, edges = _check(
        tmp_path,
        {
            "loader": """from importlib import import_module
from sample.records import Target
records = (Target('.forbidden', package='sample'), Target('.allowed', package=unknown))
for target in records:
    import_module(target.module, target.package)
"""
        },
    )
    assert categories == ["UNRESOLVED_DYNAMIC_TARGET", "UNRESOLVED_DYNAMIC_TARGET"]
    assert edges == set()
