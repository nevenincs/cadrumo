import { useId, useState } from "react";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Field,
  FieldDescription,
  FieldError,
  FieldLabel,
} from "@/components/ui/field";
import { Icon } from "@/components/ui/icon";
import {
  parseDecimal,
  parseIsoDate,
  QUANTITY_RULE,
  TAX_AMOUNT_RULE,
  UNIT_PRICE_RULE,
  type Parsed,
} from "../../../shell/ledgerGrammar";
import type {
  InventoryBook,
  InventoryBookRow,
  InventoryCreateResult,
  InventoryMovement,
  InventoryRefusal,
  InventoryValuationResult,
} from "../../../shell/ledgerSetup";
import { useStrings } from "../../../shell/strings";
import { amountText, dateText } from "../movements/movementWords";
import { PeriodSelector } from "../PeriodSelector";
import {
  CallLine,
  ChoiceField,
  FormGrid,
  Panel,
  Reading,
  SetupTable,
  TextField,
  useSetupRead,
  useSetupWrite,
  type Column,
} from "./SetupParts";
import type { SetupProps } from "./setupProps";
import { parseObject, setupCall, type SetupCall } from "./setupModel";
import { grammarText, tokenText } from "./setupWords";

const METHODS = ["fifo", "pmp", "coste_medio"] as const;
const KINDS = ["opening", "purchase", "cogs", "count"] as const;

/**
 * A JSON document typed or pasted by the person: the inventory's closing
 * authority record. The same field takes a picked file's content once the
 * host reads one.
 */
export function JsonDocumentField({
  label,
  value,
  onValue,
  hint,
  error,
}: {
  label: string;
  value: string;
  onValue(value: string): void;
  hint?: string;
  error?: string | null;
}) {
  const id = useId();
  return (
    <Field data-invalid={error ? true : undefined}>
      <FieldLabel htmlFor={id}>{label}</FieldLabel>
      <textarea
        id={id}
        value={value}
        spellCheck={false}
        rows={8}
        aria-invalid={error ? true : undefined}
        aria-describedby={hint ? `${id}-hint` : undefined}
        className="w-full rounded-md border border-input bg-card p-2 font-mono text-sm text-foreground aria-invalid:border-destructive"
        onChange={(event) => onValue(event.target.value)}
      />
      {hint && <FieldDescription id={`${id}-hint`}>{hint}</FieldDescription>}
      <FieldError>{error}</FieldError>
    </Field>
  );
}

type Task = "create" | "movement" | "closing";

/**
 * The inventory books, one per activity and year: their valuation method
 * and opening stock, the movements added to them, a valuation preview that
 * records nothing, and the record of who decides the closing value.
 */
