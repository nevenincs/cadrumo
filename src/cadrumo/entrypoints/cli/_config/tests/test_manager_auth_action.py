"""What the manager's authentication page offers, and what it refuses.

The page exists so an operator can say how they identify to AEAT without
leaving the profile they are looking at. Authenticating is what lets the
rest of the profile be filled in from what AEAT already holds, so the
credentials belong beside the data they unlock rather than in a dotenv
file the operator has to find and edit.

Two properties carry that, and both are pinned here.

The first is that the page is reachable at all. It used to refuse
outright when no certificate was registered, which locked out precisely
the operator it was built for: someone setting up through the screen who
authenticates with Cl@ve and needs no certificate. The mode and both
Cl@ve fields are now unconditional, and the certificate row is the only
part that depends on one being registered.

The second is that a Cl@ve mode missing a credential is refused here,
naming the absent field, rather than at the first pull, by which point
the operator has forgotten which page asked for it.

The page cases run the real ``FormApp`` under Textual's ``Pilot`` against
the real page the action builds. Rendered prose is never asserted: it is
locale data, and pinning it would test the catalogue rather than the
page. The refusal cases instead pin the CORRESPONDENCE between two
surfaces, that the name in the refusal is the very label the field
carried, which no choice of words can satisfy by accident.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from pathlib import Path

import pytest
from textual.widgets import DataTable

from .....adapters.inbound.tui import FormApp, FormPage
from .....application.user_profile import ProfileRepository, profile_create_storage_span
from .....application.workflow import workflow_state_repository
from .....core import AuthProviderKind, require_active_bucket_id
from .....core.i18n import tr
from .....tests.secure_sql import isolated_profile_storage_root
from .....tests.user_profile import register_minimal_profile
from .._manager_actions import (
    _AUTH_DNI_NIE_PATH,
    _AUTH_PROVIDER_PATH,
    _AUTH_SOPORTE_PATH,
    _CERTIFICATE_KEY,
    _auth_form_page,
    _commit_auth_choice,
    _missing_clave_credentials,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_TERMINAL_SIZE = (140, 60)
"""Wide enough that every row is on-screen, so a Pilot click lands."""

_PROFILE_ID = "22222222-2222-4222-8222-222222222222"

_SUPPORTED_LOCALES = ("en", "es", "ca", "hu")
"""Every catalogue the refusal has to be able to render."""


def _page(
    *,
    on_record: Mapping[str, str] | None = None,
    certificate_names: tuple[str, ...] = (),
    active_certificate: str = "",
) -> FormPage:
    return _auth_form_page(
        on_record=on_record or {},
        certificate_names=certificate_names,
        active_certificate=active_certificate,
    )


def _rows(app: FormApp) -> dict[str, str]:
    """Read the page as the operator sees it: row key to displayed value."""
    table: DataTable[str] = app.query_one("#form-table", DataTable)
    return {str(row_key.value): str(table.get_row(row_key)[1]) for row_key in table.rows}


def _label_of(page: FormPage, key: str) -> str:
    """Return the label the page gave one field."""
    for field in page.fields:
        if field.key == key:
            return field.label
    message = f"page has no field {key!r}; it offers {[field.key for field in page.fields]}"
    raise AssertionError(message)


@pytest.mark.asyncio
async def test_the_page_is_reachable_when_no_certificate_is_registered() -> None:
    """The defect this action carried: it refused rather than opened.

    Returning "no certificates registered" and stopping blocked an
    operator who wants Cl@ve and needs no certificate at all, which is
    the common case for someone setting up through this screen.
    """
    app = FormApp(_page(certificate_names=()))
    async with app.run_test(size=_TERMINAL_SIZE) as pilot:
        await pilot.pause()
        assert list(_rows(app)) == [_AUTH_PROVIDER_PATH, _AUTH_DNI_NIE_PATH, _AUTH_SOPORTE_PATH]
        assert _CERTIFICATE_KEY not in _rows(app), "an empty choice list must not become a dead row"
        app.exit(None)


@pytest.mark.asyncio
async def test_a_registered_certificate_adds_a_row_opened_on_the_active_one() -> None:
    app = FormApp(_page(certificate_names=("work", "personal"), active_certificate="personal"))
    async with app.run_test(size=_TERMINAL_SIZE) as pilot:
        await pilot.pause()
        rows = _rows(app)
        assert list(rows) == [
            _AUTH_PROVIDER_PATH,
            _AUTH_DNI_NIE_PATH,
            _AUTH_SOPORTE_PATH,
            _CERTIFICATE_KEY,
        ]
        assert rows[_CERTIFICATE_KEY] == "personal"
        app.exit(None)


@pytest.mark.asyncio
async def test_the_page_opens_on_the_auth_values_the_profile_already_holds() -> None:
    """Seeding is what makes this an edit rather than a retype."""
    app = FormApp(
        _page(
            on_record={
                _AUTH_PROVIDER_PATH: AuthProviderKind.CLAVE_PERMANENTE.value,
                _AUTH_DNI_NIE_PATH: "00000000T",
                _AUTH_SOPORTE_PATH: "ABC123456",
            },
        ),
    )
    async with app.run_test(size=_TERMINAL_SIZE) as pilot:
        await pilot.pause()
        rows = _rows(app)
        assert rows[_AUTH_PROVIDER_PATH] == AuthProviderKind.CLAVE_PERMANENTE.value
        assert rows[_AUTH_DNI_NIE_PATH] == "00000000T"
        assert rows[_AUTH_SOPORTE_PATH] == "ABC123456"
        app.exit(None)


@pytest.mark.asyncio
async def test_an_unanswered_profile_opens_on_a_mode_it_can_actually_use() -> None:
    """Certificate registration needs a file and a secret through another verb.

    An operator arriving here has, by construction, not done that, so
    opening on the certificate mode would offer a mode they cannot
    complete from this page.
    """
    app = FormApp(_page(on_record={}))
    async with app.run_test(size=_TERMINAL_SIZE) as pilot:
        await pilot.pause()
        assert _rows(app)[_AUTH_PROVIDER_PATH] != AuthProviderKind.CERTIFICATE.value
        app.exit(None)


@pytest.mark.asyncio
async def test_committing_hands_back_every_auth_path_the_action_writes() -> None:
    """The page's output has to carry exactly what the commit half reads."""
    app = FormApp(
        _page(
            on_record={
                _AUTH_PROVIDER_PATH: AuthProviderKind.CLAVE_MOVIL.value,
                _AUTH_DNI_NIE_PATH: "00000000T",
                _AUTH_SOPORTE_PATH: "ABC123456",
            },
        ),
    )
    async with app.run_test(size=_TERMINAL_SIZE) as pilot:
        await pilot.pause()
        await pilot.click("#btn-form-save")
        await pilot.pause()
    assert app.collected is not None
    assert dict(app.collected) == {
        _AUTH_PROVIDER_PATH: AuthProviderKind.CLAVE_MOVIL.value,
        _AUTH_DNI_NIE_PATH: "00000000T",
        _AUTH_SOPORTE_PATH: "ABC123456",
    }


