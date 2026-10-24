import {
  useEffect,
  useRef,
  useState,
  type KeyboardEvent,
  type ReactNode,
} from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/components/ui/cn";
import { Icon } from "@/components/ui/icon";
import { Input } from "@/components/ui/input";
import {
  Popover,
  PopoverAnchor,
  PopoverContent,
} from "@/components/ui/popover";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import type {
  FormBlock,
  FormField,
  FormSection,
  GridCell,
  Intent,
} from "./types";
import {
  calm,
  dateWords,
  display,
  editing,
  holdsValue,
  money,
  originWords,
  periodWords,
  SURFACE_WORD,
  TONE_TEXT,
} from "./vocabulary";
import { w } from "./words";

// The form as a document: the official sections in order, each box on one
// line with its printed number, its words, its value and where the value
// comes from. Grids keep the official rows and columns; repeated records are
// tables. Nothing here knows which modelo it draws, and nothing here decides
// a box's state: the origin the application reports decides how it reads.

/** Edits made here and not saved, keyed by the address the edit contract
 * takes (see `editKey`), each with what the box held before. */
export type Staged = Record<string, { intent: Intent; was: string }>;

export type FieldFilter = "all" | "todo" | "mine";

export const fieldKey = (f: FormField) =>
  f.address.kind === "casilla"
    ? `c:${f.address.casilla_id}`
    : `b:${f.address.binding_id}`;

/** The address an edit of this box is submitted to: a value that comes from
 * a source is replaced at the binding that feeds the box, as the
 * application's `edit_address` says; any other box at its own address. */
export const editKey = (f: FormField) =>
  (f.editability === "overridable_source" ||
    f.editability === "editable_override") &&
  f.bindings[0]
    ? `b:${f.bindings[0].binding_id}`
    : fieldKey(f);

/** The contract intent for what was typed into a box, or the catalogue key
 * of why it cannot be staged. */
export function intentFor(
  f: FormField,
  text: string,
): Intent | { refused: string } {
  const atBinding = editKey(f) !== fieldKey(f);
  if (text.trim())
    return atBinding
      ? { kind: "set_override_value", text: text.trim() }
      : { kind: "set_typed_value", text: text.trim() };
  if (atBinding || f.origin !== "entered")
    return { refused: "workspace.modelo.stage_refused.nothing_to_clear" };
  return { kind: "clear_declared_value" };
}

/** Giving a box back to its source, at the address its edit takes. */
export const restoreIntent = (f: FormField): Intent =>
  editKey(f) !== fieldKey(f)
    ? { kind: "remove_override" }
    : { kind: "restore_source_value" };

/** Boxes the filer must act on: a value is wanted, an assumed value waits
 * for confirmation, or the calculation could not work the box out. */
export const isTodo = (f: FormField) =>
  f.origin === "needs_input" ||
  f.origin === "default_to_confirm" ||
  f.origin === "calculation_failed";

export function matches(field: FormField, filter: FieldFilter, query: string) {
  const byFilter =
    filter === "all" ||
    (filter === "todo" && isTodo(field)) ||
    (filter === "mine" &&
      (field.origin === "entered" || field.origin === "overrides_source"));
  if (!byFilter) return false;
  const q = query.trim().toLowerCase();
  if (!q) return true;
  return (
    (field.box ?? "") === q.replace(/^\[|\]$/g, "") ||
    field.label.text.toLowerCase().includes(q)
  );
}

/** The box number as printed on the official form; nothing when it has none. */
export function BoxNumber({
  box,
  size = "md",
}: {
  box: string | null;
  size?: "sm" | "md";
}) {
  if (!box) return null;
  return (
    <span
      className={cn(
        "inline-flex shrink-0 items-center justify-center rounded-sm border border-border-strong font-mono text-muted-foreground tabular-nums",
        size === "md"
          ? "h-6 min-w-10 px-1 text-sm"
          : "h-5 min-w-8 px-0.5 text-xs",
      )}
    >
      {box}
    </span>
  );
}

/** Origins whose value is a fact worth printing. */
const SHOWS_VALUE = new Set([
  "imported",
  "calculated",
  "entered",
  "overrides_source",
  "default_to_confirm",
  "informational",
  "cleared",
]);

