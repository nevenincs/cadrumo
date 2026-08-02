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
authenticates with Cl@ve and needs no certificate. The mode and every
Cl@ve field are now unconditional, and the certificate row is the only
part that depends on one being registered.

The second is that the page asks for what the chosen route actually
reads, and no more. Every Cl@ve mode needs the DNI or NIE. The contraste
beside it is read only by the non-QR fallback and its form follows the
document, so it is required exactly on that route and either the soporte
or the validity date satisfies it; Cl@ve Permanente's second half is a
password that never becomes a profile fact. Demanding both halves from
every Cl@ve mode refused the default QR flow and Permanente outright,
which is the flow-breaking refusal these cases exist to prevent.

The page cases run the real ``FormApp`` under Textual's ``Pilot`` against
the real page the action builds. Rendered prose is never asserted: it is
locale data, and pinning it would test the catalogue rather than the
page. The refusal cases instead pin the CORRESPONDENCE between two
surfaces, that the name in the refusal is the very label the field
carried, which no choice of words can satisfy by accident.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from datetime import date
from pathlib import Path

import pytest
from textual.widgets import DataTable

from .....adapters.inbound.tui import FormApp, FormPage
from .....application.user_profile import ProfileRepository, profile_create_storage_span
from .....application.workflow import workflow_state_repository
from .....core import AuthProviderKind, require_active_bucket_id
from .....core.config import override_settings
from .....core.i18n import tr
from .....domain.user_profile import ProfileSchemaValidationError
from .....tests.secure_sql import isolated_profile_storage_root
from .....tests.user_profile import register_minimal_profile
from .._manager_actions import (
    _AUTH_DNI_NIE_PATH,
    _AUTH_FECHA_VALIDEZ_PATH,
    _AUTH_PROFILE_PATHS,
    _AUTH_PROVIDER_PATH,
    _AUTH_SOPORTE_PATH,
    _CERTIFICATE_KEY,
    _auth_facts_on_record,
    _auth_form_page,
    _clave_refusal,
    _commit_auth_choice,
    _run_certificate,
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
        assert list(_rows(app)) == list(_AUTH_PROFILE_PATHS)
        assert _CERTIFICATE_KEY not in _rows(app), "an empty choice list must not become a dead row"
        app.exit(None)


@pytest.mark.asyncio
async def test_a_registered_certificate_adds_a_row_opened_on_the_active_one() -> None:
    app = FormApp(_page(certificate_names=("work", "personal"), active_certificate="personal"))
    async with app.run_test(size=_TERMINAL_SIZE) as pilot:
        await pilot.pause()
        rows = _rows(app)
        assert list(rows) == [*_AUTH_PROFILE_PATHS, _CERTIFICATE_KEY]
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
    """The page's output has to carry exactly what the commit half reads.

    The expectation is derived from the path tuple the commit half
    iterates, so a fifth path added to one side and not the other fails
    here rather than passing against a literal this test wrote for
    itself.
    """
    values = {
        _AUTH_PROVIDER_PATH: AuthProviderKind.CLAVE_MOVIL.value,
        _AUTH_DNI_NIE_PATH: "00000000T",
        _AUTH_SOPORTE_PATH: "ABC123456",
        _AUTH_FECHA_VALIDEZ_PATH: "1990-01-01",
    }
    seeded = {path: values.get(path, "seeded") for path in _AUTH_PROFILE_PATHS}
    app = FormApp(_page(on_record=seeded))
    async with app.run_test(size=_TERMINAL_SIZE) as pilot:
        await pilot.pause()
        await pilot.click("#btn-form-save")
        await pilot.pause()
    assert app.collected is not None
    assert dict(app.collected) == seeded
    assert set(app.collected) == set(_AUTH_PROFILE_PATHS), "the page and the commit half must agree on the path set"


_NO_CLAVE_SETTINGS: Mapping[str, object] = {
    "cadrumo_clave_movil_dni_nie": None,
    "cadrumo_clave_movil_nie_soporte": None,
    "cadrumo_clave_movil_dni_fecha": None,
    "cadrumo_clave_permanente_dni_nie": None,
}
"""Settings carrying no Cl@ve credential, so the page answer is the only source.

Without this the host's own environment could satisfy a credential the
case means to leave absent, and the refusal case would pass for the wrong
reason.
"""


def _answer(**values: str) -> dict[str, str]:
    """Build a committed page answer, defaulting every auth path to blank."""
    answer = dict.fromkeys(_AUTH_PROFILE_PATHS, "")
    answer.update(values)
    return answer


def test_the_qr_route_does_not_ask_for_a_contraste_it_never_reads() -> None:
    """The default Cl@ve Movil route is QR, which reads no contraste.

    Demanding one anyway refused a setup that authenticates perfectly
    well, which is the flow-breaking refusal D1a corrects.
    """
    with override_settings(cadrumo_clave_prefer_non_qr=False, **_NO_CLAVE_SETTINGS):
        assert (
            _clave_refusal(
                _answer(**{_AUTH_PROVIDER_PATH: AuthProviderKind.CLAVE_MOVIL.value, _AUTH_DNI_NIE_PATH: "00000000T"}),
            )
            is None
        )


def test_clave_permanente_is_never_asked_for_a_contraste() -> None:
    """Permanente's second half is a password, not a contraste.

    It lives in the secret store beside the certificate passphrase and is
    never a profile fact, so no page answer can supply it and refusing
    for its absence locks the mode out entirely.
    """
    with override_settings(cadrumo_clave_prefer_non_qr=True, **_NO_CLAVE_SETTINGS):
        assert (
            _clave_refusal(
                _answer(
                    **{
                        _AUTH_PROVIDER_PATH: AuthProviderKind.CLAVE_PERMANENTE.value,
                        _AUTH_DNI_NIE_PATH: "00000000T",
                    },
                ),
            )
            is None
        )


@pytest.mark.parametrize(
    "provider",
    [AuthProviderKind.CLAVE_MOVIL, AuthProviderKind.CLAVE_PERMANENTE],
)
def test_every_clave_mode_needs_the_identity_and_the_refusal_names_it(provider: AuthProviderKind) -> None:
    """The DNI/NIE identifies the person, so no Cl@ve route works without it."""
    with override_settings(cadrumo_clave_prefer_non_qr=False, **_NO_CLAVE_SETTINGS):
        refusal = _clave_refusal(_answer(**{_AUTH_PROVIDER_PATH: provider.value}))
    assert refusal is not None
    assert _label_of(_page(), _AUTH_DNI_NIE_PATH) in refusal, "the refusal must name the row the operator saw"


def test_the_non_qr_route_refuses_when_neither_contraste_form_is_present() -> None:
    with override_settings(cadrumo_clave_prefer_non_qr=True, **_NO_CLAVE_SETTINGS):
        refusal = _clave_refusal(
            _answer(**{_AUTH_PROVIDER_PATH: AuthProviderKind.CLAVE_MOVIL.value, _AUTH_DNI_NIE_PATH: "00000000T"}),
        )
    assert refusal is not None
    assert _label_of(_page(), _AUTH_DNI_NIE_PATH) not in refusal, "the identity is present; this is the contraste gap"


@pytest.mark.parametrize("contraste_path", [_AUTH_SOPORTE_PATH, _AUTH_FECHA_VALIDEZ_PATH])
def test_either_contraste_form_satisfies_the_non_qr_route(contraste_path: str) -> None:
    """Cl@ve asks a NIE holder for the soporte and a DNI holder for the date.

    Exactly one of the two is expected, so requiring the soporte
    specifically would lock out every DNI holder.
    """
    with override_settings(cadrumo_clave_prefer_non_qr=True, **_NO_CLAVE_SETTINGS):
        assert (
            _clave_refusal(
                _answer(
                    **{
                        _AUTH_PROVIDER_PATH: AuthProviderKind.CLAVE_MOVIL.value,
                        _AUTH_DNI_NIE_PATH: "00000000T",
                        contraste_path: "VALUE",
                    },
                ),
            )
            is None
        )


def test_a_credential_supplied_through_settings_is_not_refused_at_the_page() -> None:
    """The page must not refuse what the session entry would authenticate with.

    An operator who configured Cl@ve through the environment keeps
    working; the profile takes precedence over settings rather than
    replacing them.
    """
    with override_settings(
        cadrumo_clave_prefer_non_qr=True,
        cadrumo_clave_movil_dni_nie="00000000T",
        cadrumo_clave_movil_nie_soporte="ABC123456",
        cadrumo_clave_movil_dni_fecha=None,
        cadrumo_clave_permanente_dni_nie=None,
    ):
        assert _clave_refusal(_answer(**{_AUTH_PROVIDER_PATH: AuthProviderKind.CLAVE_MOVIL.value})) is None


def test_the_certificate_mode_needs_neither_clave_credential() -> None:
    """A certificate authenticates on its own, so blank Cl@ve fields are fine."""
    with override_settings(cadrumo_clave_prefer_non_qr=True, **_NO_CLAVE_SETTINGS):
        assert _clave_refusal(_answer(**{_AUTH_PROVIDER_PATH: AuthProviderKind.CERTIFICATE.value})) is None


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


@pytest.mark.parametrize("locale", _SUPPORTED_LOCALES)
@pytest.mark.parametrize(
    "key",
    ["flows.manager.action.auth_contraste_missing", "flows.manager.action.auth_fecha_validez"],
)
def test_the_contraste_strings_are_translated_in_every_catalogue(locale: str, key: str) -> None:
    """A leaf holding its own key renders a dotted path at the operator.

    The honesty ratchet compares locales against English and so cannot
    see a key that is untranslated in English too; reading the leaf back
    is what catches it.
    """
    rendered = tr(key, locale=locale)
    assert rendered != key, f"{locale} still holds {key} as its own value"
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
    answer = {
        _AUTH_PROVIDER_PATH: AuthProviderKind.CLAVE_MOVIL.value,
        _AUTH_DNI_NIE_PATH: "00000000T",
        _AUTH_SOPORTE_PATH: "ABC123456",
        _AUTH_FECHA_VALIDEZ_PATH: "1990-01-01",
    }
    chosen, configure_result = _commit_auth_choice(answer)

    assert chosen == "", "no certificate was offered, so none can have been selected"
    assert configure_result.provider == AuthProviderKind.CLAVE_MOVIL.value
    assert _auth_facts() == {
        _AUTH_PROVIDER_PATH: AuthProviderKind.CLAVE_MOVIL.value,
        _AUTH_DNI_NIE_PATH: "00000000T",
        _AUTH_SOPORTE_PATH: "ABC123456",
        # The schema declares this one a date, so the record holds a typed
        # date rather than the text the operator typed.
        _AUTH_FECHA_VALIDEZ_PATH: date(1990, 1, 1),
    }


@pytest.mark.usefixtures("active_profile")
def test_a_stored_date_seeds_the_page_as_text_the_operator_can_resubmit() -> None:
    """The one path whose stored type is not the type the page shows.

    `fecha_validez` is declared a date, so it comes back off the record as
    a typed date while every other auth path comes back as text. If the
    page seeded it in any other form the operator would reopen the screen,
    see something they did not type, and re-submitting it would be refused
    by the same schema that accepted it.
    """
    _commit_auth_choice(
        {
            _AUTH_PROVIDER_PATH: AuthProviderKind.CLAVE_MOVIL.value,
            _AUTH_DNI_NIE_PATH: "00000000T",
            _AUTH_SOPORTE_PATH: "",
            _AUTH_FECHA_VALIDEZ_PATH: "1990-01-01",
        },
    )

    assert _auth_facts_on_record()[_AUTH_FECHA_VALIDEZ_PATH] == "1990-01-01"


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
            _AUTH_FECHA_VALIDEZ_PATH: "1990-01-01",
        },
    )
    _commit_auth_choice(
        {
            _AUTH_PROVIDER_PATH: AuthProviderKind.CERTIFICATE.value,
            _AUTH_DNI_NIE_PATH: "",
            _AUTH_SOPORTE_PATH: "   ",
            _AUTH_FECHA_VALIDEZ_PATH: "  ",
        },
    )

    facts = _auth_facts()
    assert facts.get(_AUTH_PROVIDER_PATH) == AuthProviderKind.CERTIFICATE.value
    assert facts.get(_AUTH_DNI_NIE_PATH) is None
    assert facts.get(_AUTH_SOPORTE_PATH) is None
    assert facts.get(_AUTH_FECHA_VALIDEZ_PATH) is None


