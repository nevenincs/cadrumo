import {
  useState,
  useEffect,
  useRef,
  useLayoutEffect,
  useEffectEvent,
  useContext,
  createContext,
  useId,
  Fragment,
  type PointerEvent,
  type ReactNode,
} from "react";
import { Icon } from "./Icon";
import { usePage } from "./page";
import type {
  ApprovalFields,
  Cls,
  Doc,
  Draft,
  Invoice,
  Pair,
  Movement,
  Option,
  StagedAction,
  State,
  Suggestion,
  Value,
} from "./types";
import type { Action, StageChange } from "./store";
import type { GridActive } from "./DataGrid";
import type { Dispatch } from "react";
import { clsx as cx } from "clsx";
import { useStore } from "./store";
import {
  ClsCell,
  DirCell,
  SumLine,
  canonOfEdit,
  reconciliationSuggestions,
} from "./Movements";
import {
  Alert,
  Badge,
  Button,
  Empty,
  Field,
  Hint,
  IconButton,
  Input,
  Menu,
  type MenuItem,
  Meter,
  Popover,
  Seg,
  Select,
  copyText,
  sleep,
  useToast,
} from "./Primitives";
import {
  DRAFT_REQUIRED,
  EMPTY_FILTERS,
  F,
  REASON_FIX,
  SAVED_VIEWS,
  SEAL_LABEL,
  SINGLE_SECONDS,
  STATUS_FILTERS,
  checkIssues,
  deriveIva,
  diffOf,
  effDate,
  effective,
  fmtDateLong,
  fmtMoney,
  fmtStamp,
  getField,
  grossCheck,
  isIdentity,
  lockReason,
  optionsFor,
  parseFor,
  parsePercent,
  plural,
  reviewStatus,
  routeField,
  sameValue,
  shortId,
  show,
  statusOf,
  sumsOf,
} from "./model";
import {
  CATEGORY_FAMILY,
  CATEGORY_LABEL,
  CLASSIFIED,
  CLS,
  FAMILIES,
  FAMILY_LABEL,
  IMPORT_ISSUES,
  IRPF,
  IVA_GROUPS,
  IVA_LABEL,
  LIFECYCLE,
  PAYMENT,
  REASONS,
  TODAY,
  pct,
} from "./vocab";
import { hashHex } from "./data";
import { HostFileDialog } from "./Dialogs";

export type FieldProps = {
  row: Movement;
  staged: Record<string, Record<string, Value>>;
  dispatchStage: (changes: StageChange[], label: string) => void;
};

/* ── The inspector (R10): one scroll with a sticky section index,
   Classification first; actions behind ⋯ in its header. ────────────── */
export const INSP_SECTIONS: [string, string][] = [
  ["classification", "Classify"],
  ["documents", "Documents"],
  ["invoice", "Invoice"],
  ["details", "Details"],
  ["history", "History"],
];
export const InspCloseCtx = createContext<(() => void) | null>(null);
export function Inspector({
  active,
  onClose,
  embedded,
}: {
  active: GridActive | null;
  onClose?: () => void;
  embedded?: boolean;
}) {
  const [state, dispatch] = useStore();
  const page = usePage();
  const { view, data, staged } = state;
  const ids = Object.keys(state.selection).filter(
    (id) => data.byId[id] || staged.drafts.some((d) => d.key === id),
  );
  const ref = useRef<HTMLElement>(null);
  const width = view.inspectorW;
  const resize = (nw: number) => {
    const v = Math.max(280, Math.min(Math.round(window.innerWidth * 0.6), nw));
    dispatch({ type: "VIEW", patch: { inspectorW: v } });
  };
  const startResize = (e: PointerEvent<HTMLElement>) => {
    e.preventDefault();
    const el = ref.current;
    if (!el) return;
    const x0 = e.clientX,
      w0 = el.offsetWidth;
    const h = e.currentTarget;
    h.classList.add("on");
    document.body.setAttribute("data-resizing", "vertical");
    const mv = (ev: globalThis.PointerEvent) => {
      el.style.width =
        Math.max(
          280,
          Math.min(window.innerWidth * 0.6, w0 - (ev.clientX - x0)),
        ) + "px";
    };
    const up = () => {
      h.classList.remove("on");
      document.body.removeAttribute("data-resizing");
      window.removeEventListener("pointermove", mv);
      window.removeEventListener("pointerup", up);
      resize(el.offsetWidth);
    };
    window.addEventListener("pointermove", mv);
    window.addEventListener("pointerup", up);
  };
  const peekId = page.peekId && data.byId[page.peekId] ? page.peekId : null;
  const id =
    peekId || (ids.length === 1 ? ids[0] : !ids.length ? active?.key : null);
  const draft = id ? staged.drafts.find((d) => d.key === id) : null;
  const row = id && !draft ? data.byId[id] : null;
  const close =
    onClose ||
    (() => {
      dispatch({ type: "VIEW", patch: { inspector: false } });
      setTimeout(() => page.focusGrid(), 0);
    });
  const cur = ref.current?.offsetWidth || 320;
  return (
    <InspCloseCtx.Provider value={embedded ? null : close}>
      <aside
        ref={ref}
        className={cx("inspector", embedded && "embedded")}
        aria-label="Movement details"
        style={{ width: embedded ? undefined : width || undefined }}
        onKeyDown={(e) => {
          if (
            e.key === "Escape" &&
            !e.defaultPrevented &&
            !(e.target as Element).closest(
              "input, select, textarea, .menu, .popover",
            )
          ) {
            e.preventDefault();
            close();
          }
        }}
      >
        <div className="sheet-handle" aria-hidden="true"></div>
        {embedded ? null : (
          <div
            className="insp-resize"
            role="separator"
            aria-orientation="vertical"
            aria-label="Resize the inspector"
            tabIndex={0}
            aria-valuemin={280}
            aria-valuemax={Math.round(window.innerWidth * 0.6)}
            aria-valuenow={Math.round(width || cur)}
            onPointerDown={startResize}
            onKeyDown={(e) => {
              if (e.key === "ArrowLeft" || e.key === "ArrowRight") {
                e.preventDefault();
                resize((width || cur) + (e.key === "ArrowLeft" ? 24 : -24));
              } else if (e.key === "Home") {
                e.preventDefault();
                resize(280);
              } else if (e.key === "End") {
                e.preventDefault();
                resize(window.innerWidth * 0.6);
              }
            }}
          ></div>
        )}
        {peekId ? (
          <div className="peek-bar">
            <span className="t-sm muted f1">Not in the current view.</span>
            <Button
              size="xs"
              variant="outline"
              icon="back"
              onClick={() => page.setPeek(null)}
            >
              Back to{" "}
              {state.view.savedView === "custom"
                ? "your view"
                : SAVED_VIEWS[state.view.savedView]?.label}
            </Button>
            <Button
              size="xs"
              variant="ghost"
              onClick={() => page.showInGrid(peekId)}
            >
              Show it in the grid
            </Button>
          </div>
        ) : null}
        {!peekId && ids.length > 1 ? (
          <MultiInspector ids={ids} />
        ) : draft ? (
          <DraftInspector draft={draft} />
        ) : row ? (
          <RowInspector key={row.id} row={row} />
        ) : (
          <Empty
            icon="info"
            title="Nothing selected"
            desc="Select a movement to see every field, its documents, its history and what it can do."
          />
        )}
      </aside>
    </InspCloseCtx.Provider>
  );
}
export function InspHead({
  title,
  sub,
  children,
  menuItems,
}: {
  title: ReactNode;
  sub?: ReactNode;
  children?: ReactNode;
  menuItems?: MenuItem[];
}) {
  const close = useContext(InspCloseCtx);
  const [menu, setMenu] = useState<HTMLElement | null>(null);
  return (
    <div className="insp-head">
      <div className="f1 col g1">
        <div className="insp-title">{title}</div>
        {sub ? <div className="insp-sub">{sub}</div> : null}
        {children}
      </div>
      {menuItems ? (
        <IconButton
          icon="more"
          label="Actions for this movement"
          aria-haspopup="menu"
          aria-expanded={!!menu}
          onClick={(e) => setMenu(e.currentTarget)}
        />
      ) : null}
      {close ? (
        <IconButton
          icon="close"
          label="Hide the inspector"
          shortcut="Alt+I"
          onClick={close}
        />
      ) : null}
      {menu ? (
        <Menu
          anchor={menu}
          items={menuItems ?? []}
          onClose={() => setMenu(null)}
          label="Actions for this movement"
          align="end"
        />
      ) : null}
    </div>
  );
}

/* One editable fact. The value is a button named by the value and
   described by its label; Enter or click edits it. */
