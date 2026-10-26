import { useState, useEffect, useRef, useMemo, useId, Fragment } from "react";
import { Icon, type IconName } from "./Icon";
import { usePage, type DialogProps } from "./page";
import type {
  ActionOp,
  Batch,
  Blocker,
  Cls,
  Direction,
  Fx,
  Invoice,
  Period,
  Rule,
  State,
  Use,
  View,
  Movement,
  Plan,
  PlanEntry,
  PlanOp,
} from "./types";
import { clsx as cx } from "clsx";
import {
  ACTION_WORD,
  F,
  EMPTY_FILTERS,
  PART_SIZE,
  SEAL_LABEL,
  SINGLE_SECONDS,
  buildPlan,
  canon,
  checkIssues,
  effDate,
  fmtDateLong,
  fmtMoney,
  fmtTime,
  getField,
  normDescription,
  parseAmount,
  parsePercent,
  periodLabel,
  periodRange,
  periodShort,
  plural,
  show,
  stagedRowIds,
  summarizeChanges,
  trayCounts,
  tsvEscape,
} from "./model";
import {
  Alert,
  Button,
  Checkbox,
  Dialog,
  Field,
  FilterChip,
  IconButton,
  Input,
  Kbd,
  Keys,
  Meter,
  Popover,
  Progress,
  Seg,
  Select,
  Spinner,
  Switch,
  announce,
  copyText,
  Overlay,
  sleep,
} from "./Primitives";
import {
  CLOCK,
  COL_LABEL,
  DEFAULT_COLUMNS,
  NOW,
  PRESETS,
  STICKY,
  useStore,
} from "./store";
import { DataTable } from "./DataGrid";
import {
  CATEGORY_LABEL,
  CLASSIFIED,
  CLS,
  DIRECTION,
  FAMILIES,
  IVA_LABEL,
  PAYMENT,
  PROVIDERS,
  TODAY,
  pct,
} from "./vocab";
import { hashHex, quarterOf } from "./data";
import type { Dispatch } from "react";
import type { Action } from "./store";
import { linkFacts, stageApproval } from "./Inspector";
import { PeriodControl, yearOk } from "./PeriodSelector";

/* ── Review and save (R2, R6, R11). ──────────────────────────────────── */
const opEntries = (o: PlanOp): PlanEntry[] => ("entries" in o ? o.entries : []);
export function DiffLines({
  base,
  eff,
  fields,
  derived = [],
}: {
  base: Movement;
  eff: Movement;
  fields: string[];
  derived?: string[];
}) {
  return (
    <div>
      {fields
        .filter((k) => F[k])
        .map((k) => (
          <div key={k} className="diffrow">
            <span className="muted">{F[k]!.label}</span>
            <span className="b">
              {show(k, getField(base, k), base, true) || "empty"}
            </span>
            <Icon name="arrow" size="xs" className="muted" />
            <span className="a">
              {show(k, getField(eff, k), eff, true) || "empty"}
              {derived.includes(k) ? (
                <span className="muted fw4 t-xs"> · worked out by Cadrumo</span>
              ) : null}
            </span>
          </div>
        ))}
    </div>
  );
}
export type ResStatus =
  | "applied"
  | "unchanged"
  | "refused"
  | "notSaved"
  | "unknown"
  | "notSent"
  | "running"
  | "waiting";
type DupHit = { row: string; amount: number; date: string; existing: string };
type FilePreview = {
  f: string;
  det?: string;
  rows?: number;
  imp?: number;
  skip?: number;
  dups?: DupHit[];
  unmapped?: string[];
  diag?: string[];
  refused?: boolean;
  why?: string;
  size?: string;
};
type ImportResult = {
  imported: number;
  skipped: number;
  dups: number;
  refused: FilePreview[];
  batchId?: string;
  span: [string, string];
  ids: string[];
  refusedChanged?: string[];
  created: number;
  skippedDup: number;
  refusedRows: { row: number; field: string; reason: string }[];
  ingested: number;
  drafts: number;
};
const NO_RESULT: ImportResult = {
  imported: 0,
  skipped: 0,
  dups: 0,
  refused: [],
  span: ["", ""],
  ids: [],
  created: 0,
  skippedDup: 0,
  refusedRows: [],
  ingested: 0,
  drafts: 0,
};
type NewRow = {
  date: string;
  amount: number;
  desc: string;
  cp: string;
  dir: Direction;
  cls: Cls;
  acc: string | undefined;
  currency?: string;
  fx?: Fx;
};
type Part = {
  amount?: string;
  description: string;
  cls: string;
  category: string;
};
type ResMap = Record<
  string,
  Record<string, { status: ResStatus; msg?: string }>
>;
export const RES_ICON: Record<ResStatus, [IconName, string, string]> = {
  applied: ["check", "ok-t", "Saved"],
  unchanged: ["minus", "muted", "Unchanged"],
  refused: ["refused", "danger-t", "Refused"],
  notSaved: ["refused", "danger-t", "Not saved"],
  unknown: ["unknown", "warn-t", "Outcome unknown"],
  notSent: ["pause", "muted", "Not sent"],
  running: ["loader", "muted spin", "Saving"],
  waiting: ["clock", "muted", "Waiting"],
};
export function ResIcon({ s }: { s: ResStatus }) {
  const [i, c, l] = RES_ICON[s];
  return (
    <span className="res-ico" data-tip={l}>
      <Icon name={i} size="xs" className={c} />
      <span className="sr-only">{l}</span>
    </span>
  );
}
export const KIND_FILTERS = [
  ["all", "All"],
  ["together", "Saved together"],
  ["single", "One at a time"],
  ["new", "New"],
  ["actions", "Actions"],
];

