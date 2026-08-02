"""What the profile manager can do besides edit a field.

The manager page answers "what does my profile hold". These are the
operations an operator reaches for while looking at that answer: say how
they identify to AEAT, fill the profile in from what AEAT already holds,
and take a copy of it away. They are offered in that order because it is
the order they depend on each other in - the pull cannot run until the
authentication mode is complete, and says so rather than failing at the
browser.

Each one is a plain callable returning a
:class:`~cadrumo.adapters.inbound.tui.ManagerActionOutcome`, so the screen
never learns what a censal read or a profile bundle is — it renders a
label, calls the callable, and shows the sentence it gets back. That is
the same injected-door arrangement the rest of this seam uses.

Import is deliberately absent. ``aeat config profile import`` feeds
secrets over stdin and threads an atomic-create callback the screen has no
way to supply; a button would either duplicate that orchestration or drop
its guards, and both are worse than sending the operator to the verb.

See Also:
    :mod:`cadrumo.entrypoints.cli._config._manager_frontend`
        The presenter that assembles these into the running screen.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ....core.i18n import tr

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from ....adapters.inbound.tui import FormPage, ManagerAction, ManagerActionOutcome
    from ....application.auth import AuthConfigureResult
    from ....application.user_profile import CensalReconciliation, EffectiveFact, ProfileOverview
    from ....core import AuthProviderKind

_AUTH_PROVIDER_PATH = "auth.provider"
_AUTH_DNI_NIE_PATH = "auth.dni_nie"
_AUTH_SOPORTE_PATH = "auth.numero_soporte"
_AUTH_FECHA_VALIDEZ_PATH = "auth.fecha_validez"

_AUTH_PROFILE_PATHS = (
    _AUTH_PROVIDER_PATH,
    _AUTH_DNI_NIE_PATH,
    _AUTH_SOPORTE_PATH,
    _AUTH_FECHA_VALIDEZ_PATH,
)
"""Every profile path this page collects, in the order it shows them.

The two contraste paths are alternatives rather than a pair: Cl@ve asks a
NIE holder for the numero de soporte and a DNI holder for the document's
validity date, so an operator fills in whichever their document carries.
"""

_VALIDATION_SCRATCH_PROFILE_ID = "00000000-0000-4000-8000-000000000000"
"""Stand-in identity for validating one typed row before it is written.

The validation report is keyed by profile id and refuses anything that is
not a UUID, but a row-level check has no profile yet - the operator is
still typing. Nothing is persisted under this id and no record is read by
it; it exists only to let the page ask the record's own validator what it
thinks of one value.
"""

_CERTIFICATE_KEY = "certificate"
"""Form key for the certificate choice.

