import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { cn } from "@/components/ui/cn";
import {
  Field,
  FieldDescription,
  FieldError,
  FieldLabel,
} from "@/components/ui/field";
import { Icon } from "@/components/ui/icon";
import { Input } from "@/components/ui/input";
import { NativeSelect } from "@/components/ui/native-select";
import { Spinner } from "@/components/ui/spinner";
import { useTableView, type SortValue } from "@/components/ui/table-view";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import type {
  LedgerDefinitionId,
  LedgerPort,
  LedgerRequest,
  LedgerResult,
} from "../../../shell/ledger";
import { useNavigationGuard } from "../../../shell/navigation/hooks";
import { useStrings } from "../../../shell/strings";
import {
  landingSettle,
  useWritePause,
  type Landing,
  type LandingCheck,
} from "../WritePause";
import { setupCall, type SetupCall } from "./setupModel";
import { callText } from "./setupWords";

/**
 * A titled part of a Setup section: its heading, the controls that act on
 * all of it, and its body. The danger variant edges a destructive part so
 * it is told apart without colour alone.
 */
export function Panel({
  title,
  actions,
  children,
  tone,
  className,
  open,
  onOpen,
}: {
  title: string;
  actions?: ReactNode;
  children: ReactNode;
  tone?: "danger";
  className?: string;
  /** Given, the title opens and closes the panel's content. */
  open?: boolean;
  onOpen?: (open: boolean) => void;
}) {
  const heading = useId();
  const content = useId();
  const folds = open !== undefined && onOpen !== undefined;
  const mark = tone === "danger" && (
    <Icon name="alert" size="sm" className="text-destructive" />
  );
  return (
    <section
      aria-labelledby={heading}
      className={cn(
        "flex flex-col gap-3 rounded-lg bg-card p-3 shadow-raised",
        tone === "danger" && "border border-destructive shadow-none",
        className,
      )}
    >
      <div className="flex flex-wrap items-center gap-2">
        <h3 id={heading} className="flex items-center gap-1.5 font-medium">
          {folds ? (
            <Button
              variant="ghost"
              size="sm"
              className="-mx-2 font-medium"
              aria-expanded={open}
              aria-controls={content}
              onClick={() => onOpen(!open)}
            >
              {mark}
              {title}
              <Icon name={open ? "chevronUp" : "chevronDown"} size="sm" />
            </Button>
          ) : (
            <>
              {mark}
              {title}
            </>
          )}
        </h3>
        <span className="flex-1" />
        {actions}
      </div>
      {folds ? (
        <div id={content} hidden={!open} className="flex flex-col gap-3">
          {children}
        </div>
      ) : (
        children
      )}
    </section>
  );
}

/** The Ledger section a Setup form is drawn in, by its register id: what a
 * navigation that leaves the section would take down. */
const SetupOwner = createContext("ledger");

/** The sub-areas of a Setup section, as a tab row. `owner` is the section's
 * register id, which the forms inside weigh their work under. */
export function SetupTabs<Value extends string>({
  label,
  owner,
  value,
  onValue,
  tabs,
  children,
}: {
  label: string;
  owner: string;
  value: Value;
  onValue(value: Value): void;
  tabs: readonly { value: Value; label: string }[];
  children: ReactNode;
}) {
  return (
    <Tabs
      value={value}
      onValueChange={(next) => onValue(next as Value)}
      className="flex min-h-0 flex-1 flex-col"
    >
      <TabsList
        aria-label={label}
        className="h-control-md shrink-0 overflow-x-auto px-3"
      >
        {tabs.map((tab) => (
          <TabsTrigger
            key={tab.value}
            value={tab.value}
            className="shrink-0 text-sm"
          >
            {tab.label}
          </TabsTrigger>
        ))}
      </TabsList>
      <TabsContent
        value={value}
        className="flex flex-col gap-3 overflow-y-auto p-3"
      >
        <SetupOwner.Provider value={owner}>{children}</SetupOwner.Provider>
      </TabsContent>
    </Tabs>
  );
}

export type Column<Row> = {
  key: string;
  label: string;
  /** The header is read, not shown: an actions column. */
  hidden?: boolean;
  numeric?: boolean;
  /** What ranks a row by this column; leave it out where rows are not
   * ranked, as in an actions column or free text. Absent values are null. */
  sort?(row: Row): SortValue;
  /** False where the column is only buttons and stays as wide as it is. */
  resizable?: boolean;
  cell(row: Row): ReactNode;
};

/** A decimal string as a number to rank rows by; null where it is absent or
 * not a number. */
export function rankDecimal(value: string | null | undefined): number | null {
  if (value === null || value === undefined || value.trim() === "") return null;
  const ranked = Number(value);
  return Number.isFinite(ranked) ? ranked : null;
}

