import { useMemo, useState, type ReactNode, type RefObject } from "react";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  DataGrid,
  DataGridText,
  type GridColumn,
  type GridRow,
} from "@/components/ui/data-grid";
import { EmptyState } from "@/components/ui/empty";
import { Icon } from "@/components/ui/icon";
import { Input } from "@/components/ui/input";
import { NativeSelect } from "@/components/ui/native-select";
import {
  SegmentedControl,
  SegmentedControlItem,
} from "@/components/ui/segmented-control";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { cn } from "@/components/ui/cn";
import { PaneHeader, type PaneControl } from "../../PaneHeader";
import type { ModeloPort } from "../../../shell/modelo";
import type {
  DeclarationListGroup,
  ModeloDeclarationListRowV1 as Row,
  OutputLanguage,
} from "../../../shell/modeloContract";
import { useStrings, type Translate } from "../../../shell/strings";
import { aeatWords, rowMark } from "./declarationsWords";
import {
  NewDeclarationDialog,
  type NewDeclarationStart,
} from "./NewDeclarationDialog";
import { DEADLINE_TONE } from "../workspace/Marks";
import { AeatFilingDialog } from "./AeatFilingDialog";
import { useDeclarationsList, type ListMemory } from "./useDeclarationsList";

/** What the page keeps of itself while it is put away for a declaration:
 * the list as read, and how it was looked at. Held in memory only. */
export type DeclarationsMemory = ListMemory & {
  view?: View;
  sort?: SortState;
  query?: string;
  collapsed?: ReadonlySet<string>;
};

/** A piece of the page's state that outlives the page in its memory. */
function useKept<K extends "view" | "sort" | "query" | "collapsed">(
  memory: RefObject<DeclarationsMemory>,
  key: K,
  initial: NonNullable<DeclarationsMemory[K]>,
) {
  const [value, setValue] = useState<NonNullable<DeclarationsMemory[K]>>(
    () => memory.current[key] ?? initial,
  );
  const set = (
    next:
      | NonNullable<DeclarationsMemory[K]>
      | ((
          held: NonNullable<DeclarationsMemory[K]>,
        ) => NonNullable<DeclarationsMemory[K]>),
  ) =>
    setValue((held) => {
      const value = typeof next === "function" ? next(held) : next;
      memory.current[key] = value;
      return value;
    });
  return [value, set] as const;
}

type View = "todo" | "recorded" | "all";
/** Work order is the read model's own, in its groups; the others are flat
 * and are the page's columns. */
type Sort = "work_order" | (typeof SORT_COLUMNS)[number];
type SortState = { key: Sort; direction: "asc" | "desc" };
const VIEWS = ["todo", "recorded", "all"] as const;
const SORT_COLUMNS = [
  "modelo",
  "declaration",
  "deadline",
  "state",
  "result",
] as const;
const SORTS = ["work_order", ...SORT_COLUMNS] as const;
const isSortColumn = (id: string): id is (typeof SORT_COLUMNS)[number] =>
  (SORT_COLUMNS as readonly string[]).includes(id);

const collator = new Intl.Collator(undefined, { numeric: true });
/** What a row is ranked by under a column; a row without one goes last,
 * whichever way the column is sorted. */
const SORT_VALUES: Record<
  (typeof SORT_COLUMNS)[number],
  (row: Row) => string | null
> = {
  modelo: (row) => row.modelo,
  declaration: (row) => row.modelo_title,
  deadline: (row) => row.deadline,
  state: (row) => row.state_words,
  result: (row) => row.result_words,
};

const VIEW_KEYS: Record<View, string> = {
  todo: "workspace.declarations.list.filter.todo",
  recorded: "workspace.declarations.list.filter.recorded",
  all: "workspace.declarations.list.filter.all",
};

const inView = (view: View, row: Row) =>
  view === "all" || (view === "recorded") === (row.group === "recorded");

/** What choosing a row does, as the read model says: open its local
 * declaration, open the AEAT's return to read, start one, or say why it
 * has no step of its own. */
function rowAction(row: Row): "open" | "aeat" | "start" | "help" | null {
  if (row.opens_local_work && row.work_unit_id !== null) return "open";
  if (row.opens_aeat_filing) return "aeat";
  if (row.next_step === "start") return "start";
  return row.help_words ? "help" : null;
}

/** Under the title: the period, or for a row without one what the read
 * model advises. */
const subline = (row: Row) => row.period_words ?? row.advice_words;

