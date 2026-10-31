import type { Meta, StoryObj } from "@storybook/react-vite";
import type { ReactNode } from "react";
import { userEvent, waitFor } from "storybook/test";
import {
  STORY_PERIOD,
  STORY_READER,
  storyMovementIds,
  useLedgerPort,
  useLedgerRead,
  useStoryStage,
} from "@/dev/LedgerStage";
import type { LedgerShape } from "@/dev/ledgerFixture";
import type { LedgerPeriod } from "../../../shell/ledgerGrammar";
import type { Readiness } from "../../../shell/ledgerWindow";
import { usePagePause, WritePauseContext } from "../WritePause";
import { AccountsPane } from "./AccountsPane";
import { CapitalGoodsPane } from "./CapitalGoodsPane";
import { CounterpartiesPane } from "./CounterpartiesPane";
import { DiagnosticsPane } from "./DiagnosticsPane";
import { HealthSection } from "./HealthSection";
import { ProrrataPane } from "./ProrrataPane";
import { RatiosPane } from "./RatiosPane";
import { RegistersSection } from "./RegistersSection";
import { RuleDialog, type RuleDialogTarget } from "./RuleDialog";
import { RulesSection, type RulesArea } from "./RulesSection";
import type { SetupProps } from "./setupProps";

// The Setup sections of the Ledger page over the scenario's ledger: the
// rules and what hangs on them, the registers, and the ledger's health, each
// given what the page gives it. The panes of a section are shown on their own
// as well as inside it.

const noop = () => undefined;

type Args = {
  shape?: LedgerShape;
  period?: LedgerPeriod;
  locale: string;
};

/** The page's own reads, held as the page holds them, for a Setup part. */
function Setup({
  shape,
  period = STORY_PERIOD,
  locale,
  children,
}: Args & {
  children: (
    props: SetupProps,
    read: ReturnType<typeof useLedgerRead>,
  ) => ReactNode;
}) {
  const port = useLedgerPort(shape);
  const read = useLedgerRead(port, period);
  const { stage, onStage } = useStoryStage();
  const pause = usePagePause({
    reader: STORY_READER,
    afterReread: read.reread,
  });
  return (
    <WritePauseContext.Provider value={pause}>
      <div className="flex h-full min-h-0 flex-col">
        {children(
          {
            port,
            reader: STORY_READER,
            locale,
            rows: read.rows,
            stage: stage.content,
            onStage,
            years: read.years,
            fallbackYear: STORY_PERIOD.year,
            period,
          },
          read,
        )}
      </div>
    </WritePauseContext.Provider>
  );
}

const meta: Meta<Args> = {
  title: "Ledger/Setup",
  render: (args, { globals }) => (
    <Setup {...args} locale={String(globals.locale ?? "en")}>
      {(props) => (
        <RulesSection {...props} onOpenRule={noop} rulesVersion={0} />
      )}
    </Setup>
  ),
  args: { locale: "en" },
  argTypes: { locale: { table: { disable: true } } },
  parameters: { fill: true, layout: "fullscreen" },
};
export default meta;
type Story = StoryObj<Args>;

const pane = (
  draw: (
    props: SetupProps,
    read: ReturnType<typeof useLedgerRead>,
  ) => ReactNode,
  extra: Partial<Story> = {},
): Story => ({
  ...extra,
  render: (args, { globals }) => (
    <Setup {...args} locale={String(globals.locale ?? "en")}>
      {(props, read) => (
        <div className="min-h-0 flex-1 overflow-y-auto">
          {draw(props, read)}
        </div>
      )}
    </Setup>
  ),
});

const rules = (area: RulesArea, extra: Partial<Story> = {}): Story =>
  pane(
    (props) => (
      <RulesSection
        {...props}
        onOpenRule={noop}
        rulesVersion={0}
        initialArea={area}
      />
    ),
    extra,
  );

export const Rules: Story = rules("rules");
export const RulesEmpty: Story = rules("rules", {
  name: "Rules, none yet",
  args: { shape: "empty" },
});
export const RulesUnavailable: Story = rules("rules", {
  name: "Rules, ledger not answering",
  args: { shape: "unavailable" },
});
export const RulesRatios: Story = rules("ratios", {
  name: "Rules, business-use ratios",
});
export const RulesCounterparties: Story = rules("counterparties", {
  name: "Rules, counterparties",
});
export const RulesDiagnostics: Story = rules("diagnostics", {
  name: "Rules, model diagnostics",
});

