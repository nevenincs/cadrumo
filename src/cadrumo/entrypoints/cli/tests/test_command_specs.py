from __future__ import annotations

import ast
import json
import subprocess
import sys
from dataclasses import replace
from importlib.util import find_spec, resolve_name
from pathlib import Path

import pytest

from .._app_ledger_command_specs import (
    _LEDGER_CLI_CENSUS_ANNOTATIONS,
    LEDGER_CLI_COMMAND_CENSUS,
    LEDGER_COMMAND_SPECS,
    LedgerCliAdapterOwnership,
    LedgerCliCensusAnnotation,
    _build_ledger_cli_command_census,
    _ledger_invocable_specs,
    _validated_annotations,
)
from ..command_spec import (
    CommandNodeKind,
    LazyBinding,
    ResultSchemaSpec,
    SchemaState,
    TuiCapability,
    translation_key,
)
from ..command_specs import COMMAND_GRAPH, COMMAND_SPECS

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_complete_command_authority_has_the_exact_shipped_shape() -> None:
    assert COMMAND_SPECS
    assert len(COMMAND_GRAPH.nodes()) == len(COMMAND_SPECS)
    assert sum(spec.kind == "root" for spec in COMMAND_SPECS) == 1
    assert all(spec.kind in {"root", "group", "leaf"} for spec in COMMAND_SPECS)
    assert len({node.path for node in COMMAND_GRAPH.nodes()}) == len(COMMAND_SPECS)


def test_every_executable_target_is_public_and_every_schema_identity_is_unique() -> None:
    executable = [spec for spec in COMMAND_SPECS if spec.handler is not None]
    assert executable
    assert all(spec.handler is not None and spec.handler.target is not None for spec in executable)
    assert all(
        not spec.handler.target.qualname.startswith("_") and ".<locals>." not in spec.handler.target.qualname
        for spec in executable
        if spec.handler is not None and spec.handler.target is not None
    )
    identities = [spec.result_schema.identity for spec in COMMAND_SPECS if spec.result_schema.identity is not None]
    assert len(identities) == len(set(identities))


def test_complete_authority_import_does_not_import_behavior_modules() -> None:
    source = (
        "import json, sys; "
        "from cadrumo.entrypoints.cli.command_specs import COMMAND_SPECS; "
        "targets = {spec.result_schema.target.module for spec in COMMAND_SPECS "
        "if spec.result_schema.target is not None}; "
        "targets.update(spec.handler.target.module for spec in COMMAND_SPECS "
        "if spec.handler is not None and spec.handler.target is not None); "
        "loaded = sorted(targets.intersection(sys.modules)); "
        "print(json.dumps({'specs': len(COMMAND_SPECS), 'loaded': loaded}))"
    )
    completed = subprocess.run(  # noqa: S603 - fixed interpreter and authored test program
        [sys.executable, "-c", source],
        check=True,
        capture_output=True,
        text=True,
    )
    observation = json.loads(completed.stdout)
    assert observation["specs"] == len(COMMAND_SPECS)
    assert observation["loaded"] == []