function columns(t: Translate): GridColumn<Row>[] {
  return [
    {
      id: "modelo",
      header: t("workspace.declarations.list.column.modelo"),
      width: 5.5,
      sortable: true,
      cell: (row) => (
        <span className="flex h-8 w-12 items-center justify-center rounded-md border border-border-strong font-mono text-base font-semibold">
          {row.modelo}
        </span>
      ),
    },
    {
      id: "declaration",
      header: t("workspace.declarations.list.column.declaration"),
      width: 18,
      grow: 1,
      sortable: true,
      cell: (row) => (
        <span className="flex min-w-0 flex-col py-2">
          <DataGridText className="text-base font-medium">
            {row.modelo_title}
          </DataGridText>
          {subline(row) && (
            <DataGridText className="text-sm text-muted-foreground">
              {subline(row) ?? ""}
            </DataGridText>
          )}
        </span>
      ),
    },
    {
      id: "deadline",
      header: t("workspace.declarations.list.column.deadline"),
      width: 18,
      sortable: true,
      cell: (row) => (
        // The read model's deadline sentence already names the date; a row
        // it does not word keeps the bare deadline.
        <span className="flex min-w-0 flex-col">
          {row.due_words ? (
            <DataGridText
              className={cn(
                "text-sm",
                row.due_tone ? DEADLINE_TONE[row.due_tone] : undefined,
              )}
            >
              {row.due_words}
            </DataGridText>
          ) : row.deadline_text ? (
            <DataGridText className="text-sm text-muted-foreground">
              {row.deadline_text}
            </DataGridText>
          ) : null}
        </span>
      ),
    },
    {
      id: "state",
      header: t("workspace.declarations.list.column.state"),
      width: 16,
      grow: 1,
      sortable: true,
      cell: (row) => <StateCell row={row} t={t} />,
    },
    {
      id: "result",
      header: t("workspace.declarations.list.column.result"),
      width: 10,
      align: "end",
      sortable: true,
      cell: (row) =>
        row.result_words ? (
          <DataGridText className="text-sm text-muted-foreground">
            {row.result_words}
          </DataGridText>
        ) : null,
    },
  ];
}

function StateCell({ row, t }: { row: Row; t: Translate }) {
  const mark = rowMark(row);
  const aeat = aeatWords(t, row);
  return (
    <span className="flex min-w-0 flex-col py-2">
      <span className="flex min-w-0 items-center gap-1 text-sm font-medium">
        {mark && (
          <Icon
            name={mark.icon}
            size="xs"
            className={cn("shrink-0", mark.tone)}
          />
        )}
        <DataGridText>{row.state_words}</DataGridText>
        {row.blocking_count > 0 && (
          <Tooltip>
            <TooltipTrigger asChild>
              <Badge variant="count" tabIndex={-1}>
                {row.blocking_count}
              </Badge>
            </TooltipTrigger>
            {row.next_step_words && (
              <TooltipContent>{row.next_step_words}</TooltipContent>
            )}
          </Tooltip>
        )}
      </span>
      {row.next_step_words && (
        <DataGridText className="text-sm text-muted-foreground">
          {row.next_step_words}
        </DataGridText>
      )}
      {aeat && (
        <DataGridText className="text-xs text-muted-foreground">
          {aeat}
        </DataGridText>
      )}
    </span>
  );
}

/**
 * The Declarations page: every declaration of the profile in the read
 * model's work order, and the dialog that starts a new one. Each row says
 * what the read model says of it; opening one hands its work unit to the
 * shell, which shows the workspace.
 */
