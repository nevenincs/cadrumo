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
from ._models import HelpDocument, HelpEntry, HelpSection, HelpSurface, RootLandingReport


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


def build_root_landing_report(active_profile: str | None) -> RootLandingReport:
    """Return the :class:`RootLandingReport` for caller-supplied profile state.

    The caller owns active-profile discovery and passes the projected display
    label here.  A present profile points operators at ``cadrumo app overview
    status``; a missing profile points at profile creation.  The CLI root
    callback decides whether this landing report or the full overview status is
    emitted under ``root.status``.
    """
    if active_profile:
        return RootLandingReport(
            active_profile=active_profile,
            command="cadrumo app overview status",
            message=tr("cli.operator_surface.landing.active_profile_message", profile=active_profile),
        )
    return RootLandingReport(
        active_profile=None,
        command="cadrumo config profile create NAME",
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


def render_root_landing_text(report: RootLandingReport) -> str:
    """Render the compact single-line view of a :class:`RootLandingReport`.

    New root CLI output uses a multi-line entrypoint renderer for the text half
    of the ``root.status`` envelope. This helper remains the application-level
    plain-text formatter for callers that need the compact message /
    next-command template.
    """
    return tr("cli.operator_surface.landing.text_template", message=report.message, command=report.command)


def _root_help() -> HelpDocument:
    return HelpDocument(
        surface=HelpSurface.ROOT,
        heading=tr(
            "cli.operator_surface.help.root.heading",
            default="cadrumo - local-first Spanish tax workflow",
        ),
        paragraphs=(
            tr(
                "cli.operator_surface.help.root.paragraph_two_roots",
                default="The CLI has exactly two roots: config and app.",
            ),
            tr(
                "cli.operator_surface.help.root.paragraph_type_help",
                default="Use config for local state and app for tax work.",
            ),
            tr(
                "cli.operator_surface.help.root.paragraph_storage_isolation",
                default=(
                    "For an isolated blank state, set CADRUMO_LOCAL_STORAGE_ROOT, "
                    "CADRUMO_SECRET_STORE_BACKEND=file, CADRUMO_SECRET_STORE_DIR, and "
                    "CADRUMO_SECRET_PASSPHRASE; logs default under that storage root."
                ),
            ),
        ),
        sections=(
            HelpSection(
                title=tr("cli.operator_surface.help.root.section_setup"),
                entries=(
                    HelpEntry(
                        command="cadrumo config profile create NAME",
                        description=tr("cli.operator_surface.help.root.setup_create_profile"),
                    ),
                    HelpEntry(
                        command="cadrumo config profile",
                        description=tr("cli.operator_surface.help.root.setup_inspect_profile"),
                    ),
                    HelpEntry(
                        command="cadrumo config auth",
                        description=tr("cli.operator_surface.help.root.setup_configure_auth"),
                    ),
                ),
            ),
            HelpSection(
                title=tr("cli.operator_surface.help.root.section_daily_ledger"),
                entries=(
                    HelpEntry(
                        command="cadrumo app ledger import",
                        description=tr("cli.operator_surface.help.root.ledger_import"),
                    ),
                    HelpEntry(
                        command="cadrumo app ledger list",
                        description=tr("cli.operator_surface.help.root.ledger_list"),
                    ),
                    HelpEntry(
                        command="cadrumo app ledger view",
                        description=tr("cli.operator_surface.help.root.ledger_view"),
                    ),
                    HelpEntry(
                        command="cadrumo app ledger status",
                        description=tr("cli.operator_surface.help.root.ledger_status"),
                    ),
                    HelpEntry(
                        command="cadrumo app ledger review",
                        description=tr("cli.operator_surface.help.root.ledger_review"),
                    ),
                    HelpEntry(
                        command="cadrumo app ledger update",
                        description=tr("cli.operator_surface.help.root.ledger_update"),
                    ),
                    HelpEntry(
                        command="cadrumo app ledger classify",
                        description=tr("cli.operator_surface.help.root.ledger_classify"),
                    ),
                    HelpEntry(
                        command="cadrumo app ledger allocate",
                        description=tr("cli.operator_surface.help.root.ledger_allocate"),
                    ),
                    HelpEntry(
                        command="cadrumo app ledger attach",
                        description=tr("cli.operator_surface.help.root.ledger_attach"),
                    ),
                    HelpEntry(
                        command="cadrumo app ledger archive",
                        description=tr("cli.operator_surface.help.root.ledger_archive"),
                    ),
                    HelpEntry(
                        command="cadrumo app ledger stash",
                        description=tr("cli.operator_surface.help.root.ledger_stash"),
                    ),
                    HelpEntry(
                        command="cadrumo app ledger remove",
                        description=tr("cli.operator_surface.help.root.ledger_remove"),
                    ),
                    HelpEntry(
                        command="cadrumo app ledger reset",
                        description=tr("cli.operator_surface.help.root.ledger_reset"),
                    ),
                    HelpEntry(
                        command="cadrumo app ledger export",
                        description=tr("cli.operator_surface.help.root.ledger_export"),
                    ),
                ),
            ),
            HelpSection(
                title=tr("cli.operator_surface.help.root.section_modelo_lifecycle"),
                entries=(
                    HelpEntry(
                        command="cadrumo app modelo list",
                        description=tr("cli.operator_surface.help.root.modelo_list"),
                    ),
                    HelpEntry(
                        command="cadrumo app modelo bindings list",
                        description=tr("cli.operator_surface.help.root.modelo_bindings_list"),
                    ),
                    HelpEntry(
                        command="cadrumo app modelo work",
                        description=tr("cli.operator_surface.help.root.modelo_work"),
                    ),
                ),
            ),
            HelpSection(
                title=tr("cli.operator_surface.help.root.section_diagnostics"),
                entries=(
                    HelpEntry(
                        command="cadrumo config repair --help",
                        description=tr("cli.operator_surface.help.root.diagnostics_repair"),
                    ),
                    HelpEntry(
                        command="cadrumo app overview status",
                        description=tr("cli.operator_surface.help.root.diagnostics_overview"),
                    ),
                    HelpEntry(
                        command="cadrumo app live filed list",
                        description=tr("cli.operator_surface.help.root.diagnostics_live_filed"),
                    ),
                    HelpEntry(
                        command="cadrumo app review queue",
                        description=tr("cli.operator_surface.help.root.diagnostics_review_queue"),
                    ),
                    HelpEntry(
                        command="cadrumo app registry inspect",
                        description=tr("cli.operator_surface.help.root.diagnostics_registry_inspect"),
                    ),
                ),
            ),
        ),
        footer=tr(
            "cli.operator_surface.help.root.footer",
            default="Run cadrumo config --help or cadrumo app --help for subtree commands.",
        ),
    )


def _config_help() -> HelpDocument:
    return HelpDocument(
        surface=HelpSurface.CONFIG,
        heading=tr(
            "cli.operator_surface.help.config.heading",
            default="cadrumo config - profile, auth, diagnostics",
        ),
        paragraphs=(
            tr(
                "cli.operator_surface.help.config.paragraph_durable_state",
                default="Config commands manage local durable state.",
            ),
            tr(
                "cli.operator_surface.help.config.paragraph_storage_isolation",
                default=(
                    "For an isolated blank state, set CADRUMO_LOCAL_STORAGE_ROOT, "
                    "CADRUMO_SECRET_STORE_BACKEND=file, CADRUMO_SECRET_STORE_DIR, and "
                    "CADRUMO_SECRET_PASSPHRASE; logs default under that storage root."
                ),
            ),
        ),
        sections=(
            HelpSection(
                title=tr("cli.operator_surface.help.config.section_first_run"),
                entries=(
                    HelpEntry(
                        command="cadrumo config profile create NAME",
                        description=tr("cli.operator_surface.help.config.first_run_bootstrap"),
                    ),
                    HelpEntry(
                        command="cadrumo config profile edit NAME",
                        description=tr("cli.operator_surface.help.config.first_run_edit"),
                    ),
                ),
            ),
            HelpSection(
                title=tr("cli.operator_surface.help.config.section_profile_lifecycle"),
                entries=(
                    HelpEntry(
                        command="cadrumo config switch NAME",
                        description=tr("cli.operator_surface.help.config.profile_switch"),
                    ),
                    HelpEntry(
                        command="cadrumo config profile delete NAME",
                        description=tr("cli.operator_surface.help.config.profile_delete"),
                    ),
                    HelpEntry(
                        command="cadrumo config profile duplicate SRC DST",
                        description=tr("cli.operator_surface.help.config.profile_duplicate"),
                    ),
                    HelpEntry(
                        command="cadrumo config profile rename SRC DST",
                        description=tr("cli.operator_surface.help.config.profile_rename"),
                    ),
                ),
            ),
            HelpSection(
                title=tr("cli.operator_surface.help.config.section_profile_inspection"),
                entries=(
                    HelpEntry(
                        command="cadrumo config profile list",
                        description=tr("cli.operator_surface.help.config.profile_list"),
                    ),
                    HelpEntry(
                        command="cadrumo config profile show [NAME]",
                        description=tr("cli.operator_surface.help.config.profile_show"),
                    ),
                    HelpEntry(
                        command="cadrumo config profile status",
                        description=tr("cli.operator_surface.help.config.profile_status"),
                    ),
                    HelpEntry(
                        command="cadrumo config profile history",
                        description=tr("cli.operator_surface.help.config.profile_history"),
                    ),
                ),
            ),
            HelpSection(
                title=tr("cli.operator_surface.help.config.section_authentication"),
                entries=(
                    HelpEntry(
                        command="cadrumo config auth providers",
                        description=tr("cli.operator_surface.help.config.auth_providers"),
                    ),
                    HelpEntry(
                        command="cadrumo config auth configure",
                        description=tr("cli.operator_surface.help.config.auth_configure"),
                    ),
                    HelpEntry(
                        command="cadrumo config auth status",
                        description=tr("cli.operator_surface.help.config.auth_status"),
                    ),
                    HelpEntry(
                        command="cadrumo config auth test",
                        description=tr("cli.operator_surface.help.config.auth_test"),
                    ),
                    HelpEntry(
                        command="cadrumo config auth clear",
                        description=tr("cli.operator_surface.help.config.auth_clear"),
                    ),
                ),
            ),
            HelpSection(
                title=tr("cli.operator_surface.help.config.section_diagnostics"),
                entries=(
                    HelpEntry(
                        command="cadrumo config repair --help",
                        description=tr("cli.operator_surface.help.config.diagnostics_repair"),
                    ),
                    HelpEntry(
                        command="cadrumo config repair logs",
                        description=tr("cli.operator_surface.help.config.diagnostics_logs"),
                    ),
                    HelpEntry(
                        command="cadrumo config repair quarantine",
                        description=tr("cli.operator_surface.help.config.diagnostics_quarantine"),
                    ),
                    HelpEntry(
                        command="cadrumo config repair reset-progress",
                        description=tr("cli.operator_surface.help.config.diagnostics_reset_progress"),
                    ),
                ),
            ),
        ),
        footer=tr("cli.operator_surface.help.config.footer", default="Run cadrumo --help for the full overview."),
    )


def _app_help() -> HelpDocument:
    return HelpDocument(
        surface=HelpSurface.APP,
        heading=tr("cli.operator_surface.help.app.heading", default="cadrumo app - operational tax work"),
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
                        command="cadrumo app overview status",
                        description=tr("cli.operator_surface.help.app.overview_status"),
                    ),
                ),
            ),
            HelpSection(
                title=tr("cli.operator_surface.help.app.section_ledger"),
                entries=(
                    HelpEntry(
                        command="cadrumo app ledger import",
                        description=tr("cli.operator_surface.help.app.ledger_import"),
                    ),
                    HelpEntry(
                        command="cadrumo app ledger add",
                        description=tr("cli.operator_surface.help.app.ledger_add"),
                    ),
                    HelpEntry(
                        command="cadrumo app ledger list",
                        description=tr("cli.operator_surface.help.app.ledger_list"),
                    ),
                    HelpEntry(
                        command="cadrumo app ledger view",
                        description=tr("cli.operator_surface.help.app.ledger_view"),
                    ),
                    HelpEntry(
                        command="cadrumo app ledger status",
                        description=tr("cli.operator_surface.help.app.ledger_status"),
                    ),
                    HelpEntry(
                        command="cadrumo app ledger review",
                        description=tr("cli.operator_surface.help.app.ledger_review"),
                    ),
                    HelpEntry(
                        command="cadrumo app ledger update",
                        description=tr("cli.operator_surface.help.app.ledger_update"),
                    ),
                    HelpEntry(
                        command="cadrumo app ledger classify",
                        description=tr("cli.operator_surface.help.app.ledger_classify"),
                    ),
                    HelpEntry(
                        command="cadrumo app ledger allocate",
                        description=tr("cli.operator_surface.help.app.ledger_allocate"),
                    ),
                    HelpEntry(
                        command="cadrumo app ledger attach",
                        description=tr("cli.operator_surface.help.app.ledger_attach"),
                    ),
                    HelpEntry(
                        command="cadrumo app ledger archive",
                        description=tr("cli.operator_surface.help.app.ledger_archive"),
                    ),
                    HelpEntry(
                        command="cadrumo app ledger stash",
                        description=tr("cli.operator_surface.help.app.ledger_stash"),
                    ),
                    HelpEntry(
                        command="cadrumo app ledger remove",
                        description=tr("cli.operator_surface.help.app.ledger_remove"),
                    ),
                    HelpEntry(
                        command="cadrumo app ledger reset",
                        description=tr("cli.operator_surface.help.app.ledger_reset"),
                    ),
                    HelpEntry(
                        command="cadrumo app ledger export",
                        description=tr("cli.operator_surface.help.app.ledger_export"),
                    ),
                ),
            ),
            HelpSection(
                title=tr("cli.operator_surface.help.app.section_modelo"),
                entries=(
                    HelpEntry(
                        command="cadrumo app modelo list",
                        description=tr("cli.operator_surface.help.app.modelo_list"),
                    ),
                    HelpEntry(
                        command="cadrumo app modelo describe",
                        description=tr("cli.operator_surface.help.app.modelo_describe"),
                    ),
                    HelpEntry(
                        command="cadrumo app modelo bindings",
                        description=tr("cli.operator_surface.help.app.modelo_bindings"),
                    ),
                    HelpEntry(
                        command="cadrumo app modelo work",
                        description=tr("cli.operator_surface.help.app.modelo_work"),
                    ),
                    HelpEntry(
                        command="cadrumo app modelo verification-report list",
                        description=tr("cli.operator_surface.help.app.modelo_verification_report"),
                    ),
                    HelpEntry(
                        command="cadrumo app modelo m036",
                        description=tr("cli.operator_surface.help.app.modelo_m036"),
                    ),
                ),
            ),
            HelpSection(
                title=tr("cli.operator_surface.help.app.section_review_and_registry"),
                entries=(
                    HelpEntry(
                        command="cadrumo app review queue",
                        description=tr("cli.operator_surface.help.app.review_queue"),
                    ),
                    HelpEntry(
                        command="cadrumo app review view ID",
                        description=tr("cli.operator_surface.help.app.review_view"),
                    ),
                    HelpEntry(
                        command="cadrumo app registry inspect",
                        description=tr("cli.operator_surface.help.app.registry_inspect"),
                    ),
                    HelpEntry(
                        command="cadrumo app registry verify",
                        description=tr("cli.operator_surface.help.app.registry_verify"),
                    ),
                ),
            ),
            HelpSection(
                title=tr("cli.operator_surface.help.app.section_live_reads"),
                entries=(
                    HelpEntry(
                        command="cadrumo app live filed list",
                        description=tr("cli.operator_surface.help.app.live_filed_list"),
                    ),
                    HelpEntry(
                        command="cadrumo app live filed pull",
                        description=tr("cli.operator_surface.help.app.live_filed_capture"),
                    ),
                    HelpEntry(
                        command="cadrumo app live filed pull-sources",
                        description=tr("cli.operator_surface.help.app.live_filed_capture_sources"),
                    ),
                ),
            ),
        ),
        footer=tr("cli.operator_surface.help.app.footer", default="Run cadrumo --help for the full overview."),
    )


__all__ = [
    "build_help_document",
    "build_root_landing_report",
    "render_help_text",
    "render_root_landing_text",
]
