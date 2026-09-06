"""Backend-owned help and discovery documents for accepted CLI roots.

The builders return typed :class:`HelpDocument` and
:class:`RootLandingReport` records for the contract-backed root, config, and
app help surfaces declared by :mod:`application.operator_surface`.  CLI
adapters render these records through the shared output boundary; they do not
own the command inventory.

This module is manifest-discovery only: it builds in-memory documents from
locale keys and caller-supplied profile state.  It does not inspect storage,
read environment variables, construct repositories, or decide whether the bare
root should render the landing report or the overview status report.
"""

from __future__ import annotations

from ...core.i18n import tr
from .help_models import HelpDocument, HelpEntry, HelpSection, HelpSurface, RootLandingReport


def build_help_document(surface: HelpSurface | str) -> HelpDocument:
    """Return the curated help document for ``surface``.

    Accepts a :class:`HelpSurface` member or its string token and returns a
    :class:`HelpDocument` with workflow-ordered :class:`HelpSection` and
    :class:`HelpEntry` records for the requested surface.  The returned document
    is consumed by :func:`render_help_text` and by the root/app envelope paths.
    """
    resolved = HelpSurface(surface)
    if resolved is HelpSurface.ROOT:
        return _root_help()
    if resolved is HelpSurface.CONFIG:
        return _config_help()
    return _app_help()


def build_root_landing_report(
    active_profile: str | None,
    *,
    profile_selected: bool | None = None,
    registered_profile_count: int = 0,
) -> RootLandingReport:
    """Return the :class:`RootLandingReport` for caller-supplied profile state.

    The caller owns active-profile discovery and passes the projected display
    label here, separately from whether the profile-selection pointer exists.
    A present label points operators at ``aeat app overview status``; a selected
    profile whose label cannot be resolved points at profile repair; a genuinely
    absent selection points at profile creation. The CLI root callback decides
    whether this landing report or the full overview status is emitted under
    ``root.status``.
    """
    if registered_profile_count < 0:
        raise ValueError("registered_profile_count cannot be negative")
    selected = active_profile is not None if profile_selected is None else profile_selected
    if active_profile is not None:
        return RootLandingReport(
            profile_selected=selected,
            active_profile=active_profile,
            command="aeat app overview status",
            message=tr("cli.operator_surface.landing.active_profile_message", profile=active_profile),
        )
    if selected:
        return RootLandingReport(
            profile_selected=True,
            active_profile=None,
            command="aeat config repair profile",
            message=tr("cli.operator_surface.landing.active_profile_unavailable_message"),
        )
    if registered_profile_count:
        return RootLandingReport(
            profile_selected=False,
            active_profile=None,
            command="aeat config login NAME",
            message=tr("cli.config.errors.no_active_profile_registered"),
        )
    return RootLandingReport(
        profile_selected=False,
        active_profile=None,
        command="aeat config profile create NAME",
        message=tr("cli.operator_surface.landing.no_active_profile_message"),
    )


def render_help_text(document: HelpDocument) -> str:
    """Render a curated :class:`HelpDocument` as terminal-safe plain text.

    The renderer preserves the backend-owned ordering of
    :class:`HelpSection` and :class:`HelpEntry` records, aligns command columns,
    and returns text for CLI adapters to pass through their normal output
    boundary. It does not inspect the live CLI tree; conformance tests own
    the check that rendered command rows still map to mounted command families.
    """
    lines: list[str] = [document.heading, ""]
    for paragraph in document.paragraphs:
        lines.append(paragraph)
    lines.append("")
    for section in document.sections:
        lines.append(section.title)
        width = max(len(entry.command) for entry in section.entries)
        for entry in section.entries:
            lines.append(f"  {entry.command.ljust(width)}  {entry.description}")
        lines.append("")
    lines.append(document.footer)
    return "\n".join(lines)