export function DeclarationsPage({
  port,
  reader,
  withheld,
  language,
  shown,
  page,
  pane,
  memory,
  onOpen,
  onCensus,
}: {
  port: ModeloPort;
  /** Whose declarations, or null while the account withholds them. */
  reader: string | null;
  /** What stands in the page while the account withholds them. */
  withheld: ReactNode;
  language: OutputLanguage;
  shown: boolean;
  page: RefObject<HTMLElement | null>;
  /** The pane's title and controls, which the page's header carries. */
  pane: {
    title: string;
    controls: PaneControl[];
    onToggleMaximize(): void;
  };
  /** What the page keeps of itself while a declaration is open, for one
   * profile. */
  memory: RefObject<DeclarationsMemory>;
  /** Opens one declaration's workspace. */
  onOpen(workUnitId: string): void;
  /** Asks for the window's one census flow; absent where the window has
   * none to offer. */
  onCensus?: () => void;
}) {
  const t = useStrings();
  const { read, reread } = useDeclarationsList(
    port,
    reader,
    language,
    shown,
    memory,
  );
  const [view, setView] = useKept(memory, "view", "todo" as View);
  const [sort, setSort] = useKept(memory, "sort", {
    key: "work_order",
    direction: "asc",
  } as SortState);
  const [query, setQuery] = useKept(memory, "query", "");
  const [collapsed, setCollapsed] = useKept(
    memory,
    "collapsed",
    new Set<string>() as ReadonlySet<string>,
  );
  const [aeatRow, setAeatRow] = useState<Row | null>(null);
  const [creating, setCreating] = useState<NewDeclarationStart | null | false>(
    false,
  );
  const list = read.list;
  const rows = useMemo(() => list?.rows ?? [], [list]);
  const cols = useMemo(() => columns(t), [t]);
  const todo = rows.filter((row) => row.group !== "recorded").length;
  const [help, setHelp] = useState<string | null>(null);
  // The list is whole only when every zone and source it reads was read.
  const complete =
    list !== null &&
    [...list.zones, ...list.sources].every(
      (part) => part.availability === "available",
    );

  const shownRows = useMemo(() => {
    const q = query.trim().toLowerCase();
    const found = rows.filter(
      (row) =>
        inView(view, row) &&
        (!q ||
          row.modelo.includes(q) ||
          row.modelo_title.toLowerCase().includes(q)),
    );
    if (sort.key === "work_order") return found;
    const value = SORT_VALUES[sort.key];
    const sign = sort.direction === "asc" ? 1 : -1;
    // A row without a value goes last: a row without a deadline is not due
    // first.
    return [...found].sort((a, b) => {
      const [x, y] = [value(a), value(b)];
      return x === null || y === null
        ? Number(x === null) - Number(y === null)
        : sign * collator.compare(x, y);
    });
  }, [rows, view, sort, query]);

  const gridRows = useMemo(() => {
    const data = (row: Row): GridRow<Row> => ({
      kind: "data",
      key: row.key,
      data: row,
    });
    if (sort.key !== "work_order") return shownRows.map(data);
    // Groups in the order the read model lists their first row.
    const groups = new Map<DeclarationListGroup, Row[]>();
    for (const row of shownRows)
      groups.set(row.group, [...(groups.get(row.group) ?? []), row]);
    return [...groups].flatMap(([group, members]) => {
      const key = `group:${group}`;
      const closed = collapsed.has(key);
      return [
        {
          kind: "section",
          key,
          label: members[0]?.group_words ?? "",
          collapsed: closed,
          summary: <span className="tabular-nums">{members.length}</span>,
        } satisfies GridRow<Row>,
        ...(closed ? [] : members.map(data)),
      ];
    });
  }, [shownRows, sort, collapsed]);

  const byKey = useMemo(
    () => new Map(rows.map((row) => [row.key, row])),
    [rows],
  );
  const activate = (key: string) => {
    const row = byKey.get(key);
    if (!row) return;
    const action = rowAction(row);
    setHelp(null);
    if (action === "open" && row.work_unit_id) onOpen(row.work_unit_id);
    else if (action === "aeat") setAeatRow(row);
    else if (action === "help") setHelp(row.help_words);
    else if (action === "start")
      setCreating({
        modelo: row.modelo,
        period:
          row.filing_year !== null && row.period_code !== null
            ? { filing_year: row.filing_year, code: row.period_code }
            : null,
      });
  };

  // Nothing to do is said only of a whole list; otherwise an empty list is
  // just what was listed.
  const emptyText =
    query.trim() !== ""
      ? t("workspace.declarations.list.no_match", { query: query.trim() })
      : complete && view === "todo"
        ? t("workspace.declarations.list.all_recorded")
        : t("workspace.declarations.list.none_listed");

  let body: ReactNode;
  if (reader === null) body = withheld;
  else if (read.phase === "failed")
    body = (
      <EmptyState
        className="declarations-failed"
        icon="alert"
        description={
          <span role="alert">{t("desktop.declarations.read_failed")}</span>
        }
      >
        <Button variant="outline" onClick={reread}>
          {t("desktop.declarations.retry")}
        </Button>
      </EmptyState>
    );
  else if (list === null)
    body = (
      <EmptyState
        className="declarations-loading"
        role="status"
        busy
        description={t("desktop.declarations.loading")}
      />
    );
  else
    body = (
      <>
        <div className="declarations-toolbar flex flex-wrap items-center gap-3 px-5 pt-4 pb-3">
          <p className="min-w-0 flex-1 text-base text-faint">
            {list.deadline_note_words}
          </p>
          <div className="relative w-64 max-w-full">
            <Icon
              name="search"
              size="xs"
              className="pointer-events-none absolute top-1/2 left-2.5 -translate-y-1/2 text-faint"
            />
            <Input
              type="search"
              className="declarations-search pl-7"
              maxLength={64}
              placeholder={t("workspace.declarations.list.search.modelo")}
              aria-label={t("desktop.declarations.search.label")}
              value={query}
              onChange={(event) => setQuery(event.target.value)}
            />
          </div>
          {onCensus && (
            <Button
              variant="outline"
              className="declarations-census"
              onClick={onCensus}
            >
              <Icon name="sync" size="xs" />
              {t("desktop.profile.censo.title")}
            </Button>
          )}
          <Button
            className="declarations-new"
            onClick={() => setCreating(null)}
          >
            <Icon name="plus" size="xs" />
            {t("workspace.declarations.list.key.new")}
          </Button>
        </div>
        <div className="flex flex-wrap items-center gap-3 border-b border-border px-5 pb-3">
          <SegmentedControl
            aria-label={t("desktop.declarations.show.label")}
            value={view}
            onValueChange={(value) => setView(value as View)}
            className="declarations-view"
          >
            {VIEWS.map((v) => (
              <SegmentedControlItem key={v} value={v} className="flex-none">
                {t(VIEW_KEYS[v])}
                {v === "todo" && (
                  <span className="ml-1 text-muted-foreground tabular-nums">
                    {todo}
                  </span>
                )}
              </SegmentedControlItem>
            ))}
          </SegmentedControl>
          <label className="ml-auto flex items-center gap-2 text-sm text-muted-foreground">
            {t("workspace.declarations.list.sort.by")}
            <NativeSelect
              controlSize="sm"
              className="declarations-sort w-36"
              value={sort.key}
              onChange={(event) =>
                setSort({ key: event.target.value as Sort, direction: "asc" })
              }
            >
              {SORTS.map((s) => (
                <option key={s} value={s}>
                  {t(`workspace.declarations.list.sort.${s}`)}
                </option>
              ))}
            </NativeSelect>
          </label>
        </div>
        {(list.notices.length > 0 || help) && (
          <div className="flex flex-col gap-2 px-5 pt-3">
            {list.notices.map((notice) => (
              <Alert
                key={notice}
                tone="warning"
                className="declarations-notice"
                icon={<Icon name="alert" />}
              >
                {notice}
              </Alert>
            ))}
            {help && (
              <Alert className="declarations-help" icon={<Icon name="info" />}>
                {help}
              </Alert>
            )}
          </div>
        )}
        <div className="flex min-h-0 flex-1 flex-col p-3">
          <DataGrid
            className="declarations-grid rounded-md"
            label={t("workspace.declarations.destination.overview")}
            columns={cols}
            rows={gridRows}
            sort={
              sort.key === "work_order"
                ? null
                : { column: sort.key, direction: sort.direction }
            }
            onSort={(column) => {
              if (!isSortColumn(column)) return;
              setSort((held) => ({
                key: column,
                direction:
                  held.key === column && held.direction === "asc"
                    ? "desc"
                    : "asc",
              }));
            }}
            density="comfortable"
            // Fixed heights, so every cell spans its row: two lines, or three
            // where the AEAT side is said too.
            rowHeight={(row) =>
              row.kind !== "data"
                ? undefined
                : row.data.aeat_submission_state !== null
                  ? 4.25
                  : 3.5
            }
            positionLabel={(row, count) =>
              t("desktop.declarations.position", { row, count })
            }
            onActivate={activate}
            onToggleSection={(key) =>
              setCollapsed((held) => {
                const next = new Set(held);
                if (!next.delete(key)) next.add(key);
                return next;
              })
            }
            describeRow={(key) => byKey.get(key)?.help_words ?? undefined}
            empty={
              <EmptyState
                className="declarations-empty"
                icon="page"
                description={emptyText}
              />
            }
          />
        </div>
      </>
    );

  return (
    <>
      <PaneHeader
        title={pane.title}
        controls={pane.controls}
        onToggleMaximize={pane.onToggleMaximize}
      />
      <section
        ref={page}
        tabIndex={-1}
        aria-label={pane.title}
        aria-busy={read.phase === "reading" || undefined}
        className="declarations-page flex min-h-0 flex-1 flex-col overflow-hidden bg-background focus-visible:-outline-offset-2"
      >
        {body}
      </section>
      {reader !== null && list !== null && (
        <NewDeclarationDialog
          open={creating !== false}
          onOpenChange={(open) => {
            if (!open) setCreating(false);
          }}
          port={port}
          targets={list.creation_targets}
          rows={rows}
          start={creating || null}
          onOpen={onOpen}
          onWritten={() => {
            // Stale even if the page goes before the read: the next one
            // reads again.
            memory.current.stale = true;
            reread();
          }}
        />
      )}
      {aeatRow && (
        <AeatFilingDialog row={aeatRow} onClose={() => setAeatRow(null)} />
      )}
    </>
  );
}
