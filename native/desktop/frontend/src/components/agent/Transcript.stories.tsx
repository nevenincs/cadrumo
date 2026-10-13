import type { Meta, StoryObj } from "@storybook/react-vite";
import type { ComponentProps } from "react";
import { cn } from "@/components/ui/cn";
import { AgentHeader } from "./AgentHeader";
import {
  APPEARANCE_NOTE,
  MODELS,
  NOOP,
  PROVIDERS,
  SELECTION,
} from "./Composer.stories";
import { Composer } from "./Composer";
import { Transcript } from "./Transcript";
import type { SentFile, TranscriptItem } from "./types";

// Appearance only: fixed turns in fixed states. No host and no model:
// nothing here is sent, answered or retried, no tool runs, and no reply
// grows. A story that shows following the newest turn shows only where the
// list starts, scrolled to the bottom.

const TRANSCRIPT_NOTE = `${APPEARANCE_NOTE} Following the newest turn is shown only as where the list starts: at the bottom.`;

export const SENT_FILES: SentFile[] = [
  {
    id: "f1",
    name: "factura-2026-031.pdf",
    extension: "pdf",
    kind: "document",
  },
  { id: "f2", name: "ticket-gasolinera.jpg", extension: "jpg", kind: "image" },
  {
    id: "f3",
    name: "extracto-tercer-trimestre.xlsx",
    extension: "xlsx",
    kind: "sheet",
  },
];

const MANY_FILES: SentFile[] = [
  ...SENT_FILES,
  {
    id: "f4",
    name: "facturas-septiembre.zip",
    extension: "zip",
    kind: "archive",
  },
  { id: "f5", name: "notas.txt", extension: "txt", kind: "text" },
  { id: "f6", name: "factura-luz.png", extension: "png", kind: "image" },
  {
    id: "f7",
    name: "factura-agua-tercer-trimestre-2026.pdf",
    extension: "pdf",
    kind: "document",
  },
  { id: "f8", name: "alquiler-local.pdf", extension: "pdf", kind: "document" },
];

export const EXCHANGE: TranscriptItem[] = [
  {
    kind: "person",
    id: "m1",
    text: "Classify these for me.\nThe fuel receipt is for the van.",
    files: SENT_FILES,
    sentAtLabel: "10:42",
  },
  {
    kind: "tool",
    id: "t1",
    label: "Read the attached documents",
    state: "completed",
  },
  {
    kind: "agent",
    id: "m2",
    state: "complete",
    text: "factura-2026-031.pdf is a sale to a customer in Valencia: 1.200,00 € plus 21 % IVA.\n\nticket-gasolinera.jpg is fuel for the van, 64,30 € with IVA included. Only the share the van is used for the business can be deducted.\n\nThe bank export has 48 movements in the third quarter. Three of them have no document yet.",
  },
];

const QUESTIONS = [
  "When is the 303 for the third quarter due?",
  "Which invoices from September are still missing?",
  "Is the van's insurance deductible?",
  "What did I declare in the second quarter?",
  "Can I still correct the 130 from July?",
  "How much IVA do I owe so far this quarter?",
];

const ANSWERS = [
  "The 303 for the third quarter is due on 20 October. Paid by direct debit, it is due on 15 October.",
  "Two invoices from September have no document: the electricity bill and the rent for the premises.",
  "Insurance for a vehicle used only for the business can be deducted. For mixed use, the deduction follows the share of business use you can show.",
  "In the second quarter you declared 3.480,00 € of IVA charged and 1.112,40 € of IVA paid.",
  "Yes. A correction is filed as a complementary 130 for the same period.",
  "From the records so far: 2.016,00 € charged and 744,90 € paid, which leaves 1.271,10 €.",
];

const LONG: TranscriptItem[] = QUESTIONS.flatMap((question, index) => [
  {
    kind: "person",
    id: `q${index}`,
    text: question,
    sentAtLabel: `10:${String(10 + index * 4)}`,
  },
  {
    kind: "tool",
    id: `r${index}`,
    label: index % 2 === 0 ? "Read ledger entries" : "Read filed declarations",
    state: "completed",
  },
  {
    kind: "agent",
    id: `a${index}`,
    state: "complete",
    text: ANSWERS[index] ?? "",
  },
]);

const WORKING: TranscriptItem[] = [
  {
    kind: "person",
    id: "w1",
    text: "What is left to file for the third quarter, and when is the 303 due?",
    sentAtLabel: "11:05",
  },
  {
    kind: "tool",
    id: "w2",
    label: "Read the filing calendar",
    state: "completed",
  },
  {
    kind: "agent",
    id: "w3",
    state: "working",
    text: "The 303 for the third quarter is due on 20 October.",
  },
];

