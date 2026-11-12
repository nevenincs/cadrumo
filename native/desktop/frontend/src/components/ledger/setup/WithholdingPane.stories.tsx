import type { Meta, StoryObj } from "@storybook/react-vite";
import { expect, userEvent, waitFor, within } from "storybook/test";
import served from "@fixtures/desktop-withholding-refusal-words/ledgerWithholdingRefusalWords.json" with { type: "json" };
import type { LedgerShape } from "@/dev/ledgerFixture";
import {
  STORY_PERIOD,
  STORY_READER,
  useLedgerPort,
  useLedgerRead,
  useStoryStage,
} from "@/dev/LedgerStage";
import { translator } from "../../../shell/strings";
import { LedgerSuggestions } from "../suggestions/SuggestionsProvider";
import { usePagePause, WritePauseContext } from "../WritePause";
import { WithholdingPane } from "./WithholdingPane";

// The withholding register of Setup › Registers over the scenario's ledger:
// the payers' certificates by income class, a year with none, the statements
// that a class had no withholding with the withdrawn ones kept as history, a
// certificate file picked and kept, and the refusals of both operations said
// in the sentences the backend served for them, with the one that kept the
// file. The pane holds no words of its own for a refusal. The scenario's
// payer and tax ID are made up.

type Args = { locale: string; shape?: LedgerShape };

/** The page's own reads, held as the page holds them, for the register. */
function Register({ locale, shape }: Args) {
  const port = useLedgerPort(shape, true, locale);
  const read = useLedgerRead(port, STORY_PERIOD);
  const { stage, onStage } = useStoryStage();
  const pause = usePagePause({
    reader: STORY_READER,
    afterReread: read.reread,
  });
  return (
    <WritePauseContext.Provider value={pause}>
      <LedgerSuggestions
        port={port}
        reader={STORY_READER}
        rows={read.rows}
        stage={stage.content}
        applied={stage.applied}
        locale={locale}
      >
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
      </LedgerSuggestions>
    </WritePauseContext.Provider>
  );
}

const meta: Meta<Args> = {
  title: "Ledger/Setup/Withholding",
  render: (args, { globals }) => (
    <Register {...args} locale={String(globals.locale ?? "en")} />
  ),
  args: { locale: "en" },
  argTypes: {
    locale: { table: { disable: true } },
    shape: { table: { disable: true } },
  },
  parameters: { fill: true, layout: "fullscreen" },
};
export default meta;
type Story = StoryObj<Args>;

const words = translator("en");
const word = (key: string) => words(key);

/** The words of a certificate figure, as the ledger serves their key. */
const figureWord = (field: string) =>
  word(
    `application.ledger.entry_options.withholding_certificate_figure.${field}`,
  );

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

/** A certificate the register refused for passing on more than it was paid,
 * said in the sentence the backend served. */
export const RefusedInServedWords: Story = {
  name: "Refusal in the served words",
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
      "B00000281",
    );
    const onAccount = await inside.findByLabelText(
      figureWord("ingreso_a_cuenta"),
    );
    await userEvent.clear(onAccount);
    await userEvent.type(onAccount, "20");
    for (const field of ["reducciones_aplicables", "gastos_deducibles"])
      await userEvent.type(inside.getByLabelText(figureWord(field)), "0");
    const passedOn = inside.getByLabelText(
      figureWord("ingreso_a_cuenta_repercutido"),
    );
    await userEvent.clear(passedOn);
    await userEvent.type(passedOn, "30");
    await userEvent.selectOptions(origin!, "operator_declaration");
    await userEvent.click(
      inside.getByRole("button", {
        name: word("desktop.ledger.withholding.action.record"),
      }),
    );
    await waitFor(() =>
      within(canvasElement).getByText(
        served.record.repercutido_exceeds_ingreso_a_cuenta.en.refusal_words,
      ),
    );
  },
};

/** A statement for a class that has certificates, said in the sentence the
 * backend served for the absence operation. */
export const AttestationRefusedRecordsPresent: Story = {
  name: "Statement refused: certificates recorded",
  play: async ({ canvasElement }) => {
    await openForm(canvasElement, "attest");
    const form = canvasElement.querySelector<HTMLElement>(
      ".ledger-withholding-form",
    )!;
    const inside = within(form);
    const [choose] = inside.getAllByRole("combobox");
    await userEvent.selectOptions(choose!, "trabajo");
    await userEvent.type(
      inside.getByLabelText(word("desktop.ledger.withholding.note")),
      "None.",
    );
    await userEvent.click(
      inside.getByRole("button", {
        name: word("desktop.ledger.withholding.action.attest"),
      }),
    );
    await waitFor(() =>
      within(canvasElement).getByText(
        served.absence.records_present.en.refusal_words,
      ),
    );
  },
};