export type InspFieldProps = {
  row: Movement;
  k: string;
  label?: string;
  isDraft?: boolean;
  staged: Record<string, Record<string, Value>>;
  render?: (eff: Movement) => ReactNode;
  readonlyReason?: string | null;
  dispatchStage: (changes: StageChange[], label: string) => void;
};
export function InspField({
  row,
  k,
  label,
  isDraft,
  staged,
  render,
  readonlyReason,
  dispatchStage,
}: InspFieldProps) {
  const [state] = useStore();
  const toast = useToast();
  const [editing, setEditing] = useState(false);
  const [val, setVal] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const btnRef = useRef<HTMLButtonElement>(null);
  const lid = useId();
  const def = F[k]!;
  const base = row;
  const eff = isDraft ? row : effective(row, staged, state.staged.actions);
  const v = getField(eff, k);
  const approval =
    !isDraft &&
    state.staged.actions.find(
      (a) =>
        a.type === "approve" &&
        a.rowIds[0] === row.id &&
        k in (a.payload?.fields ?? {}),
    );
  const changed =
    !isDraft &&
    ((staged[row.id] &&
      k in staged[row.id]! &&
      !sameValue(getField(base, k), staged[row.id]![k])) ||
      (approval &&
        !sameValue(
          getField(base, k),
          (approval.payload?.fields as Record<string, Value>)?.[k],
        )));
  const derived = !isDraft && state.staged.derived?.[row.id]?.[k];
  const lock =
    readonlyReason ||
    (def
      ? lockReason(isDraft ? eff : eff, k, isDraft, state.staged.actions)
      : "Read-only.");
  const shown = render
    ? render(eff)
    : show(k, v, eff, true) ||
      (k === "counterpartyCountry" || k === "sourceJurisdiction"
        ? "Not stated"
        : k === "account"
          ? "No account"
          : "Not set");
  const refocus = () => setTimeout(() => btnRef.current?.focus(), 0);
  const begin = () => {
    if (lock) {
      toast(lock);
      return;
    }
    setVal(def.editor === "combo" ? String(v ?? "") : canonOfEdit(k, eff));
    setErr(null);
    setEditing(true);
  };
  const commit = (raw?: Value) => {
    const r =
      def.editor === "combo"
        ? { value: raw }
        : parseFor(k, raw ?? val, { row: eff, draft: isDraft });
    if (r.error) {
      setErr(r.error);
      return;
    }
    const value = r.empty || r.value === "" ? null : r.value;
    setEditing(false);
    refocus();
    if (sameValue(value, v)) return;
    dispatchStage(
      [{ id: row.id, field: k, value }],
      `Edit ${def.label.toLowerCase()}`,
    );
    toast(
      `${def.label}: ${show(k, value, eff, true) || "cleared"} · not saved. Undo with Ctrl+Z.`,
    );
  };
  const dt = <dt id={lid}>{label || def?.label}</dt>;
  if (editing && def.editor !== "combo") {
    return (
      <Fragment>
        {dt}
        <dd>
          <div className="col g1" style={{ width: "100%" }}>
            <Input
              size="sm"
              autoFocus
              value={val}
              aria-invalid={!!err}
              aria-labelledby={lid}
              aria-describedby={lid + "-h"}
              onChange={(e) => {
                setVal(e.target.value);
                setErr(null);
              }}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  commit();
                } else if (e.key === "Escape") {
                  e.preventDefault();
                  e.stopPropagation();
                  setEditing(false);
                  refocus();
                }
              }}
              onBlur={() => {
                if (val === canonOfEdit(k, eff)) setEditing(false);
                else commit();
              }}
            />
            <span
              id={lid + "-h"}
              className={err ? "danger-t t-sm" : "muted t-xs"}
            >
              {err ||
                [
                  def.hint,
                  isIdentity(k, base) && !isDraft
                    ? "Saved under a new reference: the movement's id changes."
                    : "",
                ]
                  .filter(Boolean)
                  .join(" ")}
            </span>
          </div>
        </dd>
      </Fragment>
    );
  }
  return (
    <Fragment>
      {dt}
      <dd>
        {changed ? (
          <span className="was">
            {show(k, getField(base, k), base, true) || "empty"}
            {derived
              ? " · worked out by Cadrumo"
              : approval
                ? " · from the model, approved"
                : ""}
          </span>
        ) : null}
        <button
          ref={btnRef}
          type="button"
          className={cx("dd-btn", lock && "locked", changed && "fw5")}
          aria-describedby={lid}
          aria-disabled={lock ? "true" : undefined}
          aria-haspopup={def?.editor === "combo" ? "listbox" : undefined}
          data-tip={lock || undefined}
          onClick={begin}
          onKeyDown={(e) => {
            if (e.altKey && e.key === "ArrowDown" && def?.editor === "combo") {
              e.preventDefault();
              begin();
            }
          }}
        >
          <span className="dd-val">{shown}</span>
          {lock && def ? (
            <Icon name="lock" size="xs" className="muted" />
          ) : null}
        </button>
        {editing && def.editor === "combo" ? (
          <InspCombo
            anchor={btnRef.current}
            k={k}
            row={eff}
            value={v == null ? null : String(v)}
            label={`${label || def.label} for ${eff.description || "the new movement"}`}
            onCommit={commit}
            onCancel={() => setEditing(false)}
          />
        ) : null}
      </dd>
    </Fragment>
  );
}
export function RowInspector({ row }: { row: Movement }) {
  const [state, dispatch] = useStore();
  const page = usePage();
  const { staged } = state;
  const scrollRef = useRef<HTMLDivElement>(null);
  const eff = effective(row, staged.rows, staged.actions);
  const issues = checkIssues(row, state.check);
  const stage = (changes: StageChange[], label: string) =>
    dispatch({ type: "STAGE", changes, label });
  const fieldProps = { row, staged: staged.rows, dispatchStage: stage };
  const sugg = page.suggestionFor(row);
  const outcome = state.outcomes[row.id];
  const S = statusOf(row, state.check);
  const fields = diffOf(row, staged.rows[row.id]);
  const rowActions = staged.actions.filter((a) => a.rowIds.includes(row.id));
  const go = (sec: string, focus?: boolean) => {
    const sc = scrollRef.current;
    const el = sc?.querySelector<HTMLElement>(`[data-sec="${sec}"]`);
    if (sc && el) {
      sc.scrollTop = el.offsetTop - 8;
      if (focus) el.querySelector("h3")?.focus();
    }
  };
  const [current, setCurrent] = useState("classification");
  useEffect(() => {
    const sc = scrollRef.current;
    if (!sc) return;
    const spy = () => {
      let c = INSP_SECTIONS[0]![0];
      sc.querySelectorAll<HTMLElement>("[data-sec]").forEach((el) => {
        if (el.offsetTop - sc.scrollTop <= 24)
          c = el.getAttribute("data-sec") ?? c;
      });
      if (sc.scrollTop + sc.clientHeight >= sc.scrollHeight - 2)
        c = INSP_SECTIONS[INSP_SECTIONS.length - 1]![0];
      setCurrent(c);
    };
    spy();
    sc.addEventListener("scroll", spy);
    return () => sc.removeEventListener("scroll", spy);
  }, [row.id]);
  const arrive = useEffectEvent(() => {
    const want =
      page.inspAt ||
      (reviewStatus(row) === "pending" ? "classification" : null);
    page.inspAt = null;
    if (want) setTimeout(() => go(want), 30);
    if (page.inspFocusIndex) {
      page.inspFocusIndex = false;
      setTimeout(
        () =>
          scrollRef.current?.parentElement
            ?.querySelector<HTMLElement>(".insp-index button")
            ?.focus(),
        40,
      );
    }
  });
  useEffect(() => {
    arrive();
  }, [row.id, page.inspTick]);
  const lockAct = lockReason(row, "amount", false, staged.actions);
  const menuItems: MenuItem[] = [
    {
      label: "Revert movement",
      icon: "reset",
      disabled: !fields.length && !rowActions.length,
      reason: "Nothing unsaved on this movement.",
      onSelect: () => dispatch({ type: "REVERT_ROW", id: row.id }),
    },
    { sep: true },
    {
      label: "Split into parts…",
      icon: "split",
      disabled: !!lockAct,
      reason: lockAct,
      onSelect: () => page.openAction("split", [row.id]),
    },
    ...(row.split?.role === "child"
      ? ([
          {
            label: "Merge parts back…",
            icon: "merge",
            disabled: !!row.sealed?.length,
            onSelect: () => page.openAction("merge", [row.id]),
          },
        ] satisfies MenuItem[])
      : []),
    ...(row.issue === "duplicate" && row.lifecycle === "active"
      ? ([
          {
            label: "Archive as duplicate",
            icon: "archive",
            onSelect: () => page.stageArchiveDuplicate(row.id),
          },
          {
            label: "Keep both",
            icon: "check",
            onSelect: () => page.stageKeepBoth(row.id),
          },
        ] satisfies MenuItem[])
      : []),
    {
      label: "Exclude from filing…",
      icon: "eyeOff",
      disabled: !!row.sealed?.length || row.cls === "excluded",
      reason: row.cls === "excluded" ? "Already excluded." : lockAct,
      onSelect: () => page.openAction("exclude", [row.id]),
    },
    {
      label: "Archive…",
      icon: "archive",
      disabled: row.lifecycle !== "active" || !!row.sealed?.length,
      reason: "Only active, unsealed movements can be archived.",
      onSelect: () => page.openAction("archive", [row.id]),
    },
    {
      label: "Set aside…",
      icon: "stash",
      disabled: row.lifecycle !== "active" || !!row.sealed?.length,
      reason: "Only active, unsealed movements can be set aside.",
      onSelect: () => page.openAction("stash", [row.id]),
    },
    {
      label: "Restore…",
      icon: "unarchive",
      disabled: !(row.lifecycle === "archived" || row.lifecycle === "stashed"),
      reason: "Only archived or set-aside movements can be restored.",
      onSelect: () => page.openAction("restore", [row.id]),
    },
    { sep: true },
    {
      label: "Remove…",
      icon: "trash",
      onSelect: () => page.openAction("remove", [row.id]),
    },
  ];
  return (
    <Fragment>
      <InspHead
        title={eff.description}
        sub={`${eff.counterparty || "No counterparty"} · ${fmtDateLong(effDate(eff))}`}
        menuItems={menuItems}
      >
        <div className="row g2 wrap" style={{ marginTop: "var(--spacing)" }}>
          <span className="insp-amount">
            {fmtMoney(row.amount)}{" "}
            <span className="muted t-sm">{row.currency}</span>
          </span>
          <DirCell v={row.direction} />
          <span className={cx("st", S.key)}>
            <Icon name={S.icon} size="xs" />
            <span className="st-word">{S.label}</span>
          </span>
          {row.lifecycle !== "active" ? (
            <span className="tag">{LIFECYCLE[row.lifecycle].label}</span>
          ) : null}
        </div>
        {fields.length || rowActions.length ? (
          <div className="unsaved-line">
            <span className="unsaved-bar static" aria-hidden="true"></span>
            {fields.includes("cls") ||
            rowActions.some((a) => a.type === "approve")
              ? `${show("cls", row.cls, row)} → ${show("cls", eff.cls, eff)}`
              : plural(fields.length + rowActions.length, "change")}{" "}
            · not saved
            <Button
              size="xs"
              variant="ghost"
              onClick={() => dispatch({ type: "REVERT_ROW", id: row.id })}
            >
              Revert
            </Button>
          </div>
        ) : null}
        {row.sealed?.length ? (
          <div
            className="row g1 t-sm muted"
            style={{ alignItems: "flex-start" }}
          >
            <Icon name="lock" size="xs" />
            Used in{" "}
            {row.sealed
              .map(
                (u) =>
                  `Modelo ${u.modelo} · ${u.period} (${SEAL_LABEL[u.state]})`,
              )
              .join(" and ")}
            . Read-only.
          </div>
        ) : null}
      </InspHead>
      {outcome ? (
        <div className="insp-pad">
          <Alert
            tone={outcome.status === "refused" ? "danger" : "warning"}
            icon={
              outcome.status === "refused"
                ? "refused"
                : outcome.status === "unknown"
                  ? "unknown"
                  : "pause"
            }
            title={
              outcome.status === "refused"
                ? "The ledger refused this change"
                : outcome.status === "unknown"
                  ? "Outcome unknown"
                  : "Not sent"
            }
          >
            {outcome.msg}
          </Alert>
        </div>
      ) : null}
      <SectionIndex current={current} go={go} sugg={!!sugg} />
      <div
        className="insp-body"
        ref={scrollRef}
        tabIndex={0}
        role="region"
        aria-label="Movement sections"
      >
        <section
          data-sec="classification"
          className="sec"
          aria-labelledby={"h-cl-" + row.id}
        >
          <h3 id={"h-cl-" + row.id} className="sec-title" tabIndex={-1}>
            Classification
          </h3>
          <ClassifySection
            row={row}
            eff={eff}
            issues={issues}
            fieldProps={fieldProps}
            stage={stage}
            sugg={sugg}
          />
        </section>
        <section
          data-sec="documents"
          className="sec"
          aria-labelledby={"h-do-" + row.id}
        >
          <h3 id={"h-do-" + row.id} className="sec-title" tabIndex={-1}>
            Documents
          </h3>
          <DocsSection row={row} />
        </section>
        <section
          data-sec="invoice"
          className="sec"
          aria-labelledby={"h-in-" + row.id}
        >
          <h3 id={"h-in-" + row.id} className="sec-title" tabIndex={-1}>
            Invoice
          </h3>
          <InvoiceSection row={row} />
        </section>
        <section
          data-sec="details"
          className="sec"
          aria-labelledby={"h-de-" + row.id}
        >
          <h3 id={"h-de-" + row.id} className="sec-title" tabIndex={-1}>
            Details
          </h3>
          <DetailsSection row={row} eff={eff} fieldProps={fieldProps} />
        </section>
        <section
          data-sec="history"
          className="sec"
          aria-labelledby={"h-hi-" + row.id}
        >
          <h3 id={"h-hi-" + row.id} className="sec-title" tabIndex={-1}>
            History
          </h3>
          <HistorySection row={row} />
          <div className="sub-sec">
            <div className="sub-title">Used in</div>
            <UsesSection row={row} />
          </div>
        </section>
      </div>
    </Fragment>
  );
}
/* A jump bar, not tabs: scroll-spy marks where you are; what doesn't
   fit goes into More, never clipped (M6). */
