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

The population is DERIVED from the registry, never pinned. Modelo 200 and 202 were
the original one -- the wording defect reached the Sociedades forms -- and both now
DECLARE the read surface, because an authenticated register-discovery run found
AEAT's own modelo combobox offering them. A pinned pair would have gone silently
vacuous at that moment: the planner stops refusing, so there is no message left to
inspect and every assertion below passes over an empty loop. Deriving the set and
refusing an empty one keeps the property under test rather than the fixture.
"""

from __future__ import annotations

import pytest

from ....domain.calculations.registry import bundled_authority
from ..filed_data_capture import _filed_capture_unsupported_reason, _plan_filed_capture_queries

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

#: How many derived modelos to assert over. The property is identical for each, so
#: the cap buys runtime without weakening it, and the derivation is sorted so the
#: sample is deterministic rather than dependent on registry iteration order.
_SAMPLE_SIZE = 8


def _modelos_declaring_no_read_surface() -> tuple[str, ...]:
    """Return registry modelos that carry a 2024 revision but declare no read surface.

    A modelo with no revision for the year is excluded: its refusal is about
    corpus coverage and says nothing about a read surface, so it would not
    exercise the wording this module gates.
    """
    derived = sorted(
        modelo_id
        for modelo in bundled_authority().modelos
        if (reason := _filed_capture_unsupported_reason(modelo=(modelo_id := str(modelo.id)), year=2024)) is not None
        and "no revision" not in reason
    )
    assert derived, (
        "every registry modelo now declares a filed-declarations read surface, so this module "
        "asserts over an empty population and proves nothing -- retire it or re-scope it"
    )
    return tuple(derived[:_SAMPLE_SIZE])


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


def test_the_refusal_claims_nothing_about_what_aeat_offers() -> None:
    """The message states our registry's silence, never AEAT's coverage.

    Asserted over every message the planner produced rather than one, so a second
    refusal path growing the same claim is caught too.
    """
    for modelo in _modelos_declaring_no_read_surface():
        messages = _unsupported_rows(modelo)
        assert messages, f"the planner produced no refusal for modelo {modelo}, so this proves nothing"

        for message in messages:
            lowered = message.lower()
            offending = [claim for claim in _AEAT_COVERAGE_CLAIMS if claim in lowered]
            assert not offending, (
                f"refusal for modelo {modelo} asserts {offending} about AEAT's coverage, which is only "
                f"a fact about this registry's silence: {message!r}"
            )


def test_the_refusal_says_what_is_true_and_what_the_operator_can_do() -> None:
    """Accuracy alone is not enough: an unactionable refusal is its own defect.

    The message must name the real reason, which is this deployment's own missing
    declaration, and name the read that would settle the open question. The verb
    cited is checked for existence by the suggestion-command conformance gate, so
    this asserts the citation is present rather than re-checking it resolves.
    """
    for modelo in _modelos_declaring_no_read_surface():
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
