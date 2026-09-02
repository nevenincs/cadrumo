"""Proofs that a locally-declared execution policy still names a write surface.

A command spec is matched as a write by the NAME of the execution-policy
constant it declares, against the set of policy names swept from the CLI tree.
Substituting that name for the expression it is bound to destroys the match: the
bound value is an ``ExecutionPolicySpec(...)`` call, which carries no dotted name
at all, so the policy reads as the empty string and the leaf silently drops out
of the analysis.

The substitution only reaches a spec whose policy constant is declared in the
SAME module, because only then is the name a module-level binding. No production
spec module is shaped that way today, which is exactly why this needs a test: a
detector that silently drops a write surface is the failure this package exists
to prevent, and the next spec module someone writes is one module-level constant
away from being invisible.

The negative half matters as much: a policy that is genuinely not a write must
keep being skipped, so the fix must not widen the sweep into read surfaces.

See Also:
    :mod:`dev.source_connectivity.discovery`
        The structural walk under test.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ..discovery import discover_ingress_surfaces

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

#: A spec module that declares its own policy constants and passes one directly
#: to a bare ``CommandSpec``, with no ``_leaf`` wrapper to route the name through
#: call bindings.
_SPEC_MODULE = """PROBE_WRITE = ExecutionPolicySpec(
    capabilities=frozenset({"encrypted-facts"}),
    side_effects=frozenset({"local-state"}),
    performance="local-io",
    write_route="profile-bound",
)

PROBE_READ = ExecutionPolicySpec(
    capabilities=frozenset({"encrypted-facts"}),
    side_effects=frozenset({"none"}),
    performance="local-io",
    write_route="none",
)

PROBE_COMMAND_SPECS = (
    CommandSpec(
        key="probe_add",
        parent_key="probe",
        token="add",
        kind=CommandNodeKind.LEAF,
        policy=__POLICY__,
        handler=LazyBinding.available(DeferredTarget("cadrumo.entrypoints.cli._probe", "probe_add")),
    ),
)
"""


def _write_spec_module(root: Path, policy: str) -> None:
    """Materialise a spec module declaring ``policy`` beside the spec it governs."""
    path = root / "src" / "cadrumo" / "entrypoints" / "cli" / "_probe_command_specs.py"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_SPEC_MODULE.replace("__POLICY__", policy), encoding="utf-8")


def test_a_write_policy_declared_in_the_spec_module_is_still_detected(tmp_path: Path) -> None:
    """The declared constant name, not the expression it binds, decides the match."""
    _write_spec_module(tmp_path, "PROBE_WRITE")

    rows = discover_ingress_surfaces(tmp_path)

    assert [(row.module, row.callback_name, row.command_name, row.execution_policy) for row in rows] == [
        ("src/cadrumo/entrypoints/cli/_probe.py", "probe_add", "add", "PROBE_WRITE")
    ]


def test_a_non_write_policy_declared_in_the_spec_module_is_still_skipped(tmp_path: Path) -> None:
    """Keeping the declared name must not widen the sweep onto read surfaces."""
    _write_spec_module(tmp_path, "PROBE_READ")

    assert discover_ingress_surfaces(tmp_path) == ()
