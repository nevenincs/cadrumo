import { ACCOUNT_LABEL, ACCOUNTS, daysIn, iso, quarterOf } from "./data";
import type { IconName } from "./Icon";
import type {
  Cls,
  Direction,
  Check,
  DataState,
  FieldDef,
  Filters,
  Movement,
  Option,
  Parsed,
  Period,
  Plan,
  PlanChange,
  PlanDraft,
  PlanEntry,
  PlanOp,
  State,
  WindowCtx,
  StagedAction,
  Staging,
  Value,
} from "./types";
import {
  CATEGORY_FAMILY,
  CATEGORY_LABEL,
  CATEGORY_OPTIONS,
  CLASSIFIED,
  CLS,
  DEDUCTION_KIND,
  DIRECTION,
  EU_STATES,
  FAMILY_LABEL,
  IRPF,
  IRPF_OPTIONS,
  IVA_LABEL,
  IVA_OPTIONS,
  IVA_RATE,
  LIFECYCLE,
  MONTH_LABEL,
  TODAY,
  pct,
} from "./vocab";

/* ── Formatting and the canonical input grammar. ──────────────────────── */
export const PREFS = { locale: "en-GB", yearInDates: false };
export const nf2 = () =>
  new Intl.NumberFormat(PREFS.locale, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
export const fmtMoney = (c: number | null | undefined) =>
  c == null ? "" : nf2().format(c / 100);
export const canon = (c: number | null | undefined) =>
  c == null ? "" : (c / 100).toFixed(2);
export const fmtDate = (d: string | null | undefined, withYear?: boolean) =>
  d
    ? new Date(d + "T12:00:00Z").toLocaleDateString(PREFS.locale, {
        day: "2-digit",
        month: "short",
        year: withYear || PREFS.yearInDates ? "numeric" : undefined,
        timeZone: "UTC",
      })
    : "";
export const fmtDateLong = (d: string | null | undefined) =>
  d
    ? new Date(d.slice(0, 10) + "T12:00:00Z").toLocaleDateString(PREFS.locale, {
        day: "numeric",
        month: "short",
        year: "numeric",
        timeZone: "UTC",
      })
    : "";
export const fmtStamp = (t: string | null | undefined) =>
  t
    ? new Date(t).toLocaleString(PREFS.locale, {
        day: "numeric",
        month: "short",
        hour: "2-digit",
        minute: "2-digit",
        timeZone: "UTC",
      })
    : "";
export const fmtTime = (t: string | null | undefined) =>
  t
    ? new Date(t).toLocaleTimeString(PREFS.locale, {
        hour: "2-digit",
        minute: "2-digit",
        timeZone: "UTC",
      })
    : "";
export const pctText = (f: number | null | undefined) =>
  f == null ? "" : `${+(f * 100).toFixed(4)}%`;
export const shortId = (id: string | null | undefined) =>
  id ? id.slice(0, 10) : "";
export const plural = (n: number, one: string, many?: string) =>
  `${n} ${n === 1 ? one : many || one + "s"}`;
export const quarterLabel = (d: string) => `${d.slice(0, 4)} ${quarterOf(d)}T`;

export function numberShapeError(
  s: string,
  q: string,
  what: string,
  maxDp: number,
) {
  if (/e/i.test(s) && /^\d+(\.\d+)?e[+-]?\d+$/i.test(s))
    return `${q} uses an exponent. Write the number in full.`;
  if (/^\d{1,3}(\.\d{3})+$/.test(s) && maxDp < 3)
    return `${q} is ambiguous: the dot could be a thousands separator. Write ${s.replace(/\./g, "")} for the whole number, or give at most ${maxDp} decimals.`;
  if (/^\d+,\d+$/.test(s))
    return `${q} uses a comma for decimals. Write ${s.replace(",", ".")}.`;
  if (/^\d{1,3}(,\d{3})+(\.\d+)?$/.test(s))
    return `${q} has a thousands separator. Write ${s.replace(/,/g, "")}.`;
  if (/^\d{1,3}(\.\d{3})+,\d+$/.test(s))
    return `${q} uses separators. Write ${s.replace(/\./g, "").replace(",", ".")}.`;
  if (new RegExp(`^\\d+\\.\\d{${maxDp + 1},}$`).test(s))
    return `${q} has more than ${maxDp} decimals. ${what} take at most ${maxDp}.`;
  if (/€|eur/i.test(s))
    return `${q} includes a currency. Write the number only.`;
  return `${q} is not a number. Use digits and a dot for decimals, e.g. 1234.50.`;
}
export function parseAmount(
  raw: Value,
  { allowZero = true, label = "Amount" } = {},
): Parsed {
  const s = String(raw).trim();
  if (s === "") return { empty: true };
  const q = `“${raw}”`;
  if (/^[+-]/.test(s))
    return {
      error: `${q} has a sign. ${label === "Amount" ? "Amounts are magnitudes: write " + s.replace(/^[+-]/, "") + " and set Direction to In or Out." : label + " is a magnitude: write " + s.replace(/^[+-]/, "") + "."}`,
    };
  if (/^\d+(\.\d{1,2})?$/.test(s)) {
    const [i = "", f = ""] = s.split(".");
    const c = parseInt(i, 10) * 100 + parseInt((f + "00").slice(0, 2), 10);
    if (c === 0 && !allowZero)
      return { error: `${q} is zero. A movement needs an amount above zero.` };
    if (c > 99999999999)
      return { error: `${q} is too large for one movement.` };
    return { value: c };
  }
  return { error: numberShapeError(s, q, "Amounts", 2) };
}
/* Quantities and unit prices: dot decimal, no grouping, up to 6 decimals. */
export function parseDecimal6(
  raw: Value,
  { label, positive }: { label: string; positive?: boolean },
): Parsed {
  const s = String(raw).trim();
  if (s === "") return { empty: true };
  const q = `“${raw}”`;
  if (/^[+-]/.test(s))
    return { error: `${q} has a sign. ${label} is a magnitude.` };
  if (/^\d+(\.\d{1,6})?$/.test(s)) {
    const v = Number(s);
    if (positive && !(v > 0))
      return { error: `${q}: ${label.toLowerCase()} must be above zero.` };
    return { value: v, text: s };
  }
  return {
    error: numberShapeError(
      s,
      q,
      label === "Quantity" ? "Quantities" : "Prices",
      6,
    ),
  };
}
export function parseDateIso(raw: Value): Parsed {
  const s = String(raw).trim();
  if (s === "") return { empty: true };
  const q = `“${raw}”`;
  const m = s.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (m) {
    const d = new Date(Date.UTC(+m[1]!, +m[2]! - 1, +m[3]!));
    if (d.getUTCMonth() !== +m[2]! - 1 || d.getUTCDate() !== +m[3]!)
      return { error: `${q} is not a calendar date.` };
    if (+m[1]! < 1980 || +m[1]! > 2200)
      return { error: `${q} is outside the years the ledger accepts.` };
    return { value: s };
  }
  const e = s.match(/^(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})$/);
  if (e)
    return {
      error: `${q} is not an ISO date. Write ${e[3]}-${e[2]!.padStart(2, "0")}-${e[1]!.padStart(2, "0")} (year-month-day).`,
    };
  return { error: `${q} is not a date. Write year-month-day, e.g. ${TODAY}.` };
}
/* One percent grammar for every rate and share: typed and pasted values
   mean the same, 50 is 50%, and a bare 0.5 is refused, never guessed. */
