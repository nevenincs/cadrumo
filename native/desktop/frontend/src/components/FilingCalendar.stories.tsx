import type { Meta, StoryObj } from "@storybook/react-vite";
import { EMPTY_CALENDAR, FIXTURE_CALENDAR } from "@/dev/fixtures/calendar";
import { useStrings } from "../shell/strings";
import { FilingCalendarView, type CalendarState } from "./FilingCalendar";
import { PaneHeader } from "./PaneHeader";

// The filing calendar page in every state, over a fixed calendar in the
// product's own shape. The toolbar's language also sets how dates are written.
const noop = () => undefined;

type Args = { state: CalendarState; refreshing?: boolean };

function Page({ state, refreshing }: Args) {
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
        onRefresh={noop}
        onSignIn={noop}
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

export const SignedOut: Story = { args: { state: { kind: "signed-out" } } };

export const Failed: Story = {
  args: { state: { kind: "failed", code: "timed_out" } },
};
