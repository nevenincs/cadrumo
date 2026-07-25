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

from collections.abc import Iterator
from pathlib import Path

import pytest
from pydantic import SecretStr

from ....core import AuthProviderKind
from ....core.config import override_settings
from ....tests.secure_sql import isolated_profile_storage_root
from ....tests.user_profile import register_minimal_profile
from ...user_profile import profile_create_storage_span
from ...workflow import workflow_state_repository
from .._sessions import ClaveCredentialsIncompleteError, _prepare_clave_auth

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "22222222-2222-4222-8222-222222222222"
_PROFILE_LABEL = "clave-operator"
_TAX_ID = "12345678Z"
_OTHER_TAX_ID = "00000001R"
_SOPORTE = "E12345678"


def _register_profile(**overrides: str) -> None:
    facts = {"identity.tax_id": _TAX_ID}
    facts.update(overrides)
    workflow_state_repository().update(
        lambda state: register_minimal_profile(
            state,
            profile_id=_BUCKET_ID,
            display_name=_PROFILE_LABEL,
            overrides=facts,
        ),
    )


def test_profile_dni_nie_wins_over_settings_and_reaches_the_provider() -> None:
    """A profile that carries the credential is the authority.

    The settings value is deliberately a different identity, so a pass
    here cannot be explained by the fallback: the resolved identity and
    the settings the provider reads must both carry the profile's value.
    """

    _register_profile(**{"auth.dni_nie": _TAX_ID})
    with override_settings(cadrumo_clave_movil_dni_nie=SecretStr(_OTHER_TAX_ID)) as settings:
        bound, expected_identity = _prepare_clave_auth(settings, AuthProviderKind.CLAVE_MOVIL)

    assert expected_identity == _TAX_ID
    assert bound.cadrumo_clave_movil_dni_nie is not None
    assert bound.cadrumo_clave_movil_dni_nie.get_secret_value() == _TAX_ID


def test_settings_remain_the_fallback_when_the_profile_carries_nothing() -> None:
    """The environment-configured path must keep working untouched.

    The profile holds no ``auth`` section at all, which is the shape every
    profile created before the section existed has.
    """

    _register_profile()
    with override_settings(cadrumo_clave_movil_dni_nie=SecretStr(_TAX_ID)) as settings:
        bound, expected_identity = _prepare_clave_auth(settings, AuthProviderKind.CLAVE_MOVIL)

    assert expected_identity == _TAX_ID
    assert bound is settings


def test_profile_numero_soporte_reaches_the_non_qr_contraste_setting() -> None:
    """The numero de soporte is the contraste the non-QR form types in.

    It is read from :class:`Settings` by the page flow, so a profile-borne
    soporte is inert until it lands on that field.
    """

    _register_profile(**{"auth.dni_nie": _TAX_ID, "auth.numero_soporte": _SOPORTE})
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

    _register_profile(**{"auth.dni_nie": _TAX_ID})
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

    _register_profile()
    with (
        override_settings(cadrumo_clave_movil_dni_nie=None) as settings,
        pytest.raises(ClaveCredentialsIncompleteError) as raised,
    ):
        _prepare_clave_auth(settings, AuthProviderKind.CLAVE_MOVIL)

    assert raised.value.translated_message == "application.auth.sessions.errors.clave_identity_missing"
    assert raised.value.context == {"provider": "clave_movil"}


def test_non_qr_route_without_a_contraste_refuses_before_the_browser_opens() -> None:
    """The non-QR form needs a contraste and cannot proceed without one.

    Refusing here is the point of the change: the operator learns what is
    missing at the entry to the session rather than part-way through an
    AEAT form.
    """

    _register_profile(**{"auth.dni_nie": _TAX_ID})
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

    _register_profile(**{"auth.dni_nie": _TAX_ID})
    with override_settings(
        cadrumo_clave_movil_dni_nie=SecretStr(_TAX_ID),
        cadrumo_clave_movil_nie_soporte=None,
        cadrumo_clave_movil_dni_fecha=None,
        cadrumo_clave_prefer_non_qr=False,
    ) as settings:
        _bound, expected_identity = _prepare_clave_auth(settings, AuthProviderKind.CLAVE_MOVIL)

    assert expected_identity == _TAX_ID


def test_dni_validity_date_satisfies_the_contraste_for_a_dni_holder() -> None:
    """A DNI holder's contraste is the validity date, not a soporte number.

    The profile schema carries only the soporte, so a DNI holder supplies
    the date through settings; the refusal must accept that as the
    contraste rather than demanding a soporte the document does not have.
    """

    _register_profile(**{"auth.dni_nie": _TAX_ID})
    with override_settings(
        cadrumo_clave_movil_dni_nie=SecretStr(_TAX_ID),
        cadrumo_clave_movil_nie_soporte=None,
        cadrumo_clave_movil_dni_fecha="2030-01-01",
        cadrumo_clave_prefer_non_qr=True,
    ) as settings:
        _bound, expected_identity = _prepare_clave_auth(settings, AuthProviderKind.CLAVE_MOVIL)

    assert expected_identity == _TAX_ID


def test_clave_permanente_resolves_its_identity_from_the_profile() -> None:
    """Cl@ve Permanente reads its own DNI/NIE setting, not the movil one.

    Its password stays environment-only - the profile schema declares no
    field for it - so only the identity half is bound here.
    """

    _register_profile(**{"auth.dni_nie": _TAX_ID})
    with override_settings(cadrumo_clave_permanente_dni_nie=None) as settings:
        bound, expected_identity = _prepare_clave_auth(settings, AuthProviderKind.CLAVE_PERMANENTE)

    assert bound.cadrumo_clave_permanente_dni_nie is not None
    assert bound.cadrumo_clave_permanente_dni_nie.get_secret_value() == _TAX_ID
    # The movil field is left exactly as the caller had it, whatever the
    # ambient environment configured, so the two providers cannot bleed
    # one taxpayer's identity into the other's login form.
    assert bound.cadrumo_clave_movil_dni_nie == settings.cadrumo_clave_movil_dni_nie
    # Only Cl@ve Móvil binds a session to the profile identity today, so
    # the permanente path returns no expected identity to assert against.
    assert expected_identity is None


def test_certificate_provider_needs_neither_clave_field() -> None:
    """The certificate provider authenticates with an installed certificate.

    It must not be refused for absent Cl@ve credentials, and it must not
    have its settings rewritten.
    """

    _register_profile()
    with override_settings(cadrumo_clave_movil_dni_nie=None) as settings:
        bound, expected_identity = _prepare_clave_auth(settings, AuthProviderKind.CERTIFICATE)

    assert bound is settings
    assert expected_identity is None


@pytest.fixture(autouse=True)
def _isolated_backend(tmp_path: Path) -> Iterator[None]:
    with (
        isolated_profile_storage_root(tmp_path=tmp_path),
        profile_create_storage_span(_BUCKET_ID),
    ):
        yield
