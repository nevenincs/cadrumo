import { useMemo, useState, type ReactNode } from "react";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty";
import { Icon, type IconName } from "@/components/ui/icon";
import { IconButton } from "@/components/ui/icon-button";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { formatDay } from "../../../shared/dateFormats";
import { formatAmount, formatDecimal } from "../../../shared/numbers";
import type {
  InventoryBookRow,
  InventoryMovement,
  InventoryValuationResult,
} from "../../../shell/ledgerSetup";
import { useStrings } from "../../../shell/strings";
import { WriteHold } from "../WritePause";
import {
  CallLine,
  rankDecimal,
  Reading,
  SetupTable,
  type Column,
} from "../setup/SetupParts";
import { setupCall, type SetupCall } from "../setup/setupModel";
import type { SetupProps } from "../setup/setupProps";
import { formatUnitPrice } from "../unitPrice";
import { History, PurchaseFacts, Advisories } from "./StockBookDetails";
import {
  BookForm,
  DescribeForm,
  CorrectForm,
  ReverseForm,
  RetireForm,
  RestoreForm,
} from "./StockBookForms";
import { ClosingForm } from "./StockClosingForm";
import { MovementClaimForm, CLAIM_ROW_KEYS } from "./StockClaimForm";
import { MovementForm, MovementCorrectForm } from "./StockMovementForms";
import { YearStepper } from "./YearStepper";
import { bookName, claimOf } from "./stockModel";
import {
  keyOf,
  useBookList,
  useBookDetail,
  useOffers,
  type BookKey,
} from "./stockReads";
import { plays, wordOf } from "./stockVocabulary";
import { refusalOf, refusalWords } from "./stockWords";

const NO_BOOKS: readonly InventoryBookRow[] = [];

// ---- Book table decorations -------------------------------------------------------

/** A status as a glyph and a count; the words sit in its tooltip and its
 * accessible name. */
function Pill({
  icon,
  count,
  label,
}: {
  icon: IconName;
  count: number;
  label: string;
}) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span
          role="img"
          aria-label={label}
          className="ledger-stock-pill inline-flex items-center gap-1 rounded-full bg-secondary px-2 py-0.5 text-xs font-medium tabular-nums text-secondary-foreground"
        >
          <Icon name={icon} size="xs" />
          <span aria-hidden="true">{count}</span>
        </span>
      </TooltipTrigger>
      <TooltipContent>{label}</TooltipContent>
    </Tooltip>
  );
}

/** The actions on one row. Each is an icon button; another action is one more
 * child. */
function RowActions({ children }: { children: ReactNode }) {
  return (
    <span className="ledger-stock-actions flex justify-end gap-0.5">
      {children}
    </span>
  );
}

// ---- The pane -------------------------------------------------------------------------

type Task =
  | { kind: "book" }
  | {
      kind:
        "movement" | "describe" | "correct" | "retire" | "restore" | "closing";
      book: BookKey;
    }
  | {
      kind:
        | "movement_correct"
        | "movement_reverse"
        | "movement_claim"
        | "purchase_facts";
      book: BookKey;
      target: InventoryMovement;
    };

/**
 * Assets › Stock (existencias): the stock books for a year, one per activity,
 * the movements and history of the chosen one, a valuation preview that saves
 * nothing, and the forms to add a book or a movement and to change them. A
 * list not yet loaded, one that could not be loaded, one that was refused, an
 * account that withholds it and a year with no book are each said apart. A
 * retired book stays listed, marked with its reason; its stock cannot change
 * until it is restored.
 */
