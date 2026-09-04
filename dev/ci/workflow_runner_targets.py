"""Resolve the concrete runner targets a workflow job schedules onto.

Two structural gates ask the same question of every workflow -- which runners
does this job actually land on -- and both used to answer it with their own
copy of a `runs-on:`/matrix reader. Both copies made the same assumption, that
`strategy.matrix` is a mapping, and both raised `AttributeError` on the first
workflow that computed its matrix at runtime. A gate that crashes proves
nothing about the document it crashed on, so the answer lives here once.

A `runs-on:` resolves three ways:

* **Literal.** A label list (`[self-hosted, Linux, X64]`) or a hosted image
  name (`ubuntu-latest`) is its own target.
* **Static matrix.** `runs-on: ${{ matrix.os }}` over a mapping matrix expands
  to the referenced dimension's values, from `include:` rows and from a
  top-level list dimension alike.
* **Runtime matrix.** `matrix: ${{ fromJSON(needs.<job>.outputs.<key>) }}` is a
  string, not a mapping: the combinations do not exist until the producing job
  has run. The reference is still followed -- to the producing job, to the step
  whose output it names, and to the runner labels that step's script emits --
  because refusing to look is not the same as checking, and a release path
  whose runner targets were never inspected is a gate in name only.

Every failure to resolve returns a sentinel rather than an empty list. Zero
targets is indistinguishable from "no violation found" to a caller that
iterates, which is precisely how an unschedulable or unauthorized runner would
pass unnoticed; the sentinels are strings that satisfy neither
:func:`is_hosted_image` nor :func:`is_fleet_label_set`, so an unresolvable
reference fails whichever direction the caller is gating.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any, Final

#: The dimension a `runs-on:` expression selects, e.g. `os` in `${{ matrix.os }}`.
_MATRIX_DIMENSION: Final = re.compile(r"matrix\.([A-Za-z_][\w-]*)")

#: The one runtime-matrix shape GitHub can expand: a whole matrix mapping
#: supplied by an upstream job's output. Anything else (an input, a literal
#: JSON blob, a nested expression) is reported unresolvable rather than guessed
#: at, because a guess here is a runner target nobody checked.
_MATRIX_FROM_JSON: Final = re.compile(
    r"^\$\{\{\s*fromJSON\(\s*needs\.(?P<job>[A-Za-z_][\w-]*)\.outputs\.(?P<output>[A-Za-z_][\w-]*)\s*\)\s*\}\}$",
)

#: A job output forwarding a step's output, the only shape a producer can use
#: to publish a matrix it computed in a script.
_STEP_OUTPUT: Final = re.compile(
    r"^\$\{\{\s*steps\.(?P<step>[A-Za-z_][\w-]*)\.outputs\.(?P<key>[A-Za-z_][\w-]*)\s*\}\}$",
)

#: A runner label written as a literal in a producer script. The vocabulary is
#: deliberately narrow -- the three GitHub-hosted image families and the
#: `self-hosted` label -- so an ordinary matrix value (a runtime id, a Python
#: version) is never mistaken for a runner target.
_RUNNER_LABEL_LITERAL: Final = re.compile(
    r"""["'](?P<label>(?:ubuntu|windows|macos)-[0-9a-z][0-9a-z.\-]*|self-hosted)["']""",
)

#: A GitHub-hosted runner image name.
_HOSTED_IMAGE: Final = re.compile(r"^(?:ubuntu|windows|macos)-[0-9a-z][0-9a-z.\-]*$")

#: Shared opening of every sentinel, so a caller can recognise one without
#: matching the prose that explains it. No runner label can collide: a label is
#: a bare name or a YAML list, never a bracketed sentence.
_UNRESOLVED_PREFIX: Final = "<matrix runs-on "

#: Returned when a matrix-referencing `runs-on:` expands to no value at all.
UNRESOLVED_ZERO_TARGETS: Final = f"{_UNRESOLVED_PREFIX}resolved to zero targets>"


def unresolvable(reason: str) -> str:
    """Return the sentinel target for a reference that cannot be resolved."""
    return f"{_UNRESOLVED_PREFIX}unresolvable: {reason}>"


