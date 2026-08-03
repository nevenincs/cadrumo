"""When the manager offers the censal pull, and what it says when it cannot.

The pull is the reason the profile screen exists: AEAT publishes the
taxpayer's censal state, and an operator should not retype it. What makes
the action worth testing is not the read - that needs a live authenticated
session - but the two decisions around it.

The first is the gate. Live navigation can push a Cl@ve prompt to the
operator's phone, so an action that opened a browser and only then
discovered the credentials were incomplete would spend their second
factor on nothing. The gate refuses first and says what is missing.

What "complete" means is the load-bearing part. There are already two
surfaces deciding whether a credential is sufficient, and making them
agree took a whole step; a third opinion here would drift from the entry
that actually authenticates, and the action would then either refuse a
working setup or promise a pull that fails at the browser. So the gate
asks the same predicate the authentication page asks, and these cases pin
that it tracks the route rather than the mode - a QR operator carrying no
contraste is ready, because the route they will use never reads one.

The second is the report. A field where AEAT disagrees with a declared
answer is the reconciliation working, not a failure, so all three
outcomes are counted and the diverging paths are named.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import AnyHttpUrl

from .....adapters.outbound.aeat.sede import CensalDatosResult, CensalDomicilio, CensalIdentity
from .....application.user_profile import (
    CensalReconciliation,
    EffectiveFact,
    apply_censal_read,
    censal_facts_from_read,
    profile_create_storage_span,
    reconcile_censal_read,
)
from .....application.workflow import workflow_state_repository
from .....core import AuthProviderKind
from .....core.config import override_settings
from .....domain.user_profile import UserProfileFact
from .....tests.secure_sql import isolated_profile_storage_root
from .....tests.user_profile import register_minimal_profile
from .._manager_actions import (
    _AUTH_DNI_NIE_PATH,
    _AUTH_PROVIDER_PATH,
    _AUTH_SOPORTE_PATH,
    _censal_pull_summary,
    _censal_pull_unavailable,
    _commit_auth_choice,
    _split_divergences,
    manager_actions,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_PROFILE_ID = "44444444-4444-4444-8444-444444444444"

_NO_CLAVE_SETTINGS = {
    "cadrumo_clave_movil_dni_nie": None,
    "cadrumo_clave_movil_nie_soporte": None,
    "cadrumo_clave_movil_dni_fecha": None,
    "cadrumo_clave_permanente_dni_nie": None,
}
"""Settings carrying no Cl@ve credential, so the profile is the only source.

Without this the host's own environment could satisfy a credential a
refusal case means to leave absent.
"""


@pytest.fixture(name="active_profile")
def _active_profile(tmp_path: Path) -> Iterator[None]:
    """Stand up a real encrypted profile bucket for the gate cases."""
    from .....application import wizard as _wizard_catalogue

    assert _wizard_catalogue.WIZARD_FLOWS, "importing the wizard must register its compiled flows"

    with isolated_profile_storage_root(tmp_path=tmp_path), profile_create_storage_span(_PROFILE_ID):
        workflow_state_repository().update(
            lambda state: register_minimal_profile(state, profile_id=_PROFILE_ID),
        )
        yield


def _record_auth(**values: str) -> None:
    """Put an auth answer on the real profile, through the action's own door."""
    _commit_auth_choice({_AUTH_DNI_NIE_PATH: "", _AUTH_SOPORTE_PATH: "", **values})


def test_the_pull_is_offered_beside_the_other_manager_actions() -> None:
    """A capability nothing offers is not a capability."""
    assert "censal-pull" in [action.key for action in manager_actions()]


def test_the_pull_is_offered_after_the_action_that_unblocks_it() -> None:
    """Order is guidance: identify first, then read, then take a copy away."""
    keys = [action.key for action in manager_actions()]
    assert keys.index("certificate") < keys.index("censal-pull"), (
        "the authentication action must come before the pull it gates"
    )


