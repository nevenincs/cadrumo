import { useState } from "react";
import { Alert } from "@/components/ui/alert";
import { Icon } from "@/components/ui/icon";
import type { LedgerPort } from "../../../shell/ledger";
import type {
  InventoryBook,
  InventoryBookRow,
  InventoryMovement,
} from "../../../shell/ledgerSetup";
import { useStrings } from "../../../shell/strings";
import {
  CallLine,
  Panel,
  readLanding,
  useSetupDraft,
  useSetupWrite,
} from "../setup/SetupParts";
import { setupCall } from "../setup/setupModel";
import { StockChangeForm } from "./StockChangeForm";
import { StockFields } from "./StockFields";
import { OffersNote, FormButtons } from "./StockFormParts";
import {
  bookTouched,
  EMPTY_BOOK,
  EMPTY_CORRECTION,
  type BookDraft,
  type CorrectDraft,
  type DescribeDraft,
} from "./stockDraft";
import { mint } from "./stockDraftState";
import {
  BOOK_FIELDS,
  CORRECT_FIELDS,
  DESCRIBE_FIELDS,
  REASON_FIELD,
} from "./stockFieldDefinitions";
import {
  bookListed,
  bookName,
  bookNameOptions,
  bookRequest,
  correctRequest,
  describeRequest,
  restoreRequest,
  retireRequest,
  reverseRequest,
} from "./stockModel";
import type { OfferState } from "./stockReads";
import { choicesOf, refusalOf, refusalWords, movementLine } from "./stockWords";

// ---- A new book --------------------------------------------------------------------

export function BookForm({
  port,
  year,
  books,
  catalogue,
  onClose,
  onWritten,
}: {
  port: LedgerPort;
  year: number;
  /** The books held, in every year; null while unread or where it failed. */
  books: readonly InventoryBookRow[] | null;
  catalogue: OfferState;
  onClose(): void;
  onWritten(): void;
}) {
  const t = useStrings();
  const write = useSetupWrite(t("desktop.ledger.stock.title"));
  const [draft, setDraft] = useState<BookDraft>(EMPTY_BOOK);
  const [tried, setTried] = useState(false);
  useSetupDraft(bookTouched(draft));
  const built = bookRequest(year, draft, catalogue.vocabulary);
  const choices = {
    method: choicesOf(t, catalogue.offers, "valuation_method"),
  };

  const send = async () => {
    if (write.busy) return;
    const request = built.request;
    if (request === null) {
      setTried(true);
      return;
    }
    const done = await write.run(
      () => setupCall(port, "ledger.inventory.create", request, true),
      readLanding(port, "ledger.inventory.list", {}, (listed) =>
        bookListed(listed.rows, request.actividad_id, year),
      ),
    );
    if (done.kind === "done" && refusalOf(done) === null) onWritten();
  };

  return (
    <Panel
      title={t("desktop.ledger.stock.form.book", { year })}
      className="ledger-stock-form ledger-stock-form-book"
    >
      <form
        noValidate
        className="flex flex-col gap-3"
        onSubmit={(event) => {
          event.preventDefault();
          void send();
        }}
      >
        <OffersNote state={catalogue.state} />
        <StockFields
          fields={BOOK_FIELDS.map((field) =>
            field.key === "name" && books !== null
              ? {
                  ...field,
                  offers: { suggestions: bookNameOptions(books, year) },
                }
              : field,
          )}
          valueOf={(field) => draft[field.key as keyof BookDraft]}
          onValue={(field, value) =>
            setDraft((current) => ({ ...current, [field.key]: value }))
          }
          choices={choices}
          problems={built.problems}
          missing={built.missing}
          tried={tried}
          autoFocus
        />
        <FormButtons
          busy={write.busy}
          ready={built.request !== null}
          submit={t("desktop.ledger.stock.submit.book")}
          onClose={onClose}
        />
        <CallLine call={write.last} refusal={refusalWords(t, write.last)} />
      </form>
    </Panel>
  );
}

export function DescribeForm({
  port,
  book,
  ledger,
  onClose,
  onWritten,
}: {
  port: LedgerPort;
  book: InventoryBookRow;
  ledger: InventoryBook;
  onClose(): void;
  onWritten(): void;
}) {
  const t = useStrings();
  const start: DescribeDraft = {
    label: ledger.descriptor?.label ?? bookName(book),
    description: ledger.descriptor?.description ?? "",
  };
  const [draft, setDraft] = useState<DescribeDraft>(start);
  const [correction] = useState(mint);
  const [tried, setTried] = useState(false);
  const built = describeRequest(book, correction, draft);
  return (
    <StockChangeForm
      port={port}
      definition="ledger.inventory.describe"
      book={book}
      correction={correction}
      request={built.request}
      touched={
        draft.label !== start.label || draft.description !== start.description
      }
      title={t("desktop.ledger.stock.form.describe", {
        name: bookName(book),
        year: book.year,
      })}
      submit={t("desktop.ledger.stock.submit.describe")}
      className="ledger-stock-form-describe"
      onTry={() => setTried(true)}
      onClose={onClose}
      onWritten={onWritten}
    >
      <StockFields
        fields={DESCRIBE_FIELDS}
        valueOf={(field) => draft[field.key as keyof DescribeDraft]}
        onValue={(field, value) =>
          setDraft((current) => ({ ...current, [field.key]: value }))
        }
        choices={{}}
        problems={built.problems}
        missing={built.missing}
        tried={tried}
        autoFocus
      />
    </StockChangeForm>
  );
}

