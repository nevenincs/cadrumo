import type { ModeloFormCalculationNote } from "../../../shell/modeloContract/modeloWorkForm";
import type { CounterpartyAsk } from "../../../shell/counterpartyAsk";
import { RefusalNotice } from "../../RefusalNotice";
import { BoxNumber } from "../form/BoxNumber";
import { noteRecoveryRoute, notesWithRecovery } from "./noteRecoveryRoute";

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
  const doors = notesWithRecovery(notes);
  if (doors.length === 0) return null;
  const { opens, follow } = noteRecoveryRoute({
    onOpenInvoice,
    onOpenCounterparty,
  });
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
                verdict: note.recovery ?? null,
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
