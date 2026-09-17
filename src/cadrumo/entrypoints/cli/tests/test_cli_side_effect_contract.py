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
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import TypedDict

import pytest
from pydantic import TypeAdapter

from ..command_spec import CommandSpec
from ..command_specs import COMMAND_GRAPH
from .cli_performance import is_non_authoritative_artifact

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_CREATED_PATHS_ADAPTER: TypeAdapter[list[str]] = TypeAdapter(list[str])

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

#: Side-effect-free leaves this headless probe cannot run, keyed with why. The
#: probe has no terminal to give them, so they would wait for input forever.
_INTERACTIVE_ONLY_LEAVES: dict[tuple[str, ...], str] = {
    ("app", "tui"): "hands the console to the full-screen root process, which waits for an interactive terminal",
}

_DATABASE_PATHS = ("cadrumo.db", "cadrumo.db-shm", "cadrumo.db-wal")


#: The leaf that is also run alone in its own interpreter. It creates state, so
#: a batched run that lost track of where state goes disagrees with it, and it
#: runs last in its batch, after the other store-opening leaves, where
#: process-lifetime state carried over from earlier leaves is most likely to
#: hide a write.
_CONTROL_LEAF: tuple[str, ...] = ("config", "auth", "certificate", "list")

_BATCH_COUNT = 2

#: Runs a sequence of leaves in one interpreter. Importing the CLI dominates the
#: cost of a leaf, so it is paid once per batch; each leaf still gets its own
#: runner and its own never-before-used storage root. Process-lifetime state
#: (cached settings, engines, registered ports) can still send a later leaf's
#: writes to an earlier root, where a scan of the new root would miss them, so
#: after each leaf every earlier root -- including the one live during import --
#: is rescanned and any change is reported as a stray write.
_PROBE = textwrap.dedent(
    """
    import json
    import os
    import sys
    from pathlib import Path

    base = Path(sys.argv[1])
    leaves = json.loads(sys.stdin.read())

    def scan(root):
        return sorted(p.relative_to(root).as_posix() for p in root.rglob("*")) if root.exists() else []

    import_root = base / "import" / "state"
    os.environ["CADRUMO_LOCAL_STORAGE_ROOT"] = str(import_root)

    import typer.main
    from click.testing import CliRunner

    from cadrumo.entrypoints.cli.main import app

    command = typer.main.get_command(app)
    observed = {import_root: scan(import_root)}
    report = []
    for index, argv in enumerate(leaves):
        root = base / f"leaf-{index:03d}" / "state"
        before = scan(root)
        os.environ["CADRUMO_LOCAL_STORAGE_ROOT"] = str(root)
        CliRunner().invoke(command, argv)
        strayed = {}
        for earlier, seen in observed.items():
            now = scan(earlier)
            if now != seen:
                strayed[earlier.parent.name] = sorted(set(now) - set(seen))
                observed[earlier] = now
        created = scan(root)
        observed[root] = created
        report.append({"argv": argv, "before": before, "created": created, "strayed": strayed})
    print(json.dumps(report))
    """
)


def _has_only_optional_parameters(spec: CommandSpec) -> bool:
    return all(not str(parameter.default.kind).endswith("REQUIRED") for parameter in spec.parameters)


def _declared_side_effect_free_leaves() -> list[tuple[str, ...]]:
    return [
        node.path[1:]
        for node in COMMAND_GRAPH.nodes()
        if node.spec.kind == "leaf"
        and node.spec.policy.side_effects == frozenset({"none"})
        and _has_only_optional_parameters(node.spec)
    ]


def _side_effect_free_leaves() -> list[tuple[str, ...]]:
    return [argv for argv in _declared_side_effect_free_leaves() if argv not in _INTERACTIVE_ONLY_LEAVES]


class _LeafReport(TypedDict):
    argv: list[str]
    before: list[str]
    created: list[str]
    strayed: dict[str, list[str]]


_REPORT_ADAPTER: TypeAdapter[list[_LeafReport]] = TypeAdapter(list[_LeafReport])


def _run_probe(leaves: list[tuple[str, ...]]) -> list[_LeafReport]:
    """Invoke ``leaves`` in order in one fresh interpreter, one empty root each."""
    with tempfile.TemporaryDirectory(prefix="cadrumo-side-effect-") as directory:
        completed = subprocess.run(
            [sys.executable, "-c", _PROBE, directory],
            input=json.dumps([list(argv) for argv in leaves]),
            capture_output=True,
            text=True,
            timeout=900,
            check=False,
        )
    assert completed.returncode == 0, f"probe crashed on {leaves}\n{completed.stderr}"
    reports = _REPORT_ADAPTER.validate_python(json.loads(completed.stdout.strip().splitlines()[-1]))
    assert [tuple(report["argv"]) for report in reports] == leaves, "probe did not report every leaf in order"
    for report in reports:
        assert report["before"] == [], f"{report['argv']}: storage root was not empty before the leaf ran"
        assert report["strayed"] == {}, (
            f"{report['argv']}: wrote into a root from an earlier leaf or from import:\n{report['strayed']}"
        )
    return reports