Not a profile path: which certificate is active lives in the auth
registry beside the certificate itself, so this row is the one on the
page that does not round-trip through the ``auth`` profile section.
"""


def censal_pull_action() -> ManagerAction:
    """Fill the censal fields in from what AEAT already publishes.

    This is the reason the profile screen exists: AEAT holds the
    taxpayer's censal state at *Mis Datos Censales*, and an operator
    should not retype what the authority already has.
    """
    from ....adapters.inbound.tui import ManagerAction

    return ManagerAction(
        key="censal-pull",
        label=tr("flows.manager.action.censal_pull"),
        label_key="flows.manager.action.censal_pull",
        run=_run_censal_pull,
    )


def _run_censal_pull() -> ManagerActionOutcome:
    """Read the censal consulta and reconcile it onto the active profile.

    A pure read. The reader navigates to the consulta view and parses the
    rendered DOM; it submits nothing, and refuses at runtime if AEAT
    lands it on a modification surface. Nothing on this path can file.

    There is no way to aim the read at anybody: the taxpayer is taken
    from the authenticated session's own identity, so this action offers
    no subject to choose and could not read another person's data if an
    operator asked it to.

    The commit routes through ``apply_censal_read`` onto ``apply_cotejo``,
    the single censal apply authority the CLI verb drives, so one
    ``CENSO_APPLIED`` marks the change and no second write path exists.

    Three things can happen to any field and the operator is told all
    three. A blank path is adopted. A path already carrying the same
    value is unchanged. A path where AEAT disagrees with an answer the
    operator declared is reported and left standing - that is the
    reconciliation working, not a failure. A value a previous pull
    adopted is refreshed rather than reported, because there is no
    operator answer to protect and both sides are the authority's.
    """
    import asyncio

    from ....adapters.inbound.tui import ManagerActionOutcome
    from ....application.live import pull_censal_datos
    from ....application.user_profile import (
        apply_censal_read,
        censal_facts_from_read,
        reconcile_censal_read,
        record_to_effective_facts,
    )
    from ....application.workflow import workflow_state_repository
    from ._manager_frontend import build_active_profile_overview

    unavailable = _censal_pull_unavailable()
    if unavailable is not None:
        # Refuse before the read, not after: the live navigation can push
        # a Cl@ve prompt to the operator's phone, and spending their
        # second factor on a pull that cannot authenticate is worse than
        # telling them what is missing.
        return ManagerActionOutcome(message=unavailable)

    repository = workflow_state_repository()
    state = repository.load()
    read = asyncio.run(pull_censal_datos())
    facts = censal_facts_from_read(read)
    record = state.active_profile_record()
    # Read the effective facts BEFORE the commit: afterwards a cleared
    # path may carry the adopted value and no longer look cleared.
    declared = record_to_effective_facts(record)
    reconciliation = reconcile_censal_read(record, facts, incoming_identity=read.identity.nif)
    # The projection is exactly the adoptable paths now, so every fact it
    # emits is an outcome the operator is told about.
    adoptable_read = len(facts)
    repository.save(apply_censal_read(state, read))

    # Built once and used twice: the summary names the diverging fields
    # the way the page does, and the page itself is what the screen redraws.
    overview = build_active_profile_overview()
    return ManagerActionOutcome(
        message=_censal_pull_summary(
            reconciliation,
            read_count=adoptable_read,
            declared=declared,
            labels=_field_labels(overview),
        ),
        overview=overview,
    )


def _censal_pull_unavailable() -> str | None:
    """Return why the pull cannot run yet, or ``None`` when it can.

    "Ready" here means exactly what the live session entry means by it,
    because it asks the same question through the same predicate the
    authentication page uses. A separate opinion about credential
    sufficiency would drift from the entry that actually authenticates,
    and this action would then either refuse a working setup or promise
    a pull that fails at the browser.

    That the certificate mode passes this gate carrying no Cl@ve half is
    not an oversight: the session entry imposes no Cl@ve requirement on
    it either, and the certificate's own sufficiency is settled where the
    provider loads it.
    """
    on_record = _auth_facts_on_record()
    if not on_record.get(_AUTH_PROVIDER_PATH, "").strip():
        return tr("flows.manager.action.censal_pull_no_provider")
    if _clave_refusal(on_record) is not None:
        return tr("flows.manager.action.censal_pull_auth_incomplete")
    return None


def _censal_pull_summary(
    reconciliation: CensalReconciliation,
    *,
    read_count: int,
    declared: Mapping[str, EffectiveFact],
    labels: Mapping[str, str],
) -> str:
    """Report what the read did to each field, in the operator's terms.

    Unchanged is derived rather than reported by the reconciliation,
    which emits only the two axes that changed something: a field AEAT
    agrees with is neither adopted nor diverging.

    That derivation counts only the ADOPTABLE paths, and the restriction
    is load-bearing rather than tidiness. The projection also carries
    ``identity.tax_id``, which the reconciliation consumes for its
    ownership guard and then passes over - so a subtraction across
    everything read would sweep the fiscal identity into "already
    matching" and tell the operator AEAT had corroborated it. On a first
    read onto a profile carrying no identity the guard deliberately
    allows the read through, so nothing has been corroborated at all,
    and it is the one row an operator cannot check for themselves
    because both sides render as hashes. An ownership check is not an
    outcome of the reconciliation and belongs in none of the three.

    The diverging axis carries two different situations and they do not
    read alike. "You declared X and AEAT says Y" describes an answer the
    operator gave. A path they deliberately CLEARED has no declared
    answer to set against AEAT's value, so the same wording would
    describe a declaration they never made, and a rendering that shows
    their side would show a blank that looks like a fault rather than
    their deletion being honoured. They are reported separately, in the
    vocabulary the CLI verb uses for the same two states.
    """
    from ....application.user_profile import CENSAL_ADOPTABLE_PATHS

    adoptable = frozenset(CENSAL_ADOPTABLE_PATHS)
    adopted = sum(1 for fact in reconciliation.adopted if fact.path in adoptable)
    diverging = sum(1 for path, _ in reconciliation.divergences if path in adoptable)
    parts = [
        tr(
            "flows.manager.action.censal_pull_done",
            adopted=adopted,
            unchanged=read_count - adopted - diverging,
            diverging=diverging,
        ),
    ]
    cleared, contested = _split_divergences(reconciliation, declared)
    if contested:
        parts.append(tr("flows.manager.action.censal_pull_contested", paths=_name_paths(contested, labels)))
    if cleared:
        parts.append(tr("flows.manager.action.censal_pull_cleared", paths=_name_paths(cleared, labels)))
    return " ".join(parts)


def _name_paths(paths: Sequence[str], labels: Mapping[str, str]) -> str:
    """Name each path the way the page names it.

    The operator is being told which of their fields AEAT disagrees with,
    so they are named as the rows they can go and look at. A dotted path
    is how the record addresses a field, not how the page shows it, and it
    is not what the operator was reading when they answered.

    A path with no label falls back to itself rather than being dropped: a
    field missing from the projection is still a divergence they must be
    told about, and an obscure name is better than silence about a value
    AEAT contradicts.
    """
    return ", ".join(labels.get(path, path) for path in paths)


def _field_labels(overview: ProfileOverview) -> Mapping[str, str]:
    """Every field path on the page, mapped to the label shown for it.

    Read from the projection rather than from a table here, so the names
    follow the page: whatever the overview calls a field, including once
    those labels are translated, is what this reports.
    """
    return {field.path: field.label for section in overview.sections for field in section.fields}


def _split_divergences(
    reconciliation: CensalReconciliation,
    declared: Mapping[str, EffectiveFact],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Separate a deletion the operator made from an answer they declared.

    A cleared path is an effective fact whose value is ``None``: the
    operator emptied it, and that deletion is their answer. A path they
    never set at all does not reach here, because the reconciliation
    adopts it.

    Args:
        reconciliation: The split the read produced.
        declared: The effective fact at each path the record holds.

    Returns:
        The cleared paths and the contested paths, in that order.
    """
    from ....application.user_profile import CENSAL_ADOPTABLE_PATHS

    adoptable = frozenset(CENSAL_ADOPTABLE_PATHS)
    cleared: list[str] = []
    contested: list[str] = []
    for path, _incoming in reconciliation.divergences:
        if path not in adoptable:
            continue
        fact = declared.get(path)
        target = cleared if fact is not None and fact.value is None else contested
        target.append(path)
    return tuple(cleared), tuple(contested)