const shows = (f: FormField) =>
  SHOWS_VALUE.has(f.origin) || (f.origin === "optional_empty" && holdsValue(f));

/** What a box holds as a value, or "" when it holds none: never the words a
 * value cell shows in place of a missing value. */
export function heldValue(field: FormField, locale: string): string {
  return shows(field) ? display(field, locale) : "";
}

/** A staged edit as the box will read: the text as typed, formatted when it
 * reads as an amount; the application parses it when the edits are checked. */
export function stagedWords(f: FormField, intent: Intent, locale: string) {
  switch (intent.kind) {
    case "set_typed_value":
    case "set_override_value":
      // Shown as typed: the application reads it when the edits are checked.
      return "confirms" in intent && intent.confirms
        ? display(f, locale)
        : intent.text;
    case "clear_declared_value":
      return w("workspace.modelo.staged.clear", locale);
    case "restore_source_value":
    case "remove_override":
      return w("workspace.modelo.staged.restore", locale);
  }
}

export function valueWords(
  field: FormField,
  locale: string,
  staged?: Staged[string],
  uncalculated = false,
) {
  if (staged)
    return {
      text: stagedWords(field, staged.intent, locale),
      tone: "text-foreground",
    };
  if (shows(field)) {
    const text = display(field, locale);
    if (text) return { text, tone: "text-foreground" };
  }
  switch (field.origin) {
    case "needs_input":
      return { text: "", tone: "" };
    case "calculation_failed":
      return {
        text: w("workspace.modelo.origin.calculation_failed", locale),
        tone: "text-destructive",
      };
    case "not_calculated_yet":
    case "not_imported_yet":
      return {
        text: uncalculated
          ? "—"
          : w(`workspace.modelo.origin.${field.origin}`, locale),
        tone: "text-faint",
      };
    case "not_applicable":
      return { text: "", tone: "" };
    default:
      return { text: "—", tone: "text-faint" };
  }
}

function OriginMark({
  field,
  staged,
  locale,
}: {
  field: FormField;
  staged: Staged[string] | undefined;
  locale: string;
}) {
  if (staged)
    return (
      <span className="inline-flex items-center gap-1 text-sm text-foreground">
        <Icon name="edit" size="xs" />
        {staged.intent.kind === "restore_source_value" ||
        staged.intent.kind === "remove_override"
          ? w("workspace.modelo.staged.restore", locale)
          : "Changed, not applied"}
      </span>
    );
  const o = originWords(field, locale);
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 text-sm",
        TONE_TEXT[o.tone],
      )}
    >
      <Icon name={o.icon} size="xs" />
      {o.word}
    </span>
  );
}

/** Typing a value. Enter keeps it and moves down, Tab keeps it and lets the
 * focus go on, Escape leaves it. The text is kept as typed; the application
 * reads it when the edits are checked before saving. */
function ValueEditor({
  field,
  initial,
  onDone,
}: {
  field: FormField;
  initial: string;
  onDone: (text: string | null, advance: boolean) => void;
}) {
  const [text, setText] = useState(initial);
  const ref = useRef<HTMLInputElement>(null);
  useEffect(() => ref.current?.select(), []);
  const numeric = ["money", "integer", "decimal", "ratio"].includes(
    field.data_type,
  );
  const onKey = (event: KeyboardEvent) => {
    event.stopPropagation();
    if (event.key === "Enter") {
      event.preventDefault();
      onDone(text, true);
    }
    if (event.key === "Tab") onDone(text, false);
    if (event.key === "Escape") onDone(null, false);
  };
  return (
    <Input
      ref={ref}
      controlSize="sm"
      value={text}
      onChange={(e) => setText(e.target.value)}
      onKeyDown={onKey}
      onBlur={() => onDone(text, false)}
      inputMode={numeric ? "decimal" : "text"}
      className={cn("w-40", numeric && "text-right tabular-nums")}
      aria-label={`Box ${field.box ?? ""}: new value`}
    />
  );
}

/** Asked before a value from a source is replaced: fixing it where it comes
 * from is the better way; replacing it here is said plainly. */