export function ReviewDialog({ onClose }: { onClose: () => void }) {
  const [state, dispatch] = useStore();
  const page = usePage();
  const plan = useMemo(
    () => buildPlan({ staged: state.staged, data: state.data }),
    [state.staged, state.data],
  );
  const planRef = useRef(plan);
  planRef.current = plan;
  const stateRef = useRef(state);
  stateRef.current = state;
  const [phase, setPhase] = useState("review");
  const [res, setRes] = useState<ResMap>({});
  const [parts, setParts] = useState<Record<string, string>>({});
  const [cur, setCur] = useState<string | null>(null);
  const [frozen, setFrozen] = useState<Plan | null>(null);
  const [kind, setKind] = useState("all");
  const [fieldFilter, setFieldFilter] = useState<string | null>(null);
  const [limit, setLimit] = useState(60);
  const [ticks, setTicks] = useState<Record<string, boolean>>({});
  const [ack, setAck] = useState(false);
  const [checkedAt, setCheckedAt] = useState<string | null>(null);
  useEffect(() => {
    requestAnimationFrame(() =>
      document.querySelector<HTMLElement>(".dialog .dialog-title")?.focus(),
    );
  }, [phase]);
  const resRef = useRef<ResMap>({});
  const setR = (
    opKey: string,
    rowKey: string,
    status: ResStatus,
    msg?: string,
  ) => {
    resRef.current = {
      ...resRef.current,
      [opKey]: { ...(resRef.current[opKey] || {}), [rowKey]: { status, msg } },
    };
    setRes(resRef.current);
  };
  const [ticks2, setTicks2] = useState<Record<string, boolean>>({});
  const facts = plan.links.map((a) => ({ a, ...linkFacts(state, a) }));
  const linksTicked = facts.every(
    (x) => ticks[x.a.id] && (!x.chips.length || ticks2[x.a.id]),
  );
  const total = trayCounts(state).total;
  const n = plan.changes;

  async function begin() {
    setPhase("reading");
    await sleep(700);
    // Ask only when both sides changed the same field; held rows are left out (V-12).
    const blockedIds = planRef.current.blocked.map((e) => e.id);
    const conflicts = Object.keys(state.staged.rows).filter(
      (id) =>
        state.data.byId[id]?.remoteChange &&
        "notes" in state.staged.rows[id]! &&
        !blockedIds.includes(id),
    );
    dispatch({ type: "REREAD_PERIOD", skip: blockedIds });
    if (conflicts.length) {
      setAck(false);
      setPhase("conflicts");
      return;
    }
    setTimeout(run, 0);
  }
  async function run() {
    const p = planRef.current;
    setFrozen(p);
    setPhase("applying");
    dispatch({ type: "APPLY_START" });
    const outcome = state.proto.outcome;
    const mix = outcome === "mix";
    const updates = p.ops.filter((o) => o.kind === "update");
    const refusedRows = new Set<string>();
    let stop: "paused" | "refused" | null = null;
    let firstBulk = true;
    for (const op of p.ops) {
      const keys = "entries" in op ? op.entries.map((e) => e.id) : [op.key];
      if (stop) {
        const msg =
          stop === "paused"
            ? "Not sent: writes paused after an unknown outcome. It stays staged."
            : "Not sent: an earlier part was not saved. Re-read, then save again.";
        keys.forEach((k) => {
          setR(op.key, k, "notSent", msg);
          if ("entries" in op)
            dispatch({ type: "OUTCOME", id: k, status: "notSent", msg });
        });
        continue;
      }
      setCur(op.key);
      keys.forEach((k) => setR(op.key, k, "waiting"));
      if (op.kind === "bulk") {
        setParts((x) => ({ ...x, [op.key]: "running" }));
        await sleep(900);
        if (firstBulk && outcome === "batchRefused") {
          setParts((x) => ({ ...x, [op.key]: "refused" }));
          const msg =
            "Not saved: the ledger changed while saving this part. Re-read, then save again.";
          keys.forEach((k) => {
            setR(op.key, k, "notSaved");
            dispatch({ type: "OUTCOME", id: k, status: "notSent", msg });
            refusedRows.add(k);
          });
          stop = "refused";
          continue;
        }
        if (firstBulk && outcome === "batchUnknown") {
          setParts((x) => ({ ...x, [op.key]: "unknown" }));
          keys.forEach((k) => {
            setR(op.key, k, "unknown");
            dispatch({
              type: "OUTCOME",
              id: k,
              status: "unknown",
              msg: "No answer came back for the part this was saved in. Re-read before writing again.",
              label: op.label,
            });
          });
          dispatch({
            type: "PAUSE",
            paused: {
              id: keys[0] ?? "",
              ids: keys,
              fields: op.entries.map((e) => [
                ...e.bulk,
                ...e.fields.filter((k) => e.routes[k] === "implicit"),
              ]),
              label: op.label,
              kind: "part",
            },
          });
          stop = "paused";
          continue;
        }
        firstBulk = false;
        setParts((x) => ({ ...x, [op.key]: "done" }));
        op.entries.forEach((e, i) => {
          const fields = [
            ...e.bulk,
            ...e.fields.filter((k) => e.routes[k] === "implicit"),
          ];
          if (e.gross) {
            const msg = `Refused: ${e.gross.text}. Fix the figures or the amount, then save again.`;
            setR(op.key, e.id, "refused", msg);
            dispatch({ type: "OUTCOME", id: e.id, status: "refused", msg });
            refusedRows.add(e.id);
          } else if (mix && op.entries.length >= 3 && i === 1) {
            setR(
              op.key,
              e.id,
              "unchanged",
              `The ledger already held ${e.bulk.map((k) => `${F[k]!.label.toLowerCase()} ${show(k, getField(e.eff, k), e.eff, true)}`).join(", ")} (read again ${fmtTime(NOW())}). Nothing changed.`,
            );
            dispatch({ type: "COMMIT", id: e.id, fields });
          } else if (
            mix &&
            !op.entries.some((x) => x.gross) &&
            op.entries.length >= 4 &&
            i === 2
          ) {
            const msg =
              "Refused: another window classified this movement after you read it. It was left as it is; look at its value and save again.";
            setR(op.key, e.id, "refused", msg);
            dispatch({ type: "OUTCOME", id: e.id, status: "refused", msg });
            refusedRows.add(e.id);
          } else {
            setR(op.key, e.id, "applied");
            dispatch({ type: "COMMIT", id: e.id, fields });
          }
        });
        await sleep(200);
      } else if (op.kind === "classify" || op.kind === "update") {
        const e = op.entries[0]!;
        if (refusedRows.has(e.id)) {
          const msg =
            "Not sent: its classification was refused first. It stays staged.";
          setR(op.key, e.id, "notSent", msg);
          continue;
        }
        setR(op.key, e.id, "running");
        await sleep(op.kind === "update" ? 650 : 450);
        if (
          op.kind === "update" &&
          mix &&
          updates.length >= 2 &&
          op === updates[updates.length - 1]
        ) {
          setR(
            op.key,
            e.id,
            "unknown",
            "No answer within 30 seconds. It may or may not have been saved.",
          );
          dispatch({
            type: "OUTCOME",
            id: e.id,
            status: "unknown",
            msg: "No answer came back. It may or may not have been saved; re-read before writing again.",
            label: op.label,
          });
          stop = "paused";
        } else if (e.gross && op.kind === "update") {
          const msg = `Refused: ${e.gross.text}.`;
          setR(op.key, e.id, "refused", msg);
          dispatch({ type: "OUTCOME", id: e.id, status: "refused", msg });
        } else {
          setR(
            op.key,
            e.id,
            "applied",
            e.identityNote && op.kind === "update"
              ? "Saved under a new reference"
              : undefined,
          );
          dispatch({
            type: "COMMIT",
            id: e.id,
            fields: op.kind === "update" ? e.update : e.classify,
          });
        }
      } else if (op.kind === "add") {
        setR(op.key, op.key, "running");
        await sleep(450);
        setR(op.key, op.key, "applied");
        dispatch({ type: "COMMIT_DRAFT", key: op.key });
      } else {
        const latest =
          stateRef.current.staged.actions.find((x) => x.id === op.action.id) ||
          op.action;
        if (latest.rowIds.some((id: string) => refusedRows.has(id))) {
          setR(
            op.key,
            op.key,
            "notSent",
            "Not sent: a change to the same movement was refused first.",
          );
          continue;
        }
        setR(op.key, op.key, "running");
        await sleep(400);
        setR(
          op.key,
          op.key,
          "applied",
          latest.type === "link"
            ? "Linked. This cannot be removed."
            : undefined,
        );
        dispatch({ type: "APPLY_ACTION", action: latest });
      }
    }
    setCur(null);
    const savedAny = Object.values(resRef.current).some((m) =>
      Object.values(m).some(
        (x) => x.status === "applied" || x.status === "unchanged",
      ),
    );
    dispatch({ type: "APPLY_END", savedAny });
    setPhase("done");
    await sleep(300);
    dispatch({ type: "CHECK" });
    setCheckedAt(NOW());
  }
  const shown = frozen || plan;
  const totals = useMemo(() => {
    const t: Partial<Record<ResStatus, number>> = {
      applied: 0,
      unchanged: 0,
      refused: 0,
      notSaved: 0,
      unknown: 0,
      notSent: 0,
    };
    Object.values(res).forEach((m) =>
      Object.values(m).forEach((x) => {
        if (t[x.status] != null) t[x.status]! += 1;
      }),
    );
    return t;
  }, [res]);
  const doneCount = Object.values(res).reduce(
    (s, m) =>
      s +
      Object.values(m).filter((x) => !["waiting", "running"].includes(x.status))
        .length,
    0,
  );
  const allCount = shown.ops.reduce(
    (s, o) => s + ("entries" in o ? o.entries.length : 1),
    0,
  );

  /* Blockers, grouped so hundreds of rows stay one line each (ADV-24). */
  const groups: Record<string, { e: PlanEntry; b: Blocker }[]> = {};
  plan.blocked.forEach((e) =>
    e.blockers.forEach((b) => {
      (groups[b.type] ||= []).push({ e, b });
    }),
  );
  const showInGrid = (ids: string[]) => {
    onClose();
    dispatch({
      type: "VIEW",
      patch: {
        filters: { ...EMPTY_FILTERS, unsaved: true },
        savedView: "custom",
      },
    });
    dispatch({ type: "SELECT", mode: "set", ids });
    page.setSection("movements");
    setTimeout(() => ids[0] && page.jumpTo(ids[0], "cls"), 80);
  };
  const classifyAll = (list: { e: PlanEntry }[], cls: string) =>
    dispatch({
      type: "STAGE",
      changes: list.flatMap(({ e }) =>
        e.eff.direction === "transfer" && cls !== "personal"
          ? []
          : [
              { id: e.id, field: "cls", value: cls },
              { id: e.id, field: "share", value: null },
            ],
      ),
      label: `Classify ${list.length} in review`,
    });
  const GROUP_TITLE: Record<string, (n: number) => string> = {
    needsClass: (n) => `${plural(n, "movement")} need a classification`,
    needsShare: (n) => `${plural(n, "Mixed movement")} need a business share`,
    transferTax: (n) =>
      `${plural(n, "transfer")} carry a classification or tax fields`,
    actionAndEdit: (n) =>
      `${plural(n, "movement")} have both edits and an action`,
    cannotClear: (n) => `${plural(n, "usage ratio")} cannot be cleared`,
    gone: (n) => `${plural(n, "movement")} are no longer in the ledger`,
  };
  const groupFix = (type: string, list: { e: PlanEntry }[]) => {
    const ids = list.map((x) => x.e.id);
    if (type === "needsClass")
      return (
        <>
          <Button
            size="xs"
            variant="outline"
            onClick={() => classifyAll(list, "business")}
          >
            Classify all as Business
          </Button>
          <Button
            size="xs"
            variant="outline"
            onClick={() => classifyAll(list, "personal")}
          >
            Classify all as Personal
          </Button>
          <Button size="xs" variant="ghost" onClick={() => showInGrid(ids)}>
            Show in grid
          </Button>
        </>
      );
    if (type === "needsShare")
      return (
        <Button size="xs" variant="outline" onClick={() => showInGrid(ids)}>
          Show in grid
        </Button>
      );
    if (type === "cannotClear")
      return (
        <Button
          size="xs"
          variant="outline"
          onClick={() =>
            list.forEach(({ e }) =>
              dispatch({ type: "REVERT_CELL", id: e.id, field: "usageRatio" }),
            )
          }
        >
          Keep the ratio
        </Button>
      );
    if (type === "gone")
      return (
        <Button
          size="xs"
          variant="outline"
          onClick={() =>
            list.forEach(({ e }) => dispatch({ type: "REVERT_ROW", id: e.id }))
          }
        >
          Drop their changes
        </Button>
      );
    if (type === "transferTax")
      return (
        <>
          <Button
            size="xs"
            variant="outline"
            onClick={() =>
              list.forEach(({ e }) =>
                dispatch({ type: "REVERT_ROW", id: e.id, keepActions: true }),
              )
            }
          >
            Drop the edits
          </Button>
          <Button size="xs" variant="ghost" onClick={() => showInGrid(ids)}>
            Show in grid
          </Button>
        </>
      );
    return null;
  };
  const kindOf = (e: PlanEntry) => (e.bulk.length ? "together" : "single");
  const readyRows = plan.ready.filter(
    (e) =>
      (kind === "all" || kind === kindOf(e)) &&
      (!fieldFilter || e.fields.includes(fieldFilter)),
  );
  const summary = summarizeChanges(plan.ready);
  const counts = {
    all: n,
    together: plan.ready.filter((e) => e.bulk.length).length,
    single: plan.ready.filter((e) => !e.bulk.length).length,
    new: plan.drafts.filter((d) => !d.missing.length).length,
    actions: plan.ops.filter((o): o is ActionOp => o.kind === "action").length,
  };
  const opIcon = (o: PlanOp): IconName =>
    o.kind === "bulk"
      ? "selectAll"
      : o.kind === "add"
        ? "plus"
        : o.kind === "update" || o.kind === "classify"
          ? "edit"
          : o.action.type === "link"
            ? "link"
            : o.action.type === "attach" || o.action.type === "detach"
              ? "attach"
              : o.action.type === "split"
                ? "split"
                : o.action.type === "remove"
                  ? "trash"
                  : o.action.type === "reject"
                    ? "close"
                    : o.action.type === "approve"
                      ? "agent"
                      : o.action.type === "rules"
                        ? "agent"
                        : "archive";
  const title =
    phase === "review" || phase === "reading"
      ? `Review and save · ${total}`
      : phase === "conflicts"
        ? "Changed since you read it"
        : phase === "applying"
          ? "Saving"
          : Object.values(res).some((m) =>
                Object.values(m).some(
                  (x) => x.status === "applied" || x.status === "unchanged",
                ),
              )
            ? "Saved"
            : "Nothing saved";
  const held = plan.held;
  // One line of counts leads the review (R22); the kinds expand below.
  const secs = plan.oneAtATime * SINGLE_SECONDS;
  const summaryLine =
    [
      counts.together ? `${counts.together} together` : "",
      counts.single
        ? `${counts.single} one by one (~${secs < 60 ? secs + " s" : Math.ceil(secs / 60) + " min"})`
        : "",
      counts.new ? `${counts.new} new` : "",
      counts.actions
        ? `${counts.actions} ${counts.actions === 1 ? "action" : "actions"}`
        : "",
      plan.links.length ? `${plan.links.length} permanent` : "",
      held ? `${held} held` : "",
    ]
      .filter(Boolean)
      .join(" · ") || "Nothing ready";
  return (
    <Dialog
      className="wide"
      placement="top"
      onClose={phase === "applying" || phase === "reading" ? () => {} : onClose}
      closeLabel={phase === "applying" || phase === "reading" ? false : "Close"}
      title={title}
      desc={
        phase === "review"
          ? summaryLine
          : phase === "reading"
            ? "Reading the period again to compare it with what you staged…"
            : phase === "conflicts"
              ? "Another window saved these movements after you read them. Choose what to keep for each."
              : phase === "applying"
                ? "Keep the window open; each step settles before the next starts."
                : "What the ledger answered, change by change."
      }
      footer={
        phase === "review" || phase === "reading" ? (
          <Fragment>
            <span className="muted t-sm f1">
              {held
                ? `${plural(held, "change")} held back by the problems above; ${held === 1 ? "it stays" : "they stay"} staged.`
                : plan.links.length && !linksTicked
                  ? "Tick each permanent link to save."
                  : ""}
            </span>
            <Button variant="ghost" onClick={onClose}>
              Keep editing
            </Button>
            <Button
              disabled={!plan.ops.length || !!state.paused || !linksTicked}
              pending={phase === "reading"}
              data-tip={state.paused ? "Re-read first" : undefined}
              onClick={begin}
            >
              {plan.ops.length
                ? `Save ${n}${held ? ` · ${held} held back` : ""}`
                : "Nothing ready to save"}
            </Button>
          </Fragment>
        ) : phase === "conflicts" ? (
          <Fragment>
            <span className="f1"></span>
            <Button variant="ghost" onClick={() => setPhase("review")}>
              Back
            </Button>
            <Button disabled={!ack} onClick={run}>
              Continue saving
            </Button>
          </Fragment>
        ) : phase === "applying" ? (
          <>
            <span className="f1 muted t-sm tnum">
              {doneCount} of {allCount}
            </span>
            <Button disabled pending>
              Saving
            </Button>
          </>
        ) : (
          <Fragment>
            <span className="f1 muted t-sm">
              {state.paused
                ? "Writes are paused until you re-read."
                : totals.refused || totals.notSaved
                  ? "Refused and unsaved changes stay staged for you to fix."
                  : "Everything settled."}
              {checkedAt
                ? ` Readiness checked again at ${fmtTime(checkedAt)}.`
                : ""}
            </span>
            {state.paused || totals.notSaved ? (
              <Button
                variant="outline"
                icon="sync"
                pending={page.rereading}
                onClick={async () => {
                  await page.reread();
                }}
              >
                Re-read
              </Button>
            ) : null}
            <Button onClick={onClose}>Done</Button>
          </Fragment>
        )
      }
    >
      {phase === "review" || phase === "reading" ? (
        <div className="col g4">
          {state.paused ? (
            <Alert tone="warning" icon="unknown" title="Writes are paused">
              An earlier save has an unknown outcome. Re-read the ledger before
              saving more.
            </Alert>
          ) : null}
          {held ? (
            <section className="sec" aria-labelledby="rv-held">
              <h3 id="rv-held" className="sec-title">
                Needs you first
              </h3>
              {Object.entries(groups)
                .filter(([t]) => t !== "actionAndEdit")
                .map(([type, list]) => (
                  <div key={type} className="review-row">
                    <div className="row g2 wrap">
                      <Icon name="alert" size="xs" className="danger-t" />
                      <b className="fw5 f1">
                        {GROUP_TITLE[type]?.(list.length)}
                      </b>
                      {groupFix(type, list)}
                    </div>
                    <span className="t-sm muted">{list[0]?.b.text}</span>
                    <span className="t-xs muted wrapt">
                      {list
                        .slice(0, 6)
                        .map((x) => x.e.base.description)
                        .join(" · ")}
                      {list.length > 6 ? ` · and ${list.length - 6} more` : ""}
                    </span>
                  </div>
                ))}
              {(groups.actionAndEdit || []).map(({ e, b }) => (
                <div key={"ae" + e.id} className="review-row">
                  <div className="row g2 wrap">
                    <Icon name="alert" size="xs" className="danger-t" />
                    <b className="fw5 f1 wrapt">{e.base.description}</b>
                    <Button
                      size="xs"
                      variant="outline"
                      onClick={() =>
                        dispatch({
                          type: "REVERT_ROW",
                          id: e.id,
                          keepActions: true,
                        })
                      }
                    >
                      Drop the edits
                    </Button>
                    <Button
                      size="xs"
                      variant="outline"
                      onClick={() =>
                        b.action &&
                        dispatch({ type: "UNSTAGE_ACTION", id: b.action.id })
                      }
                    >
                      Drop the{" "}
                      {ACTION_WORD[b.action?.type ?? ""]?.toLowerCase()}
                    </Button>
                  </div>
                  <span className="t-sm">{b.text}</span>
                </div>
              ))}
              {plan.blockedDrafts.map((d) => (
                <div key={d.key} className="review-row">
                  <div className="row g2 wrap">
                    <Icon name="alert" size="xs" className="danger-t" />
                    <b className="fw5 f1">
                      New movement
                      {d.fields.description ? " · " + d.fields.description : ""}
                    </b>
                    <Button
                      size="xs"
                      variant="outline"
                      onClick={() => {
                        onClose();
                        page.jumpTo(d.key, d.missing[0]);
                      }}
                    >
                      Go to the draft
                    </Button>
                  </div>
                  <span className="t-sm">
                    Fill in:{" "}
                    {d.missing.map((k) => F[k]!.label.toLowerCase()).join(", ")}
                    .
                  </span>
                </div>
              ))}
              {plan.heldActions.map((a) => (
                <div key={a.id} className="review-row">
                  <div className="row g2 wrap">
                    <Icon name="alert" size="xs" className="danger-t" />
                    <b className="fw5 f1 wrapt">{a.label}</b>
                    {a.holdReason === "Enter a share to approve" ? (
                      <Button
                        size="xs"
                        variant="outline"
                        onClick={() => {
                          onClose();
                          page.jumpTo(a.rowIds[0] ?? "", "cls");
                          page.openInspectorAt("classification");
                        }}
                      >
                        Enter a share
                      </Button>
                    ) : null}
                  </div>
                  <span className="t-sm">
                    {(a.holdReason ?? "").slice(0, 1).toUpperCase() +
                      (a.holdReason ?? "").slice(1)}
                    .
                  </span>
                </div>
              ))}
            </section>
          ) : null}
          {plan.links.length ? (
            <section className="sec permanent" aria-labelledby="rv-perm">
              <h3 id="rv-perm" className="sec-title">
                <Icon name="lock" size="xs" />
                Permanent
              </h3>
              <p className="t-sm">
                A link cannot be removed later, here or anywhere else. Tick each
                one you are sure of.
              </p>
              {facts.map(({ a, row, inv, settle, chips }) => (
                <div key={a.id} className="review-row link-row">
                  <span className="t-sm wrapt">
                    {row
                      ? `${fmtMoney(row.amount)} · ${row.counterparty || row.description} · ${fmtDateLong(effDate(row))}`
                      : "A removed movement"}{" "}
                    <span aria-label="linked to">↔</span>{" "}
                    {inv
                      ? `${inv.number} · ${fmtMoney(settle)} · ${inv.counterparty} · ${fmtDateLong(inv.date)}`
                      : "A missing invoice"}
                  </span>
                  {chips.length ? (
                    <div className="row g1 wrap">
                      {chips.map((c) => (
                        <span key={c} className="badge warning">
                          {c}
                        </span>
                      ))}
                    </div>
                  ) : null}
                  <label className="row g2 t-sm">
                    <Checkbox
                      checked={!!ticks[a.id]}
                      onChange={(e) =>
                        setTicks({ ...ticks, [a.id]: e.target.checked })
                      }
                    />
                    Link these · permanent
                  </label>
                  {chips.length ? (
                    <label className="row g2 t-sm">
                      <Checkbox
                        checked={!!ticks2[a.id]}
                        onChange={(e) =>
                          setTicks2({ ...ticks2, [a.id]: e.target.checked })
                        }
                      />
                      I know they differ
                    </label>
                  ) : null}
                </div>
              ))}
            </section>
          ) : null}
          {summary.length ? (
            <section className="sec" aria-labelledby="rv-sum">
              <h3 id="rv-sum" className="sec-title">
                Summary
              </h3>
              <DataTable
                label="Summary of changes"
                rowKey={(s) => s.field + s.from + s.to}
                rows={summary.slice(0, 12)}
                columns={[
                  {
                    key: "field",
                    label: "Field",
                    render: (s) => F[s.field]!.label,
                  },
                  {
                    key: "change",
                    label: "Change",
                    wrap: true,
                    render: (s) => (
                      <span className="row g1 wrap">
                        <span className="muted">{s.from}</span>
                        <Icon name="arrow" size="xs" className="muted" />
                        <span className="fw5">{s.to}</span>
                      </span>
                    ),
                  },
                  {
                    key: "n",
                    label: "Movements",
                    num: true,
                    render: (s) => s.ids.length,
                  },
                  {
                    key: "x",
                    label: "",
                    render: (s) => (
                      <Button
                        size="xs"
                        variant="ghost"
                        aria-pressed={fieldFilter === s.field}
                        onClick={() =>
                          setFieldFilter(
                            fieldFilter === s.field ? null : s.field,
                          )
                        }
                      >
                        {fieldFilter === s.field ? "Show all" : "Show rows"}
                      </Button>
                    ),
                  },
                ]}
              />
            </section>
          ) : null}
          <section className="sec" aria-labelledby="rv-ch">
            <h3 id="rv-ch" className="sec-title">
              Changes
            </h3>
            <div className="chips" role="group" aria-label="Show">
              {KIND_FILTERS.map(([k, l]) => (
                <button
                  key={k}
                  type="button"
                  className="btn pill"
                  aria-pressed={kind === k}
                  onClick={() => setKind(k!)}
                >
                  {l}{" "}
                  <span className="tnum">
                    {counts[k as keyof typeof counts]}
                  </span>
                </button>
              ))}
              {fieldFilter ? (
                <FilterChip
                  label={"Field: " + F[fieldFilter]!.label}
                  onRemove={() => setFieldFilter(null)}
                />
              ) : null}
            </div>
            {kind !== "new" && kind !== "actions"
              ? readyRows.slice(0, limit).map((e) => (
                  <div key={e.id} className="review-row">
                    <div className="row g2 wrap">
                      <span className="fw5 f1 wrapt">{e.base.description}</span>
                      <span className="tag">
                        {e.bulk.length ? "Saved together" : "One at a time"}
                      </span>
                      <span className="muted t-sm tnum">
                        {fmtDateLong(effDate(e.base))} ·{" "}
                        {fmtMoney(e.base.amount)} {e.base.currency}
                      </span>
                      <IconButton
                        icon="close"
                        label={"Drop the changes to " + e.base.description}
                        onClick={() =>
                          dispatch({
                            type: "REVERT_ROW",
                            id: e.id,
                            keepActions: true,
                          })
                        }
                      />
                    </div>
                    <DiffLines
                      base={e.base}
                      eff={e.eff}
                      fields={e.fields}
                      derived={e.derived || []}
                    />
                    {e.notes.map((t) => (
                      <span key={t} className="t-xs muted row g1">
                        <Icon name="info" size="xs" />
                        {t}
                      </span>
                    ))}
                    {e.identityNote ? (
                      <span className="t-xs row g1">
                        <Icon name="info" size="xs" />
                        {e.identityNote}
                      </span>
                    ) : null}
                    {e.gross ? (
                      <span className="t-xs row g1">
                        <Icon name="alert" size="xs" className="warn-t" />
                        Gross check: {e.gross.text}. The ledger decides; expect
                        a refusal.
                      </span>
                    ) : null}
                  </div>
                ))
              : null}
            {kind !== "new" &&
            kind !== "actions" &&
            readyRows.length > limit ? (
              <Button
                size="sm"
                variant="outline"
                onClick={() => setLimit(limit + 100)}
              >
                Show {Math.min(100, readyRows.length - limit)} more of{" "}
                {readyRows.length - limit}
              </Button>
            ) : null}
            {kind === "all" || kind === "new"
              ? plan.drafts
                  .filter((d) => !d.missing.length)
                  .map((d) => (
                    <div key={d.key} className="review-row">
                      <div className="row g2 wrap">
                        <span className="tag">
                          <Icon name="plus" />
                          New
                        </span>
                        <span className="fw5 f1 wrapt">
                          {d.fields.description}
                        </span>
                        <span className="tnum">
                          {fmtMoney(Number(d.fields.amount))} ·{" "}
                          {DIRECTION[d.fields.direction as Direction]?.label}
                        </span>
                        <IconButton
                          icon="close"
                          label={"Remove the draft " + d.fields.description}
                          onClick={() =>
                            dispatch({ type: "REMOVE_DRAFT", key: d.key })
                          }
                        />
                      </div>
                      <span className="t-xs muted">
                        Added once, even if the save is retried.
                      </span>
                    </div>
                  ))
              : null}
            {kind === "all" || kind === "actions"
              ? plan.ops
                  .filter((o): o is ActionOp => o.kind === "action")
                  .map((o) => (
                    <div key={o.key} className="review-row">
                      <div className="row g2 wrap">
                        <Icon name={opIcon(o)} />
                        <span className="fw5 f1 wrapt">{o.label}</span>
                        {o.action.type === "link" ? (
                          <span className="tag">
                            <Icon name="lock" />
                            Permanent
                          </span>
                        ) : null}
                        <IconButton
                          icon="close"
                          label={"Drop: " + o.label}
                          onClick={() =>
                            dispatch({
                              type: "UNSTAGE_ACTION",
                              id: o.action.id,
                            })
                          }
                        />
                      </div>
                      {o.action.type === "approve" &&
                      state.data.byId[o.action.rowIds[0] ?? ""] &&
                      o.action.payload?.fields
                        ? (() => {
                            const r =
                              state.data.byId[o.action.rowIds[0] ?? ""]!;
                            const f = o.action.payload!.fields!;
                            return (
                              <DiffLines
                                base={r}
                                eff={{ ...r, ...f }}
                                fields={[
                                  "cls",
                                  "share",
                                  "category",
                                  "ivaCategory",
                                ].filter(
                                  (k) =>
                                    k in f &&
                                    (k !== "share" || f.cls === "mixed"),
                                )}
                              />
                            );
                          })()
                        : null}
                    </div>
                  ))
              : null}
          </section>
          <details className="tech">
            <summary>Technical details</summary>
            <ul className="opplan">
              {plan.ops.map((o) => (
                <li key={o.key}>
                  <Icon name={opIcon(o)} />
                  <span className="f1 col">
                    <span>{o.label}</span>
                    <span className="mono t-xs muted">{o.tech}</span>
                  </span>
                </li>
              ))}
            </ul>
            <p className="t-xs muted">
              Order: classification, then corrections, then links and documents,
              then state changes. Classification saved together goes in parts of{" "}
              {PART_SIZE}.
            </p>
          </details>
        </div>
      ) : phase === "conflicts" ? (
        <div className="col g3">
          {(state.conflicts || []).map((c) => {
            const mine = state.staged.rows[c.id];
            return (
              <div key={c.id} className="review-row">
                <div className="row g2 wrap">
                  <b className="fw5 f1 wrapt">{c.after.description}</b>
                  <span className="muted t-sm">
                    Saved elsewhere at {fmtTime(c.after.modified)}
                  </span>
                </div>
                {c.changed.map((k) => (
                  <div key={k} className="col g1 t-sm">
                    <span className="muted">{F[k]!.label}</span>
                    <span>
                      When you read it:{" "}
                      <b>
                        {show(k, getField(c.before, k), c.before, true) ||
                          "empty"}
                      </b>
                    </span>
                    <span>
                      Now in the ledger:{" "}
                      <b>
                        {show(k, getField(c.after, k), c.after, true) ||
                          "empty"}
                      </b>
                    </span>
                    <span>
                      Your staged change:{" "}
                      <b>
                        {mine && k in mine
                          ? show(k, mine[k], c.after, true) || "empty"
                          : "none to this field"}
                      </b>
                    </span>
                  </div>
                ))}
                {mine ? (
                  <div className="row g2">
                    <Button size="xs" variant="outline" aria-pressed="true">
                      Keep mine
                    </Button>
                    <Button
                      size="xs"
                      variant="ghost"
                      onClick={() =>
                        dispatch({ type: "TAKE_THEIRS", id: c.id })
                      }
                    >
                      Take theirs
                    </Button>
                  </div>
                ) : (
                  <span className="t-sm muted">
                    You took theirs: your changes to it were dropped.
                  </span>
                )}
              </div>
            );
          })}
          <label className="row g2 t-sm">
            <Checkbox
              checked={ack}
              onChange={(e) => setAck(e.target.checked)}
            />
            I have looked at what changed
          </label>
        </div>
      ) : (
        <div className="col g3">
          {(state.conflictInfo || []).length ? (
            <Alert icon="info" title="Changed elsewhere since you read it">
              {(state.conflictInfo ?? [])
                .map(
                  (c) =>
                    `${c.after.description} (${c.changed.map((k) => F[k]!.label.toLowerCase()).join(", ")})`,
                )
                .join(" · ")}
              . Your changes don't touch those fields.
            </Alert>
          ) : null}
          <Progress
            value={doneCount}
            max={allCount || 1}
            label="Save progress"
          />
          {phase === "done" ? (
            <div className="row g3 wrap t-sm" role="status">
              {Object.entries(totals)
                .filter(([, k]) => k)
                .map(([k, c]) => (
                  <span key={k} className="row g1">
                    <ResIcon s={k as ResStatus} />
                    {RES_ICON[k as ResStatus][2]} <b className="tnum">{c}</b>
                  </span>
                ))}
            </div>
          ) : null}
          {state.paused && phase === "done" && state.paused.kind !== "part" ? (
            <Alert
              tone="warning"
              icon="unknown"
              title="One save has an unknown outcome"
            >
              {state.paused.label}. It may or may not be saved. Writes are
              paused and nothing is retried; re-read the ledger to find out.
            </Alert>
          ) : null}
          {shown.ops.map((o) => {
            const ps = parts[o.key];
            return (
              <section key={o.key} className="sec">
                <h3 className="sec-title">
                  <Icon name={opIcon(o)} size="xs" />
                  <span className="wrapt">{o.label}</span>
                  {cur === o.key ? (
                    <span className="ml-auto row g1">
                      <Spinner label="Saving" />
                      {o.kind === "bulk" ? "saving together" : "saving"}
                    </span>
                  ) : null}
                </h3>
                {ps === "refused" ? (
                  <Alert
                    tone="danger"
                    icon="refused"
                    title="Not saved: the ledger changed while saving"
                  >
                    Nothing in this part was saved. The changes stay staged;
                    later parts were not sent. Re-read, then save again.
                  </Alert>
                ) : null}
                {ps === "unknown" ? (
                  <Alert tone="warning" icon="unknown" title="Outcome unknown">
                    No answer came back for this part. It may or may not have
                    been saved, as a whole. Writes are paused until you re-read.
                  </Alert>
                ) : null}
                {o.kind === "bulk" && (ps === "running" || ps == null) ? (
                  <p className="t-sm muted">
                    {ps === "running"
                      ? `Saving ${plural(o.entries.length, "movement")} in one save…`
                      : "Waiting"}
                  </p>
                ) : ps === "refused" || ps === "unknown" ? (
                  <p className="t-sm muted">
                    {plural(opEntries(o).length, "movement")}:{" "}
                    {opEntries(o)
                      .slice(0, 5)
                      .map((e) => e.base.description)
                      .join(" · ")}
                    {opEntries(o).length > 5 ? " …" : ""}
                  </p>
                ) : (
                  <ul className="list-rows">
                    {("entries" in o
                      ? o.entries
                      : [
                          {
                            id: o.key,
                            base: {
                              description:
                                o.kind === "add"
                                  ? String(o.draft.fields.description)
                                  : o.label,
                            },
                          },
                        ]
                    ).map(
                      (e: { id: string; base: { description: string } }) => {
                        const r = res[o.key]?.[e.id] || { status: "waiting" };
                        return (
                          <li key={e.id}>
                            <ResIcon s={r.status} />
                            <span className="f1 col">
                              <span className="wrapt">
                                {e.base.description}
                              </span>
                              {r.msg ? (
                                <span
                                  className="t-xs"
                                  style={{
                                    color:
                                      r.status === "refused"
                                        ? "var(--foreground)"
                                        : "var(--muted-foreground)",
                                  }}
                                >
                                  {r.msg}
                                </span>
                              ) : null}
                            </span>
                          </li>
                        );
                      },
                    )}
                  </ul>
                )}
              </section>
            );
          })}
        </div>
      )}
    </Dialog>
  );
}

