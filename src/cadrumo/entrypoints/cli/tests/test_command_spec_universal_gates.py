"""Universal fail-closed gates for the sole CommandSpec authority."""

from __future__ import annotations

import ast
import dataclasses
import importlib
import importlib.util
from collections import Counter
from pathlib import Path
from typing import Any, cast

import pytest

from ....core.i18n import SUPPORTED_OUTPUT_LANGUAGES, lookup_translation_entry
from ....core.json_contract import OutputRootSchema, OutputSchema
from .._command_spec import (
    CommandSpec,
    CommandSpecGraph,
    DeferredTarget,
    ExecutionPolicySpec,
    ParameterDefault,
    ResultSchemaSpec,
    SchemaState,
    TranslationKey,
)
from .._command_specs import COMMAND_GRAPH, COMMAND_SPECS

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _assert_exact_projection(authored: tuple[CommandSpec, ...], projected: tuple[CommandSpec, ...]) -> None:
    authored_counts = Counter(spec.key for spec in authored)
    projected_counts = Counter(spec.key for spec in projected)
    duplicates = sorted(key for key, count in authored_counts.items() if count != 1)
    missing = sorted(authored_counts.keys() - projected_counts.keys())
    undeclared = sorted(projected_counts.keys() - authored_counts.keys())
    assert not duplicates, f"duplicate authored command specs: {duplicates}"
    assert not missing, f"missing projected command specs: {missing}"
    assert not undeclared, f"undeclared projected command specs: {undeclared}"
    assert authored_counts == projected_counts


def _translation_keys(value: object) -> tuple[TranslationKey, ...]:
    if isinstance(value, TranslationKey):
        return (value,)
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return tuple(
            key for field in dataclasses.fields(value) for key in _translation_keys(getattr(value, field.name))
        )
    if isinstance(value, tuple):
        return tuple(key for item in value for key in _translation_keys(item))
    return ()