def _root_help() -> HelpDocument:
    return HelpDocument(
        surface=HelpSurface.ROOT,
        heading=tr(
            "cli.operator_surface.help.root.heading",
            default="CADRUMO - local-first workflow with the Spanish Tax Agency (AEAT)",
        ),
        paragraphs=(
            tr(
                "cli.operator_surface.help.root.paragraph_local_first",
                default="CADRUMO keeps taxpayer data local and exposes exactly two command roots.",
            ),
            tr(
                "cli.operator_surface.help.root.paragraph_config_root",
                default=(
                    "The config root manages profiles, encrypted local data, recovery keys, "
                    "profile sessions, AEAT authentication, and repair."
                ),
            ),
            tr(
                "cli.operator_surface.help.root.paragraph_app_root",
                default=(
                    "The app root manages profile overview, ledger, modelo, review, registry, "
                    "and authenticated AEAT reads."
                ),
            ),
            tr(
                "cli.operator_surface.help.root.paragraph_profile_terms",
                default=(
                    "A profile stores one taxpayer's local facts and settings. The active profile is the selected "
                    "taxpayer context. A profile session provides resumable access to encrypted profile data."
                ),
            ),
            tr(
                "cli.operator_surface.help.root.paragraph_tax_terms",
                default=(
                    "The ledger contains imported money movements. A modelo is an official AEAT declaration form, "
                    "distinct from its local work unit or export."
                ),
            ),
            tr(
                "cli.operator_surface.help.root.paragraph_review_terms",
                default=(
                    "The review queue contains findings that need operator action. The registry contains validated, "
                    "versioned tax-rule data and sources; it holds no taxpayer data and performs no live submission."
                ),
            ),
            tr(
                "cli.operator_surface.help.root.paragraph_privacy",
                default=(
                    "Profile labels stay visible. Tax identities, credentials, storage identifiers, object keys, "
                    "and sensitive web-address content stay protected."
                ),
            ),
            # Deliberately the CONFIG document's key, rendered here as well. An
            # operator cannot set what no surface names, and this operator is
            # frequently an agent holding only the help text -- so the settable
            # storage variables have to be reachable from the root landing, not
            # only from a subcommand's help. Sharing the key rather than minting
            # a root one keeps one translated sentence instead of two that drift.
            tr(
                "cli.operator_surface.help.config.paragraph_storage_isolation",
                default=(
                    "For isolated state, set CADRUMO_LOCAL_STORAGE_ROOT and CADRUMO_SECRET_STORE_DIR. "
                    "Pass profile secrets through --profile-secrets-stdin or --profile-secrets-fd, "
                    "and command secrets through --secrets-stdin or --secrets-fd."
                ),
            ),
        ),
        sections=(
            _root_start_resume_section(),
            HelpSection(
                title=tr("cli.operator_surface.help.root.section_workflow"),
                entries=(
                    HelpEntry(
                        command="aeat config profile status",
                        description=tr("cli.operator_surface.help.root.workflow_profile_status"),
                    ),
                    HelpEntry(
                        command="aeat app overview status",
                        description=tr("cli.operator_surface.help.root.workflow_overview"),
                    ),
                    HelpEntry(
                        command="aeat app ledger import",
                        description=tr("cli.operator_surface.help.root.workflow_import"),
                    ),
                    HelpEntry(
                        command="aeat app ledger review",
                        description=tr("cli.operator_surface.help.root.workflow_ledger_review"),
                    ),
                    HelpEntry(
                        command="aeat app modelo work --help",
                        description=tr("cli.operator_surface.help.root.workflow_modelo"),
                    ),
                    HelpEntry(
                        command="aeat app modelo verification-report list",
                        description=tr("cli.operator_surface.help.root.workflow_verification"),
                    ),
                    HelpEntry(
                        command="aeat app review queue",
                        description=tr("cli.operator_surface.help.root.workflow_review_queue"),
                    ),
                    HelpEntry(
                        command="aeat app registry inspect",
                        description=tr("cli.operator_surface.help.root.workflow_registry"),
                    ),
                ),
            ),
            HelpSection(
                title=tr("cli.operator_surface.help.root.section_recovery"),
                entries=(
                    HelpEntry(
                        command="aeat config login NAME",
                        description=tr("cli.operator_surface.help.root.recovery_login"),
                    ),
                    HelpEntry(
                        command="aeat config repair",
                        description=tr("cli.operator_surface.help.root.recovery_repair"),
                    ),
                    HelpEntry(
                        command="aeat config repair profile",
                        description=tr("cli.operator_surface.help.root.recovery_profile"),
                    ),
                ),
            ),
            HelpSection(
                title=tr("cli.operator_surface.help.root.section_command_families"),
                entries=(
                    HelpEntry(
                        command="aeat config",
                        description=tr("cli.operator_surface.help.root.family_config"),
                    ),
                    HelpEntry(
                        command="aeat app",
                        description=tr("cli.operator_surface.help.root.family_app"),
                    ),
                ),
            ),
            HelpSection(
                title=tr("cli.operator_surface.help.root.section_diagnostics"),
                entries=(
                    HelpEntry(
                        command="aeat app overview status --verbose",
                        description=tr("cli.operator_surface.help.root.diagnostics_overview_verbose"),
                    ),
                    HelpEntry(
                        command="aeat --format json config repair",
                        description=tr("cli.operator_surface.help.root.diagnostics_repair_json"),
                    ),
                    HelpEntry(
                        command="aeat config repair logs",
                        description=tr("cli.operator_surface.help.root.diagnostics_logs"),
                    ),
                    HelpEntry(
                        command="aeat --version --detail",
                        description=tr("cli.operator_surface.help.root.diagnostics_version"),
                    ),
                ),
            ),
        ),
        footer=tr(
            "cli.operator_surface.help.root.footer",
            default=(
                "Add --help for details. Remove sensitive log values, then report bugs at "
                "github.com/nevenincs/cadrumo/issues."
            ),
        ),
    )


