"""What the profile manager can do besides edit a field.

The manager page answers "what does my profile hold". These are the
operations an operator reaches for while looking at that answer: take a
copy of it away, and say how they identify to AEAT.

Each one is a plain callable returning a
:class:`~cadrumo.adapters.inbound.tui.ManagerActionOutcome`, so the screen
never learns what a profile bundle or an authentication provider is — it
renders a label, calls the callable, and shows the sentence it gets back.
That is the same injected-door arrangement the rest of this seam uses.

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
    from ....core import AuthProviderKind

_AUTH_PROVIDER_PATH = "auth.provider"
_AUTH_DNI_NIE_PATH = "auth.dni_nie"
_AUTH_SOPORTE_PATH = "auth.numero_soporte"

_CERTIFICATE_KEY = "certificate"
"""Form key for the certificate choice.

Not a profile path: which certificate is active lives in the auth
registry beside the certificate itself, so this row is the one on the
page that does not round-trip through the ``auth`` profile section.
"""


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
    """Collect how this taxpayer authenticates, and whatever that mode needs.

    The point of asking here is that authenticating is what lets the
    profile be filled in from what AEAT already holds, so the credentials
    belong on the profile beside the data they unlock — not in a dotenv
    file the operator has to find and edit by hand.

    Which fields appear follows the mode. Cl@ve authenticates the person,
    so it needs their DNI or NIE and the numero de soporte printed on that
    document. The certificate mode needs none of that and instead selects
    among the certificates already registered through the CLI verb, which
    is where a file and a secret belong.

    Everything collected lands in the encrypted profile store under the
    ``auth`` section, never a plain file.
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
    missing = _missing_clave_credentials(provider, collected)
    if missing:
        # Cl@ve cannot authenticate without both halves, so refuse here
        # rather than let the operator discover it at the first pull, and
        # say which half is absent rather than make them re-read the page.
        return ManagerActionOutcome(
            message=tr("flows.manager.action.auth_clave_incomplete", missing=", ".join(missing)),
        )

    chosen_certificate = _commit_auth_choice(collected)
    return ManagerActionOutcome(
        message=tr("flows.manager.action.certificate_done", name=chosen_certificate or "-", provider=provider),
        overview=build_active_profile_overview(),
    )


def _auth_form_page(
    *,
    on_record: Mapping[str, str],
    certificate_names: Sequence[str],
    active_certificate: str,
) -> FormPage:
    """Build the page the authentication action shows.

    The mode and both Cl@ve fields are offered unconditionally, seeded
    from whatever the profile already holds. Hiding the credential fields
    until a mode was already chosen would make the page unable to set the
    thing it exists to set.

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


def _missing_clave_credentials(provider: str, collected: Mapping[str, str]) -> tuple[str, ...]:
    """Name the Cl@ve credentials the operator left blank, in page order.

    Each name is the very label the field carried on the page, so the
    refusal points at a row the operator just looked at rather than at a
    profile path they have never seen.

    The certificate provider authenticates with an installed certificate
    and needs neither credential, so it is never short of anything.

    Args:
        provider: The chosen provider token.
        collected: The values committed on the page.

    Returns:
        The labels of the missing credentials, empty when none are.
    """
    from ....core import AuthProviderKind

    if provider == AuthProviderKind.CERTIFICATE.value:
        return ()
    return tuple(
        label
        for path, label in (
            (_AUTH_DNI_NIE_PATH, tr("flows.manager.action.auth_dni_nie")),
            (_AUTH_SOPORTE_PATH, tr("flows.manager.action.auth_numero_soporte")),
        )
        if not collected.get(path, "").strip()
    )


def _commit_auth_choice(collected: Mapping[str, str]) -> str:
    """Persist the auth section, select the certificate, activate the provider.

    The three profile fields go through the plural ``set_active_fields``
    door in one call rather than a loop of single writes, so a failure
    part-way cannot leave a provider recorded with half its credentials.

    Certificate before provider: selecting the source before making it
    the active provider means the provider is never briefly active with
    nothing behind it.

    A blank field clears its fact rather than storing an empty string, so
    "I have not answered this" and "this is empty" stay one state.

    Args:
        collected: The values committed on the page.

    Returns:
        The certificate name selected, or ``""`` when the page offered
        none to select.
    """
    from ....application.auth import configure_operator_auth, select_operator_certificate_source
    from ....application.user_profile import set_active_fields
    from ....application.workflow import workflow_state_repository
    from ....domain.user_profile import UserProfileFact

    facts = tuple(
        UserProfileFact(path=path, value=collected.get(path, "").strip() or None)
        for path in (_AUTH_PROVIDER_PATH, _AUTH_DNI_NIE_PATH, _AUTH_SOPORTE_PATH)
    )
    workflow_state_repository().update(lambda state: set_active_fields(state, facts))

    chosen_certificate = collected.get(_CERTIFICATE_KEY, "").strip()
    if chosen_certificate:
        select_operator_certificate_source(name=chosen_certificate)
    configure_operator_auth(collected[_AUTH_PROVIDER_PATH])
    return chosen_certificate


def _auth_facts_on_record() -> dict[str, str]:
    """Return the auth fields already stored, so the page opens on them."""
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
    return (export_action(), certificate_action())


__all__ = [
    "certificate_action",
    "export_action",
    "manager_actions",
]
