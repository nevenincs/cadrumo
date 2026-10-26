import {
  useState,
  useEffect,
  useRef,
  useMemo,
  useCallback,
  useEffectEvent,
  useLayoutEffect,
  Fragment,
  useId,
  type ClipboardEvent,
  type KeyboardEvent,
  type MouseEvent,
  type PointerEvent,
  type CSSProperties,
  type ReactNode,
} from "react";
import { clsx as cx } from "clsx";
import {
  ACTION_WORD,
  DRAFT_FIELDS,
  DRAFT_REQUIRED,
  EMPTY_FILTERS,
  F,
  GROUPS,
  PREFS,
  READONLY_REASON,
  REASON_FIX,
  SAVED_VIEWS,
  SEAL_LABEL,
  SERVER_SORT,
  STATUS_FILTERS,
  canon,
  canonOf,
  checkIssues,
  compareRows,
  diffOf,
  effDate,
  effective,
  fmtDate,
  fmtDateLong,
  fmtMoney,
  fmtStamp,
  fmtTime,
  getField,
  grossCheck,
  isIdentity,
  lockReason,
  matchesFilters,
  optionsFor,
  parseDateIso,
  parseFor,
  parsePercent,
  parseTsv,
  periodLabel,
  periodRange,
  periodShort,
  plural,
  quarterLabel,
  reviewStatus,
  sameValue,
  shortId,
  show,
  stagedRowIds,
  statusOf,
  sumsOf,
  trayCounts,
  tsvEscape,
} from "./model";
import {
  Alert,
  Button,
  Empty,
  Field,
  FilterChip,
  IconButton,
  Input,
  Kbd,
  Menu,
  type MenuItem,
  Popover,
  Seg,
  Select,
  Switch,
  announce,
  chord,
  Overlay,
  place,
  sleep,
  useDismiss,
  useToast,
} from "./Primitives";
import {
  CATEGORY_LABEL,
  CATEGORY_OPTIONS,
  CLASSIFIED,
  CLS,
  DIRECTION,
  FAMILIES,
  IMPORT_ISSUES,
  LIFECYCLE,
  PAYMENT,
  REASONS,
  pct,
} from "./vocab";
import { ACCOUNT_LABEL, RULES } from "./data";
import {
  COL_FLEX,
  COL_LABEL,
  COL_WIDTH,
  PRESETS,
  STICKY,
  useStore,
} from "./store";
import { Inspector } from "./Inspector";
import { DataGrid } from "./DataGrid";
import { Icon, type IconName } from "./Icon";
import type { CellAttrs, GridActive, GridColumn, MoveInfo } from "./DataGrid";
import type { StageChange } from "./store";
import { usePage, type PastePlan, type PasteRefusal } from "./page";
import type {
  Check,
  DataState,
  Direction,
  Draft,
  Filters,
  Invoice,
  Option,
  Item,
  Match,
  Movement,
  MovementWindow,
  RowItem,
  Outcome,
  Pair,
  Recon,
  Refusal,
  StagedAction,
  State,
  Value,
  View,
  WindowCtx,
} from "./types";

type Pill = {
  tone: string;
  icon: IconName;
  label: string;
  n?: number;
  fill?: number;
  pressed?: boolean;
  onClick: () => void;
};
/* ── Movements: the window, the grid, its editors. ────────────────────── */
export const gridCellId = (key: string, col: string) =>
  `cell-${key}-${col}`.replace(/[^a-zA-Z0-9_-]/g, "_");
export const NUM_COLS = new Set([
  "amount",
  "eur",
  "base",
  "ivaRate",
  "ivaAmount",
  "recargo",
  "share",
]);
export function useMedia(query: string) {
  const mq = useMemo(() => window.matchMedia(query), [query]);
  const [matches, setMatches] = useState(mq.matches);
  useEffect(() => {
    setMatches(mq.matches);
    const f = (e: MediaQueryListEvent) => setMatches(e.matches);
    mq.addEventListener("change", f);
    return () => mq.removeEventListener("change", f);
  }, [mq]);
  return matches;
}
export const useNarrow = () => useMedia("(max-width: 47.5rem)");
export const daysBetween = (a: string, b: string) =>
  Math.round(
    (Date.parse(b + "T12:00:00Z") - Date.parse(a + "T12:00:00Z")) / 86400000,
  );

/* Reconciliation, one-to-one (R6): candidates must settle the amount
   within a cent on a flow that pairs; they are ranked by the invoice
   number found in the description, then the shortest issue-to-payment
   gap, then the counterparty, then the amount. Ties are flagged. */
export function reconciliationSuggestions(
  data: DataState,
  stagedActions: StagedAction[] = [],
): Recon {
  const linkedRows = new Set(
    stagedActions.filter((a) => a.type === "link").map((a) => a.rowIds[0]),
  );
  const linkedInv = new Set(
    stagedActions
      .filter((a) => a.type === "link")
      .map((a) => a.payload?.invoiceId),
  );
  const rows = Object.values(data.byId).filter(
    (r) =>
      !r.invoiceId &&
      r.lifecycle === "active" &&
      r.direction !== "transfer" &&
      !linkedRows.has(r.id),
  );
  const pairs: Pair[] = [];
  data.invoices
    .filter((i) => !i.linked.length && !linkedInv.has(i.id))
    .forEach((inv) => {
      const settle = inv.total - (inv.retention || 0);
      rows.forEach((r) => {
        if (
          (inv.kind === "issued") !== (r.direction === "in") ||
          r.currency !== inv.currency ||
          Math.abs(r.amount - settle) > 1
        )
          return;
        const a = (inv.counterparty || "").toLowerCase(),
          b = (r.counterparty || "").toLowerCase();
        const cp =
          !!a &&
          !!b &&
          (a.includes(b) ||
            b.includes(a) ||
            a.split(" ")[0] === b.split(" ")[0]);
        const num =
          inv.number &&
          r.description
            .replace(/\s/g, "")
            .toUpperCase()
            .includes(inv.number.replace(/\s/g, "").toUpperCase());
        const gap = daysBetween(inv.date, effDate(r));
        const gapScore = gap >= -3 ? Math.abs(gap) : 1000 - gap;
        const key = [
          num ? 0 : 1,
          gapScore,
          cp ? 0 : 1,
          Math.abs(r.amount - settle),
        ];
        const chips = [
          num && "Number in description",
          gap === 0
            ? "Paid on the issue day"
            : gap > 0
              ? `Paid ${plural(gap, "day")} after issue`
              : `Paid ${plural(-gap, "day")} before issue`,
          cp && "Same counterparty",
          "Amount settles",
        ].filter((c): c is string => typeof c === "string");
        pairs.push({
          invoiceId: inv.id,
          rowId: r.id,
          inv,
          row: r,
          num: !!num,
          gap,
          counterparty: cp,
          key,
          chips,
          settle,
        });
      });
    });
  const cmp = (x: Pair, y: Pair) => {
    for (let i = 0; i < 4; i++)
      if (x.key[i] !== y.key[i]) return x.key[i]! - y.key[i]!;
    return 0;
  };
  pairs.sort((x, y) => cmp(x, y) || (x.invoiceId < y.invoiceId ? -1 : 1));
  const usedRow = new Set<string>(),
    usedInv = new Set<string>(),
    best: Record<string, Match> = {};
  pairs.forEach((p) => {
    if (usedRow.has(p.rowId) || usedInv.has(p.invoiceId)) return;
    const rivals = pairs.filter(
      (q) =>
        q !== p &&
        (q.rowId === p.rowId || q.invoiceId === p.invoiceId) &&
        !usedRow.has(q.rowId) &&
        !usedInv.has(q.invoiceId),
    );
    const ties = rivals.filter((q) => cmp(q, p) === 0);
    usedRow.add(p.rowId);
    usedInv.add(p.invoiceId);
    best[p.rowId] = {
      ...p,
      ambiguous: ties.length > 0,
      ties,
      others: pairs.filter((q) => q.rowId === p.rowId && q !== p),
    };
  });
  // A tied rival row keeps a pointer to the same chooser.
  Object.values(best).forEach((b) =>
    b.ties.forEach((t) => {
      if (!best[t.rowId])
        best[t.rowId] = {
          ...t,
          ambiguous: true,
          ties: [b],
          others: [],
          rivalOf: b.rowId,
        };
    }),
  );
  return {
    best,
    pairs,
    list: Object.values(best).sort((a, b) =>
      effDate(b.row).localeCompare(effDate(a.row)),
    ),
  };
}

export function useMovementWindow(
  state: State,
  ctx: WindowCtx,
): MovementWindow {
  const { data, view } = state;
  const { period, filters, search, sort, loaded } = view;
  return useMemo(() => {
    const range = periodRange(period);
    const all = data.order.flatMap((id) => data.byId[id] ?? []);
    const inPer = range
      ? all.filter((r) => {
          const d = effDate(r);
          return d >= range[0] && d <= range[1];
        })
      : all;
    const truncated = !range && loaded < inPer.length;
    let windowRows = inPer;
    if (!range) {
      const key = SERVER_SORT[sort.key] ? sort.key : "date";
      windowRows = [...inPer]
        .sort((a, b) => compareRows(a, b, key, sort.dir, ctx))
        .slice(0, loaded);
    }
    const text = search.trim();
    const filtered = windowRows.filter((r) =>
      matchesFilters(r, filters, text, ctx),
    );
    const sortKey = truncated && !SERVER_SORT[sort.key] ? "date" : sort.key;
    filtered.sort((a, b) => compareRows(a, b, sortKey, sort.dir, ctx));
    // Parts sit under their split parent.
    const ids = new Set(filtered.map((r) => r.id));
    const nested: Movement[] = [];
    const kids = new Set<string>();
    filtered.forEach((r) => {
      if (r.split?.role === "child" && ids.has(r.split.parent)) kids.add(r.id);
    });
    filtered.forEach((r) => {
      if (kids.has(r.id)) return;
      nested.push(r);
      if (r.split?.role === "parent")
        r.split.children.forEach((c) => {
          if (kids.has(c)) nested.push(data.byId[c]!);
        });
    });
    const elsewhere =
      text && range
        ? all.filter(
            (r) =>
              !inPer.includes(r) &&
              matchesFilters(r, { ...EMPTY_FILTERS }, text, ctx),
          )
        : [];
    return {
      inPeriod: inPer,
      windowRows,
      filtered: nested,
      kids,
      truncated,
      totalCount: inPer.length,
      sortKey,
      elsewhere,
    };
  }, [data.order, data.byId, period, filters, search, sort, loaded, ctx]);
}
export function buildItems(
  win: MovementWindow,
  view: View,
  drafts: Draft[],
  rowH: number,
  ctx: WindowCtx,
): Item[] {
  const items: Item[] = drafts.map((d) => ({
    key: d.key,
    kind: "row",
    draft: d,
  }));
  const grouping =
    win.truncated && view.groupBy !== "group" ? "none" : view.groupBy;
  if (grouping === "none") {
    win.filtered.forEach((r) =>
      items.push({
        key: r.id,
        kind: "row",
        row: r,
        nested: win.kids.has(r.id),
      }),
    );
    return items;
  }
  const g = GROUPS[grouping]!;
  const gKey = g.key!;
  const gName = g.name!;
  const map = new Map<string, Movement[]>();
  win.filtered.forEach((r) => {
    const k = gKey(r, ctx);
    if (!map.has(k)) map.set(k, []);
    map.get(k)!.push(r);
  });
  const keys = [...map.keys()].sort((a, b) =>
    a === ""
      ? 1
      : b === ""
        ? -1
        : grouping === "month"
          ? a < b
            ? view.sort.dir === "desc"
              ? 1
              : -1
            : view.sort.dir === "desc"
              ? -1
              : 1
          : grouping === "counterparty" || grouping === "description"
            ? (view.savedView === "review"
                ? map.get(b)!.filter((r) => reviewStatus(r) === "pending")
                    .length -
                  map.get(a)!.filter((r) => reviewStatus(r) === "pending")
                    .length
                : 0) ||
              map.get(b)!.length - map.get(a)!.length ||
              gName(a).localeCompare(gName(b))
            : gName(a).localeCompare(gName(b)),
  );
  keys.forEach((k) => {
    const rows = map.get(k) ?? [];
    const gk = "g:" + grouping + ":" + k;
    items.push({
      key: gk,
      kind: "group",
      height: rowH + 10,
      gk: k,
      grouping,
      label: gName(k),
      rows,
      collapsed: !!view.collapsed[gk],
    });
    if (!view.collapsed[gk])
      rows.forEach((r) => items.push({ key: r.id, kind: "row", row: r }));
  });
  return items;
}
type CellInfo = {
  st?: Record<string, Value>;
  ref?: Refusal;
  changed?: boolean | null;
  eff?: Movement;
  lock?: string | null;
};
type CellSpan = { r0: number; r1: number; c0: number; c1: number };
export function SumLine({
  sums,
}: {
  sums: Record<string, { in: number; out: number; transfer: number }>;
}) {
  const cur = Object.keys(sums).sort((a, b) =>
    a === "EUR" ? -1 : b === "EUR" ? 1 : a.localeCompare(b),
  );
  return (
    <span className="gsum row g3 wrap">
      {cur.map((c) => (
        <span key={c} className="row g2">
          {c !== "EUR" ? <span className="tag">{c}</span> : null}
          {sums[c]!.in ? (
            <span>
              In <b>{fmtMoney(sums[c]!.in)}</b>
            </span>
          ) : null}
          {sums[c]!.out ? (
            <span>
              Out <b>{fmtMoney(sums[c]!.out)}</b>
            </span>
          ) : null}
          {sums[c]!.transfer ? (
            <span>
              Transfer <b>{fmtMoney(sums[c]!.transfer)}</b>
            </span>
          ) : null}
        </span>
      ))}
    </span>
  );
}

/* ── Cells. The status shows what is stored and was last checked; a staged
   row carries the dashed unsaved bar and says where it is going. ────── */