def is_unresolved(target: object) -> bool:
    """Return whether ``target`` is a sentinel rather than a real runner."""
    return isinstance(target, str) and target.startswith(_UNRESOLVED_PREFIX)


def is_hosted_image(target: object) -> bool:
    """Return whether ``target`` is a GitHub-hosted runner image name."""
    return isinstance(target, str) and _HOSTED_IMAGE.fullmatch(target) is not None


def is_fleet_label_set(target: object) -> bool:
    """Return whether ``target`` is a self-hosted label set."""
    return isinstance(target, list) and bool(target) and target[0] == "self-hosted"


def runner_targets(job: Mapping[str, Any], workflow: Mapping[str, Any]) -> list[object]:
    """Return every concrete runner target ``job`` can land on.

    Args:
        job: The job mapping, as parsed from the workflow document.
        workflow: The whole workflow document, needed to follow a runtime
            matrix back to the job that produces it.

    Returns:
        One entry per resolved target, or a single sentinel string when the
        reference resolves to nothing.
    """
    runs_on = job.get("runs-on")
    if not (isinstance(runs_on, str) and "matrix" in runs_on):
        return [runs_on]
    matrix = (job.get("strategy") or {}).get("matrix")
    if isinstance(matrix, str):
        return _runtime_matrix_targets(matrix, workflow)
    dimension_match = _MATRIX_DIMENSION.search(runs_on)
    dimension = dimension_match.group(1) if dimension_match else None
    mapping: Mapping[str, Any] = matrix if isinstance(matrix, Mapping) else {}
    targets: list[object] = [
        row[dimension] for row in mapping.get("include") or [] if isinstance(row, Mapping) and dimension in row
    ]
    top_level = mapping.get(dimension)
    if isinstance(top_level, list):
        targets.extend(top_level)
    return targets or [UNRESOLVED_ZERO_TARGETS]


def _runtime_matrix_targets(expression: str, workflow: Mapping[str, Any]) -> list[object]:
    """Return the runner labels a runtime-computed matrix can carry.

    The combinations themselves are unknowable before the producing job runs,
    but the labels are not: they are written as literals in the script that
    emits the matrix, and that script is in this same document. Following the
    reference is what turns "the matrix is computed" from an excuse into an
    answer.
    """
    match = _MATRIX_FROM_JSON.fullmatch(expression.strip())
    if match is None:
        return [unresolvable(f"{expression.strip()!r} is not a fromJSON(needs.<job>.outputs.<output>) reference")]
    producer_name, output_name = match.group("job"), match.group("output")
    producer = (workflow.get("jobs") or {}).get(producer_name)
    if not isinstance(producer, Mapping):
        return [unresolvable(f"matrix producer job {producer_name!r} is not declared in this workflow")]
    output = (producer.get("outputs") or {}).get(output_name)
    step_match = _STEP_OUTPUT.fullmatch(output.strip()) if isinstance(output, str) else None
    if step_match is None:
        return [
            unresolvable(
                f"{producer_name}.outputs.{output_name} is {output!r}, "
                "not a ${{ steps.<id>.outputs.<key> }} reference",
            ),
        ]
    step_id = step_match.group("step")
    step = next(
        (candidate for candidate in producer.get("steps") or [] if isinstance(candidate, Mapping) and candidate.get("id") == step_id),
        None,
    )
    if step is None:
        return [unresolvable(f"job {producer_name!r} has no step {step_id!r} to emit the matrix")]
    labels = _runner_label_literals(str(step.get("run", "")))
    return labels or [unresolvable(f"step {step_id!r} of {producer_name!r} names no runner label literal")]


def _runner_label_literals(script: str) -> list[object]:
    """Return the runner labels ``script`` names, in first-appearance order.

    Comment lines are dropped before matching. A label named only in a comment
    is not a label the step emits, and reading one as a target would let a
    workflow be judged on prose it does not execute.
    """
    executed = "\n".join(line for line in script.splitlines() if not line.strip().startswith("#"))
    return list(dict.fromkeys(match.group("label") for match in _RUNNER_LABEL_LITERAL.finditer(executed)))
