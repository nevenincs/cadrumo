"""Masking-verdict singularity gate: one authority decides what an operator screen hides.

``mask_profile_field`` (:mod:`cadrumo.application.user_profile.overview`) is
the single masking authority for every surface that projects profile facts —
its own docstring says so, and until recently a cross-reference proved it: a
test imported both the public re-export and the private definition side by
side and asserted they were the same object, so a second definition anywhere
in the tree would have broken that identity check on sight.

That cross-reference is gone (``test_status_projection.py`` now reaches
only the public facade, correctly — a private-import is exactly what
``aeat-architecture-boundaries`` forbids), and nothing replaced
its enforcement. What is left is a docstring claim: *"there is one
``mask_profile_field``"*. A second implementation — under any name, in any
module — would leave every existing test green, because they all call the
facade one. This is the same failure mode ``test_wizard_prompter_singularity.py``
was written to catch for interactive prompting: a hand-copied decision drifts
silently because nothing structural stops a second one from existing. Read
that gate first; this one follows its idiom rather than inventing a second
style.

The masking decision has no third-party library to key on the way
questionary keys the prompter gate, so this gate pins the decision's own
SILHOUETTE instead: a function (or method) that accepts a parameter typed
``SensitivityClass | None`` and returns ``bool``. That shape is not a loose
guess — across the whole production tree exactly one function carries it
today, this module's own ``mask_profile_field``. The one other
production consumer of the same parameter name, ``default_policy_for`` in
:mod:`cadrumo.core.classification`, takes a *required* ``SensitivityClass``
(no ``None`` arm) and returns a ``ClassificationPolicy``, not a ``bool`` — it
answers a different question (which storage/at-rest policy applies) and does
not match. The ``| None`` arm is what makes the signature specific to
"decide from a classification that might not exist," which is the exact
shape of the masking decision: a classified field is decided directly, an
unclassified one falls through to the keyword net, and the whole point is a
plain yes/no whether to hide the value.

This gate does not merely check that the facade re-export still resolves —
that would only catch the canonical function disappearing, not a second one
appearing beside it. It fails when a second matching signature shows up
ANYWHERE outside the canonical module, under any name.
"""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING

import pytest

from .inventory import aeat_relative, leaf_name, production_ast_items, repo_relative

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path


MASK_PROFILE_FIELD_MODULE = "application/user_profile/overview.py"
"""The single production module allowed to declare a masking-verdict function."""

MASK_PROFILE_FIELD_NAME = "mask_profile_field"


def _is_canonical_masking_module(path: Path) -> bool:
    return aeat_relative(path) == MASK_PROFILE_FIELD_MODULE


def _annotation_is_optional_sensitivity_class(annotation: ast.expr | None) -> bool:
    """Return True for ``SensitivityClass | None`` or ``Optional[SensitivityClass]``.

    Both spellings are checked because the annotation is read from source
    text, not from a type checker; a future author reaching for
    ``typing.Optional`` instead of the shipped ``X | None`` idiom must not
    silently escape the gate.
    """
    if annotation is None:
        return False
    if isinstance(annotation, ast.BinOp) and isinstance(annotation.op, ast.BitOr):
        sides = (annotation.left, annotation.right)
        has_none = any(isinstance(side, ast.Constant) and side.value is None for side in sides)
        has_sensitivity = any(leaf_name(side) == "SensitivityClass" for side in sides)
        return has_none and has_sensitivity
    if isinstance(annotation, ast.Subscript) and leaf_name(annotation.value) == "Optional":
        return leaf_name(annotation.slice) == "SensitivityClass"
    return False