export function stagedSummary(eff: Movement, fields: string[]) {
  if (!fields.length) return "";
  if (fields.includes("cls") || fields.includes("share"))
    return `→ ${show("cls", eff.cls, eff)} · not saved`;
  return `${plural(fields.length, "edit")} · not saved`;
}
/* R22: short nouns for reasons, glyphs with names for markers. */
export const REASON_SHORT: Record<string, string> = {
  missing_business_classification: "Classification",
  missing_category: "Category",
  missing_taxable_base: "Base",
  missing_iva_amount: "IVA amount",
  missing_iva_rate: "IVA rate",
  missing_eur_tax_substrate: "EUR figures",
  missing_counterparty_identification_state: "VAT state",
  domestic_identification_on_intra_community_transaction: "Spanish VAT id",
  eu_member_state_on_export_transaction: "Export state",
  missing_counterparty_establishment_on_export: "Establishment",
  inadmissible_deduction_classification: "Deduction",
  missing_proportionality_reference: "Usage ratio",
  unsupported_currency: "EUR rate",
  unsupported_period: "Period",
  censo_ratio_mismatch: "Censo ratio",
  missing_home_office_afectacion: "Afectación",
  anomaly_non_declarable_iva_category: "IVA category",
  anomaly_non_declarable_recargo_equivalencia: "Recargo",
};
export function Mark({
  icon,
  label,
  className,
}: {
  icon: IconName;
  label: string;
  className?: string;
}) {
  return (
    <span
      className={cx("mark row", className)}
      role="img"
      aria-label={label}
      data-tip={label}
    >
      <Icon name={icon} size="xs" />
    </span>
  );
}
export function StatusCell({
  r,
  draft,
  check,
  outcome,
  actions = [],
}: {
  r?: Movement;
  draft?: Draft;
  check?: Check | null;
  outcome?: Outcome;
  actions?: StagedAction[];
}) {
  if (draft) {
    const missing = DRAFT_REQUIRED.filter(
      (k) => draft.fields[k] == null || draft.fields[k] === "",
    );
    return (
      <span className="row g1 st">
        <span className="tag" style={{ color: "var(--foreground)" }}>
          <Icon name="plus" />
          New
        </span>
        {missing.length ? (
          <span
            className="issue-n"
            data-tip={
              "Required before saving: " +
              missing.map((k) => F[k]!.label).join(", ")
            }
          >
            <Icon name="alert" size="xs" />
            {missing.length}
          </span>
        ) : null}
      </span>
    );
  }
  if (!r) return null;
  const S = statusOf(r, check);
  return (
    <span className="row status-cell">
      <span className={cx("st", S.key)} data-tip={S.label}>
        <Icon name={S.icon} size="xs" />
        <span className="st-word">
          {S.key === "needsFix" ? "Needs fixing" : S.label}
        </span>
        {S.n ? (
          <span className="issue-n" aria-hidden="true">
            {S.n}
          </span>
        ) : null}
      </span>
      {r.lifecycle !== "active" ? (
        <span className="tag">{LIFECYCLE[r.lifecycle].label}</span>
      ) : null}
      {r.issue === "duplicate" && r.lifecycle === "active" ? (
        <Mark
          icon="duplicate"
          label="Possible duplicate: archive it, or keep both"
        />
      ) : null}
      {r.sealed?.length ? (
        <Mark
          icon="lock"
          className="muted"
          label={
            "Sealed: " +
            r.sealed
              .map(
                (u) => `Modelo ${u.modelo} ${u.period}, ${SEAL_LABEL[u.state]}`,
              )
              .join("; ")
          }
        />
      ) : null}
      {r.suggestion && !actions.some((a) => a.type === "approve") ? (
        <Mark icon="agent" className="muted" label="Model suggestion waiting" />
      ) : null}
      {outcome?.status === "refused" ? (
        <Mark
          icon="refused"
          className="danger-t"
          label={"Refused: " + outcome.msg}
        />
      ) : outcome?.status === "unknown" ? (
        <Mark
          icon="unknown"
          className="warn-t"
          label="Outcome unknown: re-read first"
        />
      ) : outcome?.status === "notSent" ? (
        <Mark icon="pause" className="muted" label="Not sent: still staged" />
      ) : null}
    </span>
  );
}
export function DirCell({ v }: { v?: string | null }) {
  if (!v) return null;
  const d = DIRECTION[v as Direction];
  return (
    <span className={cx("dir", v)}>
      <Icon name={d.icon} size="xs" />
      {d.label}
    </span>
  );
}
export function ClsCell({
  r,
  pending,
}: {
  r: { cls: string; share?: number | null };
  pending?: boolean;
}) {
  const v = r.cls;
  const mark =
    v === "business"
      ? "business"
      : v === "personal"
        ? "personal"
        : v === "mixed"
          ? "mixed"
          : "none";
  return (
    <span className="cls">
      <span className={cx("cls-mark", mark)} aria-hidden="true"></span>
      <span className={CLASSIFIED.has(v) ? "" : "muted"}>
        {pending ? "→ " : ""}
        {show("cls", v, r)}
      </span>
    </span>
  );
}
export function MatchCell({ s }: { s?: Match | null }) {
  if (!s) return null;
  if (s.ambiguous)
    return (
      <span className="row g1">
        <span className="badge warning">Ambiguous</span>
        <span className="v muted">
          {plural(s.ties.length + 1, "candidate")}
        </span>
      </span>
    );
  return (
    <span className="row g1 v">
      <Icon name="link" size="xs" />
      <span className="truncate">{s.inv.number}</span>
      <span className="muted t-xs truncate">{s.chips[0]}</span>
    </span>
  );
}
export type CellCtx = {
  draft?: Draft;
  stored?: Movement;
  check?: Check | null;
  outcome?: Outcome;
  invoiceOf: (id: string) => Invoice | undefined;
  match?: Match | null;
  rowActions: StagedAction[];
  clsStaged?: boolean;
  nested?: boolean;
  unsaved?: boolean;
};
export function cellContent(
  col: GridColumn,
  r: Movement,
  ctx: CellCtx,
): ReactNode {
  const k = col.key;
  const { draft } = ctx;
  if (draft) {
    const v = draft.fields[k];
    const reqd = DRAFT_REQUIRED.includes(k);
    if (k === "status") return <StatusCell draft={draft} />;
    if (k === "select") return null;
    if ((v == null || v === "") && reqd)
      return (
        <span className="reqmiss">
          <Icon name="alert" size="xs" />
          Required
        </span>
      );
    if (k === "account")
      return v === undefined ? (
        <span className="placeholder">Choose…</span>
      ) : (
        <span className="v">{v ? ACCOUNT_LABEL[String(v)] : "No account"}</span>
      );
    if (k === "direction")
      return <DirCell v={typeof v === "string" ? v : null} />;
    if (k === "cls")
      return (
        <ClsCell
          r={{
            cls: typeof v === "string" && v ? v : "pending",
            share:
              typeof draft.fields.share === "number"
                ? draft.fields.share
                : null,
          }}
        />
      );
    if (k === "group") return <span className="placeholder">After saving</span>;
    if (
      [
        "eur",
        "invoice",
        "docs",
        "lifecycle",
        "classifiedBy",
        "modified",
        "match",
      ].includes(k)
    )
      return <span className="faint">—</span>;
    return <span className="v">{show(k, v, draft.fields)}</span>;
  }
  switch (k) {
    case "select":
      return ctx.unsaved ? (
        <span className="unsaved-bar" aria-hidden="true"></span>
      ) : null;
    case "status":
      return (
        <StatusCell
          r={ctx.stored}
          check={ctx.check}
          outcome={ctx.outcome}
          actions={ctx.rowActions}
        />
      );
    case "direction":
      return <DirCell v={r.direction} />;
    case "amount":
      return (
        <>
          <span className="v">{fmtMoney(r.amount)}</span>
          {r.currency !== "EUR" ? (
            <span className="cur">{r.currency}</span>
          ) : null}
        </>
      );
    case "date":
      return <span className="v tnum">{fmtDate(effDate(r))}</span>;
    case "eur":
      if (r.currency === "EUR") return null;
      if (r.fx)
        return (
          <span
            className="v"
            data-tip={`${r.fx.source} ${r.fx.rate} on ${fmtDateLong(r.fx.date)}`}
          >
            {fmtMoney(r.fx.eur)}
          </span>
        );
      return (
        <span
          className="reqmiss"
          data-tip="No exchange rate for this date: the EUR value is not known, and it is not zero."
        >
          <Icon name="noRate" size="xs" />
          No rate
        </span>
      );
    case "cls":
      return <ClsCell r={r} pending={ctx.clsStaged} />;
    case "ivaRate":
      return r.ivaRate == null ? null : (
        <span className="v">{pct(r.ivaRate)}</span>
      );
    case "share":
      return r.share == null ? null : <span className="v">{pct(r.share)}</span>;
    case "match":
      return <MatchCell s={ctx.match} />;
    case "invoice":
      if (r.invoiceId) {
        const inv = ctx.invoiceOf(r.invoiceId);
        return (
          <span className="row g1 v">
            <Icon name="link" size="xs" />
            {inv ? inv.number : shortId(r.invoiceId)}
          </span>
        );
      }
      if (ctx.match)
        return (
          <span
            className="tag"
            data-tip="A catalogue invoice settles this movement. Open the inspector's Invoice section to link it."
          >
            {ctx.match.ambiguous ? "Ambiguous match" : "Suggested"}
          </span>
        );
      return null;
    case "docs": {
      const n = (r.evidenceId ? 1 : 0) + r.attachments.length;
      return n ? (
        <span className="row g1">
          <Icon name="attach" size="xs" />
          <span className="tnum">{n}</span>
        </span>
      ) : null;
    }
    case "lifecycle":
      return r.lifecycle === "active" ? (
        <span className="muted">Active</span>
      ) : (
        <span className="tag">{LIFECYCLE[r.lifecycle].label}</span>
      );
    case "classifiedBy": {
      const b = r.classifiedBy;
      const t = b.startsWith("rule:")
        ? `Rule “${(RULES.find((x) => "rule:" + x.id === b) || {}).pattern || b.slice(5)}”`
        : b.startsWith("llm:")
          ? "Model, approved by you"
          : b.startsWith("derived:")
            ? "Worked out"
            : b === "manual"
              ? "You"
              : "Not yet";
      return <span className={b === "auto" ? "muted" : ""}>{t}</span>;
    }
    case "modified":
      return <span className="muted tnum">{fmtStamp(r.modified)}</span>;
    case "notes":
      return r.notes ? <span className="v">{r.notes}</span> : null;
    case "description":
      return (
        <>
          {ctx.nested ? (
            <span className="nest" aria-hidden="true">
              ↳
            </span>
          ) : null}
          <span className="v">{r.description}</span>
          {r.split?.role === "child" ? <span className="tag">part</span> : null}
        </>
      );
    default: {
      const v = getField(r, k);
      if (v == null || v === "") return null;
      return <span className="v">{show(k, v, r)}</span>;
    }
  }
}

/* ── Editors. ────────────────────────────────────────────────────────── */
export function FloatingNote({
  anchorId,
  children,
  tone,
  id,
}: {
  anchorId: string;
  children: ReactNode;
  tone: string;
  id?: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [pos, setPos] = useState<ReturnType<typeof place> | null>(null);
  useLayoutEffect(() => {
    const a = document.getElementById(anchorId);
    const el = ref.current;
    if (!a || !el) return;
    const upd = () => setPos(place(a, el, { align: "start", gap: 4 }));
    upd();
    const g = a.closest(".grid");
    g?.addEventListener("scroll", upd);
    return () => g?.removeEventListener("scroll", upd);
  }, [anchorId, children]);
  return (
    <Overlay>
      <div
        ref={ref}
        id={id}
        data-float=""
        className="edit-hint"
        role={tone === "error" ? "alert" : "note"}
        style={{ left: pos?.left ?? -9999, top: pos?.top ?? -9999 }}
      >
        {children}
      </div>
    </Overlay>
  );
}
export function canonOfEdit(k: string, r: Movement) {
  const v = getField(r, k);
  if (v == null) return "";
  if (k === "ivaRate" || k === "share")
    return String(+(Number(v) * 100).toFixed(4));
  if (F[k]?.editor === "amount") return canon(Number(v));
  return String(v);
}
type ComboOption = Omit<Option, "value"> & {
  value: string | null;
  clear?: boolean;
};
export function TextEditor({
  field,
  cellKey,
  row,
  isDraft,
  initial,
  onCommit,
  onCancel,
  onRefuse,
}: {
  field: string;
  cellKey: string;
  row: Movement;
  isDraft: boolean;
  initial: string;
  onCommit: (value: Value, move: string | null) => void;
  onCancel: () => void;
  onRefuse: (raw: string, msg: string) => void;
}) {
  const def = F[field]!;
  const [val, setVal] = useState(initial);
  const [err, setErr] = useState<string | null>(null);
  const ref = useRef<HTMLInputElement>(null);
  const done = useRef(false);
  const hintId = useId();
  const focusEditor = useEffectEvent(() => {
    const el = ref.current;
    if (!el) return;
    el.focus();
    if (initial.length > 1 || initial === canonOfEdit(field, row)) el.select();
    else el.setSelectionRange(el.value.length, el.value.length);
  });
  useEffect(() => {
    focusEditor();
  }, []);
  const tryParse = () =>
    parseFor(field, val, {
      row,
      draft: isDraft,
      draftRequired:
        isDraft && ["date", "amount", "description"].includes(field),
    });
  const commit = (move: string) => {
    const r = tryParse();
    if (r.error) {
      setErr(r.error);
      return false;
    }
    done.current = true;
    onCommit(r.empty ? null : r.value, move);
    return true;
  };
  const live = useMemo(() => {
    if (!["amount", "base", "ivaAmount", "ivaRate"].includes(field))
      return null;
    const r = parseFor(field, val, { row });
    if (r.error || r.empty) return null;
    return grossCheck({ ...row, [field]: r.value });
  }, [val, field, row]);
  const percent = field === "ivaRate" || field === "share";
  const quarterMove =
    field === "date" &&
    !isDraft &&
    (() => {
      const r = parseDateIso(val);
      return typeof r.value === "string" &&
        quarterLabel(r.value) !== quarterLabel(effDate(row))
        ? quarterLabel(r.value)
        : null;
    })();
  return (
    <div
      className={cx(
        "g-editor",
        (def.editor === "date" ||
          field === "date" ||
          field === "valueDate" ||
          field === "booked") &&
          "wide",
      )}
      aria-invalid={err ? "true" : undefined}
      onPointerDown={(e) => e.stopPropagation()}
    >
      <input
        ref={ref}
        className={def.num ? "num" : ""}
        value={val}
        aria-label={`${def.label} for ${row.description || "the new movement"}`}
        aria-invalid={!!err}
        aria-describedby={hintId}
        spellCheck="false"
        inputMode={def.editor === "amount" || percent ? "decimal" : undefined}
        onChange={(e) => {
          setVal(e.target.value);
          setErr(null);
        }}
        onKeyDown={(e) => {
          if (e.key === "Enter") {
            e.preventDefault();
            e.stopPropagation();
            commit(e.shiftKey ? "up" : "down");
          } else if (e.key === "Tab") {
            e.preventDefault();
            e.stopPropagation();
            commit(e.shiftKey ? "left" : "right");
          } else if (e.key === "Escape") {
            e.preventDefault();
            e.stopPropagation();
            done.current = true;
            onCancel();
          } else e.stopPropagation();
        }}
        onBlur={() => {
          if (done.current) return;
          const r = tryParse();
          done.current = true;
          if (r.error) {
            if (val !== initial) onRefuse(val, r.error);
            else onCancel();
          } else if (val !== initial) onCommit(r.empty ? null : r.value, null);
          else onCancel();
        }}
      />
      <FloatingNote
        id={hintId}
        anchorId={gridCellId(cellKey, field)}
        tone={err ? "error" : "hint"}
      >
        {err ? (
          <span className="err">
            <Icon name="alert" size="xs" />
            <span>{err}</span>
          </span>
        ) : null}
        {def.hint ? <span>{def.hint}</span> : null}
        {live ? (
          <span className="row g1" style={{ color: "var(--foreground)" }}>
            <Icon name="alert" size="xs" className="warn-t" />
            Gross check: {live.text}. The ledger will refuse it unless the
            figures close.
          </span>
        ) : null}
        {isIdentity(field, row) && !isDraft ? (
          <span className="row g1">
            <Icon name="info" size="xs" />
            Saved under a new reference: the movement's id changes.
          </span>
        ) : null}
        {quarterMove ? (
          <span className="row g1" style={{ color: "var(--foreground)" }}>
            <Icon name="calendar" size="xs" />
            Moves to {quarterMove}
            {row.uses?.length
              ? ` · affects ${[...new Set(row.uses.map((u) => "Modelo " + u.modelo))].join(", ")} ${quarterMove.slice(5)}`
              : ""}
            .
          </span>
        ) : null}
        <span>Enter keeps it in the tray · Esc cancels · Tab moves right</span>
      </FloatingNote>
    </div>
  );
}
/* A named listbox editor with type-to-filter; families are groups. */
export function ComboEditor({
  field,
  cellKey,
  row,
  initialFilter,
  onCommit,
  onCancel,
  ratios,
}: {
  field: string;
  cellKey: string;
  row: Movement;
  isDraft: boolean;
  initialFilter: string;
  onCommit: (
    value: Value,
    move: string | null,
    extra?: { share?: number | null },
  ) => void;
  onCancel: (move?: string) => void;
  ratios: DataState["ratios"];
}) {
  const def = F[field]!;
  const opts = useMemo((): ComboOption[] => {
    const list: ComboOption[] = optionsFor(field, row);
    return field === "account"
      ? [
          ...list,
          { value: "__none", label: "No account", note: "decide later" },
        ]
      : list;
  }, [field, row]);
  const [q, setQ] = useState(initialFilter || "");
  const [step, setStep] = useState("pick");
  const [share, setShare] = useState("");
  const [shareErr, setShareErr] = useState<string | null>(null);
  const [noMatch, setNoMatch] = useState(false);
  const shareRef = useRef<HTMLInputElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const anchor = document.getElementById(gridCellId(cellKey, field));
  const ref = useRef<HTMLDivElement>(null);
  const [pos, setPos] = useState<ReturnType<typeof place> | null>(null);
  const lbId = useId();
  useLayoutEffect(() => {
    if (anchor && ref.current) setPos(place(anchor, ref.current, { gap: 2 }));
  }, [step, anchor]);
  const current = getField(row, field);
  const filtered = useMemo(() => {
    const t = q.trim().toLowerCase();
    const list = opts.filter(
      (o) =>
        !t ||
        o.label.toLowerCase().includes(t) ||
        (o.token || "").toLowerCase().includes(t) ||
        (o.group || "").toLowerCase().includes(t),
    );
    const clear: ComboOption[] =
      def.clearable && !t && current != null && field !== "account"
        ? [{ value: null, label: "Clear value", clear: true }]
        : [];
    return [...clear, ...list];
  }, [q, opts, def.clearable, current, field]);
  const [hl, setHl] = useState(() =>
    Math.max(
      0,
      filtered.findIndex((o) => o.value === current),
    ),
  );
  useEffect(() => {
    setHl((h) => Math.min(h, Math.max(0, filtered.length - 1)));
    setNoMatch(false);
  }, [filtered.length]);
  useEffect(() => {
    inputRef.current?.focus();
  }, []);
  useEffect(() => {
    ref.current
      ?.querySelector(`[data-i="${hl}"]`)
      ?.scrollIntoView({ block: "nearest" });
  }, [hl]);
  useDismiss(ref, () => onCancel(), anchor);
  const ratio = row.category ? ratios[2026]?.[row.category] : undefined;
  const pickOpt = (o: ComboOption | undefined, move = "down") => {
    if (!o) {
      setNoMatch(true);
      return;
    }
    if (o.disabled) return;
    if (field === "cls" && o.value === "mixed") {
      setStep("share");
      setShare(
        row.share != null
          ? String(+(row.share * 100).toFixed(2))
          : ratio != null
            ? String(+(ratio * 100))
            : "",
      );
      setTimeout(() => shareRef.current?.focus(), 0);
      return;
    }
    onCommit(o.value === "__none" ? null : o.value, move);
  };
  const commitShare = () => {
    const r = parsePercent(share, { label: "Business share" });
    if (r.error || r.empty) {
      setShareErr(r.error || "Mixed needs a business share.");
      return;
    }
    onCommit("mixed", "down", { share: Number(r.value) });
  };
  const groups: { g: string; items: [ComboOption, number][] }[] = [];
  filtered.forEach((o, i) => {
    const g = o.group || "";
    let last = groups[groups.length - 1];
    if (!last || last.g !== g) groups.push((last = { g, items: [] }));
    last.items.push([o, i]);
  });
  const name = `${def.label} for ${row.description || "the new movement"}`;
  return (
    <Overlay>
      <div
        ref={ref}
        data-float=""
        className={cx(
          "combo",
          (field === "category" || field === "ivaCategory") && "wide",
        )}
        role="group"
        aria-label={name}
        style={{
          left: pos?.left ?? -9999,
          top: pos?.top ?? -9999,
          minWidth: anchor?.offsetWidth || undefined,
        }}
        onKeyDown={(e) => {
          e.stopPropagation();
          if (e.key === "Escape") {
            e.preventDefault();
            onCancel();
          }
        }}
      >
        {step === "pick" ? (
          <Fragment>
            <div className="combo-search">
              <Icon name="search" />
              <input
                ref={inputRef}
                value={q}
                placeholder={"Search " + def.label.toLowerCase()}
                role="combobox"
                aria-label={name}
                aria-expanded="true"
                aria-controls={lbId}
                aria-activedescendant={
                  filtered.length ? cellKey + "-opt-" + hl : undefined
                }
                aria-describedby={noMatch ? lbId + "-nm" : undefined}
                onChange={(e) => {
                  setQ(e.target.value);
                  setHl(0);
                }}
                onKeyDown={(e) => {
                  if (e.key === "ArrowDown") {
                    e.preventDefault();
                    setHl((h) => Math.min(filtered.length - 1, h + 1));
                  } else if (e.key === "ArrowUp") {
                    e.preventDefault();
                    setHl((h) => Math.max(0, h - 1));
                  } else if (e.key === "Enter") {
                    e.preventDefault();
                    pickOpt(filtered[hl], "down");
                  } else if (e.key === "Tab") {
                    e.preventDefault();
                    if (filtered[hl] && q.trim())
                      pickOpt(filtered[hl], e.shiftKey ? "left" : "right");
                    else onCancel(e.shiftKey ? "left" : "right");
                  } else if (e.key === "Escape") {
                    e.preventDefault();
                    onCancel();
                  }
                }}
              />
            </div>
            <div
              className="combo-list"
              role="listbox"
              id={lbId}
              aria-label={def.label + " choices"}
            >
              {filtered.length ? (
                groups.map((gr, gi) => {
                  const opts2 = gr.items.map(([o, i]) => (
                    <div
                      key={String(o.value) + i}
                      id={cellKey + "-opt-" + i}
                      data-i={i}
                      role="option"
                      aria-selected={o.value === current}
                      aria-disabled={o.disabled ? "true" : undefined}
                      className="combo-opt"
                      data-hl={i === hl}
                      data-tip={o.disabled || undefined}
                      onPointerMove={() => setHl(i)}
                      onClick={() => pickOpt(o)}
                    >
                      {o.clear ? (
                        <Icon name="erase" />
                      ) : o.icon ? (
                        <Icon name={o.icon} size="xs" />
                      ) : o.value === current ? (
                        <Icon name="tick" size="xs" />
                      ) : (
                        <span className="icon-gap"></span>
                      )}
                      <span className="truncate">{o.label}</span>
                      {o.note ? (
                        <span className="opt-note">{o.note}</span>
                      ) : null}
                    </div>
                  ));
                  return gr.g ? (
                    <div
                      key={gr.g}
                      role="group"
                      aria-labelledby={lbId + "-g" + gi}
                    >
                      <div
                        id={lbId + "-g" + gi}
                        className="combo-group"
                        role="presentation"
                      >
                        {gr.g}
                      </div>
                      {opts2}
                    </div>
                  ) : (
                    <Fragment key={"_" + gi}>{opts2}</Fragment>
                  );
                })
              ) : (
                <div className="combo-empty" id={lbId + "-nm"}>
                  No match for “{q}” · Esc to cancel
                </div>
              )}
            </div>
            {noMatch && filtered.length === 0 ? null : null}
            {field === "cls" && row.direction === "transfer" ? (
              <div className="combo-foot muted">
                Transfers can only be Personal or stay unclassified.
              </div>
            ) : null}
            {field === "category" ? (
              <div className="combo-foot muted">
                {CATEGORY_OPTIONS.length} categories in {FAMILIES.length}{" "}
                families. A category decides deductibility, not the IVA figures.
              </div>
            ) : null}
          </Fragment>
        ) : (
          <div className="combo-foot" style={{ borderTop: 0 }}>
            <Field
              label="Business share"
              req
              hint={
                ratio != null
                  ? `Your 2026 ratio for ${CATEGORY_LABEL[row.category ?? ""]} is ${pct(ratio)}.`
                  : "Percent of business use: 50 for 50%."
              }
              error={shareErr}
            >
              <Input
                ref={shareRef}
                size="sm"
                value={share}
                inputMode="decimal"
                aria-invalid={!!shareErr}
                onChange={(e) => {
                  setShare(e.target.value);
                  setShareErr(null);
                }}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === "Tab") {
                    e.preventDefault();
                    commitShare();
                  } else if (e.key === "Escape") {
                    e.preventDefault();
                    setStep("pick");
                  }
                }}
              />
            </Field>
            <div className="row g2">
              <Button size="xs" variant="ghost" onClick={() => setStep("pick")}>
                Back
              </Button>
              <span className="f1"></span>
              <Button size="xs" onClick={commitShare}>
                Set Mixed
              </Button>
            </div>
          </div>
        )}
      </div>
    </Overlay>
  );
}

