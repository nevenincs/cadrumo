"""What the profile manager can do besides edit a field.

The manager page answers "what does my profile hold". These are the
operations an operator reaches for while looking at that answer: say how
they identify to AEAT, rotate the passphrase guarding the profile itself,
fill the profile in from what AEAT already holds, add a row to a section
that holds several, and take a copy of it away. They are offered in that
order because it is the order they depend on each other in - the pull
cannot run until the authentication mode is complete, and says so rather
than failing at the browser, and a row is worth adding by hand once the
pull has filled in what AEAT already knows. The passphrase action sits
beside authentication rather than after it: both are custody of how the
operator reaches this profile, not facts the profile records about the
taxpayer.

Adding a row is an action rather than a gesture on the table because a
repeatable section's row is all-or-nothing at the write door: every
required field of the row has to arrive in one batch, so editing a single
cell cannot bring a row into existence. The page collects the whole row
and commits once.

Each one is a plain callable returning a
:class:`~cadrumo.adapters.inbound.tui.ManagerActionOutcome`, so the screen
never learns what a censal read or a profile bundle is — it renders a
label, calls the callable, and shows the sentence it gets back. That is
the same injected-door arrangement the rest of this seam uses.

Taking a copy away is offered; bringing one back is not, and there is
nowhere else to send an operator who wants to. No inbound bundle path
exists on any surface — :func:`~cadrumo.application.user_profile.deserialize_profile_bundle`
survives with no production caller — so this page carries the export half
of a transfer whose other half is absent rather than elsewhere.

See Also:
    :mod:`cadrumo.entrypoints.cli._config._manager_frontend`
        The presenter that assembles these into the running screen.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ....adapters.persistence.profile.sync_runs import SyncRunRecordRepository
from ....core.i18n import tr
from ....domain.user_profile import profile_field_label, profile_section_title

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence

    from ....adapters.inbound.tui import (
        FormField,
        FormPage,
        ManagerAction,
        ManagerActionOutcome,
    )
    from ....application.auth import AuthConfigureResult
    from ....application.live import FiledHistoryOnboardingRun
    from ....application.user_profile import CensalReconciliation, EffectiveFact, ProfileOverview
    from ....core import AuthProviderKind
    from ....domain.user_profile import ProfileFieldDefinition, ProfileSectionDefinition

_AUTH_PROVIDER_PATH = "auth.provider"
_AUTH_CLAVE_MOVIL_ROUTE_PATH = "auth.clave_movil_route"
_AUTH_DNI_NIE_PATH = "auth.dni_nie"
_AUTH_SOPORTE_PATH = "auth.numero_soporte"
_AUTH_FECHA_VALIDEZ_PATH = "auth.fecha_validez"
_IDENTITY_TAX_ID_PATH = "identity.tax_id"


def _auth_field_label(path: str) -> str:
    """Resolve an auth path through the profile schema's label authority."""
    from ....domain.user_profile import load_user_profile_schema

    section_key, _field_key = path.split(".", 1)
    return profile_field_label(section_key, load_user_profile_schema().field(path))


_AUTH_PROFILE_PATHS = (
    _AUTH_PROVIDER_PATH,
    _AUTH_CLAVE_MOVIL_ROUTE_PATH,
    _AUTH_DNI_NIE_PATH,
    _AUTH_SOPORTE_PATH,
    _AUTH_FECHA_VALIDEZ_PATH,
)
"""Every ``auth`` path this page collects, in the order it shows them.

The two contraste paths are alternatives rather than a pair: Cl@ve asks a
NIE holder for the numero de soporte and a DNI holder for the document's
validity date, so an operator fills in whichever their document carries.

``identity.tax_id`` is collected here too but is deliberately NOT in this
tuple: these paths are written blank-clears-the-fact, and the schema
declares the fiscal identity required, so a blank one is REFUSED rather
than cleared. Since the batch is judged as a whole, that refusal would
take every other row on the page down with it — an operator who has not
declared their identity yet could not save an authentication mode at all.
It is committed on its own terms in :func:`_commit_auth_choice`.
"""