/** A small register's rows, with a header a screen reader names. */
export function SetupTable<Row>({
  label,
  rows,
  rowKey,
  columns,
  className,
  selected,
}: {
  label: string;
  rows: readonly Row[];
  rowKey(row: Row): string;
  columns: readonly Column<Row>[];
  className?: string;
  selected?: string | null;
}) {
  const t = useStrings();
  const view = useTableView<Row>({
    columns: useMemo(
      () =>
        columns.map((column) => ({
          id: column.key,
          label: column.label,
          name: column.label,
          align: column.numeric ? ("end" as const) : ("start" as const),
          sortValue: column.sort,
          hidden: column.hidden,
          resizable: column.hidden ? false : column.resizable,
        })),
      [columns],
    ),
    rows,
    resizeLabel: (column) => t("desktop.table.resize_column", { column }),
  });
  return (
    <div
      role="group"
      className="overflow-x-auto"
      tabIndex={0}
      aria-label={label}
    >
      <table {...view.tableProps} className={cn("w-full text-sm", className)}>
        <caption className="sr-only">{label}</caption>
        <thead>
          <tr className="text-left text-muted-foreground">{view.headers}</tr>
        </thead>
        <tbody>
          {view.rows.map((row) => {
            const key = rowKey(row);
            return (
              <tr
                key={key}
                aria-current={selected === key ? "true" : undefined}
                className={cn(
                  "border-t border-border align-top",
                  selected === key && "bg-selected",
                )}
              >
                {columns.map((column) => (
                  <td
                    key={column.key}
                    className={cn(
                      "px-2 py-1.5 [overflow-wrap:anywhere]",
                      column.numeric && "text-right tabular-nums",
                    )}
                  >
                    {column.cell(row)}
                  </td>
                ))}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

/** How a call ended where it did not succeed: a refusal or a failure in
 * a line, an unknown write, or a saved one whose answer was not read, with
 * the page's re-read that settles it. */
export function CallLine<R>({
  call,
  refusal,
  onReread,
}: {
  call: SetupCall<R> | null;
  refusal?: (reason: string | null) => string | null;
  onReread?: () => void;
}) {
  const t = useStrings();
  const pause = useWritePause();
  const said = callText(t, call, refusal);
  if (said === null) return null;
  const undetermined =
    call?.kind === "unknown" || call?.kind === "saved_unread";
  // While the page holds this write, its re-read is the page's.
  const reread =
    undetermined && pause.writes.length > 0 ? pause.reread : onReread;
  return (
    <Alert
      tone={undetermined ? "warning" : "danger"}
      role="alert"
      icon={<Icon name={undetermined ? "unknown" : "refused"} />}
      className="setup-call-line"
    >
      <span>
        {said}
        {undetermined && reread && (
          <>
            {" "}
            <Button
              variant="link"
              size="xs"
              className="setup-call-reread"
              aria-disabled={pause.rereading || undefined}
              onClick={() => {
                if (!pause.rereading) reread();
              }}
            >
              {t("desktop.ledger.form.reread")}
            </Button>
          </>
        )}
      </span>
    </Alert>
  );
}

/** A labelled text field with its hint and the reason it was refused. */
export function TextField({
  label,
  value,
  onValue,
  hint,
  error,
  required,
  className,
  mono,
  type = "text",
  inputMode,
  maxLength,
  autoFocus,
  name,
}: {
  label: string;
  value: string;
  onValue(value: string): void;
  hint?: string;
  error?: string | null;
  required?: boolean;
  className?: string;
  mono?: boolean;
  type?: "text" | "password";
  inputMode?: "decimal" | "numeric" | "text";
  maxLength?: number;
  autoFocus?: boolean;
  name?: string;
}) {
  const id = useId();
  const hintId = `${id}-hint`;
  const errorId = `${id}-error`;
  return (
    <Field data-invalid={error ? true : undefined} className={className}>
      <FieldLabel htmlFor={id}>{label}</FieldLabel>
      <Input
        id={id}
        name={name}
        type={type}
        autoComplete="off"
        spellCheck={false}
        value={value}
        required={required}
        aria-required={required || undefined}
        aria-invalid={error ? true : undefined}
        aria-describedby={
          [hint ? hintId : null, error ? errorId : null]
            .filter(Boolean)
            .join(" ") || undefined
        }
        inputMode={inputMode}
        maxLength={maxLength}
        autoFocus={autoFocus}
        className={mono ? "font-mono" : undefined}
        onChange={(event) => onValue(event.target.value)}
      />
      {hint && <FieldDescription id={hintId}>{hint}</FieldDescription>}
      <FieldError id={errorId}>{error}</FieldError>
    </Field>
  );
}

/** A labelled choice from a closed list. Nothing is chosen until the
 * person chooses, unless `value` says so. */
export function ChoiceField({
  label,
  value,
  onValue,
  options,
  placeholder,
  hint,
  className,
  required,
  error,
}: {
  label: string;
  value: string;
  onValue(value: string): void;
  options: readonly { value: string; label: string }[];
  placeholder?: string;
  hint?: string;
  className?: string;
  /** The choice must be made before the form can be sent. */
  required?: boolean;
  /** Why the choice was not accepted, or what is still to choose. */
  error?: string | null;
}) {
  const id = useId();
  const describedBy =
    [hint ? `${id}-hint` : null, error ? `${id}-error` : null]
      .filter(Boolean)
      .join(" ") || undefined;
  return (
    <Field data-invalid={error ? true : undefined} className={className}>
      <FieldLabel htmlFor={id}>{label}</FieldLabel>
      <NativeSelect
        id={id}
        value={value}
        required={required}
        aria-required={required || undefined}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy}
        onChange={(event) => onValue(event.target.value)}
      >
        {placeholder !== undefined && (
          <option value="" disabled>
            {placeholder}
          </option>
        )}
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </NativeSelect>
      {hint && <FieldDescription id={`${id}-hint`}>{hint}</FieldDescription>}
      <FieldError id={`${id}-error`}>{error}</FieldError>
    </Field>
  );
}

/** A form's fields in a grid that folds to one column. */
export function FormGrid({ children }: { children: ReactNode }) {
  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
      {children}
    </div>
  );
}

/** Something being read: a spinner and what it reads. */
export function Reading({ label }: { label: string }) {
  return (
    <p
      role="status"
      className="flex items-center gap-2 text-sm text-muted-foreground"
    >
      <Spinner />
      {label}
    </p>
  );
}

/**
 * Reads one Setup operation while the section shows, again when `key`
 * changes or on `reload`, and drops what it read with the profile. A read
 * that a later one replaced is never shown.
 */
export function useSetupRead<D extends LedgerDefinitionId>(
  port: LedgerPort,
  reader: string | null,
  definition: D,
  payload: LedgerRequest<D> | null,
  key: string,
): {
  read: SetupCall<LedgerResult<D>> | null;
  reload(): void;
} {
  const [read, setRead] = useState<SetupCall<LedgerResult<D>> | null>(null);
  const [round, setRound] = useState(0);
  // The page's re-read after a write it could not settle reads this again.
  const { round: reread } = useWritePause();
  const latest = useRef(payload);
  latest.current = payload;
  useEffect(() => {
    setRead(null);
    const asked = latest.current;
    if (reader === null || asked === null) return;
    let active = true;
    void setupCall(port, definition, asked, false).then((answer) => {
      if (active) setRead(answer);
    });
    return () => {
      active = false;
    };
  }, [port, reader, definition, key, round, reread]);
  const reload = useCallback(() => setRound((value) => value + 1), []);
  return { read, reload };
}

/** A landing check that reads one Setup operation and judges what it
 * answered; null while it did not answer. */
export function readLanding<D extends LedgerDefinitionId>(
  port: LedgerPort,
  definition: D,
  payload: LedgerRequest<D>,
  judge: (result: LedgerResult<D>) => Landing,
): LandingCheck {
  return async () => {
    const read = await setupCall(port, definition, payload, false);
    return read.kind === "done" ? judge(read.result) : null;
  };
}

/** The landing of a call that writes nothing: sent again, it is the same
 * read. */
export const READ_ONLY: LandingCheck = async () => "repeatable";

/** Typed values of a Setup form not yet written: a navigation that leaves
 * the section asks before they go. */
export function useSetupDraft(drafted: boolean): void {
  useNavigationGuard(useContext(SetupOwner), drafted ? "dirty" : "clean");
}

/** A write in flight and how the last one ended, for one form. A write
 * whose outcome was not seen, or whose answer was not read, holds every
 * write on the page under `what` until the page's re-read reads, through
 * the write's own `landed`, what it wrote; the form's line about it goes
 * once that read settled it, so the form's send stays held until then. A
 * navigation that leaves the section is refused while the write is in
 * flight; `owner` names the section where it is not drawn inside
 * `SetupTabs`. */
export function useSetupWrite(what: string, owner?: string) {
  const t = useStrings();
  const { hold } = useWritePause();
  const [busy, setBusy] = useState(false);
  const section = useContext(SetupOwner);
  useNavigationGuard(owner ?? section, busy ? "busy" : "clean");
  const [last, setLast] = useState<SetupCall<unknown> | null>(null);
  const run = useCallback(
    async <R,>(
      write: () => Promise<SetupCall<R>>,
      landed: LandingCheck,
    ): Promise<SetupCall<R>> => {
      setBusy(true);
      setLast(null);
      try {
        const done = await write();
        setLast(done);
        if (done.kind === "unknown" || done.kind === "saved_unread")
          hold({
            what,
            outcome: done.kind,
            settle: landingSettle(t, what, landed),
            onSettled: () => setLast(null),
          });
        return done;
      } finally {
        setBusy(false);
      }
    },
    [hold, what, t],
  );
  return { busy, last, run, clear: () => setLast(null) };
}