/** A statement for a class already stated, said in the sentence the backend
 * served for the absence operation. */
export const AttestationRefusedAlreadyStated: Story = {
  name: "Statement refused: already stated",
  play: async ({ canvasElement }) => {
    await openForm(canvasElement, "attest");
    const form = canvasElement.querySelector<HTMLElement>(
      ".ledger-withholding-form",
    )!;
    const inside = within(form);
    const [choose] = inside.getAllByRole("combobox");
    await userEvent.selectOptions(choose!, "actividad_economica");
    await userEvent.type(
      inside.getByLabelText(word("desktop.ledger.withholding.note")),
      "Again.",
    );
    await userEvent.click(
      inside.getByRole("button", {
        name: word("desktop.ledger.withholding.action.attest"),
      }),
    );
    await waitFor(() =>
      within(canvasElement).getByText(
        served.absence.already_attested.en.refusal_words,
      ),
    );
  },
};

/** Opens the record form with a class chosen and returns the form. */
const chooseClass = async (canvasElement: HTMLElement, incomeClass: string) => {
  await openForm(canvasElement, "record");
  const inside = within(
    canvasElement.querySelector<HTMLElement>(".ledger-withholding-form")!,
  );
  const [choose] = inside.getAllByRole("combobox");
  await userEvent.selectOptions(choose!, incomeClass);
  return inside;
};

/** The labels of the money boxes the form draws, in order. */
const figureLabels = (form: HTMLElement) =>
  [...form.querySelectorAll<HTMLElement>("label")]
    .map((label) => label.textContent ?? "")
    .filter((text) =>
      [
        "importe_integro_dinerario",
        "valoracion_especie",
        "retencion",
        "ingreso_a_cuenta",
        "ingreso_a_cuenta_repercutido",
        "reducciones_aplicables",
        "gastos_deducibles",
      ].some((field) => text.startsWith(figureWord(field))),
    );

/** A work-income certificate: the five payment figures and the two it alone
 * states, as the ledger serves them for the class, in the served words. */
export const TrabajoFigures: Story = {
  name: "Work-income figures",
  play: async ({ canvasElement }) => {
    const inside = await chooseClass(canvasElement, "trabajo");
    for (const field of [
      "importe_integro_dinerario",
      "retencion",
      "reducciones_aplicables",
      "gastos_deducibles",
    ])
      await expect(
        await inside.findByLabelText(figureWord(field)),
      ).toBeVisible();
    await expect(
      figureLabels(
        canvasElement.querySelector<HTMLElement>(".ledger-withholding-form")!,
      ),
    ).toHaveLength(7);
    // The two only work-income certificates state start blank.
    await expect(
      inside.getByLabelText(figureWord("gastos_deducibles")),
    ).toHaveValue("");
  },
};

/** Another class's certificate: the payment figures alone. */
export const OtherClassFigures: Story = {
  name: "Another class's figures",
  play: async ({ canvasElement }) => {
    const inside = await chooseClass(canvasElement, "capital_mobiliario");
    await expect(
      await inside.findByLabelText(figureWord("retencion")),
    ).toBeVisible();
    await expect(
      inside.queryByLabelText(figureWord("reducciones_aplicables")),
    ).toBeNull();
    await expect(
      figureLabels(
        canvasElement.querySelector<HTMLElement>(".ledger-withholding-form")!,
      ),
    ).toHaveLength(5);
  },
};

/** A work-income certificate sent without the two figures only it states:
 * refused in the sentence the backend served. */
export const TrabajoFiguresMissing: Story = {
  name: "Work-income figures missing",
  play: async ({ canvasElement }) => {
    const inside = await chooseClass(canvasElement, "trabajo");
    const [, origin] = inside.getAllByRole("combobox");
    await userEvent.type(
      inside.getByLabelText(word("desktop.ledger.withholding.payer_tax_id")),
      "B00000281",
    );
    await userEvent.selectOptions(origin!, "operator_declaration");
    await userEvent.click(
      inside.getByRole("button", {
        name: word("desktop.ledger.withholding.action.record"),
      }),
    );
    await waitFor(() =>
      within(canvasElement).getByText(
        served.record.trabajo_certificate_figure_missing.en.refusal_words,
      ),
    );
  },
};

/** Starts a payer certificate: a class, a payer and the payer-certificate
 * source, with the figures left at zero. */
const startCertificate = async (canvasElement: HTMLElement) => {
  await openForm(canvasElement, "record");
  const form = canvasElement.querySelector<HTMLElement>(
    ".ledger-withholding-form",
  )!;
  const inside = within(form);
  const [incomeClass, origin] = inside.getAllByRole("combobox");
  await userEvent.selectOptions(incomeClass!, "capital_mobiliario");
  await userEvent.type(
    inside.getByLabelText(word("desktop.ledger.withholding.payer_tax_id")),
    "B00000281",
  );
  await userEvent.type(
    inside.getByLabelText(word("desktop.ledger.withholding.payer_legal_name")),
    "Banco de Ejemplo SA",
  );
  await userEvent.selectOptions(origin!, "payer_certificate");
  return inside;
};