def _assert_no_forbidden_authority(
    source: str, *, runtime_projection: bool = False, spec_declaration: bool = False
) -> None:
    tree = ast.parse(source)
    aliases = {name: name for name in ("Typer", "Option", "Argument", "CommandSpec")}
    typer_modules = {"typer"}
    for item in ast.walk(tree):
        if isinstance(item, ast.Import):
            typer_modules.update(alias.asname or alias.name for alias in item.names if alias.name == "typer")
        if isinstance(item, ast.ImportFrom):
            for alias in item.names:
                if alias.name in aliases:
                    aliases[alias.asname or alias.name] = alias.name
    allowed_spec_calls: set[int] = set()
    allowed_factories: set[str] = set()
    if spec_declaration:
        for item in tree.body:
            if isinstance(item, ast.Assign):
                targets, value = item.targets, item.value
            elif isinstance(item, ast.AnnAssign) and item.value is not None:
                targets, value = [item.target], item.value
            else:
                continue
            if any(
                isinstance(target, ast.Name)
                and target.id.isupper()
                and target.id.endswith(("_COMMAND_SPEC", "_COMMAND_SPECS"))
                for target in targets
            ):
                allowed_factories.update(
                    child.func.id
                    for child in ast.walk(value)
                    if isinstance(child, ast.Call) and isinstance(child.func, ast.Name)
                )
                allowed_spec_calls.update(
                    id(child)
                    for child in ast.walk(value)
                    if isinstance(child, ast.Call)
                    and isinstance(child.func, ast.Name)
                    and aliases.get(child.func.id, child.func.id) == "CommandSpec"
                )
        for item in tree.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name in allowed_factories:
                allowed_spec_calls.update(
                    id(child)
                    for child in ast.walk(item)
                    if isinstance(child, ast.Call)
                    and isinstance(child.func, ast.Name)
                    and aliases.get(child.func.id, child.func.id) == "CommandSpec"
                )
    forbidden_modules = {
        "cadrumo.entrypoints.cli._app_lazy_registration",
        "cadrumo.entrypoints.cli._app_lazy_families",
        "cadrumo.entrypoints.cli.schema_surface",
        "cadrumo.entrypoints.cli._machine_secret_contract",
        "dev.quality.generate_app_lazy_manifest",
        "dev.quality.generate_command_registration_metadata",
    }
    forbidden_calls = {
        "add_typer",
        "declare_metadata_group",
        "register_schema",
        "command_execution_policy",
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert not forbidden_modules.intersection(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            assert node.module not in forbidden_modules
        elif isinstance(node, ast.Call):
            name = node.func.attr if isinstance(node.func, ast.Attribute) else getattr(node.func, "id", "")
            canonical_name = aliases.get(name, name)
            if (
                isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id in typer_modules
            ):
                canonical_name = node.func.attr
            assert name not in forbidden_calls
            if not runtime_projection:
                assert canonical_name not in {"Typer", "Option", "Argument", "add_command"}
                if isinstance(node.func, ast.Call) and isinstance(node.func.func, ast.Attribute):
                    assert node.func.func.attr not in {"command", "callback"}
            if canonical_name == "CommandSpec":
                assert id(node) in allowed_spec_calls
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            parameter_names = {argument.arg for argument in (*node.args.posonlyargs, *node.args.args)}
            assert not (
                (node.name == "register" and parameter_names.intersection({"app", "typer_app"}))
                or (node.name.startswith("register_") and "command" in node.name)
            )
            if not runtime_projection:
                for decorator in node.decorator_list:
                    name = (
                        decorator.func.attr
                        if isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Attribute)
                        else ""
                    )
                    assert name not in {"command", "callback"}
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            names = {target.id for target in targets if isinstance(target, ast.Name)}
            assert not any(
                ("COMMAND" in name or "CLI" in name) and name.endswith(("_PATHS", "_ALIASES", "_PATH_MAP"))
                for name in names
            )
            value = node.value
            route_names = {
                name
                for name in names
                if name == "ROUTES" or name.endswith(("_PATHS", "_ALIASES", "_PATH_MAP", "_ROUTES"))
            }
            if route_names:
                for mapping in (child for child in ast.walk(value) if isinstance(child, ast.Dict)):
                    for key, mapped in zip(mapping.keys, mapping.values, strict=True):
                        path_key = (
                            isinstance(key, ast.Constant)
                            and isinstance(key.value, str)
                            and any(
                                token in key.value.split() for token in ("aeat", "app", "config", "modelo", "ledger")
                            )
                        ) or (
                            isinstance(key, ast.Tuple)
                            and key.elts
                            and all(isinstance(item, ast.Constant) and isinstance(item.value, str) for item in key.elts)
                        )
                        assert not (path_key and isinstance(mapped, (ast.Name, ast.Attribute, ast.Lambda)))
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            assert not node.value.endswith(("app_lazy_manifest.v1.json", "command_registration_metadata.v1.json"))


def _resolve_public_target(target: DeferredTarget) -> object:
    assert importlib.util.find_spec(target.module) is not None, target.identity
    value: object = importlib.import_module(target.module)
    for part in target.qualname.split("."):
        assert not part.startswith("_"), target.identity
        assert hasattr(value, part), target.identity
        value = getattr(value, part)
    return value


def _assert_schema_target(target: DeferredTarget) -> None:
    schema_type = _resolve_public_target(target)
    assert isinstance(schema_type, type), target.identity
    assert issubclass(schema_type, OutputSchema | OutputRootSchema), target.identity


def _deferred_targets(value: object, path: tuple[str, ...] = ()) -> tuple[tuple[tuple[str, ...], DeferredTarget], ...]:
    if isinstance(value, DeferredTarget):
        return ((path, value),)
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return tuple(
            target
            for field in dataclasses.fields(value)
            for target in _deferred_targets(getattr(value, field.name), (*path, field.name))
        )
    if isinstance(value, tuple):
        return tuple(
            target for index, item in enumerate(value) for target in _deferred_targets(item, (*path, str(index)))
        )
    return ()


def _assert_all_deferred_targets(spec: CommandSpec) -> None:
    for path, target in _deferred_targets(spec):
        if path[-2:] == ("result_schema", "target"):
            _assert_schema_target(target)
            continue
        resolved = _resolve_public_target(target)
        role = path[-1]
        if role in {"target", "factory", "parser", "completion", "callback"}:
            assert callable(resolved), target.identity
        elif role in {"annotation", "model"}:
            assert isinstance(resolved, type), target.identity
        elif role == "click_type":
            assert callable(resolved) or hasattr(resolved, "convert"), target.identity


def _reachable_modules(sources: dict[str, str], root: str) -> set[str]:
    reached: set[str] = set()
    pending = [root]
    while pending:
        module = pending.pop()
        if module in reached:
            continue
        reached.add(module)
        package = module.rpartition(".")[0]
        for node in ast.walk(ast.parse(sources[module])):
            if not isinstance(node, ast.ImportFrom) or node.level == 0:
                continue
            relative = f"{'.' * node.level}{node.module or ''}"
            dependency = importlib.util.resolve_name(relative, package)
            if dependency in sources and dependency not in reached:
                pending.append(dependency)
    return reached


def _locally_authored_export_names(source: str) -> tuple[str, ...]:
    names: list[str] = []
    for node in ast.parse(source).body:
        if isinstance(node, ast.Assign):
            targets = node.targets
            value = node.value
        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]
            value = node.value
        else:
            continue
        if value is None or (
            isinstance(value, (ast.Tuple, ast.List)) and any(isinstance(child, ast.Starred) for child in value.elts)
        ):
            continue
        names.extend(
            target.id
            for target in targets
            if isinstance(target, ast.Name)
            and target.id.isupper()
            and target.id.endswith(("_COMMAND_SPEC", "_COMMAND_SPECS"))
        )
    return tuple(names)


