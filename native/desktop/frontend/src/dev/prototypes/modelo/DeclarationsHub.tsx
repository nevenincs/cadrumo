import { useMemo, useState } from "react";
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
import { Icon, type IconName } from "@/components/ui/icon";
import { Input } from "@/components/ui/input";
import { NativeSelect } from "@/components/ui/native-select";
import {
  SegmentedControl,
  SegmentedControlItem,
} from "@/components/ui/segmented-control";
import { FIXTURE_TODAY, modeloTitle, type ListRow } from "./fixtures";
import {
  coverageWords,
  dateWords,
  dueWords,
  money,
  periodWords,
  resultWords,
  TONE_TEXT,
  type Tone,
} from "./vocabulary";
import { w } from "./words";

// Every declaration in one list, in the application's own work order: what
// needs the filer, what is under way, what is ready, what is due and not
// started, and what is recorded. Local work and what was seen of the AEAT
// stay apart, and the AEAT side is shown only once a filing is recorded.

const GROUPS: ListRow["group"][] = [
  "attention",
  "in_progress",
  "ready",
  "not_started",
  "recorded",
  "aeat_unlinked",
  "maybe",
];

const groupWords = (g: ListRow["group"], locale: string) =>
  g === "aeat_unlinked"
    ? w("workspace.declarations.list.state.aeat_unlinked", locale)
    : w(`workspace.declarations.list.group.${g}`, locale);

/** The row's own state in the product's words, and its next step. */
function status(
  row: ListRow,
  locale: string,
): { word: string; next: string; tone: Tone; icon: IconName | null } {
  const s = row.declaration?.summary;
  const blocking = s?.blocking_count ?? 0;
  const state =
    row.state === "aeat_needs_check" || row.state === "aeat_unlinked"
      ? row.state
      : s?.is_correction && s.state !== "recorded"
        ? "correction"
        : (s?.state ?? row.state);
  const word =
    state === "recorded"
      ? w("workspace.declarations.list.group.recorded", locale)
      : state === "discarded"
        ? w("workspace.declarations.work_state.descartado", locale)
        : state === "maybe"
          ? w("workspace.declarations.list.group.maybe", locale)
          : w(`workspace.declarations.list.state.${state}`, locale);
  switch (state) {
    case "blocked":
      return {
        word,
        next: w("workspace.declarations.list.next.fix", locale, {
          count: blocking,
        }),
        tone: "danger",
        icon: "alert",
      };
    case "calculated":
      return {
        word,
        next: w("workspace.modelo.next.verify", locale),
        tone: "source",
        icon: null,
      };
    case "checked":
      return {
        word,
        next: w("workspace.declarations.list.next.create_file", locale),
        tone: "source",
        icon: "check",
      };
    case "recorded":
      return { word, next: "", tone: "source", icon: "tick" };
    case "aeat_needs_check":
      return {
        word,
        next: w("workspace.declarations.list.next.check_aeat", locale),
        tone: "attention",
        icon: "alert",
      };
    case "aeat_unlinked":
      return {
        word,
        next: w("workspace.declarations.list.next.link_aeat", locale),
        tone: "attention",
        icon: "office",
      };
    case "not_started":
      return {
        word,
        next: w("workspace.declarations.list.next.start", locale),
        tone: "quiet",
        icon: null,
      };
    case "maybe":
      return {
        word: w("workspace.declarations.list.group.maybe", locale),
        next: "",
        tone: "quiet",
        icon: null,
      };
    case "unreadable":
      return { word, next: "", tone: "danger", icon: "alert" };
    default:
      return {
        word,
        next: w("workspace.declarations.list.next.continue", locale),
        tone: "quiet",
        icon: null,
      };
  }
}

type View = "todo" | "recorded" | "all";
type Sort = "deadline" | "modelo" | "amount";

const daysLeft = (closes: string) =>
  Math.round(
    (Date.parse(`${closes}T12:00:00Z`) -
      Date.parse(`${FIXTURE_TODAY}T12:00:00Z`)) /
      86_400_000,
  );