export function parsePercent(raw: Value, { label = "Rate" } = {}): Parsed {
  const s = String(raw).trim().replace(/\s*%$/, "");
  if (s === "") return { empty: true };
  const q = `“${raw}”`;
  if (/,/.test(s))
    return { error: `${q} uses a comma. Write ${s.replace(",", ".")}.` };
  if (!/^\d+(\.\d+)?$/.test(s))
    return {
      error: `${q} is not a percentage. Write a number from 0 to 100, e.g. 50.`,
    };
  const v = parseFloat(s);
  if (v > 100) return { error: `${q} is above 100%.` };
  if (v > 0 && v < 1)
    return {
      error: `${q} is ambiguous. ${label} is a percent: write ${+(v * 100).toFixed(2)} for ${+(v * 100).toFixed(2)}%, or ${s}% if you mean ${s} percent.`,
      maybe: v,
    };
  return { value: +(v / 100).toFixed(6) };
}
export function parseText(
  raw: Value,
  {
    required,
    max,
    label,
    singleLine = true,
  }: { required?: boolean; max?: number; label: string; singleLine?: boolean },
): Parsed {
  const s = String(raw).trim();
  if (singleLine && /[\t\n\r]/.test(String(raw)))
    return {
      error: `${label} is one line: tabs and line breaks are not allowed.`,
    };
  if (s === "")
    return required ? { error: `${label} cannot be empty.` } : { empty: true };
  if (max && s.length > max)
    return {
      error: `${label} takes at most ${max} characters; this has ${s.length}.`,
    };
  return { value: s };
}

/* ── Field registry. ──────────────────────────────────────────────────── */
export const F: Record<string, FieldDef> = {
  date: {
    label: "Date",
    required: true,
    editor: "date",
    hint: "Year-month-day, e.g. 2026-10-14. This is the date that decides the period.",
  },
  description: {
    label: "Description",
    required: true,
    editor: "text",
    max: 4096,
  },
  counterparty: {
    label: "Counterparty",
    editor: "text",
    clearable: true,
    max: 256,
  },
  direction: { label: "Direction", required: true, editor: "combo" },
  amount: {
    label: "Amount",
    required: true,
    editor: "amount",
    num: true,
    hint: "Dot for decimals, no grouping, up to 2 decimals: 1234.50. Direction says in or out.",
  },
  cls: { label: "Classification", editor: "combo" },
  share: {
    label: "Business share",
    editor: "share",
    needsClass: true,
    num: true,
    hint: "Percent of business use: 50 for 50%.",
  },
  category: {
    label: "Category",
    editor: "combo",
    clearable: true,
    needsClass: true,
  },
  ivaCategory: {
    label: "IVA category",
    editor: "combo",
    clearable: true,
    needsClass: true,
    tax: true,
  },
  base: {
    label: "Taxable base",
    editor: "amount",
    clearable: true,
    tax: true,
    num: true,
    hint: "Base without IVA, in the movement's currency: 1234.50.",
  },
  ivaRate: {
    label: "IVA rate",
    editor: "rate",
    clearable: true,
    tax: true,
    num: true,
    hint: "Percent: 21 for 21%.",
  },
  ivaAmount: {
    label: "IVA",
    editor: "amount",
    clearable: true,
    tax: true,
    num: true,
    hint: "IVA amount: 1234.50.",
  },
  recargo: {
    label: "Recargo",
    editor: "amount",
    addOnly: true,
    tax: true,
    num: true,
    hint: "Recargo de equivalencia amount.",
  },
  irpf: { label: "IRPF category", editor: "combo", clearable: true, tax: true },
  account: { label: "Account", editor: "combo", clearable: true },
  group: {
    label: "Group label",
    editor: "text",
    clearable: true,
    max: 64,
    notOnAdd: true,
  },
  notes: { label: "Notes", editor: "text", max: 2000, clearable: false },
  valueDate: { label: "Value date", editor: "date", clearable: true },
  booked: { label: "Booked date", required: true, editor: "date" },
  counterpartyCountry: {
    label: "Counterparty country",
    editor: "text",
    clearable: true,
    needsClass: true,
    max: 2,
  },
  idState: {
    label: "VAT-identification state",
    editor: "combo",
    clearable: true,
    needsClass: true,
    tax: true,
  },
  currency: {
    label: "Currency",
    required: true,
    editor: "text",
    max: 3,
    hint: "Three letters: EUR, USD.",
  },
  usageRatio: {
    label: "Usage ratio",
    editor: "combo",
    clearable: false,
    needsClass: true,
    clearRefusal:
      "The ledger cannot clear a usage ratio once set. Choose another category's ratio, or keep it.",
  },
  deductionKind: {
    label: "Deduction kind",
    editor: "combo",
    clearable: true,
    needsClass: true,
    tax: true,
  },
  investmentAsset: {
    label: "Investment asset",
    editor: "text",
    clearable: true,
    needsClass: true,
    tax: true,
    max: 128,
  },
  sourceJurisdiction: {
    label: "Source country",
    editor: "text",
    addOnly: true,
    max: 2,
  },
  m210: {
    label: "Modelo 210 income type",
    editor: "text",
    clearable: true,
    needsClass: true,
    tax: true,
    max: 2,
  },
  prorrataSector: {
    label: "Prorrata sector",
    editor: "text",
    addOnly: true,
    max: 64,
  },
};
export const isIdentity = (k: string, r?: Movement | null) =>
  k === "description" ||
  k === "amount" ||
  k === "account" ||
  k === "date" ||
  k === "valueDate" ||
  (k === "booked" && !(r && r.valueDate));
export const TAX_FIELDS = new Set([
  "base",
  "ivaRate",
  "ivaAmount",
  "irpf",
  "category",
  "ivaCategory",
  "share",
  "usageRatio",
  "idState",
  "deductionKind",
  "investmentAsset",
]);
export const CLASS_FIELDS = new Set([
  "cls",
  "share",
  "category",
  "ivaCategory",
  "usageRatio",
  "base",
  "ivaRate",
  "ivaAmount",
  "irpf",
  "idState",
  "counterpartyCountry",
  "deductionKind",
  "investmentAsset",
]);
export const DRAFT_REQUIRED = [
  "date",
  "amount",
  "direction",
  "description",
  "currency",
];
export const DRAFT_FIELDS = [
  "date",
  "description",
  "amount",
  "direction",
  "counterparty",
  "currency",
  "valueDate",
  "cls",
  "share",
  "category",
  "ivaCategory",
  "base",
  "ivaRate",
  "ivaAmount",
  "recargo",
  "irpf",
  "account",
  "notes",
  "counterpartyCountry",
  "idState",
  "usageRatio",
  "sourceJurisdiction",
  "prorrataSector",
];

