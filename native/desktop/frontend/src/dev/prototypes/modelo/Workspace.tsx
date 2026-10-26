import { useCallback, useMemo, useState, type KeyboardEvent } from "react";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/components/ui/cn";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Icon } from "@/components/ui/icon";
import { IconButton } from "@/components/ui/icon-button";
import { Input } from "@/components/ui/input";
import { Kbd } from "@/components/ui/kbd";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { fieldsOf, modeloTitle } from "./fixtures";
import {
  BoxNumber,
  editKey,
  fieldKey,
  heldValue,
  intentFor,
  matches,
  restoreIntent,
  SectionView,
  stagedWords,
  type FieldFilter,
  type Staged,
} from "./FormView";
import { Inspector } from "./Inspector";
import {
  CheckView,
  FilingView,
  HistoryView,
  SourcesView,
  stoppingIssues,
} from "./Panels";
import {
  HISTORY_130,
  SOURCES_130,
  type AeatSide,
  type HistoryEvent,
  type SourceGroup,
} from "./scenarios";
import type { FormEnvelope, FormField, Intent, ModeloForm } from "./types";
import {
  confirmable,
  coverageWords,
  dateWords,
  dueWords,
  money,
  periodWords,
  resultWords,
  TONE_TEXT,
} from "./vocabulary";
import { w } from "./words";

export type View = "form" | "check" | "file" | "sources" | "history";

type Next =
  | {
      kind: "act";
      word: string;
      view: View | "calculate";
      jump?: "todo" | "failed";
    }
  | { kind: "status"; word: string };

/** The boxes the filer is asked about, on pages that apply. */
function asks(form: ModeloForm, staged: Staged) {
  const onPage = new Set<FormField>();
  for (const page of form.pages)
    if (page.applies === true)
      for (const s of page.sections)
        for (const b of s.blocks)
          if (b.kind === "field") onPage.add(b.field);
          else if (b.kind === "binding_inputs")
            for (const f of b.fields) onPage.add(f);
          else if (b.kind === "grid")
            for (const r of b.rows)
              for (const c of r.cells) if (c.field) onPage.add(c.field);
  for (const f of form.working_figures) onPage.add(f);
  for (const u of form.unplaced) onPage.add(u.field);
  const all = fieldsOf(form).filter(
    (f) => !staged[editKey(f)] && onPage.has(f),
  );
  return {
    input: all.filter((f) => f.origin === "needs_input"),
    confirm: all.filter((f) => f.origin === "default_to_confirm"),
    failed: all.filter((f) => f.origin === "calculation_failed"),
  };
}

/** A declaration the edit contract refuses because Cadrumo's rules for the
 * modelo are not complete enough: nothing can be calculated or changed. */
export const rulesIncomplete = (e: FormEnvelope) =>
  e.admission_refusal?.refusal.code === "admission_denied" &&
  e.admission_refusal.refusal.facts.includes("registry_authority_grade");

/** The one next step, read from the form, its refusal and the AEAT side in
 * one order, so the header, the views and the list never disagree. Export
 * and recording follow the application's own gates: a complete check and no
 * blocking calculation note. */
function nextStep(
  e: FormEnvelope,
  aeat: AeatSide | null,
  todo: ReturnType<typeof asks>,
  staged: number,
  locale: string,
): Next | null {
  const f = e.form.form;
  const next = (key: string) =>
    w(`workspace.modelo.next_button.${key}`, locale);
  if (f.edit_closure)
    return aeat?.state === "justificante_verified"
      ? {
          kind: "status",
          word: `${w("workspace.modelo.next.recorded", locale, {
            date: f.filing?.recorded_at
              ? dateWords(f.filing.recorded_at, locale)
              : "",
          })} · ${w("workspace.declarations.calendar.aeat.justificante_verified", locale)}`,
        }
      : { kind: "act", word: next("add_receipt"), view: "file" };
  if (rulesIncomplete(e))
    return {
      kind: "status",
      word: w("workspace.modelo.editability.no_admission", locale),
    };
  if (staged) return null;
  const stale = f.issues.some((i) => i.finding.kind === "stale_calculation");
  if (!f.calculation_revision_id)
    return { kind: "act", word: next("calculate"), view: "calculate" };
  if (stale)
    return { kind: "act", word: next("recalculate"), view: "calculate" };
  if (todo.input.length)
    return { kind: "act", word: next("fill"), view: "form", jump: "todo" };
  if (todo.confirm.length)
    return { kind: "act", word: next("confirm"), view: "form", jump: "todo" };
  if (todo.failed.length)
    return {
      kind: "act",
      word: next("see_missing"),
      view: "form",
      jump: "failed",
    };
  const blockingNotes = f.calculation_notes.some(
    (n) => n.attention === "blocks",
  );
  const stop = stoppingIssues(f.issues).length;
  if (stop || blockingNotes)
    return { kind: "act", word: next("resolve"), view: "check" };
  if (f.verification !== "complete")
    return { kind: "act", word: next("verify"), view: "check" };
  if (!f.last_export)
    return { kind: "act", word: next("export"), view: "file" };
  if (!f.last_export.current)
    return { kind: "act", word: next("export_again"), view: "file" };
  if (!f.filing)
    return { kind: "act", word: next("record_after_file"), view: "file" };
  return null;
}

