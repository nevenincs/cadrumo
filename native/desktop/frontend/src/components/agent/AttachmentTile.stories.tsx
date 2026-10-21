import type { Meta, StoryObj } from "@storybook/react-vite";
import { Specimen } from "@/dev/catalogue/Frame";
import { AttachmentTile } from "./AttachmentTile";
import { APPEARANCE_NOTE, NOOP, RECEIPT_PICTURE } from "./Composer.stories";
import type { StagedAttachment } from "./types";

// Appearance only: one tile per state, at fixed values. The upload ring is
// drawn at a fixed 40 % and never moves.

const TILES: StagedAttachment[] = [
  {
    id: "t1",
    name: "factura-2026-031.pdf",
    extension: "pdf",
    sizeBytes: 182_400,
    kind: "document",
    state: "ready",
  },
  {
    id: "t2",
    name: "ticket-gasolinera.jpg",
    extension: "jpg",
    sizeBytes: 1_240_000,
    kind: "image",
    state: "ready",
    thumbnailUrl: RECEIPT_PICTURE,
  },
  {
    id: "t3",
    name: "extracto.xlsx",
    extension: "xlsx",
    sizeBytes: 48_900,
    kind: "sheet",
    state: "uploading",
    progress: 0.4,
  },
  {
    id: "t4",
    name: "notas.txt",
    extension: "txt",
    sizeBytes: 2_100,
    kind: "text",
    state: "queued",
  },
  {
    id: "t5",
    name: "facturas-septiembre.zip",
    extension: "zip",
    sizeBytes: 8_400_000,
    kind: "archive",
    state: "ready",
    memberCount: 23,
  },
  {
    id: "t6",
    name: "instalador.exe",
    extension: "exe",
    sizeBytes: 31_000_000,
    kind: "document",
    state: "refused",
    refusalReason: "Programs can't be added",
  },
];

function Tiles({ removable, locale }: { removable: boolean; locale: string }) {
  return (
    <Specimen title="Attachment tiles" note={APPEARANCE_NOTE}>
      <ul className="grid w-(--agent-w) grid-cols-4 gap-2">
        {TILES.map((tile) => (
          <AttachmentTile
            key={tile.id}
            attachment={tile}
            locale={locale}
            onRemove={removable ? NOOP : undefined}
          />
        ))}
      </ul>
    </Specimen>
  );
}

const meta = {
  title: "Shell/Agent/Attachment tile",
  parameters: {
    surface: "card",
    docs: { description: { component: APPEARANCE_NOTE } },
  },
  args: { removable: true },
  render: (args: { removable: boolean }, { globals }) => (
    <Tiles {...args} locale={String(globals.locale)} />
  ),
} satisfies Meta<{ removable: boolean }>;
export default meta;
type Story = StoryObj<typeof meta>;

export const EveryState: Story = {};

export const RemoveUnavailable: Story = { args: { removable: false } };