def export_action() -> ManagerAction:
    """Write a passphrase-encrypted portable copy of the profile."""
    from ....adapters.inbound.tui import ManagerAction

    return ManagerAction(
        key="export",
        label=tr("flows.manager.action.export"),
        label_key="flows.manager.action.export",
        run=_run_export,
    )


def _run_export() -> ManagerActionOutcome:
    """Collect a destination and a passphrase, then publish the bundle.

    Encrypted transport is the only one offered here. The cleartext form
    exists for a subject-access request and is gated behind an explicit
    command-line flag precisely so it cannot be reached by pressing a
    button while looking at the data it would expose.
    """
    from pathlib import Path

    from pydantic import SecretStr

    from ....adapters.inbound.tui import FormField, FormPage, ManagerActionOutcome
    from ....application.user_profile import (
        ProfileBundleExportPurpose,
        ProfileBundleExportRequest,
        ProfileBundleExportTransport,
        export_profile_bundle,
    )
    from ._manager_frontend import present_form

    page = FormPage(
        title=tr("flows.manager.action.export"),
        section=tr("flows.manager.action.export"),
        fields=(
            FormField(
                key="destination",
                label=tr("flows.manager.action.export_destination"),
                validate=lambda value: None if value.strip() else tr("flows.manager.action.export_destination"),
            ),
            FormField(
                key="passphrase",
                label=tr("flows.manager.action.export_passphrase"),
                validate=lambda value: None if value.strip() else tr("flows.manager.action.export_passphrase"),
            ),
        ),
    )
    collected = present_form(page)
    if collected is None:
        return ManagerActionOutcome(message=tr("flows.manager.action.abandoned"))
    destination = Path(collected["destination"].strip())
    export_profile_bundle(
        ProfileBundleExportRequest(
            destination=destination,
            purpose=ProfileBundleExportPurpose.PORTABLE_TRANSFER,
            transport=ProfileBundleExportTransport.PASSPHRASE_ENCRYPTED,
            passphrase=SecretStr(collected["passphrase"]),
        ),
    )
    return ManagerActionOutcome(message=tr("flows.manager.action.export_done", destination=str(destination)))


