"""Execute distribution probe scripts against the current public command contracts."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import cast

import pytest

from cadrumo.entrypoints.cli.command_specs import COMMAND_GRAPH
from dev._paths import REPO_ROOT

from ..command_execution import run_command
from ..command_spec_attestation import _probe_installed_command_specs
from .test_command_spec_distribution_lanes import _PROBE as DISTRIBUTION_PROBE
from .test_command_spec_distribution_lanes import _assert_probe
from .test_command_spec_source_lanes import _assert_complete_projection, _run_probe

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


@pytest.mark.parametrize("probe", ["attestation", "distribution", "source"])
def test_current_command_contracts_execute_in_every_packaging_probe(tmp_path: Path, probe: str) -> None:
    """Resolve the real graph, targets, locales and schemas without a facade import."""
    source_root = REPO_ROOT / "src"
    if probe == "attestation":
        projection = _probe_installed_command_specs(site_root=source_root, work_root=tmp_path)
        assert len(projection["identities"]) == len(COMMAND_GRAPH.nodes())
        assert projection["locales"]
        assert projection["packaged_resources"]
        assert all(Path(origin).is_relative_to(source_root) for _name, origin in projection["origins"])
        selected = projection["import_budgets"]["selected_path_deltas"]
        assert {" ".join(row[0]) for row in selected} == {
            "aeat config profile list",
            "aeat app ledger categories",
            "aeat app modelo work calculate",
        }
    elif probe == "source":
        payload = _run_probe(python=Path(sys.executable), pythonpath=(source_root,), cwd=tmp_path)
        _assert_complete_projection(payload, checkout=REPO_ROOT)
    else:
        dependency_site = next(path for path in map(Path, sys.path) if path.name == "site-packages" and path.is_dir())
        result = run_command(
            [sys.executable, "-S", "-c", DISTRIBUTION_PROBE],
            cwd=tmp_path,
            environment={
                **os.environ,
                "PYTHONPATH": "",
                "AEAT_INSTALL_SITE": str(source_root),
                "AEAT_DEPENDENCY_SITE": str(dependency_site),
            },
            errors="strict",
        )
        assert result.returncode == 0, result.stderr
        _assert_probe(cast("dict[str, object]", json.loads(result.stdout)))
