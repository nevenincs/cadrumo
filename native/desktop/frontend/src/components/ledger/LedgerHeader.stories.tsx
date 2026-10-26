import type { Meta, StoryObj } from "@storybook/react-vite";
import { useState } from "react";
import { STORY_PERIOD, useStoryControls } from "@/dev/LedgerStage";
import { LEDGER_SECTIONS, type LedgerSection } from "../../shell/layout";
import type { LedgerPeriod } from "../../shell/ledgerGrammar";
import { useStrings } from "../../shell/strings";
import { LedgerHeader, type LedgerHeaderAction } from "./LedgerHeader";
import { PeriodSelector } from "./PeriodSelector";

// The Ledger page's header: the pane's title and controls, the sections, the
// period and the actions, as the page lays them out.

const noop = () => undefined;

type Args = {
  section?: LedgerSection;
  count?: number;
  held?: boolean;
  period?: LedgerPeriod | null;
  locale: string;
};

function Header({ section = "movements", count, held, period, locale }: Args) {
  const t = useStrings();
  const [shown, setShown] = useState(section);
  const [chosen, setChosen] = useState<LedgerPeriod | null>(
    period === undefined ? STORY_PERIOD : period,
  );
  const run: LedgerHeaderAction = held
    ? { reason: t("desktop.ledger.unavailable") }
    : { run: noop };
  const controls = useStoryControls();
  return (
    <>
      <LedgerHeader
        title={t("desktop.ledger.title")}
        controls={controls}
        onToggleMaximize={noop}
        section={shown}
        onSection={setShown}
        counts={
          count
            ? {
                movements: {
                  count,
                  label: t("desktop.ledger.count.to_classify", { count }),
                },
              }
            : {}
        }
        panel="ledger-story-panel"
        period={
          <PeriodSelector
            value={chosen}
            onChange={setChosen}
            label={t("desktop.ledger.period.label")}
            years={[2024, 2025, 2026]}
            locale={locale}
            fallbackYear={STORY_PERIOD.year}
          />
        }
        importAction={run}
        exportAction={run}
        addAction={run}
      />
      <div id="ledger-story-panel" />
    </>
  );
}

const meta: Meta<typeof Header> = {
  title: "Ledger/Header",
  component: Header,
  render: (args, { globals }) => (
    <Header {...args} locale={String(globals.locale ?? "en")} />
  ),
  args: { locale: "en" },
  argTypes: {
    section: { control: "select", options: LEDGER_SECTIONS },
    locale: { table: { disable: true } },
  },
  parameters: { surface: "chrome", fill: true },
};
export default meta;
type Story = StoryObj<typeof Header>;

export const Movements: Story = {};
export const ToClassifyCount: Story = {
  name: "Movements to classify",
  args: { count: 8 },
};
export const Invoices: Story = { args: { section: "invoices" } };
export const SetupSection: Story = {
  name: "A setup section",
  args: { section: "rules" },
};
export const EveryPeriod: Story = {
  name: "Every period",
  args: { period: null },
};
export const ActionsHeld: Story = {
  name: "Actions that cannot run",
  args: { held: true },
};