def certificate_action() -> ManagerAction:
    """Choose how this taxpayer authenticates, and with which certificate."""
    from ....adapters.inbound.tui import ManagerAction

    return ManagerAction(
        key="certificate",
        label=tr("flows.manager.action.certificate"),
        label_key="flows.manager.action.certificate",
        run=_run_certificate,
    )


def _run_certificate() -> ManagerActionOutcome:
    """Collect how this taxpayer authenticates, and whatever that mode needs.

    The point of asking here is that authenticating is what lets the
    profile be filled in from what AEAT already holds, so the credentials
    belong on the profile beside the data they unlock — not in a dotenv
    file the operator has to find and edit by hand.

    Cl@ve authenticates the person, so every Cl@ve mode needs their DNI
    or NIE. The contraste beside it is read only by the non-QR fallback,
    and its form follows the document: the numero de soporte for a NIE,
    the validity date for a DNI. The certificate mode needs none of that
    and instead selects among the certificates already registered through
    the CLI verb, which is where a file and a secret belong.

    Everything collected lands in the encrypted profile store under the
    ``auth`` section, never a plain file.

    Args:
        present: The door that shows the page and returns what the
            operator committed, or ``None`` for the real screen. Injected
            so the refusal and commit branches can be driven without a
            terminal, which is the only way to prove that a refused
            answer writes nothing.
    """
    from ....adapters.inbound.tui import ManagerActionOutcome
    from ....application.auth import list_operator_certificate_sources
    from ._manager_frontend import build_active_profile_overview, present_form

    listing = list_operator_certificate_sources()
    collected = present_form(
        _auth_form_page(
            on_record=_auth_facts_on_record(),
            certificate_names=tuple(source.name for source in listing.sources),
            active_certificate=listing.active_source,
        ),
    )
    if collected is None:
        return ManagerActionOutcome(message=tr("flows.manager.action.abandoned"))

    provider = collected[_AUTH_PROVIDER_PATH]
    refusal = _clave_refusal(collected)
    if refusal is not None:
        # Refuse here, naming what is absent, rather than let the
        # operator discover it at the first pull.
        return ManagerActionOutcome(message=refusal)

    chosen_certificate, configure_result = _commit_auth_choice(collected)
    if not configure_result.complete:
        message = tr(
            "flows.manager.action.certificate_incomplete",
            provider=provider,
            reason=configure_result.incomplete_reason,
            next_action=configure_result.next_action,
        )
    else:
        message = tr("flows.manager.action.certificate_done", name=chosen_certificate or "-", provider=provider)
    return ManagerActionOutcome(
        message=message,
        overview=build_active_profile_overview(),
    )


def _auth_form_page(
    *,
    on_record: Mapping[str, str],
    certificate_names: Sequence[str],
    active_certificate: str,
) -> FormPage:
    """Build the page the authentication action shows.

    The mode and every Cl@ve field are offered unconditionally, seeded
    from whatever the profile already holds. Hiding the credential fields
    until a mode was already chosen would make the page unable to set the
    thing it exists to set.

    Both contraste rows are shown rather than one chosen for the
    operator: which applies follows the document in their hand, and the
    page cannot know whether that is a DNI or a NIE. They fill in the one
    theirs carries and leave the other blank.

    The certificate row appears only when a certificate is registered:
    an empty choice list is a dead row, and refusing the whole page for
    want of a certificate — which is what this action used to do — locked
    out every operator who authenticates with Cl@ve and needs no
    certificate at all.

    Args:
        on_record: The ``auth.*`` values the profile already holds, which
            seed the fields so the page opens on the current answer.
        certificate_names: Names of the registered certificate sources.
        active_certificate: The currently selected certificate name, or
            ``""`` when none is selected.

    Returns:
        The :class:`~cadrumo.adapters.inbound.tui.FormPage` to present.
    """
    from ....adapters.inbound.tui import FormField, FormFieldKind, FormPage, form_choices
    from ....core import AuthProviderKind

    fields = [
        FormField(
            key=_AUTH_PROVIDER_PATH,
            label=tr("flows.manager.action.auth_provider"),
            # Cl@ve Movil is the opening answer for a profile that has not
            # answered yet, because registering a certificate needs a file
            # and a secret through a separate verb: an operator setting up
            # here has, by construction, not done that.
            value=on_record.get(_AUTH_PROVIDER_PATH, AuthProviderKind.CLAVE_MOVIL.value),
            kind=FormFieldKind.SINGLE_CHOICE,
            choices=form_choices([(kind.value, _provider_label(kind)) for kind in AuthProviderKind]),
            validate=lambda value: None if value else tr("flows.manager.action.auth_provider"),
        ),
        FormField(
            key=_AUTH_DNI_NIE_PATH,
            label=tr("flows.manager.action.auth_dni_nie"),
            value=on_record.get(_AUTH_DNI_NIE_PATH, ""),
        ),
        FormField(
            key=_AUTH_SOPORTE_PATH,
            label=tr("flows.manager.action.auth_numero_soporte"),
            value=on_record.get(_AUTH_SOPORTE_PATH, ""),
        ),
        FormField(
            key=_AUTH_FECHA_VALIDEZ_PATH,
            label=tr("flows.manager.action.auth_fecha_validez"),
            value=on_record.get(_AUTH_FECHA_VALIDEZ_PATH, ""),
            validate=_validated_schema_value,
        ),
    ]
    if certificate_names:
        fields.append(
            FormField(
                key=_CERTIFICATE_KEY,
                label=tr("flows.manager.action.certificate_active"),
                value=active_certificate,
                kind=FormFieldKind.SINGLE_CHOICE,
                choices=form_choices([(name, name) for name in certificate_names]),
            ),
        )
    return FormPage(
        title=tr("flows.manager.action.certificate"),
        section=tr("flows.manager.action.certificate"),
        fields=tuple(fields),
    )