function ResultLine({
  form,
  locale,
  provisional,
  staged,
}: {
  form: ModeloForm;
  locale: string;
  provisional: boolean;
  staged: number;
}) {
  const r = form.result;
  if (!r)
    return (
      <span className="text-sm text-muted-foreground">
        {w("workspace.modelo.header.result.no_result_box", locale)}
      </span>
    );
  if (!form.calculation_revision_id)
    return (
      <span className="text-base text-muted-foreground">
        {w("workspace.modelo.header.result.not_calculated", locale)}
      </span>
    );
  if (!r.value)
    return (
      <span className="text-base font-medium text-destructive">
        {w("workspace.modelo.header.result.failed", locale)}
      </span>
    );
  return (
    <span className="flex flex-col items-end">
      <span
        className={cn(
          "text-lg font-semibold tabular-nums",
          provisional || staged ? "text-muted-foreground" : "text-foreground",
        )}
      >
        {money(r.value, locale)}
      </span>
      <span className="text-sm text-muted-foreground">
        {resultWords(r.direction, locale)}
        {staged
          ? ` · ${w("workspace.modelo.header.result.out_of_date_until_applied", locale)}`
          : provisional
            ? ` · ${w("workspace.modelo.header.result.provisional", locale)}`
            : ""}
      </span>
    </span>
  );
}

function AboutForm({ form, locale }: { form: ModeloForm; locale: string }) {
  return (
    <Popover>
      <PopoverTrigger asChild>
        <IconButton label={w("workspace.modelo.about.title", locale)} size="xs">
          <Icon name="info" />
        </IconButton>
      </PopoverTrigger>
      <PopoverContent className="flex w-80 flex-col gap-2 text-sm">
        <p className="font-medium">
          {w("workspace.modelo.about.title", locale)}
        </p>
        <p className="text-muted-foreground">
          {w("workspace.modelo.about.official", locale, {
            modelo: form.modelo,
          })}
          {form.layout_provenance === "generated" &&
            ` ${w("workspace.modelo.about.generated", locale)}`}
        </p>
        {!form.filing && (
          <p className="text-muted-foreground">
            {w("workspace.modelo.header.own_calculation", locale)}
          </p>
        )}
      </PopoverContent>
    </Popover>
  );
}

function Keys({ locale }: { locale: string }) {
  return (
    <Popover>
      <PopoverTrigger asChild>
        <IconButton
          label={w("workspace.modelo.legend.group.keys", locale)}
          size="sm"
        >
          <Icon name="keyboard" />
        </IconButton>
      </PopoverTrigger>
      <PopoverContent
        align="end"
        className="grid w-72 grid-cols-[auto_minmax(0,1fr)] gap-x-3 gap-y-1.5 text-sm"
      >
        <span>
          <Kbd>↑</Kbd> <Kbd>↓</Kbd>
        </span>
        <span>{w("desktop.modelo.keys.move", locale)}</span>
        <span>
          <Kbd>Enter</Kbd>
        </span>
        <span>{w("desktop.modelo.keys.change", locale)}</span>
        <span>
          <Kbd>Esc</Kbd>
        </span>
        <span>{w("desktop.modelo.keys.leave", locale)}</span>
        <span>
          <Kbd>N</Kbd>
        </span>
        <span>{w("desktop.modelo.keys.next_attention", locale)}</span>
      </PopoverContent>
    </Popover>
  );
}

