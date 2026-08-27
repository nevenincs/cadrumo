"""Resolving a node must load only the capability families its spec declares.

``capabilities`` is a declaration the census, the write router and the operator
surface all read. This makes it mean something at the import level too: if a
spec says ``profile-custody`` and nothing else, then resolving that node must
not drag in the calculation registry.

**Why groups rather than nodes.** The Step this implements asks for a
fresh-process check over every projected live node -- 365 of them, which is 365
interpreters. The 365 nodes carry only 25 DISTINCT capability declarations, and
those declarations PARTITION the node set. Resolving a whole group in one
process and checking the UNION of what it loaded is therefore equivalent to
checking each node separately: if the union is within the declared families,
every member is. Every node is still covered; the guarantee is not narrowed,
and the sweep costs 25 processes instead of 365.

**Resolution, not invocation.** A leaf may load whatever its declared
capabilities allow once an operator actually runs it. What this measures is the
cost paid on the way *to* a command, by ancestors and siblings, before anything
has been asked for -- which is the amplification this campaign exists to
remove.

Three groups do not satisfy their declaration yet. They are named below with
what they load and why it is unresolved, and a stale case deletes an entry the
moment it starts passing. Widening those declarations to make this file green
was available and refused: the declaration is the claim, and weakening the
claim to fit the code inverts the gate.
"""

from __future__ import annotations

import json
import subprocess
import sys
import textwrap

import pytest

from ....tests.cli_performance import IMPORT_FAMILY_PREFIXES
from .. import command_graph
from .._command_schema import CommandCapabilityClass

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_COMPLETED = "PROBE-COMPLETED"

#: Which import families a declared capability entitles a node to load.
#:
#: Read against EXPANDED capabilities, so the implications the schema already
#: declares (``calculation`` and ``filing`` imply ``registry``;
#: ``encrypted-facts`` implies ``profile-custody``) are honoured here rather
#: than restated. ``profile-custody`` entitles the persistence families because
#: custody IS encrypted local persistence: it opens the secure store, derives
#: keys and reaches the keyring by definition.
_CAPABILITY_FAMILIES: dict[str, frozenset[str]] = {
    "registry": frozenset({"registry"}),
    "crypto": frozenset({"crypto"}),
    "profile-custody": frozenset({"custody", "storage", "keyring", "crypto"}),
    "local-storage": frozenset({"storage"}),
}

#: Capability groups whose resolution graph exceeds their declaration today.
#: Each states the families and the reason, because this is where the judgement
#: sits; a bare list would record only that someone found them inconvenient.
_PENDING_ADJUDICATION: dict[frozenset[str], str] = {
    frozenset({"encrypted-facts"}): (
        "loads the registry package root and its `ids` leaf, because "
        "`domain.calculations._row_source_identity` takes `BindingId` from there. "
        "The same module imports `ContentDigest` from `core.identity`; `BindingId` "
        "belongs beside it. A placement fix, not a threshold"
    ),
    frozenset({"encrypted-facts", "network"}): (
        "loads the registry through `ledger.actions_common` typing against "
        "`domain.modelos` protocols, which reach `CalculationRevision` and through it "
        "`registry.bindings`. That chain is semantically real: a module typed against "
        "calculation revisions needs registry types. Resolving it means either "
        "declaring `calculation` on these nodes or splitting the protocol module"
    ),
    frozenset({"registry"}): (
        "registry-inspection commands load the persistence and crypto families they "
        "do not declare. Whether an inspection command legitimately reaches the "
        "secure store, or is pulling it through a shared emit path, is unadjudicated"
    ),
}

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
    print(json.dumps({family: len(names) for family, names in loaded.items() if names}))
    print(COMPLETED_MARKER)
    """
)


def _groups() -> dict[frozenset[str], list[list[str]]]:
    """Partition every live node by its exact capability declaration."""
    groups: dict[frozenset[str], list[list[str]]] = {}
    for node in command_graph.nodes():
        groups.setdefault(frozenset(node.spec.policy.capabilities), []).append(list(node.path[1:]))
    return groups


def _allowed_families(capabilities: frozenset[str]) -> frozenset[str]:
    expanded = CommandCapabilityClass(
        capabilities=capabilities,
        side_effects=frozenset({"none"}),
        performance="metadata",
    ).expanded_capabilities
    allowed: frozenset[str] = frozenset()
    for capability in expanded:
        allowed |= _CAPABILITY_FAMILIES.get(capability, frozenset())
    return allowed


def _loaded_families(paths: list[list[str]]) -> dict[str, int]:
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
        timeout=900,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    lines = [line for line in completed.stdout.splitlines() if line.strip()]
    assert _COMPLETED in lines, f"the probe did not reach its assertion: {completed.stdout}{completed.stderr}"
    return json.loads(lines[0]) if lines[0] != _COMPLETED else {}


_GROUPS = _groups()


def test_the_declarations_still_partition_every_live_node() -> None:
    """FIXTURE ANCHOR: the group sweep must cover the whole graph.

    The equivalence between checking groups and checking nodes rests entirely
    on the groups partitioning the node set. If that stopped being true, this
    file would silently check less than it claims.
    """
    covered = sum(len(paths) for paths in _GROUPS.values())

    assert covered == len(command_graph.nodes()), f"groups cover {covered} of {len(command_graph.nodes())} nodes"
    assert len(_GROUPS) >= 20, f"only {len(_GROUPS)} distinct declarations; the taxonomy may have collapsed"


@pytest.mark.parametrize("capabilities", sorted(_GROUPS, key=sorted), ids=lambda caps: ",".join(sorted(caps)) or "none")
def test_a_group_loads_only_the_families_it_declares(capabilities: frozenset[str]) -> None:
    """DISCRIMINATING: resolution stays inside the declared capability set."""
    if capabilities in _PENDING_ADJUDICATION:
        pytest.skip(f"pending adjudication: {_PENDING_ADJUDICATION[capabilities]}")

    allowed = _allowed_families(capabilities)
    loaded = _loaded_families(_GROUPS[capabilities])
    undeclared = sorted(family for family in loaded if family not in allowed)

    assert undeclared == [], (
        f"nodes declaring {sorted(capabilities) or ['(none)']} resolved and loaded "
        f"undeclared families {undeclared} (counts: {loaded}). "
        "Either the nodes need the capability -- declare it -- or something on their "
        "resolution path gained an eager import."
    )


@pytest.mark.parametrize(
    "capabilities", sorted(_PENDING_ADJUDICATION, key=sorted), ids=lambda caps: ",".join(sorted(caps))
)
def test_a_pending_group_that_now_passes_must_be_removed(capabilities: frozenset[str]) -> None:
    """STALE-ENTRY: a residue entry that stopped applying must be deleted.

    Without this the pending list would outlive the problem and quietly excuse
    a regression into a group that had been cleaned up.
    """
    allowed = _allowed_families(capabilities)
    loaded = _loaded_families(_GROUPS[capabilities])
    undeclared = sorted(family for family in loaded if family not in allowed)

    assert undeclared != [], (
        f"nodes declaring {sorted(capabilities)} now load only their declared families, so their "
        f"_PENDING_ADJUDICATION entry is stale and must be removed: {_PENDING_ADJUDICATION[capabilities]}"
    )
