"""Universal fail-closed gates for the sole CommandSpec authority."""

from __future__ import annotations

import ast
import dataclasses
import importlib.util
from collections import Counter
from pathlib import Path

import pytest

from ....core.i18n import SUPPORTED_OUTPUT_LANGUAGES, lookup_translation_entry
from .._command_spec import (
    CommandSpec,
    CommandSpecGraph,
    DeferredTarget,
    ExecutionPolicySpec,
    OptionSpec,
    ResultSchemaSpec,
    SchemaState,
    TranslationKey,
)
from .._command_specs import COMMAND_GRAPH, COMMAND_SPECS

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _assert_exact_projection(
    authored: tuple[CommandSpec, ...], projected: tuple[CommandSpec, ...]
) -> None:
    authored_counts = Counter(spec.key for spec in authored)
    projected_counts = Counter(spec.key for spec in projected)
    duplicates = sorted(key for key, count in authored_counts.items() if count != 1)
    missing = sorted(authored_counts.keys() - projected_counts.keys())
    undeclared = sorted(projected_counts.keys() - authored_counts.keys())
    assert not duplicates, f"duplicate authored command specs: {duplicates}"
    assert not missing, f"missing projected command specs: {missing}"
    assert not undeclared, f"undeclared projected command specs: {undeclared}"
    assert authored_counts == projected_counts


def _translation_keys(spec: CommandSpec) -> tuple[TranslationKey, ...]:
    keys = [spec.help_key]
    if spec.short_help_key is not None:
        keys.append(spec.short_help_key)
    if spec.invocation.deprecated_key is not None:
        keys.append(spec.invocation.deprecated_key)
    if spec.handler is not None and spec.handler.reason_key is not None:
        keys.append(spec.handler.reason_key)
    if spec.result_schema.reason_key is not None:
        keys.append(spec.result_schema.reason_key)
    for parameter in spec.parameters:
        if parameter.help_key is not None:
            keys.append(parameter.help_key)
        if isinstance(parameter, OptionSpec) and parameter.prompt_key is not None:
            keys.append(parameter.prompt_key)
    return tuple(keys)


def _assert_no_forbidden_authority(source: str) -> None:
    tree = ast.parse(source)
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
            assert name not in forbidden_calls
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            assert not node.value.endswith(("app_lazy_manifest.v1.json", "command_registration_metadata.v1.json"))


def test_graph_projection_is_an_exact_dynamic_set() -> None:
    projected = tuple(node.spec for node in COMMAND_GRAPH.nodes())
    _assert_exact_projection(COMMAND_SPECS, projected)
    assert {id(spec) for spec in COMMAND_SPECS} == {id(spec) for spec in projected}


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
        if spec.parent_key is None:
            assert spec.kind == "root"
        else:
            assert spec.parent_key in by_key
            assert by_key[spec.parent_key].kind != "leaf"
            assert node.path[:-1] == next(item.path for item in COMMAND_GRAPH.nodes() if item.spec is by_key[spec.parent_key])
        assert node.path[-1] == spec.token

        if spec.handler is not None and spec.handler.target is not None:
            assert not spec.handler.target.qualname.startswith("_")
            assert importlib.util.find_spec(spec.handler.target.module) is not None
        if spec.result_schema.state is SchemaState.TARGET:
            assert spec.result_schema.target is not None
            assert spec.result_schema.identity is not None
            assert not spec.result_schema.target.qualname.startswith("_")
            assert importlib.util.find_spec(spec.result_schema.target.module) is not None
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
        token="planted-schema-duplicate",
    )
    with pytest.raises(ValueError, match="schema identities must be unique"):
        CommandSpecGraph((*COMMAND_SPECS, duplicate_schema)).by_schema_identity()
    with pytest.raises(ValueError, match="translation key"):
        TranslationKey("malformed")
    with pytest.raises(ValueError, match="dotted Python module"):
        DeferredTarget("not a module", "handler")
    with pytest.raises(ValueError, match="unknown performance class"):
        ExecutionPolicySpec(frozenset({"state-free"}), frozenset({"none"}), "slow", "none")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="unknown write route"):
        ExecutionPolicySpec(frozenset({"state-free"}), frozenset({"none"}), "metadata", "elsewhere")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="requires an identity and target"):
        ResultSchemaSpec(SchemaState.TARGET)


def test_former_authority_edges_are_absent_and_detector_bites() -> None:
    cli_root = Path(__file__).parents[1]
    for path in cli_root.rglob("*.py"):
        if "tests" not in path.parts:
            _assert_no_forbidden_authority(path.read_text(encoding="utf-8"))

    planted = """
from cadrumo.entrypoints.cli._app_lazy_registration import register
register_schema('invented')
RESOURCE = 'command_registration_metadata.v1.json'
"""
    with pytest.raises(AssertionError):
        _assert_no_forbidden_authority(planted)