/* ── Group header quick actions (R8). ─────────────────────────────────── */
export function GroupClassify({
  anchor,
  rows,
  mode,
  onClose,
}: {
  anchor: HTMLElement;
  rows: Movement[];
  mode: string;
  onClose: () => void;
}) {
  const [state, dispatch] = useStore();
  const page = usePage();
  const [cls, setCls] = useState(mode === "category" ? "" : mode);
  const [cat, setCat] = useState("");
  const [share, setShare] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const eligible = rows.filter(
    (r) =>
      !lockReason(
        effective(r, state.staged.rows),
        "cls",
        false,
        state.staged.actions,
      ),
  );
  const sealed = rows.length - eligible.length;
  const stage = () => {
    const ch: StageChange[] = [];
    let sh = null;
    if (cls === "mixed") {
      const r = parsePercent(share, { label: "Business share" });
      if (r.error || r.empty)
        return setErr(r.error || "Mixed needs a business share.");
      sh = r.value;
    }
    eligible.forEach((r) => {
      if (r.direction === "transfer" && cls && cls !== "personal") return;
      if (cls) {
        ch.push({ id: r.id, field: "cls", value: cls });
        ch.push({
          id: r.id,
          field: "share",
          value: cls === "mixed" ? sh : null,
        });
      }
      if (cat && (cls || CLASSIFIED.has(r.cls)) && cls !== "personal")
        ch.push({ id: r.id, field: "category", value: cat });
    });
    dispatch({ type: "STAGE", changes: ch, label: "Group change" });
    page.toast(
      `Staged for ${plural(new Set(ch.map((c) => c.id)).size, "movement")}${sealed ? ` (${sealed} sealed or read-only skipped)` : ""}`,
    );
    onClose();
  };
  return (
    <Popover
      anchor={anchor}
      onClose={onClose}
      width="20rem"
      label="Classify this group"
      className="col g3"
    >
      <b className="fw6">{plural(rows.length, "movement")} in this group</b>
      {mode !== "category" ? (
        <Seg
          size="sm"
          label="Classification"
          value={cls}
          onChange={setCls}
          options={(["business", "personal", "mixed"] as const).map((v) => ({
            value: v,
            label: CLS[v].label,
          }))}
        />
      ) : null}
      {cls === "mixed" ? (
        <Field label="Business share" req error={err}>
          <Input
            size="sm"
            data-autofocus
            value={share}
            placeholder="e.g. 50"
            onChange={(e) => {
              setShare(e.target.value);
              setErr(null);
            }}
          />
        </Field>
      ) : null}
      {cls !== "personal" ? (
        <Field
          label={
            mode === "category" ? "Category" : "Category (asked with Business)"
          }
        >
          <Select
            size="sm"
            value={cat}
            onChange={(e) => setCat(e.target.value)}
          >
            <option value="">
              {mode === "category" ? "Choose…" : "Leave as it is"}
            </option>
            {FAMILIES.map(([, fl, cs]) => (
              <optgroup key={fl} label={fl}>
                {cs.map((c) => (
                  <option key={c} value={c}>
                    {CATEGORY_LABEL[c]}
                  </option>
                ))}
              </optgroup>
            ))}
          </Select>
        </Field>
      ) : null}
      <div className="row g2">
        <span className="muted t-sm f1">
          {sealed
            ? `${sealed} sealed or read-only skipped`
            : "Staged, not saved"}
        </span>
        <Button size="sm" disabled={!cls && !cat} onClick={stage}>
          Set for {eligible.length}
        </Button>
      </div>
    </Popover>
  );
}