export function SectionIndex({
  current,
  go,
  sugg,
}: {
  current: string;
  go: (section: string, focus?: boolean) => void;
  sugg: boolean;
}) {
  const ref = useRef<HTMLElement>(null);
  const [fit, setFit] = useState(INSP_SECTIONS.length);
  const [menu, setMenu] = useState<HTMLElement | null>(null);
  const [measure, setMeasure] = useState(0);
  useLayoutEffect(() => {
    const el = ref.current;
    if (el && el.scrollWidth > el.clientWidth + 1 && fit > 1) setFit(fit - 1);
  }, [fit, measure, current, sugg]);
  useEffect(() => {
    const ro = new ResizeObserver(() => {
      setFit(INSP_SECTIONS.length);
      setMeasure((m) => m + 1);
    });
    if (ref.current) ro.observe(ref.current);
    return () => ro.disconnect();
  }, []);
  const shown = INSP_SECTIONS.slice(0, fit),
    rest = INSP_SECTIONS.slice(fit);
  return (
    <nav ref={ref} className="insp-index" aria-label="Jump to a section">
      {shown.map(([k, l]) => (
        <button
          key={k}
          type="button"
          className="jump"
          aria-current={current === k ? "location" : undefined}
          onClick={() => go(k!, true)}
        >
          {l}
          {k === "classification" && sugg ? (
            <>
              <span className="badge count" aria-hidden="true">
                1
              </span>
              <span className="sr-only">, 1 model suggestion</span>
            </>
          ) : null}
        </button>
      ))}
      {rest.length ? (
        <button
          type="button"
          className="jump"
          aria-haspopup="menu"
          aria-expanded={!!menu}
          aria-current={
            rest.some(([k]) => k === current) ? "location" : undefined
          }
          onClick={(e) => setMenu(e.currentTarget)}
        >
          More <Icon name="chevronDown" size="xs" />
        </button>
      ) : null}
      {menu ? (
        <Menu
          anchor={menu}
          label="More sections"
          align="end"
          onClose={() => setMenu(null)}
          items={rest.map(([k, l]) => ({
            label: l,
            onSelect: () => go(k!, true),
          }))}
        />
      ) : null}
    </nav>
  );
}
/* V-05: a combobox for list fields. It opens on Enter or Alt+Down;
   arrows move; only Enter or Tab commits; focus returns to the field. */
