import type { ReactNode } from "react";
import type {
  LedgerPort,
  LedgerRequest,
  LedgerResult,
} from "../../../shell/ledger";
import { useStrings } from "../../../shell/strings";
import {
  CallLine,
  Panel,
  readLanding,
  useSetupDraft,
  useSetupWrite,
} from "../setup/SetupParts";
import { setupCall, type SetupCall } from "../setup/setupModel";
import { FormButtons } from "./StockFormParts";
import { changeLanded } from "./stockModel";
import type { BookKey } from "./stockReads";
import { refusalOf, refusalWords } from "./stockWords";

type ChangeId =
  | "ledger.inventory.describe"
  | "ledger.inventory.correct"
  | "ledger.inventory.movement.correct"
  | "ledger.inventory.movement.reverse"
  | "ledger.inventory.movement.claim"
  | "ledger.inventory.retire"
  | "ledger.inventory.restore";

/**
 * The form of a change to a book. The change carries the reference its form
 * minted when it opened, so a change sent again is the same change. A write
 * not seen to settle holds the page's writes and is judged on the history of
 * the book read again, never sent a second time.
 */
export function StockChangeForm<D extends ChangeId>({
  port,
  definition,
  book,
  correction,
  request,
  touched,
  title,
  submit,
  className,
  onTry,
  onClose,
  onWritten,
  children,
}: {
  port: LedgerPort;
  definition: D;
  book: BookKey;
  correction: string;
  request: LedgerRequest<D> | null;
  touched: boolean;
  title: string;
  submit: string;
  className: string;
  onTry(): void;
  onClose(): void;
  onWritten(): void;
  children: ReactNode;
}) {
  const t = useStrings();
  const write = useSetupWrite(title);
  useSetupDraft(touched);
  const send = async () => {
    if (write.busy) return;
    if (request === null) {
      onTry();
      return;
    }
    const done = await write.run(
      () =>
        setupCall(port, definition, request, true) as Promise<
          SetupCall<LedgerResult<D>>
        >,
      readLanding(
        port,
        "ledger.inventory.inspect",
        { actividad_id: book.actividad_id, year: book.year },
        (read) => changeLanded(read.ledger, correction),
      ),
    );
    if (done.kind === "done" && refusalOf(done) === null) onWritten();
  };
  return (
    <Panel title={title} className={`ledger-stock-form ${className}`}>
      <form
        noValidate
        className="flex flex-col gap-3"
        onSubmit={(event) => {
          event.preventDefault();
          void send();
        }}
      >
        {children}
        <FormButtons
          busy={write.busy}
          ready={request !== null}
          submit={submit}
          onClose={onClose}
        />
        <CallLine call={write.last} refusal={refusalWords(t, write.last)} />
      </form>
    </Panel>
  );
}