/* What each operation accepts, and whether it can clear (brief §14). */
export const OPS = {
  bulk: {
    name: "ledger.classify.bulk",
    words: "saved together",
    sets: new Set([
      "cls",
      "category",
      "share",
      "usageRatio",
      "base",
      "ivaRate",
      "ivaAmount",
      "ivaCategory",
      "irpf",
      "notes",
    ]),
    clears: false,
  },
  classify: {
    name: "ledger.classify",
    words: "saved one at a time",
    sets: new Set([
      "idState",
      "counterpartyCountry",
      "deductionKind",
      "investmentAsset",
      "m210",
    ]),
    clears: new Set([
      "category",
      "ivaCategory",
      "share",
      "idState",
      "counterpartyCountry",
      "deductionKind",
      "investmentAsset",
      "m210",
    ]),
  },
  update: {
    name: "ledger.update",
    words: "saved one at a time",
    sets: new Set([
      "description",
      "date",
      "booked",
      "valueDate",
      "amount",
      "direction",
      "currency",
      "counterparty",
      "group",
      "account",
      "base",
      "ivaRate",
      "ivaAmount",
      "irpf",
      "notes",
    ]),
    clears: new Set([
      "valueDate",
      "counterparty",
      "base",
      "ivaRate",
      "ivaAmount",
      "irpf",
      "group",
      "account",
    ]),
  },
};
export const UPDATE_FIELDS = new Set([
  "description",
  "date",
  "booked",
  "valueDate",
  "amount",
  "direction",
  "currency",
  "counterparty",
  "group",
  "account",
]);
/* Which operation a staged value goes through. `classified` is the row's
   effective classification (stored or staged). */
export function routeField(
  k: string,
  v: Value,
  classified: boolean,
  hasBulk: boolean,
) {
  const clear = v == null || v === "";
  if (UPDATE_FIELDS.has(k)) return "update";
  if (k === "notes") return hasBulk ? "bulk" : "update";
  if (["base", "ivaRate", "ivaAmount", "irpf"].includes(k))
    return clear ? "update" : classified ? "bulk" : "update";
  if (k === "cls") return "bulk";
  if (["category", "ivaCategory", "share"].includes(k))
    return clear ? "classify" : "bulk";
  if (k === "usageRatio") return clear ? "refuse" : "bulk";
  return "classify";
}

export const effDate = (r: Movement) => r.valueDate || r.booked;
export function getField(r: Movement, k: string): Value {
  if (k === "date")
    return r.booked !== undefined || r.valueDate ? effDate(r) : r.date;
  return (r as Record<string, unknown>)[k] as Value;
}
export function setField(r: Movement, k: string, v: Value): Movement {
  const o: Record<string, unknown> = { ...r };
  if (k === "date") {
    if (r.valueDate) o.valueDate = v;
    else o.booked = v;
  } else o[k] = v;
  return o as Movement;
}
export function sameValue(a: Value, b: Value) {
  return (
    (a ?? null) === (b ?? null) ||
    (typeof a === "number" && typeof b === "number" && Math.abs(a - b) < 1e-9)
  );
}

export function show(
  k: string,
  v: Value,
  r?: { share?: number | null } | null,
  long?: boolean,
): string {
  if (v == null || v === "") return "";
  switch (k) {
    case "amount":
    case "base":
    case "ivaAmount":
    case "recargo":
      return fmtMoney(Number(v));
    case "ivaRate":
    case "share":
      return pct(Number(v));
    case "date":
    case "valueDate":
    case "booked":
      return long ? fmtDateLong(String(v)) : fmtDate(String(v));
    case "direction":
      return DIRECTION[v as Direction].label;
    case "cls":
      return (
        CLS[v as Cls].label +
        (v === "mixed" && r && r.share != null ? " " + pct(r.share) : "")
      );
    case "category":
    case "usageRatio":
      return CATEGORY_LABEL[String(v)] || String(v);
    case "ivaCategory":
      return IVA_LABEL[String(v)] || String(v);
    case "irpf":
      return IRPF[String(v)] || String(v);
    case "account":
      return ACCOUNT_LABEL[String(v)] || String(v);
    case "idState":
      return String(v).toUpperCase();
    case "deductionKind":
      return DEDUCTION_KIND[String(v)] || String(v);
    default:
      return String(v);
  }
}
/* The clipboard form: canonical numbers, percents as 50%. */
export function canonOf(k: string, v: Value): string {
  if (v == null) return "";
  switch (k) {
    case "amount":
    case "base":
    case "ivaAmount":
    case "recargo":
      return canon(Number(v));
    case "ivaRate":
    case "share":
      return pctText(Number(v));
    case "direction":
      return DIRECTION[v as Direction].token;
    case "cls":
      return CLS[v as Cls].token;
    default:
      return String(v);
  }
}
export function parseFor(
  k: string,
  raw: Value,
  ctx: { draftRequired?: boolean; draft?: boolean; row?: Movement } = {},
): Parsed {
  const def = F[k];
  if (!def) return { error: "This column cannot take a value." };
  const str = String(raw ?? "");
  const s = str.trim();
  if (def.editor === "amount") {
    const r = parseAmount(s, { allowZero: k !== "amount", label: def.label });
    if (r.empty && (def.required || ctx.draftRequired))
      return { error: `${def.label} is required.` };
    return r;
  }
  if (def.editor === "date") {
    const r = parseDateIso(s);
    if (r.empty && def.required) return { error: `${def.label} is required.` };
    return r;
  }
  if (def.editor === "rate" || def.editor === "share")
    return parsePercent(s, { label: def.label });
  if (def.editor === "text") {
    if (k === "notes" && s === "" && !ctx.draft)
      return {
        error:
          "Notes can be replaced but not emptied: the ledger keeps a note once written.",
      };
    if (k === "currency") {
      if (!/^[A-Za-z]{3}$/.test(s))
        return {
          error: `“${raw}” is not a currency code. Use three letters, e.g. EUR or USD.`,
        };
      return { value: s.toUpperCase() };
    }
    if (k === "m210") {
      if (s === "") return { empty: true };
      if (!/^\d{2}$/.test(s))
        return {
          error: `“${raw}” is not a Modelo 210 income type: two digits, e.g. 01.`,
        };
      return { value: s };
    }
    if (k === "counterpartyCountry" || k === "sourceJurisdiction") {
      if (s === "") return { empty: true };
      if (!/^[A-Za-z]{2}$/.test(s))
        return {
          error: `“${raw}” is not a two-letter country code, e.g. ES or LU.`,
        };
      return { value: s.toUpperCase() };
    }
    return parseText(str, {
      required: def.required,
      max: def.max,
      label: def.label,
      singleLine: k !== "notes",
    });
  }
  if (def.editor === "combo") {
    if (s === "")
      return def.clearable
        ? { empty: true }
        : { error: def.clearRefusal || `${def.label} is required.` };
    const opts = optionsFor(k, ctx.row || {});
    const low = s.toLowerCase();
    const hit = opts.find(
      (o) =>
        String(o.value).toLowerCase() === low ||
        (o.token || "").toLowerCase() === low ||
        o.label.toLowerCase() === low,
    );
    if (hit) {
      if (hit.disabled) return { error: hit.disabled };
      return { value: hit.value };
    }
    return {
      error: `“${raw}” is not a ${def.label.toLowerCase()} the ledger knows. Pick one from the list.`,
    };
  }
  return { error: "Not editable." };
}
export function optionsFor(k: string, r: Partial<Movement>): Option[] {
  switch (k) {
    case "direction":
      return Object.entries(DIRECTION).map(([v, d]) => ({
        value: v,
        label: d.label,
        token: d.token,
        icon: d.icon,
      }));
    case "cls":
      return (["business", "personal", "mixed"] as const).map((v) => ({
        value: v,
        label: CLS[v].label,
        token: CLS[v].token,
        disabled:
          r.direction === "transfer" && v !== "personal"
            ? "A transfer between your own accounts can only be Personal or left unclassified."
            : null,
        note: v === "mixed" ? "asks for a share" : undefined,
      }));
    case "category":
      return CATEGORY_OPTIONS;
    case "ivaCategory":
      return IVA_OPTIONS;
    case "irpf":
      return IRPF_OPTIONS;
    case "account":
      return [
        ...ACCOUNTS.map((a) => ({
          value: a.id,
          label: a.label,
          token: a.id,
          note: "…" + a.iban.slice(-4),
        })),
      ];
    case "idState":
      return EU_STATES.map((s) => ({
        value: s,
        label: s.toUpperCase(),
        token: s,
      }));
    case "usageRatio":
      return CATEGORY_OPTIONS;
    case "deductionKind":
      return Object.entries(DEDUCTION_KIND).map(([v, l]) => ({
        value: v,
        label: l,
        token: v,
      }));
    default:
      return [];
  }
}

