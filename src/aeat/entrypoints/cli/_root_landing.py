"""CLI root landing renderer: formats the bare ``aeat`` invocation screen.

Provides :func:`render_cli_root_landing_lines`, which converts a
:class:`~aeat.application.operator_surface.RootLandingReport` into an
ordered tuple of i18n-translated strings ready for the CLI output layer.
The helper functions in this module are all private; only
``render_cli_root_landing_lines`` is part of the public surface.
"""

from __future__ import annotations

from collections.abc import Iterable

from ...application.operator_surface import RootLandingReport
from ...core.i18n import tr


def render_cli_root_landing_lines(landing: RootLandingReport) -> tuple[str, ...]:
    """Render the bare ``aeat`` invocation as a CLI landing screen."""
    lines: list[str] = [
        tr("cli.root.landing.headline"),
        tr("cli.root.landing.tagline"),
        "",
        _welcome_line(landing),
        "",
    ]
    lines.extend(_quick_start_lines(has_profile=landing.active_profile is not None))
    lines.extend(("", *_section_lines(), "", tr("cli.root.landing.help_line")))
    return tuple(lines)


def _welcome_line(landing: RootLandingReport) -> str:
    if landing.active_profile is None:
        return tr("cli.root.landing.welcome_no_profile")
    return tr("cli.root.landing.welcome_profile", profile=landing.active_profile)


def _quick_start_lines(*, has_profile: bool) -> list[str]:
    setup_line = (
        tr("cli.root.landing.quick_start_setup_done")
        if has_profile
        else tr("cli.root.landing.quick_start_setup_needed")
    )
    return [
        tr("cli.root.landing.quick_start_heading"),
        setup_line,
        tr("cli.root.landing.quick_start_status"),
        tr("cli.root.landing.quick_start_import"),
        tr("cli.root.landing.quick_start_review"),
        tr("cli.root.landing.quick_start_repair"),
    ]


def _section_lines() -> Iterable[str]:
    yield tr("cli.root.landing.sections_heading")
    yield tr("cli.root.landing.section_config")
    yield tr("cli.root.landing.section_overview")
    yield tr("cli.root.landing.section_ledger")
    yield tr("cli.root.landing.section_modelo")
    yield tr("cli.root.landing.section_review")
    yield tr("cli.root.landing.section_registry")


__all__ = ["render_cli_root_landing_lines"]
