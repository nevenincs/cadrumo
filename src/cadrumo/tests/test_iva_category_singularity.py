"""IVA-category singularity gate: one deciding surface on the ingestion path.

The document-ingestion package (:mod:`cadrumo.application.ledger`) reads an
invoice, confirms it, and mints a catalogue record. Exactly ONE module in it may
decide that record's :class:`~domain.iva.IvaCategory`:
:data:`CANONICAL_CATEGORY_AUTHORITY`, which assembles the rule table's criteria,
consults :func:`~domain.iva.classify_iva`, and weighs the verdict against the
document's own declared code.

The hazard this gate pins is historical and concrete, and it is filing-grade
rather than stylistic. Two rival deriving surfaces once sat on the live confirm
flow ahead of that authority and reached it never. One read the document's
UNTDID 5305 tax-category code straight into a category. The other re-derived a
domestic category from the declared rate through
:func:`~domain.iva.domestic_categories_by_rate_kind` — the exact mapping the
rule table's own ``R05`` row consults, so it was a second copy of a decision
the table already owned. Meanwhile the criteria assembly that feeds the table
had no production caller at all. The state was the inverse of the ruling: the
sanctioned authority was unreachable and two unsanctioned ones were live.

What that costs is not code tidiness. A domestic reverse charge, an exempt
supply and a zero-rated supply all print a base and no cuota, so the surfaces
deciding between them decide whether the self-assessed output IVA a reverse
charge obliges is ever assessed — and Modelo 303 collects that in its own
inversión del sujeto pasivo tier. Two surfaces answering it independently can
disagree with no one detecting the disagreement.

Three rules, recomputed from the real ``ast`` module every run against the
production tree (test modules excluded), with NO stored baseline, NO
per-violation allowlist, and NO hardcoded count as a pass condition — each rule
gates on the property, so a new module joins the sweep on the day it is written:

1. **Construction.** ``IvaCategory(...)`` is called only inside the authority.
   Building a category from a document token is deciding what the operation's
   treatment is, and that is the authority's question.
2. **Annotated verdict.** No function outside the authority declares a return
   annotation naming ``IvaCategory``. This is the rule that catches the shape
   the deleted rate deriver actually had: it never named ``IvaCategory`` in its
   body at all, reaching a category purely through a mapping call, so rule 1
   walked straight past it and only its signature gave it away.
3. **Authority reach.** No module outside the authority calls a shipped
   category-producing authority (:data:`CATEGORY_PRODUCING_CALLABLES`).
   Reaching ``classify_iva`` or either direction of the domestic
   category/rate-tier mapping from the ingestion package IS a rival classifier
   by construction, whatever it is named and however it is annotated. This is
   the rule with no annotation escape.

Residual limits, stated rather than papered over
------------------------------------------------
* An **unannotated** function that reaches a category through a first-party
  helper this gate does not name is invisible to all three rules. Rule 3
  narrows that to helpers outside :data:`CATEGORY_PRODUCING_CALLABLES`, and the
  category-producing surface in ``domain.iva`` is small and facade-exported, so
  a new one would be added here with it — but that is author discipline, not
  enforcement.
* A module string built at runtime and fed to ``importlib.import_module`` is
  not an import statement and no static walk can see its target. This is the
  documented structural limit of AST scanning across this tree's gates.

Scope is the DOCUMENT-ingestion package deliberately. The bank-transaction LLM
lane, the persisted-model field coercion in ``domain.invoices`` and the
registry regulation parser in ``domain.iva`` each build a category from data
that is already a category, on paths a document confirm never reaches; folding
them in would make the rules unusable without telling anyone anything.

Every detector is a pure function over ``(display path, tree)`` so the
discrimination tests below can feed each one the drift it exists to catch and
prove it fires. A gate that cannot fail is worse than no gate.
"""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING

import pytest

from ._inventory import SRC_CADRUMO, aeat_relative, production_ast_items, repo_relative

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path


INGESTION_PACKAGE = "application/ledger/"
"""The document-ingestion package this gate governs, as an aeat-relative prefix."""

CANONICAL_CATEGORY_AUTHORITY = "application/ledger/classification_assembly.py"
"""The sole module that may decide an ingested record's IVA category.

It assembles the rule table's criteria, refuses when an input is unestablished,
consults :func:`~domain.iva.classify_iva`, and adjudicates that verdict against
the document's own declared tax-category code. Every other module on the
ingestion path consumes its answer.
"""