/* Why a cell cannot take an edit, said plainly; null when it can. It is
   asked of the row as staged, so a staged transfer locks its tax cells. */
export function lockReason(
  r: Movement,
  k: string,
  isDraft?: boolean,
  actions?: StagedAction[],
): string | null {
  const def = F[k];
  if (!def) return READONLY_REASON[k] || "This column is read-only.";
  if (isDraft) {
    if (def.notOnAdd)
      return "A group label is set after the movement is saved: adding takes none.";
    return null;
  }
  if (r.split?.role === "parent")
    return "This movement was split. Edit its parts, or merge them back (⋯ in the inspector).";
  if (r.lifecycle !== "active")
    return `${LIFECYCLE[r.lifecycle].label} movements are read-only. Restore it first (⋯ in the inspector).`;
  if (r.sealed?.length)
    return `Used in ${r.sealed.map((u) => `Modelo ${u.modelo} · ${u.period} (${SEAL_LABEL[u.state]})`).join(" and ")}. Its facts are sealed.`;
  const act =
    actions &&
    actions.find((a) => a.rowIds.includes(r.id) && STRUCTURAL.has(a.type));
  if (act)
    return `A staged ${ACTION_WORD[act.type]!.toLowerCase()} is waiting in the tray for this movement. Save or drop it before editing.`;
  if (def.addOnly)
    return k === "recargo"
      ? "Recargo is recorded when a movement is added; no operation changes it later."
      : `${def.label} is recorded when a movement is added; no operation changes it later.`;
  if (r.direction === "transfer" && TAX_FIELDS.has(k))
    return "Transfers between your own accounts carry no tax fields.";
  if (k === "share" && r.cls !== "mixed")
    return "A business share belongs to a Mixed movement. Choose Mixed first.";
  return null;
}
export const STRUCTURAL = new Set([
  "archive",
  "stash",
  "restore",
  "exclude",
  "split",
  "merge",
  "remove",
]);
export const ACTION_WORD: Record<string, string> = {
  archive: "Archive",
  stash: "Set aside",
  restore: "Restore",
  exclude: "Exclude",
  split: "Split",
  merge: "Merge",
  remove: "Removal",
  link: "Link",
  attach: "Attach",
  detach: "Detach",
  reject: "Rejection",
  approve: "Model suggestion",
  rules: "Rules",
  keepBoth: "Keep both",
};
export const READONLY_REASON: Record<string, string> = {
  status: "Status follows the classification and the last readiness check.",
  eur: "The EUR value comes from the exchange rate at import. See Details.",
  invoice: "Link an invoice from the inspector's Invoice section.",
  match:
    "Link from the inspector's Invoice section, or from the To match list.",
  docs: "Attach documents from the inspector's Documents section.",
  lifecycle: "Archive, set aside or restore from ⋯ in the inspector.",
  classifiedBy: "Set by whoever made the last classification.",
  modified: "Stamped by the ledger on every saved change.",
  select: "",
};
export const SEAL_LABEL: Record<string, string> = {
  verified: "Verified (sealed)",
  filed_local: "Filed locally · AEAT status not confirmed",
  filed_receipt: "Filed · receipt confirmed",
  superseded: "Superseded",
  draft: "Draft",
};

/* ── Readiness: the per-row preflight. ───────────────────────────────── */
export const NEEDS_FIGURES = new Set([
  "domestic_general",
  "domestic_reduced",
  "domestic_super_reduced",
  "intra_community_service_acquisition_reverse_charge",
  "intra_community_acquisition_reverse_charge",
  "import_third_country",
]);
export function issuesOf(r: Movement): string[] {
  if (r.lifecycle !== "active" || r.direction === "transfer") return [];
  if (r.forceIssues) return r.forceIssues;
  if (!CLASSIFIED.has(r.cls))
    return ["pending", "unclassified", "failed"].includes(r.cls)
      ? ["missing_business_classification"]
      : [];
  if (r.cls === "personal") return [];
  if (r.ivaCategory === "unknown" || r.ivaCategory === "erroneous_invoice")
    return ["anomaly_non_declarable_iva_category"];
  if (r.currency !== "EUR") return r.fx ? [] : ["unsupported_currency"];
  const out = [];
  if (r.direction === "out" && !r.category) out.push("missing_category");
  if (r.cls === "mixed" && !r.usageRatio)
    out.push("missing_proportionality_reference");
  if (r.ivaCategory && NEEDS_FIGURES.has(r.ivaCategory)) {
    if (r.base == null) out.push("missing_taxable_base");
    if (r.ivaRate == null) out.push("missing_iva_rate");
    if (r.ivaAmount == null) out.push("missing_iva_amount");
  }
  if (
    r.ivaCategory &&
    r.ivaCategory.startsWith("intra_community") &&
    !r.idState
  )
    out.push("missing_counterparty_identification_state");
  return out;
}
export const REASON_FIX: Record<
  string,
  {
    label: string;
    field?: string;
    preset?: string;
    derive?: boolean;
    profile?: boolean;
  }
> = {
  missing_category: {
    label: "Set category",
    field: "category",
    preset: "review",
  },
  missing_taxable_base: {
    label: "Derive figures",
    field: "base",
    preset: "iva",
    derive: true,
  },
  missing_iva_rate: {
    label: "Derive figures",
    field: "ivaRate",
    preset: "iva",
    derive: true,
  },
  missing_iva_amount: {
    label: "Derive figures",
    field: "ivaAmount",
    preset: "iva",
    derive: true,
  },
  missing_proportionality_reference: {
    label: "Set share from the ratio",
    field: "usageRatio",
    preset: "mixed",
  },
  missing_counterparty_identification_state: {
    label: "Set VAT-identification state",
    field: "idState",
    preset: "iva",
  },
  missing_home_office_afectacion: {
    label: "Set afectación in Profile ›",
    profile: true,
    preset: "review",
  },
  anomaly_non_declarable_iva_category: {
    label: "Set IVA category",
    field: "ivaCategory",
    preset: "iva",
  },
  unsupported_currency: {
    label: "See exchange rate",
    field: "eur",
    preset: "review",
  },
  missing_business_classification: {
    label: "Classify",
    field: "cls",
    preset: "review",
  },
};
/* Status, said in the person's words, from the stored row and the last
   readiness check: never from what is only staged. */
