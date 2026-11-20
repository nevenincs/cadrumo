import type { Meta, StoryObj } from "@storybook/react-vite";
import { useRef } from "react";
import type { LedgerShape } from "@/dev/ledgerFixture";
import { STORY_READER, useLedgerPort } from "@/dev/LedgerStage";
import { useLedgerPeriodsReader } from "../../shell/ledgerPeriods";
import { WithholdingPage } from "./WithholdingPage";

// The withholding payers took, over the scenario's ledger: the certificates
// of the ejercicio under the served amount columns with the statements that an
// income class had none, and a ledger that answers nothing, where each list
// says so with its code instead of being drawn as empty.

type Args = { locale: string; shape?: LedgerShape };

const noop = () => undefined;

function Page({ locale, shape }: Args) {
  const port = useLedgerPort(shape, true, locale);
  // The year that holds today is the ledger's to serve.
  useLedgerPeriodsReader(port, STORY_READER, locale);
  const page = useRef<HTMLElement | null>(null);
  return (
    <div className="flex h-full min-h-0 flex-col">
      <WithholdingPage
        port={port}
        reader={STORY_READER}
        locale={locale}
        page={page}
        pane={{ controls: [], onToggleMaximize: noop }}
        onOpenLedger={noop}
      />
    </div>
  );
}

const meta: Meta<Args> = {
  title: "Withholding/Page",
  render: (args, { globals }) => (
    <Page {...args} locale={String(globals.locale ?? "en")} />
  ),
  args: { locale: "en" },
  argTypes: {
    locale: { table: { disable: true } },
    shape: { table: { disable: true } },
  },
  parameters: { fill: true, layout: "fullscreen" },
};
export default meta;
type Story = StoryObj<Args>;

export const Certificates: Story = {};
export const LedgerUnavailable: Story = { args: { shape: "unavailable" } };
