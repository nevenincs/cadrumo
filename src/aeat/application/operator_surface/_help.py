"""Backend-owned help and discovery documents for the accepted CLI roots."""

from __future__ import annotations

from ...core.i18n import tr
from ._models import HelpDocument, HelpEntry, HelpSection, HelpSurface, RootLandingReport


def build_help_document(surface: HelpSurface | str) -> HelpDocument:
    """Return the curated help document for ``surface``.

    Returns a :class:`HelpDocument` with sections and entries for the
    requested surface.
    """
    resolved = HelpSurface(surface)
    if resolved is HelpSurface.ROOT:
        return _root_help()
    if resolved is HelpSurface.CONFIG:
        return _config_help()
    return _app_help()


def build_root_landing_report(active_profile: str | None) -> RootLandingReport:
    """Return the :class:`RootLandingReport` for the current profile state."""
    if active_profile:
        return RootLandingReport(
            active_profile=active_profile,
            command="aeat app overview status",
            message=tr("cli.operator_surface.landing.active_profile_message", profile=active_profile),
        )
    return RootLandingReport(
        active_profile=None,
        command="aeat config profile create NAME",
        message=tr("cli.operator_surface.landing.no_active_profile_message"),
    )


def render_help_text(document: HelpDocument) -> str:
    """Render a curated help document as terminal-safe plain text."""
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
    """Render the bare-invocation landing report."""
    return tr("cli.operator_surface.landing.text_template", message=report.message, command=report.command)