export function ClassifyDialog({
  kind,
  ids,
  skipped,
  partial,
  onClose,
}: DialogProps["classify"] & { onClose: () => void }) {
  const [, dispatch] = useStore();
  const page = usePage();
  const [cat, setCat] = useState("");
  const [share, setShare] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const n = ids.length;
  const stage = () => {
    let sh: number | null = null;
    if (kind === "mixed") {
      const r = parsePercent(share, { label: "Business share" });
      if (r.error || r.empty) {
        setErr(r.error || "Mixed needs a business share.");
        return;
      }
      sh = Number(r.value);
    }
    if (kind === "business" && !cat) {
      setErr("Choose a category, or keep each movement's own.");
      return;
    }
    const keep = cat === "__keep";
    dispatch({
      type: "STAGE",
      label: `Classify as ${CLS[kind as Cls].label}`,
      changes: ids.flatMap((id) => [
        { id, field: "cls", value: kind },
        { id, field: "share", value: sh },
        ...(cat && !keep ? [{ id, field: "category", value: cat }] : []),
      ]),
    });
    page.toast(
      `${CLS[kind as Cls].label}${kind === "mixed" ? " " + pct(sh ?? 0) : ""}${cat && !keep ? " · " + CATEGORY_LABEL[cat] : ""} · ${plural(n, "movement")} staged`,
    );
    onClose();
  };
  return (
    <Dialog
      onClose={onClose}
      title={`${CLS[kind as Cls].label} for ${plural(n, "movement")}`}
      desc={
        [
          skipped ? `${skipped} skipped: sealed, read-only or transfers.` : "",
          partial
            ? `Loaded rows only: ${partial.loaded} of ${partial.total}.`
            : "",
        ]
          .filter(Boolean)
          .join(" ") || "Staged, not saved."
      }
      focusFirst
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={stage}>Stage for {n}</Button>
        </>
      }
    >
      <div className="col g3">
        {kind === "mixed" ? (
          <Field
            label="Business share"
            req
            hint="Write 50 for 50%."
            error={err && kind === "mixed" ? err : null}
          >
            <Input
              data-autofocus
              value={share}
              inputMode="decimal"
              placeholder="e.g. 50"
              onChange={(e) => {
                setShare(e.target.value);
                setErr(null);
              }}
              onKeyDown={(e) => e.key === "Enter" && stage()}
            />
          </Field>
        ) : null}
        <Field
          label="Category"
          req={kind === "business"}
          error={err && kind === "business" ? err : null}
        >
          <Select
            data-autofocus={kind === "business" ? "" : undefined}
            value={cat}
            onChange={(e) => {
              setCat(e.target.value);
              setErr(null);
            }}
          >
            <option value="" disabled={kind === "business"}>
              {kind === "business"
                ? "Choose a category…"
                : "Keep each movement's own"}
            </option>
            {kind === "business" ? (
              <option value="__keep">Keep each movement's own</option>
            ) : null}
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
      </div>
    </Dialog>
  );
}
export function DiscardDialog({ onClose }: { onClose: () => void }) {
  const [state, dispatch] = useStore();
  const c = trayCounts(state);
  return (
    <Dialog
      onClose={onClose}
      title="Discard every unsaved change?"
      desc={`${plural(c.total, "unsaved change")} will be dropped. Nothing in the ledger changes. Ctrl+Z still brings them back.`}
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            Keep them
          </Button>
          <Button
            variant="destructive"
            data-autofocus
            onClick={() => {
              dispatch({ type: "DISCARD" });
              onClose();
            }}
          >
            Discard all
          </Button>
        </>
      }
    />
  );
}
/* Leaving with unsaved work (R11): the only place the window-only note
   is said out loud. */
export function LeaveDialog({
  what,
  onLeave,
  onClose,
}: DialogProps["leave"] & { onClose: () => void }) {
  const [state, dispatch] = useStore();
  const page = usePage();
  const c = trayCounts(state);
  return (
    <Dialog
      onClose={onClose}
      title="Leave with unsaved changes?"
      desc={`${plural(c.total, "change")} are kept only in this window. ${what} drops them.`}
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button
            variant="outline"
            onClick={() => {
              dispatch({ type: "DISCARD" });
              onClose();
              onLeave();
            }}
          >
            Discard and leave
          </Button>
          <Button
            data-autofocus
            onClick={() => {
              onClose();
              page.openDialog("review");
            }}
          >
            Review and save
          </Button>
        </>
      }
    >
      <p className="t-sm muted">
        {c.total >= 50
          ? "A large batch can be saved in parts from the review."
          : "Saving takes a moment; nothing is written until you confirm in the review."}
      </p>
    </Dialog>
  );
}

