"""Which Workspace payload fields are declared but never actually filled.

A field with a default can be omitted at every construction site and still
validate, so it is invisible: the model documents a capability the payload
never carries, and no test fails because nothing asserted a value that was
never promised. This walks the declarations and every construction across the
source tree and reports the difference.

TWO EXCLUSIONS, both of which the manual measurement had to learn and either
of which turns the result to noise if forgotten.

A ``Literal``-annotated field with a default is a DISCRIMINATOR -- the contract
version, the union tag -- and is filled BY its default at every construction by
design. Counting those put the first draft of this scan at 57 findings against
a true 11, which would have buried the real ones.

``_WorkspaceModel`` is the shared base of every payload class and is never
constructed at all, so it is not a finding; it is the base class doing its job.

THE SELF-VOUCHING TRAP is why construction sites are read from everywhere
EXCEPT the declaring module. A dead cluster inside that module constructs its
own members, so counting those would let the cluster vouch for itself and the
never-constructed set collapses to almost nothing.

Construction is counted through keyword arguments AND through the string keys
of a dict passed to ``model_validate``, because both are real ways a payload
gets built and a scan that saw only one would report a filled field as unfilled.

WHAT THIS CANNOT SEE, stated because the findings it produces look identical to
real ones. A model built through a type passed as a PARAMETER -- the generic
factory shape, ``def build(model_type: type[T]) -> T: return model_type(...)``
-- carries no model name at its call site, so every field it supplies reads as
unsupplied. Recognising it needs dataflow this does not do. The bounded facet
is exactly that shape and its three pagination fields ARE filled in production.

So a finding here is a CANDIDATE, not a verdict. The register that consumes it
records which candidates are real and which the scan simply cannot reach, and
that division is the point: a scan good enough to need no adjudication would
not need a register, and one whose gaps go unrecorded turns its own blind spots
into work items.

TESTS DO NOT COUNT AS FILLING, and the scope is deliberate rather than
convenient. The question this answers is whether the PAYLOAD an operator
receives carries the field; a fixture constructing it proves the model accepts
a value, not that anything ever produces one. Counting tests would mark a field
filled on the strength of the test written to describe the gap.

That choice is what the manual walk this replaces could not make explicitly,
and it moved the number: three bounded-facet fields are constructed by a
generic in a test and by nothing in production.
"""

from __future__ import annotations

import ast
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import override

__all__ = [
    "UnfilledField",
    "scan_unfilled_workspace_fields",
]


@dataclass(frozen=True, slots=True)
class UnfilledField:
    """One optional field no construction site anywhere ever supplies."""

    model: str
    field: str

    @override
    def __str__(self) -> str:
        """Render the finding as the address a reader would search for."""
        return f"{self.model}.{self.field}"


def _constructed_name(func: ast.expr, known: set[str]) -> str | None:
    """The model being constructed by this call, through a generic or not.

    A generic payload is built as ``Model[Record](...)``, whose callee is a
    SUBSCRIPT rather than a name. Matching only bare names misses every such
    construction, and the consequence is not a missed detail: the type reads as
    never constructed, so all of its optional fields are reported unfilled at
    once. That is three findings standing for one non-finding, which is how a
    scan loses the reader's trust.
    """
    if isinstance(func, ast.Name) and func.id in known:
        return func.id
    if isinstance(func, ast.Subscript) and isinstance(func.value, ast.Name) and func.value.id in known:
        return func.value.id
    return None


def _declared_fields(models_module: Path) -> dict[str, dict[str, bool]]:
    """Return each model's optional, non-discriminator field names."""
    tree = ast.parse(models_module.read_text(encoding="utf-8"))
    declared: dict[str, dict[str, bool]] = {}
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        fields: dict[str, bool] = {}
        for statement in node.body:
            if not isinstance(statement, ast.AnnAssign) or not isinstance(statement.target, ast.Name):
                continue
            has_default = statement.value is not None
            is_discriminator = ast.unparse(statement.annotation).startswith("Literal[")
            if has_default and not is_discriminator:
                fields[statement.target.id] = True
        if fields:
            declared[node.name] = fields
    return declared


def _supplied_fields(source_root: Path, models_module: Path, known: set[str]) -> dict[str, set[str]]:
    """Return, per model, every field name some construction site supplies."""
    supplied: dict[str, set[str]] = defaultdict(set)
    for path in source_root.rglob("*.py"):
        if path == models_module or "tests" in path.parts:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError, UnicodeDecodeError):
            # A file that is unreadable, or half-written by another lane, is not
            # evidence about fields; skipping it can only over-report, never
            # under-report. The walk can list a path the read no longer reaches,
            # and that is the same non-evidence, not a reason to lose the run.
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            constructed = _constructed_name(node.func, known)
            if constructed is not None:
                supplied[constructed].update(keyword.arg for keyword in node.keywords if keyword.arg)
            if (
                isinstance(node.func, ast.Attribute)
                and node.func.attr == "model_validate"
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id in known
                and node.args
                and isinstance(node.args[0], ast.Dict)
            ):
                supplied[node.func.value.id].update(
                    key.value
                    for key in node.args[0].keys
                    if isinstance(key, ast.Constant) and isinstance(key.value, str)
                )
    return supplied


def scan_unfilled_workspace_fields(source_root: Path, models_module: Path) -> tuple[UnfilledField, ...]:
    """Return every optional field the tree declares and never supplies."""
    declared = _declared_fields(models_module)
    supplied = _supplied_fields(source_root, models_module, set(declared))
    return tuple(
        sorted(
            (
                UnfilledField(model=model, field=field)
                for model, fields in declared.items()
                if model != "_WorkspaceModel"
                for field in fields
                if field not in supplied.get(model, set())
            ),
            key=str,
        )
    )