_AUTH_PAGE_PATHS = (
    _AUTH_PROVIDER_PATH,
    _IDENTITY_TAX_ID_PATH,
    _AUTH_CLAVE_MOVIL_ROUTE_PATH,
    _AUTH_DNI_NIE_PATH,
    _AUTH_SOPORTE_PATH,
    _AUTH_FECHA_VALIDEZ_PATH,
)
"""Every profile row the page shows, in the order it shows them.

The fiscal identity sits directly above the credential it must agree
with, because the two rows exist beside each other to be read against
each other. Kept honest against the page it describes by
``test_the_declared_row_order_is_the_order_the_page_builds``.
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
    from ....adapters.outbound.aeat import operator_progress_sink

    return ManagerAction(
        key="censal-pull",
        label=tr("flows.manager.action.censal_pull"),
        label_key="flows.manager.action.censal_pull",
        run=_run_censal_pull,
        progress_sink=operator_progress_sink,
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

    from ....adapters.inbound.tui import ManagerActionDisposition, ManagerActionOutcome
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
        return ManagerActionOutcome(message=unavailable, disposition=ManagerActionDisposition.REFUSED)

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
    if (refusal := _clave_refusal(on_record)) is not None:
        return f"{tr('flows.manager.action.censal_pull_auth_incomplete')} {refusal}"
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

    A path missing from the projection is still reported, but only through a
    generic operator label. Its dotted storage address is diagnostic data,
    not actionable screen copy.
    """
    return ", ".join(labels.get(path, tr("flows.manager.field_unavailable")) for path in paths)


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


def filed_history_pull_all_action() -> ManagerAction:
    """Pull this taxpayer's AEAT-declared filing history in one sweep.

    Composes ``pull_filed_history`` -- discovery, bulk filed capture, IVA
    wallet reconciliation and the notificaciones pull -- exactly as
    ``aeat app live filed pull-all`` does, so the manager offers the same
    capability the verb already ships rather than a second, thinner
    implementation of it. Gated on the same auth-readiness predicate the
    censal pull uses, for the same reason: the live navigation can push a
    Cl@ve prompt to the operator's phone, and spending it on a sweep that
    cannot authenticate is worse than saying so first.
    """
    from ....adapters.inbound.tui import ManagerAction
    from ....adapters.outbound.aeat import operator_progress_sink

    return ManagerAction(
        key="filed-history-pull-all",
        label=tr("flows.manager.action.filed_history_pull_all"),
        label_key="flows.manager.action.filed_history_pull_all",
        run=_run_filed_history_pull_all,
        progress_sink=operator_progress_sink,
    )


def _run_filed_history_pull_all() -> ManagerActionOutcome:
    """Run the history-onboarding sweep and report every stage's outcome.

    Reads the same profile the discover and pull-all CLI verbs read, so a
    profile that has not yet declared enough to derive an expectation grid
    downgrades the report the same way the CLI does rather than refusing.
    The sweep persists filed observations and reconciliation state of its
    own accord; it writes no profile field, so the outcome carries no
    rebuilt overview.
    """
    import asyncio

    from ....adapters.inbound.tui import ManagerActionDisposition, ManagerActionOutcome
    from ....application.live import pull_filed_history
    from ....application.wizard import load_active_taxpayer_profile
    from ....application.workflow import workflow_state_repository
    from ....core.config import load_settings
    from ....core.errors import CadrumoError

    unavailable = _censal_pull_unavailable()
    if unavailable is not None:
        return ManagerActionOutcome(message=unavailable, disposition=ManagerActionDisposition.REFUSED)

    try:
        profile = load_active_taxpayer_profile(workflow_state_repository().load())
    except CadrumoError:
        profile = None

    output_root = load_settings().cadrumo_filed_declarations_dir
    run = asyncio.run(
        pull_filed_history(
            output_root=output_root,
            profile=profile,
            sync_run_repository=SyncRunRecordRepository(),
        ),
    )
    disposition = ManagerActionDisposition.WARNING if run.stage_failures else ManagerActionDisposition.SUCCESS
    return ManagerActionOutcome(message=_filed_history_pull_all_summary(run), disposition=disposition)