def test_the_pull_offers_no_way_to_aim_the_read_at_anybody() -> None:
    """The taxpayer is the authenticated session's own identity, deliberately.

    A subject parameter anywhere on this path would be a way to ask AEAT
    for someone else's censal data, so the absence is the safety
    property and is pinned rather than assumed.

    This is one half of that property. It fixes WHOSE census the read
    describes - the authenticated session's, with no way to redirect it.
    The other half is that the reconciliation refuses a read describing
    anyone but the profile's own taxpayer, below in
    ``test_a_read_for_a_different_taxpayer_is_refused_outright``. Both are
    load-bearing: this one means a session cannot be aimed elsewhere, that
    one means a read obtained some other way is not adopted anyway.
    Removing either leaves the remaining test still passing while the
    composition no longer holds.
    """
    import inspect

    from .....application.live import pull_censal_datos
    from .. import _manager_actions

    assert not inspect.signature(pull_censal_datos).parameters, (
        "the read takes its subject from the session; a parameter would be a way to redirect it"
    )
    assert not inspect.signature(_manager_actions._run_censal_pull).parameters, (
        "the action must not accept a subject either"
    )


def test_the_pull_commits_through_the_single_censal_apply_authority() -> None:
    """One ``CENSO_APPLIED`` per commit, and no parallel write path.

    The artefact door, the CLI verb and this action all reconcile through
    ``apply_cotejo``; a direct fact write here would skip the event and
    put a second opinion on the same reconciliation.
    """
    import inspect

    from .. import _manager_actions

    source = inspect.getsource(_manager_actions._run_censal_pull)
    assert "apply_censal_read(state, read)" in source, "the commit routes through the censal apply authority"
    assert "set_active_fields(" not in source, "a direct fact write would bypass the single apply authority"
    assert "apply_cotejo(" not in source, "the action reaches apply_cotejo through apply_censal_read, not around it"


@pytest.mark.usefixtures("active_profile")
def test_a_profile_with_no_provider_chosen_cannot_pull_yet() -> None:
    """Nothing can authenticate, so say so rather than open a browser."""
    assert _censal_pull_unavailable() is not None


@pytest.mark.usefixtures("active_profile")
def test_an_incomplete_clave_setup_cannot_pull_yet() -> None:
    """The non-QR route needs a contraste, and this profile has neither form."""
    _record_auth(**{_AUTH_PROVIDER_PATH: AuthProviderKind.CLAVE_MOVIL.value, _AUTH_DNI_NIE_PATH: "00000000T"})

    with override_settings(cadrumo_clave_prefer_non_qr=True, **_NO_CLAVE_SETTINGS):
        assert _censal_pull_unavailable() is not None


@pytest.mark.usefixtures("active_profile")
def test_a_qr_operator_carrying_no_contraste_is_ready_to_pull() -> None:
    """The gate tracks the route, not the mode.

    This is the regression that matters: a gate demanding a contraste
    unconditionally would refuse the default QR flow, which is the same
    defect the authentication page carried one layer up.
    """
    _record_auth(**{_AUTH_PROVIDER_PATH: AuthProviderKind.CLAVE_MOVIL.value, _AUTH_DNI_NIE_PATH: "00000000T"})

    with override_settings(cadrumo_clave_prefer_non_qr=False, **_NO_CLAVE_SETTINGS):
        assert _censal_pull_unavailable() is None


@pytest.mark.usefixtures("active_profile")
def test_a_complete_non_qr_operator_is_ready_to_pull() -> None:
    _record_auth(
        **{
            _AUTH_PROVIDER_PATH: AuthProviderKind.CLAVE_MOVIL.value,
            _AUTH_DNI_NIE_PATH: "00000000T",
            _AUTH_SOPORTE_PATH: "ABC123456",
        },
    )

    with override_settings(cadrumo_clave_prefer_non_qr=True, **_NO_CLAVE_SETTINGS):
        assert _censal_pull_unavailable() is None


