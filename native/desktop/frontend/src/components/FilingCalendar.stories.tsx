import type { Meta, StoryObj } from "@storybook/react-vite";
import { useRef } from "react";
import { accountFixture, refused, SIGNED_OUT } from "@/dev/fixtures/account";
import {
  AHEAD_CALENDAR,
  BEHIND_CALENDAR,
  CLOSE_UNKNOWN_CALENDAR,
  EMPTY_CALENDAR,
  FIXTURE_CALENDAR,
  FIXTURE_TODAY,
  STRADDLING_CALENDAR,
  UNKNOWN_YEAR_CALENDAR,
  UNKNOWN_YEAR_EMPTY_CALENDAR,
} from "@/dev/fixtures/calendar";
import { BUSY_CALENDAR, BUSY_TODAY } from "@/dev/fixtures/calendarBusy";
import {
  NONE_SUPPRESSED_CALENDAR,
  SUPPRESSED_CALENDAR,
  SUPPRESSED_ONLY_CALENDAR,
} from "@/dev/fixtures/calendarSuppressed";
import profiles from "@fixtures/desktop-profile/userProfile.json" with { type: "json" };
import type { CalendarState } from "../shell/calendar";
import type { UserProfile } from "../shell/userProfile";
import { useStrings } from "../shell/strings";
import { FilingCalendarView, type CalendarMemory } from "./FilingCalendar";
import { PaneHeader } from "./PaneHeader";
import { SignedOut } from "./SignIn";
import { fixtureDay, fixtureMonth } from "@/dev/fixtureDates";

// The filing calendar page in every state, over a fixed calendar in the
// product's own shape. The toolbar's language also sets how dates are
// written and the day a week begins on. A page as wide as the window shows
// the months and the list together; one as wide as a pane shows one of them.
const noop = () => undefined;

type Args = {
  state: CalendarState;
  refreshing?: boolean;
  /** As wide as a pane beside another, where one face is shown at a time. */
  pane?: boolean;
  /** The face such a pane shows first. */
  view?: "months" | "list";
  /** The local day; the fixture's own unless a story is about another. */
  today?: string;
  /** What the reader had made of the page before it was shown: a choice,
   * or crowded months asked for whole. */
  left?: CalendarMemory;
  /** Why the calendar is withheld, as a phase of the account. */
  phase?: "signed-out" | "checking" | "locked" | "services-down";
};

// The account as each phase has it, by the shell's own rule.
const ACCOUNTS = {
  "signed-out": accountFixture(),
  checking: accountFixture({ status: null }),
  locked: accountFixture({
    status: { ...SIGNED_OUT, refusal: refused("PROFILE_LOCKED") },
  }),
  "services-down": accountFixture({
    status: { ...SIGNED_OUT, state: "unknown", runtimeAvailable: false },
  }),
};

function Page({
  state,
  refreshing,
  phase,
  pane,
  view,
  today,
  left,
  locale,
}: Args & { locale: string }) {
  const t = useStrings();
  const memory = useRef<CalendarMemory>(left ?? {});
  return (
    <div
      className={
        pane
          ? "flex h-dvh w-full max-w-2xl flex-col border-r bg-background"
          : "flex h-dvh flex-col bg-background"
      }
    >
      <PaneHeader
        title={t("desktop.calendar.title")}
        controls={[]}
        onToggleMaximize={noop}
      />
      <FilingCalendarView
        state={state}
        profile={
          (profiles[locale as keyof typeof profiles] ??
            profiles.en) as UserProfile
        }
        onNavigate={noop}
        locale={locale}
        refreshing={refreshing}
        defaultView={view}
        memory={memory}
        // The fixture's day, so the catalogue reads the same on any day.
        today={today ?? FIXTURE_TODAY}
        withheld={
          phase && (
            <SignedOut
              account={ACCOUNTS[phase]}
              lead={t("desktop.calendar.signed_out")}
              quiet
              onSignIn={noop}
            />
          )
        }
        onRefresh={noop}
        onOpen={noop}
      />
    </div>
  );
}

const meta = {
  title: "Shell/Filing calendar",
  parameters: { fill: true },
  args: { state: { kind: "ready", calendar: FIXTURE_CALENDAR } },
  // The catalogue's language is the calendar's: its dates, its week's first
  // day and its words for distance, as well as its strings.
  render: (args: Args, context) => (
    <Page {...args} locale={String(context.globals.locale ?? "en")} />
  ),
} satisfies Meta<Args>;
export default meta;
type Story = StoryObj<typeof meta>;

export const Obligations: Story = { name: "Months and list together" };

export const PaneMonths: Story = {
  name: "In a pane: the months",
  args: { pane: true },
};

export const PaneList: Story = {
  name: "In a pane: the list",
  args: { pane: true, view: "list" },
};

// Windows whose close the product could not work out: no day is drawn, and
// the row says only the earliest it can close.
export const CloseUnknown: Story = {
  name: "Close unknown: months and list",
  args: { state: { kind: "ready", calendar: CLOSE_UNKNOWN_CALENDAR } },
};

