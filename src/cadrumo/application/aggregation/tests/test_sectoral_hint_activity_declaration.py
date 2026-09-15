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

from types import SimpleNamespace
import pytest

from ....domain.user_profile.values import UserProfileFact
from .. import _retencion_rate_advisory
from .._retencion_rate_advisory import _profile_suggests_sectoral_activity

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "20020020-0200-4200-8200-200200200200"


def _profile_for_facts(*facts: UserProfileFact) -> SimpleNamespace:
    """Build the projected profile shape consumed by the advisory policy."""
    values = {fact.path: fact.value for fact in facts}
    return SimpleNamespace(
        irpf_activity_kind=values.get("irpf.activity_kind"),
        iva_regime=values.get("iva.regime"),
        irpf_estimation_regime=values.get("irpf.estimation_regime"),
        objective_estimation_prior_year_agri_livestock_forest_gross_eur=values.get(
            "irpf.objective_estimation_prior_year_agri_livestock_forest_gross_eur"
        ),
    )


def _suggests(*facts: UserProfileFact) -> bool | None:
    """Exercise the policy with an inward fake profile, without persistence."""
    profile = _profile_for_facts(*facts)
    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(_retencion_rate_advisory, "_load_profile_for_bucket", lambda _bucket_id: profile)
        return _profile_suggests_sectoral_activity(_BUCKET_ID)


def test_a_declared_sectorial_activity_answers_the_hint() -> None:
    """A SECTORIAL declaration alone resolves the hint, with no surrogate present."""
    assert _suggests(UserProfileFact(path="irpf.activity_kind", value="sectorial")) is True


def test_a_declared_professional_activity_answers_the_hint() -> None:
    """A PROFESIONAL declaration alone resolves the hint negatively.

    Previously unreachable without an estimación directa régimen: a profile
    declaring only its activity had no non-sectoral signal at all and fell
    through to ``None``.
    """
    assert _suggests(UserProfileFact(path="irpf.activity_kind", value="profesional")) is False


def test_the_declaration_outranks_the_estimacion_objetiva_surrogate() -> None:
    """PROFESIONAL wins over objetiva -- the one case where the ordering shows.

    This is the assertion that would fail if the declaration were consulted
    after the surrogates instead of before, so it pins the ordering rather than
    merely exercising the new branch.
    """
    assert (
        _suggests(
            UserProfileFact(path="irpf.activity_kind", value="profesional"),
            UserProfileFact(path="irpf.estimation_regime", value="objetiva"),
        )
        is False
    )


def test_the_objetiva_surrogate_still_answers_an_undeclared_profile() -> None:
    """Without a declaration the surrogate is unchanged -- the fallback survives.

    Anti-regression counterpart to the test above: proves the new branch did not
    simply displace the surrogates for every profile, only for declaring ones.
    """
    assert _suggests(UserProfileFact(path="irpf.estimation_regime", value="objetiva")) is True


def test_an_undeclared_silent_profile_still_yields_no_hint() -> None:
    """A profile silent on both axes remains unresolved rather than guessing."""
    assert _suggests() is None


def test_a_declared_sectorial_activity_needs_no_agrarian_gross_figure() -> None:
    """The declaration stands alone, with the agrarian-gross surrogate absent.

    Guards against a reading where the new branch is redundant because a
    sectorial filer would always carry the prior-year agrarian figure anyway.
    They need not, and here they do not: the régimen declared is estimación
    directa simplificada, which the surrogates read as NON-sectoral, so a True
    can only have come from the declaration.
    """
    assert (
        _suggests(
            UserProfileFact(path="irpf.activity_kind", value="sectorial"),
            UserProfileFact(path="irpf.estimation_regime", value="directa_simplificada"),
        )
        is True
    )
