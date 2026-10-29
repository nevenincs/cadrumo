"""Answer each registry question once per invoice validation pass.

Validating an invoice asks the governed-fact authority the same questions for
every invoice and line: which rate slot a persisted token names, which rate a
slot carried on a devengo date, which invoice classes and categories exist
today. Decoding a catalogue of thousands of invoices asked them thousands of
times, and every answer was rebuilt from the registry each time.

A pass is one outermost :class:`~cadrumo.domain.invoices.models.Invoice` or
:class:`~cadrumo.domain.invoices.catalogue.InvoiceCatalogue` validation. Inside it,
:func:`answer_once` returns the first successful answer to an identical
question instead of recomputing it. The memo is bounded by these invariants:

- It lives only as long as the pass. Nothing is retained after the outermost
  validation returns or raises, so no answer outlives the decode that asked it.
- An answer is keyed by the identity of the governed-fact authority in scope
  when it was asked, and the pass holds that authority strongly, so its
  identity cannot be reused by another generation while the pass runs. A
  question asked under a different authority is a different question.
- The key carries every argument, explicit dates included, and the current
  Europe/Madrid civil date, because several projections default their
  effective date to today. A pass straddling midnight asks again.
- Only successful answers are kept. A refusal is recomputed and raised afresh
  each time, so every invoice reports its own failure exactly as before.
- Answers are shared between invoices, so only immutable values are memoised.
- With no pass or no authority in scope the projection runs unchanged.
"""

from __future__ import annotations

from collections.abc import Callable, Generator, Hashable
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import cast

from ...core.time.clock import today_madrid
from ..calculations.registry.governed_fact_scope import GovernedFactSource, governed_facts_in_scope


@dataclass(slots=True)
class _ValidationPass:
    """The authorities seen by one pass and the answers given under each."""

    authorities: dict[int, GovernedFactSource] = field(default_factory=dict)
    answers: dict[tuple[Hashable, ...], object] = field(default_factory=dict)


_ACTIVE_PASS: ContextVar[_ValidationPass | None] = ContextVar("invoice_validation_pass", default=None)


@contextmanager
def invoice_validation_pass() -> Generator[None]:
    """Open a pass unless one is already open; nested validations share it."""
    if _ACTIVE_PASS.get() is not None:
        yield
        return
    token = _ACTIVE_PASS.set(_ValidationPass())
    try:
        yield
    finally:
        _ACTIVE_PASS.reset(token)


def answer_once[**P, R](projection: Callable[P, R], /, *args: P.args, **kwargs: P.kwargs) -> R:
    """Return ``projection(*args, **kwargs)``, computed once per pass and authority.

    ``projection`` must be deterministic for its arguments, the authority in
    scope and the current civil date, and must return an immutable value.
    Arguments must be hashable.
    """
    active = _ACTIVE_PASS.get()
    authority = governed_facts_in_scope()
    if active is None or authority is None:
        return projection(*args, **kwargs)
    authority_key = id(authority)
    active.authorities.setdefault(authority_key, authority)
    key: tuple[Hashable, ...] = (
        authority_key,
        projection,
        today_madrid(),
        args,
        tuple(sorted(kwargs.items())),
    )
    if key in active.answers:
        return cast("R", active.answers[key])
    answer = projection(*args, **kwargs)
    active.answers[key] = answer
    return answer


__all__ = ["answer_once", "invoice_validation_pass"]