/* Lifecycle, split, merge and removal: each staged with its reason. */
export function ActionDialog({
  type,
  ids,
  opts = {},
  onClose,
}: DialogProps["action"] & { onClose: () => void }) {
  const [state, dispatch] = useStore();
  const page = usePage();
  const rows = ids.flatMap((id) => state.data.byId[id] ?? []);
  const r0 = rows[0]!;
  const [reason, setReason] = useState("");
  const proposal = type === "split" && opts.proposal;
  const [parts, setParts] = useState<Part[]>(() =>
    type !== "split"
      ? []
      : proposal
        ? [
            {
              amount: canon(Math.round(r0.amount * 0.6)),
              description: r0.description + " · work",
              cls: "business",
              category: r0.category || "material_oficina",
            },
            {
              description: r0.description + " · personal",
              cls: "personal",
              category: "",
            },
          ]
        : [
            {
              amount: "",
              description: r0.description + " · part 1",
              cls: "",
              category: "",
            },
            {
              description: r0.description + " · part 2",
              cls: "",
              category: "",
            },
          ],
  );
  const [preview, setPreview] = useState<{
    evidence: (string | undefined)[];
    attachments: number;
    blocking: Use[];
    stale: Use[];
    invoice: Invoice | null | undefined;
  } | null>(null);
  const [busy, setBusy] = useState(false);
  const T = (
    {
      archive: [
        "Archive",
        "Archived movements stay on record but leave every view of active work and every declaration.",
        "ledger.archive",
        true,
      ],
      stash: [
        "Set aside",
        "A movement set aside stays out of calculations until you restore it.",
        "ledger.stash",
        true,
      ],
      exclude: [
        "Exclude from filing",
        "It stays active and visible, marked as deliberately left out of every declaration.",
        "ledger.exclude",
        true,
      ],
      restore: [
        "Restore",
        "Archived or set-aside movements become active again, with their earlier facts.",
        "ledger.restore",
        true,
      ],
      merge: [
        "Merge parts back",
        "The parts of the split become one movement again, the original.",
        "ledger.merge",
        false,
      ],
      split: [
        "Split into parts",
        "The movement becomes a split parent; its parts are new movements that add up to it exactly.",
        "ledger.split.manual",
        false,
      ],
      remove: [
        "Remove",
        "Removing deletes the movement and what only it uses. A dry run comes first: nothing is removed until you save.",
        "ledger.remove",
        true,
      ],
    } satisfies Record<string, [string, string, string, boolean]>
  )[type];
  const eligible = rows.filter((r) => {
    if (type === "restore")
      return r.lifecycle === "archived" || r.lifecycle === "stashed";
    if (type === "remove") return true;
    if (r.sealed?.length) return false;
    if (type === "exclude")
      return r.lifecycle === "active" && r.cls !== "excluded";
    if (type === "merge") return r.split?.role === "child";
    return r.lifecycle === "active";
  });
  const skipped = rows.length - eligible.length;
  const fixed = parts
    .slice(0, -1)
    .map((p) =>
      parseAmount(p.amount, { allowZero: false, label: "Part amount" }),
    );
  const sum = fixed.reduce((s, c) => s + Number(c.value || 0), 0);
  const remainder = type === "split" ? r0.amount - sum : 0;
  const splitOk =
    type !== "split" ||
    (fixed.every((c) => Number(c.value) > 0) &&
      remainder > 0 &&
      parts.every((p) => p.description.trim()) &&
      parts.every((p) => p.cls !== "business" || true));
  const blocked = type === "remove" && !!preview?.blocking.length;
  const reasonOk = !T[3] || reason.trim();
  const setPart = (i: number, patch: Partial<Part>) =>
    setParts(parts.map((x, j) => (j === i ? { ...x, ...patch } : x)));
  const stageIt = () => {
    const label = `${T[0]} · ${eligible.length === 1 ? eligible[0]!.description : plural(eligible.length, "movement")}`;
    const children =
      type === "split"
        ? parts.map((p, i) => ({
            amount: i < parts.length - 1 ? Number(fixed[i]?.value) : remainder,
            description: p.description.trim(),
            cls: (p.cls || undefined) as Cls | undefined,
            category: p.cls === "business" && p.category ? p.category : null,
          }))
        : undefined;
    dispatch({
      type: "STAGE_ACTION",
      action: {
        id:
          type +
          "-" +
          eligible
            .map((r) => r.id)
            .join("")
            .slice(0, 24),
        type,
        rowIds: eligible.map((r) => r.id),
        label,
        tech: `${T[2]}${eligible.length > 1 ? ` · one call per movement, ${eligible.length} calls` : ""}${type === "remove" ? ` · dry-run report ${hashHex("dry" + r0.id, 10)}, run again at save` : ""}${children?.some((c) => c.cls) ? " · then ledger.classify on the parts" : ""}`,
        payload: { reason: reason.trim(), children, report: preview },
      },
    });
    page.toast(
      `${T[0]} staged for ${plural(eligible.length, "movement")} · not saved`,
    );
    onClose();
  };
  const dryRun = async () => {
    setBusy(true);
    await sleep(800);
    setBusy(false);
    setPreview({
      evidence: r0.evidenceId
        ? [state.data.docs.find((d) => d.id === r0.evidenceId)?.file]
        : [],
      attachments: r0.attachments.length,
      blocking: r0.sealed || [],
      stale: r0.uses.filter((u) => u.state === "draft"),
      invoice: r0.invoiceId
        ? state.data.invoices.find((i) => i.id === r0.invoiceId)
        : null,
    });
  };
  return (
    <Dialog
      className={type === "split" ? "mid" : ""}
      onClose={onClose}
      title={
        T[0] + (eligible.length > 1 ? ` ${eligible.length} movements` : "")
      }
      desc={T[1]}
      focusFirst
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          {type === "remove" && !preview ? (
            <Button variant="outline" pending={busy} onClick={dryRun}>
              Run the dry run
            </Button>
          ) : (
            <Button
              variant={type === "remove" ? "destructive" : "primary"}
              disabled={!eligible.length || !reasonOk || !splitOk || blocked}
              onClick={stageIt}
            >
              Stage {T[0].toLowerCase()}
            </Button>
          )}
        </>
      }
    >
      <div className="col g3">
        {eligible.length === 1 ? (
          <div className="card-wash">
            <div className="row g2">
              <span className="fw5 f1 wrapt">{eligible[0]!.description}</span>
              <span className="tnum">
                {fmtMoney(eligible[0]!.amount)} {eligible[0]!.currency}
              </span>
            </div>
            <span className="muted t-sm">
              {eligible[0]!.counterparty} · {fmtDateLong(effDate(eligible[0]!))}
            </span>
          </div>
        ) : null}
        {skipped ? (
          <Alert icon="lock">
            {plural(skipped, "selected movement")} cannot take this (sealed, or
            not in the right state) and will be left as{" "}
            {skipped === 1 ? "it is" : "they are"}.
          </Alert>
        ) : null}
        {!eligible.length && type !== "remove" ? (
          <Alert tone="warning">
            None of the selected movements can take this.
          </Alert>
        ) : null}
        {proposal ? (
          <Alert icon="agent" title="The local model proposed this split">
            Check each part before staging it; the model never sets a rate or an
            amount you have not seen.
          </Alert>
        ) : null}
        {type === "split" ? (
          <div className="col g2">
            <div className="sec-title">Parts</div>
            {parts.map((p, i) => {
              const last = i === parts.length - 1;
              return (
                <div key={i} className="card-wash col g2">
                  <div className="row g2" style={{ alignItems: "start" }}>
                    {last ? (
                      <span
                        className="input sm tnum row"
                        style={{
                          width: "calc(var(--spacing) * 28)",
                          justifyContent: "flex-end",
                        }}
                        aria-label={`Part ${i + 1} amount, the remainder`}
                      >
                        {fmtMoney(remainder)}
                      </span>
                    ) : (
                      <Input
                        size="sm"
                        style={{ width: "calc(var(--spacing) * 28)" }}
                        className="tnum"
                        placeholder="0.00"
                        inputMode="decimal"
                        value={p.amount}
                        aria-label={`Part ${i + 1} amount`}
                        aria-invalid={!!(p.amount && fixed[i]?.error)}
                        onChange={(e) => setPart(i, { amount: e.target.value })}
                      />
                    )}
                    <Input
                      size="sm"
                      className="f1"
                      value={p.description}
                      aria-label={`Part ${i + 1} description`}
                      onChange={(e) =>
                        setPart(i, { description: e.target.value })
                      }
                    />
                    <IconButton
                      icon="close"
                      label={`Remove part ${i + 1}`}
                      disabled={parts.length <= 2}
                      onClick={() => setParts(parts.filter((_, j) => j !== i))}
                    />
                  </div>
                  <div className="row g2 wrap">
                    <div style={{ width: "calc(var(--spacing) * 40)" }}>
                      <Select
                        size="sm"
                        aria-label={`Part ${i + 1} classification`}
                        value={p.cls}
                        onChange={(e) => setPart(i, { cls: e.target.value })}
                      >
                        <option value="">Not classified</option>
                        <option value="business">Business</option>
                        <option value="personal">Personal</option>
                      </Select>
                    </div>
                    {p.cls === "business" ? (
                      <div className="f1">
                        <Select
                          size="sm"
                          aria-label={`Part ${i + 1} category`}
                          value={p.category}
                          onChange={(e) =>
                            setPart(i, { category: e.target.value })
                          }
                        >
                          <option value="">Choose a category…</option>
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
                      </div>
                    ) : null}
                    {last ? (
                      <span className="t-xs muted">
                        The remainder fills in on its own.
                      </span>
                    ) : null}
                  </div>
                </div>
              );
            })}
            {fixed.find((c, i) => parts[i]?.amount && c.error) ? (
              <span className="danger-t t-sm row g1">
                <Icon name="alert" size="xs" />
                {fixed.find((c, i) => parts[i]?.amount && c.error)?.error}
              </span>
            ) : null}
            <div className="row g2">
              <Button
                size="xs"
                variant="ghost"
                icon="plus"
                onClick={() =>
                  setParts([
                    ...parts.slice(0, -1),
                    {
                      amount: "",
                      description: r0.description + " · part " + parts.length,
                      cls: "",
                      category: "",
                    },
                    parts[parts.length - 1]!,
                  ])
                }
              >
                Add a part
              </Button>
              <span className="f1"></span>
              <span
                className={cx("t-sm tnum", remainder > 0 ? "" : "danger-t")}
              >
                {remainder > 0
                  ? `Remainder ${fmtMoney(remainder)} of ${fmtMoney(r0.amount)}`
                  : `The parts go over ${fmtMoney(r0.amount)}`}
              </span>
            </div>
            <p className="t-xs muted">
              Parts keep the parent's date, direction and account. A
              classification chosen here is saved after the split. The parent
              stays on record as Split, with its parts under it.
            </p>
            <Alert icon="scale" title="Partly used for work?">
              Use Mixed with a business share instead: one movement, no parts.{" "}
              <Button
                size="xs"
                variant="link"
                onClick={() => {
                  onClose();
                  page.openInspectorAt("classification");
                }}
              >
                Use Mixed instead
              </Button>
            </Alert>
          </div>
        ) : null}
        {type === "remove" && preview ? (
          <div className="col g2">
            <div className="sec-title">Dry run: what the ledger reports</div>
            {preview.blocking.length ? (
              <Alert tone="danger" icon="lock" title="Removal is blocked">
                Used in{" "}
                {preview.blocking
                  .map(
                    (u) =>
                      `Modelo ${u.modelo} · ${u.period} (${SEAL_LABEL[u.state]})`,
                  )
                  .join(" and ")}
                . A sealed declaration's movements cannot be removed.
              </Alert>
            ) : null}
            <dl className="kv">
              <dt>Purchase invoice evidence removed</dt>
              <dd>
                {preview.evidence.length ? preview.evidence.join(", ") : "None"}
              </dd>
              <dt>Attachments removed</dt>
              <dd>{preview.attachments || "None"}</dd>
              <dt>Draft declarations to recalculate</dt>
              <dd>
                {preview.stale.length
                  ? preview.stale
                      .map((u) => `Modelo ${u.modelo} · ${u.period}`)
                      .join(", ")
                  : "None"}
              </dd>
            </dl>
            {preview.invoice ? (
              <Alert tone="warning" title="A one-sided link stays behind">
                Invoice {preview.invoice.number} keeps its link to this movement
                after removal. It shows under Invoices as linked to a removed
                movement; links cannot be removed.
              </Alert>
            ) : null}
            <p className="t-xs muted">
              The dry run runs again when you save. If its report has changed by
              then, the removal is held back for you to look at again.
            </p>
          </div>
        ) : null}
        {type !== "remove" || preview ? (
          <Field
            label={T[3] ? "Reason" : "Reason (optional)"}
            req={T[3]}
            hint="Kept in each movement's history. Up to 500 characters."
          >
            <Input
              data-autofocus={type === "split" ? undefined : true}
              value={reason}
              maxLength={500}
              onChange={(e) => setReason(e.target.value)}
              placeholder={
                type === "archive"
                  ? "e.g. duplicate of the N26 row"
                  : type === "exclude"
                    ? "e.g. tax payment, not an expense"
                    : type === "split"
                      ? "e.g. one order, business and personal items"
                      : "Why"
              }
            />
          </Field>
        ) : null}
      </div>
    </Dialog>
  );
}

/* Paste preview (R7): nothing is staged until Paste. */
export function PasteDialog({
  plan,
  onPaste,
  onClose,
}: DialogProps["paste"] & { onClose: () => void }) {
  const cols = plan.cols.map((k) => COL_LABEL[k] || k).join(", ");
  const reasons = [...new Set(plan.refusals.map((r) => r.msg))].slice(0, 3);
  return (
    <Dialog
      onClose={onClose}
      title="Paste into the grid?"
      desc={`${plural(plan.rows, "row")} from the clipboard into ${cols || "no editable column"}. Nothing is staged until you paste.`}
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button
            data-autofocus
            disabled={!plan.changes.length}
            onClick={() => {
              onClose();
              onPaste();
            }}
          >
            Paste {plural(plan.changes.length, "cell")}
          </Button>
        </>
      }
    >
      <dl className="kv">
        <dt>Cells that change</dt>
        <dd className="tnum">{plan.changes.length}</dd>
        <dt>Refused</dt>
        <dd className="col">
          <span className="tnum">{plan.refusals.length}</span>
          {reasons.map((r) => (
            <span key={r} className="t-sm muted">
              {r}
            </span>
          ))}
        </dd>
        <dt>Past the last row or column</dt>
        <dd className="tnum">
          {plan.dropped ? <b>{plan.dropped} dropped</b> : "None"}
        </dd>
        <dt>Blank cells</dt>
        <dd>
          {plan.blanks
            ? `${plan.blanks} left as they are (only Delete clears)`
            : "None"}
        </dd>
        <dt>New identity</dt>
        <dd>
          {plan.identity ? (
            <span>
              <b className="tnum">{plan.identity}</b>{" "}
              {plan.identity === 1 ? "movement is" : "movements are"} saved
              under a new reference: description, amount, date or account
              changes it.
            </span>
          ) : (
            "None"
          )}
        </dd>
      </dl>
    </Dialog>
  );
}

/* Rules (R8): match on counterparty, words in the description or an
   amount range; applying them is staged like any other write. */
export function ruleTest(rule: Rule, r: Movement) {
  const kind = rule.kind || "regex";
  const value = rule.value ?? "";
  if (kind === "counterparty")
    return (r.counterparty || "").toLowerCase() === value.toLowerCase();
  if (kind === "contains") {
    const d = r.description.toLowerCase();
    return value
      .toLowerCase()
      .split(/\s+/)
      .filter(Boolean)
      .every((w) => d.includes(w));
  }
  if (kind === "amount")
    return (
      r.amount >= (rule.min ?? 0) &&
      r.amount <= (rule.max ?? 0) &&
      (!value || (r.counterparty || "").toLowerCase() === value.toLowerCase())
    );
  try {
    return new RegExp(rule.pattern ?? "", "i").test(r.description);
  } catch {
    return false;
  }
}
export const ruleText = (rule: Rule): string =>
  rule.name
    ? rule.name
    : rule.kind === "counterparty"
      ? `Counterparty is “${rule.value}”`
      : rule.kind === "contains"
        ? `Description contains “${rule.value}”`
        : rule.kind === "amount"
          ? `Amount ${fmtMoney(rule.min)} to ${fmtMoney(rule.max)}${rule.value ? ` from “${rule.value}”` : ""}`
          : `Description matches ${rule.pattern}`;
