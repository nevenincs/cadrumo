import { translator, type Translate } from "../shell/strings";

// The English of the update-progress view's chrome keys while the generated
// catalogue does not yet carry them. A key the catalogue has always wins;
// this table only fills a gap, so it can be deleted once the catalogue has
// every key below.
const P = "desktop.aeat_sync.progress.";
const PENDING: Record<string, string> = {
  "desktop.aeat_sync.area.census.name": "Census",
  "desktop.aeat_sync.area.identity.name": "Identity checks",
  "desktop.aeat_sync.area.notifications.name": "Notifications",
  "desktop.aeat_sync.area.vat.name": "VAT balance",
  "desktop.aeat_sync.area.filed.name": "Filed declarations",
  [`${P}title`]: "Updating from AEAT",
  [`${P}running`]: "Updating…",
  [`${P}stopping`]: "Stopping…",
  [`${P}stopped`]: "Stopped",
  [`${P}paused_status`]: "Paused",
  [`${P}done_all`]: "Done",
  [`${P}done_problems`]: "Done, with problems",
  [`${P}stop`]: "Stop",
  [`${P}stop_hint`]: "Stops after this step",
  [`${P}paused`]: "Your AEAT session timed out — sign in again to continue.",
  [`${P}resume`]: "Sign in again",
  [`${P}waiting`]: "Waiting",
  [`${P}not_started`]: "Not started",
  [`${P}outcome.brought`]: "Done",
  [`${P}outcome.nothing_found`]: "Nothing new",
  [`${P}outcome.failed`]: "Couldn't update",
  [`${P}outcome.unknown`]: "Couldn't confirm",
  [`${P}reason.session_ended`]: "Session timed out",
  [`${P}reason.no_access`]: "Access details not accepted",
  [`${P}reason.unavailable`]: "AEAT didn't answer",
  [`${P}reason.refused`]: "AEAT refused",
  [`${P}reason.other`]: "Something went wrong",
  [`${P}try_again`]: "Try again",
  [`${P}try_again_for`]: "Try again: {name}",
  [`${P}check_again`]: "Check again",
  [`${P}check_again_for`]: "Check again: {name}",
  [`${P}warn_unknown`]: "May already be updated. Check anyway?",
  [`${P}warn_confirm`]: "Check anyway",
  [`${P}warn_cancel`]: "Cancel",
  [`${P}action_failed`]: "Couldn't do that. Try again.",
  [`${P}action_unknown`]: "Couldn't confirm that went through.",
  [`${P}unavailable`]: "Couldn't load progress",
  "desktop.aeat_sync.loading": "Loading…",
};

/** The shell's translator, with the pending English filling any gap. */
export function withPendingWords(locale: string): Translate {
  const base = translator(locale);
  return (key, values) => {
    const found = base(key, values);
    const pending = PENDING[key];
    if (found !== key || pending === undefined) return found;
    return pending.replace(/\{(\w+)\}/g, (whole, name: string) =>
      values && name in values ? String(values[name]) : whole,
    );
  };
}
