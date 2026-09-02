"""Invoice-kind singularity gate: one authority maps bank direction to issuance.

``invoice_kind_for_direction``
(:mod:`cadrumo.application.aggregation._invoice_kind`) is the single production
answer to "is this bank movement an invoice the taxpayer issued or received?".
No other production module may decide it.

The hazard is concrete and was found by a semantic sweep rather than by any
gate. Three byte-identical private copies of the mapping had accreted, in
``application/aggregation/iva_ledger.py``,
``application/aggregation/_evidence_advisory.py`` and
``application/modelo/_ledger_evidence_gate.py``, each maintained independently.
Nothing structural prevented a fourth.

What makes the duplication expensive is not the repetition itself but what it
does to the *fix*. The mapping is known to be incomplete: a supplier refund on
a returned purchase is an ``INCOMING`` movement, so it resolves to ``ISSUED``
and settles as output IVA where the correct treatment corrects input IVA. While
three copies existed, correcting that meant finding and changing all three and
keeping them in step; with one, the pending decision lands in one place. A gate
that keeps the count at one is therefore protecting a known-open correction, not
just tidiness.

This is a *policy* singularity gate, and that distinction is the point. This
codebase centralises regulatory VALUES well — the M347 threshold, for one, has a
named constant and an AST gate pinning every consumer to it — while the
DECISIONS encoded in private helpers have had no equivalent guard. Every
duplicate authority the sweep found was of the second kind. The sibling gates
``test_wizard_prompter_singularity`` and ``test_mask_profile_field_singularity``
are the established shape for closing one; this is a third instance of it.

Detection is a silhouette check over the real ``ast`` module, recomputed every
run against the production tree with NO stored baseline and NO per-violation
allowlist: a function that references BOTH ``TransactionDirection.INCOMING`` and
``InvoiceKind.ISSUED`` is deciding this mapping, whatever it is named.

The conjunction is deliberate and is what keeps the gate honest in both
directions. Matching ``InvoiceKind.ISSUED`` alone would fire on the legitimate
consumers that branch on an *already-decided* kind (``_flow_for_transaction``
and ``_row_flow`` both do, to pick a settlement flow), and a gate that fires on
correct code is one somebody eventually deletes. Requiring the direction
member too names the act of deriving the kind from the direction, which is the
thing that must happen once.

Known limits, stated rather than papered over: a copy that reaches the enum
members through an alias, or builds them dynamically, is invisible to a static
walk — the same residual the sibling gates document. The gate raises the cost of
a fourth copy; it does not make one impossible.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from ..core.directory_scan import scan_directory

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

#: The one module permitted to derive an invoice kind from a bank direction.
CANONICAL_MODULE = Path("src/cadrumo/application/aggregation/_invoice_kind.py")

#: The enum members whose co-occurrence in one function IS the mapping decision.
_DIRECTION_MEMBER = ("TransactionDirection", "INCOMING")
_KIND_MEMBER = ("InvoiceKind", "ISSUED")

_REPO_ROOT = Path(__file__).resolve().parents[3]
_PRODUCTION_ROOT = _REPO_ROOT / "src" / "cadrumo"


def _enum_member_references(node: ast.AST) -> set[tuple[str, str]]:
    """Return every ``Name.ATTR`` pair referenced anywhere beneath ``node``."""
    found: set[tuple[str, str]] = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Attribute) and isinstance(child.value, ast.Name):
            found.add((child.value.id, child.attr))
    return found


def _evaluates_to_invoice_kind(expr: ast.expr) -> bool:
    """Return whether ``expr`` evaluates to an ``InvoiceKind`` member.

    Deliberately follows the VALUE, not the whole subtree. A conditional's
    ``test`` may name ``InvoiceKind`` while the expression yields something else
    entirely — which is exactly what the reconciliation matcher does — so the
    branches are inspected and the condition is not.
    """
    if isinstance(expr, ast.Attribute) and isinstance(expr.value, ast.Name):
        return expr.value.id == _KIND_MEMBER[0]
    if isinstance(expr, ast.IfExp):
        return _evaluates_to_invoice_kind(expr.body) or _evaluates_to_invoice_kind(expr.orelse)
    if isinstance(expr, ast.BoolOp):
        return any(_evaluates_to_invoice_kind(value) for value in expr.values)
    return False


def _returns_an_invoice_kind(node: ast.AST) -> bool:
    """Return whether any ``return`` in ``node`` yields an ``InvoiceKind`` member."""
    return any(
        child.value is not None and _evaluates_to_invoice_kind(child.value)
        for child in ast.walk(node)
        if isinstance(child, ast.Return)
    )


def _decides_invoice_kind(node: ast.AST) -> bool:
    """Return whether ``node`` derives an invoice kind from a bank direction.

    Both halves are required, and the direction of the derivation matters.

    Co-occurrence alone is too loose: ``suggest_reconciliations``
    (:mod:`cadrumo.domain.invoices.service`) names both enums in one ternary,
    but it runs the correspondence BACKWARDS — it picks the bank direction an
    already-known invoice kind should reconcile against. That is the matcher's
    own question, not this mapping, and it could not delegate here even if it
    were: it lives in ``domain`` and the canonical helper lives in
    ``application``, so calling it would invert the layering. An earlier draft
    of this gate flagged it, which is recorded here so the exclusion reads as a
    judgement rather than an oversight.

    Requiring the function to RETURN an ``InvoiceKind`` names the act of
    producing one, which is the thing that must happen exactly once. It also
    keeps the gate off the legitimate consumers that branch on an
    already-decided kind to pick a settlement flow.
    """
    referenced = _enum_member_references(node)
    if _DIRECTION_MEMBER not in referenced or _KIND_MEMBER not in referenced:
        return False
    return _returns_an_invoice_kind(node)


def _production_modules() -> list[Path]:
    """Return every production module, test packages excluded."""
    return [
        path
        for path in scan_directory(_PRODUCTION_ROOT, pattern="*.py", recursive=True)
        if "tests" not in path.parts and "__pycache__" not in path.parts
    ]


def _deciding_functions(path: Path) -> list[str]:
    """Return the qualified names of functions in ``path`` deciding the mapping."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return [
        node.name
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and _decides_invoice_kind(node)
    ]