@pytest.mark.usefixtures("active_profile")
def test_the_certificate_mode_is_ready_without_any_clave_credential() -> None:
    """The session entry asks nothing of it either, so neither does this gate."""
    _record_auth(**{_AUTH_PROVIDER_PATH: AuthProviderKind.CERTIFICATE.value})

    with override_settings(cadrumo_clave_prefer_non_qr=True, **_NO_CLAVE_SETTINGS):
        assert _censal_pull_unavailable() is None


@pytest.mark.usefixtures("active_profile")
def test_a_read_for_a_different_taxpayer_is_refused_outright() -> None:
    """The identity of the profile is not something a pull may touch.

    Found while building the re-pull case, where a fixture NIF that did
    not match the profile's produced a puzzling divergence. The
    reconciliation now refuses the whole read rather than reporting one
    row, which is the stronger contract: a read belonging to someone else
    has nothing to reconcile, and adopting any part of it would write one
    taxpayer's data onto another's profile.

    The manager surfaces this rather than crashing on it - the screen
    catches an action's refusal and renders it as a line, so an operator
    sees the reason instead of losing the page.

    This is the second half of the pull's safety property, paired with
    ``test_the_pull_offers_no_way_to_aim_the_read_at_anybody`` above. That
    one fixes whose census is fetched; this one fixes whose census may be
    adopted. The comparison is made against the identity carried IN THE
    READ, never against the session - ``reconcile_censal_read`` takes no
    session parameter and cannot consult one. So the session selects the
    SUBJECT of the read and cannot influence whether the read is ACCEPTED,
    which is why a session bound to another taxpayer cannot write their
    data onto this profile: it yields their census, and this refuses it.
    """
    from .....application.user_profile import CensalIdentityMismatchError

    record = workflow_state_repository().load().active_profile_record()

    with pytest.raises(CensalIdentityMismatchError):
        reconcile_censal_read(record, censal_facts_from_read(_read(nif=_FOREIGN_NIF)), incoming_identity=_FOREIGN_NIF)


def _profile_tax_id() -> str:
    """Return the NIF the active profile declares.

    A real authenticated read returns the session's own taxpayer, so a
    fixture whose NIF differs from the profile's is not a re-pull, it is
    a different person - and the reconciliation would rightly say so.
    """
    record = workflow_state_repository().load().active_profile_record()
    assert record is not None
    return str(next(fact.value for fact in record.facts if fact.path == "identity.tax_id"))


#: A checksum-VALID identity belonging to somebody other than the fixture
#: profile, whose NIF is an 8-digit one derived from its id. Validity is
#: load-bearing: the ownership guard canonicalises both sides through the
#: shared tax-id authority, so a fabricated identity refuses as malformed and
#: the refusal below would pass without ever testing that the read belongs to
#: a DIFFERENT taxpayer.
_FOREIGN_NIF = "X1234567L"


def _read(*, codigo_postal: str = "08032", nif: str = _FOREIGN_NIF) -> CensalDatosResult:
    """Build a censal read with the shape the consulta surface renders."""
    domicilio = CensalDomicilio(
        tipo_via="CALLE",
        nombre_via="MAYOR",
        tipo_numero="NUM",
        numero_casa="1",
        codigo_postal=codigo_postal,
        municipio="BARCELONA",
        provincia="BARCELONA",
    )
    return CensalDatosResult(
        identity=CensalIdentity(nif=nif, apellidos_y_nombre="SANITIZED SURNAME GIVEN"),
        domicilio_fiscal=domicilio,
        domicilio_notificacion=domicilio,
        captured_at=datetime(2026, 7, 25, 12, 0, tzinfo=UTC),
        source_url=AnyHttpUrl(_censal_source_url()),
    )


def _censal_source_url() -> str:
    """Build the consulta URL from configuration rather than pinning a host.

    A literal here would assert a specific numbered host serves the
    censal launcher, which is a claim this fixture is in no position to
    make and which nothing exercises, because the read needs a live
    session. Composing it from the configured suffix and path keeps the
    fixture true whichever host actually answers.
    """
    from .....core.config import Settings

    aeat = Settings.external_constants().aeat
    return f"https://{aeat.domains.host_suffix}{aeat.sede_paths.censal_datos}"