def _validated_schema_value(value: str) -> str | None:
    """Refuse a validity date the profile schema would reject, at the row.

    The schema types this path a date and anchors it to a zero-padded
    ISO day, so an operator entering the form their document prints -
    ``01/01/1990`` - is refused. Without a check here that refusal
    arrives from the write, and the write is not atomic: the three
    earlier paths are already persisted by the time the fourth is
    rejected, leaving a half-written auth section and a provider
    recorded but never activated.

    The check asks the very validator the write will ask, rather than
    restating its rule, so the page and the record cannot disagree about
    what a date is. A blank is not an answer and is left to the write,
    which stores it as a cleared fact.

    Args:
        value: The text the operator typed into the row.

    Returns:
        The refusal to show, or ``None`` when the value is storable.
    """
    from ....application.user_profile import ProfileValidationService
    from ....domain.user_profile import UserProfileFact, load_user_profile_schema

    text = value.strip()
    if not text:
        return None
    report = ProfileValidationService(schema=load_user_profile_schema()).validate_facts(
        _VALIDATION_SCRATCH_PROFILE_ID,
        (UserProfileFact(path=_AUTH_FECHA_VALIDEZ_PATH, value=text),),
    )
    # The report also carries required-field issues for every path this
    # single fact does not cover, so only this row's own verdict counts.
    if any(issue.path == _AUTH_FECHA_VALIDEZ_PATH for issue in report.issues):
        return tr("flows.manager.action.auth_fecha_validez_invalid")
    return None


def _clave_refusal(collected: Mapping[str, str]) -> str | None:
    """Return the refusal for a Cl@ve answer the flow cannot use, or ``None``.

    What a Cl@ve mode actually needs follows the route rather than the
    mode. Every Cl@ve mode needs the DNI or NIE that identifies the
    person. The contraste is read only by the non-QR fallback form, and
    it is the numero de soporte for a NIE but the document's validity
    date for a DNI, so it is required exactly when that route is
    selected and either form satisfies it. Cl@ve Permanente's second
    half is a password, which lives in the secret store beside the
    certificate passphrase and never becomes a profile fact.

    Demanding both fields from every Cl@ve mode - which this page used to
    do - refuses the default QR flow and Permanente outright, locking out
    operators whose setup works today.

    The decision routes through the same resolver the live session entry
    uses, so the page cannot refuse a credential the session would
    authenticate with: a value already supplied through settings counts,
    and the profile simply takes precedence over it.

    Args:
        collected: The values committed on the page.

    Returns:
        The refusal to show, or ``None`` when the answer is usable.
    """
    from ....application.auth import clave_auth_facts_from_profile_values, resolve_clave_credentials
    from ....core import AuthProviderKind
    from ....core.config import load_settings

    settings = load_settings()
    credentials = resolve_clave_credentials(
        AuthProviderKind(collected[_AUTH_PROVIDER_PATH]),
        settings=settings,
        facts=clave_auth_facts_from_profile_values(collected),
    )
    if credentials is None:
        # The certificate provider authenticates with an installed
        # certificate and needs neither Cl@ve half.
        return None
    if not credentials.dni_nie:
        return tr(
            "flows.manager.action.auth_clave_incomplete",
            missing=tr("flows.manager.action.auth_dni_nie"),
        )
    if credentials.provider_kind is not AuthProviderKind.CLAVE_MOVIL:
        return None
    if not settings.cadrumo_clave_prefer_non_qr:
        return None
    if not credentials.contraste:
        return tr("flows.manager.action.auth_contraste_missing")
    return None