def test_the_detector_fires_on_the_canonical_implementation() -> None:
    """Positive control: the detector recognises the shape it hunts for.

    Without this, a detector that silently matched nothing — a renamed enum, a
    broken walk — would report a clean tree forever and the gate below would
    pass while saying nothing at all.
    """
    canonical = _REPO_ROOT / CANONICAL_MODULE
    assert canonical.is_file(), f"canonical module missing: {CANONICAL_MODULE}"

    assert _deciding_functions(canonical) == ["invoice_kind_for_direction"], (
        "the detector no longer recognises the canonical mapping; if the "
        "implementation moved or was renamed, retarget CANONICAL_MODULE and the "
        "member constants rather than weakening the detector"
    )


def test_a_fourth_copy_would_be_caught_and_a_legitimate_consumer_would_not() -> None:
    """Prove the discrimination on synthetic sources, not on the live tree.

    The control above shows the detector fires on the canonical implementation,
    and the gate below shows the tree is clean — but neither shows the gate
    would catch a NEW copy, because a detector that only ever matched the one
    module it is pointed at would satisfy both. Parsing the sources here rather
    than writing a fourth copy into the tree proves it without opening a window
    in which the repository actually carries one.
    """
    a_fourth_copy = """
def _kind_for(direction):
    if direction is TransactionDirection.INCOMING:
        return InvoiceKind.ISSUED
    if direction is TransactionDirection.OUTGOING:
        return InvoiceKind.RECEIVED
    return None
"""
    a_legitimate_consumer = """
def _flow(transaction, invoice_kind):
    if transaction.direction is TransactionDirection.INTERNAL_TRANSFER:
        return None
    return REPERCUTIDO if invoice_kind is InvoiceKind.ISSUED else SOPORTADO
"""
    a_reverse_matcher = """
def _expected_direction(invoice):
    return TransactionDirection.INCOMING if invoice.kind is InvoiceKind.ISSUED else TransactionDirection.OUTGOING
"""

    def deciders(source: str) -> list[str]:
        return [
            node.name
            for node in ast.walk(ast.parse(source))
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and _decides_invoice_kind(node)
        ]

    assert deciders(a_fourth_copy) == ["_kind_for"], "a hand-copied fourth mapping must be caught"
    assert deciders(a_legitimate_consumer) == [], "branching on an already-decided kind is not a second authority"
    assert deciders(a_reverse_matcher) == [], "deriving a direction FROM a kind is the matcher's own question"


def test_only_the_canonical_module_decides_the_invoice_kind() -> None:
    """No second production site derives an invoice kind from a bank direction."""
    canonical = (_REPO_ROOT / CANONICAL_MODULE).resolve()

    offenders = {
        path.relative_to(_REPO_ROOT).as_posix(): names
        for path in _production_modules()
        if path.resolve() != canonical and (names := _deciding_functions(path))
    }

    assert not offenders, (
        "these production sites decide the bank-direction to invoice-kind mapping "
        f"themselves instead of calling invoice_kind_for_direction: {offenders}. "
        "Three byte-identical copies of this mapping previously drifted apart "
        "here; route the call through the canonical helper instead of adding a "
        "fourth. The mapping has a known-open correction pending (a purchase "
        "refund is an INCOMING movement and resolves to ISSUED), and every copy "
        "is another place that correction has to land."
    )
