"""Cross-layer parity for the ISO 3166-1 alpha-2 source-jurisdiction shape.

The application-layer ledger command/payload models and the domain
:class:`~domain.transactions.Transaction` both carry ``source_jurisdiction``
and previously each implemented the shape check inline. Identical logic in two
places drifts silently: a change to one boundary's accepted set would not move
the other, and the jurisdiction axis selects the regulatory-source treatment
of a ledger row (Spanish-source versus foreign-source).

These tests pin that both layers accept and refuse exactly the same tokens
while each keeps its own exception boundary.
"""

from __future__ import annotations

import pytest

from ....core.errors.hierarchy import CoreValidationError
from ....core.parsing import normalise_iso_3166_alpha2_jurisdiction
from ....domain.transactions.errors import TransactionValidationError
from ....domain.transactions.models import Transaction
from ..models import _validate_iso_3166_jurisdiction

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

#: Tokens both layers must accept, with the canonical stored form.
_ACCEPTED: tuple[tuple[str | None, str | None], ...] = (
    (None, None),
    ("ES", "ES"),
    (" ES ", "ES"),
    ("\tDE\n", "DE"),
)

#: Tokens both layers must refuse. Lowercase is deliberately refused rather
#: than folded, so the caller declares the canonical code explicitly.
_REFUSED: tuple[str, ...] = ("es", "Es", "E", "ESP", "E1", "", "  ")


def _domain_jurisdiction(raw: str | None) -> str | None:
    """Run the real domain field validator in isolation."""
    return Transaction._validate_source_jurisdiction(raw)


@pytest.mark.parametrize(("raw", "expected"), _ACCEPTED)
def test_both_layers_accept_the_same_jurisdiction_tokens(raw: str | None, expected: str | None) -> None:
    """The application and domain boundaries must normalise identically.

    SUPPORTING. Both inline copies already agreed on every accepted token, so
    no parameter here flips under a drift mutation; it pins that the shared
    helper did not narrow the accepted set.
    """
    assert _validate_iso_3166_jurisdiction(raw) == expected
    assert _domain_jurisdiction(raw) == expected


@pytest.mark.parametrize("raw", _REFUSED)
def test_both_layers_refuse_the_same_jurisdiction_tokens(raw: str) -> None:
    """Neither boundary may accept a token the other refuses.

    DISCRIMINATING for the lowercase parameters (``"es"``, ``"Es"``): drifting
    the domain validator to fold case instead of refusing it makes the domain
    accept what the application layer still refuses, and these fail.
    SUPPORTING for the wrong-length and non-alphabetic parameters, which both
    implementations refuse regardless.
    """
    with pytest.raises(ValueError, match="ISO 3166-1 alpha-2 uppercase"):
        _validate_iso_3166_jurisdiction(raw)
    with pytest.raises(TransactionValidationError, match="ISO 3166-1 alpha-2 uppercase"):
        _domain_jurisdiction(raw)


def test_both_layers_are_wired_to_the_one_shared_normaliser() -> None:
    """Both boundaries must *delegate* to the core helper, not merely agree today.

    DISCRIMINATING for the dedup itself, and the only assertion here that is.
    Re-inlining a behaviourally identical copy of the shape check into either
    module leaves every behavioural assertion in this file green — identical
    logic produces identical outcomes — so behaviour alone cannot prove the
    duplication stayed removed.

    Asserting that each module's *namespace* resolves the helper is also not
    enough: a re-inlined copy that leaves the now-unused import in place still
    satisfies it (verified — that weaker form passed under exactly this
    mutation). So this inspects each validator's compiled ``co_names``, which
    names the globals the function body actually references, and therefore
    flips the moment a call site stops calling the shared helper.
    """
    domain_validator = Transaction.__dict__["_validate_source_jurisdiction"].__func__
    helper_name = normalise_iso_3166_alpha2_jurisdiction.__name__

    assert helper_name in domain_validator.__code__.co_names, (
        "domain Transaction._validate_source_jurisdiction must call the shared core normaliser"
    )
    assert helper_name in _validate_iso_3166_jurisdiction.__code__.co_names, (
        "application _validate_iso_3166_jurisdiction must call the shared core normaliser"
    )


def test_each_layer_keeps_its_own_exception_boundary() -> None:
    """Sharing the shape policy must not collapse the two error contracts.

    DISCRIMINATING: a domain validator that folds lowercase instead of
    refusing it stops raising here at all.

    The domain raises its own :class:`TransactionValidationError`; the
    application helper surfaces the core :class:`ValueError` subclass so
    Pydantic reports it as an ordinary validation failure.
    """
    with pytest.raises(TransactionValidationError):
        _domain_jurisdiction("es")

    with pytest.raises(CoreValidationError):
        _validate_iso_3166_jurisdiction("es")

    assert not issubclass(CoreValidationError, TransactionValidationError)