@pytest.mark.usefixtures("active_profile")
def test_a_refused_clave_answer_writes_nothing_at_all() -> None:
    """The refusal promises "Nothing was saved", so nothing may be saved.

    Driven through the whole action rather than its refusal half, because
    the promise is about what the action does after refusing, and
    statement order alone is not evidence of that.
    """
    with override_settings(cadrumo_clave_prefer_non_qr=True, **_NO_CLAVE_SETTINGS):
        outcome = _run_certificate(
            lambda _page: _answer(**{_AUTH_PROVIDER_PATH: AuthProviderKind.CLAVE_MOVIL.value}),
        )

    assert outcome.overview is None, "a refusal must not redraw the page as though something changed"
    assert _auth_facts() == {}, "a refused answer must leave the record untouched"
    assert workflow_state_repository().load().auth.provider is None


@pytest.mark.usefixtures("active_profile")
def test_an_accepted_answer_reaches_the_record_through_the_whole_action() -> None:
    """The other half of the same door: an acceptable answer does land."""
    with override_settings(cadrumo_clave_prefer_non_qr=False, **_NO_CLAVE_SETTINGS):
        outcome = _run_certificate(
            lambda _page: _answer(
                **{
                    _AUTH_PROVIDER_PATH: AuthProviderKind.CLAVE_MOVIL.value,
                    _AUTH_DNI_NIE_PATH: "00000000T",
                },
            ),
        )

    assert outcome.overview is not None, "a committed change must redraw the page"
    assert _auth_facts()[_AUTH_DNI_NIE_PATH] == "00000000T"