export type Status = { key: string; label: string; icon: IconName; n?: number };
export function statusOf(r: Movement, check?: Check | null): Status {
  const st = CLS[r.cls].status;
  if (st === "pending")
    return { key: "toClassify", label: "To classify", icon: "pending" };
  if (st === "skipped")
    return { key: "skipped", label: "Skipped by rule", icon: "minus" };
  if (st === "excluded")
    return { key: "excluded", label: "Excluded", icon: "eyeOff" };
  const iss = check?.issues[r.id];
  if (iss === undefined)
    return { key: "notChecked", label: "Not checked", icon: "unknown" };
  if (iss.length)
    return {
      key: "needsFix",
      label: `Needs fixing · ${iss.length}`,
      icon: "alert",
      n: iss.length,
    };
  return { key: "done", label: "Done", icon: "check" };
}
export const STATUS_FILTERS: Record<string, string> = {
  toClassify: "To classify",
  needsFix: "Needs fixing",
  done: "Done",
  skipped: "Skipped by rule",
  excluded: "Excluded",
  notChecked: "Not checked",
};
export const reviewStatus = (r: Movement) => CLS[r.cls].status;
export const checkIssues = (r: Movement, check?: Check | null) =>
  (check && check.issues[r.id]) || [];

export function grossCheck(r: Movement) {
  if (r.base == null || r.ivaAmount == null) return null;
  const sum = r.base + r.ivaAmount + (r.recargo || 0);
  if (sum === r.amount) return null;
  if (
    r.ivaCategory &&
    /reverse_charge/.test(r.ivaCategory) &&
    r.base === r.amount
  )
    return null;
  if (
    r.direction === "in" &&
    r.irpf === "actividad_economica" &&
    r.amount < sum
  )
    return null;
  return {
    sum,
    text: `${canon(r.amount)} is not ${canon(r.base)} + ${canon(r.ivaAmount)}${r.recargo ? " + " + canon(r.recargo) : ""} = ${canon(sum)}`,
  };
}
export function deriveIva(
  amount: number,
  ivaCategory: string | null | undefined,
) {
  if (!ivaCategory) return null;
  if (/reverse_charge/.test(ivaCategory))
    return {
      base: amount,
      ivaRate: 0.21,
      ivaAmount: Math.round(amount * 0.21),
      note: "Self-assessed at the general rate; the movement carries no IVA.",
    };
  if (IVA_RATE[ivaCategory] != null) {
    const rate = IVA_RATE[ivaCategory];
    const base = Math.round(amount / (1 + rate));
    return {
      base,
      ivaRate: rate,
      ivaAmount: amount - base,
      note: `From the ${pct(rate)} rate in force on the movement's date.`,
    };
  }
  if (
    [
      "domestic_exempt",
      "domestic_not_subject",
      "operacion_no_sujeta",
      "export_third_country_zero_rated",
      "intra_community_supply",
    ].includes(ivaCategory)
  )
    return {
      base: amount,
      ivaRate: 0,
      ivaAmount: 0,
      note: "No IVA is charged in this category.",
    };
  return null;
}

/* ── The window: period, filters, sort, grouping, search. ────────────── */
export function periodRange(p: Period): [string, string] | null {
  if (p.code === "ALL") return null;
  const y = p.year;
  if (p.code === "0A") return [`${y}-01-01`, `${y}-12-31`];
  if (/^\dT$/.test(p.code)) {
    const q = +p.code[0]!;
    const s = (q - 1) * 3 + 1;
    return [iso(y, s, 1), iso(y, s + 2, daysIn(y, s + 2))];
  }
  const m = +p.code;
  return [iso(y, m, 1), iso(y, m, daysIn(y, m))];
}
export const inPeriod = (d: string, p: Period) => {
  const r = periodRange(p);
  return !r || (d >= r[0] && d <= r[1]);
};
export const periodLabel = (p: Period) =>
  p.code === "ALL"
    ? "All periods"
    : p.code === "0A"
      ? `${p.year} · whole year (0A)`
      : /^\dT$/.test(p.code)
        ? `${p.year} ${p.code}`
        : `${MONTH_LABEL[+p.code - 1]} ${p.year} (${p.code})`;
export const periodShort = (p: Period) =>
  p.code === "ALL"
    ? "All periods"
    : p.code === "0A"
      ? `${p.year} 0A`
      : /^\dT$/.test(p.code)
        ? `${p.year} ${p.code}`
        : `${MONTH_LABEL[+p.code - 1]} ${p.year}`;
export function stepPeriod(p: Period, dir: number): Period {
  if (p.code === "ALL") return p;
  if (p.code === "0A") return { year: p.year + dir, code: "0A" };
  if (/^\dT$/.test(p.code)) {
    let q = +p.code[0]! + dir,
      y = p.year;
    if (q < 1) {
      q = 4;
      y--;
    }
    if (q > 4) {
      q = 1;
      y++;
    }
    return { year: y, code: q + "T" };
  }
  let m = +p.code + dir,
    y = p.year;
  if (m < 1) {
    m = 12;
    y--;
  }
  if (m > 12) {
    m = 1;
    y++;
  }
  return { year: y, code: String(m).padStart(2, "0") };
}
export const SERVER_SORT: Record<string, string> = {
  date: "date",
  amount: "amount",
  description: "description",
  lifecycle: "lifecycle_state",
  cls: "classification",
  modified: "modified_at",
  valueDate: "value_date",
  classifiedAt: "classified_at",
  created: "created_at",
};
export const normDescription = (d: string) =>
  d
    .toUpperCase()
    .replace(/\b[\w./-]*\d[\w./-]*\b/g, " ")
    .replace(/[·:]/g, " ")
    .replace(/\s+/g, " ")
    .trim() || d.toUpperCase();
export const GROUPS: Record<
  string,
  {
    label: string;
    key?: (r: Movement, ctx: WindowCtx) => string;
    name?: (k: string) => string;
    server?: boolean;
  }
> = {
  none: { label: "No grouping" },
  counterparty: {
    label: "Counterparty",
    key: (r) => r.counterparty || "",
    name: (k) => k || "No counterparty",
  },
  description: {
    label: "Description (references stripped)",
    key: (r) => normDescription(r.description),
    name: (k) => k,
  },
  category: {
    label: "Category",
    key: (r) => r.category || "",
    name: (k) => (k ? (CATEGORY_LABEL[k] ?? k) : "No category"),
  },
  family: {
    label: "Category family",
    key: (r) => (r.category ? (CATEGORY_FAMILY[r.category] ?? "") : ""),
    name: (k) => (k ? (FAMILY_LABEL[k] ?? k) : "No category"),
  },
  cls: {
    label: "Classification",
    key: (r) => r.cls,
    name: (k) => CLS[k as Cls].label,
  },
  status: {
    label: "Status",
    key: (r, ctx) => statusOf(r, ctx.check).key,
    name: (k) => STATUS_FILTERS[k] ?? k,
  },
  direction: {
    label: "Direction",
    key: (r) => r.direction,
    name: (k) => DIRECTION[k as Direction].label,
  },
  account: {
    label: "Account",
    key: (r) => r.account || "",
    name: (k) => ACCOUNT_LABEL[k] || "No account",
  },
  month: {
    label: "Month",
    key: (r) => effDate(r).slice(0, 7),
    name: (k) => `${MONTH_LABEL[+k.slice(5) - 1]!} ${k.slice(0, 4)}`,
  },
  group: {
    label: "Group label",
    key: (r) => r.group || "",
    name: (k) => k || "No group label",
    server: true,
  },
  ivaCategory: {
    label: "IVA category",
    key: (r) => r.ivaCategory || "",
    name: (k) => (k ? (IVA_LABEL[k] ?? k) : "No IVA category"),
  },
};
export const SAVED_VIEWS: Record<
  string,
  {
    label: string;
    filters: Partial<Filters>;
    groupBy?: string;
    matchList?: boolean;
  }
