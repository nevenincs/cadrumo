"""Desktop shell chrome strings, generated from the canonical locale catalogues.

The desktop shell is a TypeScript frontend, so it cannot call ``tr()``. It
reads one generated JSON file instead, shaped ``{"<locale>": {"<key>":
"<text>"}}`` for every supported locale. The strings themselves live only in
the canonical catalogues under ``desktop.*``; this module declares which keys
the shell requires and projects their values. Nothing here holds a
translation.

:data:`DESKTOP_CHROME_KEYS` is the one declaration of the shell's keys. The
locale key scan reads it as a key source, because no Python call site names
these keys and a text scan would otherwise report every one of them as stale.
A key the shell builds at runtime from a template is declared in full, member
by member, in :data:`DESKTOP_CHROME_FAMILIES`. A declared key whose view is not
written yet is also listed in :data:`DESKTOP_CHROME_AWAITING_CONSUMER`.

Generation refuses rather than degrades: a key missing, blank, echoing its own
name, or carrying placeholders the shell cannot substitute in any locale stops
the build, so a release can never show a raw key.
"""

from __future__ import annotations

import argparse
import json
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from types import MappingProxyType
from typing import Final

from cadrumo.core.atomic_write import atomic_write_text
from cadrumo.core.external_constants import UTF_8_ENCODING
from cadrumo.core.i18n.render import extract_placeholders

from ._paths import LOCALES_DIR, SRC_DIR
from ._status import CatalogueLeafState, classify_catalogue_leaf
from .errors import LocaleError
from .locale_tree import _flatten_raw_locale_leaves
from .locale_yaml import locale_catalogue_source
from .manager import LocaleManager

#: The shell's locales, source locale first.
DESKTOP_LOCALES: Final[tuple[str, ...]] = ("en", "es", "ca", "hu")

#: Keys the shell composes at runtime, as ``prefix -> members``: a template
#: such as ```desktop.example.kind_${kind}``` names ``desktop.example.kind_``
#: here with every member it can produce, and each resulting key is also
#: spelled out in :data:`DESKTOP_CHROME_KEYS`.
DESKTOP_CHROME_FAMILIES: Final[Mapping[str, tuple[str, ...]]] = MappingProxyType[str, tuple[str, ...]](
    {
        "desktop.calendar.aeat.": ("accepted", "justificante_verified", "not_observed", "submitted_observed"),
        "desktop.calendar.event.": ("filing", "message"),
        "desktop.calendar.local.": ("external_baseline_imported", "not_ready_to_file", "ready_to_file"),
        "desktop.calendar.state.": ("due", "filed", "late", "unknown"),
    }
)

