"""Backend-owned help and discovery documents for the accepted CLI roots."""

from __future__ import annotations

from ._models import HelpDocument, HelpEntry, HelpSection, HelpSurface, RootLandingReport


def build_help_document(surface: HelpSurface | str) -> HelpDocument:
    """Return the curated help document for ``surface``."""

    resolved = HelpSurface(surface)
    if resolved is HelpSurface.ROOT:
        return _root_help()
    if resolved is HelpSurface.CONFIG:
        return _config_help()
    return _app_help()


def build_root_landing_report(active_profile: str | None) -> RootLandingReport:
    """Return the bare-invocation landing report for the current profile state."""

    if active_profile:
        return RootLandingReport(
            active_profile=active_profile,
            command="aeat app overview status",
            message=f"Active profile: {active_profile}. Run aeat app overview status for current readiness.",
        )
    return RootLandingReport(
        active_profile=None,
        command="aeat config init",
        message="No active profile. Run aeat config init to get started.",
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

    return f"{report.message}\nNext: {report.command}"


def _entry(command: str, description: str) -> HelpEntry:
    return HelpEntry(command=command, description=description)


def _section(title: str, *entries: HelpEntry) -> HelpSection:
    return HelpSection(title=title, entries=entries)


def _root_help() -> HelpDocument:
    return HelpDocument(
        surface=HelpSurface.ROOT,
        heading="aeat - local-first Spanish autonomo tax workflow CLI",
        paragraphs=(
            "The CLI has exactly two roots: config and app.",
            "Type aeat config --help or aeat app --help to explore.",
        ),
        sections=(
            _section(
                "Setup",
                _entry("aeat config init", "Create your first profile"),
                _entry("aeat config profile", "Inspect and edit profile values"),
                _entry("aeat config auth", "Configure local AEAT authentication"),
            ),
            _section(
                "Daily ledger work",
                _entry("aeat app ledger import", "Import bank statements"),
                _entry("aeat app ledger list", "List ledger rows"),
                _entry("aeat app ledger view", "View one ledger transaction"),
                _entry("aeat app ledger status", "Summarize ledger readiness"),
                _entry("aeat app ledger review", "Review ledger rows"),
                _entry("aeat app ledger update", "Correct ledger transaction facts"),
                _entry("aeat app ledger classify", "Classify ledger rows"),
                _entry("aeat app ledger allocate", "Record proportional business use"),
                _entry("aeat app ledger attach", "Attach secure evidence to a ledger transaction"),
                _entry("aeat app ledger archive", "Archive one ledger transaction"),
                _entry("aeat app ledger stash", "Stash one ledger transaction"),
                _entry("aeat app ledger remove", "Remove one ledger transaction with confirmation"),
                _entry("aeat app ledger reset", "Reset the active ledger catalogue with confirmation"),
                _entry("aeat app ledger export", "Export canonical ledger rows"),
            ),
            _section(
                "Modelo lifecycle",
                _entry("aeat app modelo list", "List supported modelos"),
                _entry("aeat app modelo bindings list", "Show modelo prerequisites"),
                _entry("aeat app modelo work", "Manage modelo work units"),
            ),
            _section(
                "Diagnostics",
                _entry("aeat config repair", "Run local health checks"),
                _entry("aeat app overview status", "Show cross-domain readiness"),
                _entry("aeat app live filed list", "List filed declarations through an explicit live-read command"),
                _entry("aeat app review queue", "List items needing attention"),
                _entry("aeat app registry inspect", "Inspect local registry data"),
            ),
        ),
        footer="Run aeat config --help or aeat app --help to see that subtree.",
    )


def _config_help() -> HelpDocument:
    return HelpDocument(
        surface=HelpSurface.CONFIG,
        heading="aeat config - profile, auth, diagnostics, and local configuration",
        paragraphs=("Use config for durable local state before operational tax work.",),
        sections=(
            _section(
                "First run",
                _entry("aeat config init --profile NAME", "Bootstrap the first profile"),
                _entry("aeat config profile status", "Show active-profile readiness"),
            ),
            _section(
                "Profile lifecycle",
                _entry("aeat config profile switch NAME", "Switch to an existing profile"),
                _entry("aeat config profile delete NAME", "Delete a profile (--yes confirms)"),
                _entry("aeat config profile duplicate SRC DST", "Copy a profile under a new name"),
                _entry("aeat config profile rename SRC DST", "Rename a profile in place"),
            ),
            _section(
                "Profile inspection",
                _entry("aeat config profile list", "List editable profile keys"),
                _entry("aeat config profile view [NAME]", "Show the live record"),
                _entry("aeat config profile validate", "Validate the active record"),
                _entry("aeat config profile preflight", "Modelo / year / period readiness"),
            ),
            _section(
                "Authentication",
                _entry("aeat config auth providers", "List supported providers"),
                _entry("aeat config auth configure", "Configure one provider"),
                _entry("aeat config auth status", "Show configured auth state"),
                _entry("aeat config auth test", "Test local auth readiness"),
                _entry("aeat config auth clear", "Clear local auth state"),
            ),
            _section(
                "Diagnostics",
                _entry("aeat config repair", "Run local health checks"),
                _entry("aeat config repair logs", "Show log file details"),
                _entry("aeat config repair quarantine", "Quarantine unreadable secure rows"),
                _entry("aeat config repair reset-state", "Reset the workflow-state envelope"),
            ),
        ),
        footer="Run aeat --help for the full overview.",
    )


def _app_help() -> HelpDocument:
    return HelpDocument(
        surface=HelpSurface.APP,
        heading="aeat app - operational tax work for the active profile",
        paragraphs=("Use app for ledger, modelo, live-read, review, overview, and registry workflows.",),
        sections=(
            _section(
                "Overview",
                _entry("aeat app overview status", "Show readiness and counts"),
            ),
            _section(
                "Ledger",
                _entry("aeat app ledger import", "Import bank statements"),
                _entry("aeat app ledger list", "List ledger rows"),
                _entry("aeat app ledger view", "View one ledger transaction"),
                _entry("aeat app ledger status", "Summarize ledger readiness"),
                _entry("aeat app ledger review", "Review ledger rows"),
                _entry("aeat app ledger update", "Correct ledger transaction facts"),
                _entry("aeat app ledger classify", "Classify ledger rows"),
                _entry("aeat app ledger allocate", "Record proportional business use"),
                _entry("aeat app ledger attach", "Attach secure evidence to a ledger transaction"),
                _entry("aeat app ledger archive", "Archive one ledger transaction"),
                _entry("aeat app ledger stash", "Stash one ledger transaction"),
                _entry("aeat app ledger remove", "Remove one ledger transaction with confirmation"),
                _entry("aeat app ledger reset", "Reset the active ledger catalogue with confirmation"),
                _entry("aeat app ledger export", "Export canonical ledger rows"),
            ),
            _section(
                "Modelo",
                _entry("aeat app modelo list", "List supported modelos"),
                _entry("aeat app modelo describe", "Describe one modelo"),
                _entry("aeat app modelo bindings", "Inspect modelo prerequisites"),
                _entry("aeat app modelo work", "Manage modelo work units"),
            ),
            _section(
                "Review and registry",
                _entry("aeat app review queue", "List items needing attention"),
                _entry("aeat app review view ID", "View one review item"),
                _entry("aeat app registry inspect", "Inspect local registry data"),
                _entry("aeat app registry verify", "Verify local registry data"),
            ),
            _section(
                "Live reads",
                _entry("aeat app live filed list", "List filed declarations from AEAT"),
                _entry("aeat app live filed capture", "Capture filed declaration observations"),
                _entry("aeat app live filed capture-sources", "Capture source observations for a target filing"),
            ),
        ),
        footer="Run aeat --help for the full overview.",
    )


__all__ = [
    "build_help_document",
    "build_root_landing_report",
    "render_help_text",
    "render_root_landing_text",
]
