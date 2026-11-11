// What an entry overview shows, apart from how it is drawn: a heading, the
// amount, the chips that say the entry's state, and groups of facts. Each
// fact keeps a stored value apart from one that is not set and from one that
// is not known, so the panel never draws an unread fact as an empty one.

import type { IconName } from "@/components/ui/icon";

/** The kinds of ledger entry an overview summarises. */
export type OverviewKind = "movement" | "invoice" | "document";

/** One fact's value. `absent` is a value the entry does not carry; `unknown`
 * is one that was not read, could not be, or is still being read. */
export type OverviewValue =
  | {
      kind: "value";
      text: string;
      /** A figure or a date, set in tabular digits. */
      figure?: boolean;
      /** A second line under the value, such as who decided it and when. */
      detail?: string;
    }
  | { kind: "absent"; text: string }
  | { kind: "unknown"; text: string };

export type OverviewFact = {
  /** Stable for tests and the scenario: the stored field it shows. */
  id: string;
  label: string;
  value: OverviewValue;
};

/** A line a group says rather than lists, such as a readiness finding. */
export type OverviewNote = {
  text: string;
  tone: "neutral" | "warning";
};

export type OverviewGroup = {
  id: string;
  heading: string;
  facts: OverviewFact[];
  notes?: OverviewNote[];
};

export type OverviewChip = {
  /** Stable for tests and the scenario. */
  id: string;
  text: string;
  tone: "neutral" | "success" | "warning" | "danger";
  icon?: IconName;
};

export type OverviewModel = {
  kind: OverviewKind;
  /** What the entry is, said above its title: "Movement". */
  kindLabel: string;
  title: string;
  /** The line under the title: the other party and the day. */
  subtitle: string;
  /** The entry's amount, what kind of amount it is, and its value in euros
   * where it is in another currency. */
  amount: {
    text: string;
    detail: string | null;
    converted?: { label: string; value: OverviewValue };
  } | null;
  chips: OverviewChip[];
  /** Said above the groups: what the overview does not show, such as
   * changes not saved yet. */
  notice: string | null;
  groups: OverviewGroup[];
};

export const stored = (
  text: string,
  options: { figure?: boolean; detail?: string | null } = {},
): OverviewValue => ({
  kind: "value",
  text,
  ...(options.figure ? { figure: true } : {}),
  ...(options.detail ? { detail: options.detail } : {}),
});
export const absent = (text: string): OverviewValue => ({
  kind: "absent",
  text,
});
export const unknown = (text: string): OverviewValue => ({
  kind: "unknown",
  text,
});