export function ruleCandidates(
  rule: Rule,
  state: Pick<State, "staged" | "data">,
) {
  const staged = stagedRowIds(state);
  const all = Object.values(state.data.byId).filter(
    (r) =>
      r.lifecycle === "active" &&
      !r.sealed?.length &&
      !CLASSIFIED.has(r.cls) &&
      r.cls !== "skipped" &&
      r.cls !== "excluded" &&
      ruleTest(rule, r),
  );
  return {
    rows: all.filter((r) => !staged.has(r.id)),
    skippedStaged: all.filter((r) => staged.has(r.id)).length,
  };
}
export function stageRulesAction(
  dispatch: Dispatch<Action>,
  pairs: { rule: Rule; rows: Movement[] }[],
  newRule?: Rule,
) {
  const matches = pairs.flatMap(({ rule, rows }) =>
    rows.map((r) => ({
      id: r.id,
      cls: rule.cls,
      category: rule.category,
      rule: rule.id,
      pattern: ruleText(rule),
    })),
  );
  const n = new Set(matches.map((m) => m.id)).size;
  dispatch({
    type: "STAGE_ACTION",
    action: {
      id:
        "rules-" +
        (newRule
          ? newRule.id
          : hashHex("apply" + matches.map((m) => m.id).join(""), 6)),
      type: "rules",
      rowIds: [...new Set(matches.map((m) => m.id))],
      label: newRule
        ? `New rule: ${ruleText(newRule)}${n ? ` · classifies ${plural(n, "movement")}` : ""}`
        : `Apply rules · ${plural(n, "movement")}`,
      tech: `${newRule ? "ledger.rules.add, then " : ""}ledger.rules.apply · dry run first, then apply`,
      payload: { matches, newRule },
    },
  });
  return n;
}
export function RuleDialog({
  rows,
  from,
  onClose,
}: DialogProps["rule"] & { onClose: () => void }) {
  const [state, dispatch] = useStore();
  const page = usePage();
  const cps = [
    ...new Set(rows.flatMap((r) => (r.counterparty ? [r.counterparty] : []))),
  ];
  const words = (() => {
    const sets = rows.map(
      (r) =>
        new Set(
          normDescription(r.description)
            .toLowerCase()
            .split(" ")
            .filter((w) => w.length > 2),
        ),
    );
    const first = [...(sets[0] || [])];
    return first
      .filter((w) => sets.every((s) => s.has(w)))
      .slice(0, 3)
      .join(" ");
  })();
  const amounts = rows.length ? rows.map((r) => r.amount) : [0, 0];
  const [kind, setKind] = useState(
    from === "description" || cps.length !== 1 ? "contains" : "counterparty",
  );
  const [value, setValue] = useState(
    kind === "counterparty" ? cps[0] || "" : words,
  );
  const [advanced, setAdvanced] = useState(false);
  const [pattern, setPattern] = useState(words.toUpperCase());
  const [min, setMin] = useState(canon(Math.min(...amounts)));
  const [max, setMax] = useState(canon(Math.max(...amounts)));
  const common =
    rows.every((r) => r.cls === rows[0]?.cls) &&
    CLASSIFIED.has(rows[0]?.cls ?? "") &&
    rows[0]?.cls !== "mixed"
      ? rows[0]!.cls
      : "business";
  const [cls, setCls] = useState<Cls>(common as Cls);
  const [cat, setCat] = useState(
    rows.every((r) => r.category === rows[0]?.category) && rows[0]?.category
      ? rows[0].category
      : "",
  );
  const [order, setOrder] = useState(String(state.data.rules.length + 1));
  const [also, setAlso] = useState(true);
  const [name, setName] = useState(
    cps.length === 1
      ? cps[0]!
      : words
        ? words.replace(/\b\w/g, (c) => c.toUpperCase())
        : "",
  );
  let reErr: string | null = null;
  if (kind === "contains" && advanced)
    try {
      new RegExp(pattern, "i");
    } catch (e) {
      reErr =
        "Not a valid pattern: " +
        (e instanceof Error ? e.message : String(e)).split(":").pop()!.trim();
    }
  const minP = parseAmount(min, { label: "From" }),
    maxP = parseAmount(max, { label: "To" });
  const amountErr =
    kind === "amount"
      ? minP.error ||
        maxP.error ||
        (Number(minP.value) > Number(maxP.value)
          ? "“From” is above “To”."
          : null)
      : null;
  const rule: Rule = {
    id: "r-" + hashHex(kind + value + pattern + min + max + cls, 6),
    name: name.trim() || undefined,
    kind: kind === "contains" && advanced ? "regex" : kind,
    value: value.trim(),
    pattern: kind === "contains" && advanced ? pattern : undefined,
    min: typeof minP.value === "number" ? minP.value : null,
    max: typeof maxP.value === "number" ? maxP.value : null,
    cls,
    category: cls === "business" && cat ? cat : null,
    created: TODAY,
    actor: "You",
  };
  const ok =
    !reErr &&
    !amountErr &&
    (kind === "amount" ||
      (advanced && kind === "contains" ? pattern.trim() : value.trim()));
  const cand = ok
    ? ruleCandidates(rule, state)
    : { rows: [], skippedStaged: 0 };
  const submit = () => {
    const pos = Math.max(
      1,
      Math.min(
        state.data.rules.length + 1,
        +order || state.data.rules.length + 1,
      ),
    );
    const nr = { ...rule, priority: pos * 10 - 5, order: pos };
    const n = stageRulesAction(
      dispatch,
      also ? [{ rule: nr, rows: cand.rows }] : [],
      nr,
    );
    page.toast(
      `Rule staged${n ? `, with ${plural(n, "movement")} to classify` : ""} · not saved`,
    );
    onClose();
  };
  return (
    <Dialog
      className="mid"
      onClose={onClose}
      title="Make a rule"
      desc={`From ${plural(rows.length, "movement")}. A rule classifies new and unclassified movements; your own classifications are never touched.`}
      focusFirst
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button disabled={!ok} onClick={submit}>
            Stage the rule
          </Button>
        </>
      }
    >
      <div className="col g3">
        <Field label="Match on">
          <Seg
            label="Match on"
            value={kind}
            onChange={setKind}
            options={[
              { value: "counterparty", label: "Counterparty" },
              { value: "contains", label: "Description contains" },
              { value: "amount", label: "Amount range" },
            ]}
          />
        </Field>
        {kind === "counterparty" ? (
          <Field
            label="Counterparty is"
            req
            hint={
              cps.length > 1
                ? `The selection has ${cps.length} counterparties; the rule takes one.`
                : "Exactly this name, any case."
            }
          >
            <Input value={value} onChange={(e) => setValue(e.target.value)} />
          </Field>
        ) : null}
        {kind === "contains" ? (
          <Fragment>
            {advanced ? (
              <Field
                label="Description matches the pattern"
                req
                hint="| means or; ^ anchors the start. Case does not matter."
                error={reErr}
              >
                <Input
                  className="mono"
                  value={pattern}
                  onChange={(e) => setPattern(e.target.value)}
                  aria-invalid={!!reErr}
                />
              </Field>
            ) : (
              <Field
                label="Description contains these words"
                req
                hint="Every word must appear, in any order. Case does not matter."
              >
                <Input
                  value={value}
                  onChange={(e) => setValue(e.target.value)}
                />
              </Field>
            )}
            <label className="row g2 t-sm">
              <Switch
                checked={advanced}
                onChange={setAdvanced}
                label="Advanced: a pattern"
              />
              Advanced: a pattern
            </label>
          </Fragment>
        ) : null}
        {kind === "amount" ? (
          <div className="split2">
            <Field label="From" error={minP.error}>
              <Input
                className="tnum"
                value={min}
                onChange={(e) => setMin(e.target.value)}
              />
            </Field>
            <Field
              label="To"
              error={
                maxP.error || (amountErr && !minP.error ? amountErr : null)
              }
            >
              <Input
                className="tnum"
                value={max}
                onChange={(e) => setMax(e.target.value)}
              />
            </Field>
            <Field label="And the counterparty is (optional)">
              <Input value={value} onChange={(e) => setValue(e.target.value)} />
            </Field>
          </div>
        ) : null}
        <div className="split2">
          <Field label="Classifies as" req>
            <Select value={cls} onChange={(e) => setCls(e.target.value as Cls)}>
              <option value="business">Business</option>
              <option value="personal">Personal</option>
              <option value="skipped">Skip (transfers)</option>
            </Select>
          </Field>
          {cls === "business" ? (
            <Field label="Category">
              <Select value={cat} onChange={(e) => setCat(e.target.value)}>
                <option value="">None</option>
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
          ) : (
            <span></span>
          )}
        </div>
        <Field
          label="Name"
          hint="How the rule is shown in lists and in each movement's history."
        >
          <Input value={name} onChange={(e) => setName(e.target.value)} />
        </Field>
        <Field
          label="Order"
          hint="Rules run in order; the first that matches decides."
        >
          <Select value={order} onChange={(e) => setOrder(e.target.value)}>
            {[...state.data.rules]
              .sort((a, b) => (a.priority ?? 0) - (b.priority ?? 0))
              .map((r, i) => (
                <option key={r.id} value={String(i + 1)}>
                  Before “{ruleText(r)}”
                </option>
              ))}
            <option value={String(state.data.rules.length + 1)}>
              Last, after your {plural(state.data.rules.length, "rule")}
            </option>
          </Select>
        </Field>
        <div className="card-wash">
          <label className="row g2 t-sm">
            <Checkbox
              checked={also}
              onChange={(e) => setAlso(e.target.checked)}
            />
            Matches {plural(cand.rows.length, "unclassified movement")} · also
            classify them now (staged)
          </label>
          {cand.skippedStaged ? (
            <span className="t-xs muted">
              {plural(cand.skippedStaged, "matching movement")} with unsaved
              changes left out.
            </span>
          ) : null}
          {cand.rows.length ? (
            <span className="t-xs muted wrapt">
              {cand.rows
                .slice(0, 4)
                .map((r) => r.description)
                .join(" · ")}
              {cand.rows.length > 4 ? " …" : ""}
            </span>
          ) : null}
        </div>
      </div>
    </Dialog>
  );
}

/* Columns, presets and density (R16: move up and move down). */
export function ColumnsDialog({ onClose }: { onClose: () => void }) {
  const [state, dispatch] = useStore();
  const { view } = state;
  const cols = view.order.filter((k) => k !== "select");
  const setView = (patch: Partial<View>) =>
    dispatch({
      type: "VIEW",
      patch: { ...patch, preset: patch.preset || "custom" },
    });
  const move = (k: string, d: number) => {
    const o = [...view.order];
    const i = o.indexOf(k);
    const j = i + d;
    if (j < 1 || j >= o.length) return;
    [o[i], o[j]] = [o[j]!, o[i]!];
    dispatch({ type: "VIEW", patch: { order: o } });
    announce(`${COL_LABEL[k]} moved ${d < 0 ? "up" : "down"}`);
  };
  return (
    <Dialog
      className="mid"
      onClose={onClose}
      title="Columns and density"
      desc="Your choice is kept on this computer only."
    >
      <div className="col g3">
        <Field label="Presets">
          <div className="chips">
            {Object.entries(PRESETS).map(([k, p]) => (
              <button
                key={k}
                type="button"
                className="btn pill"
                aria-pressed={view.preset === k}
                onClick={() =>
                  dispatch({
                    type: "VIEW",
                    patch: { preset: k, visible: p.cols },
                  })
                }
              >
                {p.label}
              </button>
            ))}
          </div>
        </Field>
        <Field label="Rows">
          <Seg
            size="sm"
            label="Row density"
            value={view.density}
            onChange={(v) =>
              dispatch({
                type: "VIEW",
                patch: { density: v as View["density"] },
              })
            }
            options={[
              { value: "compact", label: "Compact" },
              { value: "comfortable", label: "Comfortable" },
            ]}
          />
        </Field>
        <ul className="list-rows" aria-label="Columns">
          {cols.map((k, i) => (
            <li key={k}>
              <label className="row g2 f1">
                <Checkbox
                  checked={view.visible.includes(k)}
                  disabled={k === "amount" || k === "date"}
                  onChange={(e) =>
                    setView({
                      visible: e.target.checked
                        ? [...view.visible, k]
                        : view.visible.filter((x) => x !== k),
                    })
                  }
                />
                <span className="f1">{COL_LABEL[k]}</span>
                {STICKY.includes(k) ? (
                  <span className="t-xs muted">kept at the left</span>
                ) : null}
              </label>
              <IconButton
                icon="chevronUp"
                label={`Move ${COL_LABEL[k]} up`}
                disabled={i === 0 || STICKY.includes(k)}
                onClick={() => move(k, -1)}
              />
              <IconButton
                icon="chevronDown"
                label={`Move ${COL_LABEL[k]} down`}
                disabled={i === cols.length - 1 || STICKY.includes(k)}
                onClick={() => move(k, 1)}
              />
            </li>
          ))}
        </ul>
        <div>
          <Button
            size="sm"
            variant="ghost"
            icon="reset"
            onClick={() =>
              dispatch({
                type: "VIEW",
                patch: { widths: {}, order: DEFAULT_COLUMNS },
              })
            }
          >
            Reset widths and order
          </Button>
        </div>
      </div>
    </Dialog>
  );
}

/* The model's suggestions, one at a time (R5): read each, then approve
   the ones you agree with together. */
export function SuggestionsDialog({
  ids,
  onClose,
}: DialogProps["suggestions"] & { onClose: () => void }) {
  const [state, dispatch] = useStore();
  const page = usePage();
  const list = ids.flatMap((id) => {
    const row = state.data.byId[id];
    const s = row ? page.suggestionFor(row) : null;
    return row && s ? [{ row, s }] : [];
  });
  const [i, setI] = useState(0);
  const [read, setRead] = useState<Record<number, boolean>>({ 0: true });
  const [leave, setLeave] = useState<Record<number, boolean>>({});
  const [shares, setShares] = useState<Record<number, string>>({});
  const cur = list[i]!;
  const allRead = list.every((_, k) => read[k]);
  const go = (k: number) => {
    setI(k);
    setRead((r) => ({ ...r, [k]: true }));
  };
  const approveAll = () => {
    let n = 0,
      skipped = 0;
    list.forEach(({ row, s }, k) => {
      if (leave[k]) return;
      let sh = s.share;
      if (s.cls === "mixed" && sh == null) {
        const p = parsePercent(shares[k] || "", { label: "Business share" });
        if (p.error || p.empty) {
          skipped++;
          return;
        }
        sh = Number(p.value);
      }
      stageApproval(dispatch, row, s, sh);
      n++;
    });
    page.toast(
      `${plural(n, "approval")} staged · not saved${skipped ? ` · ${skipped} Mixed without a share left out` : ""}`,
    );
    onClose();
  };
  if (!list.length)
    return (
      <Dialog
        onClose={onClose}
        title="No suggestions"
        desc="The model had nothing to suggest for these movements."
        footer={<Button onClick={onClose}>Close</Button>}
      />
    );
  return (
    <Dialog
      className="mid"
      onClose={onClose}
      title="The model's suggestions"
      desc={`${plural(list.length, "suggestion")} from llm:local-medium, on this computer. Read each one; approve the ones you agree with together.`}
      footer={
        <>
          <span className="muted t-sm f1">
            {allRead
              ? `${list.length - Object.values(leave).filter(Boolean).length} to approve`
              : `Read ${Object.keys(read).length} of ${list.length}`}
          </span>
          <Button variant="ghost" onClick={onClose}>
            Close
          </Button>
          <Button
            disabled={!allRead}
            data-tip={allRead ? undefined : "Read every suggestion first"}
            onClick={approveAll}
          >
            Approve the ones I agree with
          </Button>
        </>
      }
    >
      <div className="col g3">
        <div className="row g2">
          <IconButton
            icon="back"
            label="Previous suggestion"
            disabled={i === 0}
            onClick={() => go(i - 1)}
          />
          <span className="t-sm tnum f1" aria-live="polite">
            {i + 1} of {list.length}
          </span>
          <IconButton
            icon="forward"
            label="Next suggestion"
            disabled={i === list.length - 1}
            onClick={() => go(i + 1)}
          />
        </div>
        <div className="card-raised">
          <div className="row g2 wrap">
            <b className="fw6 f1 wrapt">{cur.row.description}</b>
            <span className="tnum">
              {fmtMoney(cur.row.amount)} {cur.row.currency}
            </span>
          </div>
          <span className="muted t-sm">
            {cur.row.counterparty} · {fmtDateLong(effDate(cur.row))}
          </span>
          <dl className="kv">
            <dt>Classification</dt>
            <dd>
              {CLS[cur.s.cls].label}
              {cur.s.cls === "mixed"
                ? cur.s.share != null
                  ? " " + pct(cur.s.share)
                  : " · no share proposed"
                : ""}
            </dd>
            {cur.s.category ? (
              <>
                <dt>Category</dt>
                <dd>{CATEGORY_LABEL[cur.s.category]}</dd>
              </>
            ) : null}
            {cur.s.ivaCategory ? (
              <>
                <dt>IVA category</dt>
                <dd>{IVA_LABEL[cur.s.ivaCategory]}</dd>
              </>
            ) : null}
            <dt>Confidence</dt>
            <dd>
              <Meter value={cur.s.confidence} label="Model confidence" />{" "}
              {Math.round(cur.s.confidence * 100)}%
            </dd>
          </dl>
          <p className="t-sm">{cur.s.reason}</p>
          {cur.s.cls === "mixed" && cur.s.share == null ? (
            <Field
              label="Business share"
              req
              hint="Needed to approve a Mixed suggestion."
            >
              <Input
                size="sm"
                value={shares[i] || ""}
                placeholder="e.g. 50"
                onChange={(e) => setShares({ ...shares, [i]: e.target.value })}
              />
            </Field>
          ) : null}
          <label className="row g2 t-sm">
            <Checkbox
              checked={!!leave[i]}
              onChange={(e) => setLeave({ ...leave, [i]: e.target.checked })}
            />
            Leave this one out
          </label>
        </div>
        <p className="t-xs muted">
          Approving records each as “Model · llm:local-medium · approved by
          you”. IVA figures come from registry rates, never from the model.
        </p>
      </div>
    </Dialog>
  );
}

