import type { Meta, StoryObj } from "@storybook/react-vite";
import { accountFixture, refused, SIGNED_OUT } from "@/dev/fixtures/account";
import {
  AHEAD_CALENDAR,
  BEHIND_CALENDAR,
  EMPTY_CALENDAR,
  FIXTURE_CALENDAR,
  FIXTURE_TODAY,
  STRADDLING_CALENDAR,
} from "@/dev/fixtures/calendar";
import type { CalendarState } from "../shell/calendar";
import { useStrings } from "../shell/strings";
import { FilingCalendarView } from "./FilingCalendar";
import { PaneHeader } from "./PaneHeader";
import { SignedOut } from "./SignIn";

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

function Page({ state, refreshing, phase, pane, view, today }: Args) {
  const t = useStrings();
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
        locale={document.documentElement.lang || "en"}
        refreshing={refreshing}
        defaultView={view}
        // The fixture's day, so the catalogue reads the same on any day.
        today={today ?? FIXTURE_TODAY}
        withheld={
          phase && (
            <SignedOut
              account={ACCOUNTS[phase]}
              lead={t("desktop.calendar.signed_out")}
              quiet
              onSignIn={noop}
              onOpenTui={noop}
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
  render: (args: Args) => <Page {...args} />,
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

export const Refreshing: Story = { args: { refreshing: true } };

export const NothingDue: Story = {
  name: "Nothing in the range",
  args: { state: { kind: "ready", calendar: EMPTY_CALENDAR } },
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

// A calendar the product worked out on another day than this one: its mark
// says the day, and does not call it today.
export const AnotherDay: Story = {
  name: "Evaluated on another day",
  args: { pane: true, view: "list", today: "2026-10-07" },
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
