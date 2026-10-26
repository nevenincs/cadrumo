import { useContext, createContext, type Dispatch } from "react";
import { CATEGORY_LABEL, CLASSIFIED, CLS, IVA_LABEL } from "./vocab";
import type {
  Check,
  Cls,
  Conflict,
  Direction,
  DataState,
  Movement,
  Paused,
  ProtoState,
  Snapshot,
  StagedAction,
  State,
  Value,
  View,
} from "./types";
import {
  F,
  EMPTY_FILTERS,
  effDate,
  getField,
  isIdentity,
  issuesOf,
  sameValue,
  setField,
  shortId,
  show,
} from "./model";
import {
  ACCOUNTS,
  ASSETS,
  CAPITAL_GOODS,
  CONSENT,
  COUNTERPARTIES,
  INVENTORY,
  PRORRATA,
  RATIOS,
  RULES,
  buildData,
  hashHex,
} from "./data";

/* ── The page store. Ledger facts, staged changes and the view all live in
   memory only: nothing is written to window storage, so every story starts
   from the same page. ───────────────────────────────────────────────── */
export let CLOCK = Date.parse("2026-10-23T11:02:00Z");
export const NOW = () => {
  CLOCK += 7000;
  return new Date(CLOCK).toISOString().replace(/\.\d+Z$/, "Z");
};

export const STICKY: string[] = ["select", "status", "date", "amount"];
export const DEFAULT_COLUMNS: string[] = [
  "select",
  "status",
  "date",
  "amount",
  "match",
  "description",
  "counterparty",
  "direction",
  "eur",
  "cls",
  "category",
  "share",
  "usageRatio",
  "ivaCategory",
  "base",
  "ivaRate",
  "ivaAmount",
  "recargo",
  "irpf",
  "invoice",
  "docs",
  "account",
  "group",
  "notes",
  "lifecycle",
  "classifiedBy",
  "modified",
];
export const PRESETS: Record<string, { label: string; cols: string[] }> = {
  default: {
    label: "Default",
    cols: [
      "select",
      "status",
      "date",
      "amount",
      "description",
      "counterparty",
      "direction",
      "cls",
      "category",
      "group",
    ],
  },
  review: {
    label: "Review",
    cols: [
      "select",
      "status",
      "date",
      "amount",
      "description",
      "counterparty",
      "direction",
      "eur",
      "cls",
      "category",
      "invoice",
      "docs",
      "notes",
    ],
  },
  iva: {
    label: "IVA",
    cols: [
      "select",
      "status",
      "date",
      "amount",
      "description",
      "counterparty",
      "eur",
      "cls",
      "ivaCategory",
      "base",
      "ivaRate",
      "ivaAmount",
      "recargo",
      "invoice",
    ],
  },
  mixed: {
    label: "Mixed use",
    cols: [
      "select",
      "status",
      "date",
      "amount",
      "description",
      "counterparty",
      "cls",
      "category",
      "share",
      "usageRatio",
    ],
  },
  irpf: {
    label: "IRPF",
    cols: [
      "select",
      "status",
      "date",
      "amount",
      "description",
      "counterparty",
      "direction",
      "cls",
      "category",
      "irpf",
      "account",
      "group",
    ],
  },
  match: {
    label: "Matching",
    cols: [
      "select",
      "status",
      "date",
      "amount",
      "description",
      "counterparty",
      "direction",
      "match",
      "invoice",
      "docs",
    ],
  },
  all: { label: "Everything", cols: DEFAULT_COLUMNS },
};
/* Widths in px at a 16px root: rem tokens × 16. Description and
   counterparty take what is left (flex), above their minimum. */
export const COL_WIDTH: Record<string, number> = {
  select: 36,
  status: 120,
  date: 72,
  description: 192,
  counterparty: 144,
  direction: 80,
  amount: 104,
  eur: 104,
  match: 176,
  cls: 128,
  category: 184,
  share: 96,
  usageRatio: 160,
  ivaCategory: 184,
  base: 104,
  ivaRate: 72,
  ivaAmount: 92,
  recargo: 84,
  irpf: 160,
  invoice: 120,
  docs: 92,
  account: 136,
  group: 144,
  notes: 208,
  lifecycle: 96,
  classifiedBy: 132,
  modified: 120,
};
export const COL_FLEX: Record<string, number> = {
  description: 2,
  counterparty: 1.5,
};
export const COL_LABEL: Record<string, string> = {
  select: "Select",
  status: "Status",
  date: "Date",
  description: "Description",
  counterparty: "Counterparty",
  direction: "Direction",
  amount: "Amount",
  eur: "EUR value",
  match: "Match",
  cls: "Classification",
  category: "Category",
  share: "Business share",
  usageRatio: "Usage ratio",
  ivaCategory: "IVA category",
  base: "Taxable base",
  ivaRate: "IVA rate",
  ivaAmount: "IVA",
  recargo: "Recargo",
  irpf: "IRPF category",
  invoice: "Invoice",
  docs: "Documents",
  account: "Account",
  group: "Group label",
  notes: "Notes",
  lifecycle: "State",
  classifiedBy: "Classified by",
  modified: "Modified",
};