/** The AEAT side, shown only where it is what the row is about: a recorded
 * filing, a filing seen only there, or one that needs checking. */
function aeatWords(row: ListRow, locale: string): string | null {
  const cal = row.calendar;
  if (!cal?.aeat_submission_state) return null;
  if (
    row.group !== "recorded" &&
    row.group !== "aeat_unlinked" &&
    row.state !== "aeat_needs_check"
  )
    return null;
  const word = w(
    `workspace.declarations.calendar.aeat.${cal.aeat_submission_state}`,
    locale,
  );
  return cal.evidence_conflicted
    ? `${word} · ${w("workspace.declarations.calendar.evidence.disagrees", locale)}`
    : word;
}

function Row({ row, locale }: { row: ListRow; locale: string }) {
  const st = status(row, locale);
  const cal = row.calendar;
  const due = cal
    ? dueWords(daysLeft(cal.adjusted_closes_on), cal.days_overdue, locale)
    : null;
  const result = row.declaration?.summary?.result;
  const recorded = row.group === "recorded";
  const aeat = aeatWords(row, locale);
  return (
    <li>
      <button
        type="button"
        className="grid w-full cursor-pointer grid-cols-[--spacing(14)_minmax(0,1fr)_minmax(0,auto)] items-center gap-x-4 gap-y-1 rounded-lg px-3 py-3 text-left hover:bg-accent @3xl:grid-cols-[--spacing(14)_minmax(0,1fr)_--spacing(40)_--spacing(56)_--spacing(36)]"
      >
        <span className="flex h-10 items-center justify-center rounded-md border border-border-strong font-mono text-md font-semibold">
          {row.modelo}
        </span>
        <span className="flex min-w-0 flex-col">
          <span className="truncate text-base font-medium">
            {modeloTitle(row.modelo, locale)}
          </span>
          <span className="text-sm text-muted-foreground">
            {row.period
              ? periodWords(row.period.code, row.period.filing_year, locale)
              : w("workspace.declarations.list.group.maybe", locale)}
          </span>
        </span>
        <span className="hidden flex-col @3xl:flex">
          {cal && (
            <>
              <span className="text-sm">
                {dateWords(cal.adjusted_closes_on, locale)}
              </span>
              {!recorded && due?.text && (
                <span className={cn("text-sm", TONE_TEXT[due.tone])}>
                  {due.text}
                </span>
              )}
            </>
          )}
        </span>
        <span className="hidden flex-col @3xl:flex">
          <span
            className={cn(
              "flex items-center gap-1 text-sm font-medium",
              st.tone === "quiet"
                ? "text-muted-foreground"
                : TONE_TEXT[st.tone],
            )}
          >
            {st.icon && <Icon name={st.icon} size="xs" />}
            {st.word}
          </span>
          {st.next && (
            <span className="text-sm text-muted-foreground">{st.next}</span>
          )}
          {aeat && (
            <span className="text-xs text-muted-foreground">{aeat}</span>
          )}
        </span>
        <span className="flex flex-col items-end">
          {result?.value ? (
            <>
              <span className="text-base tabular-nums">
                {money(result.value, locale)}
              </span>
              <span className="text-sm text-muted-foreground">
                {resultWords(result.direction, locale)}
              </span>
            </>
          ) : row.declaration && s_calculated(row) ? (
            <span className="text-sm text-faint">
              {w("workspace.declarations.value.result_unknown", locale)}
            </span>
          ) : null}
        </span>
      </button>
    </li>
  );
}

const s_calculated = (row: ListRow) =>
  !!row.declaration?.summary && row.declaration.summary.state !== "draft";

