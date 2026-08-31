"""CLI root landing renderer for the bare ``cadrumo`` invocation.

Provides the root landing text helper
:func:`render_cli_root_landing_lines`, which converts the
:class:`RootLandingReport` built by :func:`build_root_landing_report` into an
ordered tuple of internationalized (i18n) strings ready for
:func:`emit_envelope`. The
matching JSON payload is :class:`RootStatusResult`; this module owns only the
text-mode lines for the same ``root.status`` surface.

The renderer is presentation-only: active-profile discovery, bucket-session
checks, and overview fallback selection live upstream in the root callback and
operator-surface facade. The helper functions in this module are private; only
``render_cli_root_landing_lines`` is part of the public surface.
"""

from __future__ import annotations

from collections.abc import Iterable

from ...application.operator_surface.help_models import RootLandingReport
from ...core.i18n.render import tr


def render_cli_root_landing_lines(landing: RootLandingReport) -> tuple[str, ...]:
    """Render ``landing`` as the text half of the ``root.status`` envelope.

    The caller supplies an already-projected
    :class:`RootLandingReport`; this function only selects locale keys and
    interpolates the projected profile label. It does not inspect storage,
    resolve profiles, or decide whether the bare root should render the landing
    card or the overview status report.
    """
    lines: list[str] = [
        tr("cli.root.landing.headline"),
        tr("cli.root.landing.tagline"),
        "",
        tr("cli.root.landing.context_heading"),
        f"  {_welcome_line(landing)}",
        "",
    ]
    if landing.active_profile is not None:
        lines.extend(
            (
                f"  {tr('cli.root.landing.session_unchecked')}",
                f"  {tr('cli.root.landing.session_status_command')}",
                f"  {tr('cli.root.landing.session_login_command')}",
                "",
            )
        )
    elif landing.profile_selected:
        lines.extend((f"  {tr('cli.root.landing.profile_repair_command')}", ""))
    lines.extend(_quick_start_lines(landing=landing))
    lines.extend(
        (
            "",
            *_section_lines(),
            "",
            tr("cli.root.landing.privacy_line"),
            "",
            tr("cli.root.landing.help_line"),
        )
    )
    return tuple(lines)


def _welcome_line(landing: RootLandingReport) -> str:
    """Return the localized welcome line for the projected profile state."""
    return landing.message


def _quick_start_lines(*, landing: RootLandingReport) -> list[str]:
    """Return localized quick-start lines keyed by projected profile presence."""
    if landing.active_profile is not None:
        setup_line = tr("cli.root.landing.quick_start_setup_done")
    elif landing.profile_selected:
        setup_line = tr("cli.root.landing.quick_start_setup_repair")
    elif landing.command == "aeat config login NAME":
        setup_line = tr("cli.root.landing.quick_start_setup_login")
    else:
        setup_line = tr("cli.root.landing.quick_start_setup_needed")
    return [
        tr("cli.root.landing.quick_start_heading"),
        setup_line,
        tr("cli.root.landing.quick_start_status"),
        tr("cli.root.landing.quick_start_import"),
        tr("cli.root.landing.quick_start_review"),
        tr("cli.root.landing.quick_start_modelo"),
        tr("cli.root.landing.quick_start_queue"),
        tr("cli.root.landing.quick_start_repair"),
    ]


def _section_lines() -> Iterable[str]:
    """Yield localized command-family rows for the root landing surface."""
    yield tr("cli.root.landing.sections_heading")
    yield tr("cli.root.landing.section_config")
    yield tr("cli.root.landing.section_overview")
    yield tr("cli.root.landing.section_ledger")
    yield tr("cli.root.landing.section_modelo")
    yield tr("cli.root.landing.section_review")
    yield tr("cli.root.landing.section_registry")


__all__ = ["render_cli_root_landing_lines"]