/** Chooses the certificate file in the made-up computer's dialog. */
const chooseFile = async (inside: ReturnType<typeof within>) => {
  await userEvent.click(
    inside.getByRole("button", {
      name: `${word("desktop.ledger.withholding.file")}: ${word("desktop.ledger.withholding.file_choose")}`,
    }),
  );
  await waitFor(() => inside.getByText("ticket-gasolinera-ruta7.jpg"));
};

const sendCertificate = (inside: ReturnType<typeof within>) =>
  userEvent.click(
    inside.getByRole("button", {
      name: word("desktop.ledger.withholding.action.record"),
    }),
  );

/** The certificate file chosen with the system dialog, shown by its name. */
export const CertificateFilePicked: Story = {
  name: "Certificate file picked",
  play: async ({ canvasElement }) => {
    const inside = await startCertificate(canvasElement);
    await chooseFile(inside);
    await expect(
      inside.getByRole("button", {
        name: `${word("desktop.ledger.withholding.file")}: ${word("desktop.ledger.withholding.file_change")}`,
      }),
    ).toBeVisible();
  },
};

/** The picked file recorded: the register lists the fingerprint the backend
 * answered for the bytes it kept. */
export const CertificateFileRecorded: Story = {
  name: "Certificate file recorded",
  play: async ({ canvasElement }) => {
    const inside = await startCertificate(canvasElement);
    await chooseFile(inside);
    await sendCertificate(inside);
    await waitFor(() => within(canvasElement).getByText("Banco de Ejemplo SA"));
  },
};

/** A file that could not be read: the pane shows the sentence the backend
 * served and the file stays chosen. */
export const CertificateFileUnreadable: Story = {
  name: "Certificate file unreadable",
  play: async ({ canvasElement }) => {
    window.__scenarioWithholding!.nextRecords(["unreadable"]);
    const inside = await startCertificate(canvasElement);
    await chooseFile(inside);
    await sendCertificate(inside);
    await waitFor(() =>
      within(canvasElement).getByText(
        served.record.certificate_file_unreadable.en.refusal_words,
      ),
    );
  },
};

/** A stored document custody does not hold, said in the served words. */
export const CertificateNotInCustody: Story = {
  name: "Certificate not in custody",
  args: { shape: "documents" },
  play: async ({ canvasElement }) => {
    const inside = await startCertificate(canvasElement);
    const stored = inside.getByLabelText(
      word("desktop.ledger.withholding.document"),
    );
    await waitFor(() => {
      if (stored.querySelectorAll("option").length < 2)
        throw new Error("the stored documents are not listed yet");
    });
    await userEvent.selectOptions(
      stored,
      stored.querySelectorAll("option")[1]!.value,
    );
    await sendCertificate(inside);
    await waitFor(() =>
      within(canvasElement).getByText(
        served.record.certificate_not_in_custody.en.refusal_words,
      ),
    );
  },
};

/** A stored document beside a file that is not that document, said in the
 * served words. */
export const CertificateFingerprintMismatch: Story = {
  name: "Certificate does not match its fingerprint",
  args: { shape: "documents" },
  play: async ({ canvasElement }) => {
    const inside = await startCertificate(canvasElement);
    const stored = inside.getByLabelText(
      word("desktop.ledger.withholding.document"),
    );
    await waitFor(() => {
      if (stored.querySelectorAll("option").length < 2)
        throw new Error("the stored documents are not listed yet");
    });
    await userEvent.selectOptions(
      stored,
      stored.querySelectorAll("option")[1]!.value,
    );
    await chooseFile(inside);
    await sendCertificate(inside);
    await waitFor(() =>
      within(canvasElement).getByText(
        served.record.certificate_fingerprint_mismatch.en.refusal_words,
      ),
    );
  },
};

/** A refusal after the file was kept: partial, which is known, and not the
 * unknown outcome that asks to be refreshed. */
export const CertificateKeptInPart: Story = {
  name: "Refused after the file was kept",
  play: async ({ canvasElement }) => {
    window.__scenarioWithholding!.nextRecords(["kept_in_part"]);
    const inside = await startCertificate(canvasElement);
    await chooseFile(inside);
    await sendCertificate(inside);
    await waitFor(() =>
      within(canvasElement).getByText(word("desktop.ledger.form.partial")),
    );
    await expect(
      within(canvasElement).queryByText(word("desktop.ledger.form.unknown")),
    ).toBeNull();
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
