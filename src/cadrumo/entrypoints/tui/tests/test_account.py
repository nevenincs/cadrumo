"""Focused composition contracts for the production account utilities."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from types import SimpleNamespace
from typing import NoReturn, cast

import pytest
from textual.app import App

from ....application.user_profile.acquisition_sources import (
    AcquisitionSourceCredentialPostureV1,
    ProfileAcquisitionSourceV1,
)
from ....application.user_profile.login_interaction import ProfileLoginAttempt, ProfileLoginChoice
from ....application.user_profile.overview import ProfileOverview
from ....core.credentials import ProfilePasswordAssessment
from ..account import AccountAppearanceFactoryV1, AccountSignOutFactoryV1, compose_account_factories
from ..navigation import TuiFocusIdentityV1, TuiScreenContextV1
from ..profile.overview import ProfileManagerScreen
from ..secret.login import LoginScreen
from ..secret.passphrase import PassphraseChangeAttempt, PassphraseScreen

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


class _LanguageScreen:
    """Observe delegation to the already-owned Profile language action."""

    opened = False

    def action_choose_language(self) -> None:
        self.opened = True


def _factories(
    *,
    calls: set[str] | None = None,
    appearance: AccountAppearanceFactoryV1 | None = None,
    sign_out: AccountSignOutFactoryV1 | None = None,
    login_choices: Sequence[ProfileLoginChoice] = (ProfileLoginChoice(profile_id="profile-1", label="Profile one"),),
    preselected_profile_id: str | None = None,
    validate_profile_field: Callable[[str, str], str | None] | None = None,
    launch_profile_source: Callable[[ProfileAcquisitionSourceV1], Awaitable[None]] | None = None,
    credential_postures: Sequence[AcquisitionSourceCredentialPostureV1] | None = None,
):
    """Compose factories with opaque dependencies; factory construction is pure."""
    observed_calls = calls if calls is not None else set()

    def _unexpected(name: str) -> NoReturn:
        observed_calls.add(name)
        raise AssertionError(f"{name} ran while composing an account screen")

    def default_appearance(_app: App[None]) -> str:
        return "appearance.changed"

    selected_appearance = appearance or default_appearance

    def persist_profile_field(_path: str, _value: str) -> ProfileOverview:
        _unexpected("persist")

    def assess_password(_candidate: str) -> ProfilePasswordAssessment:
        _unexpected("assess")

    def authenticate(_profile_id: str, _passphrase: str) -> ProfileLoginAttempt:
        _unexpected("authenticate")

    def rotate_password(_current: str, _replacement: str, _confirmation: str) -> PassphraseChangeAttempt:
        _unexpected("rotate")

    async def default_sign_out() -> object:
        return object()

    return compose_account_factories(
        profile_overview=cast(ProfileOverview, object()),
        persist_profile_field=persist_profile_field,
        login_choices=login_choices,
        authenticate=authenticate,
        assess_password=assess_password,
        rotate_password=rotate_password,
        sign_out=sign_out or cast(AccountSignOutFactoryV1, default_sign_out),
        preselected_profile_id=preselected_profile_id,
        validate_profile_field=validate_profile_field,
        launch_profile_source=launch_profile_source,
        credential_postures=credential_postures,
        appearance=selected_appearance,
    )


def test_account_factories_construct_existing_screens_without_host_effects() -> None:
    """Composition does not read or mutate; each screen remains its prior owner."""
    calls: set[str] = set()

    def refuse_appearance(_app: App[None]) -> str:
        calls.add("appearance")
        raise AssertionError("appearance ran while composing an account screen")

    factories = _factories(calls=calls, appearance=refuse_appearance)
    profile = factories.profile(
        TuiScreenContextV1(
            destination="workbench.profile",
            focus=TuiFocusIdentityV1(destination="workbench.profile", semantic_key="profile.overview"),
        )
    )

    assert isinstance(profile, ProfileManagerScreen)
    assert isinstance(factories.change_user(), LoginScreen)
    assert isinstance(factories.password(), PassphraseScreen)
    assert calls == set()


def test_optional_profile_and_login_doors_reach_their_existing_screen_owner() -> None:
    """Optional doors retain the same Profile and Login ownership when composed."""

    def validate(path: str, value: str) -> str | None:
        del path, value
        return None

    async def launch(source: ProfileAcquisitionSourceV1) -> None:
        del source

    posture = SimpleNamespace(source="censal-review")
    factories = _factories(
        login_choices=(
            ProfileLoginChoice(profile_id="profile-1", label="Profile one"),
            ProfileLoginChoice(profile_id="profile-2", label="Profile two"),
        ),
        preselected_profile_id="profile-2",
        validate_profile_field=validate,
        launch_profile_source=launch,
        credential_postures=cast(Sequence[AcquisitionSourceCredentialPostureV1], (posture,)),
    )
    profile = factories.profile(
        TuiScreenContextV1(
            destination="workbench.profile",
            focus=TuiFocusIdentityV1(destination="workbench.profile", semantic_key="profile.overview"),
        )
    )
    login = factories.change_user()

    assert profile._validate_field is validate
    assert profile._launch_source is launch
    assert profile._credential_postures == {"censal-review": posture}
    assert login._preselected == "profile-2"


def test_profile_factory_refuses_another_destination_before_constructing_a_screen() -> None:
    """The route factory cannot accidentally become a second destination owner."""
    factories = _factories()
    context = TuiScreenContextV1(
        destination="workbench.home",
        focus=TuiFocusIdentityV1(destination="workbench.home", semantic_key="home.overview"),
    )

    with pytest.raises(ValueError, match="Profile destination"):
        factories.profile(context)


def test_language_and_appearance_delegates_are_explicit_host_effects() -> None:
    """Language reuses Profile's action and appearance is supplied by the host."""
    observed_apps: list[App[None]] = []

    def change_appearance(app: App[None]) -> str:
        observed_apps.append(app)
        return "appearance.changed"

    factories = _factories(appearance=change_appearance)
    language_screen = _LanguageScreen()
    factories.language(cast(ProfileManagerScreen, language_screen))
    app = cast(App[None], object())

    assert language_screen.opened is True
    assert factories.appearance(app) == "appearance.changed"
    assert observed_apps == [app]


@pytest.mark.asyncio
async def test_sign_out_is_deferred_to_the_injected_operation_factory() -> None:
    """Composing account utilities neither submits nor starts strong close."""
    calls: set[str] = set()
    sign_out_calls = 0
    expected = object()

    async def sign_out() -> object:
        nonlocal sign_out_calls
        sign_out_calls += 1
        return expected

    factories = _factories(calls=calls, sign_out=cast(AccountSignOutFactoryV1, sign_out))
    factories.profile(
        TuiScreenContextV1(
            destination="workbench.profile",
            focus=TuiFocusIdentityV1(destination="workbench.profile", semantic_key="profile.overview"),
        )
    )
    factories.change_user()
    factories.password()
    assert calls == set()
    assert sign_out_calls == 0

    actual = await cast(Awaitable[object], factories.sign_out())
    assert actual is expected
    assert sign_out_calls == 1