export function DeclarationsHub({
  rows,
  locale,
  creating = false,
}: {
  rows: ListRow[];
  locale: string;
  creating?: boolean;
}) {
  const [view, setView] = useState<View>("todo");
  const [sort, setSort] = useState<Sort>("deadline");
  const [query, setQuery] = useState("");
  const [newOpen, setNewOpen] = useState(creating);
  const shown = useMemo(() => {
    const q = query.trim().toLowerCase();
    const inView = rows.filter((r) =>
      view === "all"
        ? true
        : view === "recorded"
          ? r.group === "recorded"
          : r.group !== "recorded",
    );
    const found = q
      ? inView.filter(
          (r) =>
            r.modelo.includes(q) ||
            modeloTitle(r.modelo, locale).toLowerCase().includes(q),
        )
      : inView;
    const amount = (r: ListRow) => r.declaration?.summary?.result?.value;
    const by = {
      deadline: (a: ListRow, b: ListRow) =>
        (a.calendar?.adjusted_closes_on ?? "9999").localeCompare(
          b.calendar?.adjusted_closes_on ?? "9999",
        ),
      modelo: (a: ListRow, b: ListRow) => a.modelo.localeCompare(b.modelo),
      // Unknown amounts sort last; they are not zero.
      amount: (a: ListRow, b: ListRow) =>
        (amount(a) === undefined || amount(a) === null ? 1 : 0) -
          (amount(b) === undefined || amount(b) === null ? 1 : 0) ||
        Number(amount(b) ?? 0) - Number(amount(a) ?? 0),
    }[sort];
    return [...found].sort(by);
  }, [rows, view, sort, query, locale]);
  const todo = rows.filter((r) => r.group !== "recorded").length;

  return (
    <div className="@container flex h-full min-h-0 flex-col bg-background">
      <header className="flex flex-wrap items-end gap-4 px-8 pt-6 pb-4">
        <div className="flex flex-col gap-1">
          <h1 className="font-serif text-lg">
            {w("workspace.declarations.destination.overview", locale)}
          </h1>
          <p className="text-base text-muted-foreground">
            {w("workspace.declarations.hub.lead", locale)}
            {rows.some(
              (r) =>
                r.calendar &&
                coverageWords(r.calendar.holiday_coverage, locale),
            ) && (
              <span className="text-faint">
                {" "}
                {w("workspace.declarations.hub.holidays_national_only", locale)}
              </span>
            )}
          </p>
        </div>
        <div className="ml-auto flex items-center gap-2">
          <div className="relative w-64">
            <Icon
              name="search"
              size="xs"
              className="pointer-events-none absolute top-1/2 left-2.5 -translate-y-1/2 text-faint"
            />
            <Input
              placeholder={w(
                "workspace.declarations.list.search.modelo",
                locale,
              )}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              className="pl-7"
              aria-label={w("desktop.declarations.search.label", locale)}
            />
          </div>
          <Button onClick={() => setNewOpen(true)}>
            <Icon name="plus" size="xs" />
            {w("workspace.declarations.list.key.new", locale)}
          </Button>
        </div>
      </header>
      <div className="flex items-center gap-3 border-b border-border px-8 pb-3">
        <SegmentedControl
          aria-label={w("desktop.declarations.show.label", locale)}
          value={view}
          onValueChange={(v) => setView(v as View)}
        >
          <SegmentedControlItem value="todo" className="flex-none">
            {w("workspace.declarations.list.filter.todo", locale)}{" "}
            <span className="ml-1 text-faint tabular-nums">{todo}</span>
          </SegmentedControlItem>
          <SegmentedControlItem value="recorded" className="flex-none">
            {w("workspace.declarations.list.filter.recorded", locale)}
          </SegmentedControlItem>
          <SegmentedControlItem value="all" className="flex-none">
            {w("workspace.declarations.list.filter.all", locale)}
          </SegmentedControlItem>
        </SegmentedControl>
        <label className="ml-auto flex items-center gap-2 text-sm text-muted-foreground">
          {w("workspace.declarations.list.sort.by", locale)}
          <NativeSelect
            value={sort}
            onChange={(e) => setSort(e.target.value as Sort)}
            className="w-36"
          >
            <option value="deadline">
              {w("workspace.declarations.list.sort.work_order", locale)}
            </option>
            <option value="modelo">
              {w("workspace.declarations.list.sort.modelo", locale)}
            </option>
            <option value="amount">
              {w("workspace.declarations.list.sort.amount", locale)}
            </option>
          </NativeSelect>
        </label>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto px-5 py-4">
        {shown.length === 0 ? (
          <p className="p-8 text-center text-base text-muted-foreground">
            {query
              ? w("workspace.declarations.list.no_match", locale, { query })
              : w("workspace.declarations.list.all_recorded", locale)}
          </p>
        ) : sort === "deadline" ? (
          GROUPS.map((g) => {
            const inGroup = shown.filter((r) => r.group === g);
            if (!inGroup.length) return null;
            return (
              <section
                key={g}
                className="mb-6"
                aria-label={groupWords(g, locale)}
              >
                <div className="flex items-baseline gap-2 px-3 pb-1">
                  <h2 className="text-sm font-medium">
                    {groupWords(g, locale)}
                  </h2>
                  <span className="text-sm text-faint">{inGroup.length}</span>
                </div>
                <ul className="flex flex-col divide-y divide-border">
                  {inGroup.map((r) => (
                    <Row key={r.key} row={r} locale={locale} />
                  ))}
                </ul>
              </section>
            );
          })
        ) : (
          <ul className="flex flex-col divide-y divide-border">
            {shown.map((r) => (
              <Row key={r.key} row={r} locale={locale} />
            ))}
          </ul>
        )}
      </div>
      <NewDeclarationDialog
        open={newOpen}
        onOpenChange={setNewOpen}
        locale={locale}
        rows={rows}
      />
    </div>
  );
}

