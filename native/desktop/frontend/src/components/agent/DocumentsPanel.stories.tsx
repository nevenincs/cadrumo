import type { Meta, StoryObj } from "@storybook/react-vite";
import type { ComponentProps } from "react";
import { userEvent } from "storybook/test";
import { APPEARANCE_NOTE, INVOICE_PICTURE, NOOP } from "./Composer.stories";
import { DocumentsPanel } from "./DocumentsPanel";
import type { ConversationDocument } from "./types";

// Appearance only: fixed documents in fixed states. Nothing is read,
// extracted or removed; a role chosen here is not kept.

export const DOCUMENTS: ConversationDocument[] = [
  {
    id: "d1",
    name: "factura-2026-031.pdf",
    extension: "pdf",
    sizeBytes: 182_400,
    role: "ledger",
    status: "ready",
    kind: "document",
  },
  {
    id: "d2",
    name: "factura-luz.png",
    extension: "png",
    sizeBytes: 920_000,
    role: "ledger",
    status: "needsReview",
    kind: "image",
    thumbnailUrl: INVOICE_PICTURE,
  },
  {
    id: "d3",
    name: "facturas-septiembre.zip",
    extension: "zip",
    sizeBytes: 8_400_000,
    role: "information",
    status: "extracting",
    kind: "archive",
    members: [
      {
        id: "d3-1",
        name: "proveedor-a-0912.pdf",
        extension: "pdf",
        sizeBytes: 140_000,
        role: "information",
        status: "ready",
      },
      {
        id: "d3-2",
        name: "proveedor-b-0915.xml",
        extension: "xml",
        sizeBytes: 22_000,
        role: "information",
        status: "extracting",
      },
      {
        id: "d3-3",
        name: "Thumbs.db",
        extension: "db",
        sizeBytes: 6_000,
        role: "information",
        status: "skipped",
      },
    ],
  },
  {
    id: "d4",
    name: "extracto-tercer-trimestre.xlsx",
    extension: "xlsx",
    sizeBytes: 48_900,
    role: "context",
    status: "uploading",
    kind: "sheet",
  },
  {
    id: "d5",
    name: "escaneo-borroso.pdf",
    extension: "pdf",
    sizeBytes: 3_100_000,
    role: "information",
    status: "failed",
    kind: "document",
  },
];

type Args = Omit<ComponentProps<typeof DocumentsPanel>, "locale">;

const meta = {
  title: "Shell/Agent/Documents panel",
  excludeStories: /^[A-Z][A-Z_]*$/,
  parameters: {
    fill: true,
    docs: { description: { component: APPEARANCE_NOTE } },
  },
  args: {
    documents: DOCUMENTS,
    onClose: NOOP,
    onRoleChange: NOOP,
    onRemove: NOOP,
  },
  render: (args: Args, { globals }) => (
    <div className="flex h-dvh w-(--agent-w) flex-col border-r bg-background">
      <p className="px-3 py-2 text-xs text-faint">{APPEARANCE_NOTE}</p>
      <DocumentsPanel {...args} locale={String(globals.locale)} />
    </div>
  ),
} satisfies Meta<Args>;
export default meta;
type Story = StoryObj<typeof meta>;

export const MixedRolesAndStatuses: Story = {};

export const ZipExpanded: Story = {
  name: "ZIP expanded, with a skipped member",
  play: async ({ canvasElement }) => {
    const expand = canvasElement.querySelector<HTMLElement>(
      "[aria-expanded=false][aria-controls]",
    );
    if (expand) await userEvent.click(expand);
  },
};

export const Empty: Story = { args: { documents: [] } };

export const EveryActionUnavailable: Story = {
  args: { onClose: undefined, onRoleChange: undefined, onRemove: undefined },
};
