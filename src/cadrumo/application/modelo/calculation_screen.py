"""The one staleness check for every screen a calculation runs against registry declarations.

A screen is a calculation note that exists because the pinned registry declares
something: the first is the binding grade cap. A calculation stamps the
revision with the screen contract version and a digest of the screen-relevant
declarations of its own registry revision. Checking, exporting and recording
recompute the expected stamp from the operation's pinned authority and refuse
a revision whose stamp is absent, older or different, with one derived reason,
``calculation_screen_outdated``, whose remedy is to calculate again.

One stamp covers every stale case at once: a revision stored before stamps
existed has none, and a revision calculated before a declaration was added or
removed has a different digest. The reason is never persisted, and it names no
modelo. A screen added later enrols its declarations in :func:`_screen_payload`
and raises :data:`CALCULATION_SCREEN_CONTRACT_VERSION`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from ...core.hashing import content_hash_hex
from ...domain.calculations.registry.binding_grade_cap_reach import capped_binding_reach, capped_binding_reach_digest
from ...domain.modelos.calculation_screen_stamp import CalculationScreenStamp
from .calculation_notes import CALCULATION_SCREEN_OUTDATED_REASON, what_locale_key

if TYPE_CHECKING:
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation
    from ...domain.calculations.registry.schema import RegistrySnapshot
    from ...domain.modelos.calculation_revision import CalculationRevision

CALCULATION_SCREEN_CONTRACT_VERSION: Final[int] = 1
"""One version for every screen together; raised when a screen is added or its reading changes."""


def _screen_payload(snapshot: RegistrySnapshot, *, operation: PinnedAuthorityOperation) -> dict[str, object]:
    return {
        "binding_grade_caps": capped_binding_reach_digest(capped_binding_reach(snapshot.revision, authority=operation)),
    }


def calculation_screen_stamp(
    snapshot: RegistrySnapshot, *, operation: PinnedAuthorityOperation
) -> CalculationScreenStamp:
    """Return the stamp a calculation of ``snapshot`` under ``operation`` carries.

    The digest covers only the selected registry revision's screen
    declarations, never the authority generation, so a publication that
    changes nothing a screen reads leaves a stamped revision current.
    """
    return CalculationScreenStamp(
        contract_version=CALCULATION_SCREEN_CONTRACT_VERSION,
        digest=content_hash_hex(_screen_payload(snapshot, operation=operation)),
    )


def calculation_screen_is_current(revision: CalculationRevision, expected: CalculationScreenStamp) -> bool:
    """Whether ``revision`` was screened against exactly the ``expected`` declarations under this contract."""
    stamp = revision.screen_stamp
    return stamp is not None and stamp == expected


def calculation_screen_outdated_message_key() -> str:
    """The catalogue key of the sentence saying the revision's screen is outdated."""
    return what_locale_key(CALCULATION_SCREEN_OUTDATED_REASON)


__all__ = [
    "CALCULATION_SCREEN_CONTRACT_VERSION",
    "calculation_screen_is_current",
    "calculation_screen_outdated_message_key",
    "calculation_screen_stamp",
]
