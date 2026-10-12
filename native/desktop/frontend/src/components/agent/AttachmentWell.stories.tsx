import type { Meta, StoryObj } from "@storybook/react-vite";
import type { ComponentProps } from "react";
import { Specimen } from "@/dev/catalogue/Frame";
import { AttachmentWell } from "./AttachmentWell";
import {
  APPEARANCE_NOTE,
  INVOICE_PICTURE,
  NOOP,
  READY_FILES,
  RECEIPT_PICTURE,
} from "./Composer.stories";
import type { StagedAttachment } from "./types";

// Appearance only: fixed tiles, each in one state. Upload progress is a
// fixed share; nothing is uploaded and nothing moves.

const MANY: StagedAttachment[] = Array.from({ length: 17 }, (_, index) => {
  const number = String(index + 1).padStart(2, "0");
  return index % 3 === 0
    ? {
        id: `m${number}`,
        name: `ticket-${number}.jpg`,
        extension: "jpg",
        sizeBytes: 640_000 + index * 21_000,
        kind: "image",
        state: "ready",
        thumbnailUrl: index % 2 === 0 ? RECEIPT_PICTURE : INVOICE_PICTURE,
      }
    : {
        id: `m${number}`,
        name: `factura-${number}.pdf`,
        extension: "pdf",
        sizeBytes: 120_000 + index * 9_000,
        kind: "document",
        state: "ready",
      };
});

const REFUSED: StagedAttachment[] = [
  ...READY_FILES.slice(0, 1),
  {
    id: "r1",
    name: "instalador.exe",
    extension: "exe",
    sizeBytes: 31_000_000,
    kind: "document",
    state: "refused",
    refusalReason: "Programs can't be added",
  },
  {
    id: "r2",
    name: "escaneo-completo.pdf",
    extension: "pdf",
    sizeBytes: 212_000_000,
    kind: "document",
    state: "refused",
    refusalReason: "Larger than 100 MB",
  },
];

const ARCHIVES: StagedAttachment[] = [
  {
    id: "z1",
    name: "facturas-septiembre.zip",
    extension: "zip",
    sizeBytes: 8_400_000,
    kind: "archive",
    state: "ready",
    memberCount: 23,
  },
  {
    id: "z2",
    name: "contrato.zip",
    extension: "zip",
    sizeBytes: 310_000,
    kind: "archive",
    state: "ready",
    memberCount: 1,
  },
  {
    id: "z3",
    name: "extractos-2026.zip",
    extension: "zip",
    sizeBytes: 2_600_000,
    kind: "archive",
    state: "uploading",
    progress: 0.4,
    memberCount: 12,
  },
];

const IMAGES: StagedAttachment[] = [
  {
    id: "i1",
    name: "ticket-restaurante.jpg",
    extension: "jpg",
    sizeBytes: 1_480_000,
    kind: "image",
    state: "ready",
    thumbnailUrl: RECEIPT_PICTURE,
  },
  {
    id: "i2",
    name: "factura-luz.png",
    extension: "png",
    sizeBytes: 920_000,
    kind: "image",
    state: "ready",
    thumbnailUrl: INVOICE_PICTURE,
  },
  {
    id: "i3",
    name: "ticket-parking.heic",
    extension: "heic",
    sizeBytes: 2_100_000,
    kind: "image",
    state: "queued",
  },
];

type Args = Omit<ComponentProps<typeof AttachmentWell>, "locale">;

const meta = {
  title: "Shell/Agent/Attachment well",
  parameters: {
    surface: "chrome",
    docs: { description: { component: APPEARANCE_NOTE } },
  },
  args: {
    attachments: READY_FILES.slice(0, 1),
    onRemove: NOOP,
    onRemoveAll: NOOP,
    onShowAll: NOOP,
  },
  render: (args: Args, { globals }) => (
    <Specimen title="Attachment well" note={APPEARANCE_NOTE}>
      <div className="w-(--agent-w) rounded-xl border bg-card">
        <AttachmentWell {...args} locale={String(globals.locale)} />
      </div>
    </Specimen>
  ),
} satisfies Meta<Args>;
export default meta;
type Story = StoryObj<typeof meta>;

export const OneFile: Story = {};

export const ManyFilesOverflow: Story = {
  name: "Many files: +N more",
  args: { attachments: MANY },
};

export const Refused: Story = {
  name: "Refused tiles",
  args: { attachments: REFUSED },
};

export const Zip: Story = {
  name: "ZIP archives",
  args: { attachments: ARCHIVES },
};

export const ImagesWithThumbnails: Story = {
  args: { attachments: IMAGES },
};

export const Unavailable: Story = {
  name: "Every action unavailable",
  args: {
    attachments: MANY,
    onRemove: undefined,
    onRemoveAll: undefined,
    onShowAll: undefined,
  },
};
