"""CLI root landing renderer for the bare ``aeat`` invocation.

Provides the root landing text helper
:func:`~aeat.entrypoints.cli._root_landing.render_cli_root_landing_lines`, which
converts the
:class:`~aeat.application.operator_surface.RootLandingReport` built by
:func:`~aeat.application.operator_surface.build_root_landing_report` into an
ordered tuple of i18n-translated strings ready for
:func:`~aeat.entrypoints.cli._common._emit_envelope`. The matching JSON payload
is :class:`~aeat.entrypoints.cli._root_payloads.RootStatusResult`; this module owns
only the text-mode lines for the same ``root.status`` surface.

The renderer is presentation-only: active-profile discovery, bucket-session
checks, and overview fallback selection live upstream in
:mod:`~aeat.entrypoints.cli` and :mod:`~aeat.application.operator_surface`. The
helper functions in this module are private; only
``render_cli_root_landing_lines`` is part of the public surface.
"""

from __future__ import annotations

from collections.abc import Iterable

from ...application.operator_surface import RootLandingReport
from ...core.i18n import tr


def render_cli_root_landing_lines(landing: RootLandingReport) -> tuple[str, ...]:
    """Render ``landing`` as the text half of the ``root.status`` envelope.

    The caller supplies an already-projected
    :class:`~aeat.application.operator_surface.RootLandingReport`; this function
    only selects locale keys and interpolates the projected profile label. It
    does not inspect storage, resolve profiles, or decide whether the bare root
    should render the landing card or the overview status report.
    """
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
    """Return the localized welcome line for the projected profile state."""
    if landing.active_profile is None:
        return tr("cli.root.landing.welcome_no_profile")
    return tr("cli.root.landing.welcome_profile", profile=landing.active_profile)


def _quick_start_lines(*, has_profile: bool) -> list[str]:
    """Return localized quick-start lines keyed by projected profile presence."""
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
    """Yield localized command-family rows for the root landing surface."""
    yield tr("cli.root.landing.sections_heading")
    yield tr("cli.root.landing.section_config")
    yield tr("cli.root.landing.section_overview")
    yield tr("cli.root.landing.section_ledger")
    yield tr("cli.root.landing.section_modelo")
    yield tr("cli.root.landing.section_review")
    yield tr("cli.root.landing.section_registry")


__all__ = ["render_cli_root_landing_lines"]
