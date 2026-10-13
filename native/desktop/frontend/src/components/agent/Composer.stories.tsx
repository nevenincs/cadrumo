import type { Meta, StoryObj } from "@storybook/react-vite";
import type { ComponentProps, ReactNode } from "react";
import { Specimen } from "@/dev/catalogue/Frame";
import { Composer } from "./Composer";
import type {
  AgentSelection,
  ModelOption,
  ProviderOption,
  StagedAttachment,
} from "./types";

// Appearance only. Every value below is fixed specimen data: nothing is
// uploaded, sent or answered, and no progress moves. The handlers given do
// nothing, so a control that has one is drawn as available.

/** The note every agent story carries, saying what it does not prove. */
export const APPEARANCE_NOTE =
  "Appearance only: fixed specimen data, no host. Nothing here uploads, sends or answers, and no progress moves.";

export const NOOP = () => undefined;

/** Keeps a draft in place: the specimen never sends it. */
export const KEEP_DRAFT = () => false;

export const PROVIDERS: ProviderOption[] = [
  { id: "anthropic", name: "Anthropic", selectable: true },
  {
    id: "local",
    name: "On this computer",
    selectable: false,
    unavailableReason: "No local model is installed",
  },
];

// A specimen's efforts, as a model's catalog entry would list them.
const EFFORTS = [
  { id: "low", name: "Low" },
  { id: "medium", name: "Medium" },
  { id: "high", name: "High" },
];

export const MODELS: Record<string, ModelOption[]> = {
  anthropic: [
    {
      id: "opus",
      name: "Opus 5.5",
      description: "Most capable, for careful work across many documents",
      efforts: EFFORTS,
      defaultEffort: "high",
    },
    {
      id: "sonnet",
      name: "Sonnet 5",
      description: "Balanced speed and depth for everyday questions",
      efforts: EFFORTS,
      defaultEffort: "medium",
    },
    {
      id: "haiku",
      name: "Haiku 5",
      description: "Quick answers to short questions",
      efforts: [],
    },
  ],
  local: [],
};

export const SELECTION: AgentSelection = {
  providerId: "anthropic",
  modelId: "opus",
  effort: "high",
};

// Pictures for image tiles, drawn inline: no request leaves the catalogue.
function picture(body: string): string {
  return `data:image/svg+xml;charset=utf-8,${encodeURIComponent(
    `<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'>${body}</svg>`,
  )}`;
}

export const RECEIPT_PICTURE = picture(
  "<rect width='64' height='64' fill='gainsboro'/><rect x='18' y='8' width='28' height='48' fill='white'/><path d='M23 18h18M23 25h14M23 32h18M23 39h10' stroke='gray' stroke-width='2'/>",
);
export const INVOICE_PICTURE = picture(
  "<rect width='64' height='64' fill='lightsteelblue'/><rect x='12' y='10' width='40' height='44' fill='white'/><path d='M18 20h16M18 28h28M18 34h28M18 40h20' stroke='slategray' stroke-width='2'/>",
);

export const READY_FILES: StagedAttachment[] = [
  {
    id: "a1",
    name: "factura-2026-031.pdf",
    extension: "pdf",
    sizeBytes: 182_400,
    kind: "document",
    state: "ready",
  },
  {
    id: "a2",
    name: "ticket-gasolinera.jpg",
    extension: "jpg",
    sizeBytes: 1_240_000,
    kind: "image",
    state: "ready",
    thumbnailUrl: RECEIPT_PICTURE,
  },
  {
    id: "a3",
    name: "extracto-tercer-trimestre.xlsx",
    extension: "xlsx",
    sizeBytes: 48_900,
    kind: "sheet",
    state: "ready",
  },
];

export const UPLOADING_FILES: StagedAttachment[] = [
  ...READY_FILES.slice(0, 1),
  {
    id: "u1",
    name: "facturas-septiembre.zip",
    extension: "zip",
    sizeBytes: 8_400_000,
    kind: "archive",
    state: "uploading",
    progress: 0.4,
    memberCount: 23,
  },
  {
    id: "u2",
    name: "notas.txt",
    extension: "txt",
    sizeBytes: 2_100,
    kind: "text",
    state: "queued",
  },
];

type Args = ComponentProps<typeof Composer>;

function Column({ children }: { children: ReactNode }) {
  return (
    <div className="grid w-(--agent-w) gap-3">
      <Specimen title="Composer" note={APPEARANCE_NOTE}>
        <div className="w-full">{children}</div>
      </Specimen>
    </div>
  );
}

const meta = {
  title: "Shell/Agent/Composer",
  excludeStories: /^[A-Z][A-Z_]*$/,
  parameters: {
    surface: "chrome",
    docs: { description: { component: APPEARANCE_NOTE } },
  },
  args: {
    locale: "en",
    attachments: [],
    providers: PROVIDERS,
    models: MODELS,
    selection: SELECTION,
    onSend: KEEP_DRAFT,
    onStop: NOOP,
    onAddFiles: NOOP,
    onSelectionChange: NOOP,
    onRemoveAttachment: NOOP,
    onRemoveAllAttachments: NOOP,
    onShowAllAttachments: NOOP,
  },
  render: (args: Args, { globals }) => (
    <Column>
      <Composer
        key={args.defaultDraft ?? ""}
        {...args}
        locale={String(globals.locale)}
      />
    </Column>
  ),
} satisfies Meta<Args>;
export default meta;
type Story = StoryObj<typeof meta>;

export const Empty: Story = { name: "Empty: Send held back" };

export const WithText: Story = {
  args: {
    defaultDraft:
      "What is left to file for the third quarter, and when is the 303 due?",
  },
};

export const WithAttachments: Story = {
  args: { defaultDraft: "Classify these for me.", attachments: READY_FILES },
};

export const UploadsInProgress: Story = {
  name: "Uploads in progress: Send held back",
  args: {
    defaultDraft: "Read these when they arrive.",
    attachments: UPLOADING_FILES,
  },
};

export const Running: Story = {
  name: "Running: Stop",
  args: { running: true },
};

export const EveryActionUnavailable: Story = {
  args: {
    defaultDraft: "Nothing here can act yet.",
    attachments: READY_FILES,
    onSend: undefined,
    onStop: undefined,
    onAddFiles: undefined,
    onSelectionChange: undefined,
    onRemoveAttachment: undefined,
    onRemoveAllAttachments: undefined,
    onShowAllAttachments: undefined,
  },
};
