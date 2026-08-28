"""A state-free node must load none of the expensive capability families.

``test_lazy_command_tree`` guards ONE family (the registry) on ONE path (the
root help and version surfaces). This is the whole-graph half: every node whose
spec declares ``state-free`` -- 68 of them -- must resolve without loading the
registry, cryptography, custody, keyring, or persistence families.

The declaration is the authority. ``state-free`` is not a comment: the census,
the write router and the operator surface all read the same field, so a node
carrying it is asserting that resolving it touches none of those subsystems. A
node that needs one of them is not failing this gate -- it is mis-declared, and
the fix is the declaration or the import, never an exemption here.

Resolution, not invocation, is deliberately what is measured. A leaf may load
whatever its declared capabilities allow once an operator actually runs it; the
cost this campaign exists to remove is the cost paid on the way *to* a command,
by every sibling and ancestor, before anything has been asked for.
"""

from __future__ import annotations

import json
import subprocess
import sys
import textwrap

import pytest
from pydantic import TypeAdapter

from ....entrypoints.cli import command_graph
from ....tests.cli_performance import IMPORT_FAMILY_PREFIXES

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_COMPLETED = "PROBE-COMPLETED"
_LOADED_FAMILIES_ADAPTER: TypeAdapter[dict[str, list[str]]] = TypeAdapter(dict[str, list[str]])

_PROBE = textwrap.dedent(
    """
    import json
    import sys

    paths = json.loads(sys.argv[1])
    prefixes = json.loads(sys.argv[2])

    from cadrumo.tests.cli_performance import _resolve_cli_path

    for path in paths:
        _resolve_cli_path(tuple(path))

    loaded = {
        family: sorted(name for name in sys.modules if name.startswith(tuple(entries)))
        for family, entries in prefixes.items()
    }
    print(json.dumps({family: names for family, names in loaded.items() if names}))
    print(COMPLETED_MARKER)
    """
)


def _state_free_paths() -> list[list[str]]:
    return [list(node.path[1:]) for node in command_graph.nodes() if "state-free" in node.spec.policy.capabilities]


def _probe(paths: list[list[str]]) -> dict[str, list[str]]:
    """Resolve ``paths`` in a FRESH interpreter and report loaded families.

    A fresh process is the whole method: this session has already imported
    every family many times over, so an in-process scan of ``sys.modules``
    would read other tests' imports and pass or fail for unrelated reasons.
    """
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            _PROBE.replace("COMPLETED_MARKER", repr(_COMPLETED)),
            json.dumps(paths),
            json.dumps({family: list(entries) for family, entries in IMPORT_FAMILY_PREFIXES.items()}),
        ],
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    lines = [line for line in completed.stdout.splitlines() if line.strip()]
    assert _COMPLETED in lines, f"the probe did not reach its assertion: {completed.stdout}{completed.stderr}"
    return _LOADED_FAMILIES_ADAPTER.validate_python(json.loads(lines[0])) if lines[0] != _COMPLETED else {}


def test_the_state_free_declaration_still_covers_real_nodes() -> None:
    """FIXTURE ANCHOR: the gate below must not pass by measuring nothing.

    If the capability were renamed or dropped from every spec, the probe would
    resolve an empty list, load nothing, and report a clean tree forever.
    """
    paths = _state_free_paths()

    assert len(paths) >= 20, f"only {len(paths)} state-free nodes; the declaration may have drifted"


def test_resolving_every_state_free_node_loads_no_expensive_family() -> None:
    """DISCRIMINATING: the whole state-free surface stays free of all five families.

    Every state-free node is resolved in ONE fresh process and the union of
    what they loaded is checked. The union is what makes this equivalent to
    checking each node separately: if the union is empty, no individual node
    loaded anything, and one process does the work of sixty-eight.
    """
    loaded = _probe(_state_free_paths())

    assert loaded == {}, (
        "resolving a state-free node loaded an expensive capability family:\n  "
        + "\n  ".join(f"{family}: {len(names)} modules, first {names[0]}" for family, names in sorted(loaded.items()))
        + "\nEither the node needs the capability -- declare it on the spec -- or "
        "something on its resolution path gained an eager import."
    )


def test_the_probe_detects_every_family_it_claims_to_scan() -> None:
    """ANTI-TAUTOLOGY: each family's prefixes must be able to match something.

    A renamed package would leave its prefix matching nothing, and the gate
    above would report a clean tree while that family loaded freely. This
    imports one real module per family and requires the scan to see it.
    """
    imports = {
        "registry": "cadrumo.domain.calculations.registry",
        "crypto": "cryptography",
        "custody": "cadrumo.adapters.persistence.storage.custody",
        "keyring": "cadrumo.adapters.persistence.storage.secret_store",
        "storage": "cadrumo.adapters.persistence",
    }
    assert set(imports) == set(IMPORT_FAMILY_PREFIXES), "a family lost its anti-tautology import"

    blind: list[str] = []
    for family, module in sorted(imports.items()):
        completed = subprocess.run(
            [
                sys.executable,
                "-c",
                f"import json, sys; import {module}; "
                f"print(json.dumps(sorted(n for n in sys.modules "
                f"if n.startswith(tuple({list(IMPORT_FAMILY_PREFIXES[family])!r})))))",
            ],
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
        )
        assert completed.returncode == 0, f"{family}: {completed.stderr}"
        if not json.loads(completed.stdout.strip()):
            blind.append(f"{family} (imported {module})")

    assert blind == [], "these family scans cannot see their own module; the prefixes have drifted: " + ", ".join(blind)