export const Registers: Story = pane((props) => (
  <RegistersSection {...props} />
));
export const RegistersEmpty: Story = pane(
  (props) => <RegistersSection {...props} />,
  { name: "Registers, none yet", args: { shape: "empty" } },
);

export const Accounts: Story = pane((props) => <AccountsPane {...props} />);
export const AccountForm: Story = pane((props) => <AccountsPane {...props} />, {
  name: "Accounts, adding one",
  play: async ({ canvasElement }) => {
    const add = await waitFor(() => {
      const found = canvasElement.querySelector<HTMLElement>(
        "button.ledger-account-add",
      );
      if (!found) throw new Error("the add button is not drawn yet");
      return found;
    });
    await userEvent.click(add);
  },
});

const press = (selector: string) => async (canvasElement: HTMLElement) => {
  const found = await waitFor(() => {
    const button = canvasElement.querySelector<HTMLElement>(selector);
    if (!button) throw new Error(`${selector} is not drawn yet`);
    return button;
  });
  await userEvent.click(found);
};

export const Prorrata: Story = pane((props) => <ProrrataPane {...props} />);
export const ProrrataElection: Story = pane(
  (props) => <ProrrataPane {...props} />,
  {
    name: "Prorrata, a general election",
    play: ({ canvasElement }) =>
      press("button.ledger-prorrata-elect_general")(canvasElement),
  },
);
export const ProrrataSettlement: Story = pane(
  (props) => <ProrrataPane {...props} />,
  {
    name: "Prorrata, settling a sector",
    play: ({ canvasElement }) =>
      press("button.ledger-prorrata-settle_sector")(canvasElement),
  },
);
export const CapitalGoods: Story = pane((props) => (
  <CapitalGoodsPane {...props} />
));
export const CapitalGoodsForm: Story = pane(
  (props) => <CapitalGoodsPane {...props} />,
  {
    name: "Capital goods, declaring one",
    play: ({ canvasElement }) =>
      press("button.ledger-capital-add")(canvasElement),
  },
);
export const Ratios: Story = pane((props) => <RatiosPane {...props} />);
export const Counterparties: Story = pane((props) => (
  <CounterpartiesPane {...props} />
));
export const Diagnostics: Story = pane((props) => (
  <DiagnosticsPane {...props} />
));

export const Health: Story = pane((props, read) => (
  <HealthWith {...props} readiness={read.readiness} />
));

function HealthWith(props: SetupProps & { readiness: Readiness }) {
  return (
    <HealthSection
      {...props}
      onShowReason={noop}
      onShowReadiness={noop}
      onShowInvoices={noop}
      onReset={noop}
    />
  );
}

type RuleArgs = { target: "new" | "rule" | "seed" };

function Rule({ target, locale }: RuleArgs & { locale: string }) {
  const port = useLedgerPort();
  const read = useLedgerRead(port);
  const { onStage } = useStoryStage();
  const chosen: RuleDialogTarget | null =
    target === "new"
      ? { kind: "new" }
      : target === "seed"
        ? {
            kind: "seed",
            seed: {
              ids: storyMovementIds(
                (m) => m.transaction.counterparty === "Papelería Trazo",
                3,
              ),
            },
          }
        : null;
  void locale;
  return read.rows && chosen ? (
    <RuleDialog
      port={port}
      reader={STORY_READER}
      target={chosen}
      rows={read.rows}
      onStage={onStage}
      onSaved={noop}
      onClose={noop}
    />
  ) : null;
}

export const RuleNew: StoryObj<RuleArgs> = {
  name: "Rule dialog, a new rule",
  args: { target: "new" },
  render: (args, { globals }) => (
    <Rule {...args} locale={String(globals.locale ?? "en")} />
  ),
};
export const RuleFromMovements: StoryObj<RuleArgs> = {
  name: "Rule dialog, from movements",
  args: { target: "seed" },
  render: (args, { globals }) => (
    <Rule {...args} locale={String(globals.locale ?? "en")} />
  ),
};
