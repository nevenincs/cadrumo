import type { Meta, StoryObj } from "@storybook/react-vite";
import { expect, userEvent, waitFor, within } from "storybook/test";
import {
  STORY_PERIOD,
  STORY_READER,
  useLedgerPort,
  useLedgerRead,
  useStoryStage,
} from "@/dev/LedgerStage";
import { translator } from "../../../shell/strings";
import { usePagePause, WritePauseContext } from "../WritePause";
import { WithholdingPane } from "./WithholdingPane";

// The withholding register of Setup › Registers over the scenario's ledger:
// the payers' certificates by income class, a year with none, the statements
// that a class had no withholding with the withdrawn ones kept as history, and
// a refusal said in the words the backend served for it. The scenario's payer
// and tax ID are made up.

type Args = { locale: string };

/** The page's own reads, held as the page holds them, for the register. */
function Register({ locale }: Args) {
  const port = useLedgerPort();
  const read = useLedgerRead(port, STORY_PERIOD);
  const { stage, onStage } = useStoryStage();
  const pause = usePagePause({
    reader: STORY_READER,
    afterReread: read.reread,
  });
  return (
    <WritePauseContext.Provider value={pause}>
      <div className="flex h-full min-h-0 flex-col overflow-y-auto">
        <WithholdingPane
          port={port}
          reader={STORY_READER}
          locale={locale}
          rows={read.rows}
          stage={stage.content}
          onStage={onStage}
          years={read.years}
          fallbackYear={STORY_PERIOD.year}
          period={STORY_PERIOD}
        />
      </div>
    </WritePauseContext.Provider>
  );
}

const meta: Meta<Args> = {
  title: "Ledger/Setup/Withholding",
  render: (args, { globals }) => (
    <Register {...args} locale={String(globals.locale ?? "en")} />
  ),
  args: { locale: "en" },
  argTypes: { locale: { table: { disable: true } } },
  parameters: { fill: true, layout: "fullscreen" },
};
export default meta;
type Story = StoryObj<Args>;

const words = translator("en");
const word = (key: string) => words(key);

/** The register's controls are found by the words they carry. */
const control = async (canvasElement: HTMLElement) => {
  const canvas = within(canvasElement);
  await waitFor(() => {
    if (
      !canvasElement.querySelector(
        ".ledger-withholding-class, .ledger-withholding-empty",
      )
    )
      throw new Error("the register is not drawn yet");
  });
  return canvas;
};

const openForm = async (
  canvasElement: HTMLElement,
  action: "record" | "attest",
) => {
  const canvas = await control(canvasElement);
  await userEvent.click(
    canvas.getByRole("button", {
      name: word(`desktop.ledger.withholding.action.${action}`),
    }),
  );
  return canvas;
};

/** A payer's certificate listed under its income class. */
export const WithCertificates: Story = {
  name: "Certificates by income class",
  play: ({ canvasElement }) => control(canvasElement).then(() => undefined),
};

/** A year with no certificate recorded. */
export const Empty: Story = {
  name: "A year with none",
  play: async ({ canvasElement }) => {
    const canvas = await control(canvasElement);
    await userEvent.click(
      canvas.getByRole("button", {
        name: word("desktop.ledger.period.year_previous"),
      }),
    );
  },
};

/** An income class stated to have no withholding, shown as the backend
 * returned it, with its withdrawal offered. */
export const AttestedAbsence: Story = {
  name: "No withholding stated",
  play: async ({ canvasElement }) => {
    const canvas = await openForm(canvasElement, "attest");
    const form = canvasElement.querySelector<HTMLElement>(
      ".ledger-withholding-form",
    )!;
    const inside = within(form);
    const [choose] = inside.getAllByRole("combobox");
    await userEvent.selectOptions(choose!, "ganancia_patrimonial");
    await userEvent.type(
      inside.getByLabelText(word("desktop.ledger.withholding.note")),
      "No sales this year.",
    );
    await userEvent.click(
      inside.getByRole("button", {
        name: word("desktop.ledger.withholding.action.attest"),
      }),
    );
    await waitFor(() => canvas.getByText("No sales this year."));
  },
};

/** The statements listed for the year: an active one with its withdrawal
 * offered, and a withdrawn one kept below as history with none. */
export const AttestationsListed: Story = {
  name: "Attestations listed",
  play: async ({ canvasElement }) => {
    await control(canvasElement);
    await waitFor(() => {
      if (!canvasElement.querySelector(".ledger-withholding-withdrawn"))
        throw new Error("the statements are not listed yet");
    });
    const active = within(
      canvasElement.querySelector<HTMLElement>(".ledger-withholding-attested")!,
    );
    const history = within(
      canvasElement.querySelector<HTMLElement>(".ledger-withholding-history")!,
    );
    await expect(
      active.getByText("No professional fees were withheld."),
    ).toBeVisible();
    await expect(
      active.getByRole("button", {
        name: words("desktop.ledger.withholding.withdraw_of", {
          class: "Economic activity income",
        }),
      }),
    ).toBeVisible();
    const withdrawn = history.getByText("No dividends were paid.");
    await expect(withdrawn).toBeVisible();
    await expect(
      within(withdrawn.closest("tr")!).queryByRole("button"),
    ).toBeNull();
  },
};

/** A certificate the register refused, said in the words it served. */
export const RefusedWithServedWords: Story = {
  name: "Refusal in the backend's words",
  play: async ({ canvasElement }) => {
    await openForm(canvasElement, "record");
    const form = canvasElement.querySelector<HTMLElement>(
      ".ledger-withholding-form",
    )!;
    const inside = within(form);
    const [incomeClass, origin] = inside.getAllByRole("combobox");
    await userEvent.selectOptions(incomeClass!, "trabajo");
    await userEvent.type(
      inside.getByLabelText(word("desktop.ledger.withholding.payer_tax_id")),
      "A58818501",
    );
    const onAccount = inside.getByLabelText(
      word("desktop.ledger.withholding.amount.ingreso_a_cuenta"),
    );
    await userEvent.clear(onAccount);
    await userEvent.type(onAccount, "20");
    const passedOn = inside.getByLabelText(
      word("desktop.ledger.withholding.amount.ingreso_a_cuenta_repercutido"),
    );
    await userEvent.clear(passedOn);
    await userEvent.type(passedOn, "30");
    await userEvent.selectOptions(origin!, "operator_declaration");
    await userEvent.click(
      inside.getByRole("button", {
        name: word("desktop.ledger.withholding.action.record"),
      }),
    );
  },
};

/** Removing a certificate asks first. */
export const RemoveAsked: Story = {
  name: "Removing a certificate",
  play: async ({ canvasElement }) => {
    const canvas = await control(canvasElement);
    await userEvent.click(
      canvas.getAllByRole("button", {
        name: words("desktop.ledger.withholding.remove_of", {
          payer: "Empresa Ejemplo SL",
        }),
      })[0]!,
    );
  },
};
