"""Real-behavior tests for profile-borne Cl@ve credential resolution.

The active profile is the authority for the credentials a Cl@ve mode
needs, and the environment settings remain the fallback so an operator who
configured Cl@ve through a dotenv keeps working. Resolution alone is not
enough: the outbound providers read their credentials from
:class:`Settings`, so each test that asserts a profile value wins also
asserts that value reaches the settings the provider will read. Otherwise
the guard would pass and the provider would still refuse for a value the
profile plainly holds.

Every test drives the real profile store through the real lifecycle
service - no test doubles - because the read path this exercises depends
on an unlocked bucket session.
"""

from __future__ import annotations

import pytest
from pydantic import SecretStr

from ....core.auth_provider import AuthProviderKind, ClaveMovilRoute
from ....core.config import override_settings
from ....domain.user_profile.loader import load_user_profile_schema
from ....tests.profile_storage_root_fixture import bucket_session_storage_fixture
from ....tests.user_profile import register_minimal_profile
from ...user_profile.preflight import build_profile_preflight_requirement
from ..sessions import (
    AuthProfileIdentityMismatchError,
    ClaveCredentialsIncompleteError,
    _prepare_clave_auth,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

#: This module's OWN bucket. A bucket shared with a sibling module makes
#: the two suites' isolation fixtures interchangeable and puts both on one
#: bucket-scoped master-key session in the same run.
_BUCKET_ID = "c0000002-0000-4000-8000-000000000002"
_PROFILE_LABEL = "clave-operator"
_TAX_ID = "12345678Z"
_OTHER_TAX_ID = "00000001R"
_SOPORTE = "E12345678"
_FECHA_VALIDEZ = "2030-01-01"


def _register_profile(**overrides: str) -> None:
    facts = {"identity.tax_id": _TAX_ID}
    facts.update(overrides)
    # Seeded ahead of any workflow-state read: the capsule publishes by an
    # atomic no-replace rename onto ``buckets/<profile-id>``, and the workflow
    # repository materialises that same directory on first access.
    register_minimal_profile(
        profile_id=_BUCKET_ID,
        display_name=_PROFILE_LABEL,
        overrides=facts,
    )


def test_profile_dni_nie_wins_over_settings_and_reaches_the_provider() -> None:
    """A profile that carries the credential is the authority.

    The settings value is deliberately a different identity, so a pass
    here cannot be explained by the fallback: the resolved identity and
    the settings the provider reads must both carry the profile's value.
    """

    _register_profile(**{"auth.dni_nie": _TAX_ID, "auth.clave_movil_route": ClaveMovilRoute.QR.value})
    with override_settings(cadrumo_clave_movil_dni_nie=SecretStr(_OTHER_TAX_ID)) as settings:
        bound, expected_identity = _prepare_clave_auth(settings, AuthProviderKind.CLAVE_MOVIL)

    assert expected_identity == _TAX_ID
    assert bound.cadrumo_clave_movil_dni_nie is not None
    assert bound.cadrumo_clave_movil_dni_nie.get_secret_value() == _TAX_ID


def test_settings_remain_the_identity_fallback_when_the_profile_carries_the_required_route() -> None:
    """The environment-configured path must keep working untouched.

    The route remains profile-owned while the identity can still come from
    the current environment configuration.
    """

    _register_profile(**{"auth.clave_movil_route": ClaveMovilRoute.QR.value})
    with override_settings(cadrumo_clave_movil_dni_nie=SecretStr(_TAX_ID)) as settings:
        bound, expected_identity = _prepare_clave_auth(settings, AuthProviderKind.CLAVE_MOVIL)

    assert expected_identity == _TAX_ID
    assert bound.cadrumo_clave_movil_dni_nie == settings.cadrumo_clave_movil_dni_nie
    assert bound.cadrumo_clave_prefer_non_qr is False


def test_missing_profile_route_refuses_even_when_environment_selects_qr() -> None:
    """The route has one authority: the encrypted profile field."""
    _register_profile(**{"auth.dni_nie": _TAX_ID})
    with (
        override_settings(
            cadrumo_clave_movil_dni_nie=SecretStr(_TAX_ID),
            cadrumo_clave_prefer_non_qr=False,
        ) as settings,
        pytest.raises(ClaveCredentialsIncompleteError) as raised,
    ):
        _prepare_clave_auth(settings, AuthProviderKind.CLAVE_MOVIL)

    expected_label = build_profile_preflight_requirement(
        "auth.clave_movil_route",
        schema=load_user_profile_schema(),
    ).label
    assert expected_label != "auth.clave_movil_route"
    assert raised.value.translated_message == "application.auth.sessions.errors.clave_route_missing"
    assert raised.value.context == {"provider": "clave_movil", "route_field": expected_label}


def test_profile_numero_soporte_reaches_the_non_qr_contraste_setting() -> None:
    """The numero de soporte is the contraste the non-QR form types in.

    It is read from :class:`Settings` by the page flow, so a profile-borne
    soporte is inert until it lands on that field.
    """

    _register_profile(
        **{
            "auth.dni_nie": _TAX_ID,
            "auth.numero_soporte": _SOPORTE,
            "auth.clave_movil_route": ClaveMovilRoute.APP_REQUEST.value,
        },
    )
    with override_settings(
        cadrumo_clave_movil_dni_nie=SecretStr(_TAX_ID),
        cadrumo_clave_prefer_non_qr=True,
    ) as settings:
        bound, _expected_identity = _prepare_clave_auth(settings, AuthProviderKind.CLAVE_MOVIL)

    assert bound.cadrumo_clave_movil_nie_soporte is not None
    assert bound.cadrumo_clave_movil_nie_soporte.get_secret_value() == _SOPORTE


def test_rebinding_the_settings_preserves_every_other_secret() -> None:
    """Binding one credential must not mask or drop the rest.

    The rebind revalidates a dumped mapping, and a dump that masked
    secrets would silently replace every unrelated one with asterisks -
    a Cl@ve Permanente password, a certificate passphrase - and the
    failure would surface only as an opaque AEAT login rejection.
    """

    _register_profile(**{"auth.dni_nie": _TAX_ID, "auth.clave_movil_route": ClaveMovilRoute.QR.value})
    with override_settings(
        cadrumo_clave_movil_dni_nie=SecretStr(_OTHER_TAX_ID),
        cadrumo_clave_permanente_password=SecretStr("permanente-password"),
    ) as settings:
        bound, _expected_identity = _prepare_clave_auth(settings, AuthProviderKind.CLAVE_MOVIL)

    assert bound is not settings
    assert bound.cadrumo_clave_permanente_password is not None
    assert bound.cadrumo_clave_permanente_password.get_secret_value() == "permanente-password"


def test_clave_mode_without_any_dni_nie_refuses_naming_the_absent_credential() -> None:
    """Neither the profile nor the settings carry the identity half.

    The refusal has to name what is absent, so the assertion pins the
    canonical locale key rather than an English fragment.
    """

    _register_profile(**{"auth.clave_movil_route": ClaveMovilRoute.QR.value})
    with (
        override_settings(cadrumo_clave_movil_dni_nie=None) as settings,
        pytest.raises(ClaveCredentialsIncompleteError) as raised,
    ):
        _prepare_clave_auth(settings, AuthProviderKind.CLAVE_MOVIL)

    assert raised.value.translated_message == "application.auth.sessions.errors.clave_identity_missing"
    # The refusal names the absent credential by the label the profile editor
    # shows, derived from the schema here rather than spelled out, so this
    # asserts the name is schema-sourced without pinning one wording.
    expected_label = build_profile_preflight_requirement(
        "auth.dni_nie",
        schema=load_user_profile_schema(),
    ).label
    assert expected_label != "auth.dni_nie", "label collapsed to the path; the assertion would be vacuous"
    assert raised.value.context == {"provider": "clave_movil", "identity_field": expected_label}


def test_non_qr_route_without_a_contraste_refuses_before_the_browser_opens() -> None:
    """The non-QR form needs a contraste and cannot proceed without one.

    Refusing here is the point of the change: the operator learns what is
    missing at the entry to the session rather than part-way through an
    AEAT form.
    """

    _register_profile(
        **{"auth.dni_nie": _TAX_ID, "auth.clave_movil_route": ClaveMovilRoute.APP_REQUEST.value},
    )
    with (
        override_settings(
            cadrumo_clave_movil_dni_nie=SecretStr(_TAX_ID),
            cadrumo_clave_movil_nie_soporte=None,
            cadrumo_clave_movil_dni_fecha=None,
            cadrumo_clave_prefer_non_qr=True,
        ) as settings,
        pytest.raises(ClaveCredentialsIncompleteError) as raised,
    ):
        _prepare_clave_auth(settings, AuthProviderKind.CLAVE_MOVIL)

    assert raised.value.translated_message == "application.auth.sessions.errors.clave_contraste_missing"


def test_qr_route_is_not_refused_for_a_missing_contraste() -> None:
    """The QR route never types a contraste, so its absence is not a fault.

    This is the guard against over-refusing: the default Cl@ve Móvil flow
    has no soporte and no validity date configured and must still proceed.
    """

    _register_profile(**{"auth.dni_nie": _TAX_ID, "auth.clave_movil_route": ClaveMovilRoute.QR.value})
    with override_settings(
        cadrumo_clave_movil_dni_nie=SecretStr(_TAX_ID),
        cadrumo_clave_movil_nie_soporte=None,
        cadrumo_clave_movil_dni_fecha=None,
        cadrumo_clave_prefer_non_qr=False,
    ) as settings:
        _bound, expected_identity = _prepare_clave_auth(settings, AuthProviderKind.CLAVE_MOVIL)

    assert expected_identity == _TAX_ID


def test_profile_qr_route_overrides_an_environment_app_request() -> None:
    """The encrypted profile owns the route once the operator chooses it."""
    _register_profile(
        **{
            "auth.dni_nie": _TAX_ID,
            "auth.clave_movil_route": ClaveMovilRoute.QR.value,
        },
    )
    with override_settings(
        cadrumo_clave_movil_dni_nie=SecretStr(_TAX_ID),
        cadrumo_clave_prefer_non_qr=True,
    ) as settings:
        bound, expected_identity = _prepare_clave_auth(settings, AuthProviderKind.CLAVE_MOVIL)

    assert expected_identity == _TAX_ID
    assert bound.cadrumo_clave_prefer_non_qr is False


def test_profile_app_request_route_requires_contraste_and_reaches_provider_settings() -> None:
    """The non-QR choice is both validated and bound onto the live provider."""
    _register_profile(
        **{
            "auth.dni_nie": _TAX_ID,
            "auth.numero_soporte": _SOPORTE,
            "auth.clave_movil_route": ClaveMovilRoute.APP_REQUEST.value,
        },
    )
    with override_settings(
        cadrumo_clave_movil_dni_nie=SecretStr(_TAX_ID),
        cadrumo_clave_prefer_non_qr=False,
    ) as settings:
        bound, expected_identity = _prepare_clave_auth(settings, AuthProviderKind.CLAVE_MOVIL)

    assert expected_identity == _TAX_ID
    assert bound.cadrumo_clave_prefer_non_qr is True


def test_dni_validity_date_from_settings_satisfies_the_contraste() -> None:
    """A DNI holder's contraste is the validity date, not a soporte number.

    The refusal must accept the date as the contraste rather than
    demanding a soporte the document does not have, and the environment
    stays a working source for it.
    """

    _register_profile(
        **{"auth.dni_nie": _TAX_ID, "auth.clave_movil_route": ClaveMovilRoute.APP_REQUEST.value},
    )
    with override_settings(
        cadrumo_clave_movil_dni_nie=SecretStr(_TAX_ID),
        cadrumo_clave_movil_nie_soporte=None,
        cadrumo_clave_movil_dni_fecha=_FECHA_VALIDEZ,
        cadrumo_clave_prefer_non_qr=True,
    ) as settings:
        _bound, expected_identity = _prepare_clave_auth(settings, AuthProviderKind.CLAVE_MOVIL)

    assert expected_identity == _TAX_ID


def test_profile_fecha_validez_carries_a_dni_holder_through_the_non_qr_route() -> None:
    """A DNI holder's contraste now has a home on the profile.

    Until it was declared, only a NIE holder could keep their half on the
    profile and a DNI holder had to fall back to the environment. The
    environment is left empty here, so a pass cannot be explained by the
    fallback: the profile alone has to satisfy the refusal and reach the
    setting the non-QR form types into.
    """

    _register_profile(
        **{
            "auth.dni_nie": _TAX_ID,
            "auth.fecha_validez": _FECHA_VALIDEZ,
            "auth.clave_movil_route": ClaveMovilRoute.APP_REQUEST.value,
        },
    )
    with override_settings(
        cadrumo_clave_movil_dni_nie=SecretStr(_TAX_ID),
        cadrumo_clave_movil_nie_soporte=None,
        cadrumo_clave_movil_dni_fecha=None,
        cadrumo_clave_prefer_non_qr=True,
    ) as settings:
        bound, expected_identity = _prepare_clave_auth(settings, AuthProviderKind.CLAVE_MOVIL)

    assert expected_identity == _TAX_ID
    assert bound.cadrumo_clave_movil_dni_fecha == _FECHA_VALIDEZ


def test_a_profile_carrying_neither_contraste_still_refuses_the_non_qr_route() -> None:
    """Declaring the DNI half must not weaken the refusal.

    A profile with an identity but no contraste of either form is exactly
    the case the non-QR route cannot complete, so it has to stay refused
    now that there are two fields that could satisfy it.
    """

    _register_profile(
        **{"auth.dni_nie": _TAX_ID, "auth.clave_movil_route": ClaveMovilRoute.APP_REQUEST.value},
    )
    with (
        override_settings(
            cadrumo_clave_movil_dni_nie=SecretStr(_TAX_ID),
            cadrumo_clave_movil_nie_soporte=None,
            cadrumo_clave_movil_dni_fecha=None,
            cadrumo_clave_prefer_non_qr=True,
        ) as settings,
        pytest.raises(ClaveCredentialsIncompleteError) as raised,
    ):
        _prepare_clave_auth(settings, AuthProviderKind.CLAVE_MOVIL)

    assert raised.value.translated_message == "application.auth.sessions.errors.clave_contraste_missing"


def test_clave_permanente_resolves_its_identity_from_the_profile() -> None:
    """Cl@ve Permanente reads its own DNI/NIE setting, not the movil one.

    Its password stays environment-only - the profile schema declares no
    field for it - so only the identity half is bound here.
    """

    _register_profile(**{"auth.dni_nie": _TAX_ID, "auth.clave_movil_route": ClaveMovilRoute.QR.value})
    with override_settings(cadrumo_clave_permanente_dni_nie=None) as settings:
        bound, expected_identity = _prepare_clave_auth(settings, AuthProviderKind.CLAVE_PERMANENTE)

    assert bound.cadrumo_clave_permanente_dni_nie is not None
    assert bound.cadrumo_clave_permanente_dni_nie.get_secret_value() == _TAX_ID
    # The movil field is left exactly as the caller had it, whatever the
    # ambient environment configured, so the two providers cannot bleed
    # one taxpayer's identity into the other's login form.
    assert bound.cadrumo_clave_movil_dni_nie == settings.cadrumo_clave_movil_dni_nie
    # Permanente is held to the profile identity like every other mode.
    # It was exempt once, which meant its configured credential was never
    # compared to the profile and the session check downstream had no
    # expectation to compare either.
    assert expected_identity == _TAX_ID


def test_certificate_provider_needs_neither_clave_field() -> None:
    """The certificate provider authenticates with an installed certificate.

    It must not be refused for absent Cl@ve credentials, and it must not
    have its settings rewritten.
    """

    _register_profile()
    with override_settings(cadrumo_clave_movil_dni_nie=None) as settings:
        bound, expected_identity = _prepare_clave_auth(settings, AuthProviderKind.CERTIFICATE)

    assert bound is settings
    # It still carries an expectation. The certificate has no
    # operator-configured credential to check up front, but it does bind
    # a normalised NIF parsed from its subject at session bind, so the
    # profile identity is handed down for that comparison rather than
    # left as None, which would have made the session check no-op.
    assert expected_identity == _TAX_ID


def test_every_provider_carries_an_expectation_for_the_session_check() -> None:
    """The guard promises fail-closed; it must deliver it for each mode.

    It returned early for anything but Cl@ve Movil, so two of three
    providers got no comparison at all - and because the expectation is
    what the downstream session check compares against, returning None
    made that check pass silently rather than skip loudly. A provider
    added later would inherit the same silence, which is why this is
    asserted across the whole enum rather than for the two that were
    missing.
    """

    _register_profile(**{"auth.dni_nie": _TAX_ID, "auth.clave_movil_route": ClaveMovilRoute.QR.value})
    missing: list[str] = []
    for kind in AuthProviderKind:
        with override_settings(
            cadrumo_clave_movil_dni_nie=SecretStr(_TAX_ID),
            cadrumo_clave_permanente_dni_nie=SecretStr(_TAX_ID),
        ) as settings:
            _bound, expected_identity = _prepare_clave_auth(settings, kind)
        if expected_identity != _TAX_ID:
            missing.append(f"{kind.value} -> {expected_identity!r}")

    assert not missing, (
        f"provider(s) returned no profile identity for the session check to compare: {missing}. "
        "A provider with no expectation makes the downstream check pass silently."
    )


def test_a_clave_identity_disagreeing_with_the_profile_is_refused_for_every_clave_mode() -> None:
    """The refusal itself, not just the expectation, covers each Cl@ve mode.

    Permanente previously returned before this comparison, so a
    credential belonging to another taxpayer was accepted without
    complaint on that provider.
    """

    _register_profile(**{"auth.dni_nie": _OTHER_TAX_ID, "auth.clave_movil_route": ClaveMovilRoute.QR.value})
    refused: dict[str, bool] = {}
    for kind in (AuthProviderKind.CLAVE_MOVIL, AuthProviderKind.CLAVE_PERMANENTE):
        with override_settings(
            cadrumo_clave_movil_dni_nie=SecretStr(_OTHER_TAX_ID),
            cadrumo_clave_permanente_dni_nie=SecretStr(_OTHER_TAX_ID),
        ) as settings:
            try:
                _prepare_clave_auth(settings, kind)
            except AuthProfileIdentityMismatchError:
                refused[kind.value] = True
            else:
                refused[kind.value] = False

    assert all(refused.values()), (
        f"a mismatched Cl@ve identity was accepted by: {[k for k, v in refused.items() if not v]}"
    )


_isolated_backend = bucket_session_storage_fixture(_BUCKET_ID)