def _root_start_resume_section() -> HelpSection:
    """Build the root landing's profile creation and resumption commands."""
    return HelpSection(
        title=tr("cli.operator_surface.help.root.section_start_resume"),
        entries=(
            HelpEntry(
                command="aeat config profile create NAME",
                description=tr("cli.operator_surface.help.root.start_create"),
            ),
            HelpEntry(
                command="aeat config profile list",
                description=tr("cli.operator_surface.help.root.start_list"),
            ),
            HelpEntry(
                command="aeat config login NAME",
                description=tr("cli.operator_surface.help.root.start_login"),
            ),
            HelpEntry(
                command="aeat config profile status",
                description=tr("cli.operator_surface.help.root.start_status"),
            ),
            HelpEntry(
                command="aeat config profile edit [NAME]",
                description=tr("cli.operator_surface.help.root.start_edit"),
            ),
        ),
    )


def _config_storage_section() -> HelpSection:
    """Return the rows that answer where local data lives and what may be freed.

    Extracted from :func:`_config_help` because adding this family pushed the
    document builder through its per-callable size band. The storage verbs are
    a cohesive concern: every one addresses the on-disk tree itself rather than
    anything stored inside it.
    """
    return HelpSection(
        title=tr("cli.operator_surface.help.config.section_storage"),
        entries=(
            HelpEntry(
                command="aeat config storage list",
                description=tr("cli.operator_surface.help.config.storage_list"),
            ),
            HelpEntry(
                command="aeat config storage view AREA",
                description=tr("cli.operator_surface.help.config.storage_view"),
            ),
            HelpEntry(
                command="aeat config storage check",
                description=tr("cli.operator_surface.help.config.storage_check"),
            ),
            HelpEntry(
                command="aeat config storage init",
                description=tr("cli.operator_surface.help.config.storage_init"),
            ),
            HelpEntry(
                command="aeat config storage reclaim AREA --yes",
                description=tr("cli.operator_surface.help.config.storage_reclaim"),
            ),
        ),
    )


