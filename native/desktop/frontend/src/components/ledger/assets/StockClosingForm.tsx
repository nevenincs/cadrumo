import { useState } from "react";
import { Icon } from "@/components/ui/icon";
import { IconButton } from "@/components/ui/icon-button";
import type { LedgerPort } from "../../../shell/ledger";
import type { InventoryBookRow } from "../../../shell/ledgerSetup";
import { useStrings } from "../../../shell/strings";
import {
  CallLine,
  Panel,
  readLanding,
  useSetupDraft,
  useSetupWrite,
} from "../setup/SetupParts";
import { setupCall } from "../setup/setupModel";
import { StockFields } from "./StockFields";
import { OffersNote, FormButtons, Section } from "./StockFormParts";
import { StockProofPicker } from "./StockProofPicker";
import {
  closingTouched,
  EMPTY_CLOSING,
  blankProof,
  type ClosingDraft,
  type ProofDraft,
} from "./stockDraft";
import { mint } from "./stockDraftState";
import {
  CLOSING_FIELDS,
  COUNT_FIELDS,
  type StockField,
} from "./stockFieldDefinitions";
import { bookName, closingLanded, closingRequest } from "./stockModel";
import type { OfferState } from "./stockReads";
import { plays, servedWord } from "./stockVocabulary";
import { choicesOf, refusalOf, refusalWords } from "./stockWords";

// ---- A closing value -----------------------------------------------------------------

/** The closing value of a book from the facts the person knows: how it is
 * decided, why, the documents that show it, and the count when the count is
 * the value. Nothing is hashed or fingerprinted here. */
export function ClosingForm({
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
  // Keep the decision reference stable when the form is submitted again.
  const [ids] = useState(() => ({
    decision: mint(),
  }));
  const [draft, setDraft] = useState<ClosingDraft>(EMPTY_CLOSING);
  const [tried, setTried] = useState(false);
  useSetupDraft(closingTouched(draft));
  const built = closingRequest(book, ids, draft, catalogue.vocabulary);
  const physical = plays(
    catalogue.vocabulary,
    "count_authority",
    draft.values.authority,
  );
  const ready = catalogue.state === "done";

  const setValue = (field: StockField, value: string) =>
    setDraft((current) => ({
      ...current,
      values: { ...current.values, [field.key]: value },
    }));
  const setRole = (
    group: "decision" | "count",
    role: string,
    change: (current: ProofDraft) => ProofDraft,
  ) => {
    setDraft((current) => ({
      ...current,
      [group]: {
        ...current[group],
        [role]: change(current[group][role] ?? blankProof(role)),
      },
    }));
  };
  const setPrior = (
    key: string,
    change: (current: ProofDraft) => ProofDraft,
  ) => {
    setDraft((current) => ({
      ...current,
      prior: current.prior.map((entry) =>
        entry.key === key ? { ...entry, proof: change(entry.proof) } : entry,
      ),
    }));
  };
  const filled = (key: string) => tried && built.missing.has(`${key}:file`);
  const roles = (family: string) => catalogue.offers[family] ?? [];

  const send = async () => {
    if (write.busy) return;
    const request = built.request;
    if (request === null) {
      setTried(true);
      return;
    }
    const done = await write.run(
      () =>
        setupCall(port, "ledger.inventory.closing-value.record", request, true),
      readLanding(
        port,
        "ledger.inventory.inspect",
        { actividad_id: book.actividad_id, year: book.year },
        (read) => closingLanded(read.ledger),
      ),
    );
    if (done.kind === "done" && refusalOf(done) === null) onWritten();
  };

  const documents = (
    group: "decision" | "count",
    family: string,
    heading: string,
  ) => (
    <Section heading={heading}>
      {roles(family).map((served) => (
        <StockProofPicker
          key={served.value}
          port={port}
          label={servedWord(t, served)}
          kinds={[]}
          proof={draft[group][served.value] ?? blankProof(served.value)}
          onProof={(change) => setRole(group, served.value, change)}
          disabled={!ready}
          fillIn={filled(`${group}:${served.value}`)}
        />
      ))}
    </Section>
  );

  return (
    <Panel
      title={t("desktop.ledger.stock.form.closing", {
        name: bookName(book),
        year: book.year,
      })}
      className="ledger-stock-form ledger-stock-form-closing"
    >
      <form
        noValidate
        className="flex flex-col gap-4"
        onSubmit={(event) => {
          event.preventDefault();
          void send();
        }}
      >
        <p className="text-sm text-muted-foreground">
          {t("desktop.ledger.stock.closing.note")}
        </p>
        <OffersNote state={catalogue.state} />
        <StockFields
          fields={CLOSING_FIELDS}
          valueOf={(field) => draft.values[field.key] ?? ""}
          onValue={setValue}
          choices={{
            authority: choicesOf(t, catalogue.offers, "closing_authority"),
          }}
          problems={built.problems}
          missing={built.missing}
          tried={tried}
          autoFocus
        />
        {physical && (
          <Section heading={t("desktop.ledger.stock.closing.count")}>
            <StockFields
              fields={COUNT_FIELDS}
              valueOf={(field) => draft.values[field.key] ?? ""}
              onValue={setValue}
              choices={{
                basis: choicesOf(
                  t,
                  catalogue.offers,
                  "closing_valuation_basis",
                ),
              }}
              problems={built.problems}
              missing={built.missing}
              tried={tried}
            />
          </Section>
        )}
        {physical &&
          documents(
            "count",
            "physical_evidence_role",
            t("desktop.ledger.stock.closing.count_documents"),
          )}
        {documents(
          "decision",
          "decision_evidence_role",
          t("desktop.ledger.stock.closing.documents"),
        )}
        <Section
          heading={t("desktop.ledger.stock.closing.prior")}
          actions={
            <IconButton
              label={t("desktop.ledger.stock.closing.prior_add")}
              onClick={() =>
                setDraft((current) => ({
                  ...current,
                  prior: [
                    ...current.prior,
                    { key: mint(), proof: blankProof() },
                  ],
                }))
              }
            >
              <Icon name="plus" />
            </IconButton>
          }
        >
          <p className="text-sm text-muted-foreground">
            {t("desktop.ledger.stock.closing.prior_hint")}
          </p>
          {draft.prior.map((entry) => (
            <div key={entry.key} className="flex items-end gap-2">
              <StockProofPicker
                port={port}
                label={t("desktop.ledger.stock.closing.prior_document")}
                kinds={[]}
                proof={entry.proof}
                onProof={(change) => setPrior(entry.key, change)}
                disabled={!ready}
                fillIn={filled(`prior:${entry.key}`)}
              />
              <IconButton
                label={t("desktop.ledger.stock.closing.prior_remove")}
                onClick={() =>
                  setDraft((current) => ({
                    ...current,
                    prior: current.prior.filter(
                      (found) => found.key !== entry.key,
                    ),
                  }))
                }
              >
                <Icon name="trash" />
              </IconButton>
            </div>
          ))}
        </Section>
        <FormButtons
          busy={write.busy}
          ready={built.request !== null}
          submit={t("desktop.ledger.stock.submit.closing")}
          onClose={onClose}
        />
        <CallLine call={write.last} refusal={refusalWords(t, write.last)} />
      </form>
    </Panel>
  );
}
