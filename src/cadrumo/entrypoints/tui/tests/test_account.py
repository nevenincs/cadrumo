"""Focused composition contracts for the production account utilities."""

from __future__ import annotations

from collections.abc import Awaitable
from typing import cast

import pytest
from textual.app import App

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
    *, appearance: AccountAppearanceFactoryV1 | None = None, sign_out: AccountSignOutFactoryV1 | None = None
):
    """Compose factories with opaque dependencies; factory construction is pure."""

    def default_appearance(_app: App[None]) -> str:
        return "appearance.changed"

    selected_appearance = appearance or default_appearance

    def persist_profile_field(_path: str, _value: str) -> ProfileOverview:
        return cast(ProfileOverview, object())

    def assess_password(_candidate: str) -> ProfilePasswordAssessment:
        return cast(ProfilePasswordAssessment, object())

    async def default_sign_out() -> object:
        return object()

    return compose_account_factories(
        profile_overview=cast(ProfileOverview, object()),
        persist_profile_field=persist_profile_field,
        login_choices=(ProfileLoginChoice(profile_id="profile-1", label="Profile one"),),
        authenticate=lambda _profile_id, _passphrase: ProfileLoginAttempt(),
        assess_password=assess_password,
        rotate_password=lambda _current, _replacement, _confirmation: PassphraseChangeAttempt(),
        sign_out=sign_out or cast(AccountSignOutFactoryV1, default_sign_out),
        appearance=selected_appearance,
    )


def test_account_factories_construct_existing_screens_without_host_effects() -> None:
    """Composition does not read or mutate; each screen remains its prior owner."""
    factories = _factories()
    profile = factories.profile(
        TuiScreenContextV1(
            destination="workbench.profile",
            focus=TuiFocusIdentityV1(destination="workbench.profile", semantic_key="profile.overview"),
        )
    )

    assert isinstance(profile, ProfileManagerScreen)
    assert isinstance(factories.change_user(), LoginScreen)
    assert isinstance(factories.password(), PassphraseScreen)


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
    calls = 0
    expected = object()

    async def sign_out() -> object:
        nonlocal calls
        calls += 1
        return expected

    factories = _factories(sign_out=cast(AccountSignOutFactoryV1, sign_out))
    assert calls == 0

    actual = await cast(Awaitable[object], factories.sign_out())
    assert actual is expected
    assert calls == 1