export function runCheck(byId: Record<string, Movement>, at: string): Check {
  const issues: Record<string, string[]> = {};
  Object.values(byId).forEach((r) => {
    if (
      CLASSIFIED.has(r.cls) ||
      ["pending", "unclassified", "failed"].includes(r.cls)
    )
      issues[r.id] = issuesOf(r);
  });
  return { at, issues, changedSince: 0 };
}
export function initState(): State {
  const d = buildData();
  const byId: Record<string, Movement> = {};
  d.rows.forEach((r) => (byId[r.id] = r));
  return {
    data: {
      byId,
      order: d.rows.map((r) => r.id),
      invoices: d.invoices,
      docs: d.docs,
      batches: d.batches,
      rules: RULES.slice(),
      ratios: structuredClone(RATIOS),
      accounts: ACCOUNTS.map((a) => ({ ...a })),
      counterparties: COUNTERPARTIES.map((c) => ({ ...c })),
      prorrata: PRORRATA.map((p) => ({ ...p })),
      capital: CAPITAL_GOODS.slice(),
      inventory: structuredClone(INVENTORY),
      assets: ASSETS.slice(),
      consent: CONSENT.slice(),
      dupA: d.dupA.id,
    },
    readAt: "2026-10-23T10:41:00Z",
    check: runCheck(byId, "2026-10-23T10:41:00Z"),
    staged: { rows: {}, drafts: [], actions: [] },
    undo: [],
    redo: [],
    appliedAt: null,
    refusals: {},
    outcomes: {},
    unknownNotes: [],
    paused: null,
    selection: {},
    view: {
      period: { year: 2026, code: "4T" },
      search: "",
      filters: { ...EMPTY_FILTERS },
      savedView: "all",
      groupBy: "none",
      collapsed: {},
      sort: { key: "date", dir: "desc" },
      order: DEFAULT_COLUMNS,
      visible: PRESETS.default!.cols,
      preset: "default",
      widths: {},
      density: "compact",
      inspector: true,
      inspectorW: null,
      loaded: 250,
      missingMark: null,
    },
    proto: { state: "normal", outcome: "mix", unknownResolves: "saved" },
    draftN: 0,
  };
}

export function snapshot(s: State, label: string): Snapshot {
  return { staged: s.staged, label };
}
export function withRowStaged(
  rows: Record<string, Record<string, Value>>,
  id: string,
  field: string,
  value: Value,
  base: Movement,
) {
  const cur = { ...(rows[id] || {}) };
  if (sameValue(getField(base, field), value)) delete cur[field];
  else cur[field] = value;
  const out = { ...rows };
  if (Object.keys(cur).length) out[id] = cur;
  else delete out[id];
  return out;
}
export function describeChange(base: Movement, nb: Movement, fields: string[]) {
  return fields
    .filter((k) => F[k])
    .map(
      (k) =>
        `${F[k]!.label}: ${show(k, getField(base, k), base, true) || "empty"} → ${show(k, getField(nb, k), nb, true) || "empty"}`,
    )
    .join("; ");
}

/* Writes the staged fields of one row into the stored facts, as a saved
   operation would, following the new identity when it changes. */