def test_the_summary_counts_all_three_outcomes() -> None:
    """Unchanged is derived, because the reconciliation reports only changes.

    A read that agrees with the profile emits neither an adoption nor a
    divergence, so an operator told only those two would see a pull that
    appears to have done nothing at all.
    """
    reconciliation = CensalReconciliation(
        adopted=(UserProfileFact(path="contact.postcode", value="08032"),),
        divergences=(("contact.fiscal_address", "CALLE MAYOR 1"),),
    )

    summary = _censal_pull_summary(reconciliation, read_count=5, declared={}, labels={})

    assert "1" in summary, "one field was filled in"
    assert "3" in summary, "five read, one adopted and one diverging leaves three already matching"


def test_the_fiscal_identity_is_never_reported_as_an_outcome() -> None:
    """The projection carries the identity, but it is not one of the three.

    ``censal_facts_from_read`` emits ``identity.tax_id`` so the ownership
    guard has an input. The reconciliation consumes it and passes over
    it, so a count derived by subtracting the two decided sets from
    everything read sweeps the identity into "already matching" - telling
    the operator AEAT corroborated it. On a first read onto a profile
    carrying no identity the guard deliberately allows the read through,
    so nothing was corroborated, and it is the one row an operator cannot
    check because both sides render as hashes.

    Reported by censo-pull-verb, which hit the same construction in the
    CLI verb and fixed it there.
    """
    identity = UserProfileFact(path="identity.tax_id", value="00000000T")
    postcode = UserProfileFact(path="contact.postcode", value="08032")

    # The identity's presence must not move any of the three counts, so
    # the summary is identical with and without it. Under a subtraction
    # across everything read it shifts one field out of "already
    # matching" and into "filled in", which is what this pins.
    without = _censal_pull_summary(
        CensalReconciliation(adopted=(postcode,), divergences=()),
        read_count=2,
        declared={},
        labels={},
    )
    with_identity = _censal_pull_summary(
        CensalReconciliation(adopted=(postcode, identity), divergences=()),
        read_count=2,
        declared={},
        labels={},
    )

    assert with_identity == without, "the fiscal identity must not move any of the three counts"
    assert "identity.tax_id" not in with_identity
    assert _split_divergences(
        CensalReconciliation(adopted=(), divergences=(("identity.tax_id", "00000000T"),)),
        {},
    ) == ((), ()), "an identity divergence is not an outcome either"


def test_a_cleared_path_is_reported_apart_from_a_declared_disagreement() -> None:
    """A deletion is an answer, and it does not read like a declaration.

    "AEAT differs from what you declared" describes an answer the
    operator never gave when they deliberately emptied the field, and a
    row rendering their side would show a blank that looks like a fault
    rather than their deletion being honoured. The two states get
    separate wording, matching the vocabulary the CLI verb uses.
    """
    reconciliation = CensalReconciliation(
        adopted=(),
        divergences=(("contact.postcode", "08032"), ("contact.fiscal_address", "CALLE MAYOR 1")),
    )
    declared = {
        # Emptied by the operator: the deletion is their answer.
        "contact.postcode": EffectiveFact(value=None, source="manual_cli"),
        "contact.fiscal_address": EffectiveFact(value="OTRA CALLE 9", source="manual_cli"),
    }

    summary = _censal_pull_summary(
        reconciliation,
        read_count=2,
        declared=declared,
        labels={"contact.postcode": "Código postal", "contact.fiscal_address": "Domicilio fiscal"},
    )
    cleared, contested = _split_divergences(reconciliation, declared)

    assert cleared == ("contact.postcode",)
    assert contested == ("contact.fiscal_address",)
    # The split is asserted by path because that is what the reconciliation
    # deals in; the summary is asserted by label because that is what the
    # operator reads. Passing no labels here would let the summary fall
    # back to paths and the counts would still hold, which would quietly
    # pin the rendering this reports on.
    assert summary.count("Código postal") == 1, "the cleared field is named once, in its own sentence"
    assert summary.count("Domicilio fiscal") == 1
    assert "contact.postcode" not in summary, "a dotted path is not a name the operator has seen"
    assert "contact.fiscal_address" not in summary