type ComboChoice = Omit<Option, "value"> & { value: string | null };
export function InspCombo({
  anchor,
  k,
  row,
  value,
  label,
  onCommit,
  onCancel,
}: {
  anchor: HTMLElement | null;
  k: string;
  row: Movement;
  value: string | null;
  label: string;
  onCommit: (value: string | null) => void;
  onCancel: () => void;
}) {
  const def = F[k]!;
  const opts = optionsFor(k, row);
  const clear: ComboChoice[] =
    def.clearable || k === "account"
      ? [
          {
            value: null,
            label: k === "account" ? "No account" : "Clear the value",
            group: "",
          },
        ]
      : [];
  const [q, setQ] = useState("");
  const t = q.trim().toLowerCase();
  const list: ComboChoice[] = [
    ...(t ? [] : clear),
    ...opts.filter(
      (o) =>
        !t ||
        o.label.toLowerCase().includes(t) ||
        (o.group || "").toLowerCase().includes(t),
    ),
  ];
  const [hl, setHl] = useState(() =>
    Math.max(
      0,
      list.findIndex((o) => o.value === value),
    ),
  );
  const lid = useId();
  const choose = (o: ComboChoice | undefined) => {
    if (!o || o.disabled) return;
    onCommit(o.value);
  };
  let last: string | null = null;
  return (
    <Popover
      anchor={anchor}
      onClose={onCancel}
      width="18rem"
      label={label}
      className="col g2 insp-combo"
    >
      <input
        data-autofocus
        className="input sm"
        value={q}
        placeholder={"Search " + def.label.toLowerCase()}
        role="combobox"
        aria-label={label}
        aria-expanded="true"
        aria-controls={lid}
        aria-activedescendant={list[hl] ? lid + "-" + hl : undefined}
        onChange={(e) => {
          setQ(e.target.value);
          setHl(0);
        }}
        onKeyDown={(e) => {
          if (e.key === "ArrowDown") {
            e.preventDefault();
            setHl((h) => Math.min(list.length - 1, h + 1));
          } else if (e.key === "ArrowUp") {
            e.preventDefault();
            setHl((h) => Math.max(0, h - 1));
          } else if (e.key === "Enter" || e.key === "Tab") {
            e.preventDefault();
            choose(list[hl]);
          }
        }}
      />
      <div
        role="listbox"
        id={lid}
        aria-label={label + " choices"}
        className="combo-list insp-combo-list"
      >
        {list.length ? (
          list.map((o, i) => {
            const head =
              o.group && o.group !== last
                ? ((last = o.group),
                  (
                    <div className="combo-group" aria-hidden="true">
                      {o.group}
                    </div>
                  ))
                : null;
            return (
              <Fragment key={String(o.value) + i}>
                {head}
                <div
                  id={lid + "-" + i}
                  role="option"
                  aria-selected={o.value === value}
                  aria-disabled={o.disabled ? "true" : undefined}
                  className="combo-opt"
                  data-hl={i === hl}
                  onPointerMove={() => setHl(i)}
                  onClick={() => choose(o)}
                >
                  {o.value === value ? (
                    <Icon name="tick" size="xs" />
                  ) : (
                    <span className="icon-gap"></span>
                  )}
                  <span className="truncate">{o.label}</span>
                </div>
              </Fragment>
            );
          })
        ) : (
          <div className="combo-empty">No match · Esc to cancel</div>
        )}
      </div>
    </Popover>
  );
}
export function DetailsSection({
  row,
  eff,
  fieldProps,
}: {
  row: Movement;
  eff: Movement;
  fieldProps: FieldProps;
}) {
  const [state, dispatch] = useStore();
  const page = usePage();
  const acct = state.data.accounts.find((a) => a.id === eff.account);
  const batch = state.data.batches.find((b) => b.id === row.batch);
  return (
    <Fragment>
      <dl className="kv">
        <dt>Effective date</dt>
        <dd>
          {fmtDateLong(effDate(eff))}{" "}
          <span className="muted t-sm">
            the {row.valueDate ? "value" : "booked"} date
          </span>
        </dd>
        <InspField k="booked" {...fieldProps} />
        <InspField k="valueDate" {...fieldProps} />
        <InspField
          k="amount"
          {...fieldProps}
          render={(r) => `${fmtMoney(r.amount)} ${r.currency}`}
        />
        <InspField k="direction" {...fieldProps} />
        <InspField k="currency" {...fieldProps} />
        <dt>EUR value</dt>
        <dd>
          {row.currency === "EUR" ? (
            <span className="muted">Same: a euro movement</span>
          ) : row.fx ? (
            <span className="col">
              <span className="tnum fw5">{fmtMoney(row.fx.eur)} EUR</span>
              <span className="muted t-sm">
                {row.fx.source} {row.fx.rate} on {fmtDateLong(row.fx.date)}
              </span>
            </span>
          ) : (
            <span className="col">
              <span className="row g1">
                <Icon name="noRate" size="xs" className="warn-t" />
                No exchange rate
              </span>
              <span className="muted t-sm">
                No ECB reference rate for {fmtDateLong(effDate(row))}. The EUR
                value is unknown, not zero, and this movement stays out of EUR
                totals until a rate exists.
              </span>
            </span>
          )}
        </dd>
        <InspField k="description" {...fieldProps} />
        <InspField k="counterparty" {...fieldProps} />
        <InspField k="counterpartyCountry" {...fieldProps} />
        <InspField k="idState" {...fieldProps} />
        <InspField k="sourceJurisdiction" {...fieldProps} />
        <InspField
          k="account"
          {...fieldProps}
          render={() =>
            acct ? (
              <span className="col">
                <span>{acct.label}</span>
                <span className="muted t-sm mono nowrap">
                  {acct.iban.slice(0, 4)} •••• {acct.iban.slice(-4)}
                </span>
              </span>
            ) : (
              "No account"
            )
          }
        />
        <InspField k="group" {...fieldProps} />
        <InspField k="notes" {...fieldProps} />
      </dl>
      <dl className="kv">
        <dt>Where it came from</dt>
        <dd>
          {row.prov.file}
          {row.prov.row ? `, row ${row.prov.row}` : ""}
        </dd>
        <dt>Read as</dt>
        <dd>{row.prov.provider}</dd>
        <dt>Imported</dt>
        <dd>{fmtDateLong(row.prov.ingested)}</dd>
        {batch ? (
          <>
            <dt>Import</dt>
            <dd>
              <Button
                variant="link"
                size="xs"
                onClick={() =>
                  dispatch({
                    type: "VIEW",
                    patch: {
                      filters: { ...EMPTY_FILTERS, batch: batch.id },
                      savedView: "custom",
                    },
                  })
                }
              >
                Show this import ({batch.rows})
              </Button>
            </dd>
          </>
        ) : null}
        {row.issue ? (
          <>
            <dt>Import note</dt>
            <dd>
              <span className="tag">{IMPORT_ISSUES[row.issue]}</span>
            </dd>
          </>
        ) : null}
        <dt>Added</dt>
        <dd>{fmtStamp(row.created)}</dd>
        <dt>Last saved</dt>
        <dd>{fmtStamp(row.modified)}</dd>
      </dl>
      <details className="tech">
        <summary>Technical details</summary>
        <dl className="kv mono t-xs">
          <dt>Movement id</dt>
          <dd>
            {row.id.slice(0, 16)}…{" "}
            <IconButton
              icon="copy"
              label="Copy the full id"
              onClick={() => {
                copyText(row.id);
                page.toast("Movement id copied");
              }}
            />
          </dd>
          <dt>Provider id</dt>
          <dd>{row.providerId}</dd>
          <dt>Source digest</dt>
          <dd>sha256 {row.prov.sha.slice(0, 16)}…</dd>
          {row.lineage?.length ? (
            <>
              <dt>Earlier ids</dt>
              <dd>{row.lineage.map((l) => shortId(l.prev)).join(", ")}</dd>
            </>
          ) : null}
        </dl>
      </details>
    </Fragment>
  );
}
export function ClassifySection({
  row,
  eff,
  issues,
  fieldProps,
  stage,
  sugg,
}: {
  row: Movement;
  eff: Movement;
  issues: string[];
  fieldProps: FieldProps;
  stage: (changes: StageChange[], label: string) => void;
  sugg: Suggestion | null;
}) {
  const [state, dispatch] = useStore();
  const page = usePage();
  const locked = lockReason(eff, "cls", false, state.staged.actions);
  const [deriveCat, setDeriveCat] = useState(eff.ivaCategory || "");
  const [share, setShare] = useState(
    eff.share != null ? String(+(eff.share * 100)) : "",
  );
  const [shareErr, setShareErr] = useState<string | null>(null);
  const [rejecting, setRejecting] = useState(false);
  const [reason, setReason] = useState("");
  const [asking, setAsking] = useState<string | null>(null);
  const [suggShare, setSuggShare] = useState("");
  const [suggErr, setSuggErr] = useState<string | null>(null);
  const [askMenu, setAskMenu] = useState<HTMLElement | null>(null);
  useEffect(() => {
    setShare(eff.share != null ? String(+(eff.share * 100)) : "");
  }, [eff.share]);
  const ratio = eff.category ? state.data.ratios[2026]![eff.category] : null;
  const derived = deriveIva(eff.amount, deriveCat);
  const by = row.classifiedBy;
  const byText = by.startsWith("rule:")
    ? `The rule “${(state.data.rules.find((x) => "rule:" + x.id === by) || {}).name || by.slice(5)}”`
    : by.startsWith("llm:")
      ? `Model · ${by} · approved by you`
      : by === "manual"
        ? "You"
        : by.startsWith("derived:")
          ? "Worked out"
          : "No one yet";
  const modelDown = state.proto.state === "modelUnavailable";
  const approval = state.staged.actions.find(
    (a) => a.type === "approve" && a.rowIds[0] === row.id,
  );
  const ask = async (mode: string) => {
    setAsking(mode);
    await sleep(1000);
    setAsking(null);
    if (mode === "split")
      page.openAction("split", [row.id], { proposal: true });
    else page.askModel([row.id], mode);
  };
  const approve = () => {
    if (!sugg) return;
    let sh = sugg.share;
    if (sugg.cls === "mixed" && sh == null) {
      const r = parsePercent(suggShare, { label: "Business share" });
      if (r.error || r.empty) {
        setSuggErr(
          r.error ||
            "This suggestion has no share. Enter the business share before approving.",
        );
        return;
      }
      sh = Number(r.value);
    }
    stageApproval(dispatch, row, sugg, sh);
    page.toast(
      "Approval staged · figures worked out by Cadrumo from registry rates",
    );
  };
  const fixes = [
    ...new Set(issues.filter((x) => x !== "missing_business_classification")),
  ];
  const ratioConflict =
    eff.cls === "mixed" &&
    !!eff.usageRatio &&
    eff.share != null &&
    state.data.ratios[2026]![eff.usageRatio ?? ""]! != null &&
    Math.abs(state.data.ratios[2026]![eff.usageRatio ?? ""]! - eff.share) >
      1e-9;
  return (
    <Fragment>
      {locked ? <Alert icon="lock">{locked}</Alert> : null}
      {fixes.length ? (
        <Alert tone="warning" title="What's still missing">
          <ul className="fix-list">
            {fixes.map((x) => {
              const fx = REASON_FIX[x];
              return (
                <li key={x}>
                  <span className="f1">{REASONS[x]}</span>
                  {fx ? (
                    <Button
                      size="xs"
                      variant="outline"
                      disabled={!!locked && !fx.profile}
                      onClick={() => {
                        if (fx.profile)
                          page.toast(
                            "Opens Your profile › Home office (another page of the window)",
                          );
                        else if (fx.derive) {
                          const d = deriveIva(eff.amount, eff.ivaCategory);
                          if (d)
                            stage(
                              [
                                { id: row.id, field: "base", value: d.base },
                                {
                                  id: row.id,
                                  field: "ivaRate",
                                  value: d.ivaRate,
                                },
                                {
                                  id: row.id,
                                  field: "ivaAmount",
                                  value: d.ivaAmount,
                                },
                              ],
                              "Derive figures",
                            );
                          else
                            page.toast(
                              "Choose an IVA category with a single rate first.",
                            );
                        } else if (
                          fx.field === "usageRatio" &&
                          eff.category &&
                          state.data.ratios[2026]![eff.category] != null
                        )
                          stage(
                            [
                              {
                                id: row.id,
                                field: "usageRatio",
                                value: eff.category,
                              },
                              {
                                id: row.id,
                                field: "share",
                                value: state.data.ratios[2026]![eff.category],
                              },
                            ],
                            "Set share from ratio",
                          );
                        else if (fx.field) page.editCell(row.id, fx.field);
                      }}
                    >
                      {fx.label}
                    </Button>
                  ) : null}
                </li>
              );
            })}
          </ul>
          <Hint text="These block calculation, not saving. Press N in the grid for the next one." />
        </Alert>
      ) : null}
      <div className="card-wash">
        <div className="row g2 wrap">
          <ClsCell r={row} />
          <span className="f1"></span>
          <span className="muted t-sm">
            {byText}
            {row.classifiedAt ? " · " + fmtStamp(row.classifiedAt) : ""}
          </span>
        </div>
        {!locked && row.direction !== "transfer" ? (
          <div className="row g2 wrap" style={{ alignItems: "end" }}>
            <Seg
              size="sm"
              label="Classification"
              value={CLASSIFIED.has(eff.cls) ? eff.cls : ""}
              options={(["business", "personal", "mixed"] as const).map(
                (v) => ({
                  value: v,
                  label: CLS[v].label,
                }),
              )}
              onChange={(v) =>
                page.classifySelection(v, [row.id], { group: true })
              }
            />
            {eff.cls === "mixed" ? (
              <label className="row g1 t-sm">
                Share{" "}
                <Input
                  size="sm"
                  style={{ width: "calc(var(--spacing) * 18)" }}
                  value={share}
                  inputMode="decimal"
                  aria-label="Business share"
                  aria-invalid={!!shareErr}
                  onChange={(e) => {
                    setShare(e.target.value);
                    setShareErr(null);
                  }}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      const r = parsePercent(share, {
                        label: "Business share",
                      });
                      if (r.error || r.empty)
                        return setShareErr(r.error || "Required.");
                      stage(
                        [{ id: row.id, field: "share", value: r.value }],
                        "Set share",
                      );
                    }
                  }}
                  onBlur={() => {
                    const r = parsePercent(share, { label: "Business share" });
                    if (r.value != null && !sameValue(r.value, eff.share))
                      stage(
                        [{ id: row.id, field: "share", value: r.value }],
                        "Set share",
                      );
                    else if (r.error) setShareErr(r.error);
                  }}
                />
                %
              </label>
            ) : null}
          </div>
        ) : null}
        {shareErr ? <span className="danger-t t-sm">{shareErr}</span> : null}
        {eff.cls === "mixed" && ratio != null && !eff.usageRatio ? (
          <div className="row g2">
            <span className="t-sm f1">
              Your 2026 ratio for {CATEGORY_LABEL[eff.category ?? ""]} is{" "}
              {pct(ratio)}.
            </span>
            <Button
              size="xs"
              variant="outline"
              onClick={() => {
                stage(
                  [
                    { id: row.id, field: "share", value: ratio },
                    { id: row.id, field: "usageRatio", value: eff.category },
                  ],
                  "Use the ratio",
                );
                setShare(String(ratio * 100));
              }}
            >
              Use {pct(ratio)} and reference it
            </Button>
          </div>
        ) : null}
        {ratioConflict ? (
          <Alert tone="warning" title="Share and ratio disagree">
            The share is {pct(eff.share ?? 0)} but the referenced ratio is{" "}
            {pct(state.data.ratios[2026]![eff.usageRatio ?? ""]!)}. The ledger
            checks they match.{" "}
            <Button
              size="xs"
              variant="outline"
              onClick={() => {
                stage(
                  [
                    {
                      id: row.id,
                      field: "share",
                      value: state.data.ratios[2026]![eff.usageRatio ?? ""]!,
                    },
                  ],
                  "Use the ratio",
                );
                setShare(
                  String(state.data.ratios[2026]![eff.usageRatio ?? ""]! * 100),
                );
              }}
            >
              Use {pct(state.data.ratios[2026]![eff.usageRatio ?? ""]!)}
            </Button>
          </Alert>
        ) : null}
      </div>
      <dl className="kv">
        <InspField
          k="category"
          {...fieldProps}
          render={(r) =>
            r.category ? (
              <span className="col">
                <span>{CATEGORY_LABEL[r.category]}</span>
                <span className="muted t-sm">
                  {FAMILY_LABEL[CATEGORY_FAMILY[r.category] ?? ""]}
                </span>
              </span>
            ) : (
              "Not set"
            )
          }
        />
        <InspField k="ivaCategory" {...fieldProps} />
        <InspField k="base" {...fieldProps} />
        <InspField k="ivaRate" {...fieldProps} />
        <InspField k="ivaAmount" {...fieldProps} />
        <InspField k="recargo" {...fieldProps} />
        <InspField k="irpf" {...fieldProps} />
        <dt>Usage ratio</dt>
        <dd>
          {eff.usageRatio ? (
            `${CATEGORY_LABEL[eff.usageRatio]} · ${state.data.ratios[2026]![eff.usageRatio ?? ""]! != null ? pct(state.data.ratios[2026]![eff.usageRatio ?? ""]!) : "not set for 2026"}`
          ) : eff.cls === "mixed" ? (
            <span>None: Mixed needs one before calculation</span>
          ) : (
            <span className="muted">Not needed</span>
          )}
        </dd>
      </dl>
      {grossCheck(eff) ? (
        <Alert tone="warning" title="Gross check">
          {grossCheck(eff)?.text}. The ledger refuses figures that do not close
          (net-of-withholding income and reverse charge excepted).
        </Alert>
      ) : null}
      <div className="sub-sec">
        <div className="sub-title">
          Model suggestion{" "}
          <Hint text="A proposal from the local model, run on this computer: nothing leaves it. Only you approve it; it never sets a rate or an amount." />
        </div>
        {modelDown ? (
          <Alert
            tone="warning"
            icon="unplug"
            title="The local model is not available"
          >
            It is not loaded. Classify by hand, or check Documents › Reader
            readiness. Nothing was sent anywhere.
          </Alert>
        ) : approval ? (
          <Alert icon="agent" title="Approval staged">
            The model's suggestion is approved in the tray; it is recorded as
            Model · llm:local-medium · approved by you when saved.{" "}
            <Button
              size="xs"
              variant="ghost"
              onClick={() =>
                dispatch({ type: "UNSTAGE_ACTION", id: approval.id })
              }
            >
              Drop it
            </Button>
          </Alert>
        ) : sugg ? (
          <div className="card-raised">
            <div className="row g2">
              <Icon name="agent" />
              <b className="fw6 f1">Local model · llm:local-medium</b>
              <span className="tag tnum">
                {Math.round(sugg.confidence * 100)}% confident
              </span>
            </div>
            <Meter value={sugg.confidence} label="Model confidence" />
            <dl className="kv">
              <dt>Classification</dt>
              <dd>
                {CLS[sugg.cls].label}
                {sugg.cls === "mixed"
                  ? sugg.share != null
                    ? " " + pct(sugg.share)
                    : " · no share proposed"
                  : ""}
              </dd>
              {sugg.category ? (
                <>
                  <dt>Category</dt>
                  <dd>{CATEGORY_LABEL[sugg.category]}</dd>
                </>
              ) : null}
              {sugg.ivaCategory ? (
                <>
                  <dt>IVA category</dt>
                  <dd>{IVA_LABEL[sugg.ivaCategory]}</dd>
                </>
              ) : null}
            </dl>
            <p className="t-sm">{sugg.reason}</p>
            {sugg.cls === "mixed" && sugg.share == null ? (
              <Field
                label="Business share"
                req
                hint="The model proposed Mixed without a share. Enter it to approve."
                error={suggErr}
              >
                <Input
                  size="sm"
                  value={suggShare}
                  placeholder="e.g. 50"
                  onChange={(e) => {
                    setSuggShare(e.target.value);
                    setSuggErr(null);
                  }}
                />
              </Field>
            ) : suggErr ? (
              <span className="danger-t t-sm">{suggErr}</span>
            ) : null}
            <Hint text="The model never supplies a rate, a base or an amount. On approval, IVA figures come from the registry rate for the category and must close to the cent." />
            {rejecting ? (
              <div className="col g2">
                <Field
                  label="Why it is wrong"
                  req
                  hint="Recorded with the model's proposal; the movement stays to classify."
                >
                  <Input
                    size="sm"
                    data-autofocus
                    value={reason}
                    onChange={(e) => setReason(e.target.value)}
                    placeholder="e.g. a personal purchase"
                  />
                </Field>
                <div className="row g2">
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => setRejecting(false)}
                  >
                    Cancel
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={!reason.trim()}
                    onClick={() => {
                      dispatch({
                        type: "STAGE_ACTION",
                        action: {
                          id: "reject-" + row.id,
                          type: "reject",
                          rowIds: [row.id],
                          label: `Reject the model's suggestion · ${row.description}`,
                          tech: "ledger.classify.review · reject, with reason",
                          payload: {
                            reason: reason.trim(),
                            model: "local-medium",
                            proposal: sugg,
                          },
                        },
                      });
                      setRejecting(false);
                      page.dropSuggestion(row.id);
                      page.toast("Rejection staged");
                    }}
                  >
                    Stage rejection
                  </Button>
                </div>
              </div>
            ) : (
              <div className="row g2">
                <Button
                  size="sm"
                  icon="tick"
                  disabled={!!locked}
                  onClick={approve}
                >
                  Approve
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  disabled={!!locked}
                  onClick={() => setRejecting(true)}
                >
                  Reject…
                </Button>
              </div>
            )}
          </div>
        ) : (
          <>
            <div className="row g1">
              <Button
                size="sm"
                variant="outline"
                icon="agent"
                iconRight="chevronDown"
                pending={!!asking}
                disabled={!!locked}
                aria-haspopup="menu"
                aria-expanded={!!askMenu}
                onClick={(e) => setAskMenu(e.currentTarget)}
              >
                Ask the model
              </Button>
            </div>
            {askMenu ? (
              <Menu
                anchor={askMenu}
                label="Ask the model"
                onClose={() => setAskMenu(null)}
                items={[
                  {
                    label: "Classification",
                    onSelect: () => ask("classification"),
                  },
                  {
                    label: "With IVA figures",
                    onSelect: () => ask("saturated"),
                  },
                  { label: "Suggest a split", onSelect: () => ask("split") },
                ]}
              />
            ) : null}
          </>
        )}
        {row.modelRejected ? (
          <p className="t-sm muted">
            You rejected an earlier suggestion for this movement.
          </p>
        ) : null}
      </div>
      <div className="sub-sec">
        <div className="sub-title">Work out IVA from a category</div>
        <div className="row g2" style={{ alignItems: "end" }}>
          <Field label="IVA category" className="f1">
            <Select
              size="sm"
              value={deriveCat}
              onChange={(e) => setDeriveCat(e.target.value)}
              disabled={!!lockReason(eff, "base", false, state.staged.actions)}
            >
              <option value="">Choose…</option>
              {IVA_GROUPS.map(([g, items]) => (
                <optgroup key={g} label={g}>
                  {items.map(([k, l]) => (
                    <option key={k} value={k}>
                      {l}
                    </option>
                  ))}
                </optgroup>
              ))}
            </Select>
          </Field>
          <Button
            size="sm"
            variant="outline"
            disabled={
              !derived || !!lockReason(eff, "base", false, state.staged.actions)
            }
            onClick={() =>
              stage(
                [
                  { id: row.id, field: "ivaCategory", value: deriveCat },
                  { id: row.id, field: "base", value: derived!.base },
                  { id: row.id, field: "ivaRate", value: derived!.ivaRate },
                  { id: row.id, field: "ivaAmount", value: derived!.ivaAmount },
                ],
                "Derive IVA",
              )
            }
          >
            Stage figures
          </Button>
        </div>
        {derived ? (
          <p className="t-sm muted tnum">
            Base {fmtMoney(derived.base)} · rate {pct(derived.ivaRate)} · IVA{" "}
            {fmtMoney(derived.ivaAmount)}. {derived.note}
          </p>
        ) : deriveCat ? (
          <p className="t-sm muted">
            This category has no single rate to work from: enter the figures.
          </p>
        ) : null}
      </div>
      <details className="sub-sec">
        <summary className="sub-title">More tax fields</summary>
        <dl className="kv">
          <InspField k="deductionKind" {...fieldProps} />
          <InspField k="investmentAsset" {...fieldProps} />
          <InspField k="m210" {...fieldProps} />
        </dl>
        <Hint text="Deduction kind and investment asset matter for investment goods; the Modelo 210 type only for income a non-resident earns in Spain. Each is saved one at a time." />
      </details>
      {row.classifiedHistory?.length ||
      row.history.some((h) => /Classified|Excluded|rejected/.test(h.what)) ? (
        <div className="sub-sec">
          <div className="sub-title">Earlier decisions</div>
          <ul className="timeline">
            {[
              ...(row.classifiedHistory || []).map((h) => ({
                at: h.at,
                what: `${CLS[h.cls].label} · ${CATEGORY_LABEL[h.category ?? ""]}`,
                by: h.by,
              })),
              ...row.history.filter((h) =>
                /Classified|Excluded|rejected/.test(h.what),
              ),
            ].map((h, i) => (
              <li key={i}>
                <span className="t-sm">{h.what}</span>
                <span className="muted t-xs">
                  {h.by} · {fmtStamp(h.at)}
                </span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </Fragment>
  );
}
type DocRef = Pick<Doc, "id" | "file" | "media" | "sha">;
export function DocsSection({ row }: { row: Movement }) {
  const [state, dispatch] = useStore();
  const page = usePage();
  const docs = state.data.docs;
  const ev = row.evidenceId ? docs.find((d) => d.id === row.evidenceId) : null;
  const atts: DocRef[] = row.attachments.map(
    (a) =>
      docs.find((d) => d.id === a) || {
        id: a,
        file: a === "att-renfe-email" ? "renfe-confirmacion-email.pdf" : a,
        media: "pdf",
        sha: hashHex(a),
      },
  );
  const free = docs.filter((d) => !d.rowId && d.id !== row.evidenceId);
  const [pick, setPick] = useState("");
  const [chooser, setChooser] = useState<HTMLElement | null>(null);
  const locked =
    row.lifecycle !== "active"
      ? "Only active movements take new documents."
      : null;
  const needsEvidence =
    row.lifecycle === "active" &&
    (row.cls === "business" || row.cls === "mixed") &&
    row.direction === "out" &&
    row.ivaCategory !== "domestic_exempt" &&
    !ev;
  const stageAttach = (doc: DocRef, asEvidence: boolean, newDoc?: Doc) =>
    dispatch({
      type: "STAGE_ACTION",
      action: {
        id: "attach-" + row.id + "-" + doc.id,
        type: "attach",
        rowIds: [row.id],
        label: `Attach ${doc.file} · ${row.description}`,
        tech: newDoc
          ? "ledger.evidence.add then ledger.attach"
          : "ledger.attach",
        payload: { docId: doc.id, file: doc.file, asEvidence, newDoc },
      },
    });
  const pending = state.staged.actions.filter(
    (a) =>
      a.rowIds.includes(row.id) && (a.type === "attach" || a.type === "detach"),
  );
  return (
    <Fragment>
      {row.sealed?.length ? (
        <p className="t-sm muted">
          Documents can still be attached to a sealed movement; the declarations
          that use it are told to recalculate.
        </p>
      ) : null}
      {ev ? (
        <div className="filechip">
          <Icon name={ev.media === "image" ? "image" : "page"} />
          <span className="f1 col">
            <span className="wrapt">{ev.file}</span>
            <span className="muted t-xs">
              Purchase invoice · added {fmtDateLong(ev.added)}
            </span>
          </span>
          <Button size="xs" variant="ghost" onClick={() => page.openDoc(ev.id)}>
            Open
          </Button>
          <Button
            size="xs"
            variant="ghost"
            disabled={!!locked}
            onClick={() =>
              dispatch({
                type: "STAGE_ACTION",
                action: {
                  id: "detach-" + row.id + "-" + ev.id,
                  type: "detach",
                  rowIds: [row.id],
                  label: `Detach ${ev.file}`,
                  tech: "ledger.detach · the document's file is kept",
                  payload: { docId: ev.id, file: ev.file, evidence: true },
                },
              })
            }
          >
            Detach
          </Button>
        </div>
      ) : needsEvidence ? (
        <Alert icon="info" title="No purchase invoice yet">
          Advisory only: a missing document never blocks saving or calculation,
          but keep the invoice for a review.
        </Alert>
      ) : (
        <p className="muted t-sm">
          No purchase invoice.{" "}
          {row.cls === "personal"
            ? "Personal movements need none."
            : row.direction === "in"
              ? "Income is evidenced by the issued invoice."
              : ""}
        </p>
      )}
      {atts.length ? (
        <ul className="list-rows">
          {atts.map((a) => (
            <li key={a.id}>
              <Icon name="attach" />
              <span className="f1 wrapt">{a.file}</span>
              <Button
                size="xs"
                variant="ghost"
                disabled={!!locked}
                onClick={() =>
                  dispatch({
                    type: "STAGE_ACTION",
                    action: {
                      id: "detach-" + row.id + "-" + a.id,
                      type: "detach",
                      rowIds: [row.id],
                      label: `Detach ${a.file}`,
                      tech: "ledger.detach",
                      payload: { docId: a.id, file: a.file },
                    },
                  })
                }
              >
                Detach
              </Button>
            </li>
          ))}
        </ul>
      ) : null}
      {pending.length ? (
        <p className="t-sm">
          {plural(pending.length, "document change")} · not saved.
        </p>
      ) : null}
      <div className="row g2">
        <div className="f1">
          <Select
            size="sm"
            value={pick}
            onChange={(e) => setPick(e.target.value)}
            aria-label="A document already in the ledger"
            disabled={!!locked}
          >
            <option value="">Attach an existing document…</option>
            {free.map((d) => (
              <option key={d.id} value={d.id}>
                {d.file}
              </option>
            ))}
          </Select>
        </div>
        <Button
          size="sm"
          variant="outline"
          disabled={!pick || !!locked}
          onClick={() => {
            const d = docs.find((x) => x.id === pick);
            if (d) stageAttach(d, !row.evidenceId && d.kind !== "issued");
            setPick("");
          }}
        >
          Attach
        </Button>
      </div>
      <Button
        size="sm"
        variant="outline"
        icon="folder"
        disabled={!!locked}
        onClick={(e) => setChooser(e.currentTarget)}
      >
        Add a document from this computer…
      </Button>
      <Hint text="PDF or image. The file is read from this computer and stored encrypted; a link or a web address is never stored." />
      {chooser ? (
        <HostFileDialog
          anchor={chooser}
          kind="document"
          onClose={() => setChooser(null)}
          onPick={(files) => {
            const f = files[0] ?? "";
            const nd: Doc = {
              id: "ev-new-" + hashHex(f, 6),
              file: f,
              media: /\.(jpe?g|png|heic)$/i.test(f) ? "image" : "pdf",
              added: TODAY,
              kind: "received",
              state: "evidence",
              draft: {},
              findings: [],
              sha: hashHex("new" + f),
              reviewSha: hashHex("r" + f),
            };
            stageAttach(nd, !row.evidenceId, nd);
            setChooser(null);
            page.toast(`${f}: attach staged`);
          }}
        />
      ) : null}
    </Fragment>
  );
}
/* M5: an approval answers the review with the classification fields;
   figures derived from registry rates are separate staged corrections. */
export function stageApproval(
  dispatch: Dispatch<Action>,
  row: Movement,
  sugg: Suggestion,
  share: number | null | undefined,
) {
  const fields: ApprovalFields = {
    cls: sugg.cls,
    share: sugg.cls === "mixed" ? (share ?? null) : null,
  };
  if (sugg.category) fields.category = sugg.category;
  if (sugg.ivaCategory) fields.ivaCategory = sugg.ivaCategory;
  const digest = sugg.digest || hashHex("rv" + row.id, 12);
  dispatch({
    type: "STAGE_ACTION",
    action: {
      id: "approve-" + row.id,
      type: "approve",
      rowIds: [row.id],
      label: `Approve the model's suggestion · ${row.description}`,
      tech: `ledger.classify.review · approve · review digest ${digest} · llm:local-medium`,
      payload: { fields, model: "local-medium", digest },
    },
  });
  const d = sugg.ivaCategory && deriveIva(row.amount, sugg.ivaCategory);
  if (d && row.direction !== "in")
    dispatch({
      type: "STAGE",
      label: "Figures worked out by Cadrumo",
      changes: [
        { id: row.id, field: "base", value: d.base, derived: true },
        { id: row.id, field: "ivaRate", value: d.ivaRate, derived: true },
        { id: row.id, field: "ivaAmount", value: d.ivaAmount, derived: true },
      ],
    });
}
export function SuggestionCard({
  s,
  onLink,
}: {
  s: Pair & { ambiguous?: boolean };
  onLink?: ReactNode;
}) {
  return (
    <div className="card-raised">
      <div className="row g2 wrap">
        <b className="fw6">{s.inv.number}</b>
        <span className="muted t-sm f1">{s.inv.counterparty}</span>
        {s.ambiguous ? <span className="badge warning">Ambiguous</span> : null}
      </div>
      <span className="t-sm muted">
        Issued {fmtDateLong(s.inv.date)} · {PAYMENT[s.inv.payment]} · settles{" "}
        {fmtMoney(s.settle)}
        {s.inv.retention
          ? ` (${fmtMoney(s.inv.total)} − ${fmtMoney(s.inv.retention)} retención)`
          : ""}
      </span>
      <div className="row g1 wrap">
        {s.chips.map((c) => (
          <span key={c} className="tag">
            {c}
          </span>
        ))}
      </div>
      {onLink ? <div className="row g2">{onLink}</div> : null}
    </div>
  );
}
export function stageLinkAction(
  dispatch: Dispatch<Action>,
  row: Movement,
  inv: Invoice,
  toast: (text: string) => void,
) {
  dispatch({
    type: "STAGE_ACTION",
    action: {
      id: "link-" + row.id,
      type: "link",
      rowIds: [row.id],
      label: `Link ${inv.number} · ${row.description}`,
      tech: "ledger.link · writes both sides at once · not retry-safe",
      payload: { invoiceId: inv.id, number: inv.number },
    },
  });
  toast("Link staged · permanent once saved");
}
/* What a link joins, both sides, and how they differ (M1). */
export function linkFacts(state: State, action: StagedAction) {
  const row = state.data.byId[action.rowIds[0] ?? ""];
  const inv = state.data.invoices.find(
    (i) => i.id === action.payload?.invoiceId,
  );
  if (!row || !inv) return { row, inv, settle: 0, chips: [] as string[] };
  const settle = inv.total - (inv.retention || 0);
  const a = (inv.counterparty || "").toLowerCase(),
    b = (row.counterparty || "").toLowerCase();
  const sameCp =
    !!a &&
    !!b &&
    (a.includes(b) || b.includes(a) || a.split(" ")[0] === b.split(" ")[0]);
  const chips: string[] = [];
  if (Math.abs(row.amount - settle) > 1)
    chips.push(`Amount differs by ${fmtMoney(Math.abs(row.amount - settle))}`);
  if (!sameCp) chips.push("Different counterparty");
  if (inv.linked.length) chips.push("Invoice also linked elsewhere");
  if (
    state.staged.actions.some(
      (x) =>
        x.type === "link" &&
        x.id !== action.id &&
        x.payload?.invoiceId === inv.id,
    )
  )
    chips.push("Invoice also staged for another movement");
  return { row, inv, settle, chips };
}
export function InvoiceSection({ row }: { row: Movement }) {
  const [state, dispatch] = useStore();
  const page = usePage();
  const toast = useToast();
  const recon = reconciliationSuggestions(state.data, state.staged.actions);
  const inv = row.invoiceId
    ? state.data.invoices.find((i) => i.id === row.invoiceId)
    : null;
  const best = recon.best[row.id];
  const [showOthers, setShowOthers] = useState(false);
  const [choice, setChoice] = useState("");
  const [pick, setPick] = useState("");
  const stagedLink = state.staged.actions.find(
    (a) => a.type === "link" && a.rowIds[0] === row.id,
  );
  const lock =
    row.lifecycle !== "active" ? "Only active movements can be linked." : null;
  if (row.direction === "transfer")
    return (
      <p className="muted">
        Transfers between your own accounts have no invoice.
      </p>
    );
  const link = (i: Invoice) => stageLinkAction(dispatch, row, i, toast);
  const invTies =
    best && best.ambiguous
      ? best.ties.filter((t) => t.rowId === row.id || t.rowId === undefined)
      : [];
  const rowTies =
    best && best.ambiguous
      ? best.ties.filter((t) => t.rowId && t.rowId !== row.id)
      : [];
  const candidates = best
    ? [
        best,
        ...invTies.map(
          (t) =>
            recon.pairs.find(
              (p) => p.rowId === row.id && p.invoiceId === t.invoiceId,
            ) || t,
        ),
      ]
    : [];
  const rival = rowTies[0] ? state.data.byId[rowTies[0].rowId] : null;
  // Invoices staged for another movement, by invoice (M1).
  const stagedFor: Record<string, Movement> = {};
  state.staged.actions
    .filter((a) => a.type === "link" && a.rowIds[0] !== row.id)
    .forEach((a) => {
      const by = state.data.byId[a.rowIds[0] ?? ""];
      if (a.payload?.invoiceId && by) stagedFor[a.payload.invoiceId] = by;
    });
  const flowOk = (i: Invoice) =>
    (i.kind === "issued") === (row.direction === "in");
  const settles = (i: Invoice) =>
    i.currency === row.currency &&
    Math.abs(row.amount - (i.total - (i.retention || 0))) <= 1;
  const pool = state.data.invoices.filter(flowOk);
  const groupA = pool.filter(settles),
    groupB = pool.filter((i) => !settles(i));
  const takenBy =
    !best && !stagedLink
      ? pool.flatMap((i) => {
          const by = stagedFor[i.id];
          return settles(i) && by ? [{ inv: i, by }] : [];
        })[0]
      : null;
  const opt = (i: Invoice) => (
    <option key={i.id} value={i.id} disabled={!!stagedFor[i.id]}>
      {i.number} · {i.counterparty} · {fmtMoney(i.total)} ·{" "}
      {fmtDateLong(i.date)}
      {stagedFor[i.id]
        ? ` · staged for ${stagedFor[i.id]!.description}`
        : i.linked.length
          ? ` · already linked to ${plural(i.linked.length, "movement")}`
          : ""}
    </option>
  );
  const partial =
    "Usually one movement settles one invoice. Link both only for partial payments.";
  if (inv)
    return (
      <Fragment>
        <div className="card-raised">
          <div className="row g2">
            <Icon name="receipt" />
            <b className="fw6">{inv.number}</b>
            <span className="tag">
              {inv.kind === "issued" ? "Issued" : "Received"}
            </span>
            <span className="f1"></span>
            <span className="tnum fw6">
              {fmtMoney(inv.total)} {inv.currency}
            </span>
          </div>
          <dl className="kv">
            <dt>Counterparty</dt>
            <dd>{inv.counterparty}</dd>
            <dt>Tax id</dt>
            <dd className="mono">{inv.nif || "None (simplificada)"}</dd>
            <dt>Issued</dt>
            <dd>{fmtDateLong(inv.date)}</dd>
            {inv.retention ? (
              <>
                <dt>Retención</dt>
                <dd className="tnum">
                  {fmtMoney(inv.retention)} ({pct(inv.retentionRate ?? 0)}),
                  outside the total
                </dd>
              </>
            ) : null}
            <dt>Payment</dt>
            <dd>{PAYMENT[inv.payment]}</dd>
            <dt>Movements</dt>
            <dd>{plural(inv.linked.length, "linked movement")}</dd>
          </dl>
          <div className="row g2">
            <Button
              size="sm"
              variant="outline"
              onClick={() => page.openInvoice(inv.id)}
            >
              Open invoice
            </Button>
          </div>
        </div>
        <p className="t-xs muted">
          <Icon name="lock" size="xs" /> A link is permanent: there is no way to
          remove it here, and a linked invoice cannot be removed.
        </p>
      </Fragment>
    );
  return (
    <Fragment>
      {stagedLink ? (
        <Alert icon="link" title="Link staged · permanent once saved">
          {stagedLink.label}.{" "}
          <Button
            size="xs"
            variant="ghost"
            onClick={() =>
              dispatch({ type: "UNSTAGE_ACTION", id: stagedLink.id })
            }
          >
            Drop it
          </Button>
        </Alert>
      ) : null}
      {takenBy ? (
        <Alert
          icon="link"
          title={`${takenBy.inv.number} is staged for ${takenBy.by.description}`}
        >
          {partial}{" "}
          <Button
            size="xs"
            variant="link"
            onClick={() => page.jumpTo(takenBy.by.id, "match")}
          >
            Show it
          </Button>
        </Alert>
      ) : null}
      {!stagedLink && best && best.ambiguous && !invTies.length ? (
        <div className="col g2">
          <Alert tone="warning" title="Ambiguous: another movement fits">
            {rival
              ? `${rival.description} · ${fmtDateLong(effDate(rival))} · ${fmtMoney(rival.amount)}`
              : "Another movement"}{" "}
            settles {best.inv.number} equally well. {partial}
          </Alert>
          <SuggestionCard
            s={{ ...best, ambiguous: false }}
            onLink={
              <>
                <Button
                  size="sm"
                  disabled={!!lock}
                  onClick={() => link(best.inv)}
                >
                  Link · permanent
                </Button>
                {rival ? (
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => page.jumpTo(rival.id, "match")}
                  >
                    Show the other
                  </Button>
                ) : null}
              </>
            }
          />
        </div>
      ) : !stagedLink && best ? (
        best.ambiguous ? (
          <div className="col g2">
            <Alert tone="warning" title="Ambiguous: choose the invoice">
              {plural(candidates.length, "invoice")} settle this movement
              equally well. Pick the right one; a link cannot be undone.
            </Alert>
            <div
              role="radiogroup"
              aria-label="Candidate invoices"
              className="col g2"
            >
              {candidates.map((c) => (
                <label
                  key={c.invoiceId}
                  className="row g2"
                  style={{ alignItems: "flex-start" }}
                >
                  <input
                    type="radio"
                    name={"ch-" + row.id}
                    checked={choice === c.invoiceId}
                    onChange={() => setChoice(c.invoiceId)}
                  />
                  <div className="f1">
                    <SuggestionCard s={{ ...c, ambiguous: false }} />
                  </div>
                </label>
              ))}
            </div>
            <div>
              <Button
                size="sm"
                disabled={!choice || !!lock}
                onClick={() => {
                  const found = state.data.invoices.find(
                    (i) => i.id === choice,
                  );
                  if (found) link(found);
                }}
              >
                Link · permanent
              </Button>
            </div>
          </div>
        ) : (
          <>
            <SuggestionCard
              s={best}
              onLink={
                <>
                  <Button
                    size="sm"
                    disabled={!!lock}
                    onClick={() => link(best.inv)}
                  >
                    Link · permanent
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => page.openInvoice(best.inv.id)}
                  >
                    Open invoice
                  </Button>
                </>
              }
            />
            {best.others.length ? (
              <Button
                size="xs"
                variant="link"
                aria-expanded={showOthers}
                onClick={() => setShowOthers(!showOthers)}
              >
                Other candidates ({best.others.length})
              </Button>
            ) : null}
            {showOthers
              ? best.others.map((o) => (
                  <SuggestionCard
                    key={o.invoiceId}
                    s={o}
                    onLink={
                      <Button
                        size="xs"
                        variant="outline"
                        onClick={() => link(o.inv)}
                      >
                        Link · permanent
                      </Button>
                    }
                  />
                ))
              : null}
          </>
        )
      ) : !stagedLink && !takenBy ? (
        <p className="muted t-sm">No catalogue invoice settles this amount.</p>
      ) : null}
      <div className="row g2">
        <div className="f1">
          <Select
            size="sm"
            value={pick}
            onChange={(e) => setPick(e.target.value)}
            aria-label="Invoice to link"
          >
            <option value="">
              Link another {row.direction === "in" ? "issued" : "received"}{" "}
              invoice…
            </option>
            {groupA.length ? (
              <optgroup label="Settles this amount">{groupA.map(opt)}</optgroup>
            ) : null}
            {groupB.length ? (
              <optgroup label="Other invoices">{groupB.map(opt)}</optgroup>
            ) : null}
          </Select>
        </div>
        <Button
          size="sm"
          variant="outline"
          disabled={!pick || !!stagedLink || !!lock}
          onClick={() => {
            const found = state.data.invoices.find((i) => i.id === pick);
            if (found) link(found);
            setPick("");
          }}
        >
          Link · permanent
        </Button>
      </div>
      <Button
        size="sm"
        variant="ghost"
        icon="plus"
        onClick={() => page.newInvoiceFor(row)}
      >
        New invoice from this movement
      </Button>
      <p className="t-xs muted">
        <Icon name="lock" size="xs" /> Links are permanent: there is no way to
        remove one here.
      </p>
    </Fragment>
  );
}
export function HistorySection({ row }: { row: Movement }) {
  const [state] = useStore();
  const page = usePage();
  const pend = diffOf(row, state.staged.rows[row.id]);
  const sibs = row.split
    ? row.split.role === "parent"
      ? row.split.children
      : row.split.siblings
    : [];
  return (
    <Fragment>
      <ul className="timeline">
        {pend.length ? (
          <li className="now">
            <span className="t-sm fw5">
              Not saved yet: {pend.map((k) => F[k]?.label || k).join(", ")}
            </span>
            <span className="muted t-xs">this window</span>
          </li>
        ) : null}
        {[...row.history].reverse().map((h, i) => (
          <li key={i}>
            <span className="t-sm">{h.what}</span>
            <span className="muted t-xs">
              {h.by} · {fmtStamp(h.at)}
            </span>
          </li>
        ))}
      </ul>
      {sibs.length ? (
        <div className="sub-sec">
          <div className="sub-title">
            {row.split?.role === "parent"
              ? "Parts"
              : "Split from the same movement"}
          </div>
          <ul className="list-rows">
            {(row.split?.role === "child"
              ? [row.split.parent, ...sibs]
              : sibs
            ).map((id) => {
              const r = state.data.byId[id];
              return r ? (
                <li key={id}>
                  <span className="f1 wrapt">{r.description}</span>
                  <span className="tnum">{fmtMoney(r.amount)}</span>
                  <Button
                    size="xs"
                    variant="ghost"
                    onClick={() => page.jumpTo(id)}
                  >
                    Show
                  </Button>
                </li>
              ) : null;
            })}
          </ul>
        </div>
      ) : null}
    </Fragment>
  );
}
export function UsesSection({ row }: { row: Movement }) {
  const page = usePage();
  return (
    <Fragment>
      {row.uses.length ? (
        <ul className="list-rows">
          {row.uses.map((u, i) => (
            <li key={i}>
              <Icon
                name={u.state === "draft" ? "page" : "lock"}
                className={u.state === "draft" ? "muted" : ""}
              />
              <span className="f1 col">
                <span className="fw5">
                  Modelo {u.modelo} · {u.period}
                </span>
                <span className="muted t-sm">{u.label}</span>
              </span>
              <span className="col" style={{ alignItems: "flex-end" }}>
                <Badge variant={u.state === "draft" ? "neutral" : "inverse"}>
                  {SEAL_LABEL[u.state]}
                </Badge>
                <Button
                  size="xs"
                  variant="link"
                  onClick={() =>
                    page.toast(
                      `Opens Modelo ${u.modelo} · ${u.period} in Declarations (another page of the window)`,
                    )
                  }
                >
                  Open in Declarations ›
                </Button>
              </span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="muted">No declaration uses this movement yet.</p>
      )}
      <Hint text="A filed or fully verified declaration seals the movements it used. A draft only goes stale when they change. Filing locally is not the AEAT's confirmation: the receipt is." />
    </Fragment>
  );
}
export function DraftInspector({ draft }: { draft: Draft }) {
  const [, dispatch] = useStore();
  const stage = (changes: StageChange[], label: string) =>
    dispatch({ type: "STAGE", changes, label });
  // A draft reads as a movement with the fields it has so far.
  const row = {
    ...draft.fields,
    key: draft.key,
    id: draft.key,
  } as unknown as Movement;
  const fp = { row, staged: {}, isDraft: true, dispatchStage: stage };
  const missing = DRAFT_REQUIRED.filter(
    (k) => draft.fields[k] == null || draft.fields[k] === "",
  );
  return (
    <Fragment>
      <InspHead
        title={draft.fields.description || "New movement"}
        sub="Draft · not saved yet"
      />
      <div className="insp-body" tabIndex={0} aria-label="New movement fields">
        {missing.length ? (
          <Alert tone="warning" title="Required before it can be saved">
            {missing.map((k) => F[k]!.label).join(", ")}
          </Alert>
        ) : (
          <Alert tone="success" title="Ready to add">
            It is added when you save your changes.
          </Alert>
        )}
        <dl className="kv">
          {[
            "date",
            "description",
            "amount",
            "direction",
            "counterparty",
            "account",
            "currency",
            "valueDate",
            "cls",
            "category",
            "ivaCategory",
            "base",
            "ivaRate",
            "ivaAmount",
            "recargo",
            "irpf",
            "usageRatio",
            "counterpartyCountry",
            "idState",
            "sourceJurisdiction",
            "prorrataSector",
            "notes",
          ].map((k) => (
            <InspField
              key={k}
              k={k}
              label={F[k]!.label + (DRAFT_REQUIRED.includes(k) ? " *" : "")}
              {...fp}
            />
          ))}
        </dl>
        <Hint text="A group label and documents are added after saving. A retry never adds the movement twice." />
        <details className="tech">
          <summary>Technical details</summary>
          <p className="mono t-xs">ledger.add · idempotency key {draft.idem}</p>
        </details>
        <div className="row g2">
          <Button
            size="sm"
            variant="outline"
            icon="trash"
            onClick={() => dispatch({ type: "REMOVE_DRAFT", key: draft.key })}
          >
            Remove draft
          </Button>
        </div>
      </div>
    </Fragment>
  );
}

/* ── Many movements at once (R7, R8). ────────────────────────────────── */
export function MultiInspector({ ids }: { ids: string[] }) {
  const [state, dispatch] = useStore();
  const page = usePage();
  const visible = new Set(page.visibleIds());
  const rows = ids.flatMap((id) => state.data.byId[id] ?? []);
  const effs = rows.map((r) =>
    effective(r, state.staged.rows, state.staged.actions),
  );
  const vis = rows.filter((r) => visible.has(r.id)).length;
  const hidden = rows.length - vis;
  const [cost, setCost] = useState<{
    field: string;
    value: Value;
    extra: [string, Value][];
    singles: number;
  } | null>(null);
  const [group, setGroup] = useState("");
  const [notes, setNotes] = useState("");
  const setLabel = (n: number) =>
    hidden
      ? `Set for ${n - hidden} visible + ${hidden} hidden`
      : `Set for ${n}`;
  const eligibleFor = (field: string, value: Value) =>
    rows.filter((r) => {
      const e = effective(r, state.staged.rows);
      if (lockReason(e, field, false, state.staged.actions)) return false;
      if (field === "cls" && e.direction === "transfer" && value !== "personal")
        return false;
      if (
        F[field]?.tax &&
        field !== "irpf" &&
        (value === "personal" || e.cls === "personal")
      )
        return false;
      if (field === "irpf" && e.cls === "personal") return false;
      return true;
    });
  const stageField = (
    field: string,
    value: Value,
    extra: [string, Value][] = [],
    force?: boolean,
  ) => {
    const el = eligibleFor(field, value);
    const skipped = rows.length - el.length;
    const changes: StageChange[] = [];
    el.forEach((r) => {
      changes.push({ id: r.id, field, value });
      extra.forEach(([f, v]) => changes.push({ id: r.id, field: f, value: v }));
    });
    // A change that would go out as many single writes says so first.
    const singles = el.filter((r) => {
      const e = effective(r, state.staged.rows);
      const cl = CLASSIFIED.has(field === "cls" ? String(value) : e.cls);
      return routeField(field, value, cl, false) !== "bulk";
    }).length;
    if (!force && singles > 10) {
      setCost({ field, value, extra, singles });
      return;
    }
    dispatch({
      type: "STAGE",
      changes,
      label: `Set ${F[field]!.label.toLowerCase()} for ${el.length}`,
    });
    page.toast(
      `${F[field]!.label} for ${plural(el.length, "movement")} · not saved${skipped ? ` (${skipped} skipped: sealed, read-only, Personal or transfers)` : ""}`,
    );
    setCost(null);
  };
  const common = (k: string) => {
    const vals = [...new Set(effs.map((r) => getField(r, k) ?? null))];
    return vals.length === 1
      ? { one: true, v: vals[0], n: 1 }
      : { one: false, v: undefined, n: vals.length };
  };
  const byCls: Record<string, number> = {};
  rows.forEach((r) => (byCls[r.cls] = (byCls[r.cls] || 0) + 1));
  const bySt: Record<string, number> = {};
  rows.forEach((r) => {
    const s = statusOf(r, state.check).key;
    bySt[s] = (bySt[s] || 0) + 1;
  });
  const sealedN = rows.filter(
    (r) => r.sealed?.length || r.lifecycle !== "active",
  ).length;
  const parents = [
    ...new Set(
      rows.flatMap((r) => (r.split?.role === "child" ? [r.split.parent] : [])),
    ),
  ];
  const parentSplit = state.data.byId[parents[0] ?? ""]?.split;
  const cohort =
    parents.length === 1 &&
    parentSplit?.role === "parent" &&
    parentSplit.children.every((c) => ids.includes(c));
  const disabled = vis === 0;
  const commonRow = (k: string, label: string) => {
    const c = common(k);
    return (
      <Fragment key={k}>
        <dt>{label}</dt>
        <dd>
          {c.one ? (
            c.v == null ? (
              <span className="muted">Not set</span>
            ) : (
              show(k, c.v, effs[0], true)
            )
          ) : (
            <span className="muted">Mixed · {c.n} values</span>
          )}
        </dd>
      </Fragment>
    );
  };
  return (
    <Fragment>
      <InspHead
        title={plural(rows.length, "movement") + " selected"}
        sub={
          sealedN
            ? `${sealedN} sealed or not active: changes skip them`
            : "Changes reach every selected movement that can take them."
        }
      >
        <div className="row g2" style={{ marginTop: "var(--spacing)" }}>
          <Button
            size="xs"
            variant="ghost"
            onClick={() => dispatch({ type: "SELECT", mode: "clear", ids: [] })}
          >
            Clear selection
          </Button>
        </div>
      </InspHead>
      <div className="insp-body" tabIndex={0} aria-label="Selection">
        {page.windowInfo?.truncated ? (
          <Alert
            icon="info"
            title={`Loaded rows only: ${page.windowInfo.loaded} of ${page.windowInfo.total}`}
          />
        ) : null}
        {hidden ? (
          <Alert
            tone="warning"
            title={`${hidden} of ${rows.length} selected are hidden`}
          >
            {disabled
              ? "None of the selected movements is visible: bulk changes wait until you choose."
              : "Bulk changes would also reach the hidden ones."}
            <div className="row g2" style={{ marginTop: "var(--spacing)" }}>
              <Button
                size="xs"
                variant="outline"
                onClick={() => page.showSelected()}
              >
                Show them
              </Button>
              <Button
                size="xs"
                variant="ghost"
                onClick={() =>
                  dispatch({
                    type: "SELECT",
                    mode: "set",
                    ids: rows.filter((r) => visible.has(r.id)).map((r) => r.id),
                  })
                }
              >
                Keep only visible
              </Button>
            </div>
          </Alert>
        ) : null}
        <section className="sec">
          <h3 className="sec-title">Totals</h3>
          <div className="card-wash">
            <SumLine sums={sumsOf(rows)} />
          </div>
          <div className="row g2 wrap t-sm">
            {Object.entries(byCls).map(([k, n]) => (
              <span key={k} className="cls">
                <span
                  className={cx("cls-mark", CLASSIFIED.has(k) ? k : "none")}
                ></span>
                {CLS[k as Cls].label} <b className="tnum">{n}</b>
              </span>
            ))}
          </div>
          <div className="row g2 wrap t-sm muted">
            {Object.entries(bySt).map(([k, n]) => (
              <span key={k}>
                {STATUS_FILTERS[k]}{" "}
                <b className="tnum" style={{ color: "var(--foreground)" }}>
                  {n}
                </b>
              </span>
            ))}
          </div>
        </section>
        <section className="sec">
          <h3 className="sec-title">Common values</h3>
          <dl className="kv">
            {commonRow("cls", "Classification")}
            {commonRow("category", "Category")}
            {commonRow("ivaCategory", "IVA category")}
            {commonRow("irpf", "IRPF category")}
            {commonRow("direction", "Direction")}
            {commonRow("account", "Account")}
            {commonRow("group", "Group label")}
          </dl>
        </section>
        <section className="sec">
          <h3 className="sec-title">Set for all · applies as you choose</h3>
          {cost ? (
            <Alert
              tone="warning"
              title={`${cost.singles} would be saved one at a time`}
            >
              That is about {Math.ceil((cost.singles * SINGLE_SECONDS) / 60)}{" "}
              minutes. Classifying them first lets the ledger save them
              together.
              <div className="row g2" style={{ marginTop: "var(--spacing)" }}>
                <Button
                  size="xs"
                  onClick={() =>
                    stageField(cost.field, cost.value, cost.extra, true)
                  }
                >
                  Stage anyway
                </Button>
                <Button size="xs" variant="ghost" onClick={() => setCost(null)}>
                  Classify first
                </Button>
              </div>
            </Alert>
          ) : null}
          <div className="row g2 wrap" style={{ alignItems: "center" }}>
            <Seg
              size="sm"
              label="Classification for all"
              value=""
              options={[
                { value: "business", label: "Business…", disabled },
                { value: "personal", label: "Personal", disabled },
                { value: "mixed", label: "Mixed…", disabled },
              ]}
              onChange={(v) => page.classifySelection(v)}
            />
          </div>
          {(
            [
              [
                "category",
                "Category",
                FAMILIES.map(([, l, cs]) => [
                  l,
                  cs.map((c) => [c, CATEGORY_LABEL[c]]),
                ]),
              ],
              [
                "ivaCategory",
                "IVA category",
                IVA_GROUPS.map(([g, it]) => [g, it.map(([k, l]) => [k, l])]),
              ],
              ["irpf", "IRPF category", [["", Object.entries(IRPF)]]],
            ] as [string, string, [string, [string, string][]][]][]
          ).map(([k, label, groups]) => (
            <Field
              key={k}
              label={`${label} · ${setLabel(eligibleFor(k, "x").length).toLowerCase()}${rows.length - eligibleFor(k, "x").length ? ` (${rows.length - eligibleFor(k, "x").length} skipped)` : ""}`}
            >
              <Select
                size="sm"
                value=""
                disabled={disabled}
                onChange={(e) =>
                  e.target.value && stageField(k, e.target.value)
                }
              >
                <option value="">Choose to apply…</option>
                {groups.map(([g, opts]) =>
                  g ? (
                    <optgroup key={g} label={g}>
                      {opts.map(([o, l]) => (
                        <option key={o} value={o}>
                          {l}
                        </option>
                      ))}
                    </optgroup>
                  ) : (
                    opts.map(([o, l]) => (
                      <option key={o} value={o}>
                        {l}
                      </option>
                    ))
                  ),
                )}
              </Select>
            </Field>
          ))}
          <div className="row g2" style={{ alignItems: "end" }}>
            <Field
              label="Group label"
              className="f1"
              hint="Up to 64 characters"
            >
              <Input
                size="sm"
                value={group}
                maxLength={64}
                onChange={(e) => setGroup(e.target.value)}
              />
            </Field>
            <Button
              size="sm"
              variant="outline"
              disabled={!group.trim() || disabled}
              onClick={() => stageField("group", group.trim())}
            >
              {setLabel(eligibleFor("group", group).length)}
            </Button>
          </div>
          <div className="row g2" style={{ alignItems: "end" }}>
            <Field label="Notes" className="f1">
              <Input
                size="sm"
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
              />
            </Field>
            <Button
              size="sm"
              variant="outline"
              disabled={!notes.trim() || disabled}
              onClick={() => stageField("notes", notes.trim())}
            >
              {setLabel(eligibleFor("notes", notes).length)}
            </Button>
          </div>
        </section>
        <section className="sec">
          <h3 className="sec-title">Actions</h3>
          <div className="row g2 wrap">
            <Button
              size="sm"
              variant="outline"
              icon="archive"
              disabled={disabled}
              onClick={() => page.openAction("archive", ids)}
            >
              Archive…
            </Button>
            <Button
              size="sm"
              variant="outline"
              icon="stash"
              disabled={disabled}
              onClick={() => page.openAction("stash", ids)}
            >
              Set aside…
            </Button>
            <Button
              size="sm"
              variant="outline"
              icon="eyeOff"
              disabled={disabled}
              onClick={() => page.openAction("exclude", ids)}
            >
              Exclude…
            </Button>
            <Button
              size="sm"
              variant="outline"
              icon="unarchive"
              disabled={disabled}
              onClick={() => page.openAction("restore", ids)}
            >
              Restore…
            </Button>
            <Button
              size="sm"
              variant="outline"
              icon="merge"
              disabled={!cohort}
              data-tip={
                cohort
                  ? undefined
                  : "Select every part of one split movement to merge them."
              }
              onClick={() => page.openAction("merge", ids)}
            >
              Merge parts…
            </Button>
          </div>
          <div className="row g2 wrap">
            <Button
              size="sm"
              variant="outline"
              icon="agent"
              disabled={disabled}
              onClick={() => page.openDialog("rule", { rows })}
            >
              Make a rule…
            </Button>
            <Button
              size="sm"
              variant="outline"
              icon="agent"
              disabled={state.proto.state === "modelUnavailable" || disabled}
              onClick={() =>
                page.askModel(ids.filter((id) => visible.has(id) || !hidden))
              }
            >
              Ask the model for each
            </Button>
            <Button
              size="sm"
              variant="outline"
              icon="copy"
              onClick={() => page.copyRows(ids)}
            >
              Copy as TSV
            </Button>
            <Button
              size="sm"
              variant="outline"
              icon="download"
              onClick={() => page.openDialog("export", { selection: ids })}
            >
              Export…
            </Button>
          </div>
        </section>
      </div>
    </Fragment>
  );
}
