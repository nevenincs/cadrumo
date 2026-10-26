import type { Meta, StoryObj } from "@storybook/react-vite";
import type { ComponentProps } from "react";
import { APPEARANCE_NOTE, NOOP } from "./Composer.stories";
import { DocumentsPanel } from "./DocumentsPanel";
import type { ConversationDocument } from "./types";

export const DOCUMENTS: ConversationDocument[] = [
  {
    id: "d1",
    name: "factura-2026-031.pdf",
    extension: "pdf",
    sizeBytes: 182_400,
    kind: "document",
  },
  {
    id: "d2",
    name: "factura-luz.png",
    extension: "png",
    sizeBytes: 920_000,
    kind: "image",
  },
  {
    id: "d3",
    name: "extracto-tercer-trimestre.xlsx",
    extension: "xlsx",
    sizeBytes: 48_900,
    kind: "sheet",
  },
  {
    id: "d4",
    name: "notas.txt",
    extension: "txt",
    sizeBytes: 2_100,
    kind: "text",
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
    onAddFiles: NOOP,
    onRefresh: NOOP,
    onUse: NOOP,
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
export const StoredDocuments: Story = {};
export const SelectedForNextMessage: Story = { args: { selectedIds: ["d1"] } };
export const Empty: Story = { args: { documents: [] } };
export const Removing: Story = { args: { busy: true } };
export const EveryActionUnavailable: Story = {
  args: {
    onClose: undefined,
    onAddFiles: undefined,
    onRefresh: undefined,
    onUse: undefined,
    onRemove: undefined,
  },
};