export const CloseUnknownPane: Story = {
  name: "Close unknown: in a pane, the list",
  args: {
    state: { kind: "ready", calendar: CLOSE_UNKNOWN_CALENDAR },
    pane: true,
    view: "list",
  },
};

export const Refreshing: Story = { args: { refreshing: true } };

export const NothingDue: Story = {
  name: "Nothing in the range",
  args: { state: { kind: "ready", calendar: EMPTY_CALENDAR } },
};

// A year the registry has no deadline windows for is unknown, said in the
// served words: an empty list there is not "nothing due".
export const UnknownYearEmpty: Story = {
  name: "Unknown year: no rows, said as unknown",
  args: { state: { kind: "ready", calendar: UNKNOWN_YEAR_EMPTY_CALENDAR } },
};

export const UnknownYearBesideRows: Story = {
  name: "Unknown year: beside known rows",
  args: { state: { kind: "ready", calendar: UNKNOWN_YEAR_CALENDAR } },
};

// Obligations the read held off the schedule are set apart from the owed
// ones, each in the served words of its verdict. The section is drawn only
// where the read served any: the story above it has none, and so has this one
// that was asked and served an empty list.
export const SuppressedBesideOwed: Story = {
  name: "Held off the schedule: beside what is owed",
  args: { state: { kind: "ready", calendar: SUPPRESSED_CALENDAR } },
};

export const SuppressedInPane: Story = {
  name: "Held off the schedule: in a pane",
  args: {
    state: { kind: "ready", calendar: SUPPRESSED_CALENDAR },
    pane: true,
    view: "list",
  },
};

export const SuppressedNothingOwed: Story = {
  name: "Held off the schedule: nothing owed in the range",
  args: { state: { kind: "ready", calendar: SUPPRESSED_ONLY_CALENDAR } },
};

export const SuppressedNone: Story = {
  name: "Held off the schedule: asked, none served",
  args: { state: { kind: "ready", calendar: NONE_SUPPRESSED_CALENDAR } },
};

// Where the mark for today stands in each shape of range.
export const TodayOpens: Story = {
  name: "Today: everything is ahead",
  args: { state: { kind: "ready", calendar: AHEAD_CALENDAR } },
};

export const TodayWithinMonth: Story = {
  name: "Today: inside a month",
  args: { state: { kind: "ready", calendar: STRADDLING_CALENDAR } },
};

export const TodayCloses: Story = {
  name: "Today: everything is behind",
  args: { state: { kind: "ready", calendar: BEHIND_CALENDAR } },
};

// The turn of a year: nine windows open over the same weeks, one moved
// past a weekend into the next month, one late, one closing after the range.
export const Busy: Story = {
  name: "Many windows at once",
  args: {
    state: { kind: "ready", calendar: BUSY_CALENDAR },
    today: BUSY_TODAY,
  },
};

export const BusyPane: Story = {
  name: "Many windows at once, in a pane",
  args: {
    state: { kind: "ready", calendar: BUSY_CALENDAR },
    today: BUSY_TODAY,
    pane: true,
  },
};

// What is chosen is drawn in place of what its week would keep last: the
// month is no taller for it, and the list beside it marks the same one.
export const BusyChosen: Story = {
  name: "Many windows at once: one that was counted, chosen",
  args: {
    state: { kind: "ready", calendar: BUSY_CALENDAR },
    today: BUSY_TODAY,
    left: { selected: "390:2026" },
  },
};

export const BusyWhole: Story = {
  name: "Many windows at once: a month drawn whole",
  args: {
    state: { kind: "ready", calendar: BUSY_CALENDAR },
    today: BUSY_TODAY,
    pane: true,
    left: { asked: new Set([fixtureMonth(1, 1)]) },
  },
};

// A calendar the product worked out on another day than this one: its mark
// says the day, and does not call it today.
export const AnotherDay: Story = {
  name: "Evaluated on another day",
  args: { pane: true, view: "list", today: fixtureDay(10, 7) },
};

export const Loading: Story = { args: { state: { kind: "loading" } } };

export const Withheld: Story = {
  name: "Withheld: signed out",
  args: { state: { kind: "withheld" }, phase: "signed-out" },
};

// Withheld for a reason no password answers: the page says what the rest of
// the window says of the account, and offers nothing it cannot do.
export const Checking: Story = {
  name: "Withheld: checking the sign-in",
  args: { state: { kind: "withheld" }, phase: "checking" },
};

export const Locked: Story = {
  name: "Withheld: no password can answer",
  args: { state: { kind: "withheld" }, phase: "locked" },
};

export const ServicesDown: Story = {
  name: "Withheld: no services",
  args: { state: { kind: "withheld" }, phase: "services-down" },
};

export const FailedRefreshing: Story = {
  name: "Failed, reading again",
  args: { state: { kind: "failed", code: "timed_out" }, refreshing: true },
};

export const Failed: Story = {
  args: { state: { kind: "failed", code: "timed_out" } },
};