function ReplaceSource({
  field,
  locale,
  children,
  open,
  onOpenChange,
  onReplace,
}: {
  field: FormField;
  locale: string;
  children: ReactNode;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onReplace: () => void;
}) {
  const surface = field.bindings[0]?.policy.surface;
  const o = originWords(field, locale);
  return (
    <Popover open={open} onOpenChange={onOpenChange}>
      <PopoverAnchor asChild>{children}</PopoverAnchor>
      <PopoverContent align="end" className="flex w-80 flex-col gap-3">
        <p className="text-base">
          <span className="font-medium tabular-nums">
            {display(field, locale) || "—"}
          </span>{" "}
          · {o.word}
        </p>
        <p className="text-sm text-muted-foreground">
          {w(
            "workspace.modelo.legend.meaning.origin.overrides_source",
            locale,
          )}
        </p>
        <div className="flex flex-col gap-2">
          {surface && SURFACE_WORD[surface] && (
            <Button variant="primary" size="sm" className="justify-start">
              <Icon name="forward" size="xs" />
              {SURFACE_WORD[surface]} and correct it there
            </Button>
          )}
          <Button
            variant="outline"
            size="sm"
            className="justify-start"
            onClick={onReplace}
            autoFocus={!surface}
          >
            <Icon name="swap" size="xs" />
            Replace it in this declaration only
          </Button>
        </div>
      </PopoverContent>
    </Popover>
  );
}

type CellProps = {
  field: FormField;
  locale: string;
  staged: Staged[string] | undefined;
  editingNow: boolean;
  setEditing: (on: boolean) => void;
  onStage: (text: string, advance: boolean) => void;
  uncalculated: boolean;
  align?: "row" | "grid";
};

/** The value of one box, and the one way to change it: click it, or Enter
 * on its row. A value from a source asks first. */
function ValueCell({
  field,
  locale,
  staged,
  editingNow,
  setEditing,
  onStage,
  uncalculated,
  align = "row",
}: CellProps) {
  const [replacing, setReplacing] = useState(false);
  const { editable } = editing(field, locale);
  const fromSource =
    field.editability === "overridable_source" &&
    field.origin !== "not_applicable" &&
    !staged;
  const open = editable && field.origin !== "not_applicable";
  const words = valueWords(field, locale, staged, uncalculated);
  if (editingNow && (!fromSource || replacing))
    return (
      <ValueEditor
        field={field}
        initial={
          staged
            ? stagedWords(field, staged.intent, locale)
            : heldValue(field, locale)
        }
        onDone={(text, advance) => {
          setEditing(false);
          setReplacing(false);
          if (text !== null) onStage(text, advance);
        }}
      />
    );
  const face = (
    <button
      type="button"
      tabIndex={-1}
      disabled={!open}
      onClick={(e) => {
        e.stopPropagation();
        setEditing(true);
      }}
      className={cn(
        "flex h-control-sm min-w-32 items-center justify-end rounded-md px-2 text-base tabular-nums disabled:cursor-default",
        align === "grid" && "w-full",
        open &&
          "cursor-text border border-input bg-card hover:border-border-strong",
        field.origin === "needs_input" && !staged && "border-warning",
        staged && "border-foreground bg-selected",
        words.tone,
      )}
    >
      {words.text}
    </button>
  );
  if (!fromSource) return face;
  return (
    <ReplaceSource
      field={field}
      locale={locale}
      open={editingNow && !replacing}
      onOpenChange={(o) => !o && setEditing(false)}
      onReplace={() => setReplacing(true)}
    >
      {face}
    </ReplaceSource>
  );
}

type RowProps = {
  field: FormField;
  locale: string;
  selected: boolean;
  staged: Staged[string] | undefined;
  editingNow: boolean;
  setEditing: (on: boolean) => void;
  onSelect: () => void;
  onStage: (text: string, advance: boolean) => void;
  onConfirm: (() => void) | null;
  uncalculated: boolean;
};

