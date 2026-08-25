"""The declared activity axis outranks the sectoral hint's three surrogates.

``_profile_suggests_sectoral_activity`` answered "is this taxpayer agrícola,
ganadero or forestal?" through three proxies -- the REAGP IVA régimen, the
estimación objetiva IRPF régimen, and a prior-year agrarian gross figure --
because no activity axis existed on the profile. One does now
(:class:`~domain.deadlines.IrpfActivityKind`, the RIRPF art. 95
professional/sectorial partition), so the question can be answered directly
rather than by correlation.

**Scope, stated plainly: this changes advisory WORDING, not which rows fire.**
The hint is read only to phrase the message
(``_retencion_rate_advisory.py``: "the profile is read below purely to word the
message, never to suppress it"), so the firing set is identical before and
after. Selling it as an outcome change would be the inert-discriminator trap in
reverse -- claiming a rate effect a measurement does not support.

The case that makes the ordering load-bearing is a taxpayer who declares
PROFESIONAL while filing estimación objetiva. Objetiva is an art. 95.6 régimen
covering plenty of non-agrarian activity (taxis, bars), so the surrogate alone
called them sectoral; the declaration says otherwise and now wins.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, UserProfileRecord
from ....tests.profile_capsule import seed_test_profile_record
from .._retencion_rate_advisory import _profile_suggests_sectoral_activity
from ._secure_objects_fixtures import secure_profile_backend  # noqa: F401

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_CLOCK = datetime(2026, 5, 21, 10, 0, 0, tzinfo=UTC)
_PROFILE_ID = "20020020-0200-4200-8200-200200200200"
_BUCKET_ID = _PROFILE_ID


@pytest.fixture
def bucket_id() -> str:
    return _BUCKET_ID


def _save_profile(*facts: UserProfileFact) -> None:
    """Persist a profile carrying ``facts`` through the real repository."""
    seed_test_profile_record(
        UserProfileRecord(
            setup_state=ProfileSetupState.COMPLETE,
            profile_id=_PROFILE_ID,
            facts=(UserProfileFact(path="identity.tax_id", value="12345678Z"), *facts),
            created_at=_CLOCK,
            updated_at=_CLOCK,
        ),
    )


def test_a_declared_sectorial_activity_answers_the_hint(secure_profile_backend: None) -> None:  # noqa: F811
    """A SECTORIAL declaration alone resolves the hint, with no surrogate present."""
    _save_profile(UserProfileFact(path="irpf.activity_kind", value="sectorial"))

    assert _profile_suggests_sectoral_activity(_BUCKET_ID) is True


def test_a_declared_professional_activity_answers_the_hint(secure_profile_backend: None) -> None:  # noqa: F811
    """A PROFESIONAL declaration alone resolves the hint negatively.

    Previously unreachable without an estimación directa régimen: a profile
    declaring only its activity had no non-sectoral signal at all and fell
    through to ``None``.
    """
    _save_profile(UserProfileFact(path="irpf.activity_kind", value="profesional"))

    assert _profile_suggests_sectoral_activity(_BUCKET_ID) is False


def test_the_declaration_outranks_the_estimacion_objetiva_surrogate(secure_profile_backend: None) -> None:  # noqa: F811
    """PROFESIONAL wins over objetiva -- the one case where the ordering shows.

    This is the assertion that would fail if the declaration were consulted
    after the surrogates instead of before, so it pins the ordering rather than
    merely exercising the new branch.
    """
    _save_profile(
        UserProfileFact(path="irpf.activity_kind", value="profesional"),
        UserProfileFact(path="irpf.estimation_regime", value="objetiva"),
    )

    assert _profile_suggests_sectoral_activity(_BUCKET_ID) is False


def test_the_objetiva_surrogate_still_answers_an_undeclared_profile(secure_profile_backend: None) -> None:  # noqa: F811
    """Without a declaration the surrogate is unchanged -- the fallback survives.

    Anti-regression counterpart to the test above: proves the new branch did not
    simply displace the surrogates for every profile, only for declaring ones.
    """
    _save_profile(UserProfileFact(path="irpf.estimation_regime", value="objetiva"))

    assert _profile_suggests_sectoral_activity(_BUCKET_ID) is True


def test_an_undeclared_silent_profile_still_yields_no_hint(secure_profile_backend: None) -> None:  # noqa: F811
    """A profile silent on both axes remains unresolved rather than guessing."""
    _save_profile()

    assert _profile_suggests_sectoral_activity(_BUCKET_ID) is None


def test_a_declared_sectorial_activity_needs_no_agrarian_gross_figure(secure_profile_backend: None) -> None:  # noqa: F811
    """The declaration stands alone, with the agrarian-gross surrogate absent.

    Guards against a reading where the new branch is redundant because a
    sectorial filer would always carry the prior-year agrarian figure anyway.
    They need not, and here they do not: the régimen declared is estimación
    directa simplificada, which the surrogates read as NON-sectoral, so a True
    can only have come from the declaration.
    """
    _save_profile(
        UserProfileFact(path="irpf.activity_kind", value="sectorial"),
        UserProfileFact(path="irpf.estimation_regime", value="directa_simplificada"),
    )

    assert _profile_suggests_sectoral_activity(_BUCKET_ID) is True