def test_handler_target_modules_do_not_import_the_cli_package_facade() -> None:
    modules = {
        spec.handler.target.module
        for spec in COMMAND_SPECS
        if spec.handler is not None and spec.handler.target is not None
    }
    facade = "cadrumo.entrypoints.cli"
    violations: list[str] = []
    for module in sorted(modules):
        found = find_spec(module)
        assert found is not None and found.origin is not None
        tree = ast.parse(Path(found.origin).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                imported_module = node.module
                if node.level:
                    relative = f"{'.' * node.level}{node.module or ''}"
                    imported_module = resolve_name(relative, module.rpartition(".")[0])
                imported_names = {
                    imported_module if alias.name == "*" else f"{imported_module}.{alias.name}"
                    for alias in node.names
                    if imported_module is not None
                }
                if imported_module == facade or facade in imported_names:
                    violations.append(module)
            if isinstance(node, ast.Import) and any(alias.name == facade for alias in node.names):
                violations.append(module)
            if (
                isinstance(node, ast.Call)
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and node.args[0].value == facade
                and (
                    (isinstance(node.func, ast.Name) and node.func.id == "__import__")
                    or (isinstance(node.func, ast.Name) and node.func.id == "import_module")
                    or (isinstance(node.func, ast.Attribute) and node.func.attr == "import_module")
                )
            ):
                violations.append(module)
    assert violations == []


def test_ledger_census_projects_every_live_invocable_command_spec() -> None:
    invocables = _ledger_invocable_specs()
    live_paths = {
        node.spec.key: node.path
        for node in COMMAND_GRAPH.nodes()
        if node.path[:3] == ("aeat", "app", "ledger")
        and (node.spec.kind is CommandNodeKind.LEAF or node.spec.invocation.invoke_without_command)
    }

    assert len(LEDGER_CLI_COMMAND_CENSUS) == len(invocables) == len(live_paths)
    assert {entry.command_key for entry in LEDGER_CLI_COMMAND_CENSUS} == {spec.key for spec in invocables}
    assert "app_ledger_participation" in live_paths
    for entry in LEDGER_CLI_COMMAND_CENSUS:
        spec = next(spec for spec in invocables if spec.key == entry.command_key)
        assert spec.handler is not None and spec.handler.target is not None
        assert spec.result_schema.identity is not None
        assert entry.path == live_paths[spec.key]
        assert entry.handler_identity == spec.handler.target.identity
        assert entry.result_schema_identity == spec.result_schema.identity
        assert entry.tui_capability is spec.tui_capability is TuiCapability.NOT_IMPLEMENTED


def test_ledger_census_keeps_auto_split_effect_outcomes_distinct() -> None:
    classify = next(entry for entry in LEDGER_CLI_COMMAND_CENSUS if entry.command_key == "app_ledger_classify")

    assert classify.suboperation_ids == (
        "ledger.classify.direct",
        "ledger.classify.m210",
        "ledger.classify.iva_derive",
        "ledger.classify.llm_preview",
        "ledger.classify.llm_apply",
        "ledger.classify.llm_reject",
        "ledger.classify.llm_saturate_preview",
        "ledger.classify.llm_saturate_apply",
        "ledger.classify.llm_saturate_reject",
        "ledger.classify.evidence_read",
        "ledger.classify.auto_split.reject",
        "ledger.classify.auto_split.split_preview",
        "ledger.classify.auto_split.split_apply",
        "ledger.classify.auto_split.single_preview",
        "ledger.classify.auto_split.single_apply",
        "ledger.classify.bulk_csv",
    )


def test_ledger_census_rejects_missing_unknown_and_duplicate_annotations() -> None:
    invocables = _ledger_invocable_specs()

    with pytest.raises(ValueError, match=r"unknown=.*app_ledger_unknown"):
        _validated_annotations(
            invocables,
            (
                *_LEDGER_CLI_CENSUS_ANNOTATIONS,
                LedgerCliCensusAnnotation("app_ledger_unknown", LedgerCliAdapterOwnership.MIXED),
            ),
        )
    with pytest.raises(ValueError, match=r"missing=.*app_ledger_add"):
        _validated_annotations(invocables, _LEDGER_CLI_CENSUS_ANNOTATIONS[1:])
    with pytest.raises(ValueError, match="duplicate ownership annotations"):
        _validated_annotations(invocables, (*_LEDGER_CLI_CENSUS_ANNOTATIONS, _LEDGER_CLI_CENSUS_ANNOTATIONS[0]))


def test_ledger_census_rejects_new_and_duplicate_invocable_endpoints() -> None:
    invocables = _ledger_invocable_specs()
    unannotated = replace(invocables[0], key="app_ledger_unadjudicated")

    with pytest.raises(ValueError, match=r"missing=.*app_ledger_unadjudicated"):
        _validated_annotations((unannotated, *invocables[1:]))
    with pytest.raises(ValueError, match="duplicate invocable command keys"):
        _validated_annotations((*invocables, invocables[0]))


def test_ledger_census_rejects_duplicate_suboperation_annotations() -> None:
    duplicate_identity = _LEDGER_CLI_CENSUS_ANNOTATIONS[8].suboperation_ids[0]
    duplicate = replace(
        _LEDGER_CLI_CENSUS_ANNOTATIONS[0],
        suboperation_ids=(duplicate_identity,),
    )

    with pytest.raises(ValueError, match="duplicate semantic sub-operation identities"):
        _validated_annotations(
            _ledger_invocable_specs(),
            (duplicate, *_LEDGER_CLI_CENSUS_ANNOTATIONS[1:]),
        )


@pytest.mark.parametrize(
    "identity",
    ("ledger.fooBar", "ledger.é", "ledger._alpha", "ledger.a-", "ledger.", "ledger"),
)
def test_ledger_census_rejects_noncanonical_suboperation_identities(identity: str) -> None:
    with pytest.raises(ValueError, match="not a stable identity"):
        LedgerCliCensusAnnotation("app_ledger_add", LedgerCliAdapterOwnership.MIXED, (identity,))


def test_ledger_census_rejects_unavailable_handler_or_schema() -> None:
    invocables = _ledger_invocable_specs()
    target = invocables[0]
    unavailable_handler = replace(
        target,
        handler=LazyBinding.unavailable(translation_key("ledger.census.handler.unavailable")),
    )
    unavailable_schema = replace(
        target,
        result_schema=ResultSchemaSpec(
            SchemaState.UNAVAILABLE,
            reason_key=translation_key("ledger.census.schema.unavailable"),
        ),
    )
    handler_specs = tuple(unavailable_handler if spec.key == target.key else spec for spec in LEDGER_COMMAND_SPECS)
    schema_specs = tuple(unavailable_schema if spec.key == target.key else spec for spec in LEDGER_COMMAND_SPECS)

    with pytest.raises(ValueError, match="lacks an available deferred handler"):
        _build_ledger_cli_command_census(handler_specs)
    with pytest.raises(ValueError, match="lacks an available result schema"):
        _build_ledger_cli_command_census(schema_specs)