def _assert_authored_objects_enrolled(authored: tuple[CommandSpec, ...], aggregate: tuple[CommandSpec, ...]) -> None:
    assert Counter(id(spec) for spec in authored) == Counter(id(spec) for spec in aggregate)


def test_graph_projection_is_an_exact_dynamic_set() -> None:
    projected = tuple(node.spec for node in COMMAND_GRAPH.nodes())
    _assert_exact_projection(COMMAND_SPECS, projected)
    assert {id(spec) for spec in COMMAND_SPECS} == {id(spec) for spec in projected}


def test_every_distributed_spec_module_is_enrolled_by_the_aggregate() -> None:
    cli_root = Path(__file__).parents[1]
    sources = {}
    for path in cli_root.rglob("*.py"):
        if "tests" in path.parts:
            continue
        source = path.read_text(encoding="utf-8")
        if path.name == "_command_specs.py" or _locally_authored_export_names(source):
            module_name = "cadrumo.entrypoints.cli." + ".".join(path.relative_to(cli_root).with_suffix("").parts)
            sources[module_name] = source
    root = "cadrumo.entrypoints.cli._command_specs"
    assert _reachable_modules(sources, root) == set(sources)

    authored: list[CommandSpec] = []
    for module_name, source in sources.items():
        module = importlib.import_module(module_name)
        for name in _locally_authored_export_names(source):
            value = getattr(module, name)
            if isinstance(value, CommandSpec):
                authored.append(value)
            else:
                authored.extend(value)
    _assert_authored_objects_enrolled(tuple(authored), COMMAND_SPECS)

    planted = {**sources, "cadrumo.entrypoints.cli._planted_command_specs": "PLANTED_COMMAND_SPECS = ()"}
    assert _reachable_modules(planted, root) != set(planted)
    with pytest.raises(AssertionError):
        _assert_authored_objects_enrolled((*COMMAND_SPECS, COMMAND_SPECS[0]), COMMAND_SPECS)


