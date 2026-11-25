import type { Meta, StoryObj } from "@storybook/react-vite";
import { expect, fn, userEvent, within } from "storybook/test";
import type { ModeloFormCalculationNote } from "../../../shell/modeloContract/modeloWorkForm";
import { NoteRecoveries } from "./NoteRecoveries";

// The way out a calculation note serves, drawn by the window's refusal
// notice: the note's served sentence, then the served action in its served
// words, routed by its served operations. Synthetic placeholder words and ids
// stand in for what the backend serves.

const SENTENCE = "Synthetic: an invoice has no operation type.";
const DOOR = "Synthetic: state the operation type";
const OTHER_DOOR = "Synthetic: state the party";

const verdict = (
  words: string,
  target: string,
  bindings: NonNullable<
    ModeloFormCalculationNote["recovery"]
  >["argument_bindings"],
): NonNullable<ModeloFormCalculationNote["recovery"]> => ({
  no_recovery_words: null,
  no_recovery_words_language: null,
  action_words: words,
  action_words_language: null,
  target_operation_ids: [target],
  failed_condition_id: "synthetic.note.stated",
  evidence: [],
  action_id: "synthetic.note.door",
  argument_bindings: bindings,
  missing_argument_names: ["operation_type"],
  conditionality: "requires_arguments",
  no_recovery_outcome: null,
  alternative_actions: [],
});

const note = (
  reason: string,
  recovery: ModeloFormCalculationNote["recovery"],
): ModeloFormCalculationNote => ({
  reason,
  attention: "missing",
  casilla_id: null,
  box: "12",
  withholds_filing: false,
  finding_id: null,
  resolution_answer: null,
  fact: null,
  element_names: [],
  message: SENTENCE,
  recovery,
});

const INVOICE_DOOR = note(
  "synthetic_invoice_note",
  verdict(DOOR, "ledger.invoice.update", [
    {
      argument_name: "invoice_id",
      status: "resolved",
      value: "inv-synthetic-1",
      source: "operator_action.verdict_context",
      source_key: "invoice_id",
      source_evidence_id: null,
    },
    {
      argument_name: "operation_type",
      status: "missing",
      value: null,
      source: null,
      source_key: null,
      source_evidence_id: null,
    },
  ]),
);
const FOREIGN_DOOR = note(
  "synthetic_party_note",
  verdict(OTHER_DOOR, "ledger.counterparty.filing-name", []),
);
const NO_DOOR = note("synthetic_plain_note", null);
const PARTY_WORDS = "Synthetic: state the party's filing name";
const missing = (argument_name: string) => ({
  argument_name,
  status: "missing" as const,
  value: null,
  source: null,
  source_key: null,
  source_evidence_id: null,
});
const PARTY_DOOR = note("synthetic_party_name_note", {
  ...verdict(PARTY_WORDS, "ledger.counterparty", [
    missing("tax_identifier"),
    missing("country_code"),
    missing("kind"),
  ]),
  missing_argument_names: ["tax_identifier", "country_code", "kind"],
});

const opened = fn();
const counterparty = fn();

const meta: Meta = {
  title: "Modelo/Note ways out",
  decorators: [
    (Story) => (
      <div className="flex max-w-3xl flex-col gap-3 p-6">
        <Story />
      </div>
    ),
  ],
};
export default meta;
type Story = StoryObj;

export const InvoiceDoor: Story = {
  name: "Check · a note's served way out opens the invoice it names",
  render: () => (
    <NoteRecoveries
      notes={[INVOICE_DOOR, NO_DOOR, FOREIGN_DOOR]}
      onOpenInvoice={opened}
    />
  ),
  play: async ({ canvasElement }) => {
    opened.mockClear();
    const page = within(canvasElement);
    // Only the notes that serve a way out are drawn, each with its sentence.
    await expect(
      canvasElement.querySelectorAll("[data-note-recovery]"),
    ).toHaveLength(2);
    await expect(page.getAllByText(SENTENCE)).toHaveLength(2);
    // The served action opens the invoice its binding names.
    await userEvent.click(page.getByRole("button", { name: DOOR }));
    await expect(opened).toHaveBeenCalledWith("inv-synthetic-1");
    // A door this window does not host is shown, disabled, and opens nothing.
    const other = page.getByRole("button", { name: OTHER_DOOR });
    await expect(other.getAttribute("aria-disabled")).toBe("true");
    await userEvent.click(other);
    await expect(opened).toHaveBeenCalledTimes(1);
  },
};

export const CounterpartyDoor: Story = {
  name: "Check · a party-name note opens the counterparty's statements",
  render: () => (
    <NoteRecoveries
      notes={[PARTY_DOOR]}
      onOpenInvoice={null}
      onOpenCounterparty={counterparty}
    />
  ),
  play: async ({ canvasElement }) => {
    counterparty.mockClear();
    const door = within(canvasElement).getByRole("button", {
      name: PARTY_WORDS,
    });
    await expect(door.getAttribute("aria-disabled")).toBeNull();
    await expect(door.dataset.targetOperation).toBe("ledger.counterparty");
    await userEvent.click(door);
    // The way out bound no argument, so the journey opens empty.
    await expect(counterparty).toHaveBeenCalledWith({
      tax_identifier: null,
      country_code: null,
      kind: null,
    });
  },
};

export const CounterpartyDoorUnhosted: Story = {
  name: "Check · without a Libro the party-name door is disabled",
  render: () => <NoteRecoveries notes={[PARTY_DOOR]} onOpenInvoice={null} />,
  play: async ({ canvasElement }) => {
    const door = within(canvasElement).getByRole("button", {
      name: PARTY_WORDS,
    });
    await expect(door.getAttribute("aria-disabled")).toBe("true");
  },
};

export const NoDoors: Story = {
  name: "Check · a note without a way out draws nothing here",
  render: () => <NoteRecoveries notes={[NO_DOOR]} onOpenInvoice={null} />,
  play: async ({ canvasElement }) => {
    await expect(
      canvasElement.querySelector("[data-note-recoveries]"),
    ).toBeNull();
  },
};