/* A stand-in for the operating system's own file dialog: the desktop
   receives a handle from it, never uploaded bytes, and shows file names. */
export const HOST_FILES: Record<string, { files: [string, string][] }> = {
  statement: {
    files: [
      ["bbva-movimientos-2026-10-b.xlsx", "38 KB"],
      ["n26-business-2026-10.csv", "12 KB"],
      ["caixabank-export.csv", "9 KB"],
      ["revolut-usd-2026-10.csv", "3 KB"],
      ["leeme.txt", "1 KB"],
    ],
  },
  book: {
    files: [
      ["libro-facturas-recibidas-2026-3T.xlsx", "22 KB"],
      ["libro-facturas-emitidas-2026.csv", "8 KB"],
    ],
  },
  document: {
    files: [
      ["ticket-plenoil-1015.jpg", "1.2 MB"],
      ["factura-correos-oct.pdf", "88 KB"],
      ["factura-domestika-lettering.pdf", "64 KB"],
    ],
  },
};
export function HostFileDialog({
  anchor,
  kind,
  multiple,
  onPick,
  onClose,
  folder,
}: {
  anchor: HTMLElement;
  kind: string;
  multiple?: boolean;
  onPick: (files: string[]) => void;
  onClose: () => void;
  folder?: boolean;
}) {
  const src =
    HOST_FILES[
      kind === "statement" || kind === "bank"
        ? "statement"
        : kind === "book"
          ? "book"
          : "document"
    ]!;
  const [sel, setSel] = useState<Record<string, boolean>>({});
  const picked = Object.keys(sel).filter((k) => sel[k]);
  return (
    <Popover
      anchor={anchor}
      onClose={onClose}
      width="25rem"
      label="Choose files"
      className="col g3"
    >
      <div className="row g2">
        <Icon name="folder" />
        <b className="fw6 f1">
          {folder
            ? "Choose a folder"
            : "Choose " + (multiple ? "files" : "a file")}
        </b>
        <span className="tag">system dialog, simulated</span>
      </div>
      {folder ? (
        <p className="t-sm">
          Every importable file directly in the folder is taken. Folders inside
          it are not read.
        </p>
      ) : (
        <ul className="list-rows">
          {src.files.map(([f, size]) => (
            <li key={f}>
              <label className="row g2 f1" style={{ cursor: "pointer" }}>
                <Checkbox
                  checked={!!sel[f]}
                  onChange={(e) =>
                    setSel(
                      multiple
                        ? { ...sel, [f]: e.target.checked }
                        : { [f]: e.target.checked },
                    )
                  }
                />
                <span className="f1 truncate">{f}</span>
                <span className="muted t-xs">{size}</span>
              </label>
            </li>
          ))}
        </ul>
      )}
      <div className="row g2" style={{ justifyContent: "flex-end" }}>
        <Button size="sm" variant="ghost" onClick={onClose}>
          Cancel
        </Button>
        <Button
          size="sm"
          disabled={!folder && !picked.length}
          onClick={() =>
            onPick(
              folder
                ? src.files.map(([f]) => f).filter((f) => !/\.txt$/.test(f))
                : picked,
            )
          }
        >
          {folder ? "Choose folder" : "Open"}
        </Button>
      </div>
    </Popover>
  );
}