export function commitRow(
  s: State,
  id: string,
  fields: string[],
  by = "You",
): State {
  const base = s.data.byId[id];
  if (!base) return s;
  const st = s.staged.rows[id] || {};
  let nb = { ...base };
  const done = fields.filter((f) => f in st);
  done.forEach((f) => (nb = setField(nb, f, st[f])));
  const now = NOW();
  nb.modified = now;
  if (
    done.some((f) => f === "cls" || f === "category" || f === "ivaCategory")
  ) {
    nb.classifiedBy = "manual";
    nb.classifiedAt = now;
    nb.suggestion = null;
  }
  if (nb.cls !== "mixed") nb.share = null;
  nb.history = [
    ...base.history,
    { at: now, what: describeChange(base, nb, done) || "Saved", by },
  ];
  let newId = id;
  if (done.some((f) => isIdentity(f, base))) {
    newId = hashHex(
      [nb.amount, nb.description, nb.providerId, effDate(nb), nb.account].join(
        "|",
      ),
    );
    nb.id = newId;
    nb.lineage = [...(base.lineage || []), { prev: id, at: now }];
    nb.history.push({
      at: now,
      what: `Saved under a new reference ${shortId(newId)} (previously ${shortId(id)})`,
      by: "Ledger",
    });
  }
  return rekey(s, id, newId, nb, (left) => {
    done.forEach((f) => delete left[f]);
    return left;
  });
}
export function rekey(
  s: State,
  id: string,
  newId: string,
  nb: Movement,
  trim: (left: Record<string, Value>) => Record<string, Value>,
): State {
  const base = s.data.byId[id];
  if (!base) return s;
  const byId = { ...s.data.byId };
  let order = s.data.order;
  if (newId !== id) {
    delete byId[id];
    order = order.map((x) => (x === id ? newId : x));
  }
  byId[newId] = nb;
  const rows = { ...s.staged.rows };
  const left = trim({ ...(rows[id] || {}) });
  delete rows[id];
  if (Object.keys(left).length) rows[newId] = left;
  const selection = { ...s.selection };
  if (newId !== id && selection[id]) {
    delete selection[id];
    selection[newId] = true;
  }
  const invoices =
    newId !== id && base.invoiceId
      ? s.data.invoices.map((inv) =>
          inv.id === base.invoiceId
            ? { ...inv, linked: inv.linked.map((x) => (x === id ? newId : x)) }
            : inv,
        )
      : s.data.invoices;
  const actions =
    newId !== id
      ? s.staged.actions.map((a) =>
          a.rowIds.includes(id)
            ? { ...a, rowIds: a.rowIds.map((x) => (x === id ? newId : x)) }
            : a,
        )
      : s.staged.actions;
  return {
    ...s,
    data: { ...s.data, byId, order, invoices },
    staged: { ...s.staged, rows, actions },
    selection,
    rekeyed: newId !== id ? { from: id, to: newId } : s.rekeyed,
  };
}

