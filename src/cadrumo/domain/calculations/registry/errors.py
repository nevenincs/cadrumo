"""Registry error types for AEAT legal calculation definitions.

This module provides classmethod factories on :class:`RegistryValidationError`
and :class:`RegistrySnapshotError` for each canonical raise scenario. The
factory pattern pins the context-dict keys downstream consumers
(``cadrumo.core.errors.error_codes`` template renderer, CLI JSON emit via
``SchemaEnvelope``, i18n locales referencing keys by name) rely on.

The existing ``raise RegistryValidationError(message, context=...)`` shape
stays valid for one-off scenarios that haven't been promoted to canonical
factories yet; migration is additive and non-breaking.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Self

from ....core.casilla_id import CasillaId
from ....core.errors.hierarchy import CadrumoError, CoreValidationError, TerminalPreconditionErrorMixin
from ....core.modelo import Modelo
from .ids import RevisionId


class RegistryFailureCondition(StrEnum):
    """Domain-owned failed-condition identities for registry refusals.

    These names identify facts the registry can observe.  They deliberately do
    not encode a command or an outcome: application policy decides whether a
    live surface has a canonical action, and the CLI resolves that action.
    """

    TAXPAYER_MODEL_DECLARED = "registry.applicability.taxpayer_model.declared"
    MODELO_202_INCN_DECLARED = "registry.applicability.modelo_202.incn.declared"
    QUERY_FILING_YEAR_SCOPED = "registry.query.filing_year.scoped"
    QUERY_CASILLA_DECLARED = "registry.query.casilla.declared"
    SNAPSHOT_AUTHORITY_GRADE_SUFFICIENT = "registry.snapshot.authority_grade.sufficient"
    SNAPSHOT_EXPORT_LAYOUT_DECLARED = "registry.snapshot.export_layout.declared"
    TREE_QUIESCENT = "registry.tree.concurrent_write.quiescent"


@dataclass(frozen=True)
class RegistryFailureClassification:
    """One registry-observed failed condition and its locale-neutral facts."""

    condition: RegistryFailureCondition
    facts: Mapping[str, str | int | bool]


class RegistryError(TerminalPreconditionErrorMixin[object], CadrumoError):
    """Base error retaining domain facts for a higher-layer action projection."""

    def __init__(
        self,
        message: str | None = None,
        *,
        context: Mapping[str, object] | None = None,
        translated_message: str | None = None,
        registry_failure: RegistryFailureClassification | None = None,
        precondition_verdict: object | None = None,
    ) -> None:
        """Keep a domain classification without importing application policy."""
        super().__init__(
            message=message,
            context=context,
            translated_message=translated_message,
            precondition_verdict=precondition_verdict,
        )
        self._registry_failure = registry_failure

    @property
    def registry_failure(self) -> RegistryFailureClassification | None:
        """Return the domain fact classification for an application to resolve."""
        return self._registry_failure


class RegistryLoadError(RegistryError):
    """Raised when registry files cannot be parsed into strict schema objects."""


def _csv(items: Iterable[str]) -> str:
    """Stable comma-join used by every context-key serialisation.

    Callers pass already-sorted tuples where order matters; this
    helper just centralises the ``", ".join`` style so a future
    formatting change lands in one place.
    """
    return ",".join(items)


class RegistryValidationError(RegistryError, CoreValidationError):
    """Raised when registry definitions are incomplete or contradictory.

    Its registered ancestry includes :class:`CoreValidationError` under
    :class:`RegistryError`, so callers use the canonical registry-bound catch
    surface. Pydantic validators translate this registered failure to
    ``ValueError`` at their narrow boundary.

    Canonical raise scenarios route through one of the ``for_*``
    classmethod factories so the context-dict keys consumed by
    locale templates and CLI JSON emit are pinned to a named
    contract per scenario.
    """

    @classmethod
    def for_unknown_input_casilla_ids(cls, *, casilla_ids: Sequence[CasillaId]) -> Self:
        """Inputs to the runtime referenced casilla ids absent from the revision."""
        ids = sorted(casilla_ids)
        return cls(
            f"unknown registry input casilla ids: {ids!r}",
            translated_message="errors.calc.unknown_input_casillas",
            context={"casilla_ids": _csv(ids)},
        )

    @classmethod
    def for_prorrata_activity_rows_incomplete(cls, *, ejercicio: int) -> Self:
        """An applicable Modelo 303 ejercicio is missing a DP30305 activity row.

        An absent row collection is honest only when the register's regime
        says prorrata does not apply for ``ejercicio``; once it applies, a
        partial collection must fail before a target export file can mask the
        under-declaration. Canonical key: shares the filing package's
        pre-existing ``application.filing.m303_prorrata_activity_rows.errors.
        activity_rows_incomplete`` catalogue entry, which already carries the
        operator-facing sentence in all four locales.
        """
        return cls(
            f"modelo 303 per-activity prorrata rows are incomplete for ejercicio {ejercicio}",
            translated_message="application.filing.m303_prorrata_activity_rows.errors.activity_rows_incomplete",
            context={
                "modelo": Modelo("303").value,
                "filing_year": ejercicio,
                "required_slot_first": 1,
                "required_slot_last": 5,
            },
        )


class RegistrySnapshotError(RegistryError):
    """Raised when a filing-grade snapshot cannot be selected.

    The single canonical raise scenario is `for_modelo_not_registered`
    at the `_authority.modelo` boundary; the bare constructor stays
    valid for one-off scenarios not yet promoted to a factory.

    Two temporal-selection scenarios carry structured context as
    dedicated subclasses (:class:`NoRevisionForPeriodError`,
    :class:`AmbiguousRevisionSelectionError`) so a consumer dispatches
    by ``except`` type rather than parsing the human-readable message.
    Both subclass this type, so every existing ``except
    RegistrySnapshotError`` site catches them unchanged.
    """

    @classmethod
    def for_modelo_not_registered(cls, *, modelo_id: str) -> Self:
        """The requested modelo id has no registered revision."""
        return cls(
            f"modelo {modelo_id!r} is not present in the calculation registry",
            translated_message="errors.snapshot.modelo_not_registered",
            context={"modelo_id": modelo_id},
        )


class NoRevisionForPeriodError(RegistrySnapshotError):
    """No registry revision matches the requested temporal natural key.

    Raised by :func:`select_revision` when the (modelo, filing year,
    period, optional date window, optional revision id) constraints
    select zero candidate revisions. Carries the natural-key components
    as structured context so a consumer (e.g. the ``config profile
    preflight`` resolver) can build an instructive refusal without
    parsing the message. Catchable as :class:`RegistrySnapshotError`.

    Structured attributes: ``modelo_id``, ``filing_year``, ``period``,
    ``revision_id``, ``available_revision_ids``.
    """

    def __init__(
        self,
        *,
        modelo_id: str,
        filing_year: int,
        period: str,
        revision_id: RevisionId | None,
        available_revision_ids: Iterable[str],
    ) -> None:
        """Construct the no-revision-for-period error.

        Args:
            modelo_id: The modelo whose revisions were searched.
            filing_year: The AEAT filing year used to narrow revisions.
            period: The period token that found no covering revision.
            revision_id: The optional explicit revision-id filter, if any.
            available_revision_ids: Every revision the modelo declares, stored
                sorted on ``available_revision_ids``. REQUIRED rather than
                defaulted: a refusal that cannot say what IS available reads as
                a malfunction, and the operator's real question here is which
                filing years exist at all. Both raisers hold the modelo's
                revision collection already, so there is no case where it is
                genuinely unknown -- and a default would let a future raiser
                silently ship the uninformative form.
        """
        available = tuple(sorted(available_revision_ids))
        self.modelo_id: str = modelo_id
        self.filing_year: int = filing_year
        self.period: str = period
        self.revision_id: RevisionId | None = revision_id
        self.available_revision_ids: tuple[str, ...] = available
        detail = f"modelo {modelo_id}: no revision for year={filing_year!r} period={period!r} revision={revision_id!r}"
        if available:
            detail = f"{detail}; modelo {modelo_id} declares: {', '.join(available)}"
        super().__init__(
            detail,
            translated_message="errors.snapshot.no_revision_for_period",
            context={
                "modelo_id": modelo_id,
                "filing_year": filing_year,
                "period": period,
                "revision_id": revision_id if revision_id is not None else "",
                "available_revision_ids": _csv(available),
            },
        )


class EjercicioOrdenNotYetPublishedError(NoRevisionForPeriodError):
    """The modelo cannot answer this filing year yet, and says so itself.

    An annual modelo is re-approved once per ejercicio, and the Orden approving
    ejercicio N is published during year N+1. A request for a year whose Orden
    is unwritten is not an oversight and not a gap anybody can close: no author
    can supply what the authority has not issued.

    Raised in place of the plain absence refusal when the modelo declares a
    matching ``pending_ejercicio_ordenes`` entry. It subclasses
    :class:`NoRevisionForPeriodError` deliberately -- every existing handler
    keeps catching it, and the answer really is that no revision matched -- so
    only callers that want the distinction pay any attention to it.

    Structured attributes add ``rests_on`` and ``expected_publication_year`` to
    the inherited natural key, because an operator told to wait is owed both
    what the product currently rests on and when that changes.
    """

    def __init__(
        self,
        *,
        modelo_id: str,
        filing_year: int,
        period: str,
        revision_id: RevisionId | None,
        available_revision_ids: Iterable[str],
        rests_on: str,
        expected_publication_year: int,
    ) -> None:
        """Construct the awaiting-Orden refusal."""
        super().__init__(
            modelo_id=modelo_id,
            filing_year=filing_year,
            period=period,
            revision_id=revision_id,
            available_revision_ids=available_revision_ids,
        )
        self.rests_on: str = rests_on
        self.expected_publication_year: int = expected_publication_year
        self.args = (
            f"modelo {modelo_id}: filing year {filing_year} awaits its approving Orden; "
            f"the modelo rests on {rests_on} and the next Orden is expected in "
            f"{expected_publication_year}",
        )
        self.translated_message = "errors.snapshot.ejercicio_orden_not_yet_published"
        self.context = {
            **(self.context or {}),
            "rests_on": rests_on,
            "expected_publication_year": expected_publication_year,
        }


class FilingYearOutsideSupportEnvelopeError(RegistrySnapshotError):
    """The registry declines a coordinate its support envelope gates, not one it lacks.

    A refused filing year has two unrelated causes, and conflating them costs
    triage time out of all proportion to the fix. Either no revision was ever
    authored for the coordinate -- an authoring gap, answered by
    :class:`NoRevisionForPeriodError` -- or the corpus authors it perfectly well
    and the product's declared filing envelope refuses to resolve it, which is a
    scope decision no amount of authoring changes. The second is this error.

    Keeping them apart is the same invariant the sibling governed-fact resolver
    already holds: unsupported and absent are distinct states, and a consumer
    that cannot tell them apart cannot choose a remedy. The remedy differs
    completely -- a gap is closed by authoring the revision, an out-of-envelope
    coordinate by resolving against the authority scoped to the authored
    history instead of the filing envelope, or by moving the envelope floor.

    ``covering_revision_ids`` is deliberately the revisions whose own period
    selector DOES cover the requested coordinate. It is usually non-empty, and
    that is the whole point: the previous refusal reported those same ids under
    a message asserting nothing covered the year, so its own evidence
    contradicted its own claim.

    Subclasses :class:`RegistrySnapshotError`, not
    :class:`NoRevisionForPeriodError`: every broad ``except
    RegistrySnapshotError`` site keeps catching it, while a handler that means
    "no revision was authored" no longer silently absorbs an envelope refusal.

    Structured attributes: ``modelo_id``, ``filing_year``, ``period``,
    ``floor``, ``horizon``, ``hard_ceiling``, ``covering_revision_ids``.
    """

    def __init__(
        self,
        *,
        modelo_id: str,
        filing_year: int,
        period: str,
        floor: int,
        horizon: int,
        hard_ceiling: int | None,
        covering_revision_ids: Iterable[str],
    ) -> None:
        """Construct the outside-support-envelope refusal.

        Args:
            modelo_id: The modelo whose selection was refused.
            filing_year: The requested AEAT filing year the envelope gates.
            period: The requested period token, or ``"year"`` for the
                year-only selectors, carried so the refusal names the exact
                coordinate the caller asked for.
            floor: The envelope's hard lower gate.
            horizon: The envelope's last globally authored coordinate.
            hard_ceiling: The envelope's hard upper gate, when it declares one.
            covering_revision_ids: The revisions whose declared period selector
                covers the requested coordinate. REQUIRED, and named as
                "covering" rather than "available": a refusal that says the
                envelope gated a year the corpus does author is actionable,
                and one that merely lists revisions is the misleading form
                this error exists to replace.
        """
        covering = tuple(sorted(covering_revision_ids))
        self.modelo_id: str = modelo_id
        self.filing_year: int = filing_year
        self.period: str = period
        self.floor: int = floor
        self.horizon: int = horizon
        self.hard_ceiling: int | None = hard_ceiling
        self.covering_revision_ids: tuple[str, ...] = covering
        ceiling = "open" if hard_ceiling is None else str(hard_ceiling)
        detail = (
            f"modelo {modelo_id}: filing year {filing_year} period {period!r} lies outside the "
            f"registry support envelope [floor={floor}, horizon={horizon}, hard_ceiling={ceiling}]"
        )
        if covering:
            detail = (
                f"{detail}; the corpus DOES author this coordinate in modelo {modelo_id} "
                f"revision(s) {', '.join(covering)}, so this is an envelope scope refusal, "
                f"not a missing revision"
            )
        super().__init__(
            detail,
            translated_message="errors.snapshot.filing_year_outside_support_envelope",
            context={
                "modelo_id": modelo_id,
                "filing_year": filing_year,
                "period": period,
                "floor": floor,
                "horizon": horizon,
                "hard_ceiling": "" if hard_ceiling is None else hard_ceiling,
                "covering_revision_ids": _csv(covering),
            },
        )


class AmbiguousRevisionSelectionError(RegistrySnapshotError):
    """More than one registry revision matches the temporal natural key.

    Raised by :func:`select_revision` when the constraints select two or
    more candidate revisions. Carries the candidate revision ids as a
    structured, already-sorted tuple so a consumer can list them in an
    operator refusal without re-parsing the message. Catchable as
    :class:`RegistrySnapshotError`.

    THE REMEDY IS RAISER-SELECTED, through the locale key rather than through a
    second channel beside it. Two selectors raise this: the year-only one, where
    the fix is to supply a period or an as-of date, and the period-scoped one,
    where the caller has already supplied a period and that advice would send an
    operator to redo what they just did. No single string is correct for both,
    so the year-only raiser names its own ``translated_message`` and the
    period-scoped raiser keeps the shared default, which states the collision
    without prescribing an action the operator cannot take.

    Structured attributes: ``modelo_id``, ``candidate_ids``, ``filing_year``.
    """

    def __init__(
        self,
        *,
        modelo_id: str,
        candidate_ids: Iterable[str],
        filing_year: int | None = None,
        reason: str | None = None,
        translated_message: str = "errors.snapshot.ambiguous_revision_selection",
    ) -> None:
        """Construct the ambiguous-revision-selection error.

        Args:
            modelo_id: The modelo whose revisions were searched.
            candidate_ids: The matching revision ids; stored sorted as a
                tuple on ``candidate_ids``.
            filing_year: Optional filing year the ambiguity arose for. Named in
                the fallback text and carried structurally, because "two
                revisions match" is far more actionable once the reader knows
                WHICH year is doubly covered.
            reason: Optional raiser-supplied explanation of WHY the year is
                ambiguous, appended to the fallback text.
            translated_message: Locale key for the operator-facing refusal. The
                default states the collision alone; the year-only selector names
                a key whose text also carries the remedy, because the two
                selectors have opposite remedies and one shared string is
                correct for neither.
        """
        ids = tuple(sorted(candidate_ids))
        self.modelo_id: str = modelo_id
        self.candidate_ids: tuple[str, ...] = ids
        self.filing_year: int | None = filing_year
        scope = f"modelo {modelo_id}" if filing_year is None else f"modelo {modelo_id} filing year {filing_year}"
        detail = f"{scope}: ambiguous revision selection: {', '.join(ids)}"
        if reason:
            detail = f"{detail} -- {reason}"
        context: dict[str, object] = {"modelo_id": modelo_id, "candidate_ids": _csv(ids)}
        if filing_year is not None:
            context["filing_year"] = filing_year
        super().__init__(
            detail,
            translated_message=translated_message,
            context=context,
        )


class CasillaConstraintViolationError(RegistryError):
    """Raised when a computed casilla value falls outside its declared constraints.

    The constraint set is ``casilla.constraints`` (sign, min_value, max_value).
    The error envelope carries ``casilla_id``, the offending ``value``, the
    offended constraint clause, and the casilla's ``legal_refs`` so the
    operator sees the BOE permalink that justifies the rule.
    """