def test_a_clave_mode_missing_both_credentials_names_both_by_their_page_label() -> None:
    """The refusal points at rows the operator just looked at.

    Naming the profile paths instead would send them hunting for a field
    label that does not exist on the page.
    """
    page = _page()
    missing = _missing_clave_credentials(
        AuthProviderKind.CLAVE_MOVIL.value,
        {_AUTH_PROVIDER_PATH: AuthProviderKind.CLAVE_MOVIL.value, _AUTH_DNI_NIE_PATH: "", _AUTH_SOPORTE_PATH: "  "},
    )
    assert missing == (_label_of(page, _AUTH_DNI_NIE_PATH), _label_of(page, _AUTH_SOPORTE_PATH))


@pytest.mark.parametrize(
    ("dni_nie", "numero_soporte", "absent_path"),
    [
        ("", "ABC123456", _AUTH_DNI_NIE_PATH),
        ("00000000T", "", _AUTH_SOPORTE_PATH),
    ],
)
def test_a_clave_mode_missing_one_credential_names_only_that_one(
    dni_nie: str,
    numero_soporte: str,
    absent_path: str,
) -> None:
    missing = _missing_clave_credentials(
        AuthProviderKind.CLAVE_PERMANENTE.value,
        {_AUTH_DNI_NIE_PATH: dni_nie, _AUTH_SOPORTE_PATH: numero_soporte},
    )
    assert missing == (_label_of(_page(), absent_path),)


