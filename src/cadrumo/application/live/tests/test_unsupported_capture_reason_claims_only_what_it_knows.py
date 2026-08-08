"""The unsupported-capture refusal may not assert what AEAT does or does not offer.

Whether AEAT serves a modelo at the authenticated consulta view is not derivable
from our own registry's silence. The refusal used to open with "AEAT declarations
register does not offer modelo '200'" and only then give the real reason, so an
operator read a claim about AEAT's coverage that nothing in this tree supports and
that no recorded rationale in either the Modelo 200 or Modelo 202 registry tree
backs up.

The opposite overclaim would be no better for the operator. "Our registry declares
nothing" is accurate and unactionable, so the message must also say what they can
do about it, and the register's own modelo combobox is the authority that settles
it.

Driven through the real query planner rather than by reading the helper, because
the planner is what an operator's pull actually reaches and it is what turns the
reason into the typed failure row they see.
"""

from __future__ import annotations

import pytest

from .._filed_data_capture import _plan_filed_capture_queries

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

#: Modelos the declarations register is not declared to serve. Both are Sociedades
#: forms, which is the population the wording defect actually reached.
_UNDECLARED_MODELOS = ("200", "202")

#: Phrases asserting a fact about AEAT's coverage. A refusal grounded in our own
#: registry may not claim any of them.
_AEAT_COVERAGE_CLAIMS = (
    "does not offer",
    "does not serve",
    "aeat does not",
    "not offered by aeat",
)


def _unsupported_rows(modelo: str) -> tuple[str, ...]:
    """Return the planner's own refusal messages for one modelo."""
    _, failures = _plan_filed_capture_queries((modelo,), year_from=2024, year_to=2025)
    return tuple(row.message for row in failures)


@pytest.mark.parametrize("modelo", _UNDECLARED_MODELOS)
def test_the_refusal_claims_nothing_about_what_aeat_offers(modelo: str) -> None:
    """The message states our registry's silence, never AEAT's coverage.

    Asserted over every message the planner produced rather than one, so a second
    refusal path growing the same claim is caught too.
    """
    messages = _unsupported_rows(modelo)
    assert messages, f"the planner produced no refusal for modelo {modelo}, so this proves nothing"

    for message in messages:
        lowered = message.lower()
        offending = [claim for claim in _AEAT_COVERAGE_CLAIMS if claim in lowered]
        assert not offending, (
            f"refusal for modelo {modelo} asserts {offending} about AEAT's coverage, which is only "
            f"a fact about this registry's silence: {message!r}"
        )


@pytest.mark.parametrize("modelo", _UNDECLARED_MODELOS)
def test_the_refusal_says_what_is_true_and_what_the_operator_can_do(modelo: str) -> None:
    """Accuracy alone is not enough: an unactionable refusal is its own defect.

    The message must name the real reason, which is this deployment's own missing
    declaration, and name the read that would settle the open question. The verb
    cited is checked for existence by the suggestion-command conformance gate, so
    this asserts the citation is present rather than re-checking it resolves.
    """
    for message in _unsupported_rows(modelo):
        if "read surface" not in message:
            continue  # a different refusal shape, covered by its own reason
        assert "registry" in message.lower(), f"the refusal does not name its own cause: {message!r}"
        assert "aeat app live filed discover" in message, (
            f"the refusal leaves the operator with nothing to run: {message!r}"
        )


def test_a_declared_modelo_is_not_refused_at_all() -> None:
    """The control. Without it, a refusal that fired on everything would pass above.

    Modelo 303 declares the read surface, so the planner must queue it rather than
    divert it, and no refusal message exists to inspect.
    """
    pairs, failures = _plan_filed_capture_queries(("303",), year_from=2024, year_to=2025)

    assert pairs, "modelo 303 declares the read surface and must be queued for capture"
    assert not [row for row in failures if "read surface" in row.message], (
        f"modelo 303 was refused for a missing read surface it declares: {[r.message for r in failures]}"
    )
