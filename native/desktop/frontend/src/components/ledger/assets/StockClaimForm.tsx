import { useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import { Combobox } from "@/components/ui/combobox";
import { Icon } from "@/components/ui/icon";
import { facts } from "@/shell/compose";
import { formatDay } from "../../../shared/dateFormats";
import { formatAmount } from "../../../shared/numbers";
import { PURCHASE_LEDGER_ROWS } from "../../../shell/ledgerContract";
import { LEDGER_PAGE_SIZE } from "../../../shell/ledgerWindow";
import type { LedgerPort } from "../../../shell/ledger";
import type {
  InventoryBookRow,
  InventoryMovement,
} from "../../../shell/ledgerSetup";
import { useStrings } from "../../../shell/strings";
import { ChoiceField, useSetupRead } from "../setup/SetupParts";
import { EditorField } from "../setup/EditorField";
import { StockChangeForm } from "./StockChangeForm";
import { mint } from "./stockDraftState";
import { bookName, claimOf, claimRequest } from "./stockModel";
import { movementLine } from "./stockWords";

/** The words of the three things a purchase can state. */
export const CLAIM_ROW_KEYS = {
  unstated: "desktop.ledger.stock.claim.row_unstated",
  claimed: "desktop.ledger.stock.claim.row_claimed",
  none: "desktop.ledger.stock.claim.row_none",
} as const;

/**
 * States, for one purchase, which ledger transaction books it, that none
 * does, or clears the statement. The three are chosen apart; a transaction is
 * named exactly when one is claimed. Whether a claim stands is the backend's
 * to say, and its refusal is shown in the words it serves.
 */
export function MovementClaimForm({
  port,
  reader,
  locale,
  book,
  target,
  onClose,
  onWritten,
}: {
  port: LedgerPort;
  reader: string | null;
  locale: string;
  book: InventoryBookRow;
  target: InventoryMovement;
  onClose(): void;
  onWritten(): void;
}) {
  const t = useStrings();
  // The reference is minted once, when the form opens, and never shown.
  const [correction] = useState(mint);
  const [initial] = useState(() => claimOf(target));
  const [row, setRow] = useState(initial?.row ?? "");
  const [transaction, setTransaction] = useState(initial?.transaction ?? "");
  const [tried, setTried] = useState(false);
  const built = claimRequest(
    book,
    correction,
    target.movement_id,
    row,
    transaction,
  );
  const year = Number(target.movement_date.slice(0, 4));
  const rows = useSetupRead(
    port,
    reader,
    "ledger.list",
    row === "claimed"
      ? {
          filters: ["period=0A", `year=${year}`],
          sort_by: "date",
          sort_order: "desc",
          limit: LEDGER_PAGE_SIZE,
        }
      : null,
    `stock-claim:${year}:${row === "claimed"}`,
  ).read;
  const options = useMemo(
    () =>
      (rows?.kind === "done" ? rows.result.rows : []).map(
        ({ transaction: found }) => ({
          value: found.transaction_id,
          label: facts(t, [
            found.description,
            formatDay(locale, found.date),
            formatAmount(locale, found.amount, { currency: found.currency }),
          ]),
          keywords: [found.counterparty],
        }),
      ),
    [locale, rows, t],
  );
  const picked =
    options.find((option) => option.value === transaction)?.label ??
    transaction;
  const changed =
    row !== (initial?.row ?? "") ||
    transaction !== (initial?.transaction ?? "");
  return (
    <StockChangeForm
      port={port}
      definition="ledger.inventory.movement.claim"
      book={book}
      correction={correction}
      request={built.request}
      touched={changed}
      title={t("desktop.ledger.stock.form.movement_claim", {
        name: bookName(book),
        year: book.year,
      })}
      submit={t("desktop.ledger.stock.submit.movement_claim")}
      className="ledger-stock-form-movement-claim"
      onTry={() => setTried(true)}
      onClose={onClose}
      onWritten={onWritten}
    >
      <p className="text-sm">{movementLine(t, locale, target)}</p>
      <p className="text-sm text-muted-foreground">
        {t("desktop.ledger.stock.claim.note")}
      </p>
      <ChoiceField
        label={t("desktop.ledger.stock.claim.row")}
        value={row}
        onValue={(next) => {
          setRow(next);
          if (next !== "claimed") setTransaction("");
        }}
        placeholder={t("desktop.ledger.form.choose")}
        hint={
          row === "unstated"
            ? t("desktop.ledger.stock.claim.row_unstated_hint")
            : undefined
        }
        required
        error={
          tried && built.missing.has("row")
            ? t("desktop.ledger.form.fill_to_continue")
            : null
        }
        options={PURCHASE_LEDGER_ROWS.map((value) => ({
          value,
          label: t(CLAIM_ROW_KEYS[value]),
        }))}
      />
      {row === "claimed" && (
        <EditorField
          label={t("desktop.ledger.stock.claim.transaction")}
          hint={
            rows?.kind === "done" && rows.result.truncated
              ? t("desktop.ledger.capital.movement_cut", {
                  count: LEDGER_PAGE_SIZE,
                })
              : undefined
          }
          error={
            tried && built.missing.has("transaction")
              ? t("desktop.ledger.form.fill_to_continue")
              : null
          }
        >
          {(control) => (
            <Combobox
              label={t("desktop.ledger.stock.claim.transaction")}
              value={transaction || null}
              options={options}
              emptyLabel={t("desktop.ledger.inspector.no_match")}
              onCommit={setTransaction}
            >
              <Button
                id={control.id}
                type="button"
                variant="outline"
                aria-describedby={control.describedBy}
                className="ledger-stock-claim-transaction w-full justify-between font-normal"
              >
                <span className="truncate">
                  {picked || t("desktop.ledger.form.choose")}
                </span>
                <Icon name="chevronDown" size="xs" />
              </Button>
            </Combobox>
          )}
        </EditorField>
      )}
    </StockChangeForm>
  );
}