DESKTOP_CHROME_KEYS: Final[frozenset[str]] = frozenset(
    {
        "desktop.account.create_profile",
        "desktop.account.in_tui",
        "desktop.account.no_profile",
        "desktop.account.no_profile_lead",
        "desktop.account.remaining_access",
        "desktop.account.services_down",
        "desktop.account.sign_out",
        "desktop.account.sign_out_failed",
        "desktop.account.sign_out_hint",
        "desktop.account.signed_in",
        "desktop.account.signed_out",
        "desktop.account.unknown",
        "desktop.action.docs_back",
        "desktop.action.docs_forward",
        "desktop.action.focus_next",
        "desktop.action.focus_previous",
        "desktop.action.logs_errors",
        "desktop.action.logs_reset",
        "desktop.action.zoom_in",
        "desktop.action.zoom_out",
        "desktop.action.zoom_reset",
        "desktop.calendar.aeat.accepted",
        "desktop.calendar.aeat.justificante_verified",
        "desktop.calendar.aeat.not_observed",
        "desktop.calendar.aeat.submitted_observed",
        "desktop.calendar.as_of",
        "desktop.calendar.close",
        "desktop.calendar.empty",
        "desktop.calendar.event.filing",
        "desktop.calendar.event.message",
        "desktop.calendar.failed",
        "desktop.calendar.loading",
        "desktop.calendar.local.external_baseline_imported",
        "desktop.calendar.local.not_ready_to_file",
        "desktop.calendar.local.ready_to_file",
        "desktop.calendar.maximize",
        "desktop.calendar.modelo",
        "desktop.calendar.moved",
        "desktop.calendar.observed",
        "desktop.calendar.open_tui",
        "desktop.calendar.payment_cutoff",
        "desktop.calendar.refresh",
        "desktop.calendar.signed_out",
        "desktop.calendar.state.due",
        "desktop.calendar.state.filed",
        "desktop.calendar.state.late",
        "desktop.calendar.state.unknown",
        "desktop.calendar.title",
        "desktop.calendar.undetermined",
        "desktop.calendar.view",
        "desktop.calendar.view_list",
        "desktop.calendar.view_months",
        "desktop.calendar.warnings",
        "desktop.calendar.window_unknown",
        "desktop.docs.frame_title",
        "desktop.docs.loading",
        "desktop.host.failed",
        "desktop.host.unavailable",
        "desktop.logs.clear_logger",
        "desktop.logs.details",
        "desktop.logs.dropped",
        "desktop.logs.empty",
        "desktop.logs.errors",
        "desktop.logs.filter",
        "desktop.logs.follow",
        "desktop.logs.follow_hint",
        "desktop.logs.level_all",
        "desktop.logs.level_error",
        "desktop.logs.level_info",
        "desktop.logs.level_warning",
        "desktop.logs.loading",
        "desktop.logs.minimum_level",
        "desktop.logs.no_match",
        "desktop.logs.source_host",
        "desktop.logs.source_python",
        "desktop.logs.sources",
        "desktop.logs.state_available",
        "desktop.logs.state_missing_detail",
        "desktop.logs.state_unreadable",
        "desktop.logs.warnings",
        "desktop.messages.failed",
        "desktop.messages.never",
        "desktop.messages.none_unread",
        "desktop.messages.unread",
        "desktop.menu.clear",
        "desktop.menu.copy",
        "desktop.menu.copy_line",
        "desktop.menu.copy_link",
        "desktop.menu.copy_visible",
        "desktop.menu.only_level",
        "desktop.menu.only_logger",
        "desktop.menu.paste",
        "desktop.menu.select_all",
        "desktop.palette.actions",
        "desktop.palette.close",
        "desktop.palette.documentation",
        "desktop.palette.kind_casilla",
        "desktop.palette.kind_cli",
        "desktop.palette.kind_term",
        "desktop.palette.label",
        "desktop.palette.no_results",
        "desktop.palette.placeholder",
        "desktop.palette.searching",
        "desktop.palette.type_to_search",
        "desktop.palette.unavailable",
        "desktop.pane.docs",
        "desktop.pane.maximize_docs",
        "desktop.pane.maximize_focused",
        "desktop.pane.maximize_panel",
        "desktop.pane.maximize_tui",
        "desktop.pane.restore",
        "desktop.pane.tui",
        "desktop.panel.hide",
        "desktop.panel.label",
        "desktop.panel.resize",
        "desktop.panel.show",
        "desktop.rail.aeat",
        "desktop.rail.console",
        "desktop.rail.docs_home",
        "desktop.rail.label",
        "desktop.rail.logs",
        "desktop.rail.messages",
        "desktop.rail.python",
        "desktop.rail.search",
        "desktop.rail.settings",
        "desktop.rail.tui",
        "desktop.session.enter_restarts",
        "desktop.session.exit_line",
        "desktop.session.exited",
        "desktop.session.failed",
        "desktop.settings.always_dark",
        "desktop.settings.appearance",
        "desktop.settings.dark",
        "desktop.settings.docs_and_tui",
        "desktop.settings.first_pane",
        "desktop.settings.follow_cadrumo",
        "desktop.settings.follow_docs",
        "desktop.settings.language",
        "desktop.settings.layout_reset",
        "desktop.settings.light",
        "desktop.settings.match_appearance",
        "desktop.settings.reset_layout",
        "desktop.settings.session",
        "desktop.settings.side_by_side",
        "desktop.settings.stacked",
        "desktop.settings.terminal_text",
        "desktop.settings.terminals",
        "desktop.settings.title",
        "desktop.settings.window",
        "desktop.signin.checking",
        "desktop.signin.dismiss",
        "desktop.signin.hide_password",
        "desktop.signin.lead",
        "desktop.signin.open_tui",
        "desktop.signin.open_tui_hint",
        "desktop.signin.password",
        "desktop.signin.profile",
        "desktop.signin.refused.custody_changed",
        "desktop.signin.refused.generation_changed",
        "desktop.signin.refused.invalid",
        "desktop.signin.refused.keyring_unavailable",
        "desktop.signin.refused.login_mismatch",
        "desktop.signin.refused.other",
        "desktop.signin.refused.profile_locked",
        "desktop.signin.refused.receipt_absent",
        "desktop.signin.refused.receipt_expired",
        "desktop.signin.refused.runtime_unavailable",
        "desktop.signin.refused.throttled",
        "desktop.signin.show_password",
        "desktop.signin.signed_out_lead",
        "desktop.signin.start_services",
        "desktop.signin.submit",
        "desktop.signin.submitting",
        "desktop.signin.title",
        "desktop.signin.unsupported",
        "desktop.split.resize",
        "desktop.split.side_by_side",
        "desktop.split.stack",
        "desktop.split.swap",
        "desktop.toast.copied",
        "desktop.toast.copy_failed",
        "desktop.toast.open_failed",
        "desktop.toast.paste_failed",
        "desktop.toast.paste_too_large",
        "desktop.tui.hide",
        "desktop.tui.label",
        "desktop.tui.show",
    }
)