/* ── Import: what, preview (writes nothing), apply exactly that. ─────── */
export const DETECTED: Record<string, string> = {
  bbva: "acc-02",
  n26: "acc-01",
  revolut: "acc-03",
};
export function ImportDialog({ onClose }: { onClose: () => void }) {
  const [state, dispatch] = useStore();
  const page = usePage();
  const [step, setStep] = useState(1);
  const [kind, setKind] = useState("bank");
  const [files, setFiles] = useState<string[]>([]);
  const [provider, setProvider] = useState("auto");
  const [only, setOnly] = useState<Period | null>(null);
  const [verify, setVerify] = useState(true);
  const [bookKind, setBookKind] = useState("");
  const [country, setCountry] = useState("");
  const [docDir, setDocDir] = useState("");
  const [chooser, setChooser] = useState<{
    el: HTMLElement;
    folder: boolean;
  } | null>(null);
  const [over, setOver] = useState(false);
  const [busy, setBusy] = useState(false);
  const [preview, setPreview] = useState<{ per: FilePreview[] } | null>(null);
  const [acct, setAcct] = useState<Record<string, string>>({});
  const [dupPop, setDupPop] = useState<{ el: HTMLElement; d: DupHit } | null>(
    null,
  );
  const [shown, setResult] = useState<ImportResult | null>(null);
  const result = shown ?? NO_RESULT;
  const [changed, setChanged] = useState(false);
  const headRef = useRef<HTMLHeadingElement>(null);
  useEffect(() => {
    requestAnimationFrame(() => headRef.current?.focus());
  }, [step]);
  const countryErr =
    kind === "book" && country && !/^[A-Za-z]{2}$/.test(country)
      ? `“${country}” is not a two-letter country code.`
      : null;
  const canPreview =
    files.length &&
    (kind !== "book" || (/^[A-Za-z]{2}$/.test(country) && bookKind)) &&
    (kind !== "documents" || docDir);
  async function doPreview() {
    setBusy(true);
    await sleep(1100);
    setBusy(false);
    if (kind === "bank") {
      const per = files.map((f): FilePreview => {
        const det = Object.keys(DETECTED).find((k) => f.startsWith(k));
        if (f.startsWith("bbva"))
          return {
            f,
            det: "acc-02",
            rows: 7,
            imp: 6,
            skip: 1,
            dups: [
              {
                row: "REPSOL E.S. PATERNA",
                amount: 6120,
                date: "2026-10-09",
                existing: state.data.dupA,
              },
            ],
            unmapped: ["Saldo", "Concepto ampliado"],
            diag: ["No movements between 13 and 14 Oct"],
          };
        if (f.startsWith("n26"))
          return {
            f,
            det: "acc-01",
            rows: 31,
            imp: 0,
            skip: 31,
            dups: [],
            unmapped: [],
            diag: [],
          };
        if (f.startsWith("revolut"))
          return {
            f,
            det: "acc-03",
            rows: 2,
            imp: 1,
            skip: 1,
            dups: [],
            unmapped: ["Fee"],
            diag: [],
          };
        if (f.startsWith("caixa"))
          return {
            f,
            refused: true,
            why: "Its rows name the account ES91 •••• 1234, which is not one of your registered accounts. Register it in Setup › Registers, then import it again.",
          };
        return {
          f,
          refused: true,
          why: det
            ? ""
            : "No movements could be read: the file is not a statement.",
        };
      });
      const a: Record<string, string> = {};
      per.forEach((p) => {
        if (p.det) a[p.f] = p.det;
      });
      setAcct(a);
      setPreview({ per });
    } else
      setPreview({
        per: files.map((f) => ({
          f,
          size: f.endsWith("xlsx") ? "22 KB" : "8 KB",
        })),
      });
    setStep(2);
  }
  const usable = preview?.per.filter((p) => !p.refused) || [];
  const newRows = usable.reduce((s, p) => s + (p.imp || 0), 0);
  const nothingNew = kind === "bank" && preview && newRows === 0;
  const needsAccount =
    kind === "bank" && usable.some((p) => p.imp && !acct[p.f]);
  async function doApply() {
    setBusy(true);
    await sleep(1300);
    setBusy(false);
    if (changed && kind === "bank") {
      setResult({
        ...NO_RESULT,
        refusedChanged: files.filter((f) => f.startsWith("bbva")),
      });
      setStep(3);
      return;
    }
    if (kind === "bank") {
      const batchId = "b-" + hashHex("import" + CLOCK, 10);
      const now = NOW();
      const add: NewRow[] = [];
      const mk = (
        date: string,
        amount: number,
        desc: string,
        cp: string,
        dir: Direction = "out",
        cls: Cls = "pending",
        acc: string | undefined = acct["bbva-movimientos-2026-10-b.xlsx"],
      ): NewRow => ({ date, amount, desc, cp, dir, cls, acc });
      if (files.some((f) => f.startsWith("bbva")))
        add.push(
          mk(
            "2026-10-15",
            465,
            "CORREOS ENVIO CERTIFICADO",
            "Sociedad Estatal Correos y Telégrafos SA",
          ),
          mk(
            "2026-10-16",
            3290,
            "AMAZON.ES MKTPLACE PEDIDO 408-221",
            "Amazon EU SARL",
          ),
          mk("2026-10-19", 5210, "PLENOIL GASOLINERA PATERNA", "Plenoil SL"),
          mk("2026-10-20", 2500, "BIZUM RECIBIDO LAURA", "Laura G.", "in"),
          mk(
            "2026-10-21",
            4137,
            "MERCADONA RUZAFA VALENCIA",
            "Mercadona SA",
            "out",
            "personal",
          ),
          mk(
            "2026-09-30",
            6120,
            "REPSOL E.S. PATERNA",
            "Repsol Comercial de Productos Petrolíferos SA",
          ),
        );
      if (files.some((f) => f.startsWith("revolut")))
        add.push({
          ...mk("2026-10-22", 1500, "REVOLUT PLAN FEE", "Revolut Bank UAB"),
          currency: "USD",
          acc: acct["revolut-usd-2026-10.csv"],
          fx: {
            rate: 0.9233,
            eur: 1385,
            source: "ECB reference rate",
            date: "2026-10-22",
          },
        });
      const added = usable.filter((p) => p.imp).map((p) => p.f);
      const batch: Batch = {
        id: batchId,
        file: added.join(", "),
        account: acct[added[0] ?? ""] ?? "",
        ingested: now.slice(0, 10),
        provider: "auto",
        format: "csv/xlsx",
        sha: hashHex(batchId),
        rows: add.length,
      };
      const ids = add.map((a, i) => hashHex(batchId + i + a.desc));
      dispatch({
        type: "DATA",
        fn: (d) => {
          const byId = { ...d.byId };
          const order = [...d.order];
          add.forEach((a, i) => {
            const id = ids[i]!;
            byId[id] = {
              id,
              providerId: "imp-" + hashHex(id, 8),
              booked: a.date,
              valueDate: null,
              amount: a.amount,
              currency: a.currency || "EUR",
              direction: a.dir,
              counterparty: a.cp,
              description: a.desc,
              cls: a.cls,
              share: null,
              category: null,
              ivaCategory: null,
              base: null,
              ivaRate: null,
              ivaAmount: null,
              recargo: null,
              irpf: null,
              usageRatio: null,
              counterpartyCountry: null,
              idState: null,
              sourceJurisdiction: null,
              account: a.acc || null,
              group: null,
              notes: "",
              lifecycle: "active",
              classifiedBy: a.cls === "personal" ? "rule:r-mercadona" : "auto",
              classifiedAt: a.cls === "personal" ? now : null,
              invoiceId: null,
              evidenceId: null,
              attachments: [],
              fx: a.fx || null,
              fxMissing: false,
              batch: batchId,
              prov: {
                file: a.currency
                  ? "revolut-usd-2026-10.csv"
                  : "bbva-movimientos-2026-10-b.xlsx",
                row: i + 2,
                provider: a.currency ? "Revolut (CSV)" : "BBVA (XLSX)",
                format: a.currency ? "csv" : "xlsx",
                ingested: now.slice(0, 10),
                sha: hashHex("bytes" + a.desc),
              },
              sealed: null,
              uses: [],
              suggestion: null,
              modelRejected: false,
              issue: a.desc.startsWith("REPSOL") ? "duplicate" : null,
              forceIssues: null,
              split: null,
              created: now,
              modified: now,
              history: [
                {
                  at: now,
                  what: `Imported from ${a.currency ? "revolut-usd-2026-10.csv" : "bbva-movimientos-2026-10-b.xlsx"}${a.desc.startsWith("REPSOL") ? ", flagged as a possible duplicate" : ""}`,
                  by: "Bank statement import",
                },
              ],
              remoteChange: false,
              classifiedHistory: [],
            };
            order.push(id);
          });
          order.sort((x, y) =>
            effDate(byId[x]!).localeCompare(effDate(byId[y]!)),
          );
          return { ...d, byId, order, batches: [...d.batches, batch] };
        },
      });
      const dates = add.map((a) => a.date).sort();
      setResult({
        ...NO_RESULT,
        imported: add.length,
        skipped: usable.reduce((s, p) => s + (p.skip || 0), 0),
        dups: 1,
        refused: (preview?.per ?? []).filter((p) => p.refused),
        batchId,
        span: [dates[0] ?? "", dates[dates.length - 1] ?? ""],
        ids,
      });
    } else if (kind === "book")
      setResult({
        ...NO_RESULT,
        created: 9,
        skippedDup: 2,
        refusedRows: [
          {
            row: 7,
            field: "Counterparty tax id",
            reason: "“B0000004” is not a valid tax id",
          },
          {
            row: 12,
            field: "Taxable base",
            reason: "“1.250” is ambiguous; write 1250 or 1.25",
          },
        ],
      });
    else
      setResult({ ...NO_RESULT, ingested: files.length, drafts: files.length });
    setStep(3);
  }
  const showImported = () => {
    const [a, b] = result.span;
    const q = (d: string) => d.slice(0, 4) + quarterOf(d);
    const period =
      q(a) === q(b)
        ? { year: +a.slice(0, 4), code: quarterOf(a) + "T" }
        : a.slice(0, 4) === b.slice(0, 4)
          ? { year: +a.slice(0, 4), code: "0A" }
          : { year: 2026, code: "ALL" };
    dispatch({
      type: "VIEW",
      patch: {
        filters: { ...EMPTY_FILTERS, batch: result.batchId ?? null },
        savedView: "custom",
        period,
        groupBy: "none",
      },
    });
    page.setSection("movements");
    onClose();
    setTimeout(() => page.focusFirstRow(), 120);
  };
  const stepTitle = [
    "What to import",
    "Preview: nothing is written yet",
    "Result",
  ][step - 1];
  const fileWord = (k: number) => (k === 1 ? "this file" : `these ${k} files`);
  return (
    <Dialog
      className="wide"
      placement="top"
      onClose={onClose}
      title="Import"
      desc="Bank statements, invoice books and documents come in from files on this computer. A preview writes nothing."
      footer={
        step === 1 ? (
          <>
            <Button variant="ghost" onClick={onClose}>
              Cancel
            </Button>
            <Button disabled={!canPreview} pending={busy} onClick={doPreview}>
              Preview
            </Button>
          </>
        ) : step === 2 ? (
          <>
            <Button variant="ghost" onClick={() => setStep(1)}>
              Back
            </Button>
            <span className="f1 t-sm muted">
              {needsAccount ? "Choose the account for each file." : ""}
            </span>
            <Button
              pending={busy}
              disabled={
                kind === "bank" &&
                (!usable.length || nothingNew || needsAccount)
              }
              onClick={doApply}
            >
              {kind === "bank"
                ? nothingNew
                  ? "Nothing new to import"
                  : `Import exactly ${fileWord(usable.filter((p) => p.imp).length)}`
                : kind === "book"
                  ? "Import the book"
                  : `Add ${plural(files.length, "document")}`}
            </Button>
          </>
        ) : (
          <>
            {result.batchId ? (
              <Button variant="outline" onClick={showImported}>
                Show imported movements
              </Button>
            ) : null}
            {result.refusedChanged ? (
              <Button
                variant="outline"
                onClick={() => {
                  setChanged(false);
                  setResult(null);
                  setStep(1);
                }}
              >
                Preview again
              </Button>
            ) : null}
            {kind === "documents" && result.drafts ? (
              <Button
                variant="outline"
                onClick={() => {
                  page.setSection("documents");
                  onClose();
                }}
              >
                Review the drafts
              </Button>
            ) : null}
            <Button onClick={onClose}>Done</Button>
          </>
        )
      }
    >
      <div className="col g4">
        <ol className="steps" aria-label="Steps">
          {["What", "Preview", "Result"].map((s, i) => (
            <li
              key={s}
              className={cx(
                "row g1",
                step === i + 1 && "on",
                step > i + 1 && "done",
              )}
              aria-current={step === i + 1 ? "step" : undefined}
            >
              <span className="stepn">
                {step > i + 1 ? <Icon name="tick" size="xs" /> : i + 1}
              </span>
              {s}
              {i < 2 ? (
                <Icon name="forward" size="xs" className="muted" />
              ) : null}
            </li>
          ))}
        </ol>
        <h3 ref={headRef} tabIndex={-1} className="sec-title">
          {stepTitle}
        </h3>
        {step === 1 ? (
          <Fragment>
            <Seg
              label="What to import"
              value={kind}
              onChange={(v) => {
                setKind(v);
                setFiles([]);
              }}
              options={[
                { value: "bank", label: "Bank statement" },
                { value: "book", label: "Invoice book" },
                { value: "documents", label: "Documents" },
              ]}
            />
            <div
              className={cx("dropzone", over && "over")}
              onDragOver={(e) => {
                e.preventDefault();
                setOver(true);
              }}
              onDragLeave={() => setOver(false)}
              onDrop={(e) => {
                e.preventDefault();
                setOver(false);
                const fs = [...e.dataTransfer.files].map((f) => f.name);
                if (fs.length) setFiles(fs);
              }}
            >
              <Icon name="upload" size="lg" />
              <span>
                Drop{" "}
                {kind === "bank"
                  ? "statement files or a folder"
                  : kind === "book"
                    ? "one invoice book (CSV or XLSX)"
                    : "PDFs or images, or a folder"}{" "}
                here
              </span>
              <div className="row g2">
                <Button
                  size="sm"
                  variant="outline"
                  onClick={(e) =>
                    setChooser({ el: e.currentTarget, folder: false })
                  }
                >
                  Choose {kind === "book" ? "a file" : "files"}…
                </Button>
                {kind !== "book" ? (
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={(e) =>
                      setChooser({ el: e.currentTarget, folder: true })
                    }
                  >
                    Choose a folder…
                  </Button>
                ) : null}
              </div>
              <span className="t-xs muted">
                {kind === "bank"
                  ? "CSV, XLSX, XLS, OFX, QFX or an N26 PDF · up to 128 files and 4,096 rows at once · folders inside a folder are not read"
                  : kind === "book"
                    ? "CSV, TSV, XLSX, XLSM or XLS"
                    : "PDF, JPG, PNG, HEIC, or Facturae / UBL / CII XML · folders inside a folder are not read"}
              </span>
            </div>
            {files.length ? (
              <div className="col g1">
                {files.map((f) => (
                  <div key={f} className="filechip">
                    <Icon
                      name={
                        /\.(jpe?g|png|heic)$/i.test(f)
                          ? "image"
                          : /\.pdf$/i.test(f)
                            ? "page"
                            : "sheet"
                      }
                    />
                    <span className="f1 truncate">{f}</span>
                    <IconButton
                      icon="close"
                      label={"Remove " + f}
                      onClick={() => setFiles(files.filter((x) => x !== f))}
                    />
                  </div>
                ))}
              </div>
            ) : null}
            {kind === "bank" ? (
              <div className="split2">
                <Field
                  label="Provider"
                  hint="Detection reads the first bytes of each file."
                >
                  <Select
                    value={provider}
                    onChange={(e) => setProvider(e.target.value)}
                  >
                    {PROVIDERS.map(([k, l]) => (
                      <option key={k} value={k}>
                        {l}
                      </option>
                    ))}
                  </Select>
                </Field>
                <div className="field">
                  <label className="row g2 t-sm">
                    <Switch
                      checked={!!only}
                      onChange={(v) =>
                        setOnly(
                          v
                            ? {
                                ...state.view.period,
                                code:
                                  state.view.period.code === "ALL"
                                    ? "0A"
                                    : state.view.period.code,
                                year:
                                  state.view.period.code === "ALL"
                                    ? +TODAY.slice(0, 4)
                                    : state.view.period.year,
                              }
                            : null,
                        )
                      }
                      label="Only movements dated in a period"
                    />
                    Only movements dated in a period
                  </label>
                  {only ? (
                    <PeriodControl
                      label="Import period"
                      value={only}
                      allowAll={false}
                      onChange={setOnly}
                    />
                  ) : (
                    <span className="field-hint">
                      Any date. Rows outside a chosen period are left out and
                      counted.
                    </span>
                  )}
                </div>
                <label className="row g2 t-sm">
                  <Switch
                    checked={verify}
                    onChange={setVerify}
                    label="Check the running balance against the statement"
                  />
                  Check the running balance against the statement
                </label>
                <span className="t-sm muted">
                  The account is chosen per file in the preview.
                </span>
              </div>
            ) : kind === "book" ? (
              <div className="split2">
                <Field label="Invoices in the book" req>
                  <Seg
                    label="Invoice kind"
                    value={bookKind}
                    onChange={setBookKind}
                    options={[
                      { value: "received", label: "Invoices I received" },
                      { value: "issued", label: "Invoices I issued" },
                    ]}
                  />
                </Field>
                <Field
                  label="Counterparty country"
                  req
                  hint="Two letters, used when the book has no country column. There is no default."
                  error={countryErr}
                >
                  <Input
                    value={country}
                    maxLength={2}
                    placeholder="e.g. ES"
                    onChange={(e) => setCountry(e.target.value.toUpperCase())}
                    aria-invalid={!!countryErr}
                  />
                </Field>
              </div>
            ) : (
              <Field label="These documents are" req>
                <Seg
                  label="Document direction"
                  value={docDir}
                  onChange={setDocDir}
                  options={[
                    { value: "received", label: "Invoices I received" },
                    { value: "issued", label: "Invoices I issued" },
                  ]}
                />
              </Field>
            )}
            {chooser ? (
              <HostFileDialog
                anchor={chooser.el}
                folder={chooser.folder}
                kind={
                  kind === "bank"
                    ? "statement"
                    : kind === "book"
                      ? "book"
                      : "document"
                }
                multiple={kind !== "book"}
                onClose={() => setChooser(null)}
                onPick={(fs) => {
                  setFiles(fs);
                  setChooser(null);
                }}
              />
            ) : null}
          </Fragment>
        ) : step === 2 ? (
          <Fragment>
            <Alert icon="info">
              Importing uses exactly these files. A file that changes on disk in
              between is refused and must be previewed again.
            </Alert>
            {kind === "bank" ? (
              <Fragment>
                {nothingNew ? (
                  <Alert tone="success" title="Nothing new to import">
                    Every row is already in the ledger.
                  </Alert>
                ) : null}
                <div className="row g4 wrap t-sm">
                  <span>
                    Rows{" "}
                    <b className="tnum">
                      {(preview?.per ?? []).reduce(
                        (s, p) => s + (p.rows || 0),
                        0,
                      )}
                    </b>
                  </span>
                  <span>
                    New <b className="tnum">{newRows}</b>
                  </span>
                  <span>
                    Already in the ledger{" "}
                    <b className="tnum">
                      {(preview?.per ?? []).reduce(
                        (s, p) => s + (p.skip || 0),
                        0,
                      )}
                    </b>
                  </span>
                  <span>
                    Possible duplicates{" "}
                    <b className="tnum">
                      {(preview?.per ?? []).reduce(
                        (s, p) => s + (p.dups?.length || 0),
                        0,
                      )}
                    </b>
                  </span>
                  <span>
                    Refused files{" "}
                    <b className="tnum">
                      {(preview?.per ?? []).filter((p) => p.refused).length}
                    </b>
                  </span>
                </div>
                {(preview?.per ?? []).map((p) => (
                  <div
                    key={p.f}
                    className={cx("filechip", p.refused && "refused")}
                    style={{ alignItems: "flex-start" }}
                  >
                    <Icon
                      name={p.refused ? "refused" : "sheet"}
                      className={p.refused ? "danger-t" : ""}
                    />
                    <div className="f1 col g1">
                      <b className="fw5 wrapt">{p.f}</b>
                      {p.refused ? (
                        <span className="t-sm">Refused. {p.why}</span>
                      ) : (
                        <span className="t-sm muted tnum">
                          {p.rows} rows · {p.imp} new · {p.skip} already in the
                          ledger{p.skip === p.rows ? " (imported before)" : ""}
                        </span>
                      )}
                      {!p.refused && p.imp ? (
                        <div
                          className="row g2 wrap"
                          style={{ alignItems: "center" }}
                        >
                          <span className="t-sm">Account</span>
                          <div style={{ width: "calc(var(--spacing) * 64)" }}>
                            <Select
                              size="sm"
                              aria-label={"Account for " + p.f}
                              value={acct[p.f] || ""}
                              onChange={(e) =>
                                setAcct({ ...acct, [p.f]: e.target.value })
                              }
                            >
                              <option value="" disabled>
                                Choose the account…
                              </option>
                              {state.data.accounts.map((a) => (
                                <option key={a.id} value={a.id}>
                                  {a.label} · {a.iban.slice(-4)}
                                </option>
                              ))}
                              <option value="__rows">
                                Decide per row from the file
                              </option>
                            </Select>
                          </div>
                          {p.det && acct[p.f] === p.det ? (
                            <span className="t-xs muted">
                              detected from the file
                            </span>
                          ) : null}
                        </div>
                      ) : null}
                      {p.dups?.map((d) => (
                        <span key={d.row} className="t-sm row g1 wrap">
                          <Icon name="alert" size="xs" className="warn-t" />
                          Possible duplicate: {d.row} · {fmtMoney(d.amount)} ·{" "}
                          {fmtDateLong(d.date)}. It will be imported and
                          flagged, so you can archive it or keep both.{" "}
                          <Button
                            variant="link"
                            size="xs"
                            aria-expanded={!!dupPop}
                            onClick={(e) =>
                              setDupPop({ el: e.currentTarget, d })
                            }
                          >
                            Compare with the existing one
                          </Button>
                        </span>
                      ))}
                      {p.unmapped?.length ? (
                        <span className="t-sm muted">
                          Columns not used: {p.unmapped.join(", ")}
                        </span>
                      ) : null}
                      {p.diag?.map((x) => (
                        <span key={x} className="t-sm muted">
                          Note: {x}
                        </span>
                      ))}
                    </div>
                  </div>
                ))}
                {dupPop
                  ? (() => {
                      const ex = state.data.byId[dupPop.d.existing];
                      return (
                        <Popover
                          anchor={dupPop.el}
                          onClose={() => setDupPop(null)}
                          width="26rem"
                          label="Possible duplicate"
                          className="col g2"
                        >
                          <b className="fw6">Possible duplicate</b>
                          <div className="split2 t-sm">
                            <div className="card-wash">
                              <b className="fw5">In this file</b>
                              <span>{dupPop.d.row}</span>
                              <span className="tnum">
                                {fmtMoney(dupPop.d.amount)} ·{" "}
                                {fmtDateLong(dupPop.d.date)}
                              </span>
                              <span className="muted">BBVA statement</span>
                            </div>
                            {ex ? (
                              <div className="card-wash">
                                <b className="fw5">Already in the ledger</b>
                                <span>{ex.description}</span>
                                <span className="tnum">
                                  {fmtMoney(ex.amount)} ·{" "}
                                  {fmtDateLong(effDate(ex))}
                                </span>
                                <span className="muted">{ex.prov.file}</span>
                              </div>
                            ) : null}
                          </div>
                          <p className="t-xs muted">
                            Both stay after the import; the new one carries a
                            “Possible duplicate” marker with Archive as
                            duplicate and Keep both.
                          </p>
                        </Popover>
                      );
                    })()
                  : null}
                <button
                  type="button"
                  className="btn link xs muted"
                  style={{ alignSelf: "flex-start" }}
                  onClick={() => setChanged(!changed)}
                >
                  {changed
                    ? "Prototype: the BBVA file will have changed on disk (click to undo)"
                    : "Prototype: simulate the BBVA file changing on disk before import"}
                </button>
                <details className="tech">
                  <summary>Technical details</summary>
                  <ul className="list-rows mono t-xs">
                    {(preview?.per ?? []).map((p) => (
                      <li key={p.f}>
                        {p.f} · sha256 {hashHex("bytes" + p.f).slice(0, 16)}…
                      </li>
                    ))}
                  </ul>
                </details>
              </Fragment>
            ) : kind === "book" ? (
              <Fragment>
                {(preview?.per ?? []).map((p) => (
                  <div key={p.f} className="filechip">
                    <Icon name="sheet" />
                    <span className="f1">{p.f}</span>
                    <span className="muted t-xs">{p.size}</span>
                  </div>
                ))}
                <Alert tone="warning" title="Invoice books have no dry run">
                  Rows are checked as they are created. Rows that fail are
                  listed afterwards with their row number and reason; the rest
                  are kept.{" "}
                  {bookKind === "received"
                    ? "Invoices received"
                    : "Invoices issued"}
                  , country {country}.
                </Alert>
              </Fragment>
            ) : (
              <Fragment>
                {(preview?.per ?? []).map((p) => (
                  <div key={p.f} className="filechip">
                    <Icon
                      name={/\.(jpe?g|png)$/i.test(p.f) ? "image" : "page"}
                    />
                    <span className="f1">{p.f}</span>
                  </div>
                ))}
                <p className="t-sm muted">
                  Each document becomes evidence and a draft to review in
                  Documents. Reading happens on this computer; nothing is sent
                  off it.
                </p>
              </Fragment>
            )}
          </Fragment>
        ) : (
          <Fragment>
            {result.refusedChanged ? (
              <Alert tone="danger" icon="refused" title="Nothing was imported">
                {result.refusedChanged.join(", ")} changed on disk after the
                preview. Preview it again, then import.
              </Alert>
            ) : kind === "bank" ? (
              <Fragment>
                <Alert
                  tone="success"
                  title={`${plural(result.imported, "movement")} imported`}
                >
                  {result.skipped} already in the ledger were skipped.{" "}
                  {plural(result.dups, "possible duplicate")} imported and
                  flagged for you to check. They are dated{" "}
                  {fmtDateLong(result.span[0])} to {fmtDateLong(result.span[1])}
                  .
                </Alert>
                {result.refused.map((p) => (
                  <div key={p.f} className="filechip refused">
                    <Icon name="refused" className="danger-t" />
                    <span className="f1">{p.f}</span>
                    <span className="t-sm">Not imported</span>
                  </div>
                ))}
              </Fragment>
            ) : kind === "book" ? (
              <Fragment>
                <Alert
                  tone="success"
                  title={`${result.created} invoices created`}
                >
                  {result.skippedDup} were already in the catalogue and were
                  skipped.
                </Alert>
                <section className="sec">
                  <h3 className="sec-title">Refused rows</h3>
                  <DataTable
                    label="Refused rows"
                    rowKey={(r) => String(r.row)}
                    rows={result.refusedRows}
                    columns={[
                      { key: "row", label: "Row", num: true, width: 60 },
                      { key: "field", label: "Field" },
                      { key: "reason", label: "Reason", wrap: true },
                    ]}
                  />
                </section>
              </Fragment>
            ) : (
              <Alert
                tone="success"
                title={`${plural(result.ingested, "document")} added`}
              >
                {plural(result.drafts, "draft")} waiting for review in
                Documents.
              </Alert>
            )}
          </Fragment>
        )}
      </div>
    </Dialog>
  );
}