export function FieldRow({
  field,
  locale,
  selected,
  staged,
  editingNow,
  setEditing,
  onSelect,
  onStage,
  onConfirm,
  uncalculated,
}: RowProps) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (
      selected &&
      !editingNow &&
      ref.current?.closest("[role=grid]")?.contains(document.activeElement)
    )
      ref.current?.focus({ preventScroll: true });
  }, [selected, editingNow]);
  const label = calm(field.label.text);
  return (
    <div
      ref={ref}
      role="row"
      aria-selected={selected}
      data-key={fieldKey(field)}
      tabIndex={selected ? 0 : -1}
      onClick={onSelect}
      onFocus={onSelect}
      className={cn(
        "group grid min-h-11 cursor-default grid-cols-[--spacing(10)_minmax(0,1fr)_auto_--spacing(44)] items-center gap-3 rounded-md px-2 py-1 outline-none",
        "hover:bg-accent focus-visible:ring-2 focus-visible:ring-ring aria-selected:bg-selected",
        field.origin === "not_applicable" && "text-muted-foreground",
      )}
    >
      <span role="cell">
        <BoxNumber box={field.box} />
      </span>
      <span role="cell" className="min-w-0 text-base leading-snug">
        {label}
        {field.label.disclosure !== "localized" && locale !== "es" && (
          <span className="ml-1.5 text-xs text-faint">
            (
            {w(
              `workspace.modelo.disclosure.${field.label.disclosure}`,
              locale,
            )}
            )
          </span>
        )}
      </span>
      <span role="cell" className="flex justify-end">
        <ValueCell
          field={field}
          locale={locale}
          staged={staged}
          editingNow={editingNow}
          setEditing={setEditing}
          onStage={onStage}
          uncalculated={uncalculated}
        />
      </span>
      <span role="cell" className="flex min-w-0 flex-col items-start gap-0.5">
        <OriginMark field={field} staged={staged} locale={locale} />
        {staged && (
          <span className="text-xs text-faint tabular-nums">
            {w("workspace.modelo.was", locale, {
              value: staged.was || "—",
            })}
          </span>
        )}
        {!staged && onConfirm && (
          <Button
            size="xs"
            variant="outline"
            onClick={(e) => {
              e.stopPropagation();
              onConfirm();
            }}
          >
            <Icon name="tick" size="xs" />
            Confirm
          </Button>
        )}
      </span>
    </div>
  );
}

function GridValue({
  cell,
  selected,
  onSelect,
  ...p
}: Omit<CellProps, "field" | "align"> & {
  cell: GridCell;
  selected: boolean;
  onSelect: () => void;
}) {
  if (cell.kind === "blank" || !cell.field) return <td className="p-1" />;
  const f = cell.field;
  if (cell.kind === "design_constant") {
    const text = display(f, p.locale);
    return (
      <td className="px-3 py-2 text-right align-middle">
        <Tooltip>
          <TooltipTrigger asChild>
            <span className="inline-flex items-center gap-1.5 text-base text-muted-foreground tabular-nums">
              <BoxNumber box={f.box} size="sm" />
              {text || "—"}
            </span>
          </TooltipTrigger>
          <TooltipContent>
            {w("workspace.modelo.rate.printed_by_form", p.locale)}
          </TooltipContent>
        </Tooltip>
      </td>
    );
  }
  return (
    <td
      className={cn("p-1 align-middle", selected && "bg-selected")}
      onClick={onSelect}
      aria-label={`Box ${f.box}`}
    >
      <div className="flex items-center justify-end gap-2">
        <BoxNumber box={f.box} size="sm" />
        <ValueCell field={f} {...p} align="grid" />
      </div>
    </td>
  );
}

export type BlockProps = {
  locale: string;
  selectedKey: string | null;
  editingKey: string | null;
  staged: Staged;
  filter: FieldFilter;
  query: string;
  uncalculated: boolean;
  onSelect: (field: FormField) => void;
  setEditingKey: (key: string | null) => void;
  onType: (field: FormField, text: string, advance: boolean) => void;
  onConfirm: (field: FormField) => void;
  canConfirm: (field: FormField) => boolean;
};

function Row({ f, ...p }: BlockProps & { f: FormField }) {
  const key = fieldKey(f);
  return (
    <FieldRow
      field={f}
      locale={p.locale}
      selected={p.selectedKey === key}
      staged={p.staged[editKey(f)]}
      editingNow={p.editingKey === key}
      setEditing={(on) => p.setEditingKey(on ? key : null)}
      onSelect={() => p.onSelect(f)}
      onStage={(text, advance) => p.onType(f, text, advance)}
      onConfirm={p.canConfirm(f) ? () => p.onConfirm(f) : null}
      uncalculated={p.uncalculated}
    />
  );
}