const TOOLS: TranscriptItem[] = [
  {
    kind: "person",
    id: "x1",
    text: "Check my ledger against what I filed for the second quarter.",
  },
  {
    kind: "tool",
    id: "x2",
    label: "ledger_list",
    state: "completed",
    detail: "Reads",
  },
  {
    kind: "tool",
    id: "x3",
    label: "aeat_filed_declarations",
    state: "failed",
    detail: "Fetches",
  },
  {
    kind: "tool",
    id: "x4",
    label: "ledger_compare",
    state: "in_progress",
    detail: "Searches",
  },
  { kind: "agent", id: "x5", state: "working", text: "" },
];

const FAILED: TranscriptItem[] = [
  {
    kind: "person",
    id: "e1",
    text: "Summarise the invoices from September.",
  },
  {
    kind: "agent",
    id: "e2",
    state: "failed",
    text: "There are eleven invoices from September. Eight of them",
    failureReason: "The connection to Anthropic was lost.",
  },
];

const STOPPED: TranscriptItem[] = [
  {
    kind: "person",
    id: "s1",
    text: "List every expense from this year.",
  },
  {
    kind: "agent",
    id: "s2",
    state: "stopped",
    text: "From January: rent for the premises, 650,00 €; electricity, 92,14 €;",
  },
];

const WITH_MANY_FILES: TranscriptItem[] = [
  {
    kind: "person",
    id: "n1",
    text: "These are all the documents for the third quarter.",
    files: MANY_FILES,
    sentAtLabel: "09:30",
  },
];

type Width = "column" | "wide";
type Args = Omit<ComponentProps<typeof Transcript>, "locale"> & {
  width: Width;
};

const WIDTHS: Record<Width, string> = {
  column: "w-(--agent-w)",
  wide: "w-lg",
};

const meta = {
  title: "Shell/Agent/Transcript",
  excludeStories: /^[A-Z][A-Z_]*$/,
  parameters: {
    fill: true,
    docs: { description: { component: TRANSCRIPT_NOTE } },
  },
  argTypes: {
    width: {
      control: "inline-radio",
      options: ["column", "wide"],
      description: "The column's opening width, or 32rem.",
    },
  },
  args: { items: EXCHANGE, onRetry: NOOP, followNewest: true, width: "column" },
  render: ({ width, ...args }: Args, { globals }) => (
    <div
      className={cn(
        "flex h-dvh flex-col border-r bg-background",
        WIDTHS[width],
      )}
    >
      <p className="shrink-0 px-3 py-2 text-xs text-muted-foreground">
        {TRANSCRIPT_NOTE}
      </p>
      <Transcript {...args} locale={String(globals.locale)} />
    </div>
  ),
} satisfies Meta<Args>;
export default meta;
type Story = StoryObj<typeof meta>;

export const Empty: Story = { args: { items: [] } };

export const OneExchangeWithFiles: Story = {};

export const ManyFilesFolded: Story = {
  name: "Many files: six shown, the rest counted",
  args: { items: WITH_MANY_FILES },
};

export const LongConversation: Story = {
  name: "Long conversation: starts at the newest",
  args: { items: LONG },
};

export const LongConversationWide: Story = {
  name: "Long conversation at 32rem",
  args: { items: LONG, width: "wide" },
};

export const AgentWorking: Story = { args: { items: WORKING } };

export const AgentWaitingOnPerson: Story = {
  args: {
    items: WORKING.map((item) =>
      item.kind === "agent" && item.state === "working"
        ? { ...item, waitingOnPerson: true }
        : item,
    ),
  },
};

export const ToolActivity: Story = {
  name: "Tool activity: completed, failed, in progress",
  args: { items: TOOLS },
};

export const FailedRetryAvailable: Story = {
  name: "Failed: Retry available",
  args: { items: FAILED },
};

export const FailedRetryUnavailable: Story = {
  name: "Failed: Retry unavailable",
  args: { items: FAILED, onRetry: undefined },
};

export const Stopped: Story = { args: { items: STOPPED } };

export const InColumn: Story = {
  name: "In the column, with header and composer",
  args: { items: WORKING },
  render: ({ width, ...args }: Args, { globals }) => {
    const locale = String(globals.locale);
    return (
      <div className="grid h-dvh grid-cols-[auto_minmax(0,1fr)] bg-chrome">
        <aside
          className={cn(
            "flex h-dvh flex-col border-r bg-background",
            WIDTHS[width],
          )}
        >
          <AgentHeader
            title="IVA del tercer trimestre"
            subtitle="Opus 5.5 · High"
          />
          <Transcript {...args} locale={locale} />
          <div className="shrink-0 p-3 pt-0">
            <Composer
              locale={locale}
              attachments={[]}
              providers={PROVIDERS}
              models={MODELS}
              selection={SELECTION}
              running
            />
          </div>
        </aside>
        <p className="max-w-80 p-4 text-sm text-muted-foreground">
          {TRANSCRIPT_NOTE}
        </p>
      </div>
    );
  },
};