/* ── Export (R12): destination last, file names only. ────────────────── */
export function ExportDialog({
  onClose,
  selection,
}: { onClose: () => void } & NonNullable<DialogProps["export"]>) {
  const [state] = useStore();
  const page = usePage();
  const [fmt, setFmtState] = useState("csv");
  const [period, setPeriodState] = useState<Period>(
    state.view.period.code === "ALL"
      ? { year: +TODAY.slice(0, 4), code: "0A" }
      : state.view.period,
  );
  const [inactive, setInactiveState] = useState(false);
  const [dest, setDest] = useState<string | null>(null);
  const [saveOpen, setSaveOpen] = useState<HTMLElement | null>(null);
  const [name, setName] = useState("");
  const [confirmOverwrite, setConfirmOverwrite] = useState(false);
  const [without, setWithout] = useState(false);
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState<{ count: number; dest: string } | null>(
    null,
  );
  const setFmt = (v: string) => {
    setFmtState(v);
    setDest(null);
  };
  const setPeriod = (v: Period) => {
    setPeriodState(v);
    setDest(null);
  };
  const setInactive = (v: boolean) => {
    setInactiveState(v);
  };
  const existing = [
    "cadrumo-ledger-2026-3T.csv",
    "cadrumo-ledger-2026-4T.xlsx",
  ];
  const fileName = `cadrumo-ledger-${period.year}-${period.code}.${fmt}`;
  const win = periodRange(period) ?? ["", ""];
  const inWin = Object.values(state.data.byId).filter((r) => {
    const d = effDate(r);
    return d >= win[0] && d <= win[1];
  });
  const count = inWin.filter(
    (r) => inactive || r.lifecycle === "active",
  ).length;
  const leftOut = inWin.length - count;
  const staged = trayCounts(state).total;
  const notReady = inWin.filter(
    (r) => r.lifecycle === "active" && checkIssues(r, state.check).length,
  ).length;
  const invoicesTsv = () => {
    const inv = state.data.invoices.filter(
      (i) => i.date >= win[0] && i.date <= win[1],
    );
    const text = [
      [
        "Number",
        "Kind",
        "Date",
        "Counterparty",
        "Tax id",
        "Total",
        "Currency",
        "Payment",
      ].join("\t"),
      ...inv.map((i) =>
        [
          i.number,
          i.kind,
          i.date,
          i.counterparty,
          i.nif || "",
          canon(i.total),
          i.currency,
          PAYMENT[i.payment],
        ]
          .map(tsvEscape)
          .join("\t"),
      ),
    ].join("\n");
    copyText(text);
    page.toast(`Copied ${plural(inv.length, "invoice")} as TSV`);
  };
  return (
    <Dialog
      onClose={onClose}
      className="mid"
      title="Export the ledger"
      desc="A local file for you or your gestor. Nothing is sent to the AEAT."
      footer={
        done ? (
          <>
            <Button
              variant="outline"
              icon="folder"
              onClick={() => page.toast("Opened the folder (simulated)")}
            >
              Show in folder
            </Button>
            <Button onClick={onClose}>Done</Button>
          </>
        ) : (
          <>
            <Button variant="ghost" onClick={onClose}>
              Cancel
            </Button>
            <Button
              disabled={!dest || (!!staged && !without)}
              pending={busy}
              onClick={async () => {
                setBusy(true);
                await sleep(1000);
                setBusy(false);
                setDone({ count, dest: dest ?? "" });
              }}
            >
              Export {plural(count, "movement")}
            </Button>
          </>
        )
      }
    >
      {done ? (
        <Alert tone="success" title="Exported">
          {plural(done.count, "movement")} written to {done.dest}.
        </Alert>
      ) : (
        <div className="col g4">
          {selection?.length ? (
            <Alert
              icon="info"
              title={`${plural(selection.length, "movement")} selected`}
              action={
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => page.copyRows(selection)}
                >
                  Copy as TSV
                </Button>
              }
            >
              The ledger exports whole periods. To take just the selection to a
              spreadsheet, copy it as TSV.
            </Alert>
          ) : null}
          <Field label="Format">
            <Seg
              label="Format"
              value={fmt}
              onChange={setFmt}
              options={[
                { value: "csv", label: "CSV" },
                { value: "jsonl", label: "JSONL" },
                { value: "xlsx", label: "XLSX" },
              ]}
            />
          </Field>
          <div className="field">
            <span className="field-label">Period</span>
            <PeriodControl
              label="Export period"
              value={period}
              allowAll={false}
              onChange={setPeriod}
            />
          </div>
          <label className="row g2 t-sm">
            <Switch
              checked={inactive}
              onChange={setInactive}
              label="Include archived and set-aside movements"
            />
            Include archived and set-aside movements
          </label>
          <p className="t-sm muted">
            {plural(count, "movement")} in {periodLabel(period)}
            {leftOut
              ? `; ${leftOut} archived, set aside or split are left out`
              : ""}
            .
          </p>
          {notReady ? (
            <Alert
              tone="warning"
              title={`${periodShort(period)} is not ready for calculation`}
            >
              {plural(notReady, "movement")} still need fixing. The file shows
              what the ledger holds now.
            </Alert>
          ) : null}
          {staged ? (
            <Alert
              tone="warning"
              title={`${plural(staged, "unsaved change")} not in this file`}
            >
              The export reads what is saved.
              <div className="row g2" style={{ marginTop: "var(--spacing)" }}>
                <Button
                  size="xs"
                  onClick={() => {
                    onClose();
                    page.openDialog("review");
                  }}
                >
                  Review and save
                </Button>
                <Button
                  size="xs"
                  variant="outline"
                  aria-pressed={without}
                  onClick={() => setWithout(!without)}
                >
                  Export without them
                </Button>
              </div>
            </Alert>
          ) : null}
          <div className="row g2">
            <Button size="sm" variant="ghost" icon="copy" onClick={invoicesTsv}>
              Also copy invoices (TSV)
            </Button>
          </div>
          <Field
            label="Save as"
            hint="Chosen last, in the system's save dialog. Changing the format or period clears it."
          >
            <div className="row g2">
              <Input
                readOnly
                value={dest || ""}
                placeholder="No file chosen"
                className="f1"
              />
              <Button
                variant="outline"
                onClick={(e) => {
                  setName(fileName);
                  setSaveOpen(e.currentTarget);
                }}
              >
                Choose…
              </Button>
            </div>
          </Field>
        </div>
      )}
      {saveOpen ? (
        <Popover
          anchor={saveOpen}
          onClose={() => {
            setSaveOpen(null);
            setConfirmOverwrite(false);
          }}
          width="24rem"
          label="Save as"
          className="col g3"
        >
          <div className="row g2">
            <Icon name="folder" />
            <b className="fw6 f1">Save as</b>
            <span className="tag">system dialog, simulated</span>
          </div>
          <ul className="list-rows t-sm">
            {existing.map((f) => (
              <li key={f}>
                <Icon name="sheet" size="xs" />
                {f}
              </li>
            ))}
          </ul>
          <Field label="File name">
            <Input
              size="sm"
              value={name}
              onChange={(e) => {
                setName(e.target.value);
                setConfirmOverwrite(false);
              }}
            />
          </Field>
          {confirmOverwrite ? (
            <Alert tone="warning" title={`${name} already exists`}>
              Replace it? The export overwrites the whole file.
            </Alert>
          ) : null}
          <div className="row g2" style={{ justifyContent: "flex-end" }}>
            <Button size="sm" variant="ghost" onClick={() => setSaveOpen(null)}>
              Cancel
            </Button>
            <Button
              size="sm"
              variant={confirmOverwrite ? "destructive" : "primary"}
              disabled={!name.trim()}
              onClick={() => {
                if (existing.includes(name.trim()) && !confirmOverwrite) {
                  setConfirmOverwrite(true);
                  return;
                }
                setDest(name.trim());
                setSaveOpen(null);
                setConfirmOverwrite(false);
              }}
            >
              {confirmOverwrite ? "Replace" : "Save"}
            </Button>
          </div>
        </Popover>
      ) : null}
    </Dialog>
  );
}

/* ── Shortcuts sheet. ────────────────────────────────────────────────── */
export const SHORTCUTS: [string, [string, string][]][] = [
  [
    "Move",
    [
      ["↑ ↓ ← →", "Move between cells"],
      ["↑ on the first row", "Reach the column headers"],
      ["Home / End", "First or last column"],
      ["Ctrl+Home / Ctrl+End", "First or last row"],
      ["PageUp / PageDown", "A screen up or down"],
      ["Tab", "Leave the grid"],
      ["N", "Next readiness issue"],
      ["/", "Search"],
    ],
  ],
  [
    "Select",
    [
      ["Space", "Select or clear the row"],
      ["Shift+↑ ↓ ← →", "Extend the range"],
      ["Ctrl+A", "Select every visible row"],
      ["Ctrl+click / Shift+click", "Add one, or a run"],
      ["B / P / M", "Business, Personal or Mixed for the selection"],
      ["Esc", "Shrink the range, then the selection"],
    ],
  ],
  [
    "Edit (staged until you save)",
    [
      ["Enter / F2", "Edit the cell"],
      ["Type", "Replace the cell's value"],
      ["Enter / Tab", "Keep the edit and move on"],
      ["Esc", "Cancel the edit"],
      ["Delete", "Clear optional cells"],
      ["Ctrl+D", "Fill down the range"],
      ["Ctrl+C / Ctrl+V", "Copy or paste TSV"],
      ["Ctrl+Alt+Z", "Revert the cell"],
      ["Ctrl+Z / Ctrl+Shift+Z", "Undo or redo"],
    ],
  ],
  [
    "Headers",
    [
      ["Enter / Space", "Sort by the column"],
      ["Ctrl+← →", "Move the column"],
      ["Alt+← →", "Make it narrower or wider"],
    ],
  ],
  [
    "Page",
    [
      ["Ctrl+Enter", "Review and save"],
      ["Alt+I", "Show or hide the inspector"],
      ["Shift+F10 / Menu key", "Actions for the row"],
      ["?", "This sheet"],
    ],
  ],
];
export function ShortcutsDialog({ onClose }: { onClose: () => void }) {
  return (
    <Dialog
      className="wide"
      onClose={onClose}
      title="Keyboard shortcuts"
      desc="The grid works without a mouse. The window keeps its own shortcuts (Ctrl+K, Ctrl+, F6, Ctrl+Shift+letters); this page never takes them."
    >
      <div className="keys-grid">
        {SHORTCUTS.map(([g, list]) => (
          <section key={g} className="sec">
            <h3 className="sec-title">{g}</h3>
            <dl>
              {list.map(([k, d]) => (
                <Fragment key={k}>
                  <dt>
                    {k.includes(" on ") ? (
                      <span className="t-sm">{k}</span>
                    ) : (
                      k.split(" / ").map((c, i) => (
                        <Fragment key={i}>
                          {i ? <span className="muted t-xs">or</span> : null}
                          <Keys chord={c} />
                        </Fragment>
                      ))
                    )}
                  </dt>
                  <dd>{d}</dd>
                </Fragment>
              ))}
            </dl>
          </section>
        ))}
      </div>
    </Dialog>
  );
}

/* ── The window's palette, as the shell shows it (R16): the Ledger page
   registers its actions; the page binds no Ctrl+K of its own. ─────── */
export type PaletteAction = {
  id: string;
  group: string;
  label: string;
  icon?: IconName;
  shortcut?: string;
  disabled?: string | null;
  hidden?: boolean;
  run: (arg?: string | Period) => void;
};
export function Palette({
  onClose,
  actions,
}: {
  onClose: () => void;
  actions: PaletteAction[];
}) {
  const [q, setQ] = useState("");
  const [hl, setHl] = useState(0);
  const idRef = useRef<HTMLDivElement>(null);
  const t = q.trim().toLowerCase();
  const jump = /^[0-9a-f]{4,}$/.test(t)
    ? actions.find((a) => a.id === "jump-id")
    : null;
  const gm = t.match(/^(\d{4})(?:\s*(0a|[1-4]t|0[1-9]|1[0-2]))?$/);
  const goto =
    gm && yearOk(+gm[1]!) ? actions.find((a) => a.id === "goto") : null;
  const gp: Period | null =
    goto && gm
      ? { year: +gm[1]!, code: gm[2] ? gm[2].toUpperCase() : "0A" }
      : null;
  const list = (
    jump && !goto
      ? [
          {
            ...jump,
            label: `Go to the movement whose id starts ${t}`,
            run: () => jump.run(t),
          },
        ]
      : []
  )
    .concat(
      goto
        ? [
            {
              ...goto,
              label: `Go to ${periodShort(gp!)}`,
              run: () => goto.run(gp!),
            },
          ]
        : [],
    )
    .concat(
      actions.filter(
        (a) =>
          !a.hidden &&
          a.id !== "jump-id" &&
          (!t ||
            a.label.toLowerCase().includes(t) ||
            (a.group || "").toLowerCase().includes(t)),
      ),
    );
  useEffect(() => setHl(0), [q]);
  useEffect(() => {
    idRef.current
      ?.querySelector(`[data-i="${hl}"]`)
      ?.scrollIntoView({ block: "nearest" });
  }, [hl]);
  const lid = useId();
  let last: string | null = null;
  return (
    <Overlay>
      <Fragment>
        <div className="scrim" onClick={onClose}></div>
        <div
          className="palette"
          role="dialog"
          aria-modal="true"
          aria-label="Search and commands"
          onKeyDown={(e) => {
            if (e.key === "Escape") {
              e.stopPropagation();
              onClose();
            } else if (e.key === "ArrowDown") {
              e.preventDefault();
              setHl((h) => Math.min(list.length - 1, h + 1));
            } else if (e.key === "ArrowUp") {
              e.preventDefault();
              setHl((h) => Math.max(0, h - 1));
            } else if (e.key === "Enter") {
              e.preventDefault();
              const a = list[hl];
              if (a && !a.disabled) {
                onClose();
                setTimeout(() => a.run(), 0);
              }
            }
          }}
        >
          <div className="palette-input">
            <Icon name="search" size="lg" />
            <input
              autoFocus
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Search commands, or paste a movement id"
              aria-label="Search commands"
              role="combobox"
              aria-expanded="true"
              aria-controls={lid}
              aria-activedescendant={list[hl] ? lid + "-" + hl : undefined}
            />
            <Kbd>Esc</Kbd>
          </div>
          <div
            className="palette-list"
            ref={idRef}
            role="listbox"
            id={lid}
            aria-label="Commands"
            tabIndex={0}
          >
            {list.length ? (
              list.map((a, i) => {
                const head =
                  a.group !== last
                    ? ((last = a.group),
                      (
                        <div className="palette-group" role="presentation">
                          {a.group}
                        </div>
                      ))
                    : null;
                return (
                  <Fragment key={a.id + i}>
                    {head}
                    <div
                      id={lid + "-" + i}
                      data-i={i}
                      role="option"
                      aria-selected={i === hl}
                      aria-disabled={a.disabled ? "true" : undefined}
                      className="palette-item"
                      data-hl={i === hl}
                      onPointerMove={() => setHl(i)}
                      onClick={() => {
                        if (a.disabled) return;
                        onClose();
                        setTimeout(() => a.run(), 0);
                      }}
                    >
                      <Icon name={a.icon || "arrow"} />
                      <span className="f1">{a.label}</span>
                      {a.disabled ? (
                        <span className="t-xs muted">{a.disabled}</span>
                      ) : null}
                      {a.shortcut ? <Keys chord={a.shortcut} /> : null}
                    </div>
                  </Fragment>
                );
              })
            ) : (
              <div className="combo-empty">No command matches “{q}”.</div>
            )}
          </div>
          <div
            className="window-note"
            style={{ justifyContent: "flex-start", paddingInline: "1rem" }}
          >
            The window's palette. While the Ledger page is open it lists the
            page's commands with the window's own.
          </div>
        </div>
      </Fragment>
    </Overlay>
  );
}
