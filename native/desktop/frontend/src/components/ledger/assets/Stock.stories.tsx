import type { Meta, StoryObj } from "@storybook/react-vite";
import { useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
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

/** How the choices the forms offer are answered. */
type Choices = "fixture" | "refused";

/** What the backend answers when a chosen file cannot be kept. */
const FILE_REFUSED = {
  kind: "refused",
  operation_id: "story",
  revision: 1,
  reason: "REFUSED_INVENTORY_SERVICE_INPUT",
  detail: {
    outcome: "refused",
    profile_id: "synthetic",
    reference: null,
    content_digest: null,
    refusal: {
      code: "REFUSED_INVENTORY_SERVICE_INPUT",
      reason: "evidence_file_not_admitted",
      actividad_id: null,
      year: null,
      movement_id: null,
      valuation_method: null,
      reason_key:
        "application.inventory.service.errors.evidence_file_not_admitted",
      reason_facts: [],
    },
  },
};

type Args = {
  shape?: LedgerShape;
  answer?: Answer;
  signedOut?: boolean;
  /** The choices the forms offer, answered or refused. */
  choices?: Choices;
  /** Every file chosen is one the book cannot keep. */
  fileRefused?: boolean;
  /** Also sends a change to a retired book and shows how it was refused. */
  sendRetiredChange?: boolean;
  /** Also sends one change twice and shows how each was answered. */
  replayProbe?: boolean;
  locale: string;
};

/** The scenario's port, with the list of books answered as the story asks. A
 * write and a valuation still go to the scenario's ledger. */
function withListAnswer(
  port: LedgerPort,
  answer: Answer,
  choices: Choices,
  fileRefused: boolean,
): LedgerPort {
  if (answer === "fixture" && choices === "fixture" && !fileRefused)
    return port;
  return {
    ...port,
    submit: ((definition: string, payload: never) => {
      if (definition === "ledger.inventory.evidence.add" && fileRefused)
        return Promise.resolve(FILE_REFUSED);
      if (definition === "ledger.inventory.options" && choices === "refused")
        return Promise.resolve({
          kind: "refused",
          operation_id: "story",
          revision: 1,
          reason: "REFUSED_INVENTORY_SERVICE_INPUT",
          detail: null,
        });
      if (answer === "fixture")
        return port.submit(definition as never, payload);
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

/** Sends a change twice under one reference, and another to a retired book,
 * and says in plain words how the ledger answered each. */
function Probe({
  port,
  kind,
}: {
  port: LedgerPort;
  kind: "replay" | "retired";
}) {
  const [said, setSaid] = useState<string[]>([]);
  const send = async (
    id: string,
    label: string,
    book: string,
    year: number,
  ) => {
    try {
      const outcome = await port.submit("ledger.inventory.describe", {
        actividad_id: book,
        year,
        correction_id: id,
        label,
        description: null,
      });
      const result = outcome.kind === "settled" ? outcome.result : null;
      return result?.outcome ?? outcome.kind;
    } catch {
      return "failed";
    }
  };
  return (
    <div className="flex flex-col gap-2">
      <Button
        size="sm"
        onClick={async () => {
          if (kind === "replay") {
            const id = crypto.randomUUID();
            const book = "Venta en línea de material de dibujo";
            const first = await send(id, "Dibujo en línea", book, 2026);
            const second = await send(id, "Dibujo en línea", book, 2026);
            const other = await send(id, "Otro nombre", book, 2026);
            setSaid([first, second, other]);
          } else {
            const retire = await port.submit("ledger.inventory.correct", {
              actividad_id: "Taller de enmarcado",
              year: 2025,
              correction_id: crypto.randomUUID(),
              reason: "keying_error",
              opening_stock: { decimal: "10" },
              valuation_method: null,
            });
            setSaid([
              retire.kind === "refused"
                ? String(
                    (
                      retire.detail as {
                        refusal?: { reason?: string };
                      } | null
                    )?.refusal?.reason,
                  )
                : retire.kind,
            ]);
          }
        }}
      >
        {kind === "replay"
          ? "Send the same change twice"
          : "Change a retired book"}
      </Button>
      <ul>
        {said.map((line, at) => (
          <li key={at}>{line}</li>
        ))}
      </ul>
    </div>
  );
}

function Stage({
  shape,
  answer = "fixture",
  choices = "fixture",
  fileRefused = false,
  signedOut,
  sendRetiredChange,
  replayProbe,
  locale,
}: Args) {
  const base = useLedgerPort(shape);
  const port = useMemo(
    () => withListAnswer(base, answer, choices, fileRefused),
    [base, answer, choices, fileRefused],
  );
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
        {replayProbe && <Probe port={port} kind="replay" />}
        {sendRetiredChange && <Probe port={port} kind="retired" />}
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

/** Chooses one of the values a select offers, once the backend has served
 * the choices. */
async function pick(context: PlayContext, label: string, value: string) {
  const select = await field(context, label);
  await waitFor(() => {
    if (!select.querySelector(`option[value="${value}"]`))
      throw new Error(`${value} is not offered yet`);
  });
  await userEvent.selectOptions(select, value);
}

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
    await pick(context, t("desktop.ledger.inventory.kind_label"), "purchase");
  },
};

export const ValuationShown: Story = {
  name: "A valuation shown",
  play: (context) =>
    press(context, wordsOf(context)("desktop.ledger.stock.action.preview")),
};

/** Moves the panel to a year, as a person does with the year selector. */
async function inYear(context: PlayContext, year: string) {
  const t = wordsOf(context);
  await userEvent.selectOptions(
    await field(context, t("desktop.ledger.assets.year")),
    year,
  );
}

/** Presses an action on the row of the book a text names. */
async function rowAction(context: PlayContext, book: string, action: string) {
  const row = await waitFor(() => {
    const cell = within(context.canvasElement).queryByText(book);
    const found = cell?.closest("tr");
    if (!found) throw new Error(`${book} is not drawn yet`);
    return found;
  });
  await userEvent.click(await control(context, action, row));
}

const FIRST_BOOK = "Papelería y reprografía";
const RETIRED_BOOK = "Enmarcado (cerrado en 2025)";

export const DetailsForm: Story = {
  name: "Editing the details",
  play: (context) =>
    rowAction(
      context,
      FIRST_BOOK,
      wordsOf(context)("desktop.ledger.stock.action.describe"),
    ),
};

export const CorrectionForm: Story = {
  name: "Correcting the opening stock or the method",
  play: (context) =>
    rowAction(
      context,
      FIRST_BOOK,
      wordsOf(context)("desktop.ledger.stock.action.correct"),
    ),
};

export const RetireForm: Story = {
  name: "Retiring a stock book",
  play: (context) =>
    rowAction(
      context,
      FIRST_BOOK,
      wordsOf(context)("desktop.ledger.stock.action.retire"),
    ),
};

export const RestoreForm: Story = {
  name: "Restoring a retired stock book",
  play: async (context) => {
    await inYear(context, "2025");
    await rowAction(
      context,
      RETIRED_BOOK,
      wordsOf(context)("desktop.ledger.stock.action.restore"),
    );
  },
};

export const MovementCorrectionForm: Story = {
  name: "Correcting a movement",
  play: (context) =>
    press(
      context,
      wordsOf(context)("desktop.ledger.stock.action.movement_correct"),
    ),
};

export const MovementReversalForm: Story = {
  name: "Reversing a movement",
  play: (context) =>
    press(
      context,
      wordsOf(context)("desktop.ledger.stock.action.movement_reverse"),
    ),
};

export const RetiredBook: Story = {
  name: "A retired stock book, still listed",
  play: (context) => inYear(context, "2025"),
};

export const History: Story = {
  name: "The history of a stock book",
  play: (context) => inYear(context, "2025"),
};

/** Reverses the first movement of the 2025 book, whose closing value is saved. */
export const RefusedClosingSaved: Story = {
  name: "A change refused: a closing value is saved",
  play: async (context) => {
    const t = wordsOf(context);
    await inYear(context, "2025");
    await press(context, t("desktop.ledger.stock.action.movement_reverse"));
    await pick(context, t("desktop.ledger.stock.field.reason"), "keying_error");
    await press(context, t("desktop.ledger.stock.submit.reverse"));
  },
};

export const RefusedStockBelowZero: Story = {
  name: "A movement refused: more units out than in stock",
  play: async (context) => {
    const t = wordsOf(context);
    await rowAction(
      context,
      FIRST_BOOK,
      t("desktop.ledger.stock.action.add_movement"),
    );
    await userEvent.type(
      await field(context, t("desktop.ledger.inventory.date")),
      "2026-12-01",
    );
    await pick(context, t("desktop.ledger.inventory.kind_label"), "cogs");
    await userEvent.type(
      await field(context, t("desktop.ledger.inventory.quantity")),
      "500",
    );
    await press(context, t("desktop.ledger.stock.submit.movement"));
  },
};

export const RefusedNothingChanges: Story = {
  name: "A correction refused: it changes nothing",
  play: async (context) => {
    const t = wordsOf(context);
    await rowAction(
      context,
      FIRST_BOOK,
      t("desktop.ledger.stock.action.correct"),
    );
    await pick(context, t("desktop.ledger.stock.field.reason"), "keying_error");
    await userEvent.type(
      await field(context, t("desktop.ledger.stock.field.opening_new")),
      "410",
    );
    await press(context, t("desktop.ledger.stock.submit.correct"));
  },
};

export const RefusedRetiredBook: Story = {
  name: "A change refused: the book is retired",
  args: { sendRetiredChange: true },
};

export const SameChangeSentTwice: Story = {
  name: "The same change sent twice is one change",
  args: { replayProbe: true },
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

/** Presses the name of a book, to read it. */
async function readBook(context: PlayContext, book: string) {
  await userEvent.click(await control(context, book));
}

export const PurchaseWithFiles: Story = {
  name: "A purchase with its files chosen",
  play: async (context) => {
    const t = wordsOf(context);
    await press(context, t("desktop.ledger.stock.action.add_movement"));
    await pick(context, t("desktop.ledger.inventory.kind_label"), "purchase");
    const choose = t("desktop.ledger.stock.proof.choose_file");
    for (const slot of [
      "desktop.ledger.stock.proof.price",
      "desktop.ledger.stock.proof.cost_check",
      "desktop.ledger.stock.proof.iva_check",
    ])
      await userEvent.click(await control(context, `${t(slot)}: ${choose}`));
  },
};

export const PurchaseFacts: Story = {
  name: "What a purchase cost, as the book kept it",
  play: async (context) => {
    const t = wordsOf(context);
    await readBook(context, "Venta en línea de material de dibujo");
    await press(context, t("desktop.ledger.stock.action.purchase_facts"));
  },
};

export const PurchaseCorrection: Story = {
  name: "Correcting a purchase starts from what the book kept",
  play: async (context) => {
    const t = wordsOf(context);
    await readBook(context, "Venta en línea de material de dibujo");
    await press(context, t("desktop.ledger.stock.action.movement_correct"));
  },
};

export const ClosingForm: Story = {
  name: "Recording the closing value",
  play: (context) =>
    rowAction(
      context,
      FIRST_BOOK,
      wordsOf(context)("desktop.ledger.stock.action.closing"),
    ),
};

export const ClosingFromACount: Story = {
  name: "A closing value that rests on a count",
  play: async (context) => {
    const t = wordsOf(context);
    await rowAction(
      context,
      FIRST_BOOK,
      t("desktop.ledger.stock.action.closing"),
    );
    await pick(
      context,
      t("desktop.ledger.stock.closing.authority"),
      "physical_observation",
    );
  },
};

export const ClosingRecorded: Story = {
  name: "A book whose closing value is recorded",
  play: (context) => inYear(context, "2025"),
};

export const ClosingRefusedNeedsPriorDocument: Story = {
  name: "A closing value refused: last year has none",
  play: async (context) => {
    const t = wordsOf(context);
    await rowAction(
      context,
      "Venta en línea de material de dibujo",
      t("desktop.ledger.stock.action.closing"),
    );
    await pick(
      context,
      t("desktop.ledger.stock.closing.authority"),
      "movement_derived",
    );
    await userEvent.type(
      await field(context, t("desktop.ledger.stock.closing.reason")),
      "Counted by the movements",
    );
    await userEvent.click(
      await control(
        context,
        `${t("application.inventory.labels.decision_evidence_role.authority_reconciliation")}: ${t("desktop.ledger.stock.proof.choose_file")}`,
      ),
    );
    await press(context, t("desktop.ledger.stock.submit.closing"));
    // The sentence the backend's catalogue has for this refusal, not the plain one.
    await waitFor(() => {
      const said = t(
        "application.inventory.service.errors.prior_closing_document_needed",
      );
      if (!within(context.canvasElement).queryByText(said))
        throw new Error("the refusal's own sentence is not drawn");
    });
  },
};

export const RetiredBookWithEntries: Story = {
  name: "A retired book that still holds entries",
  play: async (context) => {
    await inYear(context, "2025");
    await readBook(context, RETIRED_BOOK);
  },
};

export const ChoicesRefused: Story = {
  name: "The choices of a form could not be loaded",
  args: { choices: "refused" },
  play: (context) =>
    press(
      context,
      wordsOf(context)("desktop.ledger.stock.action.add_movement"),
    ),
};

export const FileCannotBeKept: Story = {
  name: "A file the book cannot keep",
  args: { fileRefused: true },
  play: async (context) => {
    const t = wordsOf(context);
    await press(context, t("desktop.ledger.stock.action.add_movement"));
    await pick(context, t("desktop.ledger.inventory.kind_label"), "purchase");
    await userEvent.click(
      await control(
        context,
        `${t("desktop.ledger.stock.proof.price")}: ${t("desktop.ledger.stock.proof.choose_file")}`,
      ),
    );
  },
};
