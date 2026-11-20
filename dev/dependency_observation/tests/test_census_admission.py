"""The import gate resolves every module the census admission runs to a closed, declared census."""

from __future__ import annotations

import ast
from dataclasses import replace
from pathlib import Path

import pytest

from cadrumo.tests.module_target_inventory import load_all_target_sets

from ...quality.import_authority import read_authority
from ...quality.import_binding_inventory import read_modules
from ...quality.import_check_models import RootPackage
from ...quality.import_dynamic_targets import metadata_target_set_targets
from ...quality.import_target_evaluation import TargetEvaluationContext
from ..census_admission import PRODUCT_CENSUS, SUPPORT_CENSUSES

pytestmark = [pytest.mark.integration, pytest.mark.hex_core]

_REPOSITORY = Path(__file__).resolve().parents[3]
_PACKAGE = "dev.dependency_observation"


def test_each_run_module_target_resolves_to_its_census_partitions() -> None:
    read = read_authority(_REPOSITORY)
    assert read.authority is not None and not read.broken
    authority = replace(read.authority, roots=(RootPackage(_PACKAGE, _REPOSITORY / "dev" / "dependency_observation"),))
    modules, findings = read_modules(authority)
    assert not findings
    module = modules[f"{_PACKAGE}.census_admission"]
    context = TargetEvaluationContext(module.tree, module.name)
    resolved = [
        metadata_target_set_targets(node.args[0], node.lineno, module, context, _REPOSITORY)
        for node in ast.walk(module.tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "run_module"
    ]
    product = frozenset(load_all_target_sets(PRODUCT_CENSUS, repository=_REPOSITORY))
    support = frozenset(
        target for partition in SUPPORT_CENSUSES for target in load_all_target_sets(partition, repository=_REPOSITORY)
    )
    assert len(resolved) == 2
    assert set(resolved) == {(product, True), (support, True)}
