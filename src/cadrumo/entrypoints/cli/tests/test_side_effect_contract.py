"""A leaf declaring no side effects must not write to the storage root.

``side_effects`` is a declaration the write router and the operator surface
already read, so a leaf carrying ``none`` is asserting that running it changes
nothing on disk. Nothing checked that, and it was not true: every leaf
invocation ran an unconditional ``ensure_storage_tree()``, so a read-only
command materialised twenty-five directories -- ``blobs``, ``financial``,
``secrets``, the whole ``cache`` tree -- before doing anything. A first run
looked like a configured install.

Only leaves whose parameters are all optional are exercised. A leaf with a
required argument would exit on a usage error BEFORE reaching the point where
state is created, so including it would add a passing case that proves
nothing. That is the difference between covering 93 leaves and appearing to
cover 148.

The command is expected to fail. Most of these refuse for want of an active
profile, and that refusal happens AFTER the preflight that used to
materialise the tree -- which is exactly the path under test. What is asserted
is the filesystem, never the exit code.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

import pytest

from ....tests.cli_performance import is_non_authoritative_artifact
from .. import command_graph
from .._command_spec import CommandSpec

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

#: Commands that open the cold-bootstrap secure-object store and so create the
#: encrypted database on first access. Each entry states WHY, because this is
#: where the judgement lives -- a bare list of paths would record only that
#: someone once found these inconvenient.
#:
#: Creating a fresh store on first access is sanctioned: `no-legacy-compatibility`
#: is explicit that bootstrap-on-first-access is forward-functional, unlike a
#: migration. What is unresolved is whether a command that only READS should
#: open the store in a mode that declines to create it. That is a storage-engine
#: decision rather than a CLI one, and it is recorded in the campaign audit.
#:
#: Entries are proven live below: if a command stops creating the database, its
#: entry MUST be deleted rather than left behind to excuse a future regression.
_BOOTSTRAP_STORE_COMMANDS: dict[tuple[str, ...], str] = {
    ("config", "auth", "apoderado", "check"): "reads apoderado state through the cold-bootstrap workflow store",
    ("config", "auth", "certificate", "list"): "lists certificate sources recorded in the workflow store",
    ("config", "repair", "integrity", "objects"): "inspects secure-object integrity, which requires the store",
}

_DATABASE_PATHS = ("cadrumo.db", "cadrumo.db-shm", "cadrumo.db-wal")


_PROBE = textwrap.dedent(
    """
    import json
    import os
    import sys

    root = sys.argv[2]
    os.environ["CADRUMO_LOCAL_STORAGE_ROOT"] = root

    import typer.main
    from click.testing import CliRunner

    from cadrumo.entrypoints.cli import app

    runner = CliRunner()
    runner.invoke(typer.main.get_command(app), json.loads(sys.argv[1]))

    from pathlib import Path

    base = Path(root)
    created = sorted(p.relative_to(base).as_posix() for p in base.rglob("*")) if base.exists() else []
    print(json.dumps(created))
    """
)


def _has_only_optional_parameters(spec: CommandSpec) -> bool:
    return all(not str(parameter.default.kind).endswith("REQUIRED") for parameter in spec.parameters)


def _side_effect_free_leaves() -> list[tuple[str, ...]]:
    return [
        node.path[1:]
        for node in command_graph.nodes()
        if node.spec.kind == "leaf"
        and node.spec.policy.side_effects == frozenset({"none"})
        and _has_only_optional_parameters(node.spec)
    ]


def _created_paths(argv: tuple[str, ...]) -> list[str]:
    """Invoke ``argv`` in a fresh interpreter against an empty root."""
    with tempfile.TemporaryDirectory(prefix="cadrumo-side-effect-") as directory:
        root = Path(directory) / "state"
        completed = subprocess.run(
            [sys.executable, "-c", _PROBE, json.dumps(list(argv)), str(root)],
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
        )
        assert completed.returncode == 0, f"{argv}: probe crashed\n{completed.stderr}"
        return json.loads(completed.stdout.strip().splitlines()[-1])


def test_the_side_effect_free_declaration_still_covers_real_leaves() -> None:
    """FIXTURE ANCHOR: the gate below must not pass by measuring nothing."""
    leaves = _side_effect_free_leaves()

    assert len(leaves) >= 40, f"only {len(leaves)} exercisable side-effect-free leaves; the declaration may have drifted"


@pytest.mark.parametrize("argv", _side_effect_free_leaves(), ids=lambda argv: "/".join(argv))
def test_a_side_effect_free_leaf_writes_no_storage_state(argv: tuple[str, ...]) -> None:
    """DISCRIMINATING: running the leaf leaves the storage root free of state."""
    created = [path for path in _created_paths(argv) if not is_non_authoritative_artifact(path)]
    if argv in _BOOTSTRAP_STORE_COMMANDS:
        created = [path for path in created if path not in _DATABASE_PATHS]

    assert created == [], (
        f"`aeat {' '.join(argv)}` declares side_effects=none but created:\n  "
        + "\n  ".join(created)
        + "\nEither the leaf really does write -- declare it -- or something on its "
        "path is materialising state it was not asked for."
    )


@pytest.mark.parametrize("argv", sorted(_BOOTSTRAP_STORE_COMMANDS), ids=lambda argv: "/".join(argv))
def test_every_bootstrap_store_exception_still_earns_its_place(argv: tuple[str, ...]) -> None:
    """STALE-ENTRY: an exception that no longer applies must be deleted.

    An allowlist nobody prunes stops describing the tree and starts excusing
    whatever drifts into it. This requires each entry to still create the
    database it was granted for.
    """
    created = _created_paths(argv)

    assert any(path in _DATABASE_PATHS for path in created), (
        f"`aeat {' '.join(argv)}` no longer creates the database, so its entry in "
        f"_BOOTSTRAP_STORE_COMMANDS ({_BOOTSTRAP_STORE_COMMANDS[argv]}) is stale and must be removed."
    )


def test_the_probe_sees_state_a_writing_command_creates() -> None:
    """ANTI-TAUTOLOGY: the scan must be able to say yes.

    If the probe reported an empty list for any reason -- a crashed child, a
    root it never looked at, a path-relativity slip -- every case above would
    pass forever. This asks the same probe to observe a root that a real
    materialisation touched.
    """
    with tempfile.TemporaryDirectory(prefix="cadrumo-side-effect-proof-") as directory:
        root = Path(directory) / "state"
        completed = subprocess.run(
            [
                sys.executable,
                "-c",
                "import os, sys, json; from pathlib import Path; "
                "root = sys.argv[1]; os.environ['CADRUMO_LOCAL_STORAGE_ROOT'] = root; "
                "from cadrumo.core.storage_materialization import ensure_storage_tree; ensure_storage_tree(); "
                "base = Path(root); "
                "print(json.dumps(sorted(p.relative_to(base).as_posix() for p in base.rglob('*'))))",
                str(root),
            ],
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
        )
        assert completed.returncode == 0, completed.stderr
        created = json.loads(completed.stdout.strip().splitlines()[-1])

    observed = [path for path in created if not is_non_authoritative_artifact(path)]
    assert observed, "the probe cannot see a materialised storage tree; it would pass on any command"
