import type { ModeloFormCalculationNote } from "../../../shell/modeloContract/modeloWorkForm";
import {
  counterpartyAsk,
  type CounterpartyAsk,
} from "../../../shell/counterpartyAsk";
import type { RefusalIntent, WindowPlace } from "../../../shell/refusal";
import { RefusalNotice } from "../../RefusalNotice";
import { BoxNumber } from "../form/BoxNumber";

/** The place the invoice update opens in this window: the invoice the note
 * names, in the Libro de facturas. */
const INVOICE_UPDATE = "ledger.invoice.update";
/** The place the counterparty operation opens in this window: Rules ›
 * Counterparties in the Libro, on what the way out bound. */
const COUNTERPARTY = "ledger.counterparty";

/**
 * The way out a calculation note opens, as the application serves it: the
 * note's own sentence, then the served action by its served words, routed by
 * its served operations through the window's one refusal notice. A note that
 * opens no way out serves none and is not drawn here; the check lists it.
 * The door to an invoice is live only while this window can open an invoice,
 * and the door to a counterparty's statements only while it can open them;
 * any other door is shown disabled with the generic reason.
 */
export function NoteRecoveries({
  notes,
  onOpenInvoice,
  onOpenCounterparty = null,
}: {
  notes: readonly ModeloFormCalculationNote[];
  onOpenInvoice: ((invoiceId: string) => void) | null;
  /** Opens the counterparty journey on what the way out bound. */
  onOpenCounterparty?: ((ask: CounterpartyAsk) => void) | null;
}) {
  const doors = notes.filter((note) => note.recovery !== null);
  if (doors.length === 0) return null;
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
  return (
    <ul data-note-recoveries className="flex flex-col gap-2">
      {doors.map((note, index) => (
        <li
          key={`${note.reason}-${index}`}
          data-note-recovery={note.reason}
          className="flex items-start gap-3"
        >
          <BoxNumber box={note.box} />
          <div className="min-w-0 flex-1">
            <RefusalNotice
              refusal={{
                refusal_words: note.message,
                verdict: note.recovery,
              }}
              onAction={follow}
              opens={opens}
            />
          </div>
        </li>
      ))}
    </ul>
  );
}
