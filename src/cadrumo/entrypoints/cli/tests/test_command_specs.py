from __future__ import annotations

import subprocess
import sys

import pytest

from .._command_specs import COMMAND_GRAPH, COMMAND_SPECS

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_complete_command_authority_has_the_exact_shipped_shape() -> None:
    assert len(COMMAND_SPECS) == 363
    assert len(COMMAND_GRAPH.nodes()) == 363
    assert sum(spec.kind == "root" for spec in COMMAND_SPECS) == 1
    assert sum(spec.kind == "group" for spec in COMMAND_SPECS) == 72
    assert sum(spec.kind == "leaf" for spec in COMMAND_SPECS) == 290
    assert len({node.path for node in COMMAND_GRAPH.nodes()}) == 363


def test_every_executable_target_is_public_and_every_schema_identity_is_unique() -> None:
    executable = [spec for spec in COMMAND_SPECS if spec.handler is not None]
    assert executable
    assert all(spec.handler is not None and spec.handler.target is not None for spec in executable)
    assert all(
        not spec.handler.target.qualname.startswith("_")
        and ".<locals>." not in spec.handler.target.qualname
        for spec in executable
        if spec.handler is not None and spec.handler.target is not None
    )
    identities = [
        spec.result_schema.identity
        for spec in COMMAND_SPECS
        if spec.result_schema.identity is not None
    ]
    assert len(identities) == len(set(identities))


def test_complete_authority_import_does_not_import_behavior_modules() -> None:
    source = (
        "import sys; "
        "from cadrumo.entrypoints.cli._command_specs import COMMAND_SPECS; "
        "forbidden = ('._ledger_', '._app_live', '._modelo', '._overview', '._registry', '._review'); "
        "loaded = sorted(name for name in sys.modules "
        "if name.startswith('cadrumo.entrypoints.cli.') and any(token in name for token in forbidden) "
        "and not name.endswith('command_specs') and '_command_spec' not in name); "
        "print(len(COMMAND_SPECS)); print('\\n'.join(loaded), end='')"
    )
    completed = subprocess.run(  # noqa: S603 - fixed interpreter and authored test program
        [sys.executable, "-c", source],
        check=True,
        capture_output=True,
        text=True,
    )
    lines = completed.stdout.splitlines()
    assert lines[0] == "363"
    assert lines[1:] == []