CATEGORY_TYPE = "IvaCategory"

CATEGORY_PRODUCING_CALLABLES = frozenset(
    {
        "classify_iva",
        "classify_from_assembled_criteria",
        "domestic_categories_by_rate_kind",
        "rate_kind_for_domestic_category",
    },
)
"""Shipped callables that answer "which IVA category / which rate tier".

``classify_iva`` is the rule table itself and ``classify_from_assembled_criteria``
is its one sanctioned wrapper. The two mapping accessors are the closed
rate-tier/domestic-category correspondence in both directions — the rule table's
``R05`` row applies it, and the deleted rate deriver copied it.
"""


def _is_the_authority(path: Path) -> bool:
    """Whether *path* is the sanctioned category authority."""
    return aeat_relative(path) == CANONICAL_CATEGORY_AUTHORITY


def _on_the_ingestion_path(path: Path) -> bool:
    """Whether *path* is a production module of the document-ingestion package."""
    return aeat_relative(path).startswith(INGESTION_PACKAGE)


def _names_the_category_type(node: ast.AST) -> bool:
    """Whether an annotation expression names :class:`IvaCategory` anywhere inside it.

    Walks the whole expression rather than matching a spelling, so
    ``IvaCategory``, ``IvaCategory | None``, ``tuple[IvaCategory, ...]`` and a
    stringised ``"IvaCategory | None"`` all resolve alike. A deriver that hid
    behind ``from __future__ import annotations`` would otherwise be a string
    constant no ``ast.Name`` walk sees.
    """
    for child in ast.walk(node):
        if isinstance(child, ast.Name) and child.id == CATEGORY_TYPE:
            return True
        if isinstance(child, ast.Attribute) and child.attr == CATEGORY_TYPE:
            return True
        if isinstance(child, ast.Constant) and isinstance(child.value, str) and CATEGORY_TYPE in child.value:
            return True
    return False


def category_construction_violations(display_path: str, tree: ast.AST, *, is_authority: bool) -> list[str]:
    """Return rule-1 violations: an ``IvaCategory(...)`` construction off the authority."""
    if is_authority:
        return []
    return [
        f"{display_path}:{node.lineno}: constructs {CATEGORY_TYPE}(...); building a category from a "
        f"document token decides the operation's treatment, which is owned by {CANONICAL_CATEGORY_AUTHORITY}"
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == CATEGORY_TYPE
    ]


def category_verdict_signature_violations(display_path: str, tree: ast.AST, *, is_authority: bool) -> list[str]:
    """Return rule-2 violations: a function outside the authority returning an ``IvaCategory``.

    A function whose declared answer IS a category is a classifier by
    signature, whether or not its body ever names the type — which is exactly
    how the deleted rate deriver evaded a construction walk.
    """
    if is_authority:
        return []
    return [
        f"{display_path}:{node.lineno}: {node.name!r} returns {ast.unparse(node.returns)}; deciding an "
        f"ingested record's IVA category is owned by {CANONICAL_CATEGORY_AUTHORITY}"
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
        and node.returns is not None
        and _names_the_category_type(node.returns)
    ]


def category_authority_reach_violations(display_path: str, tree: ast.AST, *, is_authority: bool) -> list[str]:
    """Return rule-3 violations: a call into a shipped category-producing authority.

    Matches the callee's leaf name, so ``classify_iva(...)``,
    ``iva.classify_iva(...)`` and a re-exported spelling all resolve. An alias
    (``from ... import classify_iva as _classify``) is not resolved: rule 2
    still catches the aliasing function if it declares its answer honestly, and
    rule 1 catches it if it builds the value itself.
    """
    if is_authority:
        return []
    violations: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        callee = node.func
        name = callee.id if isinstance(callee, ast.Name) else callee.attr if isinstance(callee, ast.Attribute) else None
        if name in CATEGORY_PRODUCING_CALLABLES:
            violations.append(
                f"{display_path}:{node.lineno}: calls {name!r}; reaching a category-producing authority "
                f"from the ingestion package is a rival classifier. Route through "
                f"{CANONICAL_CATEGORY_AUTHORITY}"
            )
    return violations


def _ingestion_modules(source_tree_ast: Mapping[Path, ast.AST]) -> tuple[tuple[Path, ast.AST], ...]:
    return tuple((path, tree) for path, tree in production_ast_items(source_tree_ast) if _on_the_ingestion_path(path))


