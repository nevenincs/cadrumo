import type { Meta, StoryObj } from "@storybook/react-vite";
import { useMemo } from "react";
import { userEvent, waitFor, within } from "storybook/test";
import {
  STORY_PERIOD,
  STORY_READER,
  useLedgerPort,
  useStoryStage,
} from "@/dev/LedgerStage";
import type { LedgerShape } from "@/dev/ledgerFixture";
import type { LedgerPort } from "../../../shell/ledger";
import type { InventoryListResult } from "../../../shell/ledgerSetup";
import { translator } from "../../../shell/strings";
import { usePagePause, WritePauseContext } from "../WritePause";
import type { SetupProps } from "../setup/setupProps";
import { StockPane } from "./StockPane";

// The Stock panel of the Assets tab over the scenario's ledger: its books for
// a year, the forms to add a book and a movement, a valuation shown, and the
// states the list can end in. Names, amounts and files are made up.

const noop = () => undefined;

/** How the list of stock books answers: the scenario ledger's own, or as the
 * story asks. */
type Answer = "fixture" | "one" | "empty" | "refused" | "loading";

type Args = {
  shape?: LedgerShape;
  answer?: Answer;
  signedOut?: boolean;
  locale: string;
};

/** The scenario's port, with the list of books answered as the story asks. A
 * write and a valuation still go to the scenario's ledger. */
function withListAnswer(port: LedgerPort, answer: Answer): LedgerPort {
  if (answer === "fixture") return port;
  return {
    ...port,
    submit: ((definition: string, payload: never) => {
      if (definition !== "ledger.inventory.list")
        return port.submit(definition as never, payload);
      if (answer === "loading") return new Promise(() => undefined);
      if (answer === "refused")
        return Promise.resolve({
          kind: "refused",
          operation_id: "story",
          revision: 1,
          reason: "REFUSED_INVENTORY_SERVICE_INPUT",
          detail: null,
        });
      if (answer === "empty")
        return Promise.resolve({
          kind: "settled",
          operation_id: "story",
          revision: 1,
          result: { profile_id: "synthetic", rows: [] },
        });
      return port.submit(definition as never, payload).then((outcome) =>
        outcome.kind === "settled"
          ? {
              ...outcome,
              result: {
                ...(outcome.result as InventoryListResult),
                rows: (outcome.result as InventoryListResult).rows.slice(0, 1),
              },
            }
          : outcome,
      );
    }) as LedgerPort["submit"],
  };
}

function Stage({ shape, answer = "fixture", signedOut, locale }: Args) {
  const base = useLedgerPort(shape);
  const port = useMemo(() => withListAnswer(base, answer), [base, answer]);
  const { stage, onStage } = useStoryStage();
  const reader = signedOut ? null : STORY_READER;
  const pause = usePagePause({ reader, afterReread: noop });
  const props: SetupProps = {
    port,
    reader,
    locale,
    rows: null,
    stage: stage.content,
    onStage,
    years: [2025, 2026],
    fallbackYear: STORY_PERIOD.year,
    period: STORY_PERIOD,
  };
  return (
    <WritePauseContext.Provider value={pause}>
      <div className="flex h-full min-h-0 flex-col overflow-y-auto p-3">
        <StockPane {...props} />
      </div>
    </WritePauseContext.Provider>
  );
}

const meta: Meta<Args> = {
  title: "Ledger/Assets/Stock",
  render: (args, { globals }) => (
    <Stage {...args} locale={String(globals.locale ?? "en")} />
  ),
  args: { locale: "en" },
  argTypes: { locale: { table: { disable: true } } },
  parameters: { fill: true, layout: "fullscreen" },
};
export default meta;
type Story = StoryObj<Args>;

type PlayContext = Parameters<NonNullable<Story["play"]>>[0];
const wordsOf = (context: PlayContext) =>
  translator(String(context.globals.locale ?? "en"));

/** Waits for a control the story's own words name. */
async function control(
  context: PlayContext,
  name: string,
  within_?: HTMLElement,
) {
  return waitFor(() => {
    const found = within(within_ ?? context.canvasElement).queryAllByRole(
      "button",
      { name },
    )[0];
    if (!found) throw new Error(`${name} is not drawn yet`);
    return found;
  });
}

/** Presses the control a name gives, the first of them where several are drawn. */
async function press(context: PlayContext, name: string) {
  await userEvent.click(await control(context, name));
}

const field = (context: PlayContext, label: string) =>
  waitFor(() => within(context.canvasElement).getByLabelText(label));

export const SeveralBooks: Story = { name: "Several books" };

export const OneBook: Story = {
  name: "One book",
  args: { answer: "one" },
};

export const NoBook: Story = {
  name: "No book yet",
  args: { answer: "empty" },
};

export const BookForm: Story = {
  name: "Adding a book",
  play: (context) =>
    press(context, wordsOf(context)("desktop.ledger.stock.action.add_book")),
};

export const MovementForm: Story = {
  name: "Adding a movement",
  play: (context) =>
    press(
      context,
      wordsOf(context)("desktop.ledger.stock.action.add_movement"),
    ),
};

export const PurchaseForm: Story = {
  name: "Adding a purchase",
  play: async (context) => {
    const t = wordsOf(context);
    await press(context, t("desktop.ledger.stock.action.add_movement"));
    await userEvent.selectOptions(
      await field(context, t("desktop.ledger.inventory.kind_label")),
      "purchase",
    );
  },
};

export const ValuationShown: Story = {
  name: "A valuation shown",
  play: (context) =>
    press(context, wordsOf(context)("desktop.ledger.stock.action.preview")),
};

export const MovementRefused: Story = {
  name: "A movement refused",
  play: async (context) => {
    const t = wordsOf(context);
    await userEvent.selectOptions(
      await field(context, t("desktop.ledger.assets.year")),
      "2025",
    );
    const row = await waitFor(() => {
      const cell = within(context.canvasElement).queryByText(
        "Enmarcado (cerrado en 2025)",
      );
      const found = cell?.closest("tr");
      if (!found) throw new Error("the book is not drawn yet");
      return found;
    });
    await userEvent.click(
      await control(
        context,
        t("desktop.ledger.stock.action.add_movement"),
        row,
      ),
    );
    await userEvent.type(
      await field(context, t("desktop.ledger.inventory.date")),
      "2025-12-01",
    );
    await userEvent.selectOptions(
      await field(context, t("desktop.ledger.inventory.kind_label")),
      "cogs",
    );
    await userEvent.type(
      await field(context, t("desktop.ledger.inventory.quantity")),
      "5",
    );
    await press(context, t("desktop.ledger.stock.submit.movement"));
  },
};

export const Loading: Story = {
  name: "Stock being loaded",
  args: { answer: "loading" },
};

export const Refused: Story = {
  name: "Stock refused",
  args: { answer: "refused" },
};

export const Unavailable: Story = {
  name: "Ledger not answering",
  args: { shape: "unavailable" },
};

export const SignedOut: Story = {
  name: "Account withholds the ledger",
  args: { signedOut: true },
};
