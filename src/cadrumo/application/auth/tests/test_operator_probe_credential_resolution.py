"""Real-behavior tests for readiness surfaces reading profile-borne credentials.

Live authentication resolves a Cl@ve credential from the active profile
first, but the readiness probes and status surfaces used to read the
environment settings directly. That split let a status surface report
"not configured" about a credential the profile holds and the session
entry would happily authenticate with, which is a lie to the operator
rather than a cosmetic gap.

Every test here therefore leaves the environment empty and puts the
credential only on the profile, so a pass cannot be explained by the
settings fallback. The profile is driven through the real store and the
real lifecycle service; no test doubles stand in for the read.
"""

from __future__ import annotations

import pytest
from pydantic import SecretStr

from ....core import AuthProviderKind
from ....core.config import load_settings, override_settings
from ....tests.profile_storage_root_fixture import bucket_session_storage_fixture
from ....tests.user_profile import register_minimal_profile
from ..._state_projection_auth import build_auth_readiness
from ...workflow import workflow_state_repository
from ..operator import _assert_login_precondition, build_live_auth_preflight_report, configure_operator_auth
from ..operator_probes import (
    _live_auth_identity_kind,
    _live_auth_identity_state,
    probe_clave_credentials,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "55555555-5555-4555-8555-555555555555"
_PROFILE_LABEL = "probe-operator"
_TAX_ID = "12345678Z"
_OTHER_TAX_ID = "00000001R"


def _register_profile(**overrides: str) -> None:
    facts = {"identity.tax_id": _TAX_ID}
    facts.update(overrides)
    register_minimal_profile(profile_id=_BUCKET_ID, display_name=_PROFILE_LABEL, overrides=facts)


def test_probe_reports_a_profile_borne_credential_as_configured() -> None:
    """The environment holds nothing; the profile holds the identity.

    Before this, the probe read the setting and reported the credential
    absent, so the operator was told to configure something they had
    already recorded.
    """

    _register_profile(**{"auth.dni_nie": _TAX_ID})
    with override_settings(cadrumo_clave_movil_dni_nie=None) as settings:
        credentials = probe_clave_credentials(AuthProviderKind.CLAVE_MOVIL, settings=settings)

    assert credentials is not None
    assert credentials.dni_nie == _TAX_ID


def test_backend_readiness_describes_the_profile_bound_clave_provider() -> None:
    """The status backend sees the same effective credentials as live login.

    The encrypted profile is the only identity source. This exercises the
    production readiness builder and real provider description, so it fails if
    status constructs the backend from empty environment settings.
    """
    _register_profile(
        **{
            "auth.dni_nie": _TAX_ID,
            "auth.clave_movil_route": "qr",
        },
    )
    configure_operator_auth("clave_movil")
    state = workflow_state_repository().load()

    with override_settings(cadrumo_clave_movil_dni_nie=None):
        readiness = build_auth_readiness(
            state,
            provider_kind=AuthProviderKind.CLAVE_MOVIL,
            provider_kind_is_authoritative=True,
            requested_provider=None,
            probe_live_backend=True,
            credential_bucket_id=_BUCKET_ID,
            certificate_credentials=None,
        )

    assert readiness.provider == "clave_movil"
    assert readiness.configured is True


def test_alignment_reports_a_match_for_a_profile_borne_credential() -> None:
    """The five-way alignment ladder has to see the resolved identity.

    A profile whose Cl@ve credential equals its tax identity is aligned.
    Reading the empty setting instead would classify it
    ``clave_identity_missing`` and send the operator to configure a
    credential that is already correct.
    """

    _register_profile(**{"auth.dni_nie": _TAX_ID})
    with override_settings(cadrumo_clave_movil_dni_nie=None) as settings:
        profile_present, provider_present, alignment = _live_auth_identity_state(
            AuthProviderKind.CLAVE_MOVIL,
            settings=settings,
        )

    assert profile_present is True
    assert provider_present is True
    assert alignment == "matches"


def test_alignment_still_reports_a_mismatch_it_should_catch() -> None:
    """Resolving from the profile must not blunt the mismatch signal.

    A Cl@ve credential that disagrees with the profile's tax identity is
    the case the fail-closed guard exists for, so the probe has to keep
    naming it even when the credential came from the profile.
    """

    _register_profile(**{"auth.dni_nie": _OTHER_TAX_ID})
    with override_settings(cadrumo_clave_movil_dni_nie=None) as settings:
        _profile_present, _provider_present, alignment = _live_auth_identity_state(
            AuthProviderKind.CLAVE_MOVIL,
            settings=settings,
        )

    assert alignment == "mismatch"


def test_alignment_still_reports_an_absent_credential() -> None:
    """A profile with no credential anywhere is genuinely unconfigured.

    The guard against over-reporting: resolving profile-first must not
    invent a credential where neither source holds one.
    """

    _register_profile()
    with override_settings(cadrumo_clave_movil_dni_nie=None) as settings:
        _profile_present, provider_present, alignment = _live_auth_identity_state(
            AuthProviderKind.CLAVE_MOVIL,
            settings=settings,
        )

    assert provider_present is False
    assert alignment == "clave_identity_missing"


def test_identity_kind_classifies_a_profile_borne_credential() -> None:
    """The DNI/NIE classifier must see the resolved identity too.

    Reading the empty setting would report ``invalid_or_missing`` for a
    perfectly well-formed DNI the profile carries.
    """

    _register_profile(**{"auth.dni_nie": _TAX_ID})
    with override_settings(cadrumo_clave_movil_dni_nie=None) as settings:
        kind = _live_auth_identity_kind(AuthProviderKind.CLAVE_MOVIL, settings=settings)

    assert kind == "DNI"


def test_login_precondition_admits_a_profile_borne_credential() -> None:
    """Login must not refuse a credential the session entry would use.

    This is the sharpest form of the divergence: the precondition ran
    before the session entry resolved anything, so a profile-only
    operator was refused at the door by the very check meant to spare
    them a failed AEAT round-trip.
    """

    _register_profile(**{"auth.dni_nie": _TAX_ID})
    with override_settings(cadrumo_clave_movil_dni_nie=None) as settings:
        _assert_login_precondition(settings, AuthProviderKind.CLAVE_MOVIL)


def test_login_precondition_still_refuses_when_no_credential_exists() -> None:
    """The refusal has to survive: neither source holds an identity."""

    from ..operator_results import AuthLoginPreconditionError

    _register_profile()
    with (
        override_settings(cadrumo_clave_movil_dni_nie=None) as settings,
        pytest.raises(AuthLoginPreconditionError) as raised,
    ):
        _assert_login_precondition(settings, AuthProviderKind.CLAVE_MOVIL)

    assert raised.value.translated_message == "application.auth.operator.login.refused_clave_movil_identity_unset"


def test_settings_still_win_when_the_profile_carries_nothing() -> None:
    """The environment-configured operator keeps their reported state.

    The fallback is what makes this change safe to land, so it is
    asserted at the probe surface too rather than only at the session
    entry.
    """

    _register_profile()
    with override_settings(cadrumo_clave_movil_dni_nie=SecretStr(_TAX_ID)) as settings:
        _profile_present, provider_present, alignment = _live_auth_identity_state(
            AuthProviderKind.CLAVE_MOVIL,
            settings=settings,
        )

    assert provider_present is True
    assert alignment == "matches"


def test_preflight_reports_a_profile_borne_soporte_as_configured() -> None:
    """The preflight contraste booleans must see the profile too.

    ``nie_soporte_configured`` is what tells the operator whether the
    non-QR route can complete. Computed from settings alone it read
    false for a NIE holder whose soporte sits on the encrypted profile,
    while live authentication resolved it fine.
    """

    _register_profile(**{"auth.dni_nie": _TAX_ID, "auth.numero_soporte": "E12345678"})
    with override_settings(
        cadrumo_clave_movil_dni_nie=None,
        cadrumo_clave_movil_nie_soporte=None,
        cadrumo_clave_movil_dni_fecha=None,
    ):
        report = build_live_auth_preflight_report(AuthProviderKind.CLAVE_MOVIL.value)

    assert report.nie_soporte_configured is True
    assert report.dni_fecha_configured is False


def test_preflight_reports_a_profile_borne_validity_date_as_configured() -> None:
    """The DNI holder's mirror of the same report field."""

    _register_profile(**{"auth.dni_nie": _TAX_ID, "auth.fecha_validez": "2030-01-01"})
    with override_settings(
        cadrumo_clave_movil_dni_nie=None,
        cadrumo_clave_movil_nie_soporte=None,
        cadrumo_clave_movil_dni_fecha=None,
    ):
        report = build_live_auth_preflight_report(AuthProviderKind.CLAVE_MOVIL.value)

    assert report.dni_fecha_configured is True
    assert report.nie_soporte_configured is False


def test_preflight_still_reports_an_absent_contraste() -> None:
    """Neither source holds a contraste, so both booleans stay false.

    The guard against over-reporting: resolving profile-first must not
    manufacture a contraste the operator never recorded.
    """

    _register_profile(**{"auth.dni_nie": _TAX_ID})
    with override_settings(
        cadrumo_clave_movil_dni_nie=None,
        cadrumo_clave_movil_nie_soporte=None,
        cadrumo_clave_movil_dni_fecha=None,
    ):
        report = build_live_auth_preflight_report(AuthProviderKind.CLAVE_MOVIL.value)

    assert report.dni_fecha_configured is False
    assert report.nie_soporte_configured is False


def test_preflight_report_carries_no_identity_material() -> None:
    """The redaction posture must survive the resolver change.

    The report gained a profile read, so this pins that what it gained
    is booleans only: neither the identity nor either contraste value
    may appear anywhere in the serialised report.
    """

    soporte = "E12345678"
    _register_profile(**{"auth.dni_nie": _TAX_ID, "auth.numero_soporte": soporte})
    with override_settings(
        cadrumo_clave_movil_dni_nie=None,
        cadrumo_clave_movil_nie_soporte=None,
        cadrumo_clave_movil_dni_fecha=None,
    ):
        report = build_live_auth_preflight_report(AuthProviderKind.CLAVE_MOVIL.value)

    serialised = report.model_dump_json()
    assert soporte not in serialised
    assert _TAX_ID not in serialised


def test_certificate_provider_is_not_probed_for_clave_credentials() -> None:
    """A certificate profile has no Cl@ve credential to resolve."""

    _register_profile(**{"auth.dni_nie": _TAX_ID})
    assert probe_clave_credentials(AuthProviderKind.CERTIFICATE, settings=load_settings()) is None


_isolated_backend = bucket_session_storage_fixture(_BUCKET_ID)
