"""Whether a declaration was presented inside its plazo voluntario, or late.

A filing's legal kind (original, complementaria, sustitutiva, rectificativa)
and its timeliness are two independent facts. An original declaration can be
presented after the voluntary window closed, and that lateness carries its own
consequence: Ley 58/2003 art. 27 attaches a recargo por declaración
extemporánea sin requerimiento previo. A consumer reading only the declaration
kind therefore cannot tell a timely filing from a late one.

:class:`FilingTimeliness` is the closed axis of that calendar fact. It reports
a CALENDAR POSTURE only. ``EXTEMPORANEA`` says the voluntary filing window had
closed on the presentation date; it asserts no art. 27 eligibility, no recargo
amount, no interest and no absence of a prior administrative requerimiento.
Those predicates need provenance-bearing statutory evidence that no local
record carries, so a statutory assessment remains a separate, unavailable
outcome.

``UNKNOWN`` is the honest answer where the registry declares no filing window
for the declaration's axis, or declares one whose close date is unpublished:
lateness cannot be judged, and a missing window is not proof of punctuality.

The judgement itself belongs to the one owner of the effective close date,
:meth:`~cadrumo.domain.deadlines.effective_close.EffectiveFilingDeadline.timeliness_on`,
so no surface can compare a presentation date against the nominal close while
another compares it against the business-day-shifted one.
"""

from __future__ import annotations

from enum import StrEnum


class FilingTimeliness(StrEnum):
    """Posture of one presentation date against its plazo voluntario.

    Attributes:
        EN_PLAZO: Presented on or before the effective close date of the
            voluntary filing window.
        EXTEMPORANEA: Presented after that close date. A late filing remains
            admissible (Ley 58/2003 art. 27 attaches a recargo rather than
            barring the declaration), which is why this is a posture and not a
            refusal; the surcharge consequence is not assessed here.
        UNKNOWN: No filing window resolves for the declaration's axis, or its
            close date is unpublished, so timeliness cannot be judged.
    """

    EN_PLAZO = "en_plazo"
    EXTEMPORANEA = "extemporanea"
    UNKNOWN = "unknown"


__all__ = ["FilingTimeliness"]