@pytest.mark.usefixtures("active_profile")
def test_abandoning_the_page_writes_nothing() -> None:
    """Leaving without committing is "make no change", not an error."""
    outcome = _run_certificate(lambda _page: None)

    assert outcome.overview is None
    assert _auth_facts() == {}


@pytest.mark.usefixtures("active_profile")
def test_a_value_the_record_rejects_leaves_the_earlier_facts_written() -> None:
    """The plural door is a loop, so a late rejection half-writes.

    This is the behaviour the page's field validation exists to keep an
    operator away from, and it is pinned here so the docstring's account
    of the remaining failure window stays honest. If profile-fact writes
    ever become transactional this case is what should fail, and the
    docstring it defends is what should then change.
    """
    with pytest.raises(ProfileSchemaValidationError):
        _commit_auth_choice(
            {
                _AUTH_PROVIDER_PATH: AuthProviderKind.CLAVE_MOVIL.value,
                _AUTH_DNI_NIE_PATH: "00000000T",
                _AUTH_SOPORTE_PATH: "ABC123456",
                # The form the document prints, which the schema refuses.
                _AUTH_FECHA_VALIDEZ_PATH: "01/01/1990",
            },
        )

    facts = _auth_facts()
    assert facts.get(_AUTH_DNI_NIE_PATH) == "00000000T", "the earlier facts are already durable"
    assert facts.get(_AUTH_FECHA_VALIDEZ_PATH) is None, "the rejected fact never landed"
    assert workflow_state_repository().load().auth.provider is None, (
        "the provider was never activated, so the two stores now disagree"
    )


