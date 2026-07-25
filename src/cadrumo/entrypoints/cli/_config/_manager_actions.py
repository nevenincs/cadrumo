"""What the profile manager can do besides edit a field.

The manager page answers "what does my profile hold". These are the
operations an operator reaches for while looking at that answer: fill it
in from what they already filed, take a copy away, and choose which
certificate speaks for them.

Each one is a plain callable returning a
:class:`~cadrumo.adapters.inbound.tui.ManagerActionOutcome`, so the screen
never learns what a censal declaration or a bundle is — it renders a
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
    from ....adapters.inbound.tui import ManagerAction, ManagerActionOutcome

_CENSAL_PULL_YEARS_BACK = 10
"""How far back a censal pull looks for filed 036 declarations.

A censal declaration is filed when something changes, so most years are
legitimately empty and a decade is a cheap way to find the last one that
was not. Enrolment usually predates any single filing year.
"""


def censal_pull_action() -> ManagerAction:
    """Fill the censal fields in from the taxpayer's own filed Modelo 036.

    036 IS the censo — it is the declaración censal de alta, modificación
    y baja, and it is what a person or entity files to enrol in the tax
    system. So the honest way to learn someone's censal situation is to
    read the declaration they filed, rather than ask them to retype it.

    This reads their own filed declaration out of their own expediente
    history, which is a pure read of filed evidence and subject to the
    same gate as every justificante pull. It never touches the Censos WEB
    modification tool.
    """
    from ....adapters.inbound.tui import ManagerAction

    return ManagerAction(key="censal-pull", label=tr("flows.manager.action.censal_pull"), run=_run_censal_pull)


def _run_censal_pull() -> ManagerActionOutcome:
    """Pull filed 036s, derive the censal facts, and write them."""
    import asyncio

    from ....adapters.inbound.tui import ManagerActionOutcome
    from ....application.live._censo_036_pull import censo_facts_from_filed_036, pull_filed_036
    from ....application.user_profile import set_active_field
    from ....application.workflow import workflow_state_repository
    from ....core import require_active_bucket_id
    from ....core.time import now
    from ._manager_frontend import build_active_profile_overview

    bucket_id = require_active_bucket_id()
    # Through the clock seam, so a frozen-clock test pins the year span
    # rather than searching a window that moves with the calendar.
    this_year = now().year
    filings = asyncio.run(
        pull_filed_036(
            bucket_id=bucket_id,
            year_from=this_year - _CENSAL_PULL_YEARS_BACK,
            year_to=this_year,
        ),
    )
    facts = censo_facts_from_filed_036(filings)
    if not facts:
        # No filing found is an ordinary answer, not a failure: a taxpayer
        # enrolled long ago may have nothing in the window, and stamping a
        # default would invent an enrolment they never declared.
        return ManagerActionOutcome(message=tr("flows.manager.action.censal_pull_empty"))
    for fact in facts:
        workflow_state_repository().update(lambda state, fact=fact: set_active_field(state, fact))
    return ManagerActionOutcome(
        message=tr("flows.manager.action.censal_pull_done", count=len(facts), filings=len(filings)),
        overview=build_active_profile_overview(),
    )


def export_action() -> ManagerAction:
    """Write a passphrase-encrypted portable copy of the profile."""
    from ....adapters.inbound.tui import ManagerAction

    return ManagerAction(key="export", label=tr("flows.manager.action.export"), run=_run_export)


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

    return ManagerAction(key="certificate", label=tr("flows.manager.action.certificate"), run=_run_certificate)


def _run_certificate() -> ManagerActionOutcome:
    """Offer the registered certificate sources and activate the chosen one.

    Registration itself stays on ``aeat config certificate register``: it
    takes a file and a secret, and this page has no business handling
    either. What belongs here is the preference — which of the already
    registered certificates is the active one — because that is a profile
    fact an operator reads off this page and expects to change from it.
    """
    from ....adapters.inbound.tui import (
        FormField,
        FormFieldKind,
        FormPage,
        ManagerActionOutcome,
        form_choices,
    )
    from ....application.auth import (
        configure_operator_auth,
        list_operator_certificate_sources,
        select_operator_certificate_source,
    )
    from ....core import AuthProviderKind
    from ._manager_frontend import present_form

    listing = list_operator_certificate_sources()
    if not listing.sources:
        return ManagerActionOutcome(message=tr("flows.manager.action.certificate_none"))
    page = FormPage(
        title=tr("flows.manager.action.certificate"),
        section=tr("flows.manager.action.certificate"),
        fields=(
            FormField(
                key="provider",
                label=tr("flows.manager.action.auth_provider"),
                value=AuthProviderKind.CERTIFICATE.value,
                kind=FormFieldKind.SINGLE_CHOICE,
                choices=form_choices([(kind.value, _provider_label(kind)) for kind in AuthProviderKind]),
                validate=lambda value: None if value else tr("flows.manager.action.auth_provider"),
            ),
            FormField(
                key="certificate",
                label=tr("flows.manager.action.certificate_active"),
                value=listing.active_source,
                kind=FormFieldKind.SINGLE_CHOICE,
                choices=form_choices([(source.name, source.name) for source in listing.sources]),
                validate=lambda value: None if value else tr("flows.manager.action.certificate_active"),
            ),
        ),
    )
    collected = present_form(page)
    if collected is None:
        return ManagerActionOutcome(message=tr("flows.manager.action.abandoned"))
    # Certificate first, then provider: selecting the source before making
    # it the active provider means the provider is never briefly active
    # with no certificate behind it.
    select_operator_certificate_source(name=collected["certificate"])
    configure_operator_auth(collected["provider"])
    return ManagerActionOutcome(
        message=tr(
            "flows.manager.action.certificate_done",
            name=collected["certificate"],
            provider=collected["provider"],
        ),
    )


def _provider_label(kind: object) -> str:
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
    return (censal_pull_action(), export_action(), certificate_action())


__all__ = [
    "censal_pull_action",
    "certificate_action",
    "export_action",
    "manager_actions",
]