> = {
  all: { label: "All movements", filters: {} },
  review: {
    label: "Needs review",
    filters: { status: ["toClassify"] },
    groupBy: "counterparty",
  },
  match: { label: "To match", filters: { toMatch: true }, matchList: true },
  category: {
    label: "Missing category",
    filters: { reason: "missing_category" },
  },
  foreign: { label: "Foreign currency", filters: { foreign: true } },
  business: {
    label: "Business expenses",
    filters: { cls: ["business", "mixed"], direction: ["out"] },
  },
};
export const EMPTY_FILTERS: Filters = {
  status: [],
  direction: [],
  cls: [],
  account: [],
  batch: null,
  issue: null,
  group: null,
  hideRejected: false,
  reason: null,
  foreign: false,
  lifecycle: [],
  unsaved: false,
  toMatch: false,
  noRate: false,
};
export const MONTH_WORDS = [
  ["jan", "january", "enero", "ene"],
  ["feb", "february", "febrero"],
  ["mar", "march", "marzo"],
  ["apr", "april", "abril", "abr"],
  ["may", "mayo"],
  ["jun", "june", "junio"],
  ["jul", "july", "julio"],
  ["aug", "august", "agosto", "ago"],
  ["sep", "sept", "september", "septiembre"],
  ["oct", "october", "octubre"],
  ["nov", "november", "noviembre"],
  ["dec", "december", "diciembre", "dic"],
];
/* Each word must match something: description, counterparty, category,
   notes, a linked invoice number, a month, or an amount written either way. */
export function matchesText(r: Movement, text: string, ctx: WindowCtx) {
  const words = text.toLowerCase().split(/\s+/).filter(Boolean);
  if (!words.length) return true;
  const hay = [
    r.description,
    r.counterparty || "",
    r.category || "",
    r.category ? CATEGORY_LABEL[r.category] : "",
    r.notes || "",
    r.invoiceId && ctx.invoiceNumber ? ctx.invoiceNumber(r.invoiceId) : "",
  ]
    .join(" ")
    .toLowerCase();
  const month = +effDate(r).slice(5, 7) - 1;
  return words.every((w: string) => {
    if (hay.includes(w)) return true;
    if (MONTH_WORDS[month]!.includes(w)) return true;
    const n = w.replace(",", ".");
    if (/^\d+(\.\d{1,2})?$/.test(n)) {
      const c = Math.round(parseFloat(n) * 100);
      if (r.amount === c || r.base === c || (r.fx && r.fx.eur === c))
        return true;
    }
    return false;
  });
}
export function matchesFilters(
  r: Movement,
  f: Filters,
  text: string,
  ctx: WindowCtx,
) {
  if (f.status.length && !f.status.includes(statusOf(r, ctx.check).key))
    return false;
  if (f.direction.length && !f.direction.includes(r.direction)) return false;
  if (f.cls.length && !f.cls.includes(r.cls)) return false;
  if (f.account.length && !f.account.includes(r.account || "")) return false;
  if (f.lifecycle.length && !f.lifecycle.includes(r.lifecycle)) return false;
  if (f.batch && r.batch !== f.batch) return false;
  if (f.issue && r.issue !== f.issue) return false;
  if (f.group != null && (f.group === "" ? !!r.group : r.group !== f.group))
    return false;
  if (f.hideRejected && r.modelRejected) return false;
  if (f.reason && !checkIssues(r, ctx.check).includes(f.reason)) return false;
  if (f.foreign && r.currency === "EUR") return false;
  if (f.noRate && !(r.currency !== "EUR" && !r.fx)) return false;
  if (f.unsaved && !ctx.stagedIds.has(r.id)) return false;
  if (f.toMatch && !(ctx.bestByRow && ctx.bestByRow[r.id])) return false;
  if (text && !matchesText(r, text, ctx)) return false;
  return true;
}
export function sortValue(
  r: Movement,
  key: string,
  ctx?: WindowCtx,
): string | number | null {
  switch (key) {
    case "date":
      return effDate(r);
    case "valueDate":
      return r.valueDate;
    case "created":
      return r.created;
    case "classifiedAt":
      return r.classifiedAt;
    case "amount":
      return r.amount;
    case "eur":
      return r.currency === "EUR" ? r.amount : r.fx ? r.fx.eur : null;
    case "description":
      return r.description.toLowerCase();
    case "counterparty":
      return (r.counterparty || "").toLowerCase() || null;
    case "cls":
      return CLS[r.cls].token;
    case "category":
      return r.category ? (CATEGORY_LABEL[r.category] ?? null) : null;
    case "ivaCategory":
      return r.ivaCategory ? (IVA_LABEL[r.ivaCategory] ?? null) : null;
    case "irpf":
      return r.irpf;
    case "status":
      return statusOf(r, ctx && ctx.check).key;
    case "direction":
      return r.direction;
    case "account":
      return r.account;
    case "group":
      return r.group;
    case "share":
      return r.share;
    case "usageRatio":
      return r.usageRatio;
    case "base":
      return r.base;
    case "ivaRate":
      return r.ivaRate;
    case "ivaAmount":
      return r.ivaAmount;
    case "recargo":
      return r.recargo;
    case "lifecycle":
      return r.lifecycle;
    case "modified":
      return r.modified;
    case "notes":
      return r.notes || null;
    case "classifiedBy":
      return r.classifiedBy;
    default:
      return null;
  }
}
export function compareRows(
  a: Movement,
  b: Movement,
  key: string,
  dir: string,
  ctx?: WindowCtx,
) {
  const va = sortValue(a, key, ctx),
    vb = sortValue(b, key, ctx);
  const ma = va == null || va === "",
    mb = vb == null || vb === "";
  if (ma !== mb) return ma ? 1 : -1;
  if (!ma && va !== vb) return (va! < vb! ? -1 : 1) * (dir === "desc" ? -1 : 1);
  return a.id < b.id ? -1 : 1;
}
export function sumsOf(rows: Movement[]) {
  const s: Record<string, { in: number; out: number; transfer: number }> = {};
  rows.forEach((r) => {
    const c = (s[r.currency] ||= { in: 0, out: 0, transfer: 0 });
    c[r.direction] += r.amount;
  });
  return s;
}

/* ── Staged changes and the apply plan. ──────────────────────────────── */
export function diffOf(
  base: Movement,
  staged: Record<string, Value> | undefined,
) {
  if (!staged) return [];
  return Object.keys(staged).filter(
    (k) => !sameValue(getField(base, k), staged[k]),
  );
}
/* The row as it would be once saved: field edits, plus a staged model
   approval's proposal. Used for editing and preview, never for status. */
