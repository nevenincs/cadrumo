"""The classification division: inference one side, persistence the other.

``application/ledger/llm_classification.py`` mixes two concerns that the
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
    """The division line: classification writes and event history stay core-side.

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
    """The division line: the run-health verb stays unconditional.

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
        if isinstance(node, ast.ImportFrom) and node.module:
            parts = node.module.split(".")
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


def test_every_model_talking_class_lives_in_the_inference_package() -> None:
    """The inference call sites are in the subpackage, not the ledger.

    "Inference call site" means a class that TALKS TO A MODEL -- builds a
    request, sends it, parses the answer. All of them live in the gated package.
    What the ledger keeps is orchestration: resolving evidence, choosing a
    reader, calling it, and carrying the result to the confirm boundary. The
    division line is between talking to a model and deciding when to.

    The physical extraction stops there deliberately. Moving the orchestration
    too would make the subpackage import the ledger's private resolved-evidence
    type across a package boundary, which the ownership rule forbids -- and it
    would buy nothing, because the property that matters is already enforced by
    the write assertion above: the subpackage records nothing.
    """
    import ast

    from . import SRC_CADRUMO, ast_for_path, non_test_python_files_under, repo_relative

    ledger = SRC_CADRUMO / "application" / "ledger"
    package = SRC_CADRUMO / "llm"

    # A model-talking class is one that constructs an LLM request.
    def _builds_a_model_request(path) -> bool:
        tree = ast_for_path(path)
        if tree is None:
            return False
        return any(
            isinstance(node, ast.Call) and getattr(node.func, "id", None) == "LLMRequest" for node in ast.walk(tree)
        )

    in_ledger = [
        repo_relative(p) for p in non_test_python_files_under(ledger, include_data=True) if _builds_a_model_request(p)
    ]
    in_package = [
        repo_relative(p) for p in non_test_python_files_under(package, include_data=True) if _builds_a_model_request(p)
    ]

    assert in_ledger == [], f"a model request is built in the ledger; it belongs in the inference package: {in_ledger}"
    assert in_package, "the inference package must own at least one model-talking module, or this passes over nothing"


def test_the_review_workflow_does_not_import_across_the_boundary_inward() -> None:
    """The workflow settles on the ledger side of the division.

    It consumes the interchange DTOs from the owning package and the apply and
    reject functions from its own package. What it must NOT do is reach into the
    inference package for anything that performs a write, or become a second
    caller of a model -- either would put review-loop behaviour behind an
    optional install.

    Asserted on what the module imports rather than on what it happens to call,
    because the dependency is acquired at import time and that is when it would
    become conditional.
    """
    import ast

    from . import SRC_CADRUMO, ast_for_path, repo_relative

    workflow = SRC_CADRUMO / "application" / "ledger" / "llm_review_workflow.py"
    tree = ast_for_path(workflow)
    assert tree is not None, f"{repo_relative(workflow)} must be parseable"

    # Relative imports are resolved before matching, because the interesting
    # names arrive as ``from ...llm.suggestions import`` -- a submodule, so a
    # suffix test on the written module misses them -- while the ledger's own
    # ``from .llm_classification import`` would match such a test on spelling
    # alone despite belonging to this package, not the inference one.
    workflow_package = ("cadrumo", "application", "ledger")
    from_llm: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom):
            continue
        if node.level:
            base = workflow_package[: len(workflow_package) - (node.level - 1)]
            resolved = ".".join([*base, node.module]) if node.module else ".".join(base)
        else:
            resolved = node.module or ""
        if resolved == "cadrumo.llm" or resolved.startswith("cadrumo.llm."):
            from_llm.extend(alias.name for alias in node.names)

    assert from_llm, "the workflow does consume the interchange DTOs; this assertion must not pass vacuously"
    # Every name it takes from the package is a DTO. A reader, a client or a
    # store would mean the review loop had acquired an inference dependency.
    forbidden = [name for name in from_llm if name.endswith(("Classifier", "Client", "Recorder", "Cache"))]
    assert forbidden == [], (
        f"the review workflow imports {forbidden} from the inference package; it may consume the "
        "interchange contracts but must not acquire a model transport or a store"
    )