export function CorrectForm({
  port,
  book,
  catalogue,
  onClose,
  onWritten,
}: {
  port: LedgerPort;
  book: InventoryBookRow;
  catalogue: OfferState;
  onClose(): void;
  onWritten(): void;
}) {
  const t = useStrings();
  const [draft, setDraft] = useState<CorrectDraft>(EMPTY_CORRECTION);
  const [correction] = useState(mint);
  const [tried, setTried] = useState(false);
  const built = correctRequest(book, correction, draft, catalogue.vocabulary);
  const choices = {
    reason: choicesOf(t, catalogue.offers, "correction_reason"),
    method: [
      { value: "", label: t("desktop.ledger.stock.field.keep") },
      ...choicesOf(t, catalogue.offers, "valuation_method"),
    ],
  };
  return (
    <StockChangeForm
      port={port}
      definition="ledger.inventory.correct"
      book={book}
      correction={correction}
      request={built.request}
      touched={Object.values(draft).some((text) => text.trim() !== "")}
      title={t("desktop.ledger.stock.form.correct", {
        name: bookName(book),
        year: book.year,
      })}
      submit={t("desktop.ledger.stock.submit.correct")}
      className="ledger-stock-form-correct"
      onTry={() => setTried(true)}
      onClose={onClose}
      onWritten={onWritten}
    >
      <OffersNote state={catalogue.state} />
      <StockFields
        fields={CORRECT_FIELDS}
        valueOf={(field) => draft[field.key as keyof CorrectDraft]}
        onValue={(field, value) =>
          setDraft((current) => ({ ...current, [field.key]: value }))
        }
        choices={choices}
        problems={built.problems}
        missing={built.missing}
        tried={tried}
        autoFocus
      />
    </StockChangeForm>
  );
}

export function ReverseForm({
  port,
  book,
  target,
  locale,
  catalogue,
  onClose,
  onWritten,
}: {
  port: LedgerPort;
  catalogue: OfferState;
  book: InventoryBookRow;
  target: InventoryMovement;
  locale: string;
  onClose(): void;
  onWritten(): void;
}) {
  const t = useStrings();
  const [reason, setReason] = useState("");
  const [correction] = useState(mint);
  const [tried, setTried] = useState(false);
  const built = reverseRequest(
    book,
    correction,
    target.movement_id,
    reason,
    catalogue.vocabulary,
  );
  return (
    <StockChangeForm
      port={port}
      definition="ledger.inventory.movement.reverse"
      book={book}
      correction={correction}
      request={built.request}
      touched={reason !== ""}
      title={t("desktop.ledger.stock.form.reverse", {
        name: bookName(book),
        year: book.year,
      })}
      submit={t("desktop.ledger.stock.submit.reverse")}
      className="ledger-stock-form-reverse"
      onTry={() => setTried(true)}
      onClose={onClose}
      onWritten={onWritten}
    >
      <p className="text-sm">{movementLine(t, locale, target)}</p>
      <p className="text-sm text-muted-foreground">
        {t("desktop.ledger.stock.reverse_note")}
      </p>
      <OffersNote state={catalogue.state} />
      <StockFields
        fields={[REASON_FIELD]}
        valueOf={() => reason}
        onValue={(_, value) => setReason(value)}
        choices={{
          reason: choicesOf(t, catalogue.offers, "correction_reason"),
        }}
        problems={built.problems}
        missing={built.missing}
        tried={tried}
        autoFocus
      />
    </StockChangeForm>
  );
}

export function RetireForm({
  port,
  book,
  catalogue,
  onClose,
  onWritten,
}: {
  port: LedgerPort;
  catalogue: OfferState;
  book: InventoryBookRow;
  onClose(): void;
  onWritten(): void;
}) {
  const t = useStrings();
  const [reason, setReason] = useState("");
  const [correction] = useState(mint);
  const [tried, setTried] = useState(false);
  const built = retireRequest(book, correction, reason, catalogue.vocabulary);
  return (
    <StockChangeForm
      port={port}
      definition="ledger.inventory.retire"
      book={book}
      correction={correction}
      request={built.request}
      touched={reason !== ""}
      title={t("desktop.ledger.stock.form.retire", {
        name: bookName(book),
        year: book.year,
      })}
      submit={t("desktop.ledger.stock.submit.retire")}
      className="ledger-stock-form-retire"
      onTry={() => setTried(true)}
      onClose={onClose}
      onWritten={onWritten}
    >
      <Alert icon={<Icon name="info" />}>
        {t("desktop.ledger.stock.retire_note")}
      </Alert>
      <OffersNote state={catalogue.state} />
      <StockFields
        fields={[REASON_FIELD]}
        valueOf={() => reason}
        onValue={(_, value) => setReason(value)}
        choices={{
          reason: choicesOf(t, catalogue.offers, "retirement_reason"),
        }}
        problems={built.problems}
        missing={built.missing}
        tried={tried}
        autoFocus
      />
    </StockChangeForm>
  );
}

export function RestoreForm({
  port,
  book,
  onClose,
  onWritten,
}: {
  port: LedgerPort;
  book: InventoryBookRow;
  onClose(): void;
  onWritten(): void;
}) {
  const t = useStrings();
  const [correction] = useState(mint);
  return (
    <StockChangeForm
      port={port}
      definition="ledger.inventory.restore"
      book={book}
      correction={correction}
      request={restoreRequest(book, correction)}
      touched={false}
      title={t("desktop.ledger.stock.form.restore", {
        name: bookName(book),
        year: book.year,
      })}
      submit={t("desktop.ledger.stock.submit.restore")}
      className="ledger-stock-form-restore"
      onTry={() => undefined}
      onClose={onClose}
      onWritten={onWritten}
    >
      <p className="text-sm text-muted-foreground">
        {t("desktop.ledger.stock.restore_note")}
      </p>
    </StockChangeForm>
  );
}