def _config_help() -> HelpDocument:
    return HelpDocument(
        surface=HelpSurface.CONFIG,
        heading=tr(
            "cli.operator_surface.help.config.heading",
            default="aeat config - profile, auth, diagnostics",
        ),
        paragraphs=(
            tr(
                "cli.operator_surface.help.config.paragraph_durable_state",
                default="Config commands manage local durable state.",
            ),
            tr(
                "cli.operator_surface.help.config.paragraph_storage_isolation",
                default=(
                    "For isolated state, set CADRUMO_LOCAL_STORAGE_ROOT and CADRUMO_SECRET_STORE_DIR. "
                    "Pass profile secrets through --profile-secrets-stdin or --profile-secrets-fd, "
                    "and command secrets through --secrets-stdin or --secrets-fd."
                ),
            ),
        ),
        sections=(
            HelpSection(
                title=tr("cli.operator_surface.help.config.section_first_run"),
                entries=(
                    HelpEntry(
                        command="aeat config profile create NAME",
                        description=tr("cli.operator_surface.help.config.first_run_bootstrap"),
                    ),
                    HelpEntry(
                        command="aeat config profile edit [NAME]",
                        description=tr("cli.operator_surface.help.config.first_run_edit"),
                    ),
                ),
            ),
            HelpSection(
                title=tr("cli.operator_surface.help.config.section_profile_lifecycle"),
                entries=(
                    HelpEntry(
                        command="aeat config login NAME",
                        description=tr("cli.operator_surface.help.config.profile_login"),
                    ),
                    HelpEntry(
                        command="aeat config logout",
                        description=tr("cli.operator_surface.help.config.profile_logout"),
                    ),
                    HelpEntry(
                        command="aeat config profile delete NAME",
                        description=tr("cli.operator_surface.help.config.profile_delete"),
                    ),
                ),
            ),
            HelpSection(
                title=tr("cli.operator_surface.help.config.section_profile_inspection"),
                entries=(
                    HelpEntry(
                        command="aeat config profile list",
                        description=tr("cli.operator_surface.help.config.profile_list"),
                    ),
                    HelpEntry(
                        command="aeat config profile view [NAME]",
                        description=tr("cli.operator_surface.help.config.profile_view"),
                    ),
                    HelpEntry(
                        command="aeat config profile status",
                        description=tr("cli.operator_surface.help.config.profile_status"),
                    ),
                    HelpEntry(
                        command="aeat config profile history [PROFILE]",
                        description=tr("cli.operator_surface.help.config.profile_history"),
                    ),
                ),
            ),
            HelpSection(
                title=tr("cli.operator_surface.help.config.section_authentication"),
                entries=(
                    HelpEntry(
                        command="aeat config auth providers",
                        description=tr("cli.operator_surface.help.config.auth_providers"),
                    ),
                    HelpEntry(
                        command="aeat config auth configure",
                        description=tr("cli.operator_surface.help.config.auth_configure"),
                    ),
                    HelpEntry(
                        command="aeat config auth status",
                        description=tr("cli.operator_surface.help.config.auth_status"),
                    ),
                    HelpEntry(
                        command="aeat config auth test",
                        description=tr("cli.operator_surface.help.config.auth_test"),
                    ),
                    HelpEntry(
                        command="aeat config auth logout",
                        description=tr("cli.operator_surface.help.config.auth_logout"),
                    ),
                    HelpEntry(
                        command="aeat config auth reset",
                        description=tr("cli.operator_surface.help.config.auth_reset"),
                    ),
                    HelpEntry(
                        command="aeat config auth certificate check",
                        description=tr("cli.operator_surface.help.config.certificate_check"),
                    ),
                    HelpEntry(
                        command="aeat config auth certificate secret set",
                        description=tr("cli.operator_surface.help.config.certificate_secret_set"),
                    ),
                    HelpEntry(
                        command="aeat config auth certificate secret remove",
                        description=tr("cli.operator_surface.help.config.certificate_secret_remove"),
                    ),
                ),
            ),
            HelpSection(
                title=tr("cli.operator_surface.help.config.section_diagnostics"),
                entries=(
                    HelpEntry(
                        command="aeat config repair --help",
                        description=tr("cli.operator_surface.help.config.diagnostics_repair"),
                    ),
                    HelpEntry(
                        command="aeat config repair logs",
                        description=tr("cli.operator_surface.help.config.diagnostics_logs"),
                    ),
                    HelpEntry(
                        command="aeat config repair quarantine",
                        description=tr("cli.operator_surface.help.config.diagnostics_quarantine"),
                    ),
                    HelpEntry(
                        command="aeat config repair reset-progress",
                        description=tr("cli.operator_surface.help.config.diagnostics_reset_progress"),
                    ),
                    HelpEntry(
                        command="aeat config reset start --yes",
                        description=tr("cli.operator_surface.help.config.reset_start"),
                    ),
                    HelpEntry(
                        command="aeat config reset status",
                        description=tr("cli.operator_surface.help.config.reset_status"),
                    ),
                    HelpEntry(
                        command="aeat config reset resume --yes",
                        description=tr("cli.operator_surface.help.config.reset_resume"),
                    ),
                ),
            ),
            _config_storage_section(),
        ),
        footer=tr("cli.operator_surface.help.config.footer", default="Run aeat --help for the full overview."),
    )


