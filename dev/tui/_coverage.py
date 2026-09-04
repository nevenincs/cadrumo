"""Which rendered surface puts which interface class on screen.

The inventory is derived by reading the source tree, and the surface list is
answered by the harness; neither knows about the other. This module is the
join, and it is the one hand-written table in the package -- because the fact
it records, "opening the registration surface paints RegistrationScreen", is a
statement about what the harness builds, and a development tool forbidden
from importing the TUI cannot observe that from outside.

What keeps a hand-written table honest is that it is checked, not trusted.
Every qualname here must exist in the AST inventory and every surface name
must exist in the harness listing, so a rename breaks the check rather than
quietly turning a covered interface into an uncovered one. Nothing here
excuses an interface from coverage: an interface absent from this table is
reported as NOT RENDERED, which is a gap to close rather than a state to
declare acceptable.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from ._inventory import Interface

RENDERED_BY: Final[dict[str, tuple[str, ...]]] = {
    "registration": (
        "cadrumo.entrypoints.tui.secret.registration.RegistrationScreen",
        "cadrumo.entrypoints.tui.secret.credentials.CredentialScreen",
    ),
    "login": (
        "cadrumo.entrypoints.tui.secret.login.LoginScreen",
        "cadrumo.entrypoints.tui.secret.credentials.CredentialScreen",
    ),
    "manager": ("cadrumo.entrypoints.tui.profile.overview.ProfileManagerScreen",),
    "status": ("cadrumo.entrypoints.tui.profile.status.StatusScreen",),
    "form": (
        "cadrumo.entrypoints.tui.components.form_screen.FormApp",
        "cadrumo.entrypoints.tui.components.form_screen.FormScreen",
    ),
    # The question view this surface opens on is a pane rather than a screen, so
    # it is not an interface in the inventory's vocabulary and cannot be named
    # here. One entry is the whole of what this surface paints.
    "modelo-work-wizard": ("cadrumo.entrypoints.tui.flows.app.FlowScreen",),
}
"""Surface name to the interface classes opening it paints.

