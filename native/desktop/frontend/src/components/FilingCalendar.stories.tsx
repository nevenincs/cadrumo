import type { Meta, StoryObj } from "@storybook/react-vite";
import { accountFixture, refused, SIGNED_OUT } from "@/dev/fixtures/account";
import { EMPTY_CALENDAR, FIXTURE_CALENDAR } from "@/dev/fixtures/calendar";
import type { CalendarState } from "../shell/calendar";
import { useStrings } from "../shell/strings";
import { FilingCalendarView } from "./FilingCalendar";
import { PaneHeader } from "./PaneHeader";
import { SignedOut } from "./SignIn";

// The filing calendar page in every state, over a fixed calendar in the
// product's own shape. The toolbar's language also sets how dates are written.
const noop = () => undefined;

type Args = {
  state: CalendarState;
  refreshing?: boolean;
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

function Page({ state, refreshing, phase }: Args) {
  const t = useStrings();
  return (
    <div className="flex h-dvh flex-col bg-background">
      <PaneHeader
        title={t("desktop.calendar.title")}
        controls={[]}
        onToggleMaximize={noop}
      />
      <FilingCalendarView
        state={state}
        locale={document.documentElement.lang || "en"}
        refreshing={refreshing}
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

export const Obligations: Story = {};

export const Refreshing: Story = { args: { refreshing: true } };

export const NothingDue: Story = {
  name: "Nothing in the range",
  args: { state: { kind: "ready", calendar: EMPTY_CALENDAR } },
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
