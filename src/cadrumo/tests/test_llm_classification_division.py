"""The classification division: inference one side, persistence the other.

``application/ledger/_llm_classification.py`` mixes two concerns that the
inference boundary separates: the calls that ask a model something, and the
writes that record what the operator decided. The module is not moved -- it is
DIVIDED, and these assertions pin the division line so a later change cannot
drift it in either direction.

Both directions matter and they fail differently. If a core write migrates into
the subpackage, an optional install starts owning ledger state. If the core
starts reaching for inference unconditionally, the non-ledger diagnostics
consumer becomes conditional on an optional package. Neither shows up as a test
failure anywhere else, which is why these are structural.
"""

from __future__ import annotations

import ast

import pytest

from . import SRC_CADRUMO, ast_for_path, leaf_name, non_test_python_files_under, repo_relative

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_LLM_PACKAGE = SRC_CADRUMO / "llm"
_RUN_HEALTH = SRC_CADRUMO / "application" / "diagnostics_run_health.py"

# Emitting a bucket event is the act of recording a state change in the
# operator's audit trail. It belongs to whichever side owns the write, and that
# side is the core.
_EVENT_EMISSION_CALLS = {
    "emit_bucket_event",
    "derive_bucket_event",
    "append_bucket_event",
    "set_classification",
    "update_manual_transaction_fields",
}


def test_no_bucket_event_or_classification_write_happens_inside_the_subpackage() -> None:
    """S40's line: classification writes and event history stay core-side.

    The subpackage asks the model; it does not record the answer. A write that
    migrated here would put ledger state and the operator's audit trail behind
    an optional install, and would emit lifecycle events from a component the
    core cannot assume is present.

    Mutation that must trip this: call ``emit_bucket_event`` or
    ``set_classification`` from any module under the subpackage.
    """
    modules = list(non_test_python_files_under(_LLM_PACKAGE, include_data=True))
    assert modules, f"{repo_relative(_LLM_PACKAGE)} resolved to nothing; this assertion would be vacuous"

    offences: list[str] = []
    for path in modules:
        tree = ast_for_path(path)
        assert tree is not None, f"{repo_relative(path)} must be parseable"
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and leaf_name(node.func) in _EVENT_EMISSION_CALLS:
                offences.append(f"{repo_relative(path)}:{node.lineno}: calls {leaf_name(node.func)}")
    assert offences == [], (
        "classification writes and bucket-event history belong on the CORE side of the "
        f"inference division, never inside the optional subpackage. Offences: {offences}"
    )


def test_core_run_health_diagnostics_does_not_depend_on_the_optional_subpackage() -> None:
    """S43's line: the run-health verb stays unconditional.

    ``application/diagnostics_run_health.py`` is a core, non-ledger consumer of
    LLM run telemetry. That telemetry store deliberately stayed on the core
    side of the division precisely so this verb keeps working on an install
    that never enables inference. If this module reached into the subpackage,
    a bare install would raise instead of reporting run health.

    Asserted on the import graph rather than by running the verb, because the
    failure being prevented is a *dependency* acquired at import time -- which a
    runtime test on a machine that happens to have everything installed would
    not surface.
    """
    tree = ast_for_path(_RUN_HEALTH)
    assert tree is not None, f"{repo_relative(_RUN_HEALTH)} must be parseable"

    reaches: list[str] = []
    for node in ast.walk(tree):
        # `adapters.outbound.llm` is the CORE-side store package and is fine;
        # the bare `llm` top-level package is the optional one and is not.
        parts = node.module.split(".") if isinstance(node, ast.ImportFrom) and node.module else []
        if "llm" in parts and "adapters" not in parts:
            reaches.append(f"line {node.lineno}: from {node.module}")
        if isinstance(node, ast.Import):
            reaches.extend(
                f"line {node.lineno}: import {alias.name}"
                for alias in node.names
                if alias.name.startswith("cadrumo.llm")
            )
    assert reaches == [], (
        "core run-health diagnostics must not import the optional inference subpackage; "
        f"it reads run telemetry from the core-side store instead. Reaches: {reaches}"
    )