def test_the_canonical_category_authority_is_present() -> None:
    """Anti-vacuity: every rule keys off an authority module that must exist.

    Were the assembly renamed or moved, all three rules would scan a package
    with no sanctioned owner — silently green while enforcing nothing, because
    the exemption would simply never apply and the tree would have to be clean
    for a different reason. This pins the anchor.
    """
    present = {aeat_relative(path) for path, _ in production_ast_items()}

    assert CANONICAL_CATEGORY_AUTHORITY in present, (
        f"expected the sanctioned IVA-category authority to exist under src/cadrumo/; "
        f"{CANONICAL_CATEGORY_AUTHORITY} was not found"
    )


def test_the_authority_really_decides_a_category(source_tree_ast: Mapping[Path, ast.AST]) -> None:
    """Anti-vacuity: the exempted module must actually be the deciding surface.

    The three rules exempt exactly one module. Were that module to stop
    deciding categories — the decision quietly moved elsewhere while the name
    stayed — the rules would keep exempting an empty shell and the tree would
    read green with the authority hollowed out. Asserting the authority carries
    BOTH halves of the decision (it builds a category from a document token,
    and it consults the rule table) is what makes the exemption earned.
    """
    authority = SRC_CADRUMO / CANONICAL_CATEGORY_AUTHORITY
    tree = source_tree_ast[authority]

    constructs = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == CATEGORY_TYPE
    ]
    reaches_the_table = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "classify_iva"
    ]

    assert constructs, f"expected {CANONICAL_CATEGORY_AUTHORITY} to build an {CATEGORY_TYPE} from a document token"
    assert reaches_the_table, f"expected {CANONICAL_CATEGORY_AUTHORITY} to consult the classify_iva rule table"


def test_only_the_authority_constructs_an_iva_category(source_tree_ast: Mapping[Path, ast.AST]) -> None:
    """Rule 1: no ingestion module outside the authority builds a category from a token."""
    violations = [
        violation
        for path, tree in _ingestion_modules(source_tree_ast)
        for violation in category_construction_violations(
            repo_relative(path), tree, is_authority=_is_the_authority(path)
        )
    ]

    assert violations == [], (
        "exactly one production surface may construct an IVA category on the ingestion path:\n" + "\n".join(violations)
    )


def test_no_rival_returns_an_iva_category(source_tree_ast: Mapping[Path, ast.AST]) -> None:
    """Rule 2: no ingestion function outside the authority declares a category as its answer."""
    violations = [
        violation
        for path, tree in _ingestion_modules(source_tree_ast)
        for violation in category_verdict_signature_violations(
            repo_relative(path), tree, is_authority=_is_the_authority(path)
        )
    ]

    assert violations == [], (
        "a function whose declared answer is an IVA category is a classifier; the ingestion path has one:\n"
        + "\n".join(violations)
    )


def test_no_rival_reaches_a_category_producing_authority(source_tree_ast: Mapping[Path, ast.AST]) -> None:
    """Rule 3: the rule table and the domestic category mapping are reached from one module."""
    violations = [
        violation
        for path, tree in _ingestion_modules(source_tree_ast)
        for violation in category_authority_reach_violations(
            repo_relative(path), tree, is_authority=_is_the_authority(path)
        )
    ]

    assert violations == [], (
        "the rule table and the rate-tier/category mapping are reached only through the assembly:\n"
        + "\n".join(violations)
    )


# --------------------------------------------------------------------------
# Discrimination: each detector is fed the drift it exists to catch, plus the
# live shapes it must NOT flag. Both halves matter — a rule that fires on
# everything is as useless as one that fires on nothing.
# --------------------------------------------------------------------------

_MINTS_FROM_A_DECLARED_CODE = """
def _category_stated_by_the_document(draft):
    stated = (draft.iva_category or "").strip()
    if not stated:
        return None
    try:
        return IvaCategory(stated)
    except ValueError:
        return None
"""

_DERIVES_FROM_THE_RATE = """
from __future__ import annotations


def _domestic_category_from_the_declared_rate(draft, *, invoice_date: date) -> IvaCategory | None:
    tiers = rate_kinds_for_declared_rate(EUMemberState.ES, draft.iva_rate / Decimal("100"), invoice_date)
    if len(tiers) != 1:
        return None
    return domestic_categories_by_rate_kind().get(tiers[0])
"""

