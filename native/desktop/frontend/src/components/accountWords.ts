import type { IconName } from "@/components/ui/icon";
import type { AccountPhase } from "../shell/signIn";

// How the account's phases are said, wherever they are said. It is data
// beside the components that draw it, so that an edit to one of them is a
// hot update and not a reload.

/** How each phase that withholds the TUI is said: in the TUI pane, in its
 * header, in the calendar, in the dialog and in settings. */
export const GATES: Partial<
  Record<AccountPhase, { icon: IconName; title: string; lead: string | null }>
> = {
  "signed-out": {
    icon: "lock",
    title: "desktop.account.signed_out",
    lead: "desktop.signin.signed_out_lead",
  },
  "no-profile": {
    icon: "user",
    title: "desktop.account.no_profile",
    lead: "desktop.account.no_profile_lead",
  },
  "services-down": {
    icon: "unplug",
    title: "desktop.account.services_down",
    lead: null,
  },
  unknown: { icon: "alert", title: "desktop.account.unknown", lead: null },
};

/** The string that names an account phase in a line: a header's note, a
 * badge. Null where the phase has nothing to say. */
export function accountLabel(phase: AccountPhase): string | null {
  if (phase === "checking") return "desktop.signin.checking";
  if (phase === "starting") return "desktop.signin.starting_services";
  if (phase === "signed-in") return "desktop.account.signed_in";
  if (phase === "in-tui") return "desktop.account.in_tui";
  return GATES[phase]?.title ?? null;
}
