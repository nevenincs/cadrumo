from __future__ import annotations

import json
import sys

import pytest

from cadrumo.tests.audited_process import run_audited_process

from ..command_specs import COMMAND_GRAPH

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_complete_command_authority_has_the_exact_shipped_shape() -> None:
    assert COMMAND_GRAPH.specs
    assert len(COMMAND_GRAPH.nodes()) == len(COMMAND_GRAPH.specs)
    assert sum(spec.kind == "root" for spec in COMMAND_GRAPH.specs) == 1
    assert all(spec.kind in {"root", "group", "leaf"} for spec in COMMAND_GRAPH.specs)
    assert len({node.path for node in COMMAND_GRAPH.nodes()}) == len(COMMAND_GRAPH.specs)


def test_every_executable_target_is_public_and_every_schema_identity_is_unique() -> None:
    executable = [spec for spec in COMMAND_GRAPH.specs if spec.handler is not None]
    assert executable
    assert all(spec.handler is not None and spec.handler.target is not None for spec in executable)
    assert all(
        not spec.handler.target.qualname.startswith("_") and ".<locals>." not in spec.handler.target.qualname
        for spec in executable
        if spec.handler is not None and spec.handler.target is not None
    )
    identities = [
        spec.result_schema.identity for spec in COMMAND_GRAPH.specs if spec.result_schema.identity is not None
    ]
    assert len(identities) == len(set(identities))


def test_complete_authority_import_does_not_import_behavior_modules() -> None:
    source = (
        "import json, sys; "
        "from cadrumo.entrypoints.cli.command_specs import COMMAND_GRAPH; "
        "targets = {spec.result_schema.target.module for spec in COMMAND_GRAPH.specs "
        "if spec.result_schema.target is not None}; "
        "targets.update(spec.handler.target.module for spec in COMMAND_GRAPH.specs "
        "if spec.handler is not None and spec.handler.target is not None); "
        "loaded = sorted(targets.intersection(sys.modules)); "
        "print(json.dumps({'specs': len(COMMAND_GRAPH.specs), 'loaded': loaded}))"
    )
    completed = run_audited_process(
        [sys.executable, "-c", source],
        check=True,
        capture_output=True,
        text=True,
    )
    observation = json.loads(completed.stdout)
    assert observation["specs"] == len(COMMAND_GRAPH.specs)
    assert observation["loaded"] == []