/* ── The movements section. ─────────────────────────────────────────── */
export function MovementsSection() {
  const [state, dispatch] = useStore();
  const page = usePage();
  const toast = useToast();
  const { view, data, staged } = state;
  const narrow = useNarrow();
  const stagedIds = useMemo(
    () => stagedRowIds({ staged, data }),
    [staged, data],
  );
  const recon = useMemo(
    () => reconciliationSuggestions(data, staged.actions),
    [data, staged.actions],
  );
  const invoiceOf = useCallback(
    (id: string) => data.invoices.find((i) => i.id === id),
    [data.invoices],
  );
  const ctx = useMemo(
    () => ({
      check: state.check,
      stagedIds,
      bestByRow: recon.best,
      invoiceNumber: (id: string) => invoiceOf(id)?.number || "",
    }),
    [state.check, stagedIds, recon, invoiceOf],
  );
  const win = useMovementWindow(state, ctx);
  PREFS.yearInDates = view.period.code === "ALL";
  const rowH = view.density === "compact" ? 28 : 36;
  const items = useMemo(
    () => buildItems(win, view, staged.drafts, rowH, ctx),
    [win, view, staged.drafts, rowH, ctx],
  );
  const rowItems = useMemo(
    () => items.filter((i): i is RowItem => i.kind === "row"),
    [items],
  );
  const startFocus = useRef(page.startFocus);
  const [active, setActive] = useState<GridActive | null>(
    startFocus.current ?? null,
  );
  const [anchor, setAnchor] = useState<GridActive | null>(null);
  const [editing, setEditing] = useState<{
    key: string;
    col: string;
    initial: string;
  } | null>(null);
  const [note, setNote] = useState<{
    key: string;
    col: string;
    text: string;
  } | null>(null);
  const [menu, setMenu] = useState<{
    point: { x: number; y: number };
    items: MenuItem[];
  } | null>(null);
  const [groupPop, setGroupPop] = useState<{
    anchor: HTMLElement;
    rows: Movement[];
    mode: string;
  } | null>(null);
  const [sheet, setSheet] = useState(false);
  const [panelMode, setPanelMode] = useState("match");
  const gridApi = page.gridApi;
  useEffect(() => {
    const at = startFocus.current;
    if (!at) return;
    const timer = setTimeout(() => gridApi.current?.jumpTo(at.key, at.col), 60);
    return () => clearTimeout(timer);
  }, [gridApi]);

  const visibleKeys = useMemo(() => {
    const rest = view.order.filter(
      (k) => view.visible.includes(k) && !STICKY.includes(k),
    );
    return [
      ...STICKY.filter((k) => k !== "status" || view.visible.includes(k)),
      ...rest,
    ];
  }, [view.order, view.visible]);
  const selectedIds = Object.keys(state.selection);
  const visibleIds = useMemo(() => rowItems.map((i) => i.key), [rowItems]);
  const visibleSet = useMemo(() => new Set(visibleIds), [visibleIds]);
  const hiddenSelected = selectedIds.filter((id) => !visibleSet.has(id));
  const allVisibleSelected =
    visibleIds.length > 0 && visibleIds.every((id) => state.selection[id]);
  const someSelected = visibleIds.some((id) => state.selection[id]);
  const columns = useMemo(() => {
    const lastSticky = [...visibleKeys]
      .reverse()
      .find((k) => STICKY.includes(k));
    return visibleKeys.map((k) => ({
      cellClass: k === "select" ? "selcol" : undefined,
      key: k,
      width:
        view.widths[k] ||
        (k === "status"
          ? narrow
            ? 64
            : view.density === "compact"
              ? 80
              : 136
          : (COL_WIDTH[k] ?? 120)),
      flex: view.widths[k] ? undefined : COL_FLEX[k],
      sticky: STICKY.includes(k),
      lastSticky: k === lastSticky,
      num: NUM_COLS.has(k),
      minWidth: k === "select" ? 36 : COL_FLEX[k] ? (COL_WIDTH[k] ?? 56) : 56,
      resizable: k !== "select",
      sortable:
        !["select", "docs", "invoice", "match"].includes(k) &&
        (!win.truncated || !!SERVER_SORT[k]),
      sortDir: view.sort.key === k ? view.sort.dir : null,
      headerTip:
        win.truncated && k !== "select" && !SERVER_SORT[k]
          ? `Sorting by ${COL_LABEL[k]} needs the whole window. Load all, or choose a period.`
          : undefined,
      header:
        k === "select" ? (
          <input
            type="checkbox"
            className="checkbox"
            aria-label="Select the visible movements (Ctrl-click to add them)"
            checked={allVisibleSelected}
            ref={(el) => {
              if (el) el.indeterminate = !allVisibleSelected && someSelected;
            }}
            onChange={() => {}}
            onClick={(e) => {
              e.stopPropagation();
              if (allVisibleSelected && !e.ctrlKey && !e.metaKey)
                dispatch({ type: "SELECT", mode: "remove", ids: visibleIds });
              else
                dispatch({
                  type: "SELECT",
                  mode: e.ctrlKey || e.metaKey ? "add" : "set",
                  ids: visibleIds,
                });
            }}
          />
        ) : (
          <span className="truncate">
            {COL_LABEL[k]}
            {staged.drafts.length && DRAFT_REQUIRED.includes(k) ? (
              <span className="req" aria-hidden="true">
                *
              </span>
            ) : null}
          </span>
        ),
    }));
  }, [
    visibleKeys,
    view.widths,
    view.sort,
    win.truncated,
    allVisibleSelected,
    someSelected,
    staged.drafts.length,
    visibleIds,
    dispatch,
    narrow,
    view.density,
  ]);

  const followRekey = useEffectEvent(() => {
    if (state.rekeyed && active?.key === state.rekeyed.from)
      setActive({ ...active, key: state.rekeyed.to });
  });
  useEffect(() => {
    followRekey();
  }, [state.rekeyed]);
  const settleActive = useEffectEvent(() => {
    if (
      active &&
      (active.key === "__head" || items.some((i) => i.key === active.key))
    )
      return;
    setActive(
      rowItems.length
        ? {
            key: rowItems[0]!.key,
            col:
              active?.col && active.col !== "select"
                ? active.col
                : "description",
          }
        : null,
    );
    setAnchor(null);
  });
  useEffect(() => {
    settleActive();
  }, [items]);
  const focusAdded = useEffectEvent(() => {
    if (state.lastAdded && data.byId[state.lastAdded])
      setActive({ key: state.lastAdded, col: "description" });
  });
  useEffect(() => {
    focusAdded();
  }, [state.lastAdded]);
  page.register({
    startAdd: () => startAdd(),
    visibleIds: () => visibleIds,
    focusGrid: () => gridApi.current?.focus(),
    startEdit: (id, col) => {
      if (!visibleSet.has(id)) return false;
      setActive({ key: id, col });
      setTimeout(() => {
        gridApi.current?.jumpTo(id, col);
        startEdit(id, col);
      }, 40);
      return true;
    },
    windowInfo: () => ({
      truncated: win.truncated,
      total: win.totalCount,
      loaded: win.windowRows.length,
    }),
    focusFirst: () => {
      const k = rowItems.find((i) => !i.draft)?.key;
      if (k) {
        setActive({ key: k, col: "description" });
        setTimeout(() => gridApi.current?.jumpTo(k, "description"), 30);
      }
    },
    jumpTo: (id, col) => {
      if (!visibleSet.has(id)) return false;
      setActive({ key: id, col: col || "description" });
      setAnchor(null);
      setTimeout(() => gridApi.current?.jumpTo(id, col || "description"), 30);
      return true;
    },
  });

  // A draft reads as a movement with the fields it has so far.
  const effOf = (it: RowItem): Movement =>
    it.draft
      ? ({
          ...it.draft.fields,
          id: it.key,
          attachments: [],
          history: [],
          lifecycle: "active",
          uses: [],
        } as unknown as Movement)
      : effective(it.row!, staged.rows, staged.actions);
  const itemIndex = useMemo(() => {
    const m = new Map<string, number>();
    rowItems.forEach((it, i) => m.set(it.key, i));
    return m;
  }, [rowItems]);
  const colIndex = useCallback(
    (k: string) => visibleKeys.indexOf(k),
    [visibleKeys],
  );
  const range = useMemo((): CellSpan | null => {
    if (
      !anchor ||
      !active ||
      (anchor.key === active.key && anchor.col === active.col)
    )
      return null;
    const a = itemIndex.get(anchor.key),
      b = itemIndex.get(active.key);
    if (a == null || b == null) return null;
    const c1 = colIndex(anchor.col),
      c2 = colIndex(active.col);
    return {
      r0: Math.min(a, b),
      r1: Math.max(a, b),
      c0: Math.min(c1, c2),
      c1: Math.max(c1, c2),
    };
  }, [anchor, active, itemIndex, colIndex]);
  const rangeCells = () => {
    const at = active ? itemIndex.get(active.key) : undefined;
    const r: CellSpan | null =
      range ||
      (active && at != null
        ? {
            r0: at,
            r1: at,
            c0: colIndex(active.col),
            c1: colIndex(active.col),
          }
        : null);
    if (!r) return [];
    const out: { it: RowItem; col: string }[][] = [];
    for (let i = r.r0; i <= r.r1; i++) {
      const row: { it: RowItem; col: string }[] = [];
      for (let j = r.c0; j <= r.c1; j++)
        row.push({ it: rowItems[i]!, col: visibleKeys[j]! });
      out.push(row);
    }
    return out;
  };
  const lockOf = (it: RowItem, col: string) =>
    lockReason(
      it.draft ? effOf(it) : effOf(it),
      col,
      !!it.draft,
      staged.actions,
    );

  const onActive = (key: string, col: string, info: MoveInfo = {}) => {
    const it = items.find((x) => x.key === key);
    if (key === "__head" || info.via === "focus" || info.via === "jump") {
      setActive({ key, col });
      if (info.via === "jump") setAnchor(null);
      return;
    }
    if (it && it.kind !== "row") {
      setActive({ key, col });
      return;
    }
    if (info.extend) {
      const anc = anchor || active || { key, col };
      setAnchor(anc);
      setActive({ key, col });
      const a = itemIndex.get(anc.key),
        b = itemIndex.get(key);
      if (a != null && b != null) {
        const ids = rowItems
          .slice(Math.min(a, b), Math.max(a, b) + 1)
          .map((x) => x.key);
        if (ids.length > 1) dispatch({ type: "SELECT", mode: "set", ids });
      }
      return;
    }
    setAnchor({ key, col });
    setActive({ key, col });
    if (info.via === "key" && selectedIds.length <= 1)
      dispatch({ type: "SELECT", mode: "set", ids: [key] });
  };
  const onCellPointerDown = (
    e: PointerEvent<HTMLDivElement>,
    it: Item,
    col: GridColumn | null,
  ) => {
    setNote(null);
    if (!it || it.kind !== "row" || !col) return;
    if (col.key === "select") {
      e.preventDefault();
      dispatch({ type: "SELECT", mode: "toggle", ids: [it.key] });
      setActive({ key: it.key, col: "select" });
      setAnchor({ key: it.key, col: "select" });
      return false;
    }
    if (e.button === 2) {
      if (!state.selection[it.key])
        dispatch({ type: "SELECT", mode: "set", ids: [it.key] });
      return;
    }
    if (e.ctrlKey || e.metaKey) {
      dispatch({ type: "SELECT", mode: "toggle", ids: [it.key] });
      setActive({ key: it.key, col: col.key });
      setAnchor({ key: it.key, col: col.key });
      return false;
    }
    if (e.shiftKey && active) {
      const a = itemIndex.get((anchor || active).key),
        b = itemIndex.get(it.key);
      if (a != null && b != null)
        dispatch({
          type: "SELECT",
          mode: "set",
          ids: rowItems
            .slice(Math.min(a, b), Math.max(a, b) + 1)
            .map((x) => x.key),
        });
      setActive({ key: it.key, col: col.key });
      if (!anchor) setAnchor(active);
      return false;
    }
    dispatch({ type: "SELECT", mode: "set", ids: [it.key] });
    if (narrow) setSheet(true);
    if (editing && !(editing.key === it.key && editing.col === col.key))
      setEditing(null);
  };
  useEffect(() => {
    if (!note) return;
    const t = setTimeout(() => setNote(null), 5200);
    return () => clearTimeout(t);
  }, [note]);

  function startEdit(key: string, col: string, initialChar?: string) {
    const it = items.find((x) => x.key === key);
    if (!it || it.kind !== "row") return;
    if (col === "select") {
      dispatch({ type: "SELECT", mode: "toggle", ids: [key] });
      return;
    }
    const reason = lockOf(it, col);
    if (reason) {
      setNote({ key, col, text: reason });
      announce(reason);
      return;
    }
    const def = F[col];
    if (!def) {
      setNote({
        key,
        col,
        text: READONLY_REASON[col] || "This column is read-only.",
      });
      return;
    }
    if (it.draft && !DRAFT_FIELDS.includes(col)) {
      setNote({ key, col, text: "Set after the movement is saved." });
      return;
    }
    const r = effOf(it);
    const init =
      def.editor === "combo"
        ? initialChar || ""
        : initialChar != null
          ? initialChar
          : canonOfEdit(col, r);
    setEditing({ key, col, initial: init });
    setNote(null);
  }
  const stage = (changes: StageChange[], label: string) => {
    if (changes.length) dispatch({ type: "STAGE", changes, label });
  };
  const moveFrom = (key: string, col: string, move: string | null) => {
    const i = itemIndex.get(key);
    if (move === "down" || move === "up") {
      const j = Math.max(
        0,
        Math.min(rowItems.length - 1, (i ?? 0) + (move === "down" ? 1 : -1)),
      );
      setActive({ key: rowItems[j]!.key, col });
      setAnchor(null);
      gridApi.current?.jumpTo(rowItems[j]!.key, col);
    } else if (move === "right" || move === "left") {
      const c = colIndex(col) + (move === "right" ? 1 : -1);
      const nc = visibleKeys[Math.max(1, Math.min(visibleKeys.length - 1, c))]!;
      setActive({ key, col: nc });
      setAnchor(null);
      gridApi.current?.jumpTo(key, nc);
    } else gridApi.current?.focus();
  };
  const commitEdit = (
    value: Value,
    move: string | null,
    extra?: { share?: number | null },
  ) => {
    if (!editing) return;
    const { key, col } = editing;
    const changes = [{ id: key, field: col, value }];
    if (extra?.share != null)
      changes.push({ id: key, field: "share", value: extra.share });
    if (col === "cls" && value !== "mixed")
      changes.push({ id: key, field: "share", value: null });
    stage(changes, `Edit ${F[col]!.label.toLowerCase()}`);
    setEditing(null);
    moveFrom(key, col, move);
  };
  const cancelEdit = (move?: string | null) => {
    const e = editing;
    setEditing(null);
    if (e) {
      if (move) moveFrom(e.key, e.col, move);
      else gridApi.current?.focus();
    }
  };
  const refuseEdit = (raw: string, msg: string) => {
    const e = editing;
    if (!e) return;
    dispatch({
      type: "REFUSE",
      cells: [{ id: e.key, field: e.col, raw, msg }],
    });
    setEditing(null);
  };

  function startAdd() {
    dispatch({ type: "ADD_DRAFT" });
    page.setSection("movements");
    setTimeout(() => {
      const key = "draft-" + (state.draftN + 1);
      setActive({ key, col: "date" });
      setAnchor(null);
      gridApi.current?.scrollToTop();
      setTimeout(() => {
        gridApi.current?.jumpTo(key, "date");
        setEditing({ key, col: "date", initial: "" });
      }, 40);
    }, 0);
  }

  const clearCells = () => {
    const cells = rangeCells().flat();
    const changes: StageChange[] = [];
    const refused: string[] = [];
    cells.forEach(({ it, col }) => {
      if (!it || col === "select") return;
      const reason = lockOf(it, col);
      if (reason) return refused.push(reason);
      const def = F[col];
      if (!def) return;
      if (!def.clearable)
        return refused.push(
          def.clearRefusal ||
            `${def.label} cannot be cleared${def.required ? ": it is required" : col === "notes" ? ": notes can be replaced but not emptied" : ""}.`,
        );
      changes.push({ id: it.key, field: col, value: null });
    });
    stage(changes, "Clear cells");
    if (refused.length && active)
      setNote({
        key: active.key,
        col: active.col,
        text:
          refused[0] +
          (refused.length > 1 ? ` (${refused.length} cells kept)` : ""),
      });
    else if (changes.length)
      toast(`Cleared ${plural(changes.length, "cell")} · not saved`);
  };
  const fillDown = () => {
    if (!range || range.r0 === range.r1) {
      if (active)
        setNote({
          key: active.key,
          col: active.col,
          text: "Select two or more rows first (Shift+Arrow), then fill down with Ctrl+D.",
        });
      return;
    }
    const changes: StageChange[] = [];
    let kept = 0;
    for (let j = range.c0; j <= range.c1; j++) {
      const col = visibleKeys[j]!;
      const def = F[col];
      if (!def) continue;
      const src = effOf(rowItems[range.r0]!);
      const v = getField(src, col);
      if ((v == null || v === "") && !def.clearable) {
        kept += range.r1 - range.r0;
        continue;
      }
      for (let i = range.r0 + 1; i <= range.r1; i++) {
        const it = rowItems[i]!;
        if (lockOf(it, col)) {
          kept++;
          continue;
        }
        if (
          col === "cls" &&
          effOf(it).direction === "transfer" &&
          v !== "personal"
        ) {
          kept++;
          continue;
        }
        changes.push({ id: it.key, field: col, value: v });
        if (col === "cls")
          changes.push({
            id: it.key,
            field: "share",
            value: src.share ?? null,
          });
      }
    }
    stage(changes, "Fill down");
    toast(
      `Filled ${plural(changes.filter((c) => c.field !== "share" || c.value != null).length, "cell")} down · not saved${kept ? ` · ${kept} kept (locked or cannot be cleared)` : ""}`,
    );
  };
  const onCopy = (e: ClipboardEvent<HTMLDivElement>) => {
    if ((e.target as HTMLElement).tagName === "INPUT") return;
    const cells = rangeCells();
    if (!cells[0]) return;
    const text = cells
      .map((row) =>
        row
          .map(({ it, col }) => {
            if (col === "select" || col === "status") return "";
            const r = effOf(it);
            return tsvEscape(
              col === "eur"
                ? r.fx
                  ? canon(r.fx.eur)
                  : ""
                : col === "date"
                  ? effDate(r) || r.date
                  : canonOf(col, getField(r, col)),
            );
          })
          .join("\t"),
      )
      .join("\n");
    e.clipboardData.setData("text/plain", text);
    e.preventDefault();
    toast(`Copied ${cells.length} × ${cells[0].length} cells as TSV`);
  };
  /* Paste (R7): every cell through its grammar; a blank leaves the cell as
     it is; a block of several rows, or one that touches an identity
     column, is previewed before anything is staged. */
  function planPaste(text: string): PastePlan | { error: string } {
    const parsed = parseTsv(text.replace(/\n$/, ""));
    if (parsed.error) return { error: parsed.error };
    const m = parsed.rows;
    const start = range
      ? { r: range.r0, c: range.c0 }
      : {
          r: (active && itemIndex.get(active.key)) ?? 0,
          c: active ? colIndex(active.col) : 0,
        };
    const single = m.length === 1 && m[0]!.length === 1;
    const targets: { i: number; j: number; raw: string }[] = [];
    let dropped = 0;
    if (single && range) {
      for (let i = range.r0; i <= range.r1; i++)
        for (let j = range.c0; j <= range.c1; j++)
          targets.push({ i, j, raw: m[0]![0]! });
    } else
      m.forEach((row, di) =>
        row.forEach((raw, dj) => {
          if (
            start.r + di >= rowItems.length ||
            start.c + dj >= visibleKeys.length
          )
            dropped++;
          else targets.push({ i: start.r + di, j: start.c + dj, raw });
        }),
      );
    const changes: StageChange[] = [];
    const refusals: PasteRefusal[] = [];
    let blanks = 0;
    const identity = new Set<string>();
    const cols = new Set<string>();
    targets.forEach(({ i, j, raw }) => {
      const it = rowItems[i];
      const col = visibleKeys[j];
      if (!it || !col || col === "select") return;
      if (String(raw).trim() === "") {
        blanks++;
        return;
      }
      cols.add(col);
      const r = effOf(it);
      const reason =
        lockOf(it, col) ||
        (F[col] ? null : READONLY_REASON[col] || "Read-only column.");
      if (reason)
        return refusals.push({ id: it.key, field: col, raw, msg: reason });
      const p = parseFor(col, raw, { row: r, draft: !!it.draft });
      if (p.error)
        return refusals.push({ id: it.key, field: col, raw, msg: p.error });
      if (col === "cls" && p.value === "mixed" && r.share == null)
        return refusals.push({
          id: it.key,
          field: col,
          raw,
          msg: "Mixed needs a business share: paste the share column too, or set it in the cell.",
        });
      if (sameValue(getField(r, col), p.value)) return;
      if (!it.draft && isIdentity(col, it.row)) identity.add(it.key);
      changes.push({ id: it.key, field: col, value: p.value });
    });
    const rowsTouched = new Set(targets.map((t) => t.i)).size;
    return {
      changes,
      refusals,
      blanks,
      dropped,
      identity: identity.size,
      cols: [...cols],
      rows: rowsTouched,
      needsPreview: m.length > 1 || identity.size > 0 || dropped > 0,
    };
  }
  const doPaste = (plan: PastePlan) => {
    stage(plan.changes, "Paste");
    if (plan.refusals.length)
      dispatch({
        type: "REFUSE",
        cells: plan.refusals.filter((x) => F[x.field]),
      });
    toast(
      `Pasted ${plural(plan.changes.length, "cell")} · not saved${plan.refusals.length ? ` · ${plan.refusals.length} refused, marked in the grid` : ""}`,
    );
  };
  const onPaste = (e: ClipboardEvent<HTMLDivElement>) => {
    if ((e.target as HTMLElement).tagName === "INPUT") return;
    const text = e.clipboardData.getData("text/plain");
    if (!text || !active || !itemIndex.has(active.key)) return;
    e.preventDefault();
    const plan = planPaste(text);
    if ("error" in plan) {
      toast(plan.error);
      announce(plan.error);
      return;
    }
    if (plan.needsPreview)
      page.openDialog("paste", { plan, onPaste: () => doPaste(plan) });
    else doPaste(plan);
  };

  const openRowMenu = (point: { x: number; y: number }, it: Item) => {
    if (!it || it.kind !== "row") return;
    const ids = state.selection[it.key] ? selectedIds : [it.key];
    setMenu({ point, items: rowMenuItems(it, ids) });
  };
  function rowMenuItems(it: RowItem, ids: string[]): MenuItem[] {
    const r = it.draft ? null : it.row;
    const n = ids.length;
    const sfx = n > 1 ? ` (${n})` : "";
    if (it.draft)
      return [
        {
          label: "Edit cell",
          icon: "edit",
          shortcut: "Enter",
          onSelect: () => active && startEdit(active.key, active.col),
        },
        {
          label: "Remove this draft",
          icon: "trash",
          onSelect: () => dispatch({ type: "REMOVE_DRAFT", key: it.key }),
        },
      ];
    const hasStaged = stagedIds.has(it.key);
    const cellStaged = active && active.col in (staged.rows[it.key] ?? {});
    return [
      {
        label: "Edit cell",
        icon: "edit",
        shortcut: "Enter",
        onSelect: () => active && startEdit(active.key, active.col),
      },
      {
        label: "Copy cells",
        icon: "copy",
        shortcut: "Ctrl+C",
        onSelect: () => document.execCommand("copy"),
      },
      {
        label: "Fill down",
        icon: "arrow",
        shortcut: "Ctrl+D",
        onSelect: fillDown,
        disabled: !range,
        reason: "Select two or more rows first.",
      },
      {
        label: "Clear cell",
        icon: "erase",
        shortcut: "Delete",
        onSelect: clearCells,
      },
      {
        label: "Revert cell",
        icon: "undo",
        shortcut: "Ctrl+Alt+Z",
        disabled: !cellStaged,
        reason: "This cell has no unsaved change.",
        onSelect: () =>
          active &&
          dispatch({ type: "REVERT_CELL", id: it.key, field: active.col }),
      },
      {
        label: "Revert movement",
        icon: "reset",
        disabled: !hasStaged,
        reason: "This movement has no unsaved change.",
        onSelect: () => dispatch({ type: "REVERT_ROW", id: it.key }),
      },
      { sep: true },
      { heading: "Classify" + sfx },
      {
        label: "Business…",
        icon: "tick",
        shortcut: "Alt+B",
        onSelect: () => page.classifySelection("business", ids),
      },
      {
        label: "Personal",
        icon: "user",
        shortcut: "Alt+P",
        onSelect: () => page.classifySelection("personal", ids),
      },
      {
        label: "Mixed…",
        icon: "scale",
        shortcut: "Alt+M",
        onSelect: () => page.classifySelection("mixed", ids),
      },
      {
        label: "Ask the model",
        icon: "agent",
        onSelect: () => page.askModel(ids),
        disabled: state.proto.state === "modelUnavailable",
        reason: "The local model is not available.",
      },
      { sep: true },
      {
        label: "Show in the inspector",
        icon: "panelRight",
        shortcut: "Alt+I",
        onSelect: () => dispatch({ type: "VIEW", patch: { inspector: true } }),
      },
      ...(r && r.issue === "duplicate" && r.lifecycle === "active"
        ? [
            {
              label: "Archive as duplicate",
              icon: "archive" as const,
              onSelect: () => page.stageArchiveDuplicate(r.id),
            },
            {
              label: "Keep both",
              icon: "check" as const,
              onSelect: () => page.stageKeepBoth(r.id),
            },
          ]
        : []),
      {
        label: "Split into parts…",
        icon: "split",
        onSelect: () => page.openAction("split", [it.key]),
        disabled:
          n > 1 || !r || !!lockReason(r, "amount", false, staged.actions),
        reason:
          (r && lockReason(r, "amount", false, staged.actions)) ||
          "Split one movement at a time.",
      },
      {
        label: "Archive…" + sfx,
        icon: "archive",
        onSelect: () => page.openAction("archive", ids),
      },
      {
        label: "Set aside…" + sfx,
        icon: "stash",
        onSelect: () => page.openAction("stash", ids),
      },
      {
        label: "Exclude from filing…" + sfx,
        icon: "eyeOff",
        onSelect: () => page.openAction("exclude", ids),
      },
      {
        label: "Restore…" + sfx,
        icon: "unarchive",
        onSelect: () => page.openAction("restore", ids),
        disabled: !ids.some(
          (id) =>
            data.byId[id]?.lifecycle === "archived" ||
            data.byId[id]?.lifecycle === "stashed",
        ),
        reason: "Only archived or set-aside movements can be restored.",
      },
      {
        label: "Remove…",
        icon: "trash",
        onSelect: () => page.openAction("remove", [it.key]),
        disabled: n > 1,
        reason: "Remove one movement at a time, after its dry run.",
      },
      { sep: true },
      {
        label: "Copy rows as TSV" + sfx,
        icon: "sheet",
        onSelect: () => page.copyRows(ids),
      },
    ];
  }

  const nextIssue = (dir = 1) => {
    const start = active ? (itemIndex.get(active.key) ?? -1) : -1;
    for (let k = 1; k <= rowItems.length; k++) {
      const it =
        rowItems[
          (((start + dir * k) % rowItems.length) + rowItems.length) %
            rowItems.length
        ]!;
      if (
        it.row &&
        checkIssues(it.row, state.check).filter(
          (x) => x !== "missing_business_classification",
        ).length
      ) {
        const iss = checkIssues(it.row, state.check).find(
          (x) => x !== "missing_business_classification",
        );
        const fixField = iss ? REASON_FIX[iss]?.field : undefined;
        const col =
          fixField && visibleKeys.includes(fixField) ? fixField : "description";
        dispatch({ type: "SELECT", mode: "set", ids: [it.key] });
        gridApi.current?.jumpTo(it.key, col);
        announce(`${it.row.description}: ${REASONS[iss ?? ""]}`);
        return;
      }
    }
    toast("No readiness issues in this view");
  };
  const onKeyDown = (
    e: KeyboardEvent<HTMLDivElement>,
    { item }: { item: Item | undefined },
  ) => {
    setNote(null);
    if (!item) return false;
    if (item.kind === "group") {
      if (
        e.key === "Enter" ||
        e.key === " " ||
        e.key === "ArrowRight" ||
        e.key === "ArrowLeft"
      ) {
        e.preventDefault();
        const open =
          e.key === "ArrowRight"
            ? false
            : e.key === "ArrowLeft"
              ? true
              : !item.collapsed;
        dispatch({
          type: "VIEW",
          patch: { collapsed: { ...view.collapsed, [item.key]: open } },
        });
        return true;
      }
      return false;
    }
    const col = active?.col ?? "";
    if (
      chord(e, "Enter") ||
      chord(e, "Enter", { shift: true }) ||
      chord(e, "F2")
    ) {
      e.preventDefault();
      startEdit(item.key, col);
      return true;
    }
    if (chord(e, " ")) {
      e.preventDefault();
      dispatch({ type: "SELECT", mode: "toggle", ids: [item.key] });
      return true;
    }
    if (chord(e, "Escape")) {
      if (range) {
        setAnchor(null);
        return true;
      }
      if (selectedIds.length > 1) {
        dispatch({ type: "SELECT", mode: "set", ids: [item.key] });
        return true;
      }
      return false;
    }
    if (chord(e, "Delete") || chord(e, "Backspace")) {
      e.preventDefault();
      clearCells();
      return true;
    }
    if (chord(e, "a", { ctrl: true })) {
      e.preventDefault();
      dispatch({ type: "SELECT", mode: "set", ids: visibleIds });
      toast(
        win.truncated
          ? `Selected the ${visibleIds.length} loaded · Load all ${win.totalCount}`
          : `Selected ${plural(visibleIds.length, "visible movement")}`,
      );
      return true;
    }
    if (chord(e, "d", { ctrl: true })) {
      e.preventDefault();
      fillDown();
      return true;
    }
    if (chord(e, "z", { ctrl: true, alt: true })) {
      e.preventDefault();
      if (col in (staged.rows[item.key] ?? {})) {
        dispatch({ type: "REVERT_CELL", id: item.key, field: col });
        toast("Cell reverted to its stored value");
      }
      return true;
    }
    if (chord(e, "ContextMenu") || chord(e, "F10", { shift: true })) {
      e.preventDefault();
      const r = document
        .getElementById(gridCellId(item.key, col))
        ?.getBoundingClientRect();
      openRowMenu(
        r ? { x: r.left + 8, y: r.bottom } : { x: 200, y: 200 },
        item,
      );
      return true;
    }
    if (chord(e, "F8")) {
      e.preventDefault();
      nextIssue(1);
      return true;
    }
    if (chord(e, "F8", { shift: true })) {
      e.preventDefault();
      nextIssue(-1);
      return true;
    }
    if (
      !(e.ctrlKey || e.metaKey) &&
      !e.altKey &&
      e.key.length === 1 &&
      /\S/.test(e.key)
    ) {
      e.preventDefault();
      startEdit(item.key, col, e.key);
      return true;
    }
    return false;
  };

  const rangeSet = useMemo(() => {
    if (!range) return null;
    const s = new Set<string>();
    for (let i = range.r0; i <= range.r1; i++)
      for (let j = range.c0; j <= range.c1; j++)
        s.add(rowItems[i]?.key + "|" + visibleKeys[j]);
    return s;
  }, [range, rowItems, visibleKeys]);
  const missingField = view.missingMark
    ? REASON_FIX[view.missingMark]?.field
    : null;
  const cellInfo = (it: RowItem, k: string): CellInfo => {
    if (it.draft) return {};
    const st = staged.rows[it.key];
    const ref = state.refusals[it.key]?.[k];
    const changed = st && k in st && !sameValue(getField(it.row!, k), st[k]);
    const eff = effOf(it);
    const lock = F[k] ? lockOf(it, k) : null;
    return {
      st,
      ref,
      changed: changed || (k === "cls" && st && "share" in st),
      eff,
      lock,
    };
  };
  const cellAttrs = (it: Item, c: GridColumn): CellAttrs => {
    const k = c.key;
    const a: CellAttrs = {};
    if (rangeSet && rangeSet.has(it.key + "|" + k)) a["data-inrange"] = "true";
    if (it.kind !== "row") return a;
    if (it.draft) {
      if (DRAFT_REQUIRED.includes(k)) a["aria-required"] = "true";
      return a;
    }
    const { ref, changed, eff, lock } = cellInfo(it, k);
    if (ref) {
      a.className = "refused";
      a["aria-invalid"] = "true";
      a["data-tip"] = `Refused “${ref.raw}”: ${ref.msg}`;
      return a;
    }
    if (changed) {
      a.className = "changed";
      a["data-tip"] =
        `Was: ${show(k, getField(it.row!, k), it.row) || "empty"}\nNot saved yet: ${show(k, getField(eff!, k), eff) || "empty"}${isIdentity(k, it.row) ? "\nSaved under a new reference" : ""}`;
    } else if (["description", "counterparty", "notes"].includes(k)) {
      const v = getField(eff!, k);
      if (v) {
        a["data-tip"] = v;
        a["data-tip-trunc"] = "";
      }
    }
    if (
      missingField &&
      k === missingField &&
      checkIssues(it.row!, state.check).includes(view.missingMark ?? "")
    )
      a.className = cx(a.className, "missing");
    if (lock) a["aria-readonly"] = "true";
    return a;
  };
  const describeCell = (it: Item, c: GridColumn) => {
    if (it.kind !== "row" || it.draft) return null;
    const { ref, changed, lock } = cellInfo(it, c.key);
    if (ref) return `Refused: ${ref.msg}`;
    if (changed)
      return `changed, was ${show(c.key, getField(it.row!, c.key), it.row) || "empty"}`;
    if (lock && F[c.key]) return `Read-only: ${lock}`;
    return null;
  };
  const describeRow = (it: Item) => {
    if (it.kind !== "row") return "";
    if (it.draft) return "New movement, not saved";
    const r = it.row!;
    const S = statusOf(r, state.check);
    const iss = checkIssues(r, state.check).filter(
      (x) => x !== "missing_business_classification",
    );
    const eff = effOf(it);
    const f = diffOf(r, staged.rows[r.id]);
    return [
      S.label,
      iss.length ? "Readiness: " + iss.map((x) => REASONS[x]).join(", ") : "",
      r.lifecycle !== "active" ? LIFECYCLE[r.lifecycle].label : "",
      r.sealed?.length
        ? "Sealed by " +
          r.sealed
            .map(
              (u) => `Modelo ${u.modelo} ${u.period}, ${SEAL_LABEL[u.state]}`,
            )
            .join("; ")
        : "",
      r.issue === "duplicate" ? "Possible duplicate" : "",
      r.suggestion ? "Model suggestion waiting" : "",
      stagedIds.has(r.id)
        ? "Not saved: " + (stagedSummary(eff, f) || "staged action")
        : "",
      state.outcomes[r.id]
        ? state.outcomes[r.id]!.status +
          ": " +
          (state.outcomes[r.id]!.msg || "")
        : "",
    ]
      .filter(Boolean)
      .join(" · ");
  };
  const announceCell = (it: Item, col: string | undefined) => {
    if (!it || it.kind !== "row" || !col) return;
    const r = effOf(it);
    const ci = cellInfo(it, col);
    const val =
      col === "status"
        ? describeRow(it)
        : col === "select"
          ? state.selection[it.key]
            ? "selected"
            : "not selected"
          : show(col, getField(r, col), r) || "empty";
    announce(
      `Row ${(itemIndex.get(it.key) ?? 0) + 1} of ${rowItems.length}, ${COL_LABEL[col]}, ${val}${ci.changed ? ", changed, was " + (show(col, getField(it.row!, col), it.row) || "empty") : ""}${ci.ref ? ", refused" : ""}`,
    );
  };
  const rowAttrs = (it: Item): CellAttrs => {
    if (it.kind !== "row") return {};
    return {
      "aria-selected": !!state.selection[it.key],
      className: cx(
        it.draft && "draft",
        it.row && it.row.lifecycle !== "active" && "inert",
        it.row && stagedIds.has(it.row.id) && "staged",
      ),
    };
  };
  const renderCell = (it: Item, c: GridColumn) => {
    if (it.kind !== "row") return null;
    const isEditing =
      editing && editing.key === it.key && editing.col === c.key;
    if (c.key === "select")
      return (
        <>
          <input
            type="checkbox"
            className="checkbox"
            tabIndex={-1}
            aria-label={"Select " + (it.draft ? "draft" : it.row?.description)}
            checked={!!state.selection[it.key]}
            readOnly
          />
          {!it.draft && stagedIds.has(it.key) ? (
            <span className="unsaved-bar" aria-hidden="true"></span>
          ) : null}
        </>
      );
    const r = effOf(it);
    const content = cellContent(c, r, {
      draft: it.draft,
      stored: it.row,
      check: state.check,
      outcome: state.outcomes[it.key],
      invoiceOf,
      match: it.draft ? null : recon.best[it.key],
      rowActions: staged.actions.filter((a) => a.rowIds.includes(it.key)),
      clsStaged:
        (!it.draft &&
          staged.rows[it.key] &&
          ("cls" in staged.rows[it.key]! || "share" in staged.rows[it.key]!)) ||
        staged.actions.some(
          (a) => a.type === "approve" && a.rowIds[0] === it.key,
        ),
      nested: it.nested,
    });
    const ci = cellInfo(it, c.key);
    const body = ci.ref ? (
      <span className="row g1 v">
        <Icon name="alert" size="xs" className="danger-t" />
        <span className="truncate">{ci.ref.raw}</span>
      </span>
    ) : ci.changed && isIdentity(c.key, it.row) ? (
      <>
        {content}
        <span className="note-ico row" aria-hidden="true">
          <Icon name="idCard" size="xs" />
        </span>
      </>
    ) : (
      content
    );
    if (!isEditing) return body;
    const def = F[c.key]!;
    if (def.editor === "combo")
      return (
        <>
          {body}
          <ComboEditor
            field={c.key}
            cellKey={it.key}
            row={r}
            isDraft={!!it.draft}
            initialFilter={editing.initial}
            ratios={data.ratios}
            onCommit={commitEdit}
            onCancel={cancelEdit}
          />
        </>
      );
    return (
      <TextEditor
        field={c.key}
        cellKey={it.key}
        row={r}
        isDraft={!!it.draft}
        initial={editing.initial}
        onCommit={commitEdit}
        onCancel={cancelEdit}
        onRefuse={refuseEdit}
      />
    );
  };
  const renderFull = (it: Item, { active: act }: { active: boolean }) => {
    if (it.kind !== "group") return null;
    return (
      <div
        className="g-group"
        data-active={act ? "true" : undefined}
        onClick={(e) => {
          if ((e.target as Element).closest("button")) return;
          dispatch({
            type: "VIEW",
            patch: {
              collapsed: { ...view.collapsed, [it.key]: !it.collapsed },
            },
          });
        }}
      >
        <div className="g-group-inner">
          <Icon name={it.collapsed ? "forward" : "chevronDown"} size="xs" />
          <span className="glabel">{it.label}</span>
          <span className="tag tnum">{it.rows.length}</span>
          <SumLine sums={sumsOf(it.rows)} />
          <span className="group-actions row g1">
            {(() => {
              const allTransfer = it.rows.every(
                (r) => r.direction === "transfer",
              );
              const why = allTransfer
                ? "Transfers can only be Personal or stay unclassified"
                : undefined;
              return (
                <>
                  <button
                    type="button"
                    className="btn ghost xs"
                    tabIndex={-1}
                    aria-disabled={allTransfer ? "true" : undefined}
                    data-tip={why}
                    onClick={() =>
                      !allTransfer &&
                      page.classifySelection(
                        "business",
                        it.rows.map((r) => r.id),
                        { group: true },
                      )
                    }
                  >
                    Business…
                  </button>
                  <button
                    type="button"
                    className="btn ghost xs"
                    tabIndex={-1}
                    onClick={() =>
                      page.classifySelection(
                        "personal",
                        it.rows.map((r) => r.id),
                        { group: true },
                      )
                    }
                  >
                    Personal
                  </button>
                  <button
                    type="button"
                    className="btn ghost xs"
                    tabIndex={-1}
                    aria-disabled={allTransfer ? "true" : undefined}
                    data-tip={why}
                    onClick={() =>
                      !allTransfer &&
                      page.classifySelection(
                        "mixed",
                        it.rows.map((r) => r.id),
                        { group: true },
                      )
                    }
                  >
                    Mixed…
                  </button>
                </>
              );
            })()}
            <button
              type="button"
              className="btn ghost xs"
              tabIndex={-1}
              onClick={(e) =>
                setGroupPop({
                  anchor: e.currentTarget,
                  rows: it.rows,
                  mode: "category",
                })
              }
            >
              Category <Icon name="chevronDown" size="xs" />
            </button>
            <button
              type="button"
              className="btn ghost xs"
              tabIndex={-1}
              onClick={() =>
                page.openDialog("rule", { rows: it.rows, from: it.grouping })
              }
            >
              Make a rule
            </button>
            <button
              type="button"
              className="btn ghost xs"
              tabIndex={-1}
              onClick={() =>
                dispatch({
                  type: "SELECT",
                  mode: "set",
                  ids: it.rows.map((r) => r.id),
                })
              }
            >
              Select {it.rows.length}
            </button>
          </span>
        </div>
      </div>
    );
  };

  const firstRun = !Object.keys(data.byId).length && !staged.drafts.length;
  const empty = !firstRun && win.inPeriod.length === 0 && !staged.drafts.length;
  const hiddenByFilters = win.windowRows.length - win.filtered.length;
  const listMode = view.savedView === "match" && !narrow;
  if (firstRun) return <FirstRun />;
  if (narrow)
    return (
      <div className="col" style={{ minHeight: 0, flex: 1 }}>
        <ReadinessStrip win={win} />
        <MovementBanners win={win} hiddenSelected={hiddenSelected} />
        <MovementToolbar win={win} />
        {empty ? (
          <EmptyPeriod onAdd={startAdd} />
        ) : (
          <PhoneCards
            rows={[
              ...staged.drafts.map((d) => ({ draft: d })),
              ...win.filtered.map((r) => ({ row: r })),
            ]}
            onOpen={(id: string) => {
              dispatch({ type: "SELECT", mode: "set", ids: [id] });
              setActive({ key: id, col: "cls" });
              setSheet(true);
            }}
          />
        )}
        {sheet ? (
          <>
            <div className="scrim" onClick={() => setSheet(false)}></div>
            <Inspector
              active={active && itemIndex.has(active.key) ? active : null}
              onClose={() => setSheet(false)}
            />
          </>
        ) : null}
      </div>
    );
  return (
    <div className="ledger-movements col" style={{ minHeight: 0, flex: 1 }}>
      <ReadinessStrip win={win} />
      <MovementBanners win={win} hiddenSelected={hiddenSelected} />
      <MovementToolbar win={win} />
      {selectedIds.length > 1 &&
      allVisibleSelected &&
      hiddenByFilters > 0 &&
      !hiddenSelected.length ? (
        <div className="selbanner" role="status">
          All {visibleIds.length} visible movements are selected.
          <Button
            variant="link"
            size="xs"
            onClick={() =>
              dispatch({
                type: "SELECT",
                mode: "set",
                ids: win.windowRows.map((r) => r.id),
              })
            }
          >
            Select all {win.windowRows.length} in {periodShort(view.period)}
          </Button>
          <Button
            variant="link"
            size="xs"
            onClick={() => dispatch({ type: "SELECT", mode: "clear", ids: [] })}
          >
            Clear selection
          </Button>
        </div>
      ) : null}
      <div className="workarea">
        <div className="gridwrap">
          {empty ? (
            <EmptyPeriod onAdd={startAdd} />
          ) : (
            <DataGrid
              className={view.density}
              range={
                range && rowItems[range.r0] && rowItems[range.r1]
                  ? {
                      from: rowItems[range.r0]!.key,
                      to: rowItems[range.r1]!.key,
                      c0: visibleKeys[range.c0]!,
                      c1: visibleKeys[range.c1]!,
                    }
                  : null
              }
              items={items}
              columns={columns}
              rowHeight={rowH}
              label={`Movements, ${periodLabel(view.period)}`}
              renderCell={renderCell}
              renderFull={renderFull}
              cellAttrs={cellAttrs}
              rowAttrs={rowAttrs}
              describeRow={describeRow}
              describeCell={describeCell}
              announce={announceCell}
              active={active}
              onActive={onActive}
              onKeyDown={onKeyDown}
              onCellPointerDown={onCellPointerDown}
              onCellDoubleClick={(_e, it, c) =>
                it.kind === "row" &&
                c.key !== "select" &&
                startEdit(it.key, c.key)
              }
              onHeaderClick={(c) =>
                dispatch({
                  type: "VIEW",
                  patch: {
                    sort: {
                      key: c.key,
                      dir:
                        view.sort.key === c.key && view.sort.dir === "asc"
                          ? "desc"
                          : "asc",
                    },
                  },
                })
              }
              onResize={(k, w) =>
                dispatch({
                  type: "VIEW",
                  patch: { widths: { ...view.widths, [k]: w } },
                })
              }
              onReorder={(from, to, after) => {
                const o = view.order.filter((x) => x !== from);
                o.splice(o.indexOf(to) + (after ? 1 : 0), 0, from);
                dispatch({ type: "VIEW", patch: { order: o } });
                announce(
                  `${COL_LABEL[from]} moved ${after ? "after" : "before"} ${COL_LABEL[to]}`,
                );
              }}
              onCopy={onCopy}
              onPaste={onPaste}
              onContextMenu={(e, it) => {
                e.preventDefault();
                openRowMenu({ x: e.clientX, y: e.clientY }, it);
              }}
              apiRef={gridApi}
              editing={!!editing}
              emptyNode={
                <Empty
                  icon="search"
                  title="No movements match"
                  desc={`${win.windowRows.length} movements in ${periodShort(view.period)} are hidden by the search or filters.`}
                >
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() =>
                      dispatch({
                        type: "VIEW",
                        patch: {
                          filters: { ...EMPTY_FILTERS },
                          search: "",
                          savedView: "all",
                        },
                      })
                    }
                  >
                    Clear filters
                  </Button>
                </Empty>
              }
            />
          )}
          {view.period.code === "ALL" && view.loaded < win.totalCount ? (
            <div className="window-note" role="status">
              <Icon name="info" size="xs" />
              {win.totalCount > 250 && view.loaded < win.totalCount
                ? `Read ${Math.min(view.loaded, win.totalCount)} of ${win.totalCount}, 250 at a time. Grouping and totals wait for the whole window.`
                : ""}
              <Button
                size="xs"
                variant="outline"
                onClick={() =>
                  dispatch({ type: "VIEW", patch: { loaded: win.totalCount } })
                }
              >
                Load all {win.totalCount}
              </Button>
            </div>
          ) : null}
        </div>
        {listMode ? (
          <div className="rpanel">
            <div className="rpanel-mode">
              <Seg
                size="sm"
                label="Right-hand panel"
                value={panelMode}
                onChange={setPanelMode}
                options={[
                  { value: "match", label: "To match" },
                  { value: "movement", label: "Movement" },
                ]}
              />
            </div>
            {panelMode === "match" ? (
              <MatchList
                recon={recon}
                onPick={(id) => {
                  setPanelMode("movement");
                  page.jumpTo(id, "match");
                  page.openInspectorAt("invoice");
                }}
              />
            ) : (
              <Inspector
                embedded
                active={active && itemIndex.has(active.key) ? active : null}
              />
            )}
          </div>
        ) : view.inspector && !empty ? (
          <Inspector
            active={active && itemIndex.has(active.key) ? active : null}
          />
        ) : null}
      </div>
      {note ? (
        <FloatingNote anchorId={gridCellId(note.key, note.col)} tone="note">
          <span
            className="row g15"
            style={{ alignItems: "flex-start", color: "var(--foreground)" }}
          >
            <Icon name="lock" size="xs" />
            <span>{note.text}</span>
          </span>
        </FloatingNote>
      ) : null}
      {menu ? (
        <Menu
          anchor={menu.point}
          items={menu.items}
          onClose={() => setMenu(null)}
          label="Movement actions"
        />
      ) : null}
      {groupPop ? (
        <GroupClassify {...groupPop} onClose={() => setGroupPop(null)} />
      ) : null}
    </div>
  );
}
export function EmptyPeriod({ onAdd }: { onAdd: () => void }) {
  const [state] = useStore();
  const page = usePage();
  return (
    <Empty
      icon="ledger"
      title={`No movements in ${periodShort(state.view.period)}`}
      desc="Not the same as nothing owed."
    >
      <div className="row g2">
        <Button
          variant="outline"
          size="sm"
          icon="upload"
          onClick={() => page.openDialog("import")}
        >
          Import
        </Button>
        <Button size="sm" icon="plus" onClick={onAdd}>
          Add movement
        </Button>
      </div>
    </Empty>
  );
}
/* First run (R20): what to do, in order. */
export function FirstRun() {
  const [state] = useStore();
  const page = usePage();
  const hasAccounts = state.data.accounts.length > 0;
  return (
    <div
      className="section-body"
      style={{
        maxWidth: "calc(var(--spacing) * 160)",
        margin: "0 auto",
        width: "100%",
      }}
    >
      <div className="col g1">
        <h3 className="t-md fw6">Start your ledger</h3>
        <p className="muted">
          Three steps bring your year in. Nothing is sent anywhere.
        </p>
      </div>
      <ol className="checklist">
        <li>
          <span className="stepn">
            {hasAccounts ? <Icon name="tick" size="xs" /> : "1"}
          </span>
          <div className="f1 col">
            <b className="fw5">Register your bank accounts</b>
            <span className="muted t-sm">
              So each statement lands on the right account.
              {hasAccounts
                ? ` ${plural(state.data.accounts.length, "account")} registered.`
                : ""}
            </span>
          </div>
          <Button
            size="sm"
            variant="outline"
            onClick={() => page.setSection("registers")}
          >
            Accounts
          </Button>
        </li>
        <li>
          <span className="stepn">2</span>
          <div className="f1 col">
            <b className="fw5">Import a statement</b>
            <span className="muted t-sm">
              CSV, XLSX, OFX or an N26 PDF. You see a preview before anything is
              written.
            </span>
          </div>
          <Button size="sm" onClick={() => page.openDialog("import")}>
            Import
          </Button>
        </li>
        <li>
          <span className="stepn">3</span>
          <div className="f1 col">
            <b className="fw5">Review what the rules caught</b>
            <span className="muted t-sm">
              Rules classify the obvious ones; you look at the rest in “Needs
              review”.
            </span>
          </div>
          <Button
            size="sm"
            variant="ghost"
            onClick={() => page.setSection("rules")}
          >
            Rules
          </Button>
        </li>
      </ol>
    </div>
  );
}
/* Phone width (R19): one card per movement; the chip opens a sheet. */
export function PhoneCards({
  rows,
  onOpen,
}: {
  rows: { row?: Movement; draft?: Draft }[];
  onOpen: (id: string) => void;
}) {
  const [state] = useStore();
  return (
    <ul className="cards" aria-label="Movements">
      {rows.slice(0, 120).map(({ row, draft }) => {
        if (draft)
          return (
            <li key={draft.key} className="card-row">
              <span className="tag">New</span>
              <span className="f1 truncate">
                {draft.fields.description || "New movement"}
              </span>
            </li>
          );
        if (!row) return null;
        const r = row;
        const S = statusOf(r, state.check);
        const eff = effective(r, state.staged.rows, state.staged.actions);
        const staged = stagedRowIds(state).has(r.id);
        return (
          <li key={r.id} className={cx("card-row", staged && "staged")}>
            <button
              type="button"
              className="card-main"
              onClick={() => onOpen(r.id)}
            >
              <span className="sr-only">{S.label}: </span>
              <span className="col f1" style={{ minWidth: 0 }}>
                <span className="truncate fw5">{r.description}</span>
                <span className="muted t-xs">
                  {fmtDate(effDate(r))} · {r.counterparty || "No counterparty"}
                </span>
              </span>
              <span className="col" style={{ alignItems: "flex-end" }}>
                <span className="tnum fw6">
                  {fmtMoney(r.amount)}
                  {r.currency !== "EUR" ? " " + r.currency : ""}
                </span>
                <DirCell v={r.direction} />
              </span>
            </button>
            <button
              type="button"
              className="btn pill"
              onClick={() => onOpen(r.id)}
            >
              <ClsCell r={eff} pending={staged} />
            </button>
          </li>
        );
      })}
    </ul>
  );
}
/* The To match view's side list: one best pair per movement (R10, R6). */
export function MatchList({
  recon,
  onPick,
}: {
  recon: Recon;
  onPick: (id: string) => void;
}) {
  return (
    <div className="matchlist" role="region" aria-label="To match">
      <div className="insp-head">
        <div className="f1 col">
          <div className="insp-title">To match</div>
          <div className="insp-sub">
            {plural(recon.list.length, "suggested pair")} · one best invoice per
            movement
          </div>
        </div>
      </div>
      <ul
        className="list-rows"
        style={{ padding: "0 calc(var(--spacing) * 3)", overflowY: "auto" }}
      >
        {recon.list.map((s) => (
          <li key={s.rowId} className="col" style={{ alignItems: "stretch" }}>
            <button
              type="button"
              className="btn ghost block matchpick"
              onClick={() => onPick(s.rowId)}
            >
              <span className="row g2" style={{ width: "100%" }}>
                <span className="fw5 truncate f1">{s.row.description}</span>
                <span className="tnum">{fmtMoney(s.row.amount)}</span>
              </span>
              <span className="t-xs">
                {s.inv.number} · {s.inv.counterparty} · issued{" "}
                {fmtDateLong(s.inv.date)} · {PAYMENT[s.inv.payment]}
              </span>
              <span className="row g1 wrap">
                {s.ambiguous ? (
                  <span className="badge warning">Ambiguous</span>
                ) : null}
                {s.chips.slice(0, 2).map((c) => (
                  <span key={c} className="tag">
                    {c}
                  </span>
                ))}
              </span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
/* ── Readiness strip (R1, R9): frozen at the last check. ─────────────── */
export function ReadinessStrip({ win }: { win: MovementWindow }) {
  const [state, dispatch] = useStore();
  const page = usePage();
  const { view, check } = state;
  const [more, setMore] = useState(false);
  const [checking, setChecking] = useState(false);
  const rows = win.inPeriod;
  const activeRows = rows.filter((r) => r.lifecycle === "active");
  const toClassify = activeRows.filter(
    (r) => statusOf(r, check).key === "toClassify",
  );
  const toFix = activeRows.filter((r) => statusOf(r, check).key === "needsFix");
  const reasons: Record<string, number> = {};
  activeRows.forEach((r) =>
    checkIssues(r, check).forEach((x) => {
      if (x !== "missing_business_classification")
        reasons[x] = (reasons[x] || 0) + 1;
    }),
  );
  const noRate = activeRows.filter((r) => r.currency !== "EUR" && !r.fx);
  const staged = stagedRowIds(state);
  // Staged progress counts only movements to classify whose staged change sets a classification or approves one (M8).
  const stagedClassify = toClassify.filter(
    (r) =>
      (state.staged.rows[r.id] && "cls" in state.staged.rows[r.id]!) ||
      state.staged.actions.some(
        (a) => a.type === "approve" && a.rowIds[0] === r.id,
      ),
  ).length;
  const stale = state.proto.state === "stale";
  const unmeasured = state.proto.state === "unmeasured";
  const outOfDate = check.changedSince > 0;
  const f = view.filters;
  const unsaved = staged.size
    ? ` · ${plural(staged.size, "unsaved change")} not included`
    : "";
  const when = stale ? "checked 3 days ago" : "checked " + fmtTime(check.at);
  /* A pill or chip replaces the selection with its first movement and
     opens it on Classification (V-16). */
  const go = (
    patch: Partial<Filters>,
    reason: string | null,
    pick?: Movement[],
  ) => {
    const fix = reason ? REASON_FIX[reason] : undefined;
    const on = !Object.keys(patch).length;
    dispatch({
      type: "VIEW",
      patch: {
        filters: { ...EMPTY_FILTERS, ...patch },
        savedView: "custom",
        missingMark: reason || null,
        ...(fix?.preset && PRESETS[fix.preset]
          ? { preset: fix.preset, visible: PRESETS[fix.preset]!.cols }
          : {}),
      },
    });
    if (on || !pick || !pick.length) return;
    const first = [...pick].sort((a, b) =>
      compareRows(a, b, view.sort.key, view.sort.dir),
    )[0];
    if (!first) return;
    dispatch({ type: "SELECT", mode: "set", ids: [first.id] });
    setTimeout(() => {
      page.jumpTo(first.id, (fix && fix.field) || "cls");
      page.openInspectorAt("classification");
    }, 60);
  };
  const doCheck = async () => {
    setChecking(true);
    await sleep(900);
    setChecking(false);
    dispatch({ type: "CHECK" });
    if (stale || unmeasured)
      dispatch({ type: "PROTO", patch: { state: "normal" } });
    page.toast("Readiness checked for " + periodShort(view.period));
  };
  const chips = Object.entries(reasons).sort((a, b) => b[1] - a[1]);
  const shown = more ? chips : chips.slice(0, 4);
  const pill = (p: Pill) => (
    <button
      key={`${p.tone}-${p.icon}`}
      type="button"
      className={cx("btn pill state", p.tone)}
      aria-label={p.label}
      data-tip={p.label}
      aria-pressed={p.pressed}
      onClick={p.onClick}
      style={
        p.fill != null
          ? ({ "--fill": p.fill * 100 + "%" } as CSSProperties)
          : undefined
      }
    >
      <Icon name={p.icon} size="xs" />
      {p.n != null ? (
        <span className="tnum" aria-hidden="true">
          {p.n}
        </span>
      ) : null}
    </button>
  );
  const isF = (k: string) => f.status.length === 1 && f.status[0] === k;
  const pills = [];
  if (!rows.length)
    pills.push(
      <span
        key="none"
        className="stat muted"
        role="img"
        aria-label={`Nothing to check in ${periodShort(view.period)}`}
        data-tip={`Nothing to check in ${periodShort(view.period)}`}
      >
        <Icon name="info" size="xs" />
      </span>,
    );
  else {
    if (unmeasured)
      pills.push(
        pill({
          tone: "muted",
          icon: "unknown",
          label: "Readiness not checked yet · check now",
          onClick: doCheck,
        }),
      );
    else if (outOfDate || stale)
      pills.push(
        pill({
          tone: "muted",
          icon: "unknown",
          label: `Not checked since ${outOfDate ? plural(check.changedSince, "saved change") : "it was read"} · last ${when} · check now`,
          onClick: doCheck,
        }),
      );
    if (!unmeasured) {
      if (toFix.length)
        pills.push(
          pill({
            tone: "warn",
            icon: "alert",
            n: toFix.length,
            label: `Not ready for calculation · ${plural(toFix.length, "movement")} to fix · ${when}${unsaved}`,
            pressed: isF("needsFix"),
            onClick: () =>
              go(isF("needsFix") ? {} : { status: ["needsFix"] }, null, toFix),
          }),
        );
      if (toClassify.length)
        pills.push(
          pill({
            tone: "plain",
            icon: "pending",
            n: toClassify.length,
            fill: stagedClassify / toClassify.length,
            label: `${toClassify.length} to classify${stagedClassify ? ` · ${stagedClassify} staged` : ""}${unsaved}`,
            pressed: isF("toClassify"),
            onClick: () =>
              go(
                isF("toClassify") ? {} : { status: ["toClassify"] },
                null,
                toClassify,
              ),
          }),
        );
      if (noRate.length)
        pills.push(
          pill({
            tone: "plain",
            icon: "noRate",
            n: noRate.length,
            label: `${plural(noRate.length, "movement")} without an EUR rate`,
            pressed: f.noRate,
            onClick: () => go(f.noRate ? {} : { noRate: true }, null, noRate),
          }),
        );
      if (
        !toFix.length &&
        !toClassify.length &&
        !noRate.length &&
        !outOfDate &&
        !stale
      )
        pills.push(
          pill({
            tone: "ok",
            icon: "check",
            label: `Ready for calculation · ${when}${unsaved}`,
            onClick: doCheck,
          }),
        );
    }
  }
  return (
    <div className="strip" role="region" aria-label="Readiness for the period">
      {pills}
      {unmeasured
        ? null
        : shown.map(([k, n]) => (
            <button
              key={k}
              type="button"
              className="btn pill"
              aria-pressed={f.reason === k}
              aria-label={`${REASONS[k]}: ${n}. Show them and how to fix them`}
              onClick={() =>
                go(
                  f.reason === k ? {} : { reason: k },
                  f.reason === k ? null : k,
                  activeRows.filter((r) => checkIssues(r, check).includes(k)),
                )
              }
              data-tip={`${REASONS[k]} · ${n}`}
            >
              {REASON_SHORT[k] || REASONS[k]} <span className="tnum">{n}</span>
            </button>
          ))}
      {chips.length > 4 ? (
        <button
          type="button"
          className="btn pill"
          aria-expanded={more}
          aria-label={
            more ? "Show fewer reasons" : `${chips.length - 4} more reasons`
          }
          onClick={() => setMore(!more)}
        >
          {more ? "Fewer" : `+${chips.length - 4}`}
        </button>
      ) : null}
      <span className="f1"></span>
      <IconButton
        icon="sync"
        size="sm"
        variant={outOfDate ? "outline" : "ghost"}
        label="Check again"
        hint={when + unsaved}
        pending={checking}
        onClick={doCheck}
      />
    </div>
  );
}
export function MovementBanners({
  win,
  hiddenSelected,
}: {
  win: MovementWindow;
  hiddenSelected: string[];
}) {
  const [state, dispatch] = useStore();
  const page = usePage();
  const refused = Object.entries(state.outcomes).filter(
    ([, o]) => o.status === "refused",
  );
  const notSent = Object.entries(state.outcomes).filter(
    ([, o]) => o.status === "notSent",
  );
  const stale = state.proto.state === "stale";
  const sel = Object.keys(state.selection);
  const text = state.view.search.trim();
  const loadedFound =
    state.view.period.code === "ALL" &&
    state.view.loaded < win.totalCount &&
    text;
  // Banners say it in at most eight words, then the action (R22).
  return (
    <Fragment>
      {state.paused ? (
        <div className="banner" role="alert">
          <Alert
            tone="warning"
            icon="unknown"
            title="Outcome unknown: writes paused"
          >
            {
              <span className="sr-only">
                “{state.paused.label}” may or may not be saved.
                {notSent.length
                  ? ` ${notSent.length} later changes stay staged.`
                  : ""}
              </span>
            }
          </Alert>
          <Button
            size="sm"
            icon="sync"
            pending={page.rereading}
            onClick={page.reread}
          >
            Re-read
          </Button>
        </div>
      ) : null}
      {state.unknownNotes.map((n, i) => (
        <div key={i} className="banner">
          <Alert
            tone={n.saved ? "success" : "warning"}
            title={
              n.saved
                ? "Re-read: it was saved"
                : "Re-read: not saved, staged again"
            }
          >
            <span className="t-sm muted">{n.label}</span>
          </Alert>
          <IconButton
            icon="close"
            label="Dismiss"
            onClick={() => dispatch({ type: "DISMISS_NOTE", index: i })}
          />
        </div>
      ))}
      {refused.length && !state.paused ? (
        <div className="banner">
          <Alert
            tone="danger"
            icon="refused"
            title={`${plural(refused.length, "change")} refused, still staged`}
          />
          <Button
            size="sm"
            variant="outline"
            onClick={() => refused[0] && page.jumpTo(refused[0][0], "status")}
          >
            Show the first
          </Button>
        </div>
      ) : null}
      {hiddenSelected.length && sel.length ? (
        <div className="banner" role="alert">
          <Alert
            tone="warning"
            title={`${hiddenSelected.length} of ${sel.length} selected are hidden`}
          />
          <Button
            size="sm"
            variant="outline"
            onClick={() => page.showSelected()}
          >
            Show them
          </Button>
          <Button
            size="sm"
            variant="ghost"
            onClick={() =>
              dispatch({ type: "SELECT", mode: "remove", ids: hiddenSelected })
            }
          >
            Keep only visible
          </Button>
        </div>
      ) : null}
      {stale ? (
        <div className="banner">
          <Alert
            tone="warning"
            icon="clock"
            title="Read 3 days ago: may be stale"
          />
          <Button
            size="sm"
            icon="sync"
            pending={page.rereading}
            onClick={page.reread}
          >
            Re-read
          </Button>
        </div>
      ) : null}
      {win.elsewhere.length && text ? (
        <div className="banner slim" role="status">
          <span className="muted t-sm">
            {win.elsewhere.length} more in other periods
          </span>
          <Button
            size="xs"
            variant="link"
            onClick={() => {
              const ys = [
                ...new Set(win.elsewhere.map((r) => effDate(r).slice(0, 4))),
              ];
              dispatch({
                type: "VIEW",
                patch: {
                  period:
                    ys.length === 1
                      ? { year: +ys[0]!, code: "0A" }
                      : { year: 2026, code: "ALL" },
                },
              });
            }}
          >
            Show
          </Button>
        </div>
      ) : null}
      {loadedFound ? (
        <div className="banner slim" role="status">
          <span className="muted t-sm">
            {win.filtered.length} found in the{" "}
            {Math.min(state.view.loaded, win.totalCount)} loaded
          </span>
          <Button
            size="xs"
            variant="link"
            onClick={() =>
              dispatch({ type: "VIEW", patch: { loaded: win.totalCount } })
            }
          >
            Load all {win.totalCount}
          </Button>
        </div>
      ) : null}
    </Fragment>
  );
}
/* ── Toolbar. ────────────────────────────────────────────────────────── */
export function MovementToolbar({ win }: { win: MovementWindow }) {
  const [state, dispatch] = useStore();
  const page = usePage();
  const { view, data } = state;
  const [menu, setMenu] = useState<{
    kind: "views" | "group" | "sort";
    anchor: HTMLElement;
  } | null>(null);
  const [filterOpen, setFilterOpen] = useState<HTMLElement | null>(null);
  const f = view.filters;
  const setView = (patch: Partial<View>) => dispatch({ type: "VIEW", patch });
  const setF = (patch: Partial<Filters>) =>
    setView({ filters: { ...f, ...patch }, savedView: "custom" });
  const chips: { k: string; label: string; tip?: string; off: () => void }[] =
    [];
  const remove = (patch: Partial<Filters>) => () => setF(patch);
  f.status.forEach((s) =>
    chips.push({
      k: "s" + s,
      label: STATUS_FILTERS[s] ?? s,
      tip: "Status",
      off: remove({ status: f.status.filter((x) => x !== s) }),
    }),
  );
  f.direction.forEach((s) =>
    chips.push({
      k: "d" + s,
      label: DIRECTION[s].label,
      tip: "Direction",
      off: remove({ direction: f.direction.filter((x) => x !== s) }),
    }),
  );
  f.cls.forEach((s) =>
    chips.push({
      k: "c" + s,
      label: CLS[s].label,
      tip: "Classification",
      off: remove({ cls: f.cls.filter((x) => x !== s) }),
    }),
  );
  f.account.forEach((s) =>
    chips.push({
      k: "a" + s,
      label: ACCOUNT_LABEL[s]
        ? (ACCOUNT_LABEL[s].split(" ")[0] ?? s)
        : "No account",
      tip: "Account: " + (ACCOUNT_LABEL[s] || "none"),
      off: remove({ account: f.account.filter((x) => x !== s) }),
    }),
  );
  f.lifecycle.forEach((s) =>
    chips.push({
      k: "l" + s,
      label: LIFECYCLE[s].label,
      tip: "State",
      off: remove({ lifecycle: f.lifecycle.filter((x) => x !== s) }),
    }),
  );
  if (f.batch) {
    const b = data.batches.find((x) => x.id === f.batch);
    chips.push({
      k: "b",
      label: "One import",
      tip: "Import: " + (b ? b.file : "batch"),
      off: remove({ batch: null }),
    });
  }
  if (f.issue)
    chips.push({
      k: "i",
      label: IMPORT_ISSUES[f.issue] ?? f.issue,
      tip: "Import note",
      off: remove({ issue: null }),
    });
  if (f.group != null)
    chips.push({
      k: "g",
      label: f.group ? "Group label" : "No group",
      tip: "Group: " + (f.group || "none"),
      off: remove({ group: null }),
    });
  if (f.reason)
    chips.push({
      k: "r",
      label: REASON_SHORT[f.reason] || REASONS[f.reason] || f.reason,
      tip: "Readiness: " + REASONS[f.reason],
      off: () =>
        setView({
          filters: { ...f, reason: null },
          missingMark: null,
          savedView: "custom",
        }),
    });
  if (f.hideRejected)
    chips.push({
      k: "h",
      label: "No rejected",
      tip: "Hiding movements whose model suggestion you rejected",
      off: remove({ hideRejected: false }),
    });
  if (f.foreign)
    chips.push({
      k: "f",
      label: "Foreign currency",
      off: remove({ foreign: false }),
    });
  if (f.unsaved)
    chips.push({
      k: "u",
      label: "Unsaved",
      tip: "Has unsaved changes",
      off: remove({ unsaved: false }),
    });
  if (f.toMatch)
    chips.push({
      k: "m",
      label: "To match",
      tip: "Has a suggested invoice",
      off: remove({ toMatch: false }),
    });
  const viewLabel =
    view.savedView === "custom"
      ? "Custom view"
      : (SAVED_VIEWS[view.savedView]?.label ?? "");
  const groupAllowed = (k: string) =>
    view.period.code !== "ALL" ||
    view.loaded >= win.totalCount ||
    k === "none" ||
    !!GROUPS[k]?.server;
  const openMenu = (
    e: MouseEvent<HTMLElement>,
    kind: "views" | "group" | "sort",
  ) => setMenu({ kind, anchor: e.currentTarget });
  const menus: Record<"views" | "group" | "sort", () => MenuItem[]> = {
    views: (): MenuItem[] => [
      { heading: "Saved views" },
      ...Object.entries(SAVED_VIEWS).map(([k, v]) => ({
        label: v.label,
        checked: view.savedView === k,
        onSelect: () =>
          setView({
            savedView: k,
            filters: { ...EMPTY_FILTERS, ...v.filters },
            groupBy:
              v.groupBy ||
              (view.savedView !== k && SAVED_VIEWS[view.savedView]?.groupBy
                ? "none"
                : view.groupBy),
            collapsed: {},
            missingMark: null,
            ...(k === "match"
              ? { preset: "match", visible: PRESETS.match!.cols }
              : {}),
          }),
      })),
    ],
    group: (): MenuItem[] => [
      { heading: "Group by" },
      ...Object.entries(GROUPS).map(([k, g]) => ({
        label: g.label,
        checked: view.groupBy === k,
        disabled: !groupAllowed(k),
        reason:
          "Grouping waits for the whole window. Load all, or choose a period.",
        onSelect: () => setView({ groupBy: k, collapsed: {} }),
      })),
      ...(view.groupBy !== "none"
        ? ([
            { sep: true },
            {
              label: "Expand all groups",
              icon: "expandAll",
              onSelect: () => setView({ collapsed: {} }),
            },
            {
              label: "Collapse all groups",
              icon: "collapseAll",
              onSelect: () => {
                const c: Record<string, boolean> = {};
                const key = GROUPS[view.groupBy]?.key;
                if (key)
                  win.filtered.forEach((r) => {
                    c[
                      "g:" +
                        view.groupBy +
                        ":" +
                        key(r, { check: state.check, stagedIds: new Set() })
                    ] = true;
                  });
                setView({ collapsed: c });
              },
            },
          ] satisfies MenuItem[])
        : []),
    ],
    sort: (): MenuItem[] => [
      { heading: "Sort by" },
      ...[
        "date",
        "valueDate",
        "created",
        "classifiedAt",
        "amount",
        "description",
        "counterparty",
        "cls",
        "category",
        "ivaCategory",
        "eur",
        "modified",
        "lifecycle",
        "group",
      ].map((k) => ({
        label:
          {
            valueDate: "Value date",
            created: "Date added",
            classifiedAt: "Date classified",
          }[k] || COL_LABEL[k],
        checked: view.sort.key === k,
        note: SERVER_SORT[k] ? undefined : "this window",
        disabled:
          view.period.code === "ALL" &&
          view.loaded < win.totalCount &&
          !SERVER_SORT[k],
        reason: "Needs the whole window.",
        keepOpen: true,
        onSelect: () => setView({ sort: { key: k, dir: view.sort.dir } }),
      })),
      { sep: true },
      {
        label: "Ascending",
        checked: view.sort.dir === "asc",
        keepOpen: true,
        onSelect: () => setView({ sort: { ...view.sort, dir: "asc" } }),
      },
      {
        label: "Descending",
        checked: view.sort.dir === "desc",
        keepOpen: true,
        onSelect: () => setView({ sort: { ...view.sort, dir: "desc" } }),
      },
    ],
  };
  const sortName =
    {
      valueDate: "Value date",
      created: "Date added",
      classifiedAt: "Date classified",
    }[win.sortKey] ||
    COL_LABEL[win.sortKey] ||
    "Date";
  const datey = [
    "date",
    "valueDate",
    "created",
    "classifiedAt",
    "modified",
  ].includes(win.sortKey);
  const sortLabel = `${sortName}, ${view.sort.dir === "asc" ? (datey ? "oldest first" : "ascending") : datey ? "newest first" : "descending"}`;
  const batches = data.batches.filter((b) =>
    win.inPeriod.some((r) => r.batch === b.id),
  );
  const groups = [
    ...new Set(
      Object.values(data.byId).flatMap((r) => (r.group ? [r.group] : [])),
    ),
  ].sort();
  const toggleIn = <T,>(arr: T[], v: T) =>
    arr.includes(v) ? arr.filter((x) => x !== v) : [...arr, v];
  const pills = (
    key: "status" | "direction" | "cls" | "account" | "lifecycle",
    entries: [string, string][],
  ) => (
    <div className="chips">
      {entries.map(([v, l]) => (
        <button
          key={v}
          type="button"
          className="btn pill"
          aria-pressed={(f[key] as string[]).includes(v)}
          onClick={() => setF({ [key]: toggleIn(f[key] as string[], v) })}
        >
          {l}
        </button>
      ))}
    </div>
  );
  return (
    <div className="toolbar" role="toolbar" aria-label="Movements view">
      <div className="search" role="search">
        <Icon name="search" />
        <input
          ref={page.searchRef}
          className="input sm"
          type="search"
          maxLength={128}
          placeholder="Search movements"
          aria-label="Search movements: words, months, amounts, invoice numbers"
          aria-keyshortcuts="/"
          value={view.search}
          onChange={(e) => setView({ search: e.target.value })}
          onKeyDown={(e) => {
            if (e.key === "Escape" && view.search) {
              e.preventDefault();
              e.stopPropagation();
              setView({ search: "" });
            } else if (e.key === "ArrowDown" || e.key === "Enter") {
              e.preventDefault();
              page.gridApi.current?.focus();
            }
          }}
        />
        {!view.search ? <Kbd className="touch-hide">/</Kbd> : null}
      </div>
      <IconButton
        icon="filter"
        size="sm"
        variant={chips.length ? "outline" : "ghost"}
        label="Filters"
        hint={chips.length ? `${chips.length} active` : undefined}
        aria-expanded={!!filterOpen}
        onClick={(e) => setFilterOpen(e.currentTarget)}
      >
        {chips.length ? (
          <span className="badge count neutral-count tnum" aria-hidden="true">
            {chips.length}
          </span>
        ) : null}
      </IconButton>
      <Button
        variant="ghost"
        size="sm"
        icon="bookmark"
        iconRight="chevronDown"
        aria-expanded={menu?.kind === "views"}
        onClick={(e) => openMenu(e, "views")}
      >
        {viewLabel}
      </Button>
      <IconButton
        icon="group"
        size="sm"
        variant={view.groupBy === "none" ? "ghost" : "outline"}
        label="Group"
        hint={view.groupBy === "none" ? "none" : GROUPS[view.groupBy]?.label}
        aria-haspopup="menu"
        aria-expanded={menu?.kind === "group"}
        onClick={(e) => openMenu(e, "group")}
      />
      <IconButton
        icon={view.sort.dir === "asc" ? "sortAsc" : "sortDesc"}
        size="sm"
        label="Sort"
        hint={sortLabel}
        aria-haspopup="menu"
        aria-expanded={menu?.kind === "sort"}
        onClick={(e) => openMenu(e, "sort")}
      />
      <IconButton
        icon="columns"
        label="Columns and density"
        hint={view.preset !== "custom" ? PRESETS[view.preset]?.label : "custom"}
        onClick={() => page.openDialog("columns")}
        size="sm"
      />
      <IconButton
        icon={view.inspector ? "panelRightClose" : "panelRight"}
        label={view.inspector ? "Hide the inspector" : "Show the inspector"}
        shortcut="Alt+I"
        aria-pressed={view.inspector}
        onClick={page.toggleInspector}
        size="sm"
      />
      {chips.length ? (
        <div className="chips" style={{ flexBasis: "100%" }}>
          {chips.map((c) => (
            <FilterChip
              key={c.k}
              label={c.label}
              tip={c.tip}
              onRemove={c.off}
            />
          ))}
          <Button
            variant="link"
            size="xs"
            onClick={() =>
              setView({
                filters: { ...EMPTY_FILTERS },
                savedView: "all",
                missingMark: null,
              })
            }
          >
            Clear all
          </Button>
        </div>
      ) : null}
      <span className="ml-auto muted t-sm tnum" role="status">
        {win.truncated
          ? `${win.windowRows.length} of ${win.totalCount} loaded${win.filtered.length !== win.windowRows.length ? ` · ${win.filtered.length} shown` : ""}`
          : win.filtered.length === win.windowRows.length
            ? plural(win.filtered.length, "movement")
            : `${win.filtered.length} of ${win.windowRows.length} movements`}
        {Object.keys(state.selection).length
          ? ` · ${Object.keys(state.selection).length} selected`
          : ""}
      </span>
      {menu ? (
        <Menu
          anchor={menu.anchor}
          items={menus[menu.kind]()}
          onClose={() => setMenu(null)}
          label={
            { views: "Saved views", group: "Group by", sort: "Sort by" }[
              menu.kind
            ]
          }
        />
      ) : null}
      {filterOpen ? (
        <Popover
          anchor={filterOpen}
          onClose={() => setFilterOpen(null)}
          label="Filters"
          width="26rem"
          className="col g3"
        >
          <div className="row">
            <b className="fw6">Filters</b>
            <span className="f1"></span>
            <Button
              variant="ghost"
              size="xs"
              icon="reset"
              onClick={() =>
                setView({
                  filters: { ...EMPTY_FILTERS },
                  savedView: "all",
                  missingMark: null,
                })
              }
            >
              Reset
            </Button>
          </div>
          <div className="sec">
            <div className="sec-title">Status</div>
            {pills("status", Object.entries(STATUS_FILTERS))}
          </div>
          <div className="sec">
            <div className="sec-title">Direction</div>
            {pills(
              "direction",
              Object.entries(DIRECTION).map(([k, v]) => [k, v.label]),
            )}
          </div>
          <div className="sec">
            <div className="sec-title">Classification</div>
            {pills(
              "cls",
              Object.entries(CLS).map(([k, v]) => [k, v.label]),
            )}
          </div>
          <div className="sec">
            <div className="sec-title">Account</div>
            {pills("account", [
              ...data.accounts.map((a): [string, string] => [a.id, a.label]),
              ["", "No account"],
            ])}
          </div>
          <div className="sec">
            <div className="sec-title">State</div>
            {pills(
              "lifecycle",
              Object.entries(LIFECYCLE).map(([k, v]) => [k, v.label]),
            )}
          </div>
          <div className="split2" style={{ gap: "calc(var(--spacing) * 3)" }}>
            <Field label="Import">
              <Select
                size="sm"
                value={f.batch || ""}
                onChange={(e) => setF({ batch: e.target.value || null })}
              >
                <option value="">Any</option>
                {batches.map((b) => (
                  <option key={b.id} value={b.id}>
                    {b.file}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label="Import note">
              <Select
                size="sm"
                value={f.issue || ""}
                onChange={(e) => setF({ issue: e.target.value || null })}
              >
                <option value="">Any</option>
                {Object.entries(IMPORT_ISSUES).map(([k, l]) => (
                  <option key={k} value={k}>
                    {l}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label="Group label">
              <Select
                size="sm"
                value={f.group == null ? "__any" : f.group}
                onChange={(e) =>
                  setF({
                    group: e.target.value === "__any" ? null : e.target.value,
                  })
                }
              >
                <option value="__any">Any</option>
                <option value="">No group label</option>
                {groups.map((g) => (
                  <option key={g} value={g}>
                    {g}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label="Readiness reason">
              <Select
                size="sm"
                value={f.reason || ""}
                onChange={(e) => setF({ reason: e.target.value || null })}
              >
                <option value="">Any</option>
                {Object.entries(REASONS).map(([k, l]) => (
                  <option key={k} value={k}>
                    {l}
                  </option>
                ))}
              </Select>
            </Field>
          </div>
          <label className="row g2 t-sm">
            <Switch
              checked={f.unsaved}
              onChange={(v) => setF({ unsaved: v })}
              label="Has unsaved changes"
            />
            Has unsaved changes
          </label>
          <label className="row g2 t-sm">
            <Switch
              checked={f.toMatch}
              onChange={(v) => setF({ toMatch: v })}
              label="Has a suggested invoice"
            />
            Has a suggested invoice
          </label>
          <label className="row g2 t-sm">
            <Switch
              checked={f.hideRejected}
              onChange={(v) => setF({ hideRejected: v })}
              label="Hide movements whose model suggestion you rejected"
            />
            Hide movements whose model suggestion you rejected
          </label>
          <label className="row g2 t-sm">
            <Switch
              checked={f.foreign}
              onChange={(v) => setF({ foreign: v })}
              label="Foreign currency only"
            />
            Foreign currency only
          </label>
        </Popover>
      ) : null}
    </div>
  );
}

/* ── Changes tray: page-wide (R11). ──────────────────────────────────── */
export function ChangesTray() {
  const [state, dispatch] = useStore();
  const page = usePage();
  const [open, setOpen] = useState(false);
  const c = trayCounts(state);
  if (!c.total && !state.paused) return null;
  const parts = [];
  if (c.edits)
    parts.push(
      `${plural(c.edits, "edit")} on ${plural(c.editRows, "movement")}`,
    );
  if (!c.adds && !Object.keys(c.kinds).length && !c.edits)
    parts.push("Nothing staged");
  if (c.adds) parts.push(plural(c.adds, "new movement"));
  Object.entries(c.kinds).forEach(([k, n]) =>
    parts.push(
      `${n} ${ACTION_WORD[k]!.toLowerCase()}${n > 1 && !/s$/.test(ACTION_WORD[k]!) ? "s" : ""}`,
    ),
  );
  const undoHint = state.undo.length
    ? state.undo[state.undo.length - 1]!.label
    : state.appliedAt
      ? "saved changes cannot be undone here"
      : undefined;
  const what =
    parts.join(" · ").replace(/(\d+) new movements?/, "$1 new") +
    " · not saved yet";
  // At rest: "12 · Review" (R22). Expanding shows the counts by kind.
  return (
    <div
      className={cx("tray", open && "open")}
      role="region"
      aria-label="Unsaved changes"
    >
      <button
        type="button"
        className="tray-toggle"
        aria-expanded={open}
        aria-label={`${c.total} unsaved: ${what}. Kept in this window only.`}
        data-tip={what + " · kept in this window only"}
        onClick={() => setOpen(!open)}
      >
        <span className="unsaved-bar static" aria-hidden="true"></span>
        <b className="tnum" aria-hidden="true">
          {c.total}
        </b>
        {state.paused ? (
          <Icon name="pause" size="xs" className="warn-t" />
        ) : null}
        <Icon
          name={open ? "chevronDown" : "chevronUp"}
          size="xs"
          className="muted"
        />
      </button>
      {open ? (
        <div className="tray-sum">
          <span className="t-sm">{what}</span>
          {c.total >= 50 ? (
            <span className="t-sm muted">· saves in parts</span>
          ) : null}
          {state.paused ? <span className="t-sm">· writes paused</span> : null}
        </div>
      ) : (
        <span className="f1"></span>
      )}
      <div className="tray-actions">
        {open ? (
          <>
            <IconButton
              icon="undo"
              label="Undo"
              shortcut="Ctrl+Z"
              hint={undoHint}
              aria-disabled={state.undo.length ? undefined : "true"}
              onClick={() => {
                if (state.undo.length) dispatch({ type: "UNDO" });
                else
                  page.toast(
                    state.appliedAt
                      ? "Saved changes cannot be undone here. Edit the movement again to reverse one."
                      : "Nothing to undo",
                  );
              }}
              size="sm"
            />
            <IconButton
              icon="redo"
              label="Redo"
              shortcut="Ctrl+Shift+Z"
              disabled={!state.redo.length}
              onClick={() => dispatch({ type: "REDO" })}
              size="sm"
            />
            <Button
              variant="ghost"
              size="sm"
              onClick={() => page.openDialog("discard")}
              disabled={!c.total}
            >
              Discard all
            </Button>
          </>
        ) : null}
        <Button
          size="sm"
          className="tray-review"
          onClick={() => page.openDialog("review")}
          aria-label={`Review and save ${plural(c.total, "change")}`}
          aria-disabled={state.paused ? "true" : undefined}
          aria-keyshortcuts="Control+Enter"
          data-tip={
            state.paused
              ? "Re-read first: an earlier write has an unknown outcome."
              : "Review and save"
          }
          data-kbd={state.paused ? undefined : "Ctrl+Enter"}
          disabled={!c.total}
        >
          Review
        </Button>
      </div>
    </div>
  );
}
