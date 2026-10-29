import type { Meta, StoryObj } from "@storybook/react-vite";
import { userEvent, waitFor } from "storybook/test";
import {
  STORY_READER,
  useLedgerPort,
  useLedgerRead,
  useStoryStage,
} from "@/dev/LedgerStage";
import type { LedgerShape } from "@/dev/ledgerFixture";
import { usePagePause, WritePauseContext } from "../WritePause";
import {
  DOCUMENT_TABS,
  DocumentsSection,
  type DocumentTab,
} from "./DocumentsSection";
import { OffHostDialog } from "./OffHostDialog";

// The Documents section of the Ledger page over the scenario's ledger: the
// readings waiting for review and the draft invoice each opens, the evidence
// records, the attachments, the folder intake, what was sent off this
// computer, and the readers that make the readings. Shapes: `documents` holds
// readings to review, and `reader_missing` is the same on a computer whose
// local AI is not set up.

const noop = () => undefined;

type Args = { shape?: LedgerShape; locale: string };

function Documents({ shape, locale }: Args) {
  const port = useLedgerPort(shape);
  const read = useLedgerRead(port);
  const { stage, onStage } = useStoryStage();
  const pause = usePagePause({
    reader: STORY_READER,
    afterReread: read.reread,
  });
  return (
    <WritePauseContext.Provider value={pause}>
      <div className="flex h-full min-h-0 flex-col">
        <DocumentsSection
          port={port}
          reader={STORY_READER}
          locale={locale}
          shown
          rows={read.rows}
          stage={stage}
          onStage={onStage}
        />
      </div>
    </WritePauseContext.Provider>
  );
}

const meta: Meta<Args> = {
  title: "Ledger/Documents",
  render: (args, { globals }) => (
    <Documents {...args} locale={String(globals.locale ?? "en")} />
  ),
  args: { locale: "en", shape: "documents" },
  argTypes: { locale: { table: { disable: true } } },
  parameters: { fill: true, layout: "fullscreen" },
};
export default meta;
type Story = StoryObj<Args>;

const drawn = <T extends Element>(root: ParentNode, selector: string) =>
  waitFor(() => {
    const found = [...root.querySelectorAll<T>(selector)];
    if (found.length === 0) throw new Error(`${selector} is not drawn yet`);
    return found;
  });

const tab =
  (which: DocumentTab): NonNullable<Story["play"]> =>
  async ({ canvasElement }) => {
    const tabs = await drawn<HTMLElement>(canvasElement, "[role=tab]");
    await userEvent.click(tabs[DOCUMENT_TABS.indexOf(which)]!);
  };

/** Opens the reading at `at` in the review queue. */
const review =
  (at: number): NonNullable<Story["play"]> =>
  async ({ canvasElement }) => {
    const items = await drawn<HTMLElement>(
      canvasElement,
      ".ledger-review-item",
    );
    await userEvent.click(items[at] ?? items[0]!);
    await drawn(canvasElement, ".ledger-draft");
  };

export const ReviewQueue: Story = { name: "Readings to review" };
export const DraftToReview: Story = {
  name: "A draft invoice to review",
  play: review(0),
};
export const DraftWithFindings: Story = {
  name: "A draft with questions to answer",
  play: review(1),
};
export const DraftOther: Story = {
  name: "Another draft",
  play: review(2),
};
export const Records: Story = { play: tab("records") };
export const Attachments: Story = { play: tab("attachments") };
export const Folder: Story = { name: "Folder intake", play: tab("folder") };
export const Sent: Story = {
  name: "Sent off this computer",
  play: tab("sent"),
};
export const Readers: Story = { play: tab("readers") };
export const ReadersMissing: Story = {
  name: "Readers, local AI not set up",
  args: { shape: "reader_missing" },
  play: tab("readers"),
};
export const ReviewReaderMissing: Story = {
  name: "Readings to review, local AI not set up",
  args: { shape: "reader_missing" },
};
export const NothingToReview: Story = {
  name: "Nothing to review",
  args: { shape: "fixture" },
};
export const Empty: Story = { args: { shape: "empty" } };
export const Reading: Story = { args: { shape: "slow" } };
export const Unavailable: Story = { args: { shape: "unavailable" } };
export const Refused: Story = { args: { shape: "refused" } };

export const OffHost: StoryObj = {
  name: "Reading sends a document off this computer",
  render: () => (
    <OffHostDialog
      fileName="factura-estudio-lumen.pdf"
      onSend={noop}
      onClose={noop}
    />
  ),
};