def _commit_auth_choice(collected: Mapping[str, str]) -> tuple[str, AuthConfigureResult]:
    """Persist the auth section, select the certificate, activate the provider.

    The four profile fields go through the plural ``set_active_fields``
    door in one call. That buys ergonomics, not atomicity: the plural
    door is itself a loop over the singular one, persisting between
    iterations, so a fact rejected part-way leaves the earlier ones
    durably written. This action's defence against that is upstream - the
    page validates each value against the same schema before any write -
    rather than a guarantee this door does not offer.

    Two failure windows therefore remain open, and are accepted here
    rather than papered over. A fact the page passed but the record
    rejects leaves the earlier facts written. A failure in
    ``configure_operator_auth`` leaves the profile carrying credentials
    for a provider workflow state never activated. Closing either needs a
    transactional profile write, which is a question about a door shared
    across the application rather than one this action may settle.

    Certificate before provider: selecting the source before making it
    the active provider means the provider is never briefly active with
    nothing behind it.

    A blank field clears its fact rather than storing an empty string, so
    "I have not answered this" and "this is empty" stay one state.

    Args:
        collected: The values committed on the page.

    Returns:
        A pair of the certificate name selected (``""`` when the page
        offered none to select) and the typed
        :class:`~cadrumo.application.auth.AuthConfigureResult` the
        activation returned, so the caller can tell "configured" from
        "selected but not yet operationally complete" and route the
        operator to the same repair command the direct ``auth configure``
        CLI surfaces.
    """
    from ....application.auth import configure_operator_auth, select_operator_certificate_source
    from ....application.user_profile import set_active_fields
    from ....application.workflow import workflow_state_repository
    from ....domain.user_profile import UserProfileFact

    facts = tuple(
        UserProfileFact(path=path, value=collected.get(path, "").strip() or None) for path in _AUTH_PROFILE_PATHS
    )
    workflow_state_repository().update(lambda state: set_active_fields(state, facts))

    chosen_certificate = collected.get(_CERTIFICATE_KEY, "").strip()
    if chosen_certificate:
        select_operator_certificate_source(name=chosen_certificate)
    configure_result = configure_operator_auth(collected[_AUTH_PROVIDER_PATH])
    return chosen_certificate, configure_result


def _auth_facts_on_record() -> dict[str, str]:
    """Return the auth fields already stored, so the page opens on them.

    These values reach the page as ordinary text rows, so the identity
    and the contraste are legible on screen while the profile overview
    masks the same paths. That asymmetry is deliberate rather than
    overlooked: a masked edit row cannot be edited, and a page that hid
    what it holds would make this a retype rather than an edit. It is
    recorded here so the next reader meets a reason instead of an
    inconsistency; a field kind that masks until focused would resolve it
    properly, and none exists yet.
    """
    from ....application.user_profile import ProfileRepository
    from ....core import require_active_bucket_id

    record = ProfileRepository().load(require_active_bucket_id()).record
    return {
        fact.path: str(fact.value) for fact in record.facts if fact.value is not None and fact.path.startswith("auth.")
    }


def _provider_label(kind: AuthProviderKind) -> str:
    """Return one auth provider's operator-facing name.

    Literal ``tr`` keys in an exhaustive match: the locale scaffolder finds
    keys by static scan, so a key built from the enum value would be
    invisible to it and silently fall out of the catalogues.
    """
    from ....core import AuthProviderKind

    match kind:
        case AuthProviderKind.CERTIFICATE:
            return tr("flows.manager.action.provider.certificate")
        case AuthProviderKind.CLAVE_MOVIL:
            return tr("flows.manager.action.provider.clave_movil")
        case _:
            return tr("flows.manager.action.provider.clave_permanente")


def manager_actions() -> tuple[ManagerAction, ...]:
    """Every action the manager offers, in the order it offers them."""
    return (certificate_action(), censal_pull_action(), export_action())


__all__ = [
    "censal_pull_action",
    "certificate_action",
    "export_action",
    "manager_actions",
]