def _filed_history_pull_all_summary(run: FiledHistoryOnboardingRun) -> str:
    """Report what the sweep found, in the operator's terms.

    Counts rather than a completeness fraction, for the reason the run
    model itself carries none: part of the walked grid comes from AEAT's
    own offered option list, whose scoping to this NIF is unconfirmed, so a
    ratio over it would read as coverage while resting on a denominator
    that may say nothing about this taxpayer. The prose denominator note
    the run already carries says what was actually measured, and is
    appended verbatim rather than re-derived.
    """
    refused = len(run.refused_pairs)
    parts = [
        tr(
            "flows.manager.action.filed_history_pull_all_done",
            captured=run.captured_count,
            refused=refused,
            iva_wallet_status=run.iva_wallet_status,
            notificaciones_status=run.notificaciones_status,
        ),
    ]
    if refused:
        parts.append(
            tr(
                "flows.manager.action.filed_history_pull_all_refused",
                pairs=", ".join(f"{pair.modelo}/{pair.ejercicio}" for pair in run.refused_pairs),
            ),
        )
    parts.extend(run.stage_failures)
    parts.append(run.denominator_note)
    return " ".join(parts)


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

    Encrypted transport is not merely the default here, it is the only one
    reachable, and that is now load-bearing rather than a preference.
    :attr:`~cadrumo.application.user_profile.ProfileBundleExportTransport.CLEARTEXT_LOCAL`
    writes the taxpayer's financial data as plain JSON; it used to be held
    behind an explicit command-line flag, and no surface declares that flag
    any more. Hardcoding the transport at this call is therefore the sole
    remaining guard against writing cleartext by pressing a button while
    looking at the data it would expose. It is not a value to plumb through
    to the operator.
    """
    from pathlib import Path

    from pydantic import SecretStr

    from ....adapters.inbound.tui import ManagerActionOutcome
    from ....application.user_profile import (
        ProfileBundleExportPurpose,
        ProfileBundleExportRequest,
        ProfileBundleExportTransport,
        export_profile_bundle,
    )
    from ....entrypoints.tui.components.forms import FormField, FormPage
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
                secret=True,
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
    """Choose how this taxpayer authenticates, and with which certificate.

    Declares itself the sole writer of the ``auth`` section, so selecting
    one of those rows in the table opens this page instead of the
    single-field edit box.

    Every one of them is a field that cannot be set alone and stay
    correct. Writing ``auth.provider`` through the generic door recorded
    the choice on the profile but never called ``configure_operator_auth``,
    so the workflow state kept its old provider and the profile claimed one
    no session had been activated for — the exact drift ``_commit_auth_choice``
    was written to prevent. Writing ``auth.dni_nie`` alone let it diverge
    from ``identity.tax_id``, which the fail-closed session guard then
    refuses a login over, with nothing at setup time having said so. The
    two contraste paths are alternatives whose sufficiency only the whole
    page can judge, since which one is required follows the route.

    ``identity.tax_id`` is deliberately NOT claimed. This page offers it
    so the credential can agree with it, but it belongs to the identity
    section and is editable there on its own terms; claiming it would take
    a required field's ordinary edit away to solve a problem it does not
    have.
    """
    from ....adapters.inbound.tui import ManagerAction

    return ManagerAction(
        key="certificate",
        label=tr("flows.manager.action.certificate"),
        label_key="flows.manager.action.certificate",
        run=_run_certificate,
        owns_paths=_AUTH_PROFILE_PATHS,
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

    Takes no parameters, deliberately. How the page is shown is bound by
    the caller through ``presenting_forms_through``, which is what lets
    the refusal and commit branches be driven without a terminal — and it
    does so without this action carrying a door of its own for someone to
    aim elsewhere.
    """
    from ....adapters.inbound.tui import ManagerActionDisposition, ManagerActionOutcome
    from ....application.auth import list_operator_certificate_sources
    from ._manager_frontend import build_active_profile_overview, present_form

    listing = list_operator_certificate_sources()
    on_record = _auth_facts_on_record()
    collected = present_form(
        _auth_form_page(
            on_record=on_record,
            suggested_tax_id=_suggested_tax_id(on_record),
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
        return ManagerActionOutcome(message=refusal, disposition=ManagerActionDisposition.REFUSED)

    chosen_certificate, configure_result = _commit_auth_choice(collected)
    if not configure_result.complete:
        message = configure_result.incomplete_reason
    else:
        message = tr("flows.manager.action.certificate_done", name=chosen_certificate or "-", provider=provider)
    return ManagerActionOutcome(
        message=message,
        overview=build_active_profile_overview(),
        disposition=(
            ManagerActionDisposition.SUCCESS if configure_result.complete else ManagerActionDisposition.WARNING
        ),
    )


def _auth_form_page(
    *,
    on_record: Mapping[str, str],
    suggested_tax_id: str,
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

    The fiscal identity and the Cl@ve identity are both shown, and both
    open on ``suggested_tax_id`` when they hold nothing. They are separate
    fields on purpose — one names the taxpayer, the other is a credential
    input — but the fail-closed session guard refuses whenever they
    disagree, so they are two rows that must carry one value. Opening them
    blank made an operator who had already answered one of them retype it
    into the other, and get no warning until a login refused much later.
    Suggesting is as far as this goes: neither row is locked, so the day
    they legitimately diverge the operator can still say so.

    Args:
        on_record: The ``auth.*`` and ``identity.tax_id`` values the
            profile already holds, which seed the fields so the page opens
            on the current answer.
        suggested_tax_id: The identifier to open both identity rows on
            when they hold nothing, or ``""`` when none is known.
        certificate_names: Names of the registered certificate sources.
        active_certificate: The currently selected certificate name, or
            ``""`` when none is selected.

    Returns:
        The :class:`~cadrumo.adapters.inbound.tui.FormPage` to present.
    """
    from ....core import AuthProviderKind, ClaveMovilRoute
    from ....entrypoints.tui.components.forms import FormField, FormFieldKind, FormPage, form_choices

    fields = [
        FormField(
            key=_AUTH_PROVIDER_PATH,
            label=_auth_field_label(_AUTH_PROVIDER_PATH),
            # Cl@ve Movil is the opening answer for a profile that has not
            # answered yet, because registering a certificate needs a file
            # and a secret through a separate verb: an operator setting up
            # here has, by construction, not done that.
            value=on_record.get(_AUTH_PROVIDER_PATH, AuthProviderKind.CLAVE_MOVIL.value),
            kind=FormFieldKind.SINGLE_CHOICE,
            choices=form_choices([(kind.value, _provider_label(kind)) for kind in AuthProviderKind]),
            validate=lambda value: None if value else _auth_field_label(_AUTH_PROVIDER_PATH),
        ),
        FormField(
            key=_IDENTITY_TAX_ID_PATH,
            label=_auth_field_label(_IDENTITY_TAX_ID_PATH),
            value=on_record.get(_IDENTITY_TAX_ID_PATH, "") or suggested_tax_id,
            validate=_validated_tax_id,
        ),
        FormField(
            key=_AUTH_CLAVE_MOVIL_ROUTE_PATH,
            label=_auth_field_label(_AUTH_CLAVE_MOVIL_ROUTE_PATH),
            value=on_record.get(_AUTH_CLAVE_MOVIL_ROUTE_PATH, ClaveMovilRoute.QR.value),
            kind=FormFieldKind.SINGLE_CHOICE,
            choices=form_choices(
                [
                    (ClaveMovilRoute.QR.value, tr("flows.manager.action.auth_clave_movil_route_qr")),
                    (
                        ClaveMovilRoute.APP_REQUEST.value,
                        tr("flows.manager.action.auth_clave_movil_route_app_request"),
                    ),
                ],
            ),
        ),
        FormField(
            key=_AUTH_DNI_NIE_PATH,
            label=_auth_field_label(_AUTH_DNI_NIE_PATH),
            value=on_record.get(_AUTH_DNI_NIE_PATH, "") or suggested_tax_id,
        ),
        FormField(
            key=_AUTH_SOPORTE_PATH,
            label=_auth_field_label(_AUTH_SOPORTE_PATH),
            value=on_record.get(_AUTH_SOPORTE_PATH, ""),
        ),
        FormField(
            key=_AUTH_FECHA_VALIDEZ_PATH,
            label=_auth_field_label(_AUTH_FECHA_VALIDEZ_PATH),
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


def _validated_tax_id(value: str) -> str | None:
    """Refuse a fiscal identity that could never authenticate, at the row.

    Asks :func:`~core.identity.validate_spanish_tax_id` — the very
    authority the fail-closed session guard applies to this field — so
    the page cannot accept an identifier the first login would refuse.
    Restating the rule here instead would let the two drift, and the
    drift would only ever surface as a login the operator cannot explain.

    A blank passes. This row seeds from other sources and is committed
    only when it carries something, so "I have not answered this yet" is
    a state the page must be able to hold; absence is answered by the
    profile's own required-field reporting, not by this row.

    Args:
        value: The text the operator typed into the row.

    Returns:
        The refusal to show, or ``None`` when the value is storable.
    """
    from ....core.identity import IdentityError, validate_spanish_tax_id

    text = value.strip()
    if not text:
        return None
    try:
        validate_spanish_tax_id(text)
    except IdentityError:
        return tr("flows.manager.action.auth_tax_id_invalid")
    return None


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
    from ....core import AuthProviderKind, ClaveMovilRoute
    from ....core.config import load_settings

    settings = load_settings()
    facts = clave_auth_facts_from_profile_values(collected)
    credentials = resolve_clave_credentials(
        AuthProviderKind(collected[_AUTH_PROVIDER_PATH]),
        settings=settings,
        facts=facts,
    )
    if credentials is None:
        # The certificate provider authenticates with an installed
        # certificate and needs neither Cl@ve half.
        return None
    if not credentials.dni_nie:
        return tr(
            "flows.manager.action.auth_clave_incomplete",
            missing=_auth_field_label(_AUTH_DNI_NIE_PATH),
        )
    if credentials.provider_kind is not AuthProviderKind.CLAVE_MOVIL:
        return None
    route = facts.clave_movil_route
    if route is None:
        return tr(
            "application.auth.sessions.errors.clave_route_missing",
            route_field=_auth_field_label(_AUTH_CLAVE_MOVIL_ROUTE_PATH),
        )
    if route is ClaveMovilRoute.QR:
        return None
    if not credentials.contraste:
        return tr(
            "flows.manager.action.auth_contraste_missing",
            nie_field=_auth_field_label(_AUTH_SOPORTE_PATH),
            dni_field=_auth_field_label(_AUTH_FECHA_VALIDEZ_PATH),
        )
    return None


def _commit_auth_choice(collected: Mapping[str, str]) -> tuple[str, AuthConfigureResult]:
    """Persist the auth section, select the certificate, activate the provider.

    The four profile fields go through one explicit fact replacement command:
    one authenticated record read, one schema validation over the complete
    next fact set, and one revision-bound encrypted publish.
    A fact the page passed but the record rejects therefore leaves NONE of
    the batch durably written, not merely the rejected one. This
    action's defence against a rejection reaching the record at all is
    still upstream - the page validates each value against the same schema
    before any write - but the write itself no longer half-applies.

    One failure window remains open, and is accepted here rather than
    papered over: a failure in ``configure_operator_auth`` leaves the
    profile carrying credentials for a provider workflow state never
    activated. Closing it needs a transaction spanning the profile write
    and the workflow-state activation together, which is a question about
    a door shared across the application rather than one this action may
    settle.

    Certificate before provider: selecting the source before making it
    the active provider means the provider is never briefly active with
    nothing behind it.

    A blank ``auth`` field clears its fact rather than storing an empty
    string, so "I have not answered this" and "this is empty" stay one
    state.

    ``identity.tax_id`` is committed on the opposite rule: it is written
    when it carries a value and simply omitted when blank. That is not an
    inconsistency to tidy away. The schema declares the path required, so
    submitting it blank does not clear it — it is REFUSED, and because
    the batch is judged as a whole the refusal would reject the provider
    and every credential beside it. An operator who has not yet declared
    a fiscal identity would then be unable to save an authentication mode
    at all, which is the flow-breaking refusal this page already exists
    to have stopped doing.

    Omitting it is also the narrower claim. The path is the ownership
    anchor the censal read and every filing resolve against, and it is
    the only row here owned by another section: the page shows it so the
    credential can agree with it, which is a reason to let the operator
    SET it, not a mandate to let an authentication page decide it is
    gone. Clearing stays on its own row on the profile page, where
    clearing is the operator's evident intent.

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
    from ....application.user_profile import ProfileFactWriteDoor, apply_profile_fact_changes
    from ....core import require_active_bucket_id
    from ....domain.user_profile import UserProfileFact

    facts = [UserProfileFact(path=path, value=collected.get(path, "").strip() or None) for path in _AUTH_PROFILE_PATHS]
    declared_tax_id = collected.get(_IDENTITY_TAX_ID_PATH, "").strip()
    if declared_tax_id:
        facts.append(UserProfileFact(path=_IDENTITY_TAX_ID_PATH, value=declared_tax_id))
    committed = tuple(facts)
    apply_profile_fact_changes(
        profile_id=require_active_bucket_id(),
        changes=committed,
        door=ProfileFactWriteDoor.MANAGER_AUTH,
    )

    chosen_certificate = collected.get(_CERTIFICATE_KEY, "").strip()
    if chosen_certificate:
        select_operator_certificate_source(name=chosen_certificate)
    configure_result = configure_operator_auth(collected[_AUTH_PROVIDER_PATH])
    return chosen_certificate, configure_result


def _auth_facts_on_record() -> dict[str, str]:
    """Return the fields this page already holds, so it opens on them.

    These values reach the page as ordinary text rows, so the identity
    and the contraste are legible on screen while the profile overview
    masks the same paths. That asymmetry is deliberate rather than
    overlooked: a masked edit row cannot be edited, and a page that hid
    what it holds would make this a retype rather than an edit. It is
    recorded here so the next reader meets a reason instead of an
    inconsistency; a field kind that masks until focused would resolve it
    properly, and none exists yet.

    ``identity.tax_id`` is read alongside the ``auth`` section because
    the page shows it: the session guard refuses whenever it and
    ``auth.dni_nie`` disagree, so a page that could not see the fiscal
    identity could not open the credential row on it either — which is
    exactly what made an operator retype an answer they had given.
    """
    from ....application.user_profile import ProfileRecordRepository
    from ....core import require_active_bucket_id

    profile_id = require_active_bucket_id()
    record = ProfileRecordRepository.for_current_session(profile_id).load(profile_id)
    return {
        fact.path: str(fact.value)
        for fact in record.facts
        if fact.value is not None and (fact.path.startswith("auth.") or fact.path == _IDENTITY_TAX_ID_PATH)
    }


def _suggested_tax_id(on_record: Mapping[str, str]) -> str:
    """Return the identifier to open an empty identity row on, or ``""``.

    Three surfaces name one taxpayer — the fiscal identity, the Cl@ve
    credential, and the certificate's own subject — and the fail-closed
    session guard refuses whenever they disagree. None of them used to
    populate the others, so an operator who had answered one met a blank
    row on the next surface and learned they disagreed only when a login
    refused.

    Order is by how much the answer is already the operator's own.
    ``identity.tax_id`` is the taxpayer this profile describes and wins.
    ``auth.dni_nie`` is the same person typed at a credential prompt.
    The certificate's subject comes last: it is a fact read out of a file
    rather than an answer anybody gave here, so it fills a gap the
    operator has left rather than displacing something they said.

    Reading the certificate costs a PKCS#12 decode, so it is reached only
    when the two profile fields are both empty — the case where the
    operator has set up a certificate first and nothing else knows who
    they are yet.

    Args:
        on_record: The values the profile already holds.

    Returns:
        The identifier to suggest, or ``""`` when none is known.
    """
    from ....adapters.outbound.aeat.auth.certificate import read_certificate_subject_nif
    from ....application.auth import certificate_source_tax_id

    for path in (_IDENTITY_TAX_ID_PATH, _AUTH_DNI_NIE_PATH):
        known = on_record.get(path, "").strip()
        if known:
            return known
    return certificate_source_tax_id(read_subject_nif=read_certificate_subject_nif)


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


#: Key carrying the section chooser's answer.
#:
#: Deliberately not a schema field key. The chooser tells the page which fields
#: to ask for; the application mutation authority excludes it from the committed
#: row.
_ROW_SECTION_KEY = "__row_section"


def add_row_action() -> ManagerAction:
    """Add one row to a repeatable section -- a socio, an activity, a property."""
    from ....adapters.inbound.tui import ManagerAction

    return ManagerAction(
        key="add-row",
        label=tr("flows.manager.action.add_row"),
        label_key="flows.manager.action.add_row",
        run=_run_add_row,
    )


def _run_add_row() -> ManagerActionOutcome:
    """Collect one whole row, then write it in a single batch.

    A repeatable section's row is all-or-nothing at the write door: every
    required field arrives together or none of the row lands. Editing a
    single cell therefore cannot create a row -- the first write would be
    refused for the fields not yet supplied -- which is why this is a page
    that collects the row and commits once rather than an empty line added
    to the table.

    The refusal at the end is a backstop rather than the expected path. The
    form re-checks every field on submit, including ones the operator never
    opened, so a blank required field is normally caught where it was typed;
    a rule the page cannot see (a conditional requirement) would still be
    refused by the door, and it is reported rather than raised at a screen
    that cannot act on it.
    """
    from ....adapters.inbound.tui import ManagerActionDisposition, ManagerActionOutcome
    from ....application.user_profile import (
        add_profile_repeatable_section_row,
    )
    from ....core import require_active_bucket_id
    from ....domain.user_profile import ProfileSchemaValidationError, load_user_profile_schema
    from ._manager_frontend import build_active_profile_overview, present_form

    schema = load_user_profile_schema()
    sections = tuple(section for section in schema.sections if section.repeatable)
    if not sections:
        return ManagerActionOutcome(
            message=tr("flows.manager.action.add_row_none"),
            disposition=ManagerActionDisposition.REFUSED,
        )

    def _page(values: Mapping[str, str]) -> FormPage:
        return _row_page(sections, values)

    collected = present_form(_page({}), rebuild=_page)
    if collected is None:
        return ManagerActionOutcome(message=tr("flows.manager.action.abandoned"))

    section = _chosen_section(sections, collected)
    try:
        mutation = add_profile_repeatable_section_row(
            profile_id=require_active_bucket_id(),
            section_key=section.key,
            values=collected,
        )
    except ProfileSchemaValidationError:
        return ManagerActionOutcome(
            message=tr("flows.manager.action.add_row_incomplete"),
            disposition=ManagerActionDisposition.REFUSED,
        )

    return ManagerActionOutcome(
        message=tr(
            "flows.manager.action.add_row_done",
            section=profile_section_title(section),
            index=mutation.row_index,
        ),
        overview=build_active_profile_overview(),
    )


def _chosen_section(
    sections: Sequence[ProfileSectionDefinition],
    values: Mapping[str, str],
) -> ProfileSectionDefinition:
    """Return the section the chooser names, defaulting to the first offered.

    The default matters: the page opens on a section already selected so its
    fields are visible immediately, and an operator who never touches the
    chooser commits the section they were shown.
    """
    chosen = values.get(_ROW_SECTION_KEY, "")
    return next((section for section in sections if section.key == chosen), sections[0])


def _row_page(
    sections: Sequence[ProfileSectionDefinition],
    values: Mapping[str, str],
) -> FormPage:
    """Build the row page for the section currently chosen.

    Rebuilt whenever an answer changes, so picking a different section
    replaces the fields below the chooser. Field labels and the section
    title come from the shared schema-label helpers, so this page names a
    field exactly as the manager's own table does.
    """
    from ....entrypoints.tui.components.forms import FormField, FormFieldKind, FormPage, form_choices

    section = _chosen_section(sections, values)
    fields: list[FormField] = [
        FormField(
            key=_ROW_SECTION_KEY,
            label=tr("flows.manager.action.add_row_section"),
            value=section.key,
            kind=FormFieldKind.SINGLE_CHOICE,
            choices=form_choices([(item.key, profile_section_title(item)) for item in sections]),
        ),
    ]
    fields.extend(_row_field(section, field) for field in section.fields)
    return FormPage(
        title=tr("flows.manager.action.add_row"),
        section=profile_section_title(section),
        fields=tuple(fields),
    )


def _row_field(section: ProfileSectionDefinition, field: ProfileFieldDefinition) -> FormField:
    """Build one collected field from its schema declaration.

    A field with a closed answer set is offered as that set rather than as
    free text, so a value outside it is not typeable. Which fields have one,
    and what the options are called, comes from
    :func:`~cadrumo.application.user_profile.profile_field_choices` -- the
    same answer the manager's edit dialog reads. It was decided twice before,
    and the two disagreed: this form had always offered a boolean as Yes/No
    while the manager gave the same field a text box, so one surface stored
    ``true`` and the other stored whichever spelling of yes the operator
    happened to type.

    A typed field is checked against its declaration as it is left, so a bad
    date is refused beside the box rather than by the batch commit, which
    reports one field's fault as the whole row's.
    """
    from ....application.user_profile import profile_field_choices
    from ....entrypoints.tui.components.forms import FormField, FormFieldKind, form_choices

    declared = profile_field_choices(field, path=f"{section.key}.{field.key}")
    return FormField(
        key=field.key,
        label=profile_field_label(section.key, field),
        kind=FormFieldKind.SINGLE_CHOICE if declared else FormFieldKind.TEXT,
        choices=form_choices([(choice.value, choice.label) for choice in declared]),
        hint=_shape_hint(field),
        validate=_row_value_check(section, field),
    )


def _shape_hint(field: ProfileFieldDefinition) -> str:
    """The accepted-shape line for a typed row, or empty when it needs none."""
    from ....adapters.inbound.tui import accepted_shape_hint

    return accepted_shape_hint(field.type)


def _row_value_check(
    section: ProfileSectionDefinition,
    field: ProfileFieldDefinition,
) -> Callable[[str], str | None]:
    """Refuse a blank required answer, and any value the schema would reject.

    Both halves are the same question asked of one box -- "may this row keep
    what you typed" -- so they are answered together rather than by two
    validators the form would have to compose. The value half delegates to
    :func:`~._manager_frontend.profile_field_value_refusal`, the same judge
    the manager's edit dialog uses, so a value one surface accepts is not
    refused by the other.

    The path handed to the judge is the UNINDEXED declaration path. A row's
    real path carries an index the operator has not been allocated yet, and
    the judge resolves the declaration by reducing the path to its
    ``section.field`` form anyway, so the index would be discarded on
    arrival.
    """
    from ._manager_frontend import profile_field_value_refusal

    path = f"{section.key}.{field.key}"

    def _check(value: str) -> str | None:
        if not value.strip():
            return tr("flows.manager.action.add_row_required") if field.required else None
        return profile_field_value_refusal(path, value)

    return _check


_GOOGLE_EXPORT_MODELO_KEY = "modelo"
_GOOGLE_EXPORT_PERIOD_KEY = "period"
_GOOGLE_EXPORT_YEAR_KEY = "year"


def google_export_action() -> ManagerAction:
    """Export the active profile's registry calculation surface to Google Sheets.

    Class (a) gap this closes: ``aeat config google sync calc export`` has
    worked from the command line all along, gated on the same
    :attr:`~cadrumo.core.ServiceCapability.GOOGLE_EXPORT` capability the
    censal pull's own auth-readiness gate mirrors — an operator sitting in
    the manager had no way to reach it without leaving for a terminal.

    Only ``export`` is wired here, not ``verify`` / ``pull`` / ``compute``:
    those three read a spreadsheet back (a workbook id from a PRIOR export,
    an AEAT-oracle parity check), which is a second, larger surface with its
    own operator-input shape and its own care about Sheets staying a
    one-way mirror rather than an authority. ``export`` needs nothing an
    operator does not already have on the profile they are looking at, so
    it is the one clean action; the rest is a real, tracked gap.
    """
    from ....adapters.inbound.tui import ManagerAction

    return ManagerAction(
        key="google-export",
        label=tr("flows.manager.action.google_export"),
        label_key="flows.manager.action.google_export",
        run=_run_google_export,
    )


def _run_google_export() -> ManagerActionOutcome:
    """Collect parameters, then adapt them through the canonical export service."""
    from ....adapters.inbound.tui import ManagerActionDisposition, ManagerActionOutcome
    from ....core.errors import CadrumoError
    from ....entrypoints.tui.components.forms import FormField, FormPage
    from ._google_sync_calc import execute_google_sheets_export
    from ._manager_frontend import present_form

    page = FormPage(
        title=tr("flows.manager.action.google_export"),
        section=tr("flows.manager.action.google_export"),
        fields=(
            FormField(
                key=_GOOGLE_EXPORT_MODELO_KEY,
                label=tr("flows.manager.action.google_export_modelo"),
                hint=tr("cli.config.google.sync.calc.export.modelo_help"),
                validate=lambda value: None if value.strip() else tr("flows.manager.action.google_export_modelo"),
            ),
            FormField(
                key=_GOOGLE_EXPORT_PERIOD_KEY,
                label=tr("flows.manager.action.google_export_period"),
                hint=tr("cli.config.google.sync.calc.export.period_help"),
                validate=lambda value: None if value.strip() else tr("flows.manager.action.google_export_period"),
            ),
            FormField(
                key=_GOOGLE_EXPORT_YEAR_KEY,
                label=tr("flows.manager.action.google_export_year"),
                hint=tr("cli.config.google.sync.calc.export.year_help"),
                validate=_validated_google_export_year,
            ),
        ),
    )
    collected = present_form(page)
    if collected is None:
        return ManagerActionOutcome(message=tr("flows.manager.action.abandoned"))

    try:
        _profile, result = execute_google_sheets_export(
            modelo=collected[_GOOGLE_EXPORT_MODELO_KEY].strip(),
            period=collected[_GOOGLE_EXPORT_PERIOD_KEY].strip(),
            year=int(collected[_GOOGLE_EXPORT_YEAR_KEY].strip()),
        )
    except CadrumoError:
        return ManagerActionOutcome(
            message=tr("flows.manager.action.failed"),
            disposition=ManagerActionDisposition.REFUSED,
        )

    return ManagerActionOutcome(
        message=tr(
            "flows.manager.action.google_export_done",
            modelo=result.modelo,
            spreadsheet_url=result.spreadsheet_url or "",
        ),
    )


def _validated_google_export_year(value: str) -> str | None:
    """Refuse a year outside the CLI verb's own accepted range, at the row.

    ``--year`` is a Typer option bounded ``min=2000, max=2099``; a manager
    form has no Typer parser to enforce that for it, so the same bound is
    checked here rather than letting an out-of-range year reach the door
    and refuse with a colder, CLI-shaped message.
    """
    text = value.strip()
    if not text:
        return tr("flows.manager.action.google_export_year")
    if not text.isdigit() or not (2000 <= int(text) <= 2099):
        return tr("flows.manager.action.google_export_year_invalid")
    return None


def logout_action() -> ManagerAction:
    """End the operator's session and close the manager.

    The only action here whose outcome the operator cannot keep looking
    at: a logout that merely repainted would leave the just-closed
    profile's fields on screen as though they were still live. It drives
    :func:`~cadrumo.application.user_profile.logout_active_profile` --
    the same strong-close teardown ``aeat config logout`` runs on the CLI
    (session zeroised, both persisted-session halves deleted, the
    per-bucket lock released, the active-profile pointer cleared) -- and
    reports the outcome through ``close_session=True`` rather than a
    rebuilt overview, so :meth:`~cadrumo.adapters.inbound.tui._manager_screen.ProfileManagerApp._settle_action`
    exits the surface instead of redrawing it.
    """
    from ....adapters.inbound.tui import ManagerAction

    return ManagerAction(
        key="logout",
        label=tr("flows.manager.action.logout"),
        label_key="flows.manager.action.logout",
        run=_run_logout,
    )


def _run_logout() -> ManagerActionOutcome:
    from ....adapters.inbound.tui import ManagerActionOutcome
    from ....application.user_profile import logout_active_profile

    logout_active_profile()
    return ManagerActionOutcome(message=tr("flows.manager.action.logout_done"), close_session=True)


def manager_actions() -> tuple[ManagerAction, ...]:
    """Every action the manager offers, in the order it offers them."""
    return (
        certificate_action(),
        censal_pull_action(),
        filed_history_pull_all_action(),
        add_row_action(),
        google_export_action(),
        export_action(),
        logout_action(),
    )


__all__ = [
    "add_row_action",
    "censal_pull_action",
    "certificate_action",
    "export_action",
    "filed_history_pull_all_action",
    "google_export_action",
    "logout_action",
    "manager_actions",
]
