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
        "desktop.account.create.back",
        "desktop.account.create.confirm",
        "desktop.account.create.done",
        "desktop.account.create.keep_safe",
        "desktop.account.create.lead",
        "desktop.account.create.mismatch",
        "desktop.account.create.name",
        "desktop.account.create.name_characters",
        "desktop.account.create.name_hyphen",
        "desktop.account.create.name_long",
        "desktop.account.create.name_missing",
        "desktop.account.create.name_taken",
        "desktop.account.create.password_long",
        "desktop.account.create.password_short",
        "desktop.account.create.policy",
        "desktop.account.create.refused",
        "desktop.account.create.submit",
        "desktop.account.create.submitting",
        "desktop.account.create.title",
        "desktop.account.create.unknown",
        "desktop.account.create.wait",
        "desktop.account.first_run_lead",
        "desktop.account.new_profile",
        "desktop.account.no_profile",
        "desktop.account.no_profile_lead",
        "desktop.account.remaining_access",
        "desktop.account.services_down",
        "desktop.account.sign_out",
        "desktop.account.sign_out_failed",
        "desktop.account.sign_out_hint",
        "desktop.account.signed_in",
        "desktop.account.signed_out",
        "desktop.account.switch_hint",
        "desktop.account.switch_profile",
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
        "desktop.agent.add_files",
        "desktop.agent.agent_replied",
        "desktop.agent.approval_allow_always",
        "desktop.agent.approval_allow_once",
        "desktop.agent.approval_reject_always",
        "desktop.agent.approval_reject_once",
        "desktop.agent.approval_review_title",
        "desktop.agent.approval_tool_title",
        "desktop.agent.archive",
        "desktop.agent.archived_empty",
        "desktop.agent.archived_toggle",
        "desktop.agent.attachments",
        "desktop.agent.attachments_refused",
        "desktop.agent.attachments_uploading",
        "desktop.agent.can_read_images",
        "desktop.agent.can_read_pdfs",
        "desktop.agent.can_search_web",
        "desktop.agent.can_use_tools",
        "desktop.agent.can_write",
        "desktop.agent.cancel",
        "desktop.agent.capabilities",
        "desktop.agent.choose_model",
        "desktop.agent.choose_provider",
        "desktop.agent.close_documents",
        "desktop.agent.collapse_members",
        "desktop.agent.condition_budget_exhausted",
        "desktop.agent.condition_credits_exhausted",
        "desktop.agent.condition_invalid_request",
        "desktop.agent.condition_network_unreachable",
        "desktop.agent.condition_provider_overloaded",
        "desktop.agent.condition_throttled",
        "desktop.agent.condition_unauthenticated",
        "desktop.agent.condition_unknown",
        "desktop.agent.condition_usage_exhausted",
        "desktop.agent.consent_allow",
        "desktop.agent.consent_decline",
        "desktop.agent.consent_items",
        "desktop.agent.consent_lead",
        "desktop.agent.consent_note",
        "desktop.agent.consent_title",
        "desktop.agent.delete",
        "desktop.agent.delete_confirm",
        "desktop.agent.delete_confirm_bare",
        "desktop.agent.documents",
        "desktop.agent.documents_attached",
        "desktop.agent.documents_empty",
        "desktop.agent.documents_failed",
        "desktop.agent.documents_review",
        "desktop.agent.drop_accepts",
        "desktop.agent.drop_hint",
        "desktop.agent.drop_release",
        "desktop.agent.drop_release_multiple",
        "desktop.agent.drop_release_single",
        "desktop.agent.drop_title",
        "desktop.agent.effort",
        "desktop.agent.effort_default",
        "desktop.agent.effort_high",
        "desktop.agent.effort_low",
        "desktop.agent.effort_max",
        "desktop.agent.effort_medium",
        "desktop.agent.effort_ultra",
        "desktop.agent.effort_xhigh",
        "desktop.agent.expand_members",
        "desktop.agent.files_summary",
        "desktop.agent.hide",
        "desktop.agent.history",
        "desktop.agent.history_empty",
        "desktop.agent.history_no_match",
        "desktop.agent.lane_no_catalog",
        "desktop.agent.lane_not_admitted",
        "desktop.agent.lane_not_configured",
        "desktop.agent.lane_notice",
        "desktop.agent.lane_signed_out",
        "desktop.agent.lane_unreachable",
        "desktop.agent.members_multiple",
        "desktop.agent.members_single",
        "desktop.agent.message_label",
        "desktop.agent.message_placeholder",
        "desktop.agent.model",
        "desktop.agent.model_written",
        "desktop.agent.more_files",
        "desktop.agent.new_conversation",
        "desktop.agent.no_models",
        "desktop.agent.no_provider",
        "desktop.agent.provider",
        "desktop.agent.questions_answer",
        "desktop.agent.questions_clear",
        "desktop.agent.questions_control",
        "desktop.agent.questions_decline",
        "desktop.agent.questions_invalid",
        "desktop.agent.questions_lead",
        "desktop.agent.questions_missing",
        "desktop.agent.questions_optional",
        "desktop.agent.questions_title",
        "desktop.agent.questions_too_long",
        "desktop.agent.queued",
        "desktop.agent.ran_with",
        "desktop.agent.ready",
        "desktop.agent.refused",
        "desktop.agent.remove_all",
        "desktop.agent.remove_document",
        "desktop.agent.remove_file",
        "desktop.agent.reply_deleting",
        "desktop.agent.reply_failed",
        "desktop.agent.reply_in_progress",
        "desktop.agent.reply_queued",
        "desktop.agent.reply_reconciling",
        "desktop.agent.reply_repair_needed",
        "desktop.agent.reply_stopping",
        "desktop.agent.resize",
        "desktop.agent.restore",
        "desktop.agent.retry",
        "desktop.agent.role_context",
        "desktop.agent.role_information",
        "desktop.agent.role_label",
        "desktop.agent.role_ledger",
        "desktop.agent.row_documents",
        "desktop.agent.search_history",
        "desktop.agent.send",
        "desktop.agent.send_nothing",
        "desktop.agent.send_too_long",
        "desktop.agent.send_waiting",
        "desktop.agent.sent_files",
        "desktop.agent.service_absent",
        "desktop.agent.service_credential_missing",
        "desktop.agent.service_failed",
        "desktop.agent.service_incompatible",
        "desktop.agent.service_root_unmarked",
        "desktop.agent.service_runtime_unavailable",
        "desktop.agent.service_signed_out",
        "desktop.agent.service_starting",
        "desktop.agent.service_stopped",
        "desktop.agent.set_up_providers",
        "desktop.agent.settings",
        "desktop.agent.settings_label",
        "desktop.agent.settings_title",
        "desktop.agent.show",
        "desktop.agent.show_active",
        "desktop.agent.sign_in_first",
        "desktop.agent.status_extracting",
        "desktop.agent.status_failed",
        "desktop.agent.status_needs_review",
        "desktop.agent.status_ready",
        "desktop.agent.status_skipped",
        "desktop.agent.status_uploading",
        "desktop.agent.stop",
        "desktop.agent.stopped",
        "desktop.agent.tool_done",
        "desktop.agent.tool_failed",
        "desktop.agent.tool_kind_delete",
        "desktop.agent.tool_kind_edit",
        "desktop.agent.tool_kind_execute",
        "desktop.agent.tool_kind_fetch",
        "desktop.agent.tool_kind_move",
        "desktop.agent.tool_kind_other",
        "desktop.agent.tool_kind_read",
        "desktop.agent.tool_kind_search",
        "desktop.agent.tool_kind_switch_mode",
        "desktop.agent.tool_kind_think",
        "desktop.agent.tool_pending",
        "desktop.agent.tool_running",
        "desktop.agent.transcript",
        "desktop.agent.transcript_empty",
        "desktop.agent.unavailable",
        "desktop.agent.uploading",
        "desktop.agent.uploading_name",
        "desktop.agent.usage",
        "desktop.agent.waiting_on_you",
        "desktop.agent.welcome_lead",
        "desktop.agent.welcome_title",
        "desktop.agent.working",
        "desktop.agent.you_said",
        "desktop.agent_keys.cancel",
        "desktop.agent_keys.cleanup_pending",
        "desktop.agent_keys.copied",
        "desktop.agent_keys.copy",
        "desktop.agent_keys.copy_failed",
        "desktop.agent_keys.done",
        "desktop.agent_keys.empty",
        "desktop.agent_keys.expired_on",
        "desktop.agent_keys.expires_on",
        "desktop.agent_keys.issue",
        "desktop.agent_keys.issue_lead",
        "desktop.agent_keys.issue_submit",
        "desktop.agent_keys.issued_lead",
        "desktop.agent_keys.issued_on",
        "desktop.agent_keys.issued_once",
        "desktop.agent_keys.issued_title",
        "desktop.agent_keys.issuing",
        "desktop.agent_keys.key_title",
        "desktop.agent_keys.last_used",
        "desktop.agent_keys.lead",
        "desktop.agent_keys.never_used",
        "desktop.agent_keys.reference_label",
        "desktop.agent_keys.refresh",
        "desktop.agent_keys.refused_not_found",
        "desktop.agent_keys.refused_not_signed_in",
        "desktop.agent_keys.refused_outcome_unknown",
        "desktop.agent_keys.refused_person_act_required",
        "desktop.agent_keys.refused_profile_locked",
        "desktop.agent_keys.revoke",
        "desktop.agent_keys.revoke_confirm",
        "desktop.agent_keys.revoke_confirm_action",
        "desktop.agent_keys.revoking",
        "desktop.agent_keys.scope_all_operations",
        "desktop.agent_keys.scope_no_tax_values",
        "desktop.agent_keys.scope_operations_seen",
        "desktop.agent_keys.scope_profile_values",
        "desktop.agent_keys.scope_some_operations",
        "desktop.agent_keys.scope_tax_values",
        "desktop.agent_keys.standing_active",
        "desktop.agent_keys.standing_expired",
        "desktop.agent_keys.standing_pending",
        "desktop.agent_keys.standing_revoked",
        "desktop.agent_keys.standing_suspended",
        "desktop.agent_keys.tax_values",
        "desktop.agent_keys.tax_values_note",
        "desktop.agent_keys.title",
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
        "desktop.calendar.more",
        "desktop.calendar.moved",
        "desktop.calendar.observed",
        "desktop.calendar.open_tui",
        "desktop.calendar.payment_cutoff",
        "desktop.calendar.refresh",
        "desktop.calendar.show_all",
        "desktop.calendar.show_fewer",
        "desktop.calendar.signed_out",
        "desktop.calendar.standing",
        "desktop.calendar.state.due",
        "desktop.calendar.state.filed",
        "desktop.calendar.state.late",
        "desktop.calendar.state.unknown",
        "desktop.calendar.title",
        "desktop.calendar.to_day",
        "desktop.calendar.undetermined",
        "desktop.calendar.view",
        "desktop.calendar.view_list",
        "desktop.calendar.view_months",
        "desktop.calendar.warnings",
        "desktop.calendar.window_unknown",
        "desktop.canvas.lead",
        "desktop.canvas.title",
        "desktop.docs.frame_title",
        "desktop.docs.hide",
        "desktop.docs.loading",
        "desktop.docs.not_bundled",
        "desktop.docs.show",
        "desktop.docs.unavailable",
        "desktop.host.failed",
        "desktop.host.unavailable",
        "desktop.logs.clear_logger",
        "desktop.logs.details",
        "desktop.logs.dropped",
        "desktop.logs.rejected",
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
        "desktop.pane.agent",
        "desktop.pane.docs",
        "desktop.pane.maximize_agent",
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
        "desktop.providers.add_key",
        "desktop.providers.base_url_default",
        "desktop.providers.base_url_label",
        "desktop.providers.base_url_required",
        "desktop.providers.cancel",
        "desktop.providers.cli_installed_signed_in",
        "desktop.providers.cli_installed_signed_out",
        "desktop.providers.cli_not_installed",
        "desktop.providers.cli_unknown",
        "desktop.providers.development_note",
        "desktop.providers.disable",
        "desktop.providers.disable_note",
        "desktop.providers.disabled",
        "desktop.providers.key_label",
        "desktop.providers.key_note",
        "desktop.providers.lead",
        "desktop.providers.mode_provider_sign_in",
        "desktop.providers.mode_token",
        "desktop.providers.readiness_disabled",
        "desktop.providers.readiness_missing",
        "desktop.providers.readiness_not_verified",
        "desktop.providers.readiness_ready",
        "desktop.providers.readiness_sign_in_required",
        "desktop.providers.readiness_unusable",
        "desktop.providers.reason_not_configured",
        "desktop.providers.reason_record_unreadable",
        "desktop.providers.reason_sign_in_with_provider_tool",
        "desktop.providers.refresh",
        "desktop.providers.refused_base_url_rejected",
        "desktop.providers.refused_catalog_unavailable",
        "desktop.providers.refused_invalid_key_format",
        "desktop.providers.refused_not_signed_in",
        "desktop.providers.refused_person_act_required",
        "desktop.providers.refused_profile_locked",
        "desktop.providers.refused_revision_conflict",
        "desktop.providers.replace_key",
        "desktop.providers.reset",
        "desktop.providers.reset_note",
        "desktop.providers.reset_note_development",
        "desktop.providers.save",
        "desktop.providers.saved_unread",
        "desktop.providers.saving",
        "desktop.providers.sign_in_only",
        "desktop.providers.source_environment",
        "desktop.providers.source_profile",
        "desktop.providers.through",
        "desktop.providers.title",
        "desktop.rail.aeat",
        "desktop.rail.agent",
        "desktop.rail.console",
        "desktop.rail.docs",
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
        "desktop.settings.side_by_side",
        "desktop.settings.stacked",
        "desktop.settings.terminal_text",
        "desktop.settings.terminals",
        "desktop.settings.title",
        "desktop.settings.window",
        "desktop.signin.checking",
        "desktop.signin.choose_profile",
        "desktop.signin.dismiss",
        "desktop.signin.hide_password",
        "desktop.signin.lead",
        "desktop.signin.password",
        "desktop.signin.profile",
        "desktop.signin.profiles_unread",
        "desktop.signin.refused.custody_changed",
        "desktop.signin.refused.generation_changed",
        "desktop.signin.refused.invalid",
        "desktop.signin.refused.keyring_unavailable",
        "desktop.signin.refused.login_mismatch",
        "desktop.signin.refused.manager",
        "desktop.signin.refused.other",
        "desktop.signin.refused.profile_locked",
        "desktop.signin.refused.receipt_absent",
        "desktop.signin.refused.receipt_expired",
        "desktop.signin.refused.runtime_unavailable",
        "desktop.signin.refused.throttled",
        "desktop.signin.show_password",
        "desktop.signin.signed_out_lead",
        "desktop.signin.start_services",
        "desktop.signin.install_user_services",
        "desktop.signin.install_machine_services",
        "desktop.signin.install_machine_permission",
        "desktop.signin.refused.installation_unavailable",
        "desktop.signin.refused.installation_refused",
        "desktop.signin.refused.installation_cancelled",
        "desktop.signin.refused.installation_failed",
        "desktop.signin.refused.installation_unsettled",
        "desktop.signin.starting_services",
        "desktop.signin.recovering_services",
        "desktop.signin.services_recovered",
        "desktop.signin.submit",
        "desktop.signin.submitting",
        "desktop.signin.title",
        "desktop.signin.unnameable",
        "desktop.signin.unsupported",
        "desktop.split.resize",
        "desktop.split.side_by_side",
        "desktop.split.stack",
        "desktop.split.swap",
        "desktop.titlebar.close",
        "desktop.titlebar.failed",
        "desktop.titlebar.label",
        "desktop.titlebar.maximize",
        "desktop.titlebar.minimize",
        "desktop.titlebar.profile_menu",
        "desktop.titlebar.restore",
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
DESKTOP_CHROME_AWAITING_CONSUMER: Final[frozenset[str]] = frozenset({"desktop.signin.unsupported"})

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