def _batches() -> list[list[tuple[str, ...]]]:
    leaves = sorted(set(_side_effect_free_leaves()) | set(_BOOTSTRAP_STORE_COMMANDS))
    store_leaves = sorted(set(_BOOTSTRAP_STORE_COMMANDS) - {_CONTROL_LEAF})
    rest = [argv for argv in leaves if argv not in _BOOTSTRAP_STORE_COMMANDS]
    batches = [rest[index::_BATCH_COUNT] for index in range(_BATCH_COUNT)]
    batches[0].extend([*store_leaves, _CONTROL_LEAF])
    return batches


@pytest.fixture(scope="session")
def created_paths_by_leaf() -> dict[tuple[str, ...], list[str]]:
    """Paths each leaf created, batched, after checking the batch against isolation."""
    runs = [*_batches(), [_CONTROL_LEAF]]
    with ThreadPoolExecutor(max_workers=len(runs)) as pool:
        *batched, isolated = pool.map(_run_probe, runs)

    created = {tuple(report["argv"]): report["created"] for reports in batched for report in reports}

    def authoritative(paths: list[str]) -> list[str]:
        return [path for path in paths if not is_non_authoritative_artifact(path)]

    batched_control = authoritative(created[_CONTROL_LEAF])
    isolated_control = authoritative(isolated[0]["created"])
    assert batched_control == isolated_control, (
        f"`aeat {' '.join(_CONTROL_LEAF)}` created different state when batched than in its own "
        f"interpreter, so batching is hiding or inventing writes.\n"
        f"  batched:  {batched_control}\n  isolated: {isolated_control}"
    )
    assert any(path in _DATABASE_PATHS for path in isolated_control), (
        f"control leaf `aeat {' '.join(_CONTROL_LEAF)}` creates no database, so it cannot tell "
        "a batched run that lost its writes from one that had none; choose a control that writes"
    )
    return created


def _created_paths(created_paths_by_leaf: dict[tuple[str, ...], list[str]], argv: tuple[str, ...]) -> list[str]:
    return _CREATED_PATHS_ADAPTER.validate_python(created_paths_by_leaf[argv])


def test_the_side_effect_free_declaration_still_covers_real_leaves() -> None:
    """FIXTURE ANCHOR: the gate below must not pass by measuring nothing."""
    leaves = _side_effect_free_leaves()

    assert len(leaves) >= 40, (
        f"only {len(leaves)} exercisable side-effect-free leaves; the declaration may have drifted"
    )


@pytest.mark.parametrize("argv", _side_effect_free_leaves(), ids=lambda argv: "/".join(argv))
def test_a_side_effect_free_leaf_writes_no_storage_state(
    argv: tuple[str, ...], created_paths_by_leaf: dict[tuple[str, ...], list[str]]
) -> None:
    """DISCRIMINATING: running the leaf leaves the storage root free of state."""
    created = [path for path in _created_paths(created_paths_by_leaf, argv) if not is_non_authoritative_artifact(path)]
    if argv in _BOOTSTRAP_STORE_COMMANDS:
        created = [path for path in created if path not in _DATABASE_PATHS]

    assert created == [], (
        f"`aeat {' '.join(argv)}` declares side_effects=none but created:\n  "
        + "\n  ".join(created)
        + "\nEither the leaf really does write -- declare it -- or something on its "
        "path is materialising state it was not asked for."
    )


@pytest.mark.parametrize("argv", sorted(_INTERACTIVE_ONLY_LEAVES), ids=lambda argv: "/".join(argv))
def test_every_interactive_only_exclusion_still_names_a_probed_leaf(argv: tuple[str, ...]) -> None:
    """STALE-ENTRY: an exclusion must still remove a leaf the probe would otherwise run."""
    assert argv in _declared_side_effect_free_leaves(), (
        f"`aeat {' '.join(argv)}` is no longer a side-effect-free leaf, so its entry in "
        f"_INTERACTIVE_ONLY_LEAVES ({_INTERACTIVE_ONLY_LEAVES[argv]}) is stale and must be removed."
    )


@pytest.mark.parametrize("argv", sorted(_BOOTSTRAP_STORE_COMMANDS), ids=lambda argv: "/".join(argv))
def test_every_bootstrap_store_exception_still_earns_its_place(
    argv: tuple[str, ...], created_paths_by_leaf: dict[tuple[str, ...], list[str]]
) -> None:
    """STALE-ENTRY: an exception that no longer applies must be deleted.

    An allowlist nobody prunes stops describing the tree and starts excusing
    whatever drifts into it. This requires each entry to still create the
    database it was granted for.
    """
    created = _created_paths(created_paths_by_leaf, argv)

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