function Block({ block, ...p }: BlockProps & { block: FormBlock }) {
  switch (block.kind) {
    case "field":
      if (!matches(block.field, p.filter, p.query)) return null;
      return <Row f={block.field} {...p} />;
    case "grid": {
      const fields = block.rows.flatMap((r) => r.cells.map((c) => c.field));
      if (!fields.some((f) => f && matches(f, p.filter, p.query))) return null;
      return (
        <div className="overflow-x-auto rounded-lg border border-border">
          <table className="w-full border-collapse">
            <thead>
              <tr className="bg-muted">
                <th className="w-2/5 px-3 py-2" />
                {block.columns.map((c) => (
                  <th
                    key={c.key}
                    scope="col"
                    className="px-3 py-2 text-right text-sm font-medium text-muted-foreground"
                  >
                    {c.heading.text}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {block.rows.map((row) => {
                const rate = row.cells.find(
                  (c) => c.kind === "design_constant" && c.field?.printed_rate,
                )?.field;
                return (
                  <tr key={row.key} className="border-t border-border">
                    <th
                      scope="row"
                      className="px-3 py-2 text-left align-middle text-base font-normal"
                    >
                      {calm(row.heading?.text ?? "")}
                      {rate && (
                        <span className="text-muted-foreground">
                          {" · "}
                          {display(rate, p.locale)}
                        </span>
                      )}
                    </th>
                    {row.cells.map((cell, i) => {
                      const key = cell.field
                        ? fieldKey(cell.field)
                        : `blank-${i}`;
                      return (
                        <GridValue
                          key={i}
                          cell={cell}
                          locale={p.locale}
                          uncalculated={p.uncalculated}
                          selected={p.selectedKey === key}
                          staged={
                            cell.field
                              ? p.staged[editKey(cell.field)]
                              : undefined
                          }
                          editingNow={p.editingKey === key}
                          setEditing={(on) => p.setEditingKey(on ? key : null)}
                          onSelect={() => cell.field && p.onSelect(cell.field)}
                          onStage={(text, advance) =>
                            cell.field && p.onType(cell.field, text, advance)
                          }
                        />
                      );
                    })}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      );
    }
    case "binding_inputs":
      return (
        <div className="flex flex-col gap-0.5 rounded-lg border border-dashed border-border p-1">
          <span className="px-2 pt-1 text-sm text-muted-foreground">
            Figures the calculation asks for that have no box of their own
          </span>
          {block.fields
            .filter((f) => matches(f, p.filter, p.query))
            .map((f) => (
              <Row key={fieldKey(f)} f={f} {...p} />
            ))}
        </div>
      );
    case "repeating":
      return <Repeating block={block} locale={p.locale} />;
    default:
      return null;
  }
}

type RepeatingBlock = Extract<FormBlock, { kind: "repeating" }>;

/** Repeated records, read as a table. Their lines are made from the filer's
 * records, so they are changed there; when those records could not be read
 * the number of lines is unknown, never zero. */
function Repeating({
  block,
  locale,
}: {
  block: RepeatingBlock;
  locale: string;
}) {
  const shown = block.columns.slice(0, 5);
  const cellText = (
    v: RepeatingBlock["rows"][number]["values"][number],
    i: number,
  ) =>
    !v || v.kind === "null"
      ? "—"
      : block.column_data_types[i] === "money"
        ? money(v.text, locale)
        : v.text;
  return (
    <div className="rounded-lg border border-border">
      <div className="flex items-center gap-2 border-b border-border bg-muted px-3 py-2 text-sm">
        <Icon name="sheet" size="sm" className="text-muted-foreground" />
        <span className="font-medium">
          {block.rows_known
            ? w("workspace.modelo.repeating", locale, {
                count: block.rows.length,
              })
            : w("workspace.modelo.grid.records_unknown", locale)}
        </span>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr>
              {shown.map((c) => (
                <th
                  key={c.key}
                  className="px-3 py-2 text-left text-sm font-medium text-muted-foreground"
                >
                  {calm(c.heading.text)}
                </th>
              ))}
              {block.columns.length > shown.length && (
                <th className="px-3 py-2 text-right text-sm font-normal text-faint">
                  +{block.columns.length - shown.length}
                </th>
              )}
            </tr>
          </thead>
          {block.rows_known && (
            <tbody>
              {block.rows.map((r) => (
                <tr key={r.index} className="border-t border-border">
                  {shown.map((c, i) => (
                    <td key={c.key} className="px-3 py-2 text-sm tabular-nums">
                      {cellText(r.values[i] ?? null, i)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          )}
        </table>
      </div>
      <p className="px-3 py-3 text-sm text-muted-foreground">
        {w("workspace.modelo.grid.records_read_only", locale)}
      </p>
    </div>
  );
}

type ContextBlock = Extract<FormBlock, { kind: "context_field" }>;

/** Facts the form prints about the filer and the period, as a short list;
 * a fact not resolved yet says so. */
function ContextSummary({
  items,
  locale,
}: {
  items: ContextBlock[];
  locale: string;
}) {
  const year = Number(
    items.find((x) => x.id.includes("ejercicio"))?.value?.text ?? 0,
  );
  const text = (c: ContextBlock) => {
    const v = c.value && c.value.kind !== "null" ? c.value : null;
    if (!v) return null;
    if (v.kind === "date") return dateWords(v.text, locale);
    if (c.id.includes("periodo") && year)
      return periodWords(v.text, year, locale).replace(/\s\d{4}$/, "");
    return v.text;
  };
  return (
    <dl className="grid grid-cols-[minmax(0,auto)_minmax(0,1fr)] gap-x-6 gap-y-1 rounded-lg bg-muted px-4 py-3 text-sm @3xl:grid-cols-[minmax(0,auto)_minmax(0,1fr)_minmax(0,auto)_minmax(0,1fr)]">
      {items.map((c) => (
        <div key={c.id} className="contents">
          <dt className="truncate text-muted-foreground">
            {calm(c.label.text)}
          </dt>
          <dd className={text(c) ? "text-foreground" : "text-faint"}>
            {text(c) ?? "Not known yet"}
          </dd>
        </div>
      ))}
    </dl>
  );
}

export function SectionView({
  section,
  ...p
}: BlockProps & { section: FormSection }) {
  const blocks: ReactNode[] = [];
  let context: ContextBlock[] = [];
  const flush = () => {
    if (context.length && p.filter === "all" && !p.query)
      blocks.push(
        <ContextSummary
          key={`ctx-${blocks.length}`}
          items={context}
          locale={p.locale}
        />,
      );
    context = [];
  };
  section.blocks.forEach((b, i) => {
    if (b.kind === "context_field") return void context.push(b);
    flush();
    if (p.filter !== "all" || p.query) {
      if (b.kind === "field" && !matches(b.field, p.filter, p.query)) return;
      if (b.kind === "repeating") return;
    }
    blocks.push(<Block key={`${b.kind}-${b.id}-${i}`} block={b} {...p} />);
  });
  flush();
  if (!blocks.length) return null;
  const todo = section.counts.needs_input + section.counts.blocked;
  const official =
    section.official_heading &&
    section.official_heading !== section.heading.text &&
    p.locale !== "es"
      ? section.official_heading
      : null;
  const hasGrid = section.blocks.some((b) => b.kind === "grid");
  return (
    <section
      id={`section-${section.id}`}
      aria-label={section.heading.text}
      className="scroll-mt-4"
    >
      <header className="mb-1 flex items-center gap-2 border-b border-border px-2 pb-2">
        <h3 className="font-serif text-md text-foreground">
          {calm(section.heading.text)}
        </h3>
        {official && (
          <Tooltip>
            <TooltipTrigger asChild>
              <button
                type="button"
                className="text-faint hover:text-muted-foreground"
                aria-label={w(
                  "workspace.modelo.disclosure.official_spanish",
                  p.locale,
                )}
              >
                <Icon name="info" size="xs" />
              </button>
            </TooltipTrigger>
            <TooltipContent className="max-w-sm">{official}</TooltipContent>
          </Tooltip>
        )}
        {p.uncalculated && hasGrid && (
          <span className="text-sm text-faint">
            ·{" "}
            {w(
              "workspace.modelo.legend.meaning.origin.not_calculated_yet",
              p.locale,
            )}
          </span>
        )}
        {todo > 0 && (
          <Badge variant="warning" className="ml-auto">
            {todo}
          </Badge>
        )}
      </header>
      <div role="rowgroup" className="flex flex-col gap-0.5">
        {blocks}
      </div>
    </section>
  );
}