_READS_A_PERSISTED_CATEGORY = """
_ANOMALY_IVA_REASONS: dict[IvaCategory, str] = {
    IvaCategory.UNKNOWN: "not declarable",
    IvaCategory.ERRONEOUS_INVOICE: "rectified or void",
}


def _anomaly(iva_cat) -> str | None:
    if iva_cat is IvaCategory.RECARGO_EQUIVALENCIA:
        return "recargo"
    return _ANOMALY_IVA_REASONS.get(iva_cat)
"""


def test_rule_one_fires_on_a_category_minted_from_a_document_token() -> None:
    """The first deleted rival: the UNTDID code read straight into a category."""
    violations = category_construction_violations(
        "src/cadrumo/application/ledger/evidence_draft.py",
        ast.parse(_MINTS_FROM_A_DECLARED_CODE),
        is_authority=False,
    )

    assert len(violations) == 1
    assert "constructs IvaCategory(...)" in violations[0]
    assert CANONICAL_CATEGORY_AUTHORITY in violations[0]


def test_rule_one_exempts_the_authority() -> None:
    assert (
        category_construction_violations(
            f"src/cadrumo/{CANONICAL_CATEGORY_AUTHORITY}",
            ast.parse(_MINTS_FROM_A_DECLARED_CODE),
            is_authority=True,
        )
        == []
    )


def test_rule_two_catches_the_rate_deriver_that_rule_one_cannot_see() -> None:
    """Anti-tautology proof for rule 2, and the reason rule 1 alone is insufficient.

    The second deleted rival never named ``IvaCategory`` in its body: it reached
    a category through a mapping call. Rule 1 reports it clean — asserted here
    on the same source, so the proof is that rule 2 adds reach rather than that
    two rules happen to agree.
    """
    tree = ast.parse(_DERIVES_FROM_THE_RATE)
    display = "src/cadrumo/application/ledger/evidence_draft.py"

    assert category_construction_violations(display, tree, is_authority=False) == [], (
        "guard on the proof itself: this rival builds no category, which is exactly why "
        "a construction walk cannot see it"
    )

    violations = category_verdict_signature_violations(display, tree, is_authority=False)
    assert len(violations) == 1, f"expected the signature rule to catch it; got {violations}"
    assert "_domestic_category_from_the_declared_rate" in violations[0]


def test_rule_two_sees_through_a_stringised_annotation() -> None:
    """A deriver hiding its answer behind a string annotation is still a deriver."""
    source = 'def _derive(draft) -> "IvaCategory | None":\n    return None\n'

    violations = category_verdict_signature_violations(
        "src/cadrumo/application/ledger/_x.py", ast.parse(source), is_authority=False
    )

    assert len(violations) == 1, f"expected a stringised annotation to resolve; got {violations}"


def test_rule_three_fires_on_a_reach_into_the_rule_table_and_the_mapping() -> None:
    """Both category-producing authorities are caught, from an unannotated function.

    This is the rule with no annotation escape: the function below declares no
    return type at all, so rule 2 cannot see it, and it builds nothing, so
    rule 1 cannot either.
    """
    source = """
def _rival(criteria, tier):
    if criteria is not None:
        return classify_iva(criteria).category
    return domestic_categories_by_rate_kind().get(tier)
"""
    tree = ast.parse(source)
    display = "src/cadrumo/application/ledger/_rival.py"

    assert category_construction_violations(display, tree, is_authority=False) == []
    assert category_verdict_signature_violations(display, tree, is_authority=False) == []

    violations = category_authority_reach_violations(display, tree, is_authority=False)
    assert len(violations) == 2, f"expected both authority reaches to be caught; got {violations}"
    assert any("classify_iva" in violation for violation in violations)
    assert any("domestic_categories_by_rate_kind" in violation for violation in violations)


def test_the_rules_ignore_reading_an_already_persisted_category() -> None:
    """The live preflight shape must stay green: it reads a category, it never decides one.

    Keying a mapping on category members and comparing against one is how a
    downstream consumer classifies a record that ALREADY carries a category.
    Flagging that would make the gate unusable and would say nothing about the
    duplication it exists to prevent.
    """
    tree = ast.parse(_READS_A_PERSISTED_CATEGORY)
    display = "src/cadrumo/application/ledger/preflight.py"

    assert category_construction_violations(display, tree, is_authority=False) == []
    assert category_verdict_signature_violations(display, tree, is_authority=False) == []
    assert category_authority_reach_violations(display, tree, is_authority=False) == []
