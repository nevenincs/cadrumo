import type { Meta, StoryObj } from "@storybook/react-vite";
import {
  STORY_READER,
  useLedgerPort,
  useLedgerRead,
  useStoryStage,
} from "@/dev/LedgerStage";
import type { LedgerShape } from "@/dev/ledgerFixture";
import { MatchQueue } from "./MatchQueue";

// The To match queue: the movements classified for the business that carry no
// invoice yet, beside the invoices they could belong to, read from the
// scenario's ledger.

const noop = () => undefined;

function Queue({ shape, locale }: { shape?: LedgerShape; locale: string }) {
  const port = useLedgerPort(shape);
  const read = useLedgerRead(port);
  const { stage, onStage } = useStoryStage();
  return (
    <div className="h-full w-96 border-r">
      <MatchQueue
        port={port}
        reader={STORY_READER}
        shown
        rows={read.rows}
        generation={read.generation}
        stage={stage}
        onStage={onStage}
        onChoose={noop}
        locale={locale}
      />
    </div>
  );
}

const meta: Meta<typeof Queue> = {
  title: "Ledger/Matching",
  component: Queue,
  render: (args, { globals }) => (
    <Queue {...args} locale={String(globals.locale ?? "en")} />
  ),
  args: { locale: "en" },
  argTypes: { locale: { table: { disable: true } } },
  parameters: { fill: true, layout: "fullscreen" },
};
export default meta;
type Story = StoryObj<typeof Queue>;

export const Queued: Story = { name: "To match" };
export const NothingToMatch: Story = {
  name: "Nothing to match",
  args: { shape: "empty" },
};
export const Unavailable: Story = { args: { shape: "unavailable" } };
export const Refused: Story = { args: { shape: "refused" } };