def test_a_path_the_operator_never_set_is_not_treated_as_cleared() -> None:
    """Never-set and emptied are different states and must stay so.

    A path with no fact at all is adopted rather than diverging, so it
    should not reach the split; if one ever does, it is a declared
    disagreement rather than a deletion the operator made.
    """
    reconciliation = CensalReconciliation(adopted=(), divergences=(("contact.postcode", "08032"),))

    cleared, contested = _split_divergences(reconciliation, {})

    assert cleared == ()
    assert contested == ("contact.postcode",)


def test_the_summary_names_a_disagreement_the_way_the_page_names_it() -> None:
    """A divergence the operator cannot locate is not a report.

    Locating it means reading a name they have seen before. The page shows
    a label per row, so the summary names the field by that label; the
    dotted path is how the record addresses a value and is not something
    the operator was ever shown.
    """
    reconciliation = CensalReconciliation(
        adopted=(),
        divergences=(("contact.fiscal_address", "CALLE MAYOR 1"),),
    )

    summary = _censal_pull_summary(
        reconciliation,
        read_count=1,
        declared={},
        labels={"contact.fiscal_address": "Domicilio fiscal"},
    )

    assert "Domicilio fiscal" in summary, "the operator is told which field disagrees, in the page's words"
    assert "contact.fiscal_address" not in summary, "the dotted path is not a name the operator has ever seen"


def test_a_field_with_no_label_is_still_reported_by_its_path() -> None:
    """Silence about a contradicted value would be worse than an obscure name.

    A path missing from the projection has no label to show, and dropping
    it would leave AEAT disagreeing with a stored value the operator is
    never told about.
    """
    reconciliation = CensalReconciliation(
        adopted=(),
        divergences=(("contact.fiscal_address", "CALLE MAYOR 1"),),
    )

    summary = _censal_pull_summary(reconciliation, read_count=1, declared={}, labels={})

    assert "contact.fiscal_address" in summary, "an unlabelled divergence must still be named"


def test_a_clean_pull_says_nothing_about_divergences() -> None:
    """Naming a disagreement that did not happen trains operators to ignore the line."""
    reconciliation = CensalReconciliation(
        adopted=(UserProfileFact(path="contact.postcode", value="08032"),),
        divergences=(),
    )

    assert "contact." not in _censal_pull_summary(reconciliation, read_count=1, declared={}, labels={})


@pytest.mark.usefixtures("active_profile")
def test_a_read_matching_the_profile_is_neither_adopted_nor_diverging() -> None:
    """The unchanged axis is real, not a rounding artefact of the other two.

    Reconciled against a profile already carrying exactly what AEAT
    returns, every projected fact falls into the third outcome, so a
    summary derived from the other two has to report it.
    """
    read = _read(nif=_profile_tax_id())
    repository = workflow_state_repository()

    state = repository.load()
    first = reconcile_censal_read(
        state.active_profile_record(),
        censal_facts_from_read(read),
        incoming_identity=read.identity.nif,
    )
    assert first.adopted, "a blank profile must adopt the read"
    repository.save(apply_censal_read(state, read))

    # The same read again, now against the record that holds it.
    again = reconcile_censal_read(
        repository.load().active_profile_record(),
        censal_facts_from_read(read),
        incoming_identity=read.identity.nif,
    )
    assert again.adopted == (), "nothing to adopt when the record already agrees"
    assert again.divergences == (), "agreement is not a disagreement"
    assert _censal_pull_summary(again, read_count=len(first.adopted), declared={}, labels={}) is not None, (
        "a pull that changed nothing still has something to report"
    )
