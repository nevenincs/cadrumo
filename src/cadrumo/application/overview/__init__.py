"""Application read models for ``aeat app overview``.

The package owns the typed DTOs and pure builders behind the overview
``status``, ``calendar``, ``agenda``, ``backlog``, and ``explain``
surfaces. CLI adapters supply the active profile or bucket state,
already-persisted live-read snapshots, local filing records, and query dates;
these builders do not contact AEAT and do not mutate storage.

``overview status`` delegates to
:func:`application.state_projection.build_operator_state_projection`
and projects the canonical
:class:`application.state_projection.OperatorStateProjection` through
:func:`overview_status_report_from_projection` into
:class:`OverviewStatusReport`. ``overview calendar`` composes the existing
:class:`domain.deadlines.DeadlineEngine` over the requested year
window, returning :class:`OverviewCalendarEntry` obligation rows, additive
:class:`OverviewCalendarEvent` observations, and
:class:`OverviewCalendarFilingEvidence` rows.

Calendar evidence deliberately keeps :class:`OverviewLocalFilingState`
separate from :class:`OverviewAeatSubmissionState`: a local ready/filed
record never implies an AEAT submission, and an observed AEAT submission
is not a verified justificante until persisted receipt metadata proves
the CSV/model/year/period/taxpayer match. Raw profile values may also
produce typed :class:`CalendarWarning` and :class:`CalendarCompleteness`
records through :func:`build_filing_obligation_advisories` so
deadline-engine defaults are visible rather than silent.

See Also:
    :mod:`application.state_projection`
        Canonical producer for the :class:`application.state_projection.OperatorStateProjection`
        consumed by ``overview status``.
    :mod:`domain.deadlines`
        Deadline engine and :class:`domain.deadlines.Schedule` authority
        used by calendar, agenda, backlog, and explain read models.
    :mod:`application.live`
        Read-only capture surface that persists the live evidence this package
        can display without opening AEAT again.
    :mod:`domain.modelos`
        Local :class:`~ModeloRecord` and
        :class:`~ExternalEvidence` records projected into
        overview calendar evidence.
    :mod:`application.workflow`
        Active-profile and pending-obligation state that remains upstream of
        overview rendering.

Consumers import from the owning module -- :mod:`status_report`,
:mod:`calendar`, :mod:`calendar_models`, :mod:`coverage`, :mod:`data_prep`,
:mod:`next_actions`, :mod:`pipeline_health`, :mod:`agenda`, :mod:`backlog`,
:mod:`explain`, :mod:`errors` -- rather than from this package root.

The root previously DEFINED four status-report builders as well as re-exporting
fifty-odd names, which is why deleting an export map could not make it inert.
Those builders now live in :mod:`status_report`.
"""

from __future__ import annotations

__all__: tuple[str, ...] = ()
"""Inert namespace: every contract is reached at the module that defines it."""