def test_the_validity_date_row_refuses_a_malformed_date_before_any_write() -> None:
    """The page is where a bad date has to be caught, not the record.

    Refusing at the row keeps the operator away from the half-write
    above, and names the field they are looking at instead of surfacing a
    schema error through the screen's generic renderer.
    """
    field = next(f for f in _page().fields if f.key == _AUTH_FECHA_VALIDEZ_PATH)
    assert field.validate is not None, "the date row must carry a validator"
    assert field.validate("01/01/1990") is not None, "the printed form must be refused"
    assert field.validate("1990-13-45") is not None, "a non-calendar day must be refused"
    assert field.validate("1990-01-31") is None, "a zero-padded ISO day is what the schema stores"
    assert field.validate("") is None, "blank is not an answer; the write clears the fact"


@pytest.mark.usefixtures("active_profile")
def test_the_certificate_is_selected_before_the_provider_is_activated(tmp_path: Path) -> None:
    """Both writes emit into the same per-bucket catalogue, so the order is durable.

    Activating the provider first would leave it briefly active with no
    certificate behind it. Reading the two events back is the observable
    proof; the source check below it is the second wall, catching a
    reordering that also rewrote this expectation.
    """
    import inspect

    from .....adapters.persistence.profile.buckets import BucketEventHistoryRepository
    from .....application.auth import register_operator_certificate_source
    from .....domain.buckets import BucketEventType
    from .. import _manager_actions

    certificate = tmp_path / "operator.p12"
    certificate.write_bytes(b"placeholder")
    register_operator_certificate_source(name="personal", certificate_path=certificate)

    _commit_auth_choice(
        {
            _AUTH_PROVIDER_PATH: AuthProviderKind.CERTIFICATE.value,
            _AUTH_DNI_NIE_PATH: "",
            _AUTH_SOPORTE_PATH: "",
            _AUTH_FECHA_VALIDEZ_PATH: "",
            _CERTIFICATE_KEY: "personal",
        },
    )

    ordered = [
        event.event_type
        for event in BucketEventHistoryRepository()
        .load()
        .for_bucket(
            require_active_bucket_id(),
            event_types=(
                BucketEventType.AUTH_CERTIFICATE_SOURCE_SELECTED,
                BucketEventType.AUTH_PROVIDER_CONFIGURED,
            ),
        )
    ]
    assert ordered == [
        BucketEventType.AUTH_CERTIFICATE_SOURCE_SELECTED,
        BucketEventType.AUTH_PROVIDER_CONFIGURED,
    ], f"the certificate must be selected before the provider is activated; got {ordered}"

    source = inspect.getsource(_manager_actions._commit_auth_choice)
    assert source.index("select_operator_certificate_source(") < source.index("configure_operator_auth("), (
        "the source order is the second wall behind the event order"
    )


