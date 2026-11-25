import type { ModeloFormCalculationNote } from "../../../shell/modeloContract/modeloWorkForm";
import {
  counterpartyAsk,
  type CounterpartyAsk,
} from "../../../shell/counterpartyAsk";
import type { RefusalIntent, WindowPlace } from "../../../shell/refusal";

/** The place the invoice update opens in this window: the invoice the note
 * names, in the Libro de facturas. */
const INVOICE_UPDATE = "ledger.invoice.update";
/** The place the counterparty operation opens in this window: Rules ›
 * Counterparties in the Libro, on what the way out bound. */
const COUNTERPARTY = "ledger.counterparty";

/** The notes that serve a way out. The wire leaves an unserved way out out
 * altogether, so an absent one is none, as a null one is. */
export const notesWithRecovery = (
  notes: readonly ModeloFormCalculationNote[],
): ModeloFormCalculationNote[] =>
  notes.filter((note) => (note.recovery ?? null) !== null);

/** What this window opens for a note's way out, and how it follows one. The
 * door to an invoice is live only while `onOpenInvoice` is given, and the door
 * to a counterparty's statements only while `onOpenCounterparty` is. */
export function noteRecoveryRoute({
  onOpenInvoice,
  onOpenCounterparty,
}: {
  onOpenInvoice: ((invoiceId: string) => void) | null;
  onOpenCounterparty: ((ask: CounterpartyAsk) => void) | null;
}): {
  opens: (place: WindowPlace) => boolean;
  follow: (intent: RefusalIntent) => void;
} {
  const opens = (place: WindowPlace) =>
    place.page === "ledger" &&
    ((onOpenInvoice !== null && place.definition === INVOICE_UPDATE) ||
      (onOpenCounterparty !== null && place.definition === COUNTERPARTY));
  const follow = (intent: RefusalIntent) => {
    if (intent.place.definition === COUNTERPARTY) {
      onOpenCounterparty?.(counterpartyAsk(intent.bindings));
      return;
    }
    const invoice = intent.bindings.find(
      (binding) =>
        binding.argument_name === "invoice_id" &&
        typeof binding.value === "string",
    )?.value;
    if (onOpenInvoice && typeof invoice === "string") onOpenInvoice(invoice);
  };
  return { opens, follow };
}