const EXPECTED = ["303", "130", "111", "115"];
const OTHERS = ["347", "349", "390", "100"];
const QUARTERS = [
  { code: "1T", closes: "2026-04-20" },
  { code: "2T", closes: "2026-07-20" },
  { code: "3T", closes: "2026-10-20" },
  { code: "4T", closes: "2027-01-30" },
];

/** Choose a modelo, then a period. The period due next is chosen first; a
 * period that already has a declaration opens it instead of making another. */
export function NewDeclarationDialog({
  open,
  onOpenChange,
  locale,
  rows,
  initialModelo = null,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  locale: string;
  rows: ListRow[];
  initialModelo?: string | null;
}) {
  const [modelo, setModelo] = useState<string | null>(initialModelo);
  const [year, setYear] = useState(2026);
  const [period, setPeriod] = useState<string>("4T");
  const [query, setQuery] = useState("");
  const existing = (m: string, code: string) =>
    rows.find(
      (r) =>
        r.modelo === m &&
        r.period?.code === code &&
        r.period.filing_year === year &&
        r.declaration,
    );
  const open_ = (m: string) =>
    rows.filter(
      (r) => r.modelo === m && r.declaration && r.group !== "recorded",
    ).length;
  const tile = (m: string) => (
    <li key={m}>
      <button
        type="button"
        onClick={() => setModelo(m)}
        className="flex w-full items-center gap-3 rounded-lg px-3 py-2 text-left hover:bg-accent"
      >
        <span className="flex h-8 w-12 items-center justify-center rounded-md border border-border-strong font-mono text-base font-semibold">
          {m}
        </span>
        <span className="min-w-0 flex-1 truncate text-base">
          {modeloTitle(m, locale)}
        </span>
        {open_(m) > 0 && (
          <Badge>
            {w("workspace.declarations.list.new.open_count", locale, {
              count: open_(m),
            })}
          </Badge>
        )}
        <Icon name="forward" size="xs" className="text-faint" />
      </button>
    </li>
  );
  const q = query.trim().toLowerCase();
  const filter = (list: string[]) =>
    list.filter(
      (m) =>
        !q || m.includes(q) || modeloTitle(m, locale).toLowerCase().includes(q),
    );
  const annual = modelo === "347" || modelo === "390" || modelo === "100";
  const periods = annual
    ? [{ code: "0A", closes: modelo === "347" ? "2027-02-28" : "2027-01-30" }]
    : QUARTERS;
  const chosen = existing(modelo ?? "", annual ? "0A" : period);
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="w-palette"
        placement="top"
        closeLabel={w("workspace.modelo.key.close", locale)}
      >
        {modelo === null ? (
          <>
            <DialogHeader>
              <DialogTitle>
                {w("workspace.declarations.list.key.new", locale)}
              </DialogTitle>
              <DialogDescription>
                {w("workspace.declarations.list.new.which_modelo", locale)}
              </DialogDescription>
            </DialogHeader>
            <Input
              autoFocus
              placeholder={w(
                "workspace.declarations.list.new.search_placeholder",
                locale,
              )}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              aria-label={w(
                "workspace.declarations.list.search.modelo",
                locale,
              )}
            />
            <div className="flex flex-col gap-3">
              <div>
                <h3 className="px-3 pb-1 text-sm font-medium text-muted-foreground">
                  {w("workspace.declarations.list.new.expected", locale)}
                </h3>
                <ul>{filter(EXPECTED).map(tile)}</ul>
              </div>
              <div>
                <h3 className="px-3 pb-1 text-sm font-medium text-muted-foreground">
                  {w("workspace.declarations.list.new.other", locale)}
                </h3>
                <ul>{filter(OTHERS).map(tile)}</ul>
              </div>
            </div>
          </>
        ) : (
          <>
            <DialogHeader>
              <Button
                variant="link"
                size="xs"
                className="self-start text-sm text-muted-foreground"
                onClick={() => setModelo(null)}
              >
                <Icon name="back" size="xs" />{" "}
                {w("workspace.declarations.list.new.another", locale)}
              </Button>
              <DialogTitle>
                {w("workspace.modelo.modelo_title", locale, {
                  modelo,
                  title: modeloTitle(modelo, locale),
                })}
              </DialogTitle>
              <DialogDescription>
                {w(
                  annual
                    ? "workspace.declarations.list.new.which_year"
                    : "workspace.declarations.list.new.which_period",
                  locale,
                )}
              </DialogDescription>
            </DialogHeader>
            <SegmentedControl
              aria-label={w("workspace.declarations.list.new.year", locale)}
              value={String(year)}
              onValueChange={(v) => setYear(Number(v))}
              className="self-start"
            >
              {[2025, 2026, 2027].map((y) => (
                <SegmentedControlItem
                  key={y}
                  value={String(y)}
                  className="flex-none px-3"
                >
                  {y}
                </SegmentedControlItem>
              ))}
            </SegmentedControl>
            <div
              role="radiogroup"
              aria-label={w(
                "workspace.declarations.list.column.period",
                locale,
              )}
              className={cn(
                "grid gap-2",
                annual ? "grid-cols-1" : "grid-cols-2",
              )}
            >
              {periods.map((p) => {
                const there = existing(modelo, p.code);
                const pick = annual || period === p.code;
                return (
                  <button
                    key={p.code}
                    type="button"
                    role="radio"
                    aria-checked={pick}
                    onClick={() => setPeriod(p.code)}
                    className="flex flex-col items-start gap-0.5 rounded-lg border border-border px-3 py-2 text-left hover:bg-accent aria-checked:border-foreground aria-checked:bg-selected"
                  >
                    <span className="text-base font-medium">
                      {periodWords(p.code, year, locale)}
                    </span>
                    <span className="text-sm text-muted-foreground">
                      {w("workspace.declarations.due.on", locale, {
                        date: dateWords(p.closes, locale),
                      })}
                    </span>
                    <span className="text-xs text-faint">
                      {there
                        ? there.group === "recorded"
                          ? w(
                              "workspace.declarations.list.group.recorded",
                              locale,
                            )
                          : w(
                              "workspace.declarations.list.new.already_started",
                              locale,
                            )
                        : w(
                            "workspace.declarations.list.state.not_started",
                            locale,
                          )}
                    </span>
                  </button>
                );
              })}
            </div>
            <DialogFooter>
              <Button variant="ghost" onClick={() => onOpenChange(false)}>
                {w("workspace.modelo.editor.cancel", locale)}
              </Button>
              <Button>
                {chosen
                  ? w("workspace.declarations.list.new.open_it", locale)
                  : w(
                      "workspace.declarations.list.new.create_declaration",
                      locale,
                    )}
              </Button>
            </DialogFooter>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}