Only the classes a surface paints at its OPENING frame are listed. A screen
reached by pressing a key -- the flow review screen, a confirm dialog, a
field-edit modal -- is genuinely not rendered by this run, and claiming it
here would make the coverage report lie in the one direction that matters.
"""


class InventoryDisposition(StrEnum):
    """Exhaustive review disposition for one discovered interface."""

    COVERED = "covered by real fixture"
    FIXTURE_NEEDED = "fixture needed"
    ABSTRACT_BASE = "abstract or generic host base"
    DEVELOPMENT_ONLY = "development-only candidate"


@dataclass(frozen=True, slots=True)
class InterfaceClassification:
    """Stable review identity and explicit disposition for one interface."""

    disposition: InventoryDisposition
    surface_id: str | None = None
    note: str = ""


def _covered(surface_id: str) -> InterfaceClassification:
    return InterfaceClassification(InventoryDisposition.COVERED, surface_id)


def _needed(surface_id: str) -> InterfaceClassification:
    return InterfaceClassification(InventoryDisposition.FIXTURE_NEEDED, surface_id)


def _base(note: str) -> InterfaceClassification:
    return InterfaceClassification(InventoryDisposition.ABSTRACT_BASE, note=note)


def _development(note: str) -> InterfaceClassification:
    return InterfaceClassification(InventoryDisposition.DEVELOPMENT_ONLY, note=note)


CLASSIFICATIONS: Final[dict[str, InterfaceClassification]] = {
    "cadrumo.entrypoints.tui.aeat_sync.screens.AeatSyncCensusScreen": _needed("aeat-sync-census"),
    "cadrumo.entrypoints.tui.aeat_sync.screens.AeatSyncEvidenceComparisonScreen": _needed(
        "aeat-sync-evidence-comparison"
    ),
    "cadrumo.entrypoints.tui.aeat_sync.screens.AeatSyncFiledDeclarationsScreen": _needed(
        "aeat-sync-filed-declarations"
    ),
    "cadrumo.entrypoints.tui.aeat_sync.screens.AeatSyncNotificationsScreen": _needed("aeat-sync-notifications"),
    "cadrumo.entrypoints.tui.aeat_sync.screens.AeatSyncOverviewScreen": _needed("aeat-sync-overview"),
    "cadrumo.entrypoints.tui.aeat_sync.screens.AeatSyncReconciliationScreen": _needed("aeat-sync-reconciliation"),
    "cadrumo.entrypoints.tui.aeat_sync.screens.AeatSyncWorkspaceScreen": _base(
        "shared AEAT Sync navigation and action shell"
    ),
    "cadrumo.entrypoints.tui.app.CadrumoTuiApp": _needed("workbench-root"),
    "cadrumo.entrypoints.tui.components.dialogs.ChoiceEditScreen": _needed("dialog-choice-edit"),
    "cadrumo.entrypoints.tui.components.dialogs.ConfirmScreen": _needed("dialog-confirm"),
    "cadrumo.entrypoints.tui.components.dialogs.OneChoiceEditScreen": _needed("dialog-one-choice-edit"),
    "cadrumo.entrypoints.tui.components.dialogs.TextEditScreen": _needed("dialog-text-edit"),
    "cadrumo.entrypoints.tui.components.dialogs._FieldEditScreen": _base("private field-editor base"),
    "cadrumo.entrypoints.tui.components.form_screen.FormApp": _needed("form-production-caller"),
    "cadrumo.entrypoints.tui.components.form_screen.FormScreen": _needed("form-production-caller"),
    "cadrumo.entrypoints.tui.components.host.ScreenHostApp": _base("generic single-screen test and dev host"),
    "cadrumo.entrypoints.tui.declarations.calendar.DeclarationsCalendarScreen": _needed("declarations-calendar"),
    "cadrumo.entrypoints.tui.declarations.controller.DeclarationsWorkspaceScreen": _base(
        "shared Declarations workspace shell"
    ),
    "cadrumo.entrypoints.tui.declarations.filing_history.DeclarationsFilingHistoryScreen": _needed(
        "declarations-filing-history"
    ),
    "cadrumo.entrypoints.tui.declarations.overview.DeclarationsModeloWorkspaceLauncherScreen": _needed(
        "declarations-modelo-launcher"
    ),
    "cadrumo.entrypoints.tui.declarations.overview.DeclarationsOverviewScreen": _base(
        "abstract declarations overview host"
    ),
    "cadrumo.entrypoints.tui.declarations.revisions.DeclarationsRevisionsScreen": _needed("declarations-revisions"),
    "cadrumo.entrypoints.tui.declarations.routes.DeclarationsUnavailableScreen": _needed("declarations-unavailable"),
    "cadrumo.entrypoints.tui.devtools.home_candidates.DueDrivenHomeCandidateScreen": _development(
        "retained design candidate, not the production Home factory"
    ),
    "cadrumo.entrypoints.tui.devtools.home_candidates.TaskLauncherHomeCandidateScreen": _development(
        "retained design candidate, not the production Home factory"
    ),
    "cadrumo.entrypoints.tui.devtools.home_candidates._ProjectionCandidateScreen": _base(
        "development-only candidate substrate"
    ),
    "cadrumo.entrypoints.tui.flows.app.FlowScreen": _covered("modelo-work-wizard"),
    "cadrumo.entrypoints.tui.home.HomeScreen": _needed("home"),
    "cadrumo.entrypoints.tui.ledger.classification.LedgerClassificationScreen": _needed("ledger-classification"),
    "cadrumo.entrypoints.tui.ledger.controller.LedgerWorkspaceScreen": _base("shared Ledger navigation shell"),
    "cadrumo.entrypoints.tui.ledger.entries.LedgerEntriesScreen": _needed("ledger-entries"),
    "cadrumo.entrypoints.tui.ledger.evidence.LedgerEvidenceScreen": _needed("ledger-evidence"),
    "cadrumo.entrypoints.tui.ledger.import_flow.LedgerImportScreen": _needed("ledger-import"),
    "cadrumo.entrypoints.tui.ledger.overview.LedgerOverviewScreen": _needed("ledger-overview"),
    "cadrumo.entrypoints.tui.ledger.reconciliation.LedgerReconciliationScreen": _needed("ledger-reconciliation"),
    "cadrumo.entrypoints.tui.ledger.review.LedgerReviewScreen": _needed("ledger-review"),
    "cadrumo.entrypoints.tui.ledger.routes.LedgerUnavailableScreen": _needed("ledger-unavailable"),
    "cadrumo.entrypoints.tui.ledger.workspace_presentation.LedgerConfirmationFlowScreen": _base(
        "shared confirmation-state shell"
    ),
    "cadrumo.entrypoints.tui.modelo.edit.screen.ModeloEditScreen": _needed("modelo-edit"),
    "cadrumo.entrypoints.tui.modelo.view.filing.ModeloWorkspaceFilingScreen": _needed("modelo-filing"),
    "cadrumo.entrypoints.tui.modelo.view.inputs.ModeloWorkspaceInputsScreen": _needed("modelo-inputs"),
    "cadrumo.entrypoints.tui.modelo.view.overview.ModeloWorkspaceOverviewScreen": _needed("modelo-overview"),
    "cadrumo.entrypoints.tui.modelo.view.provenance.ModeloWorkspaceProvenanceScreen": _needed("modelo-provenance"),
    "cadrumo.entrypoints.tui.modelo.view.results.ModeloWorkspaceResultsScreen": _needed("modelo-results"),
    "cadrumo.entrypoints.tui.modelo.view.verification.ModeloWorkspaceVerificationScreen": _needed(
        "modelo-verification"
    ),
    "cadrumo.entrypoints.tui.modelo.view.work_review.ModeloWorkReviewApp": _needed("modelo-work-review"),
    "cadrumo.entrypoints.tui.modelo.view.work_review.ModeloWorkReviewScreen": _needed("modelo-work-review"),
    "cadrumo.entrypoints.tui.modelo.view.work_select.ModeloWorkSelectApp": _needed("modelo-work-select"),
    "cadrumo.entrypoints.tui.modelo.view.work_select.ModeloWorkSelectScreen": _needed("modelo-work-select"),
    "cadrumo.entrypoints.tui.operations.modal.OperationModal": _needed("operation-modal"),
    "cadrumo.entrypoints.tui.profile.app.ProfileJourneyScreen": _needed("profile-journey"),
    "cadrumo.entrypoints.tui.profile.overview.FieldEditScreen": _needed("profile-field-edit"),
    "cadrumo.entrypoints.tui.profile.overview.ProfileManagerScreen": _covered("manager"),
    "cadrumo.entrypoints.tui.profile.status.StatusScreen": _covered("status"),
    "cadrumo.entrypoints.tui.profile.sync_review.CensalFieldReviewScreen": _needed("profile-censal-review"),
    "cadrumo.entrypoints.tui.secret.credentials.CredentialScreen": _base(
        "generic credential base painted through login and registration"
    ),
    "cadrumo.entrypoints.tui.secret.login.LoginScreen": _covered("login"),
    "cadrumo.entrypoints.tui.secret.passphrase.PassphraseScreen": _needed("secret-passphrase"),
    "cadrumo.entrypoints.tui.secret.registration.RecoveryWordsScreen": _needed("secret-recovery-words"),
    "cadrumo.entrypoints.tui.secret.registration.RegistrationScreen": _covered("registration"),
}
"""Exhaustive, stable classification joined against the derived source census."""


def merge_rendered_by(reported: Mapping[str, tuple[str, ...]]) -> dict[str, tuple[str, ...]]:
    """Join the reviewer's static table with what the harness itself declares.

    The static entries predate surfaces that declare their own interfaces and
    stay authoritative for those; anything the registry reports is added as it
    is. Reading both is what keeps the inventory from claiming a surface is
    unrendered after its fixture has landed.
    """
    merged = dict(RENDERED_BY)
    merged.update(reported)
    return merged


def notes(rendered_table: Mapping[str, tuple[str, ...]] = RENDERED_BY) -> dict[str, str]:
    """Describe each interface's disposition against the live coverage.

    The disposition is DERIVED, not declared: an interface some surface paints
    is covered whatever the static table last said, so a landed fixture cannot
    keep reading as a gap. Only the non-renderable kinds keep their authored
    note, because no fixture can change what they are.
    """
    painted = {qualname for qualnames in rendered_table.values() for qualname in qualnames}
    resolved: dict[str, str] = {}
    for qualname, classification in CLASSIFICATIONS.items():
        disposition = classification.disposition
        if disposition in {InventoryDisposition.COVERED, InventoryDisposition.FIXTURE_NEEDED}:
            disposition = (
                InventoryDisposition.COVERED if qualname in painted else InventoryDisposition.FIXTURE_NEEDED
            )
        resolved[qualname] = "; ".join(part for part in (disposition.value, classification.note) if part)
    return resolved


NOTES: Final[dict[str, str]] = notes()


class CoverageError(RuntimeError):
    """The coverage table disagrees with the inventory or the harness."""


def check(
    interfaces: tuple[Interface, ...],
    surfaces: tuple[str, ...],
    *,
    classifications: Mapping[str, InterfaceClassification] = CLASSIFICATIONS,
    rendered_table: Mapping[str, tuple[str, ...]] = RENDERED_BY,
) -> None:
    """Refuse a coverage table that has drifted from what actually exists.

    Run before a render rather than after, so a stale table is a refusal with
    a name in it instead of a report that quietly under-claims coverage.
    """
    known = {interface.qualname for interface in interfaces}
    classified = set(classifications)
    problems = [f"unclassified interface {qualname!r}" for qualname in sorted(known - classified)]
    problems.extend(
        f"stale classification for unknown interface {qualname!r}" for qualname in sorted(classified - known)
    )
    problems.extend(
        f"coverage names unknown surface {surface!r}" for surface in rendered_table if surface not in surfaces
    )
    problems.extend(
        f"coverage maps {surface!r} to unknown interface {qualname!r}"
        for surface, qualnames in rendered_table.items()
        for qualname in qualnames
        if qualname not in known
    )
    for qualname, classification in classifications.items():
        if classification.disposition in {InventoryDisposition.COVERED, InventoryDisposition.FIXTURE_NEEDED}:
            if classification.surface_id is None:
                problems.append(f"concrete interface {qualname!r} has no stable surface identity")
        elif classification.surface_id is not None:
            problems.append(f"non-renderable interface {qualname!r} declares a surface identity")
        if classification.disposition is InventoryDisposition.COVERED and classification.surface_id is not None:
            if classification.surface_id not in surfaces:
                problems.append(f"covered interface {qualname!r} names absent surface {classification.surface_id!r}")
            elif qualname not in rendered_table.get(classification.surface_id, ()):
                problems.append(
                    f"covered interface {qualname!r} is not mapped by surface {classification.surface_id!r}"
                )
    if problems:
        raise CoverageError("; ".join(problems))


def fixture_needed(interfaces: tuple[Interface, ...]) -> tuple[Interface, ...]:
    """Return the concrete census still awaiting production-shaped fixtures."""
    check(interfaces, tuple(RENDERED_BY))
    return tuple(
        interface
        for interface in interfaces
        if CLASSIFICATIONS[interface.qualname].disposition is InventoryDisposition.FIXTURE_NEEDED
    )


def rendered_by(
    qualname: str,
    surfaces: tuple[str, ...],
    *,
    rendered_table: Mapping[str, tuple[str, ...]] = RENDERED_BY,
) -> tuple[str, ...]:
    """Which of ``surfaces`` paint the interface named ``qualname``."""
    return tuple(surface for surface in surfaces if qualname in rendered_table.get(surface, ()))


__all__ = [
    "CLASSIFICATIONS",
    "NOTES",
    "RENDERED_BY",
    "CoverageError",
    "InterfaceClassification",
    "InventoryDisposition",
    "check",
    "fixture_needed",
    "merge_rendered_by",
    "notes",
    "rendered_by",
]