export function effective(
  row: Movement,
  staged?: Staging["rows"],
  actions?: StagedAction[],
) {
  let o = row;
  const appr =
    actions &&
    actions.find((a) => a.type === "approve" && a.rowIds[0] === row.id);
  if (appr)
    for (const [k, v] of Object.entries(appr.payload?.fields ?? {}))
      o = setField(o, k, v);
  const s = staged?.[row.id];
  if (s) for (const k in s) o = setField(o, k, s[k]);
  return o;
}
export const PART_SIZE = 100;
export const SINGLE_SECONDS = 3;
/* The declarations that use a period, in words: "Modelo 303 3T (draft)". */
export function declsFor(q: string, data: DataState) {
  const out = new Map<string, string>();
  Object.values(data.byId).forEach((r) =>
    r.uses.forEach((u) => {
      if (u.period === q)
        out.set(
          u.modelo,
          `Modelo ${u.modelo} ${q.slice(5)} (${SEAL_LABEL[u.state]!.toLowerCase()})`,
        );
    }),
  );
  return [...out.values()];
}
export function buildPlan(state: Pick<State, "staged" | "data">): Plan {
  const { staged, data } = state;
  const entries: PlanEntry[] = [];
  const actionsByRow: Record<string, StagedAction[]> = {};
  staged.actions.forEach((a) =>
    a.rowIds.forEach((id) => (actionsByRow[id] ||= []).push(a)),
  );
  for (const id of Object.keys(staged.rows)) {
    const base = data.byId[id];
    if (!base) {
      const missing = {
        description: "A movement that is no longer in the ledger",
        id,
      } as Movement;
      entries.push({
        id,
        missing: true,
        base: missing,
        eff: missing,
        routes: {},
        bulk: [],
        classify: [],
        update: [],
        notes: [],
        derived: [],
        clears: [],
        fields: Object.keys(staged.rows[id] ?? {}),
        blockers: [
          {
            type: "gone",
            text: "This movement was removed or moved elsewhere since you read it. Its staged changes cannot be saved.",
          },
        ],
      });
      continue;
    }
    const rowEdits = staged.rows[id] ?? {};
    const fields = diffOf(base, rowEdits);
    if (!fields.length) continue;
    const eff = effective(base, staged.rows);
    const classified = CLASSIFIED.has(eff.cls);
    const bulkSet = fields.filter(
      (k) =>
        routeField(k, rowEdits[k], classified, false) === "bulk" &&
        k !== "notes",
    );
    const routes: Record<string, string> = {};
    fields.forEach((k) => {
      routes[k] = routeField(k, rowEdits[k], classified, bulkSet.length > 0);
    });
    // A share cleared because the classification left Mixed travels with the classification.
    if (
      routes.share === "classify" &&
      fields.includes("cls") &&
      eff.cls !== "mixed"
    )
      routes.share = "implicit";
    const by = (op: string) => fields.filter((k) => routes[k] === op);
    const entry: PlanEntry = {
      id,
      base,
      eff,
      fields,
      routes,
      bulk: by("bulk"),
      classify: by("classify"),
      update: by("update"),
      blockers: [],
      notes: [],
      derived: [],
      clears: [],
    };
    if (fields.some((k) => routes[k] === "refuse"))
      entry.blockers.push({
        type: "cannotClear",
        text: F.usageRatio!.clearRefusal ?? "",
      });
    if ((entry.bulk.length || entry.classify.length) && !classified)
      entry.blockers.push({
        type: "needsClass",
        text: `Needs a classification: ${[...entry.bulk, ...entry.classify]
          .filter((k) => k !== "notes")
          .map((k) => F[k]!.label.toLowerCase())
          .join(", ")} can only be saved with one.`,
      });
    if (eff.cls === "mixed" && eff.share == null)
      entry.blockers.push({
        type: "needsShare",
        text: "Mixed needs a business share.",
      });
    if (
      eff.direction === "transfer" &&
      fields.some((k) => k === "direction" || CLASS_FIELDS.has(k)) &&
      ((CLASSIFIED.has(eff.cls) && eff.cls !== "personal") ||
        [...TAX_FIELDS].some(
          (k) => getField(eff, k) != null && getField(eff, k) !== "",
        ))
    )
      entry.blockers.push({
        type: "transferTax",
        text: "A transfer between your own accounts can only be Personal or unclassified, and carries no tax fields.",
      });
    const acts = actionsByRow[id] || [];
    const structural = acts.filter((a) => STRUCTURAL.has(a.type));
    if (structural.length)
      entry.blockers.push({
        type: "actionAndEdit",
        action: structural[0],
        text: `This movement also has a staged ${ACTION_WORD[structural[0]!.type]!.toLowerCase()}. The ledger takes one or the other: drop the edits or drop the ${ACTION_WORD[structural[0]!.type]!.toLowerCase()}.`,
      });
    const appr = acts.find((a) => a.type === "approve");
    const derived = (staged.derived && staged.derived[id]) || {};
    entry.derived = fields.filter((k) => derived[k]);
    if (appr && fields.some((k) => CLASS_FIELDS.has(k) && !derived[k]))
      entry.blockers.push({
        type: "actionAndEdit",
        action: appr,
        text: "This movement has both a model suggestion to approve and your own classification edits. Keep one.",
      });
    if (entry.bulk.length && !fields.includes("cls") && classified)
      entry.notes.push(
        `Sends its current classification, ${show("cls", eff.cls, eff)}, with the batch.`,
      );
    entry.clears = fields.filter(
      (k) => rowEdits[k] == null && routes[k] !== "implicit",
    );
    const g = grossCheck(eff);
    if (
      g &&
      fields.some((k) => ["amount", "base", "ivaAmount", "ivaRate"].includes(k))
    )
      entry.gross = g;
    if (fields.some((k) => isIdentity(k, base)))
      entry.identityNote =
        "Saved under a new reference: the movement's id changes, and the old one stays in its history.";
    if (fields.includes("date") || fields.includes("valueDate")) {
      const q0 = quarterLabel(effDate(base)),
        q1 = quarterLabel(effDate(eff));
      if (q0 !== q1) {
        const d = declsFor(q1, data);
        entry.notes.push(
          `Moves to ${q1}${d.length ? " · affects " + d.join(", ") : ""}.`,
        );
      }
    }
    entries.push(entry);
  }
  const drafts: PlanDraft[] = staged.drafts.map((d) => ({
    ...d,
    missing: DRAFT_REQUIRED.filter(
      (k) => d.fields[k] == null || d.fields[k] === "",
    ),
  }));
  const ready = entries.filter((e) => !e.blockers.length);
  const blocked = entries.filter((e) => e.blockers.length);
  const blockedIds = new Set(blocked.map((e) => e.id));
  const bulk = ready.filter((e) => e.bulk.length);
  const singles = ready.filter((e) => e.classify.length);
  const corrections = ready.filter((e) => e.update.length);
  const readyDrafts = drafts.filter((d) => !d.missing.length);
  const blockedDrafts = drafts.filter((d) => d.missing.length);
  const actionRank: Record<string, number> = {
    approve: 0,
    reject: 0,
    rules: 0,
    keepBoth: 1,
    link: 1,
    attach: 1,
    detach: 1,
    archive: 2,
    stash: 2,
    restore: 2,
    exclude: 2,
    split: 3,
    merge: 3,
    remove: 4,
  };
  const noShare = (a: StagedAction) =>
    a.type === "approve" &&
    a.payload?.fields?.cls === "mixed" &&
    a.payload.fields.share == null;
  const actions = staged.actions
    .filter(
      (a) =>
        !noShare(a) &&
        !a.rowIds.some(
          (id) =>
            blockedIds.has(id) &&
            (STRUCTURAL.has(a.type) || a.type === "approve"),
        ),
    )
    .sort((a, b) => actionRank[a.type]! - actionRank[b.type]!);
  const heldActions = staged.actions
    .filter((a) => !actions.includes(a))
    .map((a) => ({
      ...a,
      holdReason: noShare(a)
        ? "Enter a share to approve"
        : "held back with its movement",
    }));
  const ops: PlanOp[] = [];
  const parts = Math.ceil(bulk.length / PART_SIZE);
  for (let p = 0; p < parts; p++) {
    const slice = bulk.slice(p * PART_SIZE, (p + 1) * PART_SIZE);
    ops.push({
      key: "bulk-" + p,
      kind: "bulk",
      part: p + 1,
      parts,
      label:
        parts > 1
          ? `Saved together · part ${p + 1} of ${parts} · ${plural(slice.length, "movement")}`
          : `${plural(slice.length, "movement")} saved together`,
      tech: `${OPS.bulk.name} · one revision-guarded save · about ${slice.length} CSV rows`,
      entries: slice,
    });
  }
  singles.forEach((e) =>
    ops.push({
      key: "c-" + e.id,
      kind: "classify",
      label: `${e.base.description}: ${e.classify.map((k) => (e.clears.includes(k) ? "clear " : "") + F[k]!.label.toLowerCase()).join(", ")}`,
      tech: `${OPS.classify.name} · field mask ${e.classify.join(", ")}`,
      entries: [e],
    }),
  );
  corrections.forEach((e) =>
    ops.push({
      key: "u-" + e.id,
      kind: "update",
      label: `${e.base.description}: ${e.update.map((k) => (e.clears.includes(k) ? "clear " : "") + F[k]!.label.toLowerCase()).join(", ")}`,
      tech: `${OPS.update.name} · field mask ${e.update.join(", ")}`,
      entries: [e],
    }),
  );
  readyDrafts.forEach((d) =>
    ops.push({
      key: d.key,
      kind: "add",
      label: `New movement · ${d.fields.description || "untitled"}`,
      tech: `ledger.add · idempotency key ${d.idem}`,
      draft: d,
    }),
  );
  actions.forEach((a) =>
    ops.push({
      key: a.id,
      kind: "action",
      label: a.label,
      tech: a.tech || a.detail,
      action: a,
    }),
  );
  const oneAtATime =
    singles.length +
    corrections.length +
    readyDrafts.length +
    actions.reduce((n, a) => n + (a.type === "rules" ? 0 : a.rowIds.length), 0);
  const words: string[] = [];
  if (bulk.length)
    words.push(
      `${plural(bulk.length, "movement")} saved together${parts > 1 ? ` in ${parts} parts` : ""}`,
    );
  if (oneAtATime)
    words.push(
      `${oneAtATime} saved one at a time (about ${oneAtATime * SINGLE_SECONDS < 60 ? oneAtATime * SINGLE_SECONDS + " seconds" : Math.ceil((oneAtATime * SINGLE_SECONDS) / 60) + " minutes"})`,
    );
  if (readyDrafts.length)
    words.push(plural(readyDrafts.length, "new movement"));
  const links = actions.filter((a) => a.type === "link");
  const changes = ready.length + readyDrafts.length + actions.length;
  return {
    entries,
    ready,
    blocked,
    blockedDrafts,
    heldActions,
    ops,
    drafts,
    words,
    links,
    changes,
    held: blocked.length + blockedDrafts.length + heldActions.length,
    oneAtATime,
  };
}
/* A summary of the field changes across rows: “IRPF category: empty →
   Economic activity · 132 movements”. */