export function InventoryPane({
  port,
  reader,
  locale,
  years,
  fallbackYear,
}: SetupProps) {
  const t = useStrings();
  const [year, setYear] = useState(fallbackYear);
  const { read, reload } = useSetupRead(
    port,
    reader,
    "ledger.inventory.list",
    {},
    "inventory",
  );
  const write = useSetupWrite();
  const [task, setTask] = useState<Task | null>(null);
  const [chosen, setChosen] = useState("");
  const [actividad, setActividad] = useState("");
  const [method, setMethod] = useState("");
  const [opening, setOpening] = useState("");
  const [movementId, setMovementId] = useState("");
  const [movementDate, setMovementDate] = useState("");
  const [kind, setKind] = useState("");
  const [quantity, setQuantity] = useState("");
  const [unitCost, setUnitCost] = useState("");
  const [base, setBase] = useState("");
  const [authority, setAuthority] = useState("");
  const [preview, setPreview] =
    useState<SetupCall<InventoryValuationResult> | null>(null);
  const [lastBook, setLastBook] = useState<InventoryBook | null>(null);

  const books = (read?.kind === "done" ? read.result.rows : []).filter(
    (book) => book.year === year,
  );
  const book = books.find((found) => found.actividad_id === chosen) ?? books[0];
  const start = (next: Task) => {
    write.clear();
    setTask(task === next ? null : next);
  };
  const openingParsed = parseDecimal(opening, TAX_AMOUNT_RULE);
  const quantityParsed = parseDecimal(quantity, QUANTITY_RULE);
  const unitParsed = parseDecimal(unitCost, UNIT_PRICE_RULE);
  const baseParsed = parseDecimal(base, TAX_AMOUNT_RULE);
  const dateParsed = parseIsoDate(movementDate);
  const record = parseObject(authority);
  const refusedText = (parsed: Parsed<unknown>) =>
    parsed.kind === "refused" ? grammarText(t, parsed.refusal) : null;
  const ready =
    task === "create"
      ? actividad.trim() !== "" &&
        method !== "" &&
        openingParsed.kind === "value"
      : task === "movement"
        ? book !== undefined &&
          movementId.trim() !== "" &&
          dateParsed.kind === "value" &&
          kind !== "" &&
          quantityParsed.kind === "value" &&
          unitParsed.kind !== "refused" &&
          baseParsed.kind !== "refused"
        : task === "closing"
          ? book !== undefined && record.kind === "value"
          : false;

  const decimalOr = (parsed: ReturnType<typeof parseDecimal>) =>
    parsed.kind === "value" ? { decimal: parsed.value } : null;
  const send = async () => {
    if (!ready) return;
    const done = await write.run(async (): Promise<SetupCall<unknown>> => {
      if (task === "create")
        return setupCall(
          port,
          "ledger.inventory.create",
          {
            actividad_id: actividad.trim(),
            year,
            valuation_method: method,
            opening_stock: decimalOr(openingParsed) ?? { decimal: "0" },
          },
          true,
        );
      if (task === "movement" && book)
        return setupCall(
          port,
          "ledger.inventory.movement.add",
          {
            actividad_id: book.actividad_id,
            year,
            movement_id: movementId.trim(),
            movement_date: dateParsed.kind === "value" ? dateParsed.value : "",
            kind: kind as InventoryMovement["kind"],
            quantity: decimalOr(quantityParsed) ?? { decimal: "" },
            unit_cost: decimalOr(unitParsed),
            taxable_base: decimalOr(baseParsed),
          },
          true,
        );
      if (task === "closing" && book && record.kind === "value")
        return setupCall(
          port,
          "ledger.inventory.closing-authority.record",
          {
            actividad_id: book.actividad_id,
            year,
            authority_record: record.value,
          },
          true,
        );
      return { kind: "failed", code: "invalid", reason: null };
    });
    if (done.kind === "done") {
      const result = done.result as InventoryCreateResult | null;
      if (result && "ledger" in result && result.ledger)
        setLastBook(result.ledger);
      setTask(null);
    }
    reload();
  };
  const runPreview = async (target: InventoryBookRow) => {
    setPreview(
      await setupCall(
        port,
        "ledger.inventory.valuation.preview",
        { actividad_id: target.actividad_id, year },
        false,
      ),
    );
  };
  const refusal = () => {
    const last = write.last?.kind === "refused" ? write.last : preview;
    if (last?.kind !== "refused") return null;
    const found = (last.detail as { refusal?: InventoryRefusal | null } | null)
      ?.refusal;
    return found ? t(`desktop.ledger.inventory.refusal.${found.reason}`) : null;
  };

  const columns: Column<InventoryBookRow>[] = [
    {
      key: "actividad",
      label: t("desktop.ledger.inventory.column.actividad"),
      cell: (row) => <code className="font-mono">{row.actividad_id}</code>,
    },
    {
      key: "method",
      label: t("desktop.ledger.inventory.column.method"),
      cell: (row) => tokenText(t, "inventory.method", row.valuation_method),
    },
    {
      key: "opening",
      label: t("desktop.ledger.inventory.column.opening"),
      numeric: true,
      cell: (row) => amountText(locale, row.opening_stock.decimal),
    },
    {
      key: "movements",
      label: t("desktop.ledger.inventory.column.movements"),
      numeric: true,
      cell: (row) => row.movement_count,
    },
    {
      key: "actions",
      label: t("desktop.ledger.form.actions"),
      hidden: true,
      cell: (row) => (
        <span className="flex justify-end">
          <Button
            size="xs"
            variant="ghost"
            className="ledger-inventory-preview"
            onClick={() => {
              setChosen(row.actividad_id);
              void runPreview(row);
            }}
          >
            {t("desktop.ledger.inventory.preview")}
          </Button>
        </span>
      ),
    },
  ];
  const shownMovements =
    lastBook &&
    book &&
    lastBook.actividad_id === book.actividad_id &&
    lastBook.year === year
      ? lastBook.period_movements
      : null;
  const valued = preview?.kind === "done" ? preview.result.preview : null;

  return (
    <Panel
      title={t("desktop.ledger.inventory.title")}
      actions={
        <PeriodSelector
          value={{ year, code: "0A" }}
          onChange={(next) => {
            if (!next) return;
            setYear(next.year);
            setPreview(null);
          }}
          label={t("desktop.ledger.inventory.year")}
          years={years}
          locale={locale}
          fallbackYear={fallbackYear}
          mode="year"
          allowAll={false}
        />
      }
    >
      {read === null ? (
        <Reading label={t("desktop.ledger.form.reading")} />
      ) : read.kind !== "done" ? (
        <CallLine call={read} />
      ) : books.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          {t("desktop.ledger.inventory.empty", { year })}
        </p>
      ) : (
        <SetupTable
          label={t("desktop.ledger.inventory.books", { year })}
          rows={books}
          rowKey={(row) => row.actividad_id}
          selected={book?.actividad_id ?? null}
          columns={columns}
          className="ledger-inventory-table"
        />
      )}
      {valued && (
        <Alert
          icon={<Icon name="info" />}
          className="ledger-inventory-valuation"
        >
          <span className="font-medium tabular-nums">
            {t("desktop.ledger.inventory.valuation", {
              closing: amountText(locale, valued.derived_closing_value.decimal),
              cogs: amountText(locale, valued.cogs.decimal),
              method: tokenText(t, "inventory.method", valued.valuation_method),
            })}
          </span>
          <span className="text-sm">
            {t("desktop.ledger.inventory.preview_note")}
          </span>
        </Alert>
      )}
      {shownMovements && shownMovements.length > 0 && (
        <SetupTable<InventoryMovement>
          label={t("desktop.ledger.inventory.movements")}
          rows={shownMovements}
          rowKey={(movement) => movement.movement_id}
          columns={[
            {
              key: "date",
              label: t("desktop.ledger.inventory.column.date"),
              cell: (movement) =>
                dateText(locale, movement.movement_date, true),
            },
            {
              key: "kind",
              label: t("desktop.ledger.inventory.column.kind"),
              cell: (movement) => tokenText(t, "inventory.kind", movement.kind),
            },
            {
              key: "quantity",
              label: t("desktop.ledger.inventory.column.quantity"),
              numeric: true,
              cell: (movement) => movement.quantity.decimal,
            },
            {
              key: "unit",
              label: t("desktop.ledger.inventory.column.unit_cost"),
              numeric: true,
              cell: (movement) => movement.unit_cost?.decimal ?? "—",
            },
          ]}
        />
      )}
      <div className="flex flex-wrap gap-1">
        {(["create", "movement", "closing"] as const).map((value) => (
          <Button
            key={value}
            size="xs"
            variant={task === value ? "secondary" : "outline"}
            aria-pressed={task === value}
            className={`ledger-inventory-${value}`}
            aria-disabled={(value !== "create" && !book) || undefined}
            onClick={() => (value === "create" || book) && start(value)}
          >
            {t(`desktop.ledger.inventory.task.${value}`)}
          </Button>
        ))}
      </div>
      {task && (
        <form
          className="ledger-inventory-form flex flex-col gap-3 rounded-md bg-accent p-3"
          onSubmit={(event) => {
            event.preventDefault();
            if (!write.busy) void send();
          }}
        >
          <h4 className="font-medium">
            {task === "create"
              ? t("desktop.ledger.inventory.form.create", { year })
              : t(`desktop.ledger.inventory.form.${task}`, {
                  actividad: book?.actividad_id ?? "",
                  year,
                })}
          </h4>
          {task === "create" && (
            <FormGrid>
              <TextField
                label={t("desktop.ledger.inventory.actividad")}
                value={actividad}
                onValue={setActividad}
                mono
                required
                autoFocus
              />
              <ChoiceField
                label={t("desktop.ledger.inventory.method_label")}
                value={method}
                onValue={setMethod}
                placeholder={t("desktop.ledger.form.choose")}
                options={METHODS.map((value) => ({
                  value,
                  label: tokenText(t, "inventory.method", value),
                }))}
              />
              <TextField
                label={t("desktop.ledger.inventory.opening")}
                value={opening}
                onValue={setOpening}
                inputMode="decimal"
                hint={t("desktop.ledger.form.amount_hint")}
                error={refusedText(openingParsed)}
                required
              />
            </FormGrid>
          )}
          {task === "movement" && (
            <FormGrid>
              {books.length > 1 && (
                <ChoiceField
                  label={t("desktop.ledger.inventory.book")}
                  value={book?.actividad_id ?? ""}
                  onValue={setChosen}
                  options={books.map((found) => ({
                    value: found.actividad_id,
                    label: found.actividad_id,
                  }))}
                />
              )}
              <TextField
                label={t("desktop.ledger.inventory.movement_id")}
                value={movementId}
                onValue={setMovementId}
                mono
                maxLength={64}
                required
                autoFocus
              />
              <TextField
                label={t("desktop.ledger.inventory.date")}
                value={movementDate}
                onValue={setMovementDate}
                hint={t("desktop.ledger.form.date_hint")}
                error={refusedText(dateParsed)}
                required
              />
              <ChoiceField
                label={t("desktop.ledger.inventory.kind_label")}
                value={kind}
                onValue={setKind}
                placeholder={t("desktop.ledger.form.choose")}
                options={KINDS.map((value) => ({
                  value,
                  label: tokenText(t, "inventory.kind", value),
                }))}
              />
              <TextField
                label={t("desktop.ledger.inventory.quantity")}
                value={quantity}
                onValue={setQuantity}
                inputMode="decimal"
                error={refusedText(quantityParsed)}
                required
              />
              <TextField
                label={t("desktop.ledger.inventory.unit_cost")}
                value={unitCost}
                onValue={setUnitCost}
                inputMode="decimal"
                error={refusedText(unitParsed)}
              />
              <TextField
                label={t("desktop.ledger.inventory.base")}
                value={base}
                onValue={setBase}
                inputMode="decimal"
                error={refusedText(baseParsed)}
              />
            </FormGrid>
          )}
          {task === "closing" && (
            <JsonDocumentField
              label={t("desktop.ledger.inventory.authority")}
              value={authority}
              onValue={setAuthority}
              hint={t("desktop.ledger.inventory.authority_hint")}
              error={
                record.kind === "refused"
                  ? t("desktop.ledger.inventory.authority_unread")
                  : null
              }
            />
          )}
          <div className="flex gap-2">
            <Button
              type="button"
              size="sm"
              variant="ghost"
              onClick={() => setTask(null)}
            >
              {t("desktop.ledger.form.cancel")}
            </Button>
            <Button
              type="submit"
              size="sm"
              className="ledger-inventory-submit"
              aria-disabled={!ready || write.busy || undefined}
            >
              {write.busy
                ? t("desktop.ledger.form.saving")
                : t(`desktop.ledger.inventory.task.${task}`)}
            </Button>
          </div>
        </form>
      )}
      <CallLine
        call={write.last ?? preview}
        refusal={refusal}
        onReread={reload}
      />
    </Panel>
  );
}