def _returns_bool(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    return node.returns is not None and leaf_name(node.returns) == "bool"


def _all_positional_and_keyword_args(node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[ast.arg]:
    return [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]


def masking_verdict_signature_violations(
    display_path: str,
    tree: ast.AST,
    *,
    is_canonical: bool,
) -> list[str]:
    """Return a violation for every masking-verdict-shaped function outside the canonical module.

    A function matches when it returns ``bool`` and carries a parameter typed
    ``SensitivityClass | None`` — the signature that says "decide whether to
    hide this value, from a classification that might be absent." Matches
    both free functions and methods (``ast.walk`` reaches class bodies too),
    since a rival could as easily be attached to a class as be a bare
    function, and the wizard-prompter precedent's rule 3 catches exactly
    that shape for its own silhouette.
    """
    if is_canonical:
        return []
    violations: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        if not _returns_bool(node):
            continue
        sensitivity_args = [
            arg
            for arg in _all_positional_and_keyword_args(node)
            if _annotation_is_optional_sensitivity_class(arg.annotation)
        ]
        if not sensitivity_args:
            continue
        violations.append(
            f"{display_path}:{node.lineno}: {node.name!r} takes {sensitivity_args[0].arg!r}: "
            "SensitivityClass | None and returns bool -- this is the masking-verdict signature. "
            f"The single masking authority is {MASK_PROFILE_FIELD_NAME}() in {MASK_PROFILE_FIELD_MODULE}"
        )
    return violations


def _production_modules(source_tree_ast: Mapping[Path, ast.AST]) -> tuple[tuple[Path, ast.AST], ...]:
    return production_ast_items(source_tree_ast)


def test_canonical_masking_module_is_present() -> None:
    """Anti-vacuity: the rule keys off a module that must exist.

    Were ``_overview.py`` renamed or moved without updating this gate, the
    scan below would silently exempt nothing (the canonical path would match
    no real module) and every OTHER module would still correctly be
    scanned — but the true canonical function itself would then also read as
    a violation, which the next test pins as the failure mode this guards.
    """
    present = {aeat_relative(path) for path, _ in production_ast_items()}
    assert MASK_PROFILE_FIELD_MODULE in present, (
        f"expected the canonical masking module to exist under src/cadrumo/; missing {MASK_PROFILE_FIELD_MODULE}"
    )


def test_the_canonical_function_itself_matches_the_signature_this_gate_pins(
    source_tree_ast: Mapping[Path, ast.AST],
) -> None:
    """Anti-vacuity: prove the detector's signature really describes the real function.

    Scans the real ``_overview.py`` content as though it were NOT the
    canonical module (``is_canonical=False``) and requires exactly one hit
    naming ``mask_profile_field``. A signature guess that does not match the
    real function would let this gate exempt the canonical module while
    catching nothing else either — the detector would be checking a shape
    that does not exist in this codebase.
    """
    canonical_path = next(
        path for path, _ in production_ast_items(source_tree_ast) if _is_canonical_masking_module(path)
    )
    tree = source_tree_ast[canonical_path]

    violations = masking_verdict_signature_violations(repo_relative(canonical_path), tree, is_canonical=False)

    assert len(violations) == 1, (
        f"expected exactly one masking-verdict signature in the canonical module; got {violations}"
    )
    assert MASK_PROFILE_FIELD_NAME in violations[0]


def test_no_masking_verdict_signature_exists_outside_the_canonical_module(
    source_tree_ast: Mapping[Path, ast.AST],
) -> None:
    """The real gate: no second masking-decision function anywhere in production code.

    This is what makes a second ``mask_profile_field`` -- reachable under any
    name, attached to any class -- structurally impossible rather than
    merely undocumented.
    """
    violations = [
        violation
        for path, tree in _production_modules(source_tree_ast)
        for violation in masking_verdict_signature_violations(
            repo_relative(path), tree, is_canonical=_is_canonical_masking_module(path)
        )
    ]

    assert violations == [], (
        "a second masking-verdict function was found outside the canonical authority "
        f"({MASK_PROFILE_FIELD_MODULE}):\n" + "\n".join(violations)
    )


# --------------------------------------------------------------------------
# Discrimination: the detector is fed the drift it exists to catch, plus the
# live shapes it must NOT flag. A gate that cannot fail pins a false green.
# --------------------------------------------------------------------------

_RIVAL_MASKING_FUNCTION = """
from ...core.classification import SensitivityClass


def should_hide_field(*, path: str, label: str, sensitivity: SensitivityClass | None) -> bool:
    if sensitivity is SensitivityClass.SECRET:
        return True
    return "token" in label.casefold()
"""

_RIVAL_MASKING_METHOD = """
from ...core.classification import SensitivityClass


class _StatusRow:
    def is_masked(self, *, sensitivity: SensitivityClass | None, label: str) -> bool:
        return sensitivity is SensitivityClass.SECRET
"""

_RIVAL_WITH_TYPING_OPTIONAL = """
from typing import Optional

from ...core.classification import SensitivityClass


def hide(sensitivity: Optional[SensitivityClass]) -> bool:
    return sensitivity is not None
"""

_UNRELATED_REQUIRED_SENSITIVITY = """
from ...core.classification import ClassificationPolicy, SensitivityClass


def default_policy_for(sensitivity: SensitivityClass) -> ClassificationPolicy:
    raise NotImplementedError
"""

_UNRELATED_BOOL_RETURN_NO_SENSITIVITY = """
def is_present(value: str | None) -> bool:
    return value is not None
"""

_UNRELATED_OPTIONAL_SENSITIVITY_NON_BOOL_RETURN = """
from ...core.classification import ClassificationPolicy, SensitivityClass


def resolve_policy(sensitivity: SensitivityClass | None) -> ClassificationPolicy | None:
    return None
"""


def _tree(source: str) -> ast.AST:
    return ast.parse(source, filename="<synthetic>")


def test_rule_fires_on_a_rival_masking_function_outside_the_canonical_module() -> None:
    violations = masking_verdict_signature_violations(
        "src/cadrumo/application/user_profile/status_projection.py",
        _tree(_RIVAL_MASKING_FUNCTION),
        is_canonical=False,
    )

    assert len(violations) == 1
    assert "should_hide_field" in violations[0]
    assert MASK_PROFILE_FIELD_MODULE in violations[0]


def test_rule_fires_on_a_rival_masking_method() -> None:
    """The silhouette reaches a class method, not only a bare function.

    A rival is as likely to be attached to a presenter/row class as to be a
    free function; ``ast.walk`` descends into class bodies, so this must
    catch a method exactly as it catches a top-level function.
    """
    violations = masking_verdict_signature_violations(
        "src/cadrumo/adapters/inbound/_rows.py",
        _tree(_RIVAL_MASKING_METHOD),
        is_canonical=False,
    )

    assert len(violations) == 1
    assert "is_masked" in violations[0]


def test_rule_fires_on_typing_optional_spelling() -> None:
    """Anti-tautology for the annotation matcher: ``Optional[X]`` must not escape it.

    The shipped codebase spells this ``X | None`` uniformly, but the gate
    must not silently trust that convention to hold forever -- a future
    author reaching for ``typing.Optional`` is exactly who this test
    protects against.
    """
    violations = masking_verdict_signature_violations(
        "src/cadrumo/adapters/inbound/_style.py",
        _tree(_RIVAL_WITH_TYPING_OPTIONAL),
        is_canonical=False,
    )

    assert len(violations) == 1
    assert "hide" in violations[0]


def test_rule_ignores_the_canonical_module() -> None:
    """The real canonical shape, scanned as the canonical module, must stay green."""
    violations = masking_verdict_signature_violations(
        MASK_PROFILE_FIELD_MODULE,
        _tree(_RIVAL_MASKING_FUNCTION),
        is_canonical=True,
    )

    assert violations == [], "the canonical module must be exempt from its own rule"


def test_rule_ignores_a_required_sensitivity_parameter() -> None:
    """``default_policy_for``'s real shape: required ``SensitivityClass``, non-bool return.

    Both arms of the signature must be present to match; a required
    (non-Optional) classification parameter answers "what policy applies to
    a KNOWN class," not "should I hide a value that might have no class at
    all" -- a different question, and this must not conflate them.
    """
    violations = masking_verdict_signature_violations(
        "src/cadrumo/core/classification/__init__.py",
        _tree(_UNRELATED_REQUIRED_SENSITIVITY),
        is_canonical=False,
    )

    assert violations == [], f"a required (non-Optional) sensitivity parameter must not match; got {violations}"


def test_rule_ignores_a_bool_return_with_no_sensitivity_parameter() -> None:
    violations = masking_verdict_signature_violations(
        "src/cadrumo/domain/user_profile/_predicates.py",
        _tree(_UNRELATED_BOOL_RETURN_NO_SENSITIVITY),
        is_canonical=False,
    )

    assert violations == [], (
        f"a bare bool-returning function with no sensitivity parameter must not match; got {violations}"
    )


def test_rule_ignores_an_optional_sensitivity_parameter_with_a_non_bool_return() -> None:
    violations = masking_verdict_signature_violations(
        "src/cadrumo/core/classification/_policy.py",
        _tree(_UNRELATED_OPTIONAL_SENSITIVITY_NON_BOOL_RETURN),
        is_canonical=False,
    )

    assert violations == [], (
        f"an Optional[SensitivityClass] parameter with a non-bool return must not match; got {violations}"
    )