def _root_help() -> HelpDocument:
    return HelpDocument(
        surface=HelpSurface.ROOT,
        heading=tr(
            "cli.operator_surface.help.root.heading",
            default="aeat - local-first Spanish tax workflow",
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
        ),
        sections=(
            HelpSection(
                title=tr("cli.operator_surface.help.root.section_setup"),
                entries=(
                    HelpEntry(
                        command="aeat config profile create NAME",
                        description=tr("cli.operator_surface.help.root.setup_create_profile"),
                    ),
                    HelpEntry(
                        command="aeat config profile",
                        description=tr("cli.operator_surface.help.root.setup_inspect_profile"),
                    ),
                    HelpEntry(
                        command="aeat config auth",
                        description=tr("cli.operator_surface.help.root.setup_configure_auth"),
                    ),
                ),
            ),
            HelpSection(
                title=tr("cli.operator_surface.help.root.section_daily_ledger"),
                entries=(
                    HelpEntry(
                        command="aeat app ledger import",
                        description=tr("cli.operator_surface.help.root.ledger_import"),
                    ),
                    HelpEntry(
                        command="aeat app ledger list",
                        description=tr("cli.operator_surface.help.root.ledger_list"),
                    ),
                    HelpEntry(
                        command="aeat app ledger view",
                        description=tr("cli.operator_surface.help.root.ledger_view"),
                    ),
                    HelpEntry(
                        command="aeat app ledger status",
                        description=tr("cli.operator_surface.help.root.ledger_status"),
                    ),
                    HelpEntry(
                        command="aeat app ledger review",
                        description=tr("cli.operator_surface.help.root.ledger_review"),
                    ),
                    HelpEntry(
                        command="aeat app ledger update",
                        description=tr("cli.operator_surface.help.root.ledger_update"),
                    ),
                    HelpEntry(
                        command="aeat app ledger classify",
                        description=tr("cli.operator_surface.help.root.ledger_classify"),
                    ),
                    HelpEntry(
                        command="aeat app ledger allocate",
                        description=tr("cli.operator_surface.help.root.ledger_allocate"),
                    ),
                    HelpEntry(
                        command="aeat app ledger attach",
                        description=tr("cli.operator_surface.help.root.ledger_attach"),
                    ),
                    HelpEntry(
                        command="aeat app ledger archive",
                        description=tr("cli.operator_surface.help.root.ledger_archive"),
                    ),
                    HelpEntry(
                        command="aeat app ledger stash",
                        description=tr("cli.operator_surface.help.root.ledger_stash"),
                    ),
                    HelpEntry(
                        command="aeat app ledger remove",
                        description=tr("cli.operator_surface.help.root.ledger_remove"),
                    ),
                    HelpEntry(
                        command="aeat app ledger reset",
                        description=tr("cli.operator_surface.help.root.ledger_reset"),
                    ),
                    HelpEntry(
                        command="aeat app ledger export",
                        description=tr("cli.operator_surface.help.root.ledger_export"),
                    ),
                ),
            ),
            HelpSection(
                title=tr("cli.operator_surface.help.root.section_modelo_lifecycle"),
                entries=(
                    HelpEntry(
                        command="aeat app modelo list",
                        description=tr("cli.operator_surface.help.root.modelo_list"),
                    ),
                    HelpEntry(
                        command="aeat app modelo bindings list",
                        description=tr("cli.operator_surface.help.root.modelo_bindings_list"),
                    ),
                    HelpEntry(
                        command="aeat app modelo work",
                        description=tr("cli.operator_surface.help.root.modelo_work"),
                    ),
                ),
            ),
            HelpSection(
                title=tr("cli.operator_surface.help.root.section_diagnostics"),
                entries=(
                    HelpEntry(
                        command="aeat config repair",
                        description=tr("cli.operator_surface.help.root.diagnostics_repair"),
                    ),
                    HelpEntry(
                        command="aeat app overview status",
                        description=tr("cli.operator_surface.help.root.diagnostics_overview"),
                    ),
                    HelpEntry(
                        command="aeat app live filed list",
                        description=tr("cli.operator_surface.help.root.diagnostics_live_filed"),
                    ),
                    HelpEntry(
                        command="aeat app review queue",
                        description=tr("cli.operator_surface.help.root.diagnostics_review_queue"),
                    ),
                    HelpEntry(
                        command="aeat app registry inspect",
                        description=tr("cli.operator_surface.help.root.diagnostics_registry_inspect"),
                    ),
                ),
            ),
        ),
        footer=tr(
            "cli.operator_surface.help.root.footer",
            default="Run aeat config --help or aeat app --help for subtree commands.",
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
                        command="aeat config profile edit NAME",
                        description=tr("cli.operator_surface.help.config.first_run_edit"),
                    ),
                ),
            ),
            HelpSection(
                title=tr("cli.operator_surface.help.config.section_profile_lifecycle"),
                entries=(
                    HelpEntry(
                        command="aeat config switch NAME",
                        description=tr("cli.operator_surface.help.config.profile_switch"),
                    ),
                    HelpEntry(
                        command="aeat config profile delete NAME",
                        description=tr("cli.operator_surface.help.config.profile_delete"),
                    ),
                    HelpEntry(
                        command="aeat config profile duplicate SRC DST",
                        description=tr("cli.operator_surface.help.config.profile_duplicate"),
                    ),
                    HelpEntry(
                        command="aeat config profile rename SRC DST",
                        description=tr("cli.operator_surface.help.config.profile_rename"),
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
                        command="aeat config profile show [NAME]",
                        description=tr("cli.operator_surface.help.config.profile_show"),
                    ),
                    HelpEntry(
                        command="aeat config profile status",
                        description=tr("cli.operator_surface.help.config.profile_status"),
                    ),
                    HelpEntry(
                        command="aeat config profile censo",
                        description=tr("cli.operator_surface.help.config.profile_censo"),
                    ),
                    HelpEntry(
                        command="aeat config profile history",
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
                        command="aeat config auth clear",
                        description=tr("cli.operator_surface.help.config.auth_clear"),
                    ),
                ),
            ),
            HelpSection(
                title=tr("cli.operator_surface.help.config.section_diagnostics"),
                entries=(
                    HelpEntry(
                        command="aeat config repair",
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
                ),
            ),
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
                ),
            ),
        ),
        footer=tr("cli.operator_surface.help.app.footer", default="Run aeat --help for the full overview."),
    )


__all__ = [
    "build_help_document",
    "build_root_landing_report",
    "render_help_text",
    "render_root_landing_text",
]
