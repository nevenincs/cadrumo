"""``value_kind`` is a parse directive; ``enum`` claims nothing about values.

Four ``declaracion_pdf`` targets declare ``value_kind = "enum"`` over a casilla
whose ``data_type`` is ``text`` or ``integer``, and whether that is a defect or
documentation was open: the schema enforces no distinction between ``enum``
and ``text``, which is exactly what made the status arguable. (Estate-wide the
count is eight, measured 2026-07-28 through the authority; the other four are
``export_record`` targets whose ``value_kind`` no consumer reads at all.)

Measured rather than argued, the answer is that ``value_kind`` is a parse
directive and not a type declaration. Production reads it in three places and
every one branches on ``amount``: the classifier picks Spanish-decimal parsing
plus the blank-box guard for ``amount`` and carries the raw token otherwise;
the hit-finder routes ``named_label`` amounts through the word-level
positional pass; the page-word prepass decides whether a profile needs word
extraction at all. Nothing distinguishes ``enum`` from ``text``, and nothing in
the schema declares the permitted members of any enumeration, so ``enum``
makes no claim that could be checked.

So those targets are documentation, not defects, and comparing ``value_kind``
against ``data_type`` for coherence is a category error -- the first says how to
read a printed token, the second says what the casilla holds.

This module pins the ruling as behaviour rather than prose. If someone later
makes ``enum`` load-bearing, the identity assertions below fail and force the
prerequisite the ruling names: declare the value space first, because a
constraint whose members nobody can enumerate cannot be enforced.

See Also:
    :class:`~domain.calculations.registry.ExtractionTargetDefinition`
        Carries the ruling and the condition for revisiting it.
"""

from __future__ import annotations

from typing import Literal, get_args

import pytest

from .....core.casilla_id import validated_casilla_id
from .....domain.calculations.registry.schema_extraction import ExtractionTargetDefinition
from ..parser import _classify_target

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]

_PAGES: tuple[str, ...] = ("Declaracion de: ORDINARIA\nEjercicio: 2024\n",)

_LABEL = r"Declaracion\s+de:"


def _target(value_kind: Literal["amount", "text", "enum"]) -> ExtractionTargetDefinition:
    """A named_label target differing from its sibling only in ``value_kind``."""
    return ExtractionTargetDefinition(
        casilla_id=validated_casilla_id("decl.tipo-declaracion", surface="value-kind contract probe"),
        match_strategy="named_label",
        value_kind=value_kind,
        label_pattern=_LABEL,
    )


def _classify(value_kind: Literal["amount", "text", "enum"]):
    return _classify_target(
        _target(value_kind),
        pages=_PAGES,
        pages_words=None,
        numeric_anchors={},
        printed_box_numbers={},
    )


def test_enum_and_text_targets_classify_identically() -> None:
    """The parser draws no distinction between ``enum`` and ``text``.

    Two targets identical but for ``value_kind`` must produce the same
    classification and the same captured value over the same page text. This is
    the ruling's operative content: ``enum`` is a refinement of ``text`` that
    changes no behaviour.
    """
    as_text = _classify("text")
    as_enum = _classify("enum")

    assert as_text.value is not None, "the probe page must yield a hit for the contract to mean anything"
    assert as_enum.value is not None
    assert as_enum.value.printed_value == as_text.value.printed_value
    assert as_enum.value.printed_value == "ORDINARIA", (
        f"a non-amount target carries the captured token through unchanged; got {as_enum.value.printed_value!r}"
    )


def test_amount_is_the_one_value_kind_that_changes_behaviour() -> None:
    """The directive's only real branch is amount versus everything else.

    Without this, the identity above would also hold for a checker that ignored
    ``value_kind`` entirely, and the test would prove nothing about where the
    single branch lies. ``ORDINARIA`` is not a Spanish decimal, so requesting
    ``amount`` over the same page must diverge -- classifying malformed where
    the text and enum readings both captured a value.
    """
    as_amount = _classify("amount")

    assert as_amount.value is None, "an amount reading of a non-numeric token must not yield a value"
    assert as_amount.malformed is not None, (
        "an unparseable amount classifies malformed; if this stops holding, the "
        "amount branch has moved and the enum/text identity above is no longer "
        "evidence that amount is the sole discriminating value_kind"
    )


def test_no_value_kind_carries_a_declared_value_space() -> None:
    """``enum`` is unenforceable because no member list exists to enforce.

    The ruling rests on there being no declared value space anywhere on the
    target model. If a field carrying enumeration members is added later, this
    fails and the ruling must be revisited rather than silently outlived: at
    that point ``enum`` would be a checkable claim and the four flagged targets
    would need adjudicating against real AEAT values.
    """
    fields = set(ExtractionTargetDefinition.model_fields)

    assert not (fields & {"enum_values", "allowed_values", "value_space", "members", "choices"}), (
        "ExtractionTargetDefinition now declares an enumeration member list, so "
        f"value_kind='enum' may no longer be a mere hint; fields are {sorted(fields)}"
    )


def test_the_value_kind_vocabulary_is_the_one_this_ruling_adjudicated() -> None:
    """A new ``value_kind`` member would fall outside the ruling's scope.

    The ruling covers exactly ``amount``, ``text`` and ``enum``. A fourth member
    added later would inherit neither the "parse directive" reading nor the
    identity contract by default, so it must be adjudicated on its own terms.
    """
    declared = set(get_args(ExtractionTargetDefinition.model_fields["value_kind"].annotation))

    assert declared == {"amount", "text", "enum"}, (
        f"value_kind vocabulary changed to {sorted(declared)}; the enum-is-a-hint "
        "ruling was made against {'amount', 'text', 'enum'} and does not "
        "automatically extend to a new member"
    )
