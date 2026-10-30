import type { Meta, StoryObj } from "@storybook/react-vite";
import { userEvent, waitFor } from "storybook/test";
import { LedgerStage, storyMovementIds } from "@/dev/LedgerStage";
import { translator } from "../../shell/strings";
import { LEDGER_SHAPES } from "@/dev/ledgerFixture";

// The Ledger page over the scenario's synthetic ledger, one story for each
// way that ledger answers. The page is the one the window mounts; only the
// port behind it is the fixture's.

const meta: Meta<typeof LedgerStage> = {
  title: "Ledger/Page",
  component: LedgerStage,
  render: (args, { globals }) => (
    <LedgerStage {...args} locale={String(globals.locale ?? "en")} />
  ),
  args: { locale: "en" },
  argTypes: {
    shape: { control: "select", options: LEDGER_SHAPES },
    locale: { table: { disable: true } },
  },
  parameters: { fill: true, layout: "fullscreen" },
};
export default meta;
type Story = StoryObj<typeof LedgerStage>;

export const Movements: Story = {};
export const Empty: Story = { args: { shape: "empty" } };
export const Large: Story = { args: { shape: "large" } };
export const Reading: Story = { args: { shape: "slow" } };
export const Refused: Story = { args: { shape: "refused" } };
export const Unavailable: Story = { args: { shape: "unavailable" } };
export const WritesNotSettled: Story = {
  name: "Writes not settled",
  args: { shape: "unknown" },
};
export const SignedOut: Story = { args: { signedOut: true } };
export const AllPeriods: Story = {
  name: "Every period",
  args: { period: null },
};
export const Comfortable: Story = {
  args: { view: { density: "comfortable" } },
};
export const WithInspector: Story = {
  name: "With the inspector open",
  args: { view: { inspectorOpen: true } },
};
export const ToMatch: Story = {
  name: "To match queue",
  args: { view: { savedView: "to_match", inspectorOpen: true } },
};
export const Searching: Story = {
  name: "Searching the movements",
  args: { movements: { search: "farmacia" } },
};
export const Grouped: Story = {
  name: "Grouped by counterparty",
  args: { view: { groupBy: "counterparty" } },
};
export const ToClassify: Story = {
  name: "Movements to classify",
  args: { view: { savedView: "to_classify" } },
};
export const Foreign: Story = {
  name: "Foreign currency",
  args: { view: { savedView: "foreign" } },
};
export const OneSelected: Story = {
  name: "One movement selected",
  args: {
    view: { inspectorOpen: true },
    movements: {
      selection: storyMovementIds(
        (m) =>
          m.transaction.direction === "OUTGOING" &&
          m.transaction.business_classification === "MIXED",
        1,
      ),
    },
  },
};
export const SeveralSelected: Story = {
  name: "Several movements selected",
  args: {
    view: { inspectorOpen: true },
    movements: {
      selection: storyMovementIds(
        (m) => m.transaction.business_classification === "NOT_YET_PROCESSED",
        4,
      ),
    },
  },
};
export const Invoices: Story = { args: { view: { section: "invoices" } } };
export const Documents: Story = {
  args: { shape: "documents", view: { section: "documents" } },
};
export const DocumentsReaderMissing: Story = {
  name: "Documents, local AI not set up",
  args: { shape: "reader_missing", view: { section: "documents" } },
};
export const Rules: Story = { args: { view: { section: "rules" } } };
export const Registers: Story = { args: { view: { section: "registers" } } };
export const Assets: Story = { args: { view: { section: "assets" } } };
export const Health: Story = {
  // The readiness check reads once the movements have been, so the page
  // starts on them and goes to Health from the Setup menu, as a person does.
  play: async ({ canvasElement }) => {
    const setup = await waitFor(() => {
      const found = canvasElement.querySelector<HTMLElement>(".ledger-setup");
      if (!found) throw new Error("the Setup menu is not drawn yet");
      return found;
    });
    await userEvent.click(setup);
    const items = await waitFor(() => {
      const found =
        canvasElement.ownerDocument.querySelectorAll<HTMLElement>(
          "[role=menuitem]",
        );
      if (found.length === 0) throw new Error("the menu is not open yet");
      return found;
    });
    await userEvent.click(items[items.length - 1]!);
    // The section is shown once the menu has gone, which hides the page
    // from assistive technology while it closes.
    await waitFor(() => {
      if (canvasElement.ownerDocument.querySelector("[role=menu]"))
        throw new Error("the menu is still closing");
    });
  },
};

/** Presses the page's header button named by `key`, as a person does. */
const pressed =
  (key: string): NonNullable<Story["play"]> =>
  async ({ canvasElement, globals }) => {
    const name = translator(String(globals.locale ?? "en"))(key);
    const button = await waitFor(() => {
      const found = [
        ...canvasElement.querySelectorAll<HTMLElement>("button"),
      ].find(
        (candidate) =>
          candidate.getAttribute("aria-label")?.startsWith(name) ||
          candidate.textContent?.trim() === name,
      );
      if (!found) throw new Error(`${name} is not drawn yet`);
      return found;
    });
    await userEvent.click(button);
  };

export const ImportOpen: Story = {
  name: "Import dialog",
  play: pressed("desktop.ledger.action.import"),
};
export const ExportOpen: Story = {
  name: "Export dialog",
  play: pressed("desktop.ledger.action.export"),
};
export const AddingMovement: Story = {
  name: "Adding a movement",
  play: pressed("desktop.ledger.action.add_movement"),
};
export const AddingInvoice: Story = {
  name: "Adding an invoice",
  args: { view: { section: "invoices" } },
  play: pressed("desktop.ledger.invoices.action.add"),
};