#: Declared keys no shell source names yet, because their view is still being
#: written. They are authored and generated like every other key; the drift
#: check holds the rest of the declaration to an exact match with the shell
#: source and refuses any key here once the shell names it, so a key leaves
#: this set when its view lands and the set only shrinks.
DESKTOP_CHROME_AWAITING_CONSUMER: Final[frozenset[str]] = frozenset(
    {"desktop.signin.start_services", "desktop.signin.unsupported"}
)

# The only placeholder form the shell substitutes: ``{name}``.
_SHELL_PLACEHOLDER: Final[re.Pattern[str]] = re.compile(r"\{(\w+)\}")


def _catalogue_leaves(locales_dir: Path, locale: str) -> dict[str, object]:
    """Read one locale's catalogue leaves through the catalogue authority."""
    source = locale_catalogue_source(locales_dir, locale)
    if source is None:
        raise LocaleError(f"No catalogue for desktop locale {locale!r} under {locales_dir}")
    return _flatten_raw_locale_leaves(LocaleManager(SRC_DIR, locales_dir).load_locale(source))


def _shell_placeholders(key: str, locale: str, value: str) -> frozenset[str]:
    """Return the ``{name}`` placeholders of ``value``, refusing any other form."""
    shell = frozenset(str(match.group(1)) for match in _SHELL_PLACEHOLDER.finditer(value))
    if shell != extract_placeholders(value) or "%{" in value:
        raise LocaleError(
            f"{locale}:{key} carries a placeholder the desktop shell cannot substitute; use plain {{name}}"
        )
    return shell


def desktop_chrome_strings(
    locales_dir: Path = LOCALES_DIR,
    *,
    keys: frozenset[str] = DESKTOP_CHROME_KEYS,
    locales: Sequence[str] = DESKTOP_LOCALES,
) -> dict[str, dict[str, str]]:
    """Project the declared keys out of every locale catalogue.

    Raises:
        LocaleError: when any declared key is not an authored string in every
            locale, or its placeholders differ between locales or use a form
            the shell does not substitute.
    """
    refusals: list[str] = []
    strings: dict[str, dict[str, str]] = {}
    for locale in locales:
        leaves = _catalogue_leaves(locales_dir, locale)
        values: dict[str, str] = {}
        for key in sorted(keys):
            leaf = leaves.get(key)
            value = leaf if isinstance(leaf, str) else None
            state = classify_catalogue_leaf(key, value)
            if state is not CatalogueLeafState.AUTHORED or value is None:
                refusals.append(f"{locale}:{key} is {state.value}")
                continue
            values[key] = value
        strings[locale] = values
    if refusals:
        raise LocaleError("Desktop chrome strings are incomplete: " + "; ".join(refusals))
    for key in sorted(keys):
        placeholders = {locale: _shell_placeholders(key, locale, strings[locale][key]) for locale in locales}
        if len(set(placeholders.values())) != 1:
            detail = ", ".join(f"{locale} {sorted(names)}" for locale, names in placeholders.items())
            raise LocaleError(f"{key} has different placeholders across locales: {detail}")
    return strings


def render_desktop_chrome(strings: Mapping[str, Mapping[str, str]]) -> str:
    """Serialize the projection deterministically, keys sorted, as plain UTF-8 JSON."""
    return json.dumps(strings, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    """Write the desktop shell's chrome strings."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    # The build names where its generated inputs go; nothing is written into the source tree by default.
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args(argv)
    try:
        strings = desktop_chrome_strings()
    except LocaleError as exc:
        parser.exit(1, f"refused: {exc}\n")
    output: object = arguments.output
    if not isinstance(output, Path):
        parser.error("--output must resolve to a filesystem path")
    output.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(output, render_desktop_chrome(strings), encoding=UTF_8_ENCODING)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
