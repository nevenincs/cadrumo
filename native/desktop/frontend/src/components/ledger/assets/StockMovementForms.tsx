import { useState } from "react";
import { Icon } from "@/components/ui/icon";
import { IconButton } from "@/components/ui/icon-button";
import type { LedgerPort } from "../../../shell/ledger";
import type {
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
import { OffersNote, FormButtons, Section } from "./StockFormParts";
import { StockProofPicker } from "./StockProofPicker";
import {
  blankExtra,
  blankMovement,
  draftOfMovement,
  movementTouched,
} from "./stockDraft";
import {
  mint,
  useMovementDraft,
  type MovementDraftState,
} from "./stockDraftState";
import {
  COST_FIELDS,
  EXTRA_FIELDS,
  MOVEMENT_FIELDS,
  PRICE_FIELDS,
  PROOF_SLOTS,
  REASON_FIELD,
} from "./stockFieldDefinitions";
import { slotKinds, type ProofSlotKey } from "./stockVocabulary";
import {
  bookName,
  movementCorrectionRequest,
  movementCounted,
  movementRequest,
  type Built,
} from "./stockModel";
import type { OfferState } from "./stockReads";
import { plays } from "./stockVocabulary";
import { choicesOf, refusalOf, refusalWords } from "./stockWords";

// ---- A movement ---------------------------------------------------------------------

/** The fields of a movement: its date, kind and units, then what its kind
 * states about its cost. A purchase states its price, its extra costs and
 * the files that show them; what it all comes to is the backend's to add up. */
function MovementFields({
  port,
  catalogue,
  state,
  built,
  tried,
}: {
  port: LedgerPort;
  catalogue: OfferState;
  state: MovementDraftState;
  built: Built<unknown>;
  tried: boolean;
}) {
  const t = useStrings();
  const { draft, setValue, setExtra, setProof, setDraft } = state;
  const kind = draft.values.kind ?? "";
  const purchase = plays(catalogue.vocabulary, "purchase", kind);
  const choices = { kind: choicesOf(t, catalogue.offers, "movement_kind") };
  const extraChoices = {
    kind: choicesOf(t, catalogue.offers, "attributable_cost_kind"),
  };
  const common = {
    problems: built.problems,
    missing: built.missing,
    tried,
  };
  const slotFill = (slot: ProofSlotKey) =>
    tried &&
    (built.missing.has(`${slot}:file`) || built.missing.has(`${slot}:kind`));
  const kindsOf = (slot: ProofSlotKey) =>
    choicesOf(
      t,
      catalogue.offers,
      "acquisition_evidence_kind",
      slotKinds(slot, catalogue.vocabulary),
    );
  const ready = catalogue.state === "done";
  return (
    <>
      <OffersNote state={catalogue.state} />
      <StockFields
        fields={MOVEMENT_FIELDS}
        valueOf={(field) => draft.values[field.key] ?? ""}
        onValue={setValue}
        choices={choices}
        {...common}
      />
      {kind !== "" && !purchase && (
        <StockFields
          fields={COST_FIELDS}
          valueOf={(field) => draft.values[field.key] ?? ""}
          onValue={setValue}
          choices={{}}
          {...common}
        />
      )}
      {purchase && (
        <>
          <Section heading={t("desktop.ledger.stock.purchase.price")}>
            <StockFields
              fields={PRICE_FIELDS}
              valueOf={(field) => draft.values[field.key] ?? ""}
              onValue={setValue}
              choices={{}}
              {...common}
            />
          </Section>
          <Section
            heading={t("desktop.ledger.stock.purchase.extras")}
            actions={
              <IconButton
                label={t("desktop.ledger.stock.extra.add")}
                onClick={() =>
                  setDraft((current) => ({
                    ...current,
                    extras: [...current.extras, blankExtra(mint)],
                  }))
                }
              >
                <Icon name="plus" />
              </IconButton>
            }
          >
            {draft.extras.length === 0 && (
              <p className="text-sm text-muted-foreground">
                {t("desktop.ledger.stock.extra.none")}
              </p>
            )}
            {draft.extras.map((extra) => {
              const field = (name: string) => `extra:${extra.key}:${name}`;
              return (
                <div
                  key={extra.key}
                  className="ledger-stock-extra flex flex-col gap-3 rounded-md bg-card p-3"
                >
                  <div className="flex justify-end">
                    <IconButton
                      label={t("desktop.ledger.stock.extra.remove")}
                      onClick={() =>
                        setDraft((current) => ({
                          ...current,
                          extras: current.extras.filter(
                            (found) => found.key !== extra.key,
                          ),
                        }))
                      }
                    >
                      <Icon name="trash" />
                    </IconButton>
                  </div>
                  <StockFields
                    fields={EXTRA_FIELDS}
                    valueOf={(entry) =>
                      extra[entry.key as "kind" | "price" | "iva" | "share"]
                    }
                    onValue={(entry, value) =>
                      setExtra(extra.key, entry.key, value)
                    }
                    choices={extraChoices}
                    at={(entry) => field(entry.key)}
                    {...common}
                  />
                  <StockProofPicker
                    port={port}
                    label={t("desktop.ledger.stock.proof.extra")}
                    kinds={kindsOf("price")}
                    proof={extra.proof}
                    onProof={(change) => setProof({ extra: extra.key }, change)}
                    disabled={!ready}
                    fillIn={
                      tried &&
                      (built.missing.has(field("proof:file")) ||
                        built.missing.has(field("proof:kind")))
                    }
                  />
                </div>
              );
            })}
          </Section>
          <Section heading={t("desktop.ledger.stock.purchase.proofs")}>
            <p className="text-sm text-muted-foreground">
              {t("desktop.ledger.stock.purchase.proofs_hint")}
            </p>
            {PROOF_SLOTS.map((slot) => (
              <StockProofPicker
                key={slot.key}
                port={port}
                label={t(slot.label)}
                hint={slot.hint ? t(slot.hint) : undefined}
                kinds={kindsOf(slot.key)}
                proof={draft.proofs[slot.key]}
                onProof={(change) => setProof({ slot: slot.key }, change)}
                disabled={!ready}
                fillIn={slotFill(slot.key)}
              />
            ))}
          </Section>
          <p className="text-sm text-muted-foreground">
            {t("desktop.ledger.stock.purchase.totals_note")}
          </p>
        </>
      )}
    </>
  );
}

export function MovementForm({
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
  const write = useSetupWrite(t("desktop.ledger.stock.title"));
  // The movement's reference is minted once, when the form opens, and never
  // shown or typed. A movement sent again under it is refused.
  const [reference] = useState(mint);
  const state = useMovementDraft(blankMovement());
  const [tried, setTried] = useState(false);
  useSetupDraft(movementTouched(state.draft));
  const built = movementRequest(
    book,
    reference,
    state.draft,
    catalogue.vocabulary,
  );

  const send = async () => {
    if (write.busy) return;
    const request = built.request;
    if (request === null) {
      setTried(true);
      return;
    }
    // A movement adds one to its book's count, so the count before the write
    // tells whether it landed.
    const before = book.movement_count;
    const done = await write.run(
      () => setupCall(port, "ledger.inventory.movement.add", request, true),
      readLanding(port, "ledger.inventory.list", {}, (listed) =>
        movementCounted(listed.rows, book, before),
      ),
    );
    if (done.kind === "done" && refusalOf(done) === null) onWritten();
  };

  return (
    <Panel
      title={t("desktop.ledger.stock.form.movement", {
        name: bookName(book),
        year: book.year,
      })}
      className="ledger-stock-form ledger-stock-form-movement"
    >
      <form
        noValidate
        className="flex flex-col gap-4"
        onSubmit={(event) => {
          event.preventDefault();
          void send();
        }}
      >
        <MovementFields
          port={port}
          catalogue={catalogue}
          state={state}
          built={built}
          tried={tried}
        />
        <FormButtons
          busy={write.busy}
          ready={built.request !== null}
          submit={t("desktop.ledger.stock.submit.movement")}
          onClose={onClose}
        />
        <CallLine call={write.last} refusal={refusalWords(t, write.last)} />
      </form>
    </Panel>
  );
}

export function MovementCorrectForm({
  port,
  book,
  target,
  catalogue,
  onClose,
  onWritten,
}: {
  port: LedgerPort;
  book: InventoryBookRow;
  target: InventoryMovement;
  catalogue: OfferState;
  onClose(): void;
  onWritten(): void;
}) {
  const t = useStrings();
  // Both references are minted once, when the form opens, and never shown.
  const [ids] = useState(() => ({ correction: mint(), movement: mint() }));
  const [initial] = useState(() =>
    draftOfMovement(target, catalogue.vocabulary),
  );
  const state = useMovementDraft(initial);
  const [reason, setReason] = useState("");
  const [tried, setTried] = useState(false);
  const built = movementCorrectionRequest(
    book,
    ids,
    target.movement_id,
    reason,
    state.draft,
    catalogue.vocabulary,
  );
  const changed =
    reason !== "" || JSON.stringify(state.draft) !== JSON.stringify(initial);
  return (
    <StockChangeForm
      port={port}
      definition="ledger.inventory.movement.correct"
      book={book}
      correction={ids.correction}
      request={built.request}
      touched={changed}
      title={t("desktop.ledger.stock.form.movement_correct", {
        name: bookName(book),
        year: book.year,
      })}
      submit={t("desktop.ledger.stock.submit.movement_correct")}
      className="ledger-stock-form-movement-correct"
      onTry={() => setTried(true)}
      onClose={onClose}
      onWritten={onWritten}
    >
      <p className="text-sm text-muted-foreground">
        {t("desktop.ledger.stock.movement_correct_note")}
      </p>
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
      <MovementFields
        port={port}
        catalogue={catalogue}
        state={state}
        built={built}
        tried={tried}
      />
    </StockChangeForm>
  );
}