function TodoRail({
  todo,
  locked,
  locale,
  selected,
  onPick,
}: {
  todo: ReturnType<typeof asks>;
  locked: boolean;
  locale: string;
  selected: string | null;
  onPick: (f: FormField) => void;
}) {
  const [openFailed, setOpenFailed] = useState(false);
  if (locked)
    return (
      <p className="flex gap-2 p-4 text-sm text-muted-foreground">
        <Icon name="lock" size="xs" className="mt-0.5" />
        {w("workspace.modelo.editability.no_admission", locale)}
      </p>
    );
  const item = (f: FormField) => (
    <li key={fieldKey(f)}>
      <button
        type="button"
        onClick={() => onPick(f)}
        aria-current={selected === fieldKey(f)}
        className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left hover:bg-accent aria-[current=true]:bg-selected"
      >
        <BoxNumber box={f.box} size="sm" />
        <span className="truncate text-sm">{f.label.text}</span>
      </button>
    </li>
  );
  const groups: [string, FormField[], string][] = [
    [
      w("workspace.modelo.legend.group.needs_you", locale),
      todo.input,
      "text-warning",
    ],
    [
      w("workspace.modelo.origin.default_to_confirm", locale),
      todo.confirm,
      "text-warning",
    ],
  ];
  if (!todo.input.length && !todo.confirm.length && !todo.failed.length)
    return (
      <p className="flex gap-2 p-4 text-sm text-muted-foreground">
        <Icon name="check" size="xs" className="mt-0.5 text-success" />
        {w("workspace.modelo.todo.none", locale)}
      </p>
    );
  return (
    <div className="flex flex-col gap-3 p-2">
      {groups.map(([word, list, tone]) =>
        list.length ? (
          <div key={word}>
            <p className={cn("px-2 pb-1 text-xs font-medium", tone)}>{word}</p>
            <ul>{list.map(item)}</ul>
          </div>
        ) : null,
      )}
      {todo.failed.length > 0 && (
        <div className="rounded-md border border-border">
          <button
            type="button"
            onClick={() => setOpenFailed(!openFailed)}
            aria-expanded={openFailed}
            className="flex w-full items-start gap-2 px-2 py-2 text-left"
          >
            <Icon name="alert" size="xs" className="mt-0.5 text-destructive" />
            <span className="flex flex-col">
              <span className="text-sm">
                {w("workspace.modelo.todo.failed", locale, {
                  count: todo.failed.length,
                })}
              </span>
              <span className="text-xs text-muted-foreground">
                {w("workspace.modelo.todo.failed_lead", locale)}
              </span>
            </span>
            <Icon
              name={openFailed ? "chevronUp" : "chevronDown"}
              size="xs"
              className="ml-auto mt-0.5 text-faint"
            />
          </button>
          {openFailed && <ul className="px-1 pb-1">{todo.failed.map(item)}</ul>}
        </div>
      )}
    </div>
  );
}

function Outline({
  form,
  locale,
  onGo,
}: {
  form: ModeloForm;
  locale: string;
  onGo: (id: string) => void;
}) {
  const leaf = (t: string) => t.split(" · ").pop() ?? t;
  return (
    <nav
      aria-label={w("desktop.modelo.outline.label", locale)}
      className="flex flex-col gap-4 p-3"
    >
      {form.pages.map((page) => (
        <div key={page.id} className="flex flex-col gap-0.5">
          <span className="px-2 pb-1 text-xs font-medium text-faint uppercase">
            {leaf(page.heading.text)}
          </span>
          {page.sections.map((s) => {
            const todo = s.counts.needs_input + s.counts.blocked;
            return (
              <button
                key={s.id}
                type="button"
                onClick={() => onGo(s.id)}
                title={s.heading.text}
                className="flex items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm text-muted-foreground hover:bg-accent hover:text-foreground"
              >
                <span className="min-w-0 flex-1 truncate">
                  {leaf(s.heading.text)}
                </span>
                {todo > 0 && page.applies === true && (
                  <Badge variant="warning">{todo}</Badge>
                )}
              </button>
            );
          })}
        </div>
      ))}
    </nav>
  );
}