def test_a_complete_clave_answer_is_short_of_nothing() -> None:
    assert (
        _missing_clave_credentials(
            AuthProviderKind.CLAVE_MOVIL.value,
            {_AUTH_DNI_NIE_PATH: "00000000T", _AUTH_SOPORTE_PATH: "ABC123456"},
        )
        == ()
    )


def test_the_certificate_mode_needs_neither_clave_credential() -> None:
    """A certificate authenticates on its own, so blank Cl@ve fields are fine."""
    assert (
        _missing_clave_credentials(
            AuthProviderKind.CERTIFICATE.value,
            {_AUTH_DNI_NIE_PATH: "", _AUTH_SOPORTE_PATH: ""},
        )
        == ()
    )


@pytest.mark.parametrize("locale", _SUPPORTED_LOCALES)
def test_every_catalogue_renders_the_refusal_with_the_missing_names_in_it(locale: str) -> None:
    """A refusal that drops what is missing is no better than a bare "invalid".

    This also catches the catalogue defect the honesty ratchet cannot: a
    leaf left holding its own key renders the key back, so an operator on
    that locale meets a dotted identifier instead of a sentence.
    """
    key = "flows.manager.action.auth_clave_incomplete"
    sentinel = "SENTINEL-CREDENTIAL-NAME"
    rendered = tr(key, locale=locale, missing=sentinel)
    assert sentinel in rendered, f"{locale} drops the missing names: {rendered!r}"
    assert rendered != key, f"{locale} still holds its own key as the value"
    assert "%{" not in rendered, f"{locale} left a placeholder uninterpolated: {rendered!r}"


@pytest.fixture(name="active_profile")
def _active_profile(tmp_path: Path) -> Iterator[None]:
    """Stand up a real encrypted profile bucket for the commit cases.

    The file secret-store backend is what makes this reachable on a host
    with no usable OS keychain, which is every automated lane.

    Importing the wizard package is the same precondition the CLI
    bootstrap establishes before any verb runs: compiling its catalogue
    pushes the profile keys that the active-profile health assessment
    behind ``configure_operator_auth`` reads. A test driving the action
    directly has to stand that up, or it fails on a missing registry
    rather than on the behaviour under test.
    """
    from .....application import wizard as _wizard_catalogue

    assert _wizard_catalogue.WIZARD_FLOWS, "importing the wizard must register its compiled flows"

    with isolated_profile_storage_root(tmp_path=tmp_path), profile_create_storage_span(_PROFILE_ID):
        workflow_state_repository().update(
            lambda state: register_minimal_profile(state, profile_id=_PROFILE_ID),
        )
        yield


def _auth_facts() -> Mapping[str, object]:
    """Return every stored ``auth.*`` fact, keeping a cleared one as ``None``.

    Values are read as the record holds them rather than coerced to text,
    so a fact cleared to ``None`` stays distinguishable from one storing
    an empty string.
    """
    record = ProfileRepository().load(require_active_bucket_id()).record
    return {fact.path: fact.value for fact in record.facts if fact.path.startswith("auth.")}