def test_exact_set_detector_bites_on_missing_duplicate_and_undeclared_nodes() -> None:
    first, second, *rest = COMMAND_SPECS
    with pytest.raises(AssertionError, match="missing projected"):
        _assert_exact_projection(COMMAND_SPECS, (first, *rest))
    with pytest.raises(AssertionError, match="duplicate authored"):
        _assert_exact_projection((*COMMAND_SPECS, first), COMMAND_SPECS)
    planted = dataclasses.replace(second, key="planted_undeclared")
    with pytest.raises(AssertionError, match="undeclared projected"):
        _assert_exact_projection(COMMAND_SPECS, (*COMMAND_SPECS, planted))


def test_every_parent_edge_target_schema_locale_and_policy_is_complete() -> None:
    by_key = COMMAND_GRAPH.by_key()
    schema_identities: list[str] = []
    for node in COMMAND_GRAPH.nodes():
        spec = node.spec
        _assert_all_deferred_targets(spec)
        if spec.parent_key is None:
            assert spec.kind == "root"
        else:
            assert spec.parent_key in by_key
            assert by_key[spec.parent_key].kind != "leaf"
            assert node.path[:-1] == next(
                item.path for item in COMMAND_GRAPH.nodes() if item.spec is by_key[spec.parent_key]
            )
        assert node.path[-1] == spec.token

        if spec.handler is not None and spec.handler.target is not None:
            assert not spec.handler.target.qualname.startswith("_")
            assert callable(_resolve_public_target(spec.handler.target))
        if spec.result_schema.state is SchemaState.TARGET:
            assert spec.result_schema.target is not None
            assert spec.result_schema.identity is not None
            assert not spec.result_schema.target.qualname.startswith("_")
            _assert_schema_target(spec.result_schema.target)
            schema_identities.append(spec.result_schema.identity)

        policy = spec.policy
        assert policy.capabilities
        assert policy.side_effects
        assert policy.performance in {"metadata", "local-io", "compute", "external-io", "interactive"}
        assert policy.write_route in {"none", "profile-bound", "bootstrap-root"}
        if policy.write_route != "none":
            assert "local-state" in policy.side_effects
            assert "profile-custody" in policy.expanded_capabilities
        for key in _translation_keys(spec):
            for locale in SUPPORTED_OUTPUT_LANGUAGES:
                present, _value = lookup_translation_entry(key.value, locale=locale)
                assert present, f"{spec.key}: {key.value!r} absent from {locale}"
    assert len(schema_identities) == len(set(schema_identities))