@pytest.mark.usefixtures("active_profile")
def test_run_certificate_surfaces_the_repair_command_when_no_file_is_configured() -> None:
    """An incomplete certificate configuration must name the repair command, not just "done".

    ``configure_operator_auth`` already computes ``complete=False``, a
    missing-file reason, and a concrete ``next_action`` (``aeat config
    auth configure --provider certificate --file PATH``) for this case;
    the manager action must surface it rather than rendering the generic
    "active certificate: -" message the direct CLI uses only for the
    operationally-complete case.
    """
    outcome = _run_certificate(
        lambda _page: _answer(**{_AUTH_PROVIDER_PATH: AuthProviderKind.CERTIFICATE.value}),
    )

    assert tr("application.auth.operator.errors.certificate_file_required") in outcome.message
    assert "aeat config auth configure --provider certificate --file PATH" in outcome.message
    assert outcome.message != tr(
        "flows.manager.action.certificate_done",
        name="-",
        provider=AuthProviderKind.CERTIFICATE.value,
    )


@pytest.mark.usefixtures("active_profile")
def test_run_certificate_reports_the_provider_as_done_when_operationally_complete() -> None:
    """An operationally-complete provider (any non-certificate provider) reaches the "done" message.

    The certificate provider is never operationally complete through this
    manager door today (the selected certificate *source* is read directly
    by the credential resolver rather than mirrored into the ``--file``
    completeness check), so the parity case for "valid" uses the Cl@ve
    Móvil provider, which ``configure_operator_auth`` reports complete
    unconditionally.
    """
    outcome = _run_certificate(
        lambda _page: _answer(
            **{
                _AUTH_PROVIDER_PATH: AuthProviderKind.CLAVE_MOVIL.value,
                _AUTH_DNI_NIE_PATH: "00000000T",
            },
        ),
    )

    assert outcome.message == tr(
        "flows.manager.action.certificate_done",
        name="-",
        provider=AuthProviderKind.CLAVE_MOVIL.value,
    )