@pytest.mark.usefixtures("active_profile")
def test_committing_writes_the_auth_section_into_the_encrypted_profile() -> None:
    """The credentials land on the profile, which is the whole point.

    A dotenv cannot hold a second profile's different credentials, and an
    operator setting up through the screen cannot edit one at all.
    """
    chosen = _commit_auth_choice(
        {
            _AUTH_PROVIDER_PATH: AuthProviderKind.CLAVE_MOVIL.value,
            _AUTH_DNI_NIE_PATH: "00000000T",
            _AUTH_SOPORTE_PATH: "ABC123456",
        },
    )

    assert chosen == "", "no certificate was offered, so none can have been selected"
    assert _auth_facts() == {
        _AUTH_PROVIDER_PATH: AuthProviderKind.CLAVE_MOVIL.value,
        _AUTH_DNI_NIE_PATH: "00000000T",
        _AUTH_SOPORTE_PATH: "ABC123456",
    }


@pytest.mark.usefixtures("active_profile")
def test_the_written_provider_is_the_one_the_session_will_authenticate_with() -> None:
    """Recording the choice and activating it are one operation, not two.

    A profile that says Cl@ve Permanente while the workflow still
    authenticates as something else is the drift this action exists to
    prevent.
    """
    _commit_auth_choice(
        {
            _AUTH_PROVIDER_PATH: AuthProviderKind.CLAVE_PERMANENTE.value,
            _AUTH_DNI_NIE_PATH: "00000000T",
            _AUTH_SOPORTE_PATH: "ABC123456",
        },
    )

    state = workflow_state_repository().load()
    assert state.auth.provider == AuthProviderKind.CLAVE_PERMANENTE.value
    assert _auth_facts()[_AUTH_PROVIDER_PATH] == AuthProviderKind.CLAVE_PERMANENTE.value


@pytest.mark.usefixtures("active_profile")
def test_a_blank_credential_clears_its_fact_rather_than_storing_an_empty_string() -> None:
    """Not-answered and answered-as-empty must stay one state, not two.

    Switching to the certificate mode after a Cl@ve setup must not leave
    an empty string behind that later reads as an answered field.
    """
    _commit_auth_choice(
        {
            _AUTH_PROVIDER_PATH: AuthProviderKind.CLAVE_MOVIL.value,
            _AUTH_DNI_NIE_PATH: "00000000T",
            _AUTH_SOPORTE_PATH: "ABC123456",
        },
    )
    _commit_auth_choice(
        {
            _AUTH_PROVIDER_PATH: AuthProviderKind.CERTIFICATE.value,
            _AUTH_DNI_NIE_PATH: "",
            _AUTH_SOPORTE_PATH: "   ",
        },
    )

    facts = _auth_facts()
    assert facts.get(_AUTH_PROVIDER_PATH) == AuthProviderKind.CERTIFICATE.value
    assert facts.get(_AUTH_DNI_NIE_PATH) is None
    assert facts.get(_AUTH_SOPORTE_PATH) is None


def test_the_commit_uses_the_plural_door_and_selects_before_activating() -> None:
    """Two routing properties no reachable input can distinguish.

    The plural ``set_active_fields`` write is one atomic call, so a loop
    of single writes would leave a provider recorded with half its
    credentials after a mid-way failure -- but a failure part-way through
    that loop is not something a caller can provoke here.

    The ordering is the same shape: selecting the certificate before
    activating the provider means the provider is never briefly active
    with nothing behind it, and "briefly" is a window no assertion from
    outside the call can observe.

    Both are therefore pinned by reading the source, the same way the
    censo file door pins its single-apply-authority routing.
    """
    import inspect

    from .. import _manager_actions

    source = inspect.getsource(_manager_actions._commit_auth_choice)
    assert "set_active_fields(state, facts)" in source, "the plural door is the only sanctioned write"
    assert "set_active_field(" not in source, "a loop of single writes drops the atomicity"
    assert source.index("select_operator_certificate_source(") < source.index("configure_operator_auth("), (
        "the certificate must be selected before the provider is activated"
    )