/** The contract's own word for what an edit does to a box. */
function effectWords(f: FormField, intent: Intent, locale: string) {
  const key =
    intent.kind === "clear_declared_value"
      ? "clear"
      : intent.kind === "restore_source_value" ||
          intent.kind === "remove_override"
        ? "restore"
        : intent.kind === "set_override_value"
          ? `replaces_${f.source?.family ?? "records"}`
          : f.origin === "entered" || f.origin === "default_to_confirm"
            ? "set_filer"
            : f.origin === "calculated"
              ? "set_calculation"
              : "set_nothing";
  return w(`workspace.modelo.review.effect.${key}`, locale);
}

function ReviewDialog({
  open,
  onOpenChange,
  staged,
  fields,
  form,
  locale,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  staged: Staged;
  fields: Map<string, FormField>;
  form: ModeloForm;
  locale: string;
}) {
  const entries = Object.entries(staged).sort(
    ([, a], [, b]) =>
      Number(b.intent.kind === "set_override_value") -
      Number(a.intent.kind === "set_override_value"),
  );
  const displacing = entries.filter(
    ([, c]) => c.intent.kind === "set_override_value",
  ).length;
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="w-palette"
        closeLabel={w("workspace.modelo.key.close", locale)}
      >
        <DialogHeader>
          <DialogTitle>
            {w("workspace.modelo.review.title", locale, {
              count: entries.length,
            })}
          </DialogTitle>
          <DialogDescription>
            {w("workspace.modelo.review.nothing_saved", locale)}
          </DialogDescription>
        </DialogHeader>
        <ul className="flex flex-col divide-y divide-border rounded-lg border border-border">
          {entries.map(([key, change]) => {
            const f = fields.get(key);
            if (!f) return null;
            const replaces = change.intent.kind === "set_override_value";
            return (
              <li
                key={key}
                className="grid grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-x-3 gap-y-0.5 px-3 py-2"
              >
                <BoxNumber box={f.box} size="sm" />
                <span className="min-w-0 truncate text-base">
                  {f.label.text}
                </span>
                <span className="flex items-center gap-2 text-base tabular-nums">
                  <span className="text-faint line-through">
                    {change.was || "—"}
                  </span>
                  <Icon name="forward" size="xs" className="text-faint" />
                  <span>{stagedWords(f, change.intent, locale)}</span>
                </span>
                <span />
                <span
                  className={cn(
                    "col-span-2 flex items-center gap-1 text-xs",
                    replaces ? "text-warning" : "text-muted-foreground",
                  )}
                >
                  {replaces && <Icon name="swap" size="xs" />}
                  {effectWords(f, change.intent, locale)}
                </span>
              </li>
            );
          })}
        </ul>
        {displacing > 0 && (
          <Alert tone="warning" icon={<Icon name="swap" />}>
            {w("workspace.modelo.review.displacing", locale, {
              count: displacing,
            })}
          </Alert>
        )}
        {!form.operator_entries_known && (
          <Alert tone="warning" icon={<Icon name="alert" />}>
            {w("workspace.modelo.review.operator_entries_unknown", locale)}
          </Alert>
        )}
        <DialogFooter>
          <span className="mr-auto text-sm text-muted-foreground">
            {w("workspace.modelo.filing.kept_locally", locale)}
          </span>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>
            {w("workspace.modelo.review.back", locale)}
          </Button>
          <Button onClick={() => onOpenChange(false)}>
            {w("workspace.modelo.review.apply", locale)}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

/**
 * One declaration as a document to work through: the official form drawn
 * from the registry's layout, what needs the filer beside it, details for the
 * chosen box, and the other views of the same declaration. Everything shown
 * is read from the `modelo.work.form` envelope and the calendar's AEAT side.
 */
export function ModeloWorkspace({
  envelope,
  locale,
  aeat = null,
  initialView = "form",
  initialStaged = {},
  initialSelected = null,
  initialReviewing = false,
  initialCorrecting = false,
  initialDetails = true,
  sources = SOURCES_130,
  history = HISTORY_130,
}: {
  envelope: FormEnvelope;
  locale: string;
  aeat?: AeatSide | null;
  initialView?: View;
  initialStaged?: Staged;
  initialSelected?: string | null;
  initialReviewing?: boolean;
  initialCorrecting?: boolean;
  initialDetails?: boolean;
  sources?: SourceGroup[];
  history?: HistoryEvent[];
}) {
  const form = envelope.form.form;
  const [view, setView] = useState<View>(initialView);
  const [rail, setRail] = useState<"todo" | "outline">("todo");
  const [details, setDetails] = useState(initialDetails);
  const [selected, setSelected] = useState<string | null>(initialSelected);
  const [editingKey, setEditingKey] = useState<string | null>(null);
  const [staged, setStaged] = useState<Staged>(initialStaged);
  const [filter, setFilter] = useState<FieldFilter>("all");
  const [query, setQuery] = useState("");
  const [notice, setNotice] = useState<string | null>(null);
  const [reviewing, setReviewing] = useState(initialReviewing);
  const [correcting, setCorrecting] = useState(initialCorrecting);
  const all = useMemo(() => fieldsOf(form), [form]);
  const fields = useMemo(
    () => new Map(all.map((f) => [fieldKey(f), f])),
    [all],
  );
  const byEditKey = useMemo(
    () => new Map(all.map((f) => [editKey(f), f])),
    [all],
  );
  const byCasilla = useMemo(() => {
    const m = new Map<string, FormField>();
    for (const f of all)
      if (f.address.kind === "casilla") m.set(f.address.casilla_id, f);
    return m;
  }, [all]);
  const todo = useMemo(() => asks(form, staged), [form, staged]);
  const stagedCount = Object.keys(staged).length;
  const next = nextStep(envelope, aeat, todo, stagedCount, locale);
  const chosen = selected ? (fields.get(selected) ?? null) : null;
  const locked = !!form.edit_closure || rulesIncomplete(envelope);
  const uncalculated = form.calculation_revision_id === null;
  const stop = form.verification ? stoppingIssues(form.issues).length : 0;
  const formBadge =
    todo.input.length + todo.confirm.length + todo.failed.length;

  const reveal = useCallback((key: string) => {
    setSelected(key);
    requestAnimationFrame(() =>
      document
        .querySelector(`[data-key="${key}"]`)
        ?.scrollIntoView({ block: "center", behavior: "smooth" }),
    );
  }, []);
  const pick = (f: FormField) => {
    setView("form");
    reveal(fieldKey(f));
  };
  const visible = useMemo(
    () => all.filter((f) => matches(f, filter, query)).map(fieldKey),
    [all, filter, query],
  );
  const jump = (list: FormField[]) => {
    const keys = list.map(fieldKey);
    const at = selected ? keys.indexOf(selected) : -1;
    const key = keys[(at + 1) % Math.max(keys.length, 1)];
    if (key) reveal(key);
  };
  const stage = (field: FormField, intent: Intent) =>
    setStaged((s) => ({
      ...s,
      [editKey(field)]: { intent, was: heldValue(field, locale) },
    }));
  const onType = (field: FormField, text: string, advance: boolean) => {
    const intent = intentFor(field, text);
    if ("refused" in intent) {
      if (text.trim() || heldValue(field, locale))
        setNotice(w(intent.refused, locale));
    } else if (!(
      text.trim() === heldValue(field, locale) && field.origin === "entered"
    )) {
      setNotice(null);
      stage(field, intent);
    }
    if (advance) {
      const at = visible.indexOf(fieldKey(field));
      const key = visible[at + 1];
      if (key) reveal(key);
    }
  };
  const onKey = (e: KeyboardEvent) => {
    if (editingKey || (e.target as HTMLElement).tagName === "INPUT") return;
    const at = selected ? visible.indexOf(selected) : -1;
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      const key =
        visible[
          Math.min(
            Math.max(at + (e.key === "ArrowDown" ? 1 : -1), 0),
            visible.length - 1,
          )
        ];
      if (key) reveal(key);
    } else if ((e.key === "Enter" || e.key === "F2") && chosen && !locked) {
      e.preventDefault();
      setEditingKey(selected);
    } else if (
      e.key.toLowerCase() === "n" &&
      !e.ctrlKey &&
      !e.metaKey &&
      !e.altKey
    ) {
      e.preventDefault();
      jump([...todo.input, ...todo.confirm]);
    }
  };
  const runNext = () => {
    if (!next || next.kind !== "act" || next.view === "calculate") return;
    setView(next.view);
    if (next.jump === "todo") jump([...todo.input, ...todo.confirm]);
    if (next.jump === "failed") {
      setRail("todo");
      jump(todo.failed);
    }
  };
  const go = (id: string) =>
    document
      .getElementById(`section-${id}`)
      ?.scrollIntoView({ behavior: "smooth", block: "start" });
  const goBox = (box: string) => {
    const f = all.find((x) => x.box === box);
    if (f) pick(f);
  };
  const due = form.deadline
    ? dueWords(form.deadline.days_remaining, form.deadline.days_overdue, locale)
    : null;
  const showNext =
    next && !(next.kind === "act" && next.view === view && view !== "form");

  const blockProps = {
    locale,
    selectedKey: selected,
    editingKey: locked ? null : editingKey,
    staged,
    filter,
    query,
    uncalculated: uncalculated && !locked,
    onSelect: (f: FormField) => setSelected(fieldKey(f)),
    setEditingKey: locked ? () => undefined : setEditingKey,
    onType,
    onConfirm: (f: FormField) =>
      stage(f, {
        kind: "set_typed_value",
        text: f.value?.text ?? "",
        confirms: true,
      }),
    canConfirm: (f: FormField) => !locked && confirmable(f),
  };

  const detailsPanel = (
    <Inspector
      form={form}
      field={chosen}
      locale={locale}
      staged={chosen ? staged[editKey(chosen)] : undefined}
      onRevert={() =>
        setStaged((s) => {
          const n = { ...s };
          if (chosen) delete n[editKey(chosen)];
          return n;
        })
      }
      onRestore={() => chosen && stage(chosen, restoreIntent(chosen))}
      operand={(id) => byCasilla.get(id) ?? null}
      onClose={() => setDetails(false)}
      onJump={(id) => {
        const f = byCasilla.get(id);
        if (f) reveal(fieldKey(f));
      }}
    />
  );

  return (
    <div className="@container flex h-full min-h-0 flex-col bg-background">
      <header className="flex flex-wrap items-center gap-x-8 gap-y-3 px-6 pt-3 pb-3">
        <div className="flex min-w-0 flex-col gap-1">
          <Button
            variant="link"
            size="xs"
            className="self-start text-sm text-muted-foreground"
          >
            <Icon name="back" size="xs" />
            {w("workspace.declarations.destination.overview", locale)}
          </Button>
          <div className="flex items-center gap-3">
            <span className="flex h-8 min-w-12 items-center justify-center rounded-md border border-border-strong px-1.5 font-mono text-md font-semibold">
              {form.modelo}
            </span>
            <h1 className="truncate font-serif text-lg">
              {modeloTitle(form.modelo, locale)}
            </h1>
            <span className="text-md text-muted-foreground">
              {periodWords(form.period.code, form.period.filing_year, locale)}
            </span>
            <AboutForm form={form} locale={locale} />
          </div>
          {form.deadline && (
            <span className="flex flex-wrap items-center gap-1.5 text-sm text-muted-foreground">
              <Icon name="calendar" size="xs" />
              {w("workspace.declarations.due.on", locale, {
                date: dateWords(form.deadline.closes_on, locale),
              })}
              {due?.text && !form.edit_closure && (
                <span className={cn("font-medium", TONE_TEXT[due.tone])}>
                  · {due.text}
                </span>
              )}
              {coverageWords(form.deadline.holiday_coverage, locale) &&
                !form.edit_closure && (
                  <span className="text-faint">
                    · {coverageWords(form.deadline.holiday_coverage, locale)}
                  </span>
                )}
            </span>
          )}
        </div>
        <div className="ml-auto flex items-center gap-5">
          <ResultLine
            form={form}
            locale={locale}
            provisional={todo.input.length + todo.confirm.length > 0}
            staged={stagedCount}
          />
          {showNext &&
            (next.kind === "act" ? (
              <Button onClick={runNext}>
                {next.word}
                <Icon name="forward" size="xs" />
              </Button>
            ) : (
              <span className="max-w-xs text-sm text-muted-foreground">
                {next.word}
              </span>
            ))}
        </div>
      </header>
      <Tabs
        value={view}
        onValueChange={(v) => setView(v as View)}
        className="flex-none border-b border-border px-4"
      >
        <TabsList aria-label={w("desktop.modelo.views.label", locale)}>
          <TabsTrigger value="form">
            {w("desktop.modelo.view.form", locale)}{" "}
            {formBadge > 0 && !locked && (
              <Badge variant="warning">{formBadge}</Badge>
            )}
          </TabsTrigger>
          <TabsTrigger value="check">
            {w("workspace.modelo.step.review", locale)}
            {form.verification &&
              (stop ? (
                <Badge variant="neutral">{stop}</Badge>
              ) : (
                <Icon name="check" size="xs" className="text-success" />
              ))}
          </TabsTrigger>
          <TabsTrigger value="file">
            {w("workspace.modelo.filing.title", locale)}{" "}
            {form.filing && (
              <Icon name="check" size="xs" className="text-success" />
            )}
          </TabsTrigger>
          <TabsTrigger value="sources">
            {w("workspace.modelo.key.sources", locale)}
          </TabsTrigger>
          <TabsTrigger value="history">
            {w("workspace.modelo.history.title", locale)}
          </TabsTrigger>
        </TabsList>
      </Tabs>
      {locked && (
        <div className="flex items-center gap-3 border-b border-border bg-muted px-6 py-2 text-sm">
          <Icon name="lock" size="xs" className="text-muted-foreground" />
          <span>
            {form.edit_closure
              ? w("workspace.modelo.filed.read_only", locale)
              : w(
                  envelope.admission_refusal?.refusal.reconsideration_condition
                    ? "workspace.modelo.editor.rules_incomplete"
                    : "workspace.modelo.editability.no_admission",
                  locale,
                )}
          </span>
          {form.edit_closure && (
            <Button
              size="xs"
              variant="outline"
              className="ml-auto"
              onClick={() => {
                setView("history");
                setCorrecting(true);
              }}
            >
              {w("workspace.modelo.correction.title", locale)}
            </Button>
          )}
        </div>
      )}
      {view === "form" ? (
        <div
          className="relative grid min-h-0 flex-1 grid-cols-[minmax(0,1fr)] @4xl:grid-cols-[--spacing(60)_minmax(0,1fr)] @6xl:data-[details=true]:grid-cols-[--spacing(64)_minmax(0,1fr)_--spacing(88)]"
          data-details={details}
        >
          <aside className="hidden min-h-0 flex-col border-r border-border bg-chrome @4xl:flex">
            <Tabs
              value={rail}
              onValueChange={(v) => setRail(v as "todo" | "outline")}
              className="flex-none px-2"
            >
              <TabsList aria-label={w("desktop.modelo.side.label", locale)}>
                <TabsTrigger value="todo">
                  {w("workspace.modelo.todo.title", locale)}
                </TabsTrigger>
                <TabsTrigger value="outline">
                  {w("desktop.modelo.side.outline", locale)}
                </TabsTrigger>
              </TabsList>
            </Tabs>
            <div className="min-h-0 flex-1 overflow-y-auto border-t border-border">
              {rail === "todo" ? (
                <TodoRail
                  todo={todo}
                  locked={locked}
                  locale={locale}
                  selected={selected}
                  onPick={pick}
                />
              ) : (
                <Outline form={form} locale={locale} onGo={go} />
              )}
            </div>
          </aside>
          <main className="flex min-h-0 flex-col">
            <div className="flex items-center gap-2 border-b border-border px-6 py-2">
              <div className="relative w-64">
                <Icon
                  name="search"
                  size="xs"
                  className="pointer-events-none absolute top-1/2 left-2.5 -translate-y-1/2 text-faint"
                />
                <Input
                  controlSize="sm"
                  placeholder={w("workspace.modelo.search.placeholder", locale)}
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  className="pl-7"
                  aria-label={w("desktop.modelo.search.label", locale)}
                />
              </div>
              <Button
                size="sm"
                variant="ghost"
                aria-pressed={filter === "mine"}
                onClick={() => setFilter(filter === "mine" ? "all" : "mine")}
              >
                {w("workspace.modelo.filter.only_mine", locale)}
              </Button>
              <span className="ml-auto" />
              {!locked && <Keys locale={locale} />}
              <IconButton
                label={w(
                  details
                    ? "desktop.modelo.details.hide"
                    : "desktop.modelo.details.show",
                  locale,
                )}
                size="sm"
                aria-pressed={details}
                onClick={() => setDetails(!details)}
              >
                <Icon name="splitColumn" />
              </IconButton>
            </div>
            {notice && (
              <div className="px-6 pt-3">
                <Alert tone="warning" icon={<Icon name="alert" />}>
                  {notice}
                </Alert>
              </div>
            )}
            <div
              role="grid"
              aria-label={w("desktop.modelo.view.form", locale)}
              tabIndex={selected ? -1 : 0}
              onFocus={(e) => {
                if (e.target === e.currentTarget && !selected && visible[0])
                  setSelected(visible[0]);
              }}
              onKeyDown={onKey}
              className="min-h-0 flex-1 overflow-y-auto px-6 py-5 outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-inset"
            >
              <div className="mx-auto flex max-w-4xl flex-col gap-8">
                {form.pages.map((page) =>
                  page.applies === false ? (
                    <p
                      key={page.id}
                      className="rounded-lg border border-dashed border-border p-4 text-base text-muted-foreground"
                    >
                      {w("workspace.modelo.page.does_not_apply", locale, {
                        page: page.heading.text,
                      })}
                    </p>
                  ) : (
                    <div key={page.id} className="flex flex-col gap-6">
                      {form.pages.length > 1 && (
                        <div className="flex items-baseline gap-2">
                          <h2 className="text-sm font-medium text-faint uppercase">
                            {page.heading.text}
                          </h2>
                          {page.applies === null && (
                            <span className="text-sm text-faint">
                              ·{" "}
                              {w(
                                "workspace.modelo.page.only_if_it_applies",
                                locale,
                              )}
                            </span>
                          )}
                        </div>
                      )}
                      {page.sections.map((s) => (
                        <SectionView key={s.id} section={s} {...blockProps} />
                      ))}
                    </div>
                  ),
                )}
                {form.unplaced.length > 0 && filter === "all" && !query && (
                  <SectionView
                    section={{
                      id: "unplaced",
                      heading: {
                        text: w("workspace.modelo.page.unplaced", locale),
                        disclosure: "localized",
                      },
                      official_heading: null,
                      blocks: form.unplaced.map((u, i) => ({
                        kind: "field" as const,
                        id: `unplaced-${i}`,
                        field: u.field,
                      })),
                      counts: { ...form.counts, needs_input: 0, blocked: 0 },
                    }}
                    {...blockProps}
                  />
                )}
                {form.working_figures.length > 0 &&
                  filter === "all" &&
                  !query && (
                    <SectionView
                      section={{
                        id: "working-figures",
                        heading: {
                          text: w(
                            "workspace.modelo.page.calculation_details",
                            locale,
                          ),
                          disclosure: "localized",
                        },
                        official_heading: null,
                        blocks: form.working_figures.map((f, i) => ({
                          kind: "field" as const,
                          id: `wf-${i}`,
                          field: f,
                        })),
                        counts: { ...form.counts, needs_input: 0, blocked: 0 },
                      }}
                      {...blockProps}
                    />
                  )}
              </div>
            </div>
            {details && (
              <div className="h-2/5 flex-none overflow-y-auto border-t border-border bg-card @6xl:hidden">
                {detailsPanel}
              </div>
            )}
            {stagedCount > 0 && (
              <div className="flex items-center gap-3 border-t border-border bg-card px-6 py-3 shadow-raised">
                <Icon name="edit" size="sm" />
                <span className="text-base font-medium">
                  {w("workspace.modelo.next.apply", locale, {
                    count: stagedCount,
                  })}
                </span>
                <div className="ml-auto flex gap-2">
                  <Button variant="ghost" onClick={() => setStaged({})}>
                    {w("workspace.modelo.review.discard", locale)}
                  </Button>
                  <Button onClick={() => setReviewing(true)}>
                    {w("workspace.modelo.next_button.apply", locale)}
                  </Button>
                </div>
              </div>
            )}
          </main>
          {details && (
            <aside className="hidden min-h-0 overflow-y-auto border-l border-border bg-card @6xl:block">
              {detailsPanel}
            </aside>
          )}
        </div>
      ) : (
        <div className="@container min-h-0 flex-1 overflow-y-auto px-6 py-6">
          {view === "check" && (
            <CheckView form={form} locale={locale} onGo={goBox} />
          )}
          {view === "file" && (
            <FilingView
              form={form}
              aeat={aeat}
              locale={locale}
              onCheck={() => setView("check")}
            />
          )}
          {view === "sources" && (
            <SourcesView groups={sources} locale={locale} onGo={goBox} />
          )}
          {view === "history" && (
            <HistoryView
              events={history}
              form={form}
              aeat={aeat}
              locale={locale}
              correcting={correcting}
              onCorrect={setCorrecting}
            />
          )}
        </div>
      )}
      <ReviewDialog
        open={reviewing}
        onOpenChange={setReviewing}
        staged={staged}
        fields={byEditKey}
        form={form}
        locale={locale}
      />
    </div>
  );
}