export function applyAction(s: State, a: StagedAction): State {
  const byId = { ...s.data.byId };
  let order = s.data.order;
  let invoices = s.data.invoices,
    docs = s.data.docs,
    rules = s.data.rules;
  const now = NOW();
  const hist = (r: Movement, what: string, by = "You"): Movement => ({
    ...r,
    modified: now,
    history: [...r.history, { at: now, what, by }],
  });
  const p = a.payload || {};
  const why = p.reason ? `: ${p.reason}` : "";
  switch (a.type) {
    case "archive":
    case "stash":
    case "restore":
    case "exclude":
      a.rowIds.forEach((id) => {
        const r = byId[id];
        if (!r) return;
        if (a.type === "exclude")
          byId[id] = hist(
            {
              ...r,
              cls: "excluded",
              classifiedBy: "manual",
              classifiedAt: now,
            },
            `Excluded from filing${why}`,
          );
        else
          byId[id] = hist(
            {
              ...r,
              lifecycle:
                a.type === "archive"
                  ? "archived"
                  : a.type === "stash"
                    ? "stashed"
                    : "active",
              issue:
                a.type === "archive" && r.issue === "duplicate"
                  ? null
                  : r.issue,
            },
            `${a.type === "restore" ? "Restored" : a.type === "archive" ? "Archived" : "Set aside"}${why}`,
          );
      });
      break;
    case "keepBoth": {
      const r = byId[a.rowIds[0] ?? ""];
      if (r)
        byId[r.id] = hist({ ...r, issue: null }, "Kept both: not a duplicate");
      break;
    }
    case "approve": {
      const r = byId[a.rowIds[0] ?? ""];
      if (!r) break;
      const f = p.fields;
      if (!f) break;
      byId[r.id] = hist(
        {
          ...r,
          ...f,
          share: f.cls === "mixed" ? (f.share ?? null) : null,
          classifiedBy: "llm:" + p.model,
          classifiedAt: now,
          suggestion: null,
        },
        `Classified ${CLS[f.cls].label}${f.category ? " · " + CATEGORY_LABEL[f.category] : ""}${f.ivaCategory ? " · " + IVA_LABEL[f.ivaCategory] : ""}`,
        `Model · llm:${p.model} · approved by you`,
      );
      break;
    }
    case "rules":
      if (p.newRule)
        rules = [...rules, p.newRule].sort(
          (x, y) => (x.priority ?? 0) - (y.priority ?? 0),
        );
      (p.matches ?? []).forEach((m) => {
        const r = byId[m.id];
        if (!r) return;
        byId[m.id] = hist(
          {
            ...r,
            cls: m.cls,
            category: m.category || r.category,
            classifiedBy: "rule:" + m.rule,
            classifiedAt: now,
          },
          `Classified ${CLS[m.cls].label} by the rule “${m.pattern}”`,
          "Rule",
        );
      });
      break;
    case "split": {
      const r = byId[a.rowIds[0] ?? ""];
      if (!r) break;
      const kids = (p.children ?? []).map((c, i): Movement => {
        const cls = c.cls || "pending";
        return {
          ...r,
          id: hashHex(r.id + "child" + i + c.description),
          amount: c.amount,
          description: c.description,
          cls,
          category: c.category || null,
          ivaCategory: null,
          base: null,
          ivaRate: null,
          ivaAmount: null,
          share: null,
          invoiceId: null,
          evidenceId: null,
          attachments: [],
          lifecycle: "active",
          sealed: null,
          uses: [],
          suggestion: null,
          created: now,
          modified: now,
          classifiedBy: c.cls ? "manual" : "auto",
          classifiedAt: c.cls ? now : null,
          history: [
            {
              at: now,
              what: `Created by splitting ${r.description}${why}`,
              by: "You",
            },
            ...(c.cls
              ? [
                  {
                    at: now,
                    what: `Classified ${CLS[cls].label}${c.category ? " · " + CATEGORY_LABEL[c.category] : ""}, after the split`,
                    by: "You",
                  },
                ]
              : []),
          ],
        };
      });
      kids.forEach((k) => {
        k.split = {
          role: "child",
          parent: r.id,
          siblings: kids.map((x) => x.id),
        };
        byId[k.id] = k;
      });
      byId[r.id] = hist(
        {
          ...r,
          lifecycle: "split",
          split: { role: "parent", children: kids.map((k) => k.id) },
        },
        `Split into ${kids.length} parts${why}`,
      );
      const at = order.indexOf(r.id);
      order = [
        ...order.slice(0, at + 1),
        ...kids.map((k) => k.id),
        ...order.slice(at + 1),
      ];
      break;
    }
    case "merge": {
      const kid = byId[a.rowIds[0] ?? ""];
      const parentId = kid?.split?.role === "child" ? kid.split.parent : "";
      const parent = byId[parentId];
      if (!parent) break;
      const children =
        parent.split?.role === "parent" ? parent.split.children : [];
      children.forEach((cid) => {
        delete byId[cid];
      });
      order = order.filter((x) => !children.includes(x));
      byId[parentId] = hist(
        { ...parent, lifecycle: "active", split: null },
        `Parts merged back${why}`,
      );
      break;
    }
    case "link": {
      const r = byId[a.rowIds[0] ?? ""];
      if (!r) break;
      byId[r.id] = hist(
        { ...r, invoiceId: p.invoiceId ?? null },
        `Linked to invoice ${p.number} (permanent)`,
      );
      invoices = invoices.map((inv) =>
        inv.id === p.invoiceId
          ? { ...inv, linked: [...new Set([...inv.linked, r.id])] }
          : inv,
      );
      break;
    }
    case "attach": {
      const r = byId[a.rowIds[0] ?? ""];
      if (!r) break;
      byId[r.id] = hist(
        p.asEvidence
          ? { ...r, evidenceId: p.docId ?? null }
          : { ...r, attachments: [...r.attachments, p.docId ?? ""] },
        `Attached ${p.file}`,
      );
      docs = docs.map((d) =>
        d.id === p.docId
          ? {
              ...d,
              rowId: r.id,
              state: d.state === "draft" ? d.state : "evidence",
            }
          : d,
      );
      if (p.newDoc) docs = [...docs, { ...p.newDoc, rowId: r.id }];
      break;
    }
    case "detach": {
      const r = byId[a.rowIds[0] ?? ""];
      if (!r) break;
      byId[r.id] = hist(
        p.evidence
          ? { ...r, evidenceId: null }
          : { ...r, attachments: r.attachments.filter((x) => x !== p.docId) },
        `Detached ${p.file} (its file is kept)`,
      );
      break;
    }
    case "reject": {
      const r = byId[a.rowIds[0] ?? ""];
      if (!r) break;
      byId[r.id] = {
        ...r,
        suggestion: null,
        modelRejected: true,
        history: [
          ...r.history,
          {
            at: now,
            what: `Model suggestion rejected: ${p.reason}`,
            by: `You · about llm:${p.model || "local-medium"}`,
          },
        ],
      };
      break;
    }
    case "remove":
      a.rowIds.forEach((id) => {
        delete byId[id];
      });
      order = order.filter((x) => !a.rowIds.includes(x));
      break;
    default:
  }
  const actions = s.staged.actions.filter((x) => x.id !== a.id);
  return {
    ...s,
    data: { ...s.data, byId, order, invoices, docs, rules },
    staged: { ...s.staged, actions },
  };
}
/* What another window changed since this one read: the seeded rows. */
export function remoteEdit(r: Movement): Movement {
  return {
    ...r,
    remoteChange: false,
    notes: r.notes || "Receipt requested from AWS billing.",
    category: r.category,
    modified: "2026-10-23T10:58:00Z",
    history: [
      ...r.history,
      {
        at: "2026-10-23T10:58:00Z",
        what: "Notes changed in another window",
        by: "You (TUI)",
      },
    ],
  };
}

