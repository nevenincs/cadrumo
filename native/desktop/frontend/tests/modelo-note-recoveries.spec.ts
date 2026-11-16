import { expect, test } from "@playwright/test";
import type { CounterpartyAsk } from "../src/shell/counterpartyAsk";
import type { ModeloFormCalculationNote } from "../src/shell/modeloContract/modeloWorkForm";
import { refusalControls } from "../src/shell/refusal";
import { routeAction } from "../src/shell/refusalRoute";
import {
  noteRecoveryRoute,
  notesWithRecovery,
} from "../src/components/modelo/workspace/noteRecoveryRoute";
import { markupOf } from "./support/markup";

// The way out a calculation note serves: the note's served sentence, then
// the served action in its served words, routed by its served operations
// through the window's one refusal notice. A note that serves none draws no
// door. Synthetic words and ids stand in for what the backend serves.

type Recovery = NonNullable<ModeloFormCalculationNote["recovery"]>;

const SENTENCE = "Synthetic: an invoice has no operation type.";
const PLAIN = "Synthetic: a note that opens nothing.";
const DOOR = "Synthetic: state the operation type";
const INVOICE = "inv-synthetic-1";

const invoiceDoor: Recovery = {
  failed_condition_id: "synthetic.note.stated",
  evidence: [],
  action_id: "synthetic.note.door",
  argument_bindings: [
    {
      argument_name: "invoice_id",
      status: "resolved",
      value: INVOICE,
      source: "operator_action.verdict_context",
      source_key: "invoice_id",
      source_evidence_id: null,
    },
  ],
  missing_argument_names: [],
  conditionality: "immediate",
  no_recovery_outcome: null,
  no_recovery_words: null,
  no_recovery_words_language: null,
  action_words: DOOR,
  action_words_language: null,
  target_operation_ids: ["ledger.invoice.update"],
  alternative_actions: [],
};

const note = (
  reason: string,
  message: string,
  recovery: Recovery | null | undefined,
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
  message,
  ...(recovery === undefined ? {} : { recovery }),
});

type Props = {
  notes: readonly ModeloFormCalculationNote[];
  onOpenInvoice: ((invoiceId: string) => void) | null;
  onOpenCounterparty?: ((ask: CounterpartyAsk) => void) | null;
};
const draw = () =>
  markupOf<Props>(
    "components/modelo/workspace/NoteRecoveries.tsx",
    "NoteRecoveries",
  );

test("a note that serves no way out draws no door, whether it serves null or leaves it out", async () => {
  const render = await draw();
  for (const recovery of [null, undefined]) {
    const plain = note("synthetic_plain_note", PLAIN, recovery);
    expect(notesWithRecovery([plain])).toHaveLength(0);
    const markup = render({ notes: [plain], onOpenInvoice: () => {} });
    expect(markup).toBe("");
  }
});

test("a note's served way out draws its served words and opens the invoice it names", async () => {
  const door = note("synthetic_invoice_note", SENTENCE, invoiceDoor);
  const plain = note("synthetic_plain_note", PLAIN, null);
  const markup = (await draw())({
    notes: [plain, door],
    onOpenInvoice: () => {},
  });
  expect(markup).toContain('data-note-recovery="synthetic_invoice_note"');
  expect(markup).not.toContain('data-note-recovery="synthetic_plain_note"');
  expect(markup).not.toContain(PLAIN);
  expect(markup).toContain(SENTENCE);
  expect(markup).toContain(DOOR);
  expect(markup).toContain('data-target-operation="ledger.invoice.update"');
  expect(markup).not.toContain('aria-disabled="true"');

  // The control the notice draws hands its intent to the note's routing,
  // which opens the invoice the served way out bound.
  const opened: string[] = [];
  const route = noteRecoveryRoute({
    onOpenInvoice: (id) => opened.push(id),
    onOpenCounterparty: null,
  });
  const [control] = refusalControls(invoiceDoor, routeAction);
  if (!control?.intent) throw new Error("the served way out routed nowhere");
  expect(control.words).toBe(DOOR);
  expect(route.opens(control.intent.place)).toBe(true);
  route.follow(control.intent);
  expect(opened).toEqual([INVOICE]);
});

test("a way out this window cannot open is drawn disabled and opens nothing", async () => {
  const door = note("synthetic_invoice_note", SENTENCE, invoiceDoor);
  const markup = (await draw())({ notes: [door], onOpenInvoice: null });
  expect(markup).toContain(DOOR);
  expect(markup).toContain('aria-disabled="true"');
  const route = noteRecoveryRoute({
    onOpenInvoice: null,
    onOpenCounterparty: null,
  });
  const [control] = refusalControls(invoiceDoor, routeAction);
  if (!control?.intent) throw new Error("the served way out routed nowhere");
  expect(route.opens(control.intent.place)).toBe(false);
});