export function StockPane({
  port,
  reader,
  locale,
  years,
  fallbackYear,
}: SetupProps) {
  const t = useStrings();
  const [chosenYear, setYear] = useState<number | null>(null);
  const [chosen, setChosen] = useState<string | null>(null);
  const [task, setTask] = useState<Task | null>(null);
  const [preview, setPreview] = useState<{
    key: string;
    call: SetupCall<InventoryValuationResult>;
  } | null>(null);

  const year = chosenYear ?? fallbackYear;
  const [round, setRound] = useState(0);
  const reload = () => setRound((count) => count + 1);
  const list = useBookList(port, reader, round);
  const listed = list?.kind === "done" ? list.result.rows : NO_BOOKS;
  const offered = useMemo(
    () => [...(years ?? []), ...listed.map((row) => row.year), fallbackYear],
    [years, listed, fallbackYear],
  );
  const books = listed.filter((row) => row.year === year);
  const book = books.find((row) => row.actividad_id === chosen) ?? books[0];
  const retired = books.filter((row) => row.retired === true).length;
  const bookKey: BookKey | null = book
    ? { actividad_id: book.actividad_id, year: book.year }
    : null;
  const detail = useBookDetail(port, reader, bookKey, round);
  const catalogue = useOffers(port, reader, round);

  const choose = (row: BookKey) => setChosen(row.actividad_id);
  const open = (next: Task) => {
    if (next.kind !== "book") choose(next.book);
    setTask(next);
  };
  const written = () => {
    setPreview(null);
    setTask(null);
    reload();
  };
  const runPreview = async (row: InventoryBookRow) => {
    choose(row);
    setPreview({
      key: keyOf(row),
      call: await setupCall(
        port,
        "ledger.inventory.valuation.preview",
        { actividad_id: row.actividad_id, year: row.year },
        false,
      ),
    });
  };

  const ledger =
    detail?.kind === "done" && detail.result.outcome === "found"
      ? detail.result.ledger
      : null;

  const columns: Column<InventoryBookRow>[] = [
    {
      key: "name",
      label: t("desktop.ledger.stock.column.name"),
      sort: (row) => bookName(row),
      cell: (row) => (
        <span className="flex flex-wrap items-center gap-1.5">
          <Button
            variant="link"
            size="xs"
            className="ledger-stock-choose"
            aria-current={book?.actividad_id === row.actividad_id || undefined}
            onClick={() => choose(row)}
          >
            {bookName(row)}
          </Button>
          {row.retired === true && (
            <span className="ledger-stock-retired inline-flex items-center gap-1 text-xs text-muted-foreground">
              <Icon name="archive" size="xs" />
              {row.retirement_reason
                ? t("desktop.ledger.stock.retired_because", {
                    reason: wordOf(
                      t,
                      "retirement_reason",
                      row.retirement_reason,
                    ),
                  })
                : t("desktop.ledger.stock.retired")}
            </span>
          )}
          {(row.advisories ?? []).length > 0 && (
            <Pill
              icon="alert"
              count={(row.advisories ?? []).length}
              label={t("desktop.ledger.stock.count.advisories", {
                count: (row.advisories ?? []).length,
              })}
            />
          )}
          {(row.correction_count ?? 0) > 0 && (
            <Pill
              icon="edit"
              count={row.correction_count ?? 0}
              label={t("desktop.ledger.stock.count.corrections", {
                count: row.correction_count ?? 0,
              })}
            />
          )}
        </span>
      ),
    },
    {
      key: "method",
      label: t("desktop.ledger.inventory.column.method"),
      sort: (row) => wordOf(t, "valuation_method", row.valuation_method),
      cell: (row) => wordOf(t, "valuation_method", row.valuation_method),
    },
    {
      key: "opening",
      label: t("desktop.ledger.inventory.column.opening"),
      numeric: true,
      sort: (row) => rankDecimal(row.opening_stock.decimal),
      cell: (row) => formatAmount(locale, row.opening_stock.decimal),
    },
    {
      key: "movements",
      label: t("desktop.ledger.inventory.column.movements"),
      numeric: true,
      sort: (row) => row.movement_count,
      cell: (row) => row.movement_count,
    },
    {
      key: "actions",
      label: t("desktop.ledger.form.actions"),
      hidden: true,
      resizable: false,
      cell: (row) => {
        // A retired book's stock cannot change; the tooltip says why.
        const stopped = row.retired === true;
        const why = stopped
          ? t("desktop.ledger.stock.retired_hint")
          : undefined;
        const key = { actividad_id: row.actividad_id, year: row.year };
        return (
          <RowActions>
            <WriteHold>
              <IconButton
                label={t("desktop.ledger.stock.action.add_movement")}
                hint={why}
                aria-disabled={stopped || undefined}
                className="ledger-stock-add-movement"
                onClick={() =>
                  !stopped && open({ kind: "movement", book: key })
                }
              >
                <Icon name="plus" />
              </IconButton>
            </WriteHold>
            <IconButton
              label={t("desktop.ledger.stock.action.preview")}
              className="ledger-stock-preview"
              onClick={() => void runPreview(row)}
            >
              <Icon name="eye" />
            </IconButton>
            <WriteHold>
              <IconButton
                label={t("desktop.ledger.stock.action.closing")}
                hint={why}
                aria-disabled={stopped || undefined}
                className="ledger-stock-closing"
                onClick={() => !stopped && open({ kind: "closing", book: key })}
              >
                <Icon name="lock" />
              </IconButton>
            </WriteHold>
            <WriteHold>
              <IconButton
                label={t("desktop.ledger.stock.action.describe")}
                className="ledger-stock-describe"
                onClick={() => open({ kind: "describe", book: key })}
              >
                <Icon name="edit" />
              </IconButton>
            </WriteHold>
            <WriteHold>
              <IconButton
                label={t("desktop.ledger.stock.action.correct")}
                hint={why}
                aria-disabled={stopped || undefined}
                className="ledger-stock-correct"
                onClick={() => !stopped && open({ kind: "correct", book: key })}
              >
                <Icon name="reset" />
              </IconButton>
            </WriteHold>
            <WriteHold>
              {stopped ? (
                <IconButton
                  label={t("desktop.ledger.stock.action.restore")}
                  className="ledger-stock-restore"
                  onClick={() => open({ kind: "restore", book: key })}
                >
                  <Icon name="unarchive" />
                </IconButton>
              ) : (
                <IconButton
                  label={t("desktop.ledger.stock.action.retire")}
                  className="ledger-stock-retire"
                  onClick={() => open({ kind: "retire", book: key })}
                >
                  <Icon name="archive" />
                </IconButton>
              )}
            </WriteHold>
          </RowActions>
        );
      },
    },
  ];

  const body = () => {
    if (reader === null)
      return (
        <EmptyState
          icon="lock"
          heading={t("desktop.ledger.stock.unavailable")}
          className="ledger-stock-unavailable"
        />
      );
    if (list === null)
      return (
        <EmptyState
          busy
          heading={t("desktop.ledger.stock.loading")}
          className="ledger-stock-loading"
        />
      );
    if (list.kind === "refused")
      return (
        <Alert
          tone="danger"
          role="alert"
          icon={<Icon name="refused" />}
          className="ledger-stock-refused"
        >
          {t("desktop.ledger.stock.load_refused")}
        </Alert>
      );
    if (list.kind !== "done")
      return (
        <Alert
          tone="warning"
          role="alert"
          icon={<Icon name="alert" />}
          className="ledger-stock-failed"
        >
          <span>
            {t("desktop.ledger.stock.load_failed")}{" "}
            <Button variant="link" size="xs" onClick={reload}>
              {t("desktop.ledger.form.reread")}
            </Button>
          </span>
        </Alert>
      );
    if (books.length === 0)
      return (
        <EmptyState
          icon="book"
          heading={t("desktop.ledger.stock.empty", { year })}
          className="ledger-stock-empty"
        />
      );
    return (
      <SetupTable
        label={t("desktop.ledger.stock.books", { year })}
        rows={books}
        rowKey={(row) => row.actividad_id}
        selected={book?.actividad_id ?? null}
        columns={columns}
        className="ledger-stock-table"
      />
    );
  };

  const form = () => {
    if (task === null || reader === null) return null;
    const close = () => setTask(null);
    if (task.kind === "book")
      return (
        <BookForm
          key={`book|${year}`}
          port={port}
          year={year}
          books={list?.kind === "done" ? listed : null}
          catalogue={catalogue}
          onClose={close}
          onWritten={written}
        />
      );
    const row = listed.find(
      (found) =>
        found.actividad_id === task.book.actividad_id &&
        found.year === task.book.year,
    );
    if (!row) return null;
    const common = {
      port,
      book: row,
      catalogue,
      onClose: close,
      onWritten: written,
    };
    const key = `${task.kind}|${keyOf(row)}`;
    switch (task.kind) {
      case "movement":
        return <MovementForm key={key} {...common} />;
      case "describe":
        return ledger && keyOf(ledger) === keyOf(row) ? (
          <DescribeForm key={key} {...common} ledger={ledger} />
        ) : (
          <Reading label={t("desktop.ledger.stock.detail_loading")} />
        );
      case "correct":
        return <CorrectForm key={key} {...common} />;
      case "retire":
        return <RetireForm key={key} {...common} />;
      case "restore":
        return <RestoreForm key={key} {...common} />;
      case "closing":
        return <ClosingForm key={key} {...common} />;
      case "purchase_facts":
        return (
          <PurchaseFacts
            key={`${key}|${task.target.movement_id}`}
            movement={task.target}
            locale={locale}
            onClose={close}
          />
        );
      case "movement_correct":
        return (
          <MovementCorrectForm
            key={`${key}|${task.target.movement_id}`}
            {...common}
            target={task.target}
          />
        );
      case "movement_claim":
        return (
          <MovementClaimForm
            key={`${key}|${task.target.movement_id}`}
            {...common}
            reader={reader}
            locale={locale}
            target={task.target}
          />
        );
      case "movement_reverse":
        return (
          <ReverseForm
            key={`${key}|${task.target.movement_id}`}
            {...common}
            target={task.target}
            locale={locale}
          />
        );
    }
  };

  const valued =
    preview &&
    book &&
    preview.key === keyOf(book) &&
    preview.call.kind === "done"
      ? preview.call.result.preview
      : null;

  const movementsBody = () => {
    if (!book) return null;
    if (detail === null)
      return <Reading label={t("desktop.ledger.stock.detail_loading")} />;
    if (detail.kind !== "done" || detail.result.outcome !== "found" || !ledger)
      return (
        <Alert
          tone={detail.kind === "refused" ? "danger" : "warning"}
          role="alert"
          icon={<Icon name={detail.kind === "refused" ? "refused" : "alert"} />}
          className="ledger-stock-detail-failed"
        >
          {detail.kind === "refused" ||
          (detail.kind === "done" && detail.result.outcome === "refused")
            ? t("desktop.ledger.stock.detail_refused")
            : t("desktop.ledger.stock.detail_failed")}
        </Alert>
      );
    const stopped = book.retired === true;
    const why = stopped ? t("desktop.ledger.stock.retired_hint") : undefined;
    const bookKey: BookKey = {
      actividad_id: book.actividad_id,
      year: book.year,
    };
    return (
      <>
        <Advisories
          advisories={ledger.advisories ?? book.advisories}
          className="ledger-stock-advisory"
        />
        {ledger.closing_authority_fingerprints !== null && (
          <Alert
            icon={<Icon name="lock" />}
            className="ledger-stock-closing-recorded"
          >
            {t("desktop.ledger.stock.closing.recorded", { year: book.year })}
          </Alert>
        )}
        {ledger.period_movements.length === 0 ? (
          <p className="ledger-stock-movements-note text-sm text-muted-foreground">
            {t(
              stopped
                ? "desktop.ledger.stock.movements_none_retired"
                : "desktop.ledger.stock.movements_none",
            )}
          </p>
        ) : (
          <SetupTable<InventoryMovement>
            label={t("desktop.ledger.stock.movements_of", {
              name: bookName(book),
            })}
            rows={ledger.period_movements}
            rowKey={(movement) => movement.movement_id}
            className="ledger-stock-movements"
            columns={[
              {
                key: "date",
                label: t("desktop.ledger.inventory.column.date"),
                sort: (movement) => movement.movement_date,
                cell: (movement) => formatDay(locale, movement.movement_date),
              },
              {
                key: "kind",
                label: t("desktop.ledger.inventory.column.kind"),
                sort: (movement) => wordOf(t, "movement_kind", movement.kind),
                cell: (movement) => wordOf(t, "movement_kind", movement.kind),
              },
              {
                key: "quantity",
                label: t("desktop.ledger.inventory.column.quantity"),
                numeric: true,
                sort: (movement) => rankDecimal(movement.quantity.decimal),
                cell: (movement) =>
                  formatDecimal(locale, movement.quantity.decimal),
              },
              {
                key: "unit",
                label: t("desktop.ledger.inventory.column.unit_cost"),
                numeric: true,
                sort: (movement) => rankDecimal(movement.unit_cost?.decimal),
                cell: (movement) =>
                  movement.unit_cost
                    ? formatUnitPrice(locale, movement.unit_cost.decimal)
                    : "—",
              },
              {
                key: "cost",
                label: t("desktop.ledger.stock.column.cost"),
                numeric: true,
                sort: (movement) =>
                  rankDecimal(
                    movement.acquisition_cost?.total_acquisition_cost.decimal ??
                      movement.taxable_base?.decimal,
                  ),
                cell: (movement) => {
                  const cost =
                    movement.acquisition_cost?.total_acquisition_cost.decimal ??
                    movement.taxable_base?.decimal;
                  return cost === undefined ? "—" : formatAmount(locale, cost);
                },
              },
              {
                key: "ledger_row",
                label: t("desktop.ledger.stock.claim.column"),
                sort: (movement) => claimOf(movement)?.row ?? "",
                cell: (movement) => {
                  if (!plays(catalogue.vocabulary, "purchase", movement.kind))
                    return "—";
                  const claim = claimOf(movement);
                  // A statement the read did not serve is not said as any of
                  // the three.
                  if (claim === null) return "—";
                  return claim.row === "claimed" && claim.transaction !== null
                    ? t("desktop.ledger.stock.claim.state_claimed", {
                        transaction: claim.transaction,
                      })
                    : t(CLAIM_ROW_KEYS[claim.row]);
                },
              },
              {
                key: "actions",
                label: t("desktop.ledger.form.actions"),
                hidden: true,
                resizable: false,
                cell: (movement) => (
                  <RowActions>
                    {plays(catalogue.vocabulary, "purchase", movement.kind) && (
                      <IconButton
                        label={t("desktop.ledger.stock.action.purchase_facts")}
                        className="ledger-stock-purchase-facts"
                        onClick={() =>
                          open({
                            kind: "purchase_facts",
                            book: bookKey,
                            target: movement,
                          })
                        }
                      >
                        <Icon name="eye" />
                      </IconButton>
                    )}
                    {plays(catalogue.vocabulary, "purchase", movement.kind) && (
                      <WriteHold>
                        <IconButton
                          label={t(
                            "desktop.ledger.stock.action.movement_claim",
                          )}
                          hint={why}
                          aria-disabled={stopped || undefined}
                          className="ledger-stock-movement-claim"
                          onClick={() =>
                            !stopped &&
                            open({
                              kind: "movement_claim",
                              book: bookKey,
                              target: movement,
                            })
                          }
                        >
                          <Icon name="link" />
                        </IconButton>
                      </WriteHold>
                    )}
                    <WriteHold>
                      <IconButton
                        label={t(
                          "desktop.ledger.stock.action.movement_correct",
                        )}
                        hint={why}
                        aria-disabled={stopped || undefined}
                        className="ledger-stock-movement-correct"
                        onClick={() =>
                          !stopped &&
                          open({
                            kind: "movement_correct",
                            book: bookKey,
                            target: movement,
                          })
                        }
                      >
                        <Icon name="edit" />
                      </IconButton>
                    </WriteHold>
                    <WriteHold>
                      <IconButton
                        label={t(
                          "desktop.ledger.stock.action.movement_reverse",
                        )}
                        hint={why}
                        aria-disabled={stopped || undefined}
                        className="ledger-stock-movement-reverse"
                        onClick={() =>
                          !stopped &&
                          open({
                            kind: "movement_reverse",
                            book: bookKey,
                            target: movement,
                          })
                        }
                      >
                        <Icon name="erase" />
                      </IconButton>
                    </WriteHold>
                  </RowActions>
                ),
              },
            ]}
          />
        )}
        <h3 className="font-medium">
          {t("desktop.ledger.stock.history_of", { name: bookName(book) })}
        </h3>
        <History
          ledger={ledger}
          locale={locale}
          name={bookName(book)}
          offers={catalogue.offers}
        />
      </>
    );
  };

  return (
    <div className="ledger-stock flex min-h-0 flex-1 flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2">
        <WriteHold>
          <IconButton
            label={t("desktop.ledger.stock.action.add_book")}
            className="ledger-stock-add-book"
            disabled={reader === null}
            onClick={() => open({ kind: "book" })}
          >
            <Icon name="plus" />
          </IconButton>
        </WriteHold>
        <YearStepper
          value={year}
          years={offered}
          onChange={(next) => {
            setYear(next);
            setChosen(null);
            setPreview(null);
            setTask(null);
          }}
        />
        <span className="flex-1" />
        {list?.kind === "done" && (
          <span
            role="group"
            aria-label={t("desktop.ledger.stock.summary")}
            className="flex flex-wrap items-center gap-1"
          >
            <Pill
              icon="book"
              count={books.length}
              label={t("desktop.ledger.stock.count.books", {
                count: books.length,
              })}
            />
            {retired > 0 && (
              <Pill
                icon="archive"
                count={retired}
                label={t("desktop.ledger.stock.count.retired", {
                  count: retired,
                })}
              />
            )}
          </span>
        )}
      </div>
      {form()}
      {body()}
      {valued && book && (
        <Alert icon={<Icon name="info" />} className="ledger-stock-valuation">
          <span className="font-medium tabular-nums">
            {t("desktop.ledger.inventory.valuation", {
              name: bookName(book),
              closing: formatAmount(
                locale,
                valued.derived_closing_value.decimal,
              ),
              cogs: formatAmount(locale, valued.cogs.decimal),
              method: wordOf(t, "valuation_method", valued.valuation_method),
            })}
          </span>
          <span className="text-sm">
            {t("desktop.ledger.inventory.preview_note")}
          </span>
        </Alert>
      )}
      {preview && preview.call.kind !== "done" && book && (
        <CallLine call={preview.call} refusal={refusalWords(t, preview.call)} />
      )}
      {preview?.call.kind === "done" && refusalOf(preview.call) !== null && (
        <Alert
          tone="danger"
          role="alert"
          icon={<Icon name="refused" />}
          className="ledger-stock-refused"
        >
          {refusalWords(t, preview.call)()}
        </Alert>
      )}
      {list?.kind === "done" && movementsBody()}
    </div>
  );
}