export function reducer(s: State, a: Action): State {
  switch (a.type) {
    case "STAGE": {
      let rows = s.staged.rows,
        drafts = s.staged.drafts,
        derived = s.staged.derived || {};
      const refusals = { ...s.refusals };
      const outcomes = { ...s.outcomes };
      for (const { id, field, value, derived: dv } of a.changes) {
        if (!id.startsWith("draft-")) {
          const m = { ...(derived[id] || {}) };
          if (dv) m[field] = true;
          else delete m[field];
          derived = { ...derived, [id]: m };
        }
        if (id.startsWith("draft-")) {
          drafts = drafts.map((d) =>
            d.key === id
              ? { ...d, fields: { ...d.fields, [field]: value } }
              : d,
          );
        } else {
          const base = s.data.byId[id];
          if (!base) continue;
          rows = withRowStaged(rows, id, field, value, base);
          if (
            outcomes[id]?.status === "refused" ||
            outcomes[id]?.status === "notSent"
          )
            delete outcomes[id];
        }
        if (refusals[id]?.[field]) {
          refusals[id] = { ...refusals[id] };
          delete refusals[id][field];
        }
      }
      return {
        ...s,
        staged: { ...s.staged, rows, drafts, derived },
        undo: [...s.undo, snapshot(s, a.label)].slice(-300),
        redo: [],
        refusals,
        outcomes,
      };
    }
    case "REFUSE": {
      const refusals = { ...s.refusals };
      a.cells.forEach(({ id, field, raw, msg }) => {
        refusals[id] = { ...(refusals[id] || {}), [field]: { raw, msg } };
      });
      return { ...s, refusals };
    }
    case "UNDO": {
      const prev = s.undo[s.undo.length - 1];
      if (!prev) return s;
      return {
        ...s,
        staged: prev.staged,
        undo: s.undo.slice(0, -1),
        redo: [...s.redo, snapshot(s, prev.label)],
      };
    }
    case "REDO": {
      const next = s.redo[s.redo.length - 1];
      if (!next) return s;
      return {
        ...s,
        staged: next.staged,
        redo: s.redo.slice(0, -1),
        undo: [...s.undo, snapshot(s, next.label)],
      };
    }
    case "REVERT_CELL": {
      const rows = { ...s.staged.rows };
      const cur = { ...(rows[a.id] || {}) };
      if (!(a.field in cur)) return s;
      delete cur[a.field];
      if (a.field === "cls") delete cur.share;
      if (Object.keys(cur).length) rows[a.id] = cur;
      else delete rows[a.id];
      const refusals = { ...s.refusals };
      const refused = refusals[a.id];
      if (refused) {
        refusals[a.id] = { ...refused };
        delete refusals[a.id]![a.field];
      }
      return {
        ...s,
        staged: { ...s.staged, rows },
        refusals,
        undo: [
          ...s.undo,
          snapshot(s, `Revert ${F[a.field]?.label.toLowerCase() || "cell"}`),
        ],
        redo: [],
      };
    }
    case "REVERT_ROW": {
      const rows = { ...s.staged.rows };
      delete rows[a.id];
      const actions = a.keepActions
        ? s.staged.actions
        : s.staged.actions.filter((x) => !x.rowIds.includes(a.id));
      const outcomes = { ...s.outcomes };
      delete outcomes[a.id];
      const refusals = { ...s.refusals };
      delete refusals[a.id];
      return {
        ...s,
        staged: { ...s.staged, rows, actions },
        outcomes,
        refusals,
        undo: [...s.undo, snapshot(s, "Revert movement")],
        redo: [],
      };
    }
    case "DISCARD":
      return {
        ...s,
        staged: { rows: {}, drafts: [], actions: [] },
        undo: [...s.undo, snapshot(s, "Discard all")],
        redo: [],
        refusals: {},
        outcomes: {},
      };
    case "ADD_DRAFT": {
      const n = s.draftN + 1;
      const key = "draft-" + n;
      const d = {
        key,
        idem: "add-" + hashHex("idem" + n + CLOCK, 12),
        fields: {
          cls: "pending",
          description: "",
          amount: null,
          ...(a.fields || {}),
        },
      };
      return {
        ...s,
        draftN: n,
        staged: { ...s.staged, drafts: [d, ...s.staged.drafts] },
        undo: [...s.undo, snapshot(s, "Add movement")],
        redo: [],
        selection: { [key]: true },
      };
    }
    case "REMOVE_DRAFT":
      return {
        ...s,
        staged: {
          ...s.staged,
          drafts: s.staged.drafts.filter((d) => d.key !== a.key),
        },
        undo: [...s.undo, snapshot(s, "Remove draft")],
        redo: [],
      };
    case "STAGE_ACTION":
      return {
        ...s,
        staged: {
          ...s.staged,
          actions: [
            ...s.staged.actions.filter((x) => x.id !== a.action.id),
            a.action,
          ],
        },
        undo: [...s.undo, snapshot(s, a.action.label)],
        redo: [],
      };
    case "UNSTAGE_ACTION":
      return {
        ...s,
        staged: {
          ...s.staged,
          actions: s.staged.actions.filter((x) => x.id !== a.id),
        },
        undo: [...s.undo, snapshot(s, "Drop staged action")],
        redo: [],
      };
    case "SELECT": {
      let sel: Record<string, true>;
      if (a.mode === "set") {
        sel = {};
        a.ids.forEach((id) => (sel[id] = true));
      } else if (a.mode === "add") {
        sel = { ...s.selection };
        a.ids.forEach((id) => (sel[id] = true));
      } else if (a.mode === "toggle") {
        sel = { ...s.selection };
        a.ids.forEach((id) => {
          if (sel[id]) delete sel[id];
          else sel[id] = true;
        });
      } else if (a.mode === "remove") {
        sel = { ...s.selection };
        a.ids.forEach((id) => delete sel[id]);
      } else sel = {};
      return { ...s, selection: sel };
    }
    case "VIEW": {
      const view = { ...s.view, ...a.patch };
      return { ...s, view };
    }
    case "APPLY_START":
      return s;
    /* Undo does not survive a save that saved something: those changes
       cannot be unstaged here. A save that saved nothing keeps it. */
    case "APPLY_END":
      return a.savedAny ? { ...s, undo: [], redo: [], appliedAt: NOW() } : s;
    case "OUTCOME": {
      const outcomes = { ...s.outcomes };
      if (a.status) outcomes[a.id] = { status: a.status, msg: a.msg };
      else delete outcomes[a.id];
      return {
        ...s,
        outcomes,
        paused:
          a.status === "unknown"
            ? { id: a.id, label: a.label ?? "", kind: a.kind || "row" }
            : s.paused,
      };
    }
    case "PAUSE":
      return { ...s, paused: a.paused };
    case "COMMIT": {
      const n = commitRow(s, a.id, a.fields);
      const outcomes = { ...n.outcomes };
      delete outcomes[a.id];
      return {
        ...n,
        outcomes,
        check: { ...n.check, changedSince: n.check.changedSince + 1 },
      };
    }
    case "UNCHANGED": {
      const rows = { ...s.staged.rows };
      const st = { ...(rows[a.id] || {}) };
      a.fields.forEach((f) => delete st[f]);
      if (Object.keys(st).length) rows[a.id] = st;
      else delete rows[a.id];
      return { ...s, staged: { ...s.staged, rows } };
    }
    case "COMMIT_DRAFT": {
      const d = s.staged.drafts.find((x) => x.key === a.key);
      if (!d) return s;
      const f = d.fields;
      const text = (v: Value) => (v == null || v === "" ? null : String(v));
      const figure = (v: Value) => (typeof v === "number" ? v : null);
      const cls = (text(f.cls) ?? "pending") as Cls;
      const now = NOW();
      const row: Movement = {
        id: hashHex(
          [f.amount, f.description, "manual:" + d.idem, f.date, f.account].join(
            "|",
          ),
        ),
        providerId: "manual:bucket:" + d.idem,
        booked: String(f.date),
        valueDate: text(f.valueDate),
        amount: Number(f.amount),
        currency: text(f.currency) ?? "EUR",
        direction: String(f.direction) as Direction,
        counterparty: text(f.counterparty) ?? "",
        description: String(f.description),
        cls,
        share: figure(f.share),
        category: text(f.category),
        ivaCategory: text(f.ivaCategory),
        base: figure(f.base),
        ivaRate: figure(f.ivaRate),
        ivaAmount: figure(f.ivaAmount),
        recargo: figure(f.recargo),
        irpf: text(f.irpf),
        usageRatio: text(f.usageRatio),
        counterpartyCountry: text(f.counterpartyCountry),
        idState: text(f.idState),
        sourceJurisdiction: text(f.sourceJurisdiction),
        account: text(f.account),
        group: null,
        notes: text(f.notes) ?? "",
        lifecycle: "active",
        classifiedBy: CLASSIFIED.has(cls) ? "manual" : "auto",
        classifiedAt: CLASSIFIED.has(cls) ? now : null,
        invoiceId: null,
        evidenceId: null,
        attachments: [],
        fx: null,
        fxMissing: false,
        batch: null,
        prov: {
          file: "manual entry",
          row: 1,
          provider: "manual",
          format: "manual",
          ingested: now.slice(0, 10),
          sha: hashHex(d.idem),
        },
        sealed: null,
        uses: [],
        suggestion: null,
        modelRejected: false,
        issue: null,
        forceIssues: null,
        split: null,
        created: now,
        modified: now,
        history: [{ at: now, what: "Added by hand", by: "You" }],
        remoteChange: false,
        classifiedHistory: [],
      };
      const byId = { ...s.data.byId, [row.id]: row };
      const order = [...s.data.order, row.id].sort((x, y) =>
        effDate(byId[x]!).localeCompare(effDate(byId[y]!)),
      );
      const selection = { ...s.selection };
      if (selection[d.key]) {
        delete selection[d.key];
        selection[row.id] = true;
      }
      return {
        ...s,
        data: { ...s.data, byId, order },
        staged: {
          ...s.staged,
          drafts: s.staged.drafts.filter((x) => x.key !== a.key),
        },
        selection,
        lastAdded: row.id,
      };
    }
    case "APPLY_ACTION":
      return {
        ...applyAction(s, a.action),
        check: {
          ...s.check,
          changedSince: s.check.changedSince + a.action.rowIds.length,
        },
      };
    case "CHECK":
      return { ...s, check: runCheck(s.data.byId, a.at || NOW()) };
    /* The period read again at apply: another window's change shows up. */
    case "REREAD_PERIOD": {
      const byId = { ...s.data.byId };
      const conflicts: Conflict[] = [],
        conflictInfo: Conflict[] = [];
      const skip = new Set(a.skip || []);
      Object.keys(s.staged.rows).forEach((id) => {
        const r = byId[id];
        if (r && r.remoteChange) {
          const nr = remoteEdit(r);
          byId[id] = nr;
          const c = { id, before: r, after: nr, changed: ["notes"] };
          if (skip.has(id)) return;
          if ("notes" in (s.staged.rows[id] ?? {})) conflicts.push(c);
          else conflictInfo.push(c);
        }
      });
      return {
        ...s,
        data: { ...s.data, byId },
        readAt: NOW(),
        conflicts,
        conflictInfo,
      };
    }
    case "TAKE_THEIRS": {
      const rows = { ...s.staged.rows };
      delete rows[a.id];
      return { ...s, staged: { ...s.staged, rows } };
    }
    /* Re-read after an unknown outcome: what it found is kept on screen
       and in the movement's history. */
    case "REREAD": {
      let n = s;
      const notes = [...s.unknownNotes];
      if (s.paused) {
        const id = s.paused.id;
        const st = s.staged.rows[id];
        const saved = s.proto.unknownResolves === "saved";
        if (s.paused.kind === "part") {
          const { ids = [], fields = [] } = s.paused;
          ids.forEach((pid, i) => {
            if (saved && n.data.byId[pid] && n.staged.rows[pid])
              n = commitRow(n, pid, fields[i] ?? []);
            const rid = saved && n.rekeyed?.from === pid ? n.rekeyed.to : pid;
            const r = n.data.byId[rid];
            if (r)
              n = {
                ...n,
                data: {
                  ...n.data,
                  byId: {
                    ...n.data.byId,
                    [rid]: {
                      ...r,
                      history: [
                        ...r.history,
                        {
                          at: NOW(),
                          what: saved
                            ? "Saved together with no answer; found saved on re-read"
                            : "Saved together with no answer; not saved, staged again",
                          by: "Ledger",
                        },
                      ],
                    },
                  },
                },
              };
          });
        }
        if (s.paused.kind === "row" && st && n.data.byId[id]) {
          if (saved) n = commitRow(n, id, Object.keys(st));
          const rid = saved && n.rekeyed?.from === id ? n.rekeyed.to : id;
          const r = n.data.byId[rid];
          if (r)
            n = {
              ...n,
              data: {
                ...n.data,
                byId: {
                  ...n.data.byId,
                  [rid]: {
                    ...r,
                    history: [
                      ...r.history,
                      {
                        at: NOW(),
                        what: saved
                          ? "An earlier save with no answer was found saved, on re-read"
                          : "An earlier save with no answer was not saved; the change is staged again",
                        by: "Ledger",
                      },
                    ],
                  },
                },
              },
            };
        }
        notes.push({
          id: s.paused.id,
          label: s.paused.label,
          saved,
          at: NOW(),
        });
      }
      const byId = { ...n.data.byId };
      Object.values(byId).forEach((r) => {
        if (r.remoteChange && !s.staged.rows[r.id]) byId[r.id] = remoteEdit(r);
      });
      const outcomes: State["outcomes"] = {};
      Object.entries(n.outcomes).forEach(([k, v]) => {
        if (v.status === "refused") outcomes[k] = v;
      });
      return {
        ...n,
        data: { ...n.data, byId },
        paused: null,
        outcomes,
        readAt: NOW(),
        unknownNotes: notes,
      };
    }
    case "DISMISS_NOTE":
      return {
        ...s,
        unknownNotes: s.unknownNotes.filter((_, i) => i !== a.index),
      };
    case "DATA":
      return { ...s, data: a.fn(s.data) };
    case "PROTO":
      return { ...s, proto: { ...s.proto, ...a.patch } };
    case "RESET_ALL":
      return initState();
    case "FIRST_RUN":
      return {
        ...s,
        data: {
          ...s.data,
          byId: {},
          order: [],
          invoices: [],
          docs: [],
          batches: [],
        },
        check: runCheck({}, s.check.at),
        staged: { rows: {}, drafts: [], actions: [] },
      };
    default:
      return s;
  }
}
export type StageChange = {
  id: string;
  field: string;
  value: Value;
  derived?: boolean;
};
export type Action =
  | { type: "STAGE"; changes: StageChange[]; label: string }
  | {
      type: "REFUSE";
      cells: { id: string; field: string; raw: string; msg: string }[];
    }
  | { type: "UNDO" }
  | { type: "REDO" }
  | { type: "REVERT_CELL"; id: string; field: string }
  | { type: "REVERT_ROW"; id: string; keepActions?: boolean }
  | { type: "DISCARD" }
  | { type: "ADD_DRAFT"; fields?: Record<string, Value> }
  | { type: "REMOVE_DRAFT"; key: string }
  | { type: "STAGE_ACTION"; action: StagedAction }
  | { type: "UNSTAGE_ACTION"; id: string }
  | {
      type: "SELECT";
      mode: "set" | "add" | "toggle" | "remove" | "clear";
      ids: string[];
    }
  | { type: "VIEW"; patch: Partial<View> }
  | { type: "APPLY_START" }
  | { type: "APPLY_END"; savedAny: boolean }
  | {
      type: "OUTCOME";
      id: string;
      status?: string;
      msg?: string;
      label?: string;
      kind?: "row" | "part";
    }
  | { type: "PAUSE"; paused: Paused | null }
  | { type: "COMMIT"; id: string; fields: string[] }
  | { type: "UNCHANGED"; id: string; fields: string[] }
  | { type: "COMMIT_DRAFT"; key: string }
  | { type: "APPLY_ACTION"; action: StagedAction }
  | { type: "CHECK"; at?: string }
  | { type: "REREAD_PERIOD"; skip?: string[] }
  | { type: "TAKE_THEIRS"; id: string }
  | { type: "REREAD" }
  | { type: "DISMISS_NOTE"; index: number }
  | { type: "DATA"; fn: (d: DataState) => DataState }
  | { type: "PROTO"; patch: Partial<ProtoState> }
  | { type: "RESET_ALL" }
  | { type: "FIRST_RUN" };

export const StoreCtx = createContext<[State, Dispatch<Action>] | null>(null);
export function useStore(): [State, Dispatch<Action>] {
  const store = useContext(StoreCtx);
  if (!store) throw new Error("The ledger store is not provided.");
  return store;
}
