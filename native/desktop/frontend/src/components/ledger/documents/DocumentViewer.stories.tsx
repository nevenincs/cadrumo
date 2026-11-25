import type { Meta, StoryObj } from "@storybook/react-vite";
import { expect, waitFor, within } from "storybook/test";
import { STORY_READER, useLedgerPort } from "@/dev/LedgerStage";
import {
  STRUCTURED_SAMPLE_NAMES,
  structuredSampleId,
} from "@/dev/fixtures/documentPage";
import { hex64 } from "@/dev/fixtures/ledger";
import { DocumentViewer } from "./DocumentViewer";
import type { DocumentReference } from "./documentsModel";

// The viewer over the scenario's `documents` ledger: a drawn page of an
// image, a PDF with two pages, and a structured e-invoice shown as the facts
// its record states. Shapes: `documents` holds the stored documents, and the
// refusal story asks for a document the ledger does not hold.

type Args = { reference: DocumentReference; fileName: string };

function Viewer({ reference, fileName }: Args) {
  const port = useLedgerPort("documents");
  return (
    <div className="flex h-96 w-full max-w-2xl flex-col">
      <DocumentViewer
        port={port}
        reader={STORY_READER}
        reference={reference}
        fileName={fileName}
      />
    </div>
  );
}

const meta = {
  title: "Ledger/Documents/DocumentViewer",
  component: Viewer,
  tags: ["autodocs"],
} satisfies Meta<typeof Viewer>;
export default meta;
type Story = StoryObj<typeof meta>;

const evidence = (name: string): DocumentReference => ({
  kind: "evidence",
  id: hex64(`evidence:${name}`).slice(0, 16),
});
const attachment = (name: string): DocumentReference => ({
  kind: "attachment",
  id: structuredSampleId(name),
});

export const ImagePage: Story = {
  args: {
    reference: evidence("ticket-plenoil-1015.jpg"),
    fileName: "ticket-plenoil-1015.jpg",
  },
  play: async ({ canvasElement }) => {
    await waitFor(() =>
      expect(within(canvasElement).getByRole("img")).toBeVisible(),
    );
  },
};

export const MultiPagePdf: Story = {
  args: {
    reference: evidence("factura-domestika-lettering.pdf"),
    fileName: "factura-domestika-lettering.pdf",
  },
  play: async ({ canvasElement }) => {
    await waitFor(() =>
      expect(
        canvasElement.querySelector(".ledger-document-next"),
      ).not.toBeNull(),
    );
  },
};

export const StructuredWithLines: Story = {
  args: {
    reference: attachment(STRUCTURED_SAMPLE_NAMES.withLines),
    fileName: STRUCTURED_SAMPLE_NAMES.withLines,
  },
  play: async ({ canvasElement }) => {
    await waitFor(() =>
      expect(
        canvasElement.querySelectorAll(
          ".ledger-document-structured-lines tbody tr",
        ),
      ).toHaveLength(2),
    );
    await expect(
      canvasElement.querySelector(".ledger-document-zoom"),
    ).toBeNull();
  },
};

export const StructuredWithoutLines: Story = {
  args: {
    reference: attachment(STRUCTURED_SAMPLE_NAMES.withoutLines),
    fileName: STRUCTURED_SAMPLE_NAMES.withoutLines,
  },
  play: async ({ canvasElement }) => {
    await waitFor(() =>
      expect(
        canvasElement.querySelector(".ledger-document-structured-facts"),
      ).not.toBeNull(),
    );
    await expect(
      canvasElement.querySelector(".ledger-document-structured-lines"),
    ).toBeNull();
  },
};

export const Refused: Story = {
  args: {
    reference: { kind: "attachment", id: hex64("no-such-document") },
    fileName: "missing.pdf",
  },
  play: async ({ canvasElement }) => {
    await waitFor(() =>
      expect(
        canvasElement.querySelector(".ledger-document-refused"),
      ).not.toBeNull(),
    );
  },
};