def test_parent_schema_policy_and_malformed_detectors_bite() -> None:
    root = next(spec for spec in COMMAND_SPECS if spec.kind == "root")
    group = next(spec for spec in COMMAND_SPECS if spec.kind == "group")
    leaf = next(spec for spec in COMMAND_SPECS if spec.kind == "leaf")
    with pytest.raises(ValueError, match="unknown parent"):
        CommandSpecGraph((root, dataclasses.replace(group, parent_key="orphan")))
    duplicate_schema = dataclasses.replace(
        leaf,
        key="planted_schema_duplicate",
        token="planted-schema-duplicate",  # noqa: S106 - planted CLI token
    )
    with pytest.raises(ValueError, match="schema identities must be unique"):
        CommandSpecGraph((*COMMAND_SPECS, duplicate_schema)).by_schema_identity()
    with pytest.raises(ValueError, match="translation key"):
        TranslationKey("malformed")
    with pytest.raises(ValueError, match="dotted Python module"):
        DeferredTarget("not a module", "handler")
    with pytest.raises(ValueError, match="unknown performance class"):
        ExecutionPolicySpec(frozenset({"state-free"}), frozenset({"none"}), cast(Any, "slow"), "none")
    with pytest.raises(ValueError, match="unknown write route"):
        ExecutionPolicySpec(frozenset({"state-free"}), frozenset({"none"}), "metadata", cast(Any, "elsewhere"))
    with pytest.raises(ValueError, match="lacks its owning capability"):
        ExecutionPolicySpec(frozenset({"local-storage"}), frozenset({"network"}), "external-io", "none")
    with pytest.raises(ValueError, match="requires an identity and target"):
        ResultSchemaSpec(SchemaState.TARGET)
    with pytest.raises(AssertionError, match="planted_missing_target"):
        _resolve_public_target(DeferredTarget("planted_missing_target", "handler"))
    with pytest.raises(AssertionError, match="builtins:definitely_missing"):
        _resolve_public_target(DeferredTarget("builtins", "definitely_missing"))
    with pytest.raises(AssertionError, match="builtins:_private"):
        _resolve_public_target(DeferredTarget("builtins", "_private"))
    with pytest.raises(AssertionError, match="builtins:str"):
        _assert_schema_target(DeferredTarget("builtins", "str"))
    with pytest.raises(AssertionError, match="pydantic:BaseModel"):
        _assert_schema_target(DeferredTarget("pydantic", "BaseModel"))
    planted_parameter = dataclasses.replace(
        leaf.parameters[0],
        value=dataclasses.replace(leaf.parameters[0].value, annotation=DeferredTarget("builtins", "missing")),
    )
    with pytest.raises(AssertionError, match="builtins:missing"):
        _assert_all_deferred_targets(dataclasses.replace(leaf, parameters=(planted_parameter,)))
    planted_default = dataclasses.replace(
        leaf.parameters[0], default=ParameterDefault.from_factory(DeferredTarget("builtins", "missing_factory"))
    )
    with pytest.raises(AssertionError, match="builtins:missing_factory"):
        _assert_all_deferred_targets(dataclasses.replace(leaf, parameters=(planted_default,)))
    secret_owner = next(spec for spec in COMMAND_SPECS if spec.machine_secret is not None)
    assert secret_owner.machine_secret is not None
    planted_variant = dataclasses.replace(
        secret_owner.machine_secret.variants[0], model=DeferredTarget("builtins", "missing_secret_model")
    )
    planted_secret = dataclasses.replace(secret_owner.machine_secret, variants=(planted_variant,))
    with pytest.raises(AssertionError, match="builtins:missing_secret_model"):
        _assert_all_deferred_targets(dataclasses.replace(secret_owner, machine_secret=planted_secret))
    present, _value = lookup_translation_entry("cli.planted.missing", locale="es")
    assert not present


def test_former_authority_edges_are_absent_and_detector_bites() -> None:
    cli_root = Path(__file__).parents[1]
    for path in cli_root.rglob("*.py"):
        if "tests" not in path.parts:
            source = path.read_text(encoding="utf-8")
            _assert_no_forbidden_authority(
                source,
                runtime_projection=path.name == "_command_runtime.py",
                spec_declaration=bool(_locally_authored_export_names(source)),
            )

    planted = """
from cadrumo.entrypoints.cli._app_lazy_registration import register
register_schema('invented')
RESOURCE = 'command_registration_metadata.v1.json'
"""
    with pytest.raises(AssertionError):
        _assert_no_forbidden_authority(planted)
    for former_authority in (
        "import typer\napp = typer.Typer()",
        "import typer as t\napp = t.Typer()",
        "@app.command()\ndef verb(): pass",
        "COMMAND_PATHS = (('app', 'x'),)",
        "def register_commands(app): pass",
        "def register(app): pass",
        "app.add_command(command)",
        "app.command()(handler)",
        "app.callback()(handler)",
        "ROUTES = {('app', 'x'): handler}",
        "ROUTES = [{'app x': handler}]",
        "ROGUE = CommandSpec(key='rogue')",
        "from x import CommandSpec as CS\nrogue = CS(key='rogue')",
    ):
        with pytest.raises(AssertionError):
            _assert_no_forbidden_authority(former_authority)