def _app_help() -> HelpDocument:
    return HelpDocument(
        surface=HelpSurface.APP,
        heading=tr("cli.operator_surface.help.app.heading", default="aeat app - operational tax work"),
        paragraphs=(
            tr(
                "cli.operator_surface.help.app.paragraph_operational_workflow",
                default="App commands operate on the active profile bucket.",
            ),
        ),
        sections=(
            HelpSection(
                title=tr("cli.operator_surface.help.app.section_overview"),
                entries=(
                    HelpEntry(
                        command="aeat app overview status",
                        description=tr("cli.operator_surface.help.app.overview_status"),
                    ),
                ),
            ),
            HelpSection(
                title=tr("cli.operator_surface.help.app.section_ledger"),
                entries=(
                    HelpEntry(
                        command="aeat app ledger import",
                        description=tr("cli.operator_surface.help.app.ledger_import"),
                    ),
                    HelpEntry(
                        command="aeat app ledger add",
                        description=tr("cli.operator_surface.help.app.ledger_add"),
                    ),
                    HelpEntry(
                        command="aeat app ledger list",
                        description=tr("cli.operator_surface.help.app.ledger_list"),
                    ),
                    HelpEntry(
                        command="aeat app ledger view",
                        description=tr("cli.operator_surface.help.app.ledger_view"),
                    ),
                    HelpEntry(
                        command="aeat app ledger status",
                        description=tr("cli.operator_surface.help.app.ledger_status"),
                    ),
                    HelpEntry(
                        command="aeat app ledger review",
                        description=tr("cli.operator_surface.help.app.ledger_review"),
                    ),
                    HelpEntry(
                        command="aeat app ledger update",
                        description=tr("cli.operator_surface.help.app.ledger_update"),
                    ),
                    HelpEntry(
                        command="aeat app ledger classify",
                        description=tr("cli.operator_surface.help.app.ledger_classify"),
                    ),
                    HelpEntry(
                        command="aeat app ledger allocate",
                        description=tr("cli.operator_surface.help.app.ledger_allocate"),
                    ),
                    HelpEntry(
                        command="aeat app ledger attach",
                        description=tr("cli.operator_surface.help.app.ledger_attach"),
                    ),
                    HelpEntry(
                        command="aeat app ledger archive",
                        description=tr("cli.operator_surface.help.app.ledger_archive"),
                    ),
                    HelpEntry(
                        command="aeat app ledger stash",
                        description=tr("cli.operator_surface.help.app.ledger_stash"),
                    ),
                    HelpEntry(
                        command="aeat app ledger remove",
                        description=tr("cli.operator_surface.help.app.ledger_remove"),
                    ),
                    HelpEntry(
                        command="aeat app ledger reset",
                        description=tr("cli.operator_surface.help.app.ledger_reset"),
                    ),
                    HelpEntry(
                        command="aeat app ledger export",
                        description=tr("cli.operator_surface.help.app.ledger_export"),
                    ),
                ),
            ),
            HelpSection(
                title=tr("cli.operator_surface.help.app.section_modelo"),
                entries=(
                    HelpEntry(
                        command="aeat app modelo list",
                        description=tr("cli.operator_surface.help.app.modelo_list"),
                    ),
                    HelpEntry(
                        command="aeat app modelo describe",
                        description=tr("cli.operator_surface.help.app.modelo_describe"),
                    ),
                    HelpEntry(
                        command="aeat app modelo bindings",
                        description=tr("cli.operator_surface.help.app.modelo_bindings"),
                    ),
                    HelpEntry(
                        command="aeat app modelo work",
                        description=tr("cli.operator_surface.help.app.modelo_work"),
                    ),
                    HelpEntry(
                        command="aeat app modelo verification-report list",
                        description=tr("cli.operator_surface.help.app.modelo_verification_report"),
                    ),
                    HelpEntry(
                        command="aeat app modelo m036",
                        description=tr("cli.operator_surface.help.app.modelo_m036"),
                    ),
                    HelpEntry(
                        command="aeat app modelo audit view",
                        description=tr("cli.operator_surface.help.app.modelo_audit_view"),
                    ),
                    HelpEntry(
                        command="aeat app modelo audit check",
                        description=tr("cli.operator_surface.help.app.modelo_audit_check"),
                    ),
                    HelpEntry(
                        command="aeat app modelo audit export",
                        description=tr("cli.operator_surface.help.app.modelo_audit_export"),
                    ),
                ),
            ),
            HelpSection(
                title=tr("cli.operator_surface.help.app.section_review_and_registry"),
                entries=(
                    HelpEntry(
                        command="aeat app review queue",
                        description=tr("cli.operator_surface.help.app.review_queue"),
                    ),
                    HelpEntry(
                        command="aeat app review view ID",
                        description=tr("cli.operator_surface.help.app.review_view"),
                    ),
                    HelpEntry(
                        command="aeat app registry inspect",
                        description=tr("cli.operator_surface.help.app.registry_inspect"),
                    ),
                    HelpEntry(
                        command="aeat app registry verify",
                        description=tr("cli.operator_surface.help.app.registry_verify"),
                    ),
                ),
            ),
            HelpSection(
                title=tr("cli.operator_surface.help.app.section_live_reads"),
                entries=(
                    HelpEntry(
                        command="aeat app live filed list",
                        description=tr("cli.operator_surface.help.app.live_filed_list"),
                    ),
                    HelpEntry(
                        command="aeat app live filed pull",
                        description=tr("cli.operator_surface.help.app.live_filed_capture"),
                    ),
                    HelpEntry(
                        command="aeat app live filed pull-sources",
                        description=tr("cli.operator_surface.help.app.live_filed_capture_sources"),
                    ),
                    HelpEntry(
                        command="aeat app live filed discover",
                        description=tr("cli.operator_surface.help.app.live_filed_discover"),
                    ),
                    HelpEntry(
                        command="aeat app live filed pull-all",
                        description=tr("cli.operator_surface.help.app.live_filed_pull_all"),
                    ),
                ),
            ),
        ),
        footer=tr("cli.operator_surface.help.app.footer", default="Run aeat --help for the full overview."),
    )


__all__ = [
    "build_help_document",
    "build_root_landing_report",
    "render_help_text",
]