export function summarizeChanges(entries: PlanEntry[]): PlanChange[] {
  const m = new Map<string, PlanChange>();
  entries.forEach((e) =>
    e.fields.forEach((k) => {
      if (!F[k]) return;
      const key =
        k +
        "|" +
        show(k, getField(e.base, k), e.base) +
        "|" +
        show(k, getField(e.eff, k), e.eff);
      if (!m.has(key))
        m.set(key, {
          field: k,
          from: show(k, getField(e.base, k), e.base, true) || "empty",
          to: show(k, getField(e.eff, k), e.eff, true) || "empty",
          ids: [],
        });
      m.get(key)!.ids.push(e.id);
    }),
  );
  return [...m.values()].sort((a, b) => b.ids.length - a.ids.length);
}
export function stagedRowIds(state: Pick<State, "staged" | "data">) {
  const s = new Set<string>();
  Object.keys(state.staged.rows).forEach((id) => {
    const b = state.data.byId[id];
    if (b && diffOf(b, state.staged.rows[id]).length) s.add(id);
  });
  state.staged.actions.forEach((a) => a.rowIds.forEach((id) => s.add(id)));
  return s;
}
export function trayCounts(state: Pick<State, "staged" | "data">) {
  let edits = 0;
  const rows = new Set<string>();
  for (const id of Object.keys(state.staged.rows)) {
    const base = state.data.byId[id];
    if (!base) continue;
    const n = diffOf(base, state.staged.rows[id]).filter(
      (k) =>
        !(
          k === "share" &&
          state.staged.rows[id]?.[k] == null &&
          "cls" in (state.staged.rows[id] ?? {})
        ),
    ).length;
    if (n) {
      edits += n;
      rows.add(id);
    }
  }
  const kinds: Record<string, number> = {};
  state.staged.actions.forEach((a) => {
    kinds[a.type] = (kinds[a.type] || 0) + 1;
    a.rowIds.forEach((id) => rows.add(id));
  });
  const editRows = Object.keys(state.staged.rows).filter(
    (id) =>
      state.data.byId[id] &&
      diffOf(state.data.byId[id], state.staged.rows[id]).length,
  ).length;
  const total =
    editRows + state.staged.drafts.length + state.staged.actions.length;
  return {
    edits,
    editRows,
    rows: rows.size,
    adds: state.staged.drafts.length,
    actions: state.staged.actions.length,
    kinds,
    total,
  };
}

/* TSV: what the clipboard carries. An opening quote that never closes is
   refused, so rows never run together. */
export function tsvEscape(s: Value) {
  s = String(s ?? "");
  return /[\t\n"]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
}
export function parseTsv(text: string): { rows: string[][]; error?: string } {
  const rows: string[][] = [];
  let row: string[] = [],
    cell = "",
    q = false;
  for (let i = 0; i < text.length; i++) {
    const ch = text[i];
    if (q) {
      if (ch === '"' && text[i + 1] === '"') {
        cell += '"';
        i++;
      } else if (ch === '"') q = false;
      else cell += ch;
    } else if (ch === '"' && cell === "") {
      q = true;
    } else if (ch === "\t") {
      row.push(cell);
      cell = "";
    } else if (ch === "\n" || ch === "\r") {
      if (ch === "\r" && text[i + 1] === "\n") i++;
      row.push(cell);
      rows.push(row);
      row = [];
      cell = "";
    } else cell += ch;
  }
  if (q)
    return {
      error:
        "An opening quote is never closed, so the cells would run together. Nothing was pasted.",
      rows: [],
    };
  if (cell !== "" || row.length) {
    row.push(cell);
    rows.push(row);
  }
  return { rows };
}
