"""Presentation-only projection of profile-passphrase assessment.

The application owns password policy and returns a typed, secret-free
assessment. This module only turns that result into localized copy and keeps
the typed passphrase out of any projection object.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, Protocol, cast

from ....core import PassphraseStrength, ProfilePasswordRefusalReason
from ....core.i18n import tr

if TYPE_CHECKING:
    from ....application.user_profile import ProspectiveProfilePasswordRefusal
    from ....core import ProfilePasswordAssessment


class ProfilePasswordVerdict(Protocol):
    """The secret-free assessment shape rendered by registration."""

    @property
    def strength(self) -> PassphraseStrength:
        """Advisory band for the candidate."""
        ...  # pragma: no cover

    @property
    def reason(self) -> ProfilePasswordRefusalReason | None:
        """Typed refusal reason, or ``None`` when accepted."""
        ...  # pragma: no cover

    @property
    def accepted(self) -> bool:
        """Whether the application accepts the candidate."""
        ...  # pragma: no cover

    @property
    def scalar_count(self) -> int:
        """Safe number of Unicode scalars observed."""
        ...  # pragma: no cover

    @property
    def utf8_byte_count(self) -> int | None:
        """Safe strict UTF-8 size, absent when encoding is invalid."""
        ...  # pragma: no cover


_STRENGTH_CLASSES: Final[dict[PassphraseStrength, str]] = {
    PassphraseStrength.WEAK: "strength-weak",
    PassphraseStrength.FAIR: "strength-fair",
    PassphraseStrength.STRONG: "strength-strong",
}


def assessment_refusal(
    assessment: ProfilePasswordVerdict,
) -> ProspectiveProfilePasswordRefusal | None:
    """Project a canonical assessment through the application facade."""
    from ....application.user_profile import prospective_profile_password_refusal

    return prospective_profile_password_refusal(cast("ProfilePasswordAssessment", assessment))


def assessment_copy(assessment: ProfilePasswordVerdict) -> str:
    """Resolve localized validation or advisory copy for one assessment."""
    refusal = assessment_refusal(assessment)
    if refusal is not None:
        return tr(refusal.translated_message, **dict(refusal.context))
    match assessment.strength:
        case PassphraseStrength.WEAK:
            return tr("flows.registration.strength.weak")
        case PassphraseStrength.FAIR:
            return tr("flows.registration.strength.fair")
        case PassphraseStrength.STRONG:
            return tr("flows.registration.strength.strong")


def assessment_css_class(assessment: ProfilePasswordVerdict) -> str:
    """Return the presentation class for a secret-free assessment."""
    if not assessment.accepted:
        return "strength-refused"
    return _STRENGTH_CLASSES[assessment.strength]


__all__ = ["ProfilePasswordVerdict", "assessment_copy", "assessment_css_class", "assessment_refusal"]
