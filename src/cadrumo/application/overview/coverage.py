"""Obligation-coverage reconciliation for the overview surface.

The default ``overview`` surfaces (``calendar`` / ``agenda`` / ``backlog``)
answer "what must this taxpayer file?". A filing obligation reaches those
surfaces only when it has BOTH a registered deadline window (so the deadline
engine emits it) AND a positively ``APPLICABLE`` seed applicability verdict (so
the calendar keeps it). A modelo that lacks either is otherwise dropped without a
default-visible trace, so an operator or machine-readable caller
trusting the surface would under-file.

This module reconciles the full
:func:`~application.modelo.registry_discovery.registry_modelo_codes`
set against what the calendar positively resolved and classifies every registry
modelo into exactly one disposition:

* **surfaced** — it was resolved by a registry window and an applicable verdict;
* **confidently excluded** — the taxpayer model positively answers "no" for it
  (``NOT_APPLICABLE`` / ``ATTRIBUTION_PASS_THROUGH``): an answered question, no
  advisory needed;
* **advised** — it is applicable-but-window-less (e.g. Modelo 190) or its
  applicability is undetermined (``INCOMPLETE``): an unanswered question the
  operator MUST investigate;
* **out of scope** — it is listed in
  :data:`~core.OUT_OF_SCOPE_OBLIGATIONS` with a recorded product-scope
  reason.

The classification is total by construction, so no registry modelo can be
silently absent. The **advised** set is projected into a default-visible
:class:`~core.json_contract.Notice` by the CLI, closing the
``no-silent-under-declaration`` gap one layer up, at obligation determination.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date
from enum import StrEnum
from typing import Self

from pydantic import BaseModel, model_validator

from ...core import OUT_OF_SCOPE_OBLIGATIONS as _OUT_OF_SCOPE_OBLIGATIONS
from ...core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core import UNMODELED_OBLIGATIONS as _UNMODELED_OBLIGATIONS
from ...domain.calculations.registry.applicability import (
    ApplicabilityVerdict,
    derive_modelo_applicability,
)
from ...domain.deadlines.models import TaxpayerProfile


class CoverageAdviceReason(StrEnum):
    """Why an unsurfaced obligation is advised rather than silently dropped.

    Attributes:
        APPLICABLE_WINDOW_MISSING: The taxpayer model positively triggers
            the modelo (verdict ``APPLICABLE``) but the registry carries no
            deadline window for it, so the engine never placed it on the
            calendar. This is the former Modelo-190 shape — a genuine data gap.
        APPLICABILITY_UNDETERMINED: The seed applicability table cannot yet
            decide the modelo for this profile (verdict ``INCOMPLETE`` — no
            seed rule, or a payer/enrolment fact left undeclared). The
            operator must investigate whether it applies.
        REGISTRY_UNMODELED: The modelo is a recognized AEAT obligation
            (:data:`~core.UNMODELED_OBLIGATIONS`) that the registry does
            not model at all, so neither a window nor an applicability rule
            exists. It surfaces as advised — "AEAT may expect this; the app
            cannot yet scope it" — rather than being invisible.

            :data:`~core.UNMODELED_OBLIGATIONS` is intentionally empty today,
            so no production input reaches this disposition: the out-of-scope
            partition resolves first. The branch is kept deliberately, not
            pending deletion — it is the advisory capability for taxpayers
            whose obligation is registry-less, and populating the declaration
            is a per-entry tax review against official sources rather than a
            coding change. See that declaration for the full reasoning.
    """

    APPLICABLE_WINDOW_MISSING = "applicable_window_missing"
    APPLICABILITY_UNDETERMINED = "applicability_undetermined"
    REGISTRY_UNMODELED = "registry_unmodeled"


class AdvisedObligation(BaseModel):
    """One registry modelo the operator must investigate, with its reason."""

    model_config = _STRICT_FROZEN

    modelo: str
    reason: CoverageAdviceReason


class ObligationCoverageReport(BaseModel):
    """Total partition of the registry modelo set by coverage disposition.

    Every :func:`~application.modelo.registry_discovery.registry_modelo_codes`
    code lands in
    exactly one of the four tuples, and construction refuses a report that places
    one code in two of them (or twice in one). ``advised`` is the load-bearing
    field: a non-empty ``advised`` means the default surface would otherwise have
    hidden a filing obligation the operator must investigate.

    Attributes:
        surfaced: Modelos positively resolved by registry windows and
            applicability for the queried schedule horizon.
        confidently_excluded: Modelos the taxpayer model positively answers
            "no" for — answered, so no advisory is raised.
        advised: Modelos the operator must investigate (window-missing or
            applicability-undetermined), each with its
            :class:`CoverageAdviceReason`.
        out_of_scope: Modelos declared out of scope in
            :data:`~core.OUT_OF_SCOPE_OBLIGATIONS`.
    """

    model_config = _STRICT_FROZEN

    surfaced: tuple[str, ...] = ()
    confidently_excluded: tuple[str, ...] = ()
    advised: tuple[AdvisedObligation, ...] = ()
    out_of_scope: tuple[str, ...] = ()

    @property
    def advised_modelos(self) -> tuple[str, ...]:
        """Return just the advised modelo codes, in report order."""
        return tuple(item.modelo for item in self.advised)

    @property
    def has_advisories(self) -> bool:
        """Return whether any obligation must be investigated."""
        return bool(self.advised)

    @model_validator(mode="after")
    def _require_disjoint_dispositions(self) -> Self:
        """Refuse a report that files one modelo under more than one disposition.

        The four tuples are a partition, not four independent lists: a modelo
        classified as both confidently excluded and advised would let one
        surface read it as an answered question while another raises an
        advisory for it. Enforcing it here — rather than at any one consumer —
        means no caller can observe a report that contradicts itself.
        """
        seen: dict[str, str] = {}
        for disposition, modelos in (
            ("surfaced", self.surfaced),
            ("confidently_excluded", self.confidently_excluded),
            ("advised", self.advised_modelos),
            ("out_of_scope", self.out_of_scope),
        ):
            for modelo in modelos:
                previous = seen.get(modelo)
                if previous is None:
                    seen[modelo] = disposition
                    continue
                placement = (
                    f"twice in {previous!r}" if previous == disposition else f"in both {previous!r} and {disposition!r}"
                )
                raise ValueError(
                    f"obligation coverage dispositions must form a partition: modelo {modelo!r} appears {placement}",
                )
        return self


_CONFIDENT_NEGATIVE_VERDICTS = frozenset(
    {ApplicabilityVerdict.NOT_APPLICABLE, ApplicabilityVerdict.ATTRIBUTION_PASS_THROUGH},
)


def build_obligation_coverage(
    profile: TaxpayerProfile,
    surfaced_modelos: Iterable[str],
    *,
    today: date,
) -> ObligationCoverageReport:
    """Reconcile surfaced obligations against the full registry modelo set.

    Walks every :func:`~application.modelo.registry_discovery.registry_modelo_codes`
    code and
    assigns it to exactly one disposition (see :class:`ObligationCoverageReport`).
    The classification is total, so a modelo can never be silently absent: one
    that is neither surfaced, nor confidently excluded, nor explicitly out of
    scope is ``advised``, and the CLI raises a default-visible advisory for it.

    Args:
        profile: The operator's three-axis :class:`~domain.deadlines.TaxpayerProfile`.
        surfaced_modelos: The modelo codes positively resolved by a registry
            deadline window and an applicable verdict for the queried schedule
            horizon. They need not have an entry inside the UI date range; an
            annual row outside a two-week agenda is still resolved, not a
            grounding gap.
        today: Reference date for applicability evaluation (the Modelo-720
            Beckham-window check is date-sensitive).

    Returns:
        The :class:`ObligationCoverageReport` partition.
    """
    # Deferred to break a module-load cycle: application.modelo is a heavier
    # sibling package and importing it at module scope would couple overview's
    # import graph to it. The lookup itself is cheap (cached authority).
    from ..modelo.registry_discovery import registry_modelo_codes

    surfaced_set = frozenset(surfaced_modelos)
    registry_codes = frozenset(registry_modelo_codes())
    unmodeled_codes = {str(code) for code in _UNMODELED_OBLIGATIONS}
    out_of_scope_codes = {str(code) for code in _OUT_OF_SCOPE_OBLIGATIONS}
    # The AEAT obligation universe is the registry directory plus every recognized
    # obligation the registry does not model — those advised as unmodeled and those
    # explicitly declared out of scope. Binding the reconciliation to the full union
    # — not the registry alone — is what makes an obligation AEAT expects but the app
    # never modeled surface (as advised or as a recorded out-of-scope decision) rather
    # than being invisible.
    universe = registry_codes | unmodeled_codes | out_of_scope_codes
    surfaced: list[str] = []
    confidently_excluded: list[str] = []
    advised: list[AdvisedObligation] = []
    out_of_scope: list[str] = []

    for modelo in sorted(universe):
        if modelo in surfaced_set:
            surfaced.append(modelo)
            continue
        if modelo in out_of_scope_codes:
            out_of_scope.append(modelo)
            continue
        if modelo not in registry_codes:
            # A recognized AEAT obligation the registry does not model: no window
            # and no applicability rule exist, so it cannot be positively scoped.
            advised.append(AdvisedObligation(modelo=modelo, reason=CoverageAdviceReason.REGISTRY_UNMODELED))
            continue
        verdict = derive_modelo_applicability(profile, modelo, today=today).verdict
        if verdict in _CONFIDENT_NEGATIVE_VERDICTS:
            confidently_excluded.append(modelo)
            continue
        reason = (
            CoverageAdviceReason.APPLICABLE_WINDOW_MISSING
            if verdict is ApplicabilityVerdict.APPLICABLE
            else CoverageAdviceReason.APPLICABILITY_UNDETERMINED
        )
        advised.append(AdvisedObligation(modelo=modelo, reason=reason))

    return ObligationCoverageReport(
        surfaced=tuple(surfaced),
        confidently_excluded=tuple(confidently_excluded),
        advised=tuple(advised),
        out_of_scope=tuple(out_of_scope),
    )


__all__ = [
    "AdvisedObligation",
    "CoverageAdviceReason",
    "ObligationCoverageReport",
    "build_obligation_coverage",
]
