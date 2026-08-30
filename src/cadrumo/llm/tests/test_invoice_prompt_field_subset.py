"""The extraction prompt can be asked for fewer fields, and refuses a bad ask.

The compiler emitted all declared field contracts on every call: ``_field_lines``
took no arguments and neither entry point accepted a selection. A fewer-fields
arm of a measurement could not be expressed at all -- not measured badly, but
inexpressible.

Two properties matter more than the parameter itself.

**The full-set output must be unchanged.** An existing baseline was measured
through this compiler, so a default that reorders or reshapes the prompt
silently invalidates comparability with everything already recorded. That is
asserted byte-for-byte here rather than structurally: a structural check passes
on a prompt whose field ordering moved, which is exactly the change that would
make two measurements incomparable while looking equivalent.

**A bad selection must refuse.** A name the declaration does not carry, dropped
silently, emits a SHORTER prompt that still renders -- and a measurement taken
against a prompt missing a contract nobody noticed is worse than no measurement,
because it carries the authority of a number.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ...core.period import Period
from ..invoice_extraction_prompt import (
    build_invoice_extraction_prompt,
    render_invoice_extraction_prompt,
    selected_invoice_field_contracts,
)
from ..invoice_field_contract import INVOICE_FIELD_CONTRACTS

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PERIOD = Period.from_year_and_code(2024, "1T")
_DECLARED = tuple(contract.field_name for contract in INVOICE_FIELD_CONTRACTS)


def _emitted_field_count(text: str) -> int:
    """Return how many field contracts the rendered prompt actually enumerates.

    Counted off the emitted text rather than off the argument, because the
    defect this guards against is a selection that is accepted and then ignored.
    A test asserting only that the call succeeded would pass against a compiler
    that always emits the full set.
    """
    block = text.split("Fields:\n", 1)[1].split("\n\nAnchors:", 1)[0]
    return len([line for line in block.splitlines() if line.startswith("- ")])


def test_the_default_prompt_is_byte_identical_to_the_unselected_one() -> None:
    """No selection and the complete selection must produce the same bytes.

    The comparability guarantee. If these ever diverge, every measurement taken
    before the parameter existed is incomparable with every one taken after,
    and nothing about the prompt would look wrong.
    """
    default = build_invoice_extraction_prompt(period=_PERIOD)
    complete = build_invoice_extraction_prompt(period=_PERIOD, fields=_DECLARED)

    assert default.text == complete.text
    assert default.fingerprint == complete.fingerprint


def test_the_full_prompt_still_carries_every_declared_contract() -> None:
    """The positive control: the whole set survives the parameter's arrival."""
    prompt = build_invoice_extraction_prompt(period=_PERIOD)

    assert _emitted_field_count(prompt.text) == len(INVOICE_FIELD_CONTRACTS)


@pytest.mark.parametrize("size", (1, 3, 7))
def test_a_subset_emits_exactly_that_many_contracts(size: int) -> None:
    """The capability itself, asserted on the emitted count rather than the call.

    A parameter accepted and ignored yields a green suite and a full prompt, so
    the count is what proves the window opened.
    """
    prompt = build_invoice_extraction_prompt(period=_PERIOD, fields=_DECLARED[:size])

    assert _emitted_field_count(prompt.text) == size
    assert len(prompt.text) < len(build_invoice_extraction_prompt(period=_PERIOD).text)


def test_both_entry_points_honour_the_same_selection() -> None:
    """A selection one entry point accepts and the other ignores is worse than neither.

    ``build`` resolves authority values and delegates, so the two must agree by
    construction -- this asserts the delegation actually carries the argument.
    """
    from ...application.ledger.invoice_extraction_authority import resolve_invoice_extraction_authority_values

    chosen = _DECLARED[:4]
    built = build_invoice_extraction_prompt(period=_PERIOD, fields=chosen)
    rendered = render_invoice_extraction_prompt(
        values=resolve_invoice_extraction_authority_values(period=_PERIOD),
        fields=chosen,
    )

    assert rendered.text == built.text


def test_the_selection_is_order_independent() -> None:
    """Two arms passing one set differently ordered must get one prompt.

    Otherwise a measurement could differ by argument order alone, which is a
    difference nobody would think to control for.
    """
    forward = build_invoice_extraction_prompt(period=_PERIOD, fields=_DECLARED[:5])
    reversed_order = build_invoice_extraction_prompt(period=_PERIOD, fields=tuple(reversed(_DECLARED[:5])))

    assert forward.text == reversed_order.text


@pytest.mark.parametrize(
    "selection",
    ((), ("not_a_declared_field",), ("not_a_declared_field", "also_not_one")),
)
def test_a_selection_the_declaration_cannot_satisfy_is_refused(selection: tuple[str, ...]) -> None:
    """Refusing, never silently emitting a shorter prompt.

    The empty case is refused on the same terms the period path fails closed on
    an empty rate set: a prompt asking for nothing is not a smaller prompt.
    """
    with pytest.raises(ValueError) as caught:
        build_invoice_extraction_prompt(period=_PERIOD, fields=selection)

    message = str(caught.value)
    assert _DECLARED[0] in message, "the refusal must name the accepted set, or it cannot be acted on"


def test_a_partly_valid_selection_is_refused_whole() -> None:
    """One bad name refuses the call; it does not quietly yield the good ones.

    Emitting the valid remainder is the silent-shortening failure wearing a
    friendlier face: the caller asked for N fields and would receive N-1 with
    nothing raised.
    """
    with pytest.raises(ValueError):
        build_invoice_extraction_prompt(period=_PERIOD, fields=(_DECLARED[0], "not_a_declared_field"))


def test_the_selector_returns_declaration_order_whatever_it_is_given() -> None:
    """The ordering guarantee at its own seam, not only through the prompt."""
    chosen = _DECLARED[:6]

    assert selected_invoice_field_contracts(tuple(reversed(chosen))) == selected_invoice_field_contracts(chosen)
    assert selected_invoice_field_contracts(None) == INVOICE_FIELD_CONTRACTS


def test_a_subset_is_not_a_route_around_the_empty_rate_refusal() -> None:
    """A period with no in-force rates must refuse whether or not fields are selected.

    The fail-closed path guards a prompt that would enumerate no rate at all.
    A selection narrows which FIELDS are asked for and must not narrow the
    regulatory values the prompt is required to carry.
    """
    unpriced = Period.from_year_and_code(1990, "1T")

    with pytest.raises(ValidationError) as full_refusal:
        build_invoice_extraction_prompt(period=unpriced)
    with pytest.raises(ValidationError) as subset_refusal:
        build_invoice_extraction_prompt(period=unpriced, fields=_DECLARED[:2])

    assert type(subset_refusal.value) is type(full_refusal.value)
