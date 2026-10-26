import {
  useState,
  useEffect,
  useRef,
  useMemo,
  Fragment,
  type ReactNode,
} from "react";
import { Icon, type IconName } from "./Icon";
import { usePage } from "./page";
import type { Account, Doc, Finding, Rule } from "./types";
import { clsx as cx } from "clsx";
import { CLOCK, NOW, useStore } from "./store";
import { reconciliationSuggestions } from "./Movements";
import {
  STATUS_FILTERS,
  canon,
  checkIssues,
  effDate,
  fmtDate,
  fmtDateLong,
  fmtMoney,
  fmtStamp,
  fmtTime,
  issuesOf,
  parseAmount,
  parseDateIso,
  parseDecimal6,
  parsePercent,
  periodRange,
  periodShort,
  plural,
  statusOf,
  tsvEscape,
} from "./model";
import { DataTable, sortRows, useSort, type TableColumn } from "./DataGrid";
import type { Parsed } from "./types";
import type { DataState, Invoice, Match, Movement } from "./types";
import {
  Alert,
  Button,
  Dialog,
  Empty,
  Field,
  IconButton,
  Input,
  Menu,
  Seg,
  Select,
  Switch,
  Tabs,
  announce,
  copyText,
  sleep,
} from "./Primitives";
import {
  BLOCK_REASON,
  CATEGORY_FAMILY,
  CATEGORY_LABEL,
  CLASSIFIED,
  CLS,
  FAMILIES,
  FAMILY_LABEL,
  FIELD_ORIGIN,
  GROUNDING,
  INVOICE_CLASS,
  IVA_GROUPS,
  LIFECYCLE,
  LINE_RATES,
  OPERATION_TYPES,
  PAYMENT,
  REASONS,
  TODAY,
  pct,
} from "./vocab";
import { RATIO_ELIGIBLE, hashHex } from "./data";
import { stageLinkAction } from "./Inspector";
import {
  HostFileDialog,
  ruleCandidates,
  ruleText,
  stageRulesAction,
} from "./Dialogs";
import { PeriodControl, YEAR_MAX, YEAR_MIN, yearOk } from "./PeriodSelector";
import { EMPTY_FILTERS } from "./model";
import type { Lifecycle } from "./types";

/* ── Invoices: the catalogue, filtered and sorted here (the ledger lists
   by kind only). Unmatched is a filter (R10). ───────────────────────── */
type DraftRes = Record<
  string,
  { action?: string; value?: string; note?: string }
>;
type RulePreview = {
  out: { rule: Rule; rows: Movement[] }[];
  skippedStaged: number;
};
type CpForm = {
  taxId: string;
  country: string;
  idState: string;
  scope: string;
  note: string;
};
const NO_CP_FORM: CpForm = {
  taxId: "",
  country: "",
  idState: "",
  scope: "",
  note: "",
};
type AcctAction = {
  type: "close" | "designate";
  a: Account;
  date?: string;
  role?: string;
  modelo?: string;
};
type OneSided = {
  inv: Invoice | undefined;
  tid: string;
  r: Movement | undefined;
  side: "invoice" | "movement";
};
export function oneSidedLinks(data: DataState) {
  const out: OneSided[] = [];
  data.invoices.forEach((inv) =>
    inv.linked.forEach((tid) => {
      const r = data.byId[tid];
      if (!r || r.invoiceId !== inv.id)
        out.push({ inv, tid, r, side: "invoice" });
    }),
  );
  Object.values(data.byId).forEach((r) => {
    if (r.invoiceId) {
      const inv = data.invoices.find((i) => i.id === r.invoiceId);
      if (!inv || !inv.linked.includes(r.id))
        out.push({ inv, tid: r.id, r, side: "movement" });
    }
  });
  return out;
}
export function InvoicesSection() {
  const [state] = useStore();
  const page = usePage();
  const [kind, setKind] = useState("all");
  const [q, setQ] = useState("");
  const [cls, setCls] = useState("");
  const [pay, setPay] = useState("");
  const [unmatched, setUnmatched] = useState(page.invUnmatched || false);
  const [inPeriod, setInPeriod] = useState(true);
  const [sort, toggle] = useSort({ key: "date", dir: "desc" });
  useEffect(() => {
    page.invUnmatched = false;
  }, [page]);
  const range = periodRange(state.view.period);
  const rangeStart = range?.[0];
  const rangeEnd = range?.[1];
  const recon = useMemo(
    () => reconciliationSuggestions(state.data, state.staged.actions),
    [state.data, state.staged.actions],
  );
  const suggestedFor = useMemo(() => {
    const m: Record<string, Match> = {};
    Object.values(recon.best).forEach((b) => {
      if (!m[b.invoiceId]) m[b.invoiceId] = b;
    });
    return m;
  }, [recon]);
  const rows = useMemo(() => {
    const t = q.trim().toLowerCase();
    const list = state.data.invoices.filter(
      (i) =>
        (kind === "all" || i.kind === kind) &&
        (!cls || i.cls === cls) &&
        (!pay || i.payment === pay) &&
        (!unmatched || !i.linked.length) &&
        (!inPeriod ||
          rangeStart == null ||
          rangeEnd == null ||
          (i.date >= rangeStart && i.date <= rangeEnd)) &&
        (!t ||
          [i.number, i.counterparty, i.nif || "", i.notes].some((x) =>
            x.toLowerCase().includes(t),
          )),
    );
    return sortRows(list, sort, (i, k) =>
      k === "number"
        ? i.number
        : k === "linked"
          ? i.linked.length
          : (i[k as keyof Invoice] as string | number | null),
    );
  }, [
    state.data.invoices,
    kind,
    q,
    cls,
    pay,
    unmatched,
    inPeriod,
    sort,
    rangeStart,
    rangeEnd,
  ]);
  const sided = useMemo(() => oneSidedLinks(state.data), [state.data]);
  const money = (k: "base" | "iva" | "total" | "retention") => (i: Invoice) =>
    i[k] == null ? (
      <span className="muted">—</span>
    ) : (
      <span className="tnum">{fmtMoney(i[k])}</span>
    );
  const cols: TableColumn<Invoice>[] = [
    {
      key: "kind",
      label: "Kind",
      render: (i) => (
        <span className="tag">
          {i.kind === "issued" ? "Issued" : "Received"}
        </span>
      ),
    },
    {
      key: "number",
      label: "Series and number",
      render: (i) => <span className="fw5">{i.number}</span>,
    },
    {
      key: "date",
      label: "Date",
      render: (i) => <span className="tnum">{fmtDate(i.date, true)}</span>,
    },
    { key: "counterparty", label: "Counterparty", wrap: true },
    {
      key: "nif",
      label: "Tax id",
      render: (i) =>
        i.nif ? (
          <span className="mono t-sm">{i.nif}</span>
        ) : (
          <span className="muted">None</span>
        ),
    },
    { key: "base", label: "Taxable base", num: true, render: money("base") },
    { key: "iva", label: "IVA", num: true, render: money("iva") },
    {
      key: "retention",
      label: "Retención",
      num: true,
      render: money("retention"),
    },
    {
      key: "total",
      label: "Total",
      num: true,
      render: (i) => <span className="tnum fw5">{fmtMoney(i.total)}</span>,
    },
    { key: "currency", label: "Currency" },
    {
      key: "linked",
      label: "Movement",
      render: (i) =>
        i.linked.length ? (
          <span className="row g1">
            <Icon name="link" size="xs" />
            {plural(i.linked.length, "linked")}
          </span>
        ) : suggestedFor[i.id] ? (
          <span className="row g1 t-sm">
            {suggestedFor[i.id]!.ambiguous ? (
              <span className="badge warning">Ambiguous</span>
            ) : null}
            Suggested: {fmtDateLong(effDate(suggestedFor[i.id]!.row))}
          </span>
        ) : (
          <span className="muted">Unmatched</span>
        ),
    },
    {
      key: "payment",
      label: "Payment",
      render: (i) => (
        <span className="row g1">
          {i.payment === "overdue" ? (
            <Icon name="alert" size="xs" className="warn-t" />
          ) : null}
          {PAYMENT[i.payment]}
        </span>
      ),
    },
  ];
  const tsv = () => {
    const h = [
      "Kind",
      "Number",
      "Date",
      "Counterparty",
      "Tax id",
      "Base",
      "IVA",
      "Retención",
      "Total",
      "Currency",
      "Linked",
      "Payment",
    ].join("\t");
    const b = rows
      .map((i) =>
        [
          i.kind,
          i.number,
          i.date,
          i.counterparty,
          i.nif || "",
          canon(i.base),
          canon(i.iva),
          canon(i.retention),
          canon(i.total),
          i.currency,
          i.linked.length,
          PAYMENT[i.payment],
        ]
          .map(tsvEscape)
          .join("\t"),
      )
      .join("\n");
    copyText(h + "\n" + b);
    page.toast(`Copied ${plural(rows.length, "invoice")} as TSV`);
  };
  return (
    <div className="section">
      <div
        className="section-bar"
        role="toolbar"
        aria-label="Invoice catalogue"
      >
        <Seg
          size="sm"
          label="Kind"
          value={kind}
          onChange={setKind}
          options={[
            { value: "all", label: "All" },
            { value: "issued", label: "Issued" },
            { value: "received", label: "Received" },
          ]}
        />
        <div className="search">
          <Icon name="search" />
          <input
            className="input sm"
            type="search"
            placeholder="Number, name, tax id"
            aria-label="Search invoices by number, counterparty or tax id"
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
        </div>
        <div style={{ width: "calc(var(--spacing) * 38)" }}>
          <Select
            size="sm"
            aria-label="Class"
            value={cls}
            onChange={(e) => setCls(e.target.value)}
          >
            <option value="">Any class</option>
            {Object.entries(INVOICE_CLASS).map(([k, l]) => (
              <option key={k} value={k}>
                {l}
              </option>
            ))}
          </Select>
        </div>
        <div style={{ width: "calc(var(--spacing) * 38)" }}>
          <Select
            size="sm"
            aria-label="Payment"
            value={pay}
            onChange={(e) => setPay(e.target.value)}
          >
            <option value="">Any payment</option>
            {Object.entries(PAYMENT).map(([k, l]) => (
              <option key={k} value={k}>
                {l}
              </option>
            ))}
          </Select>
        </div>
        <button
          type="button"
          className="btn pill"
          aria-pressed={unmatched}
          onClick={() => setUnmatched(!unmatched)}
        >
          Unmatched
        </button>
        <label className="row g2 t-sm">
          <Switch
            checked={inPeriod}
            onChange={setInPeriod}
            label={"Only " + periodShort(state.view.period)}
          />
          In {periodShort(state.view.period)}
        </label>
        <span className="ml-auto muted t-sm tnum">
          {plural(rows.length, "invoice")}
        </span>
        <IconButton icon="copy" label="Copy as TSV" size="sm" onClick={tsv} />
        <Button size="sm" icon="plus" onClick={() => page.addInvoice()}>
          Add invoice
        </Button>
      </div>
      {sided.length ? (
        <div className="banner">
          <Alert
            tone="warning"
            title={`${plural(sided.length, "one-sided link")}`}
          >
            {sided
              .map(
                (x) =>
                  `${x.inv ? x.inv.number : "A missing invoice"} and ${x.r ? x.r.description : "a removed movement"}`,
              )
              .join(" · ")}
            : one side lists the link, the other does not. Linking again from
            the movement writes both sides; a link cannot be removed.
          </Alert>
        </div>
      ) : null}
      <div className="tbl-wrap" tabIndex={0} aria-label="Invoices table">
        <DataTable
          label="Invoices"
          columns={cols}
          rows={rows}
          rowKey={(i) => i.id}
          sort={sort}
          onSort={toggle}
          onRowClick={(i) => page.openInvoice(i.id)}
          rowLabel={(i) =>
            `Invoice ${i.number}, ${i.counterparty}, ${fmtMoney(i.total)}`
          }
          selectedKey={page.sheetInvoice}
          empty={
            <Empty
              icon="receipt"
              title={
                unmatched ? "Every invoice here is matched" : "No invoices here"
              }
              desc="Add one, import an invoice book, or confirm a document as an invoice."
            />
          }
        />
      </div>
    </div>
  );
}
type LineForm = {
  description: string;
  qty: string;
  price: string;
  rate: string;
  category: string;
};
export function lineCalc(l: LineForm) {
  const q = parseDecimal6(l.qty, { label: "Quantity", positive: true });
  const p = parseDecimal6(l.price, { label: "Unit price" });
  const rate = LINE_RATES.find(([k]) => k === l.rate)?.[2];
  const err = q.error || p.error;
  if (err || q.empty || p.empty || rate == null)
    return { sub: null, iva: null, err };
  const sub = Math.round(Number(q.value) * Number(p.value) * 100);
  return { sub, iva: Math.round(sub * rate) };
}
export function nextNumber(
  invoices: Invoice[],
  { series, cls, year }: { series: string; cls: string; year: number },
) {
  if (cls === "rectificativa" && !series) return null;
  const pool = invoices.filter(
    (i) => i.kind === "issued" && (i.date || "").startsWith(String(year)),
  );
  let ser = series;
  if (!ser) {
    const n: Record<string, number> = {};
    pool
      .filter((i) => i.cls === "ordinaria" && i.series)
      .forEach((i) => (n[i.series!] = (n[i.series!] || 0) + 1));
    ser = Object.entries(n).sort((a, b) => b[1] - a[1])[0]?.[0] ?? "";
  }
  if (!ser) return null;
  const re = new RegExp(
    "^" + ser.replace(/[^A-Za-z0-9]/g, "") + "-" + year + "-([0-9]+)$",
  );
  const nums = pool
    .filter((i) => i.series === ser)
    .flatMap((i) => i.number.match(re) ?? []);
  if (!nums.length) return { series: ser, number: `${ser}-${year}-001` };
  const top = nums.sort((a, b) => +a[1]! - +b[1]!)[nums.length - 1]!;
  const last = top[1]!;
  return {
    series: ser,
    number: `${ser}-${year}-${String(+last + 1).padStart(last.length, "0")}`,
  };
}
/* The invoice editor is a modal Sheet (R13): scrim, focus trap, Escape,
   focus on its first field and back to the opener when it closes. */
type InvForm = {
  kind: string;
  cls: string;
  series: string;
  number: string;
  date: string;
  opDate: string;
  counterparty: string;
  nif: string;
  country: string;
  currency: string;
  ivaCategory: string;
  operationType: string;
  rectifies: string;
  retentionRate: string;
  retention: string;
  recargo: string;
  printed: string;
  notes: string;
  payment: string;
  paymentId: string;
};
const BLANK_FORM: InvForm = {
  kind: "",
  cls: "ordinaria",
  series: "",
  number: "",
  date: "",
  opDate: "",
  counterparty: "",
  nif: "",
  country: "",
  currency: "",
  ivaCategory: "",
  operationType: "",
  rectifies: "",
  retentionRate: "",
  retention: "",
  recargo: "",
  printed: "",
  notes: "",
  payment: "",
  paymentId: "",
};
export type InvoicePrefill = {
  kind?: string;
  counterparty?: string;
  date?: string;
  amount?: number;
  currency?: string;
  description?: string;
  rowId?: string;
};
export function InvoiceSheet({
  id,
  prefill,
  onClose,
}: {
  id: string | null;
  prefill?: InvoicePrefill;
  onClose: () => void;
}) {
  const [state, dispatch] = useStore();
  const page = usePage();
  const inv = id ? state.data.invoices.find((i) => i.id === id) : null;
  const isNew = !inv;
  const [f, setF] = useState<InvForm>(() => ({
    ...BLANK_FORM,
    ...(inv
      ? {
          counterparty: inv.counterparty,
          country: inv.country,
          series: inv.series || "",
          rectifies: inv.rectifies || "",
          opDate: inv.opDate || "",
          retentionRate:
            inv.retentionRate != null ? String(+(inv.retentionRate * 100)) : "",
          retention: inv.retention != null ? canon(inv.retention) : "",
          ivaCategory: inv.ivaCategory || "",
          operationType: inv.operationType || "",
          cls: inv.cls,
          notes: inv.notes,
          payment: inv.payment,
          paymentId: inv.paymentId || "",
        }
      : {
          kind: prefill?.kind || "",
          date: prefill?.date || "",
          counterparty: prefill?.counterparty || "",
          currency: prefill?.currency || "",
        }),
  }));
  const [retTouched, setRetTouched] = useState(!!inv);
  const [lines, setLines] = useState<LineForm[]>(() =>
    inv
      ? inv.lines.map((l) => ({
          description: l.description,
          qty: l.qtyText || String(l.qty),
          price: l.priceText || canon(l.price),
          rate: l.rate,
          category: l.category || "",
        }))
      : [
          {
            description: prefill?.description || "",
            qty: "1",
            price: "",
            rate: "",
            category: "",
          },
        ],
  );
  const [errors, setErrors] = useState<Record<string, string | null>>({});
  const [review, setReview] = useState(false);
  const [busy, setBusy] = useState(false);
  const [removing, setRemoving] = useState(false);
  const set =
    (k: keyof InvForm) => (e: string | { target: { value: string } }) => {
      setF({ ...f, [k]: typeof e === "string" ? e : e.target.value });
      setErrors({ ...errors, [k]: null });
    };
  const calc = lines.map(lineCalc);
  const base = isNew ? calc.reduce((s, c) => s + (c.sub || 0), 0) : inv.base;
  const iva = isNew ? calc.reduce((s, c) => s + (c.iva || 0), 0) : inv.iva;
  const recargo = isNew
    ? Number(parseAmount(f.recargo).value || 0)
    : inv.recargo || 0;
  const total = base + iva + recargo;
  const rr = parsePercent(f.retentionRate || "", { label: "Retención rate" });
  const retExpected =
    typeof rr.value === "number" ? Math.round(base * rr.value) : null;
  const retText = retTouched
    ? f.retention
    : retExpected != null
      ? canon(retExpected)
      : "";
  const retention = parseAmount(retText || "");
  const printed: Parsed = isNew
    ? parseAmount(f.printed || "")
    : { empty: true };
  const kindIssued = (isNew ? f.kind : inv?.kind) === "issued";
  const issueYear = /^\d{4}-\d{2}-\d{2}$/.test(f.date || "")
    ? +f.date.slice(0, 4)
    : +TODAY.slice(0, 4);
  const next =
    isNew && f.kind === "issued"
      ? nextNumber(state.data.invoices, {
          series: f.series.trim(),
          cls: f.cls,
          year: issueYear,
        })
      : null;
  const suggestion = next?.number || null;
  const lockMsg =
    "Part of the invoice's identity, fixed once it is in the catalogue.";
  const fieldsChanged = inv
    ? [
        "counterparty",
        "country",
        "series",
        "rectifies",
        "opDate",
        "ivaCategory",
        "operationType",
        "cls",
        "notes",
        "payment",
        "paymentId",
      ]
        .filter(
          (k) =>
            (f[k as keyof InvForm] || "") !==
            ((k === "opDate"
              ? inv.opDate
              : k === "rectifies"
                ? inv.rectifies
                : (inv as unknown as Record<string, string | null>)[k]) || ""),
        )
        .concat(
          (rr.value ?? null) !== (inv.retentionRate ?? null)
            ? ["retentionRate"]
            : [],
        )
        .concat(
          (retention.value ?? null) !== (inv.retention ?? null)
            ? ["retention"]
            : [],
        )
    : [];
  function validate() {
    const e: Record<string, string> = {};
    if (isNew && !f.kind) e.kind = "Choose whether you issued or received it.";
    if (!f.counterparty.trim())
      e.counterparty = "A counterparty name is required.";
    if (!/^[A-Za-z]{2}$/.test(f.country))
      e.country = f.country
        ? `“${f.country}” is not a two-letter country code.`
        : "Say where the counterparty is established: there is no default.";
    if (isNew) {
      if (!f.number.trim()) e.number = "The invoice number is required.";
      const d = parseDateIso(f.date);
      if (d.error || d.empty) e.date = d.error || "The issue date is required.";
      if (
        f.nif &&
        !/^[A-Z0-9-]{5,20}$/.test(f.nif.toUpperCase().replace(/\s/g, ""))
      )
        e.nif = `“${f.nif}” does not look like a tax id. Letters and digits only.`;
      if (!/^[A-Z]{3}$/.test(f.currency))
        e.currency = "Use a three-letter currency code.";
      const lineErr = calc.find((c) => c.err);
      if (lineErr) e.lines = lineErr.err ?? "";
      else if (lines.some((l) => l.description.trim() && !l.rate))
        e.lines = "Choose a rate for each line.";
      else if (
        !lines.some((l, i) => l.description.trim() && calc[i]?.sub != null)
      )
        e.lines =
          "Add at least one line with a description, a quantity above zero, a price and a rate.";
      if (!printed.empty && printed.value !== total)
        e.printed = `The printed total ${canon(Number(printed.value))} does not equal base + IVA + recargo = ${canon(total)}.`;
    }
    if (f.cls === "rectificativa") {
      if (!f.series.trim()) e.series = "A rectificativa needs a series.";
      if (!f.rectifies.trim())
        e.rectifies = "A rectificativa names the invoice it rectifies.";
    }
    if (rr.error) e.retentionRate = rr.error;
    if (retention.error) e.retention = retention.error;
    if (rr.value != null && retention.empty)
      e.retention = "A retención rate needs its amount.";
    if (typeof retention.value === "number" && retention.value > base)
      e.retention = "Retención cannot exceed the taxable base.";
    if (f.opDate) {
      const d = parseDateIso(f.opDate);
      if (d.error) e.opDate = d.error;
    }
    setErrors(e);
    return !Object.keys(e).length;
  }
  async function save() {
    setBusy(true);
    await sleep(900);
    setBusy(false);
    if (isNew) {
      const newInv: Invoice = {
        id: hashHex("inv" + f.number + f.date + CLOCK),
        kind: f.kind,
        cls: f.cls,
        series: f.series || null,
        number: f.number.trim(),
        date: f.date,
        opDate: f.opDate || null,
        counterparty: f.counterparty.trim(),
        nif: f.nif ? f.nif.toUpperCase() : null,
        country: f.country.toUpperCase(),
        idState: null,
        base,
        iva,
        recargo: recargo || null,
        retentionRate: typeof rr.value === "number" ? rr.value : null,
        retention: typeof retention.value === "number" ? retention.value : null,
        total,
        currency: f.currency,
        lines: lines
          .filter((_l, i) => calc[i]?.sub != null)
          .map((l) => {
            const c = lineCalc(l);
            return {
              description: l.description,
              qty: Number(parseDecimal6(l.qty, { label: "Quantity" }).value),
              qtyText: l.qty,
              price:
                Number(parseDecimal6(l.price, { label: "Unit price" }).value) *
                100,
              priceText: l.price,
              subtotal: c.sub ?? 0,
              rate: l.rate,
              iva: c.iva ?? 0,
              category: f.kind === "received" ? l.category || null : null,
            };
          }),
        payment: "pending",
        paymentId: null,
        linked: [],
        notes: f.notes,
        ivaCategory: f.ivaCategory || null,
        operationType: f.operationType || null,
        rectifies: f.rectifies || null,
        created: NOW(),
        provenance: "Entered in Cadrumo",
      };
      dispatch({
        type: "DATA",
        fn: (d) => ({ ...d, invoices: [...d.invoices, newInv] }),
      });
      page.toast(`Invoice ${newInv.number} added`);
      if (prefill?.rowId) page.offerLink(prefill.rowId, newInv);
      page.openInvoice(newInv.id);
    } else {
      dispatch({
        type: "DATA",
        fn: (d) => ({
          ...d,
          invoices: d.invoices.map((x) =>
            x.id === inv.id
              ? {
                  ...x,
                  counterparty: f.counterparty.trim(),
                  country: f.country.toUpperCase(),
                  series: f.series || null,
                  rectifies: f.rectifies || null,
                  opDate: f.opDate || null,
                  ivaCategory: f.ivaCategory || null,
                  operationType: f.operationType || null,
                  cls: f.cls,
                  notes: f.notes,
                  retentionRate: typeof rr.value === "number" ? rr.value : null,
                  retention:
                    typeof retention.value === "number"
                      ? retention.value
                      : null,
                  payment: f.payment,
                  paymentId: f.paymentId || null,
                }
              : x,
          ),
        }),
      });
      page.toast(`Invoice ${inv?.number} saved`);
      setReview(false);
    }
  }
  const ro = (label: string, value: ReactNode, mono?: boolean) => (
    <div className="field">
      <span className="field-label">{label}</span>
      <span
        className={cx("ro-value row g1", mono && "mono t-sm")}
        data-tip={lockMsg}
      >
        {value || "—"}
        <Icon name="lock" size="xs" className="muted" />
      </span>
    </div>
  );
  const setLine = (i: number, patch: Partial<LineForm>) =>
    setLines(lines.map((x, j) => (j === i ? { ...x, ...patch } : x)));
  const initial = useRef(JSON.stringify([f, lines]));
  const [asking, setAsking] = useState(false);
  const dirty = isNew
    ? JSON.stringify([f, lines]) !== initial.current
    : fieldsChanged.length > 0;
  const tryClose = () => {
    if (dirty && !asking) {
      setAsking(true);
      return;
    }
    if (!asking) onClose();
  };
  return (
    <Dialog
      sheet
      onClose={asking ? () => setAsking(false) : tryClose}
      focusFirst
      title={isNew ? "New invoice" : `Invoice ${inv.number}`}
      desc={
        isNew
          ? "Written to the catalogue when you add it."
          : `${inv.kind === "issued" ? "Issued to" : "Received from"} ${inv.counterparty} · ${PAYMENT[inv.payment]} · ${plural(inv.linked.length, "linked movement")}`
      }
      footer={
        <>
          {!isNew ? (
            removing ? (
              <>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => setRemoving(false)}
                >
                  Keep it
                </Button>
                {!inv.linked.length ? (
                  <Button
                    size="sm"
                    variant="destructive"
                    onClick={() => {
                      dispatch({
                        type: "DATA",
                        fn: (d) => ({
                          ...d,
                          invoices: d.invoices.filter((x) => x.id !== inv.id),
                        }),
                      });
                      page.toast(`Invoice ${inv.number} removed`);
                      onClose();
                    }}
                  >
                    Remove invoice
                  </Button>
                ) : null}
              </>
            ) : (
              <Button
                size="sm"
                variant="ghost"
                icon="trash"
                onClick={() => setRemoving(true)}
              >
                Remove…
              </Button>
            )
          ) : null}
          <span className="f1"></span>
          <Button size="sm" variant="ghost" onClick={tryClose}>
            {isNew ? "Cancel" : "Close"}
          </Button>
          {isNew ? (
            <Button
              size="sm"
              pending={busy}
              onClick={() => validate() && save()}
            >
              Add invoice
            </Button>
          ) : review ? (
            <Button size="sm" pending={busy} onClick={save}>
              Save
            </Button>
          ) : (
            <Button
              size="sm"
              disabled={!fieldsChanged.length}
              onClick={() => validate() && setReview(true)}
            >
              Review changes
            </Button>
          )}
        </>
      }
    >
      <div className="col g4">
        {asking ? (
          <Alert
            tone="warning"
            role="alertdialog"
            title={isNew ? "Discard this invoice?" : "Discard these changes?"}
          >
            Nothing has been written yet.
            <div className="row g2" style={{ marginTop: "var(--spacing)" }}>
              <Button size="xs" data-autofocus onClick={() => setAsking(false)}>
                Keep editing
              </Button>
              <Button size="xs" variant="destructive" onClick={onClose}>
                Discard
              </Button>
            </div>
          </Alert>
        ) : null}
        {isNew ? (
          <Field label="This is" req error={errors.kind}>
            <Seg
              label="Invoice kind"
              value={f.kind}
              onChange={(v) => {
                set("kind")(v);
              }}
              options={[
                { value: "issued", label: "Invoice I issued" },
                { value: "received", label: "Invoice I received" },
              ]}
            />
          </Field>
        ) : (
          <Alert icon="lock">
            Kind, number, issue date, tax id, currency, total and lines are the
            invoice's identity and are fixed once it is in the catalogue.
          </Alert>
        )}
        <section className="sec">
          <h3 className="sec-title">Party</h3>
          <div className="formgrid">
            {!isNew
              ? ro(
                  "Kind",
                  inv.kind === "issued"
                    ? "Invoice I issued"
                    : "Invoice I received",
                )
              : null}
            <Field label="Counterparty name" req error={errors.counterparty}>
              <Input
                value={f.counterparty}
                onChange={set("counterparty")}
                aria-invalid={!!errors.counterparty}
              />
            </Field>
            {isNew ? (
              <Field
                label="Counterparty tax id"
                hint="NIF, NIE, CIF or VAT number. The ledger says when one is required."
                error={errors.nif}
              >
                <Input
                  value={f.nif}
                  className="mono"
                  onChange={set("nif")}
                  aria-invalid={!!errors.nif}
                />
              </Field>
            ) : (
              ro("Counterparty tax id", inv.nif || "None", true)
            )}
            <Field
              label="Country"
              req
              hint="Two letters, e.g. ES"
              error={errors.country}
            >
              <Input
                value={f.country}
                maxLength={2}
                placeholder="e.g. ES"
                onChange={(e) => set("country")(e.target.value.toUpperCase())}
                aria-invalid={!!errors.country}
              />
            </Field>
          </div>
        </section>
        <section className="sec">
          <h3 className="sec-title">Document</h3>
          <div className="formgrid">
            <Field label="Class">
              <Select value={f.cls} onChange={set("cls")}>
                {Object.entries(INVOICE_CLASS).map(([k, l]) => (
                  <option key={k} value={k}>
                    {l}
                  </option>
                ))}
              </Select>
            </Field>
            <Field
              label="Series"
              req={f.cls === "rectificativa"}
              error={errors.series}
            >
              <Input value={f.series} onChange={set("series")} />
            </Field>
            {isNew ? (
              <Field
                label="Number"
                req
                error={errors.number}
                hint={
                  next
                    ? `Next in series ${next.series}: ${next.number}`
                    : f.kind === "issued" && f.cls === "rectificativa"
                      ? "Choose a series to see the next number"
                      : undefined
                }
              >
                <div className="row g1">
                  <Input
                    className="f1"
                    value={f.number}
                    onChange={set("number")}
                    aria-invalid={!!errors.number}
                  />
                  {suggestion && f.number !== suggestion ? (
                    <Button
                      size="sm"
                      variant="outline"
                      aria-label={`Use ${suggestion}`}
                      onClick={() =>
                        setF({
                          ...f,
                          number: suggestion,
                          series: f.series || next?.series || "",
                        })
                      }
                    >
                      Use
                    </Button>
                  ) : null}
                </div>
              </Field>
            ) : (
              ro("Number", inv.number)
            )}
            {isNew ? (
              <Field
                label="Issue date"
                req
                hint="Year-month-day"
                error={errors.date}
              >
                <Input
                  value={f.date}
                  placeholder={TODAY}
                  onChange={set("date")}
                  aria-invalid={!!errors.date}
                />
              </Field>
            ) : (
              ro("Issue date", fmtDateLong(inv.date))
            )}
            <Field
              label="Operation date"
              hint="If it differs from the issue date (devengo)"
              error={errors.opDate}
            >
              <Input
                value={f.opDate}
                placeholder="Same as issue"
                onChange={set("opDate")}
              />
            </Field>
            {f.cls === "rectificativa" ? (
              <Field label="Rectifies invoice" req error={errors.rectifies}>
                <Input value={f.rectifies} onChange={set("rectifies")} />
              </Field>
            ) : null}
            {isNew ? (
              <Field
                label="Currency"
                req
                hint={
                  prefill?.currency
                    ? "From the movement"
                    : "Three letters, e.g. EUR"
                }
                error={errors.currency}
              >
                <Input
                  value={f.currency}
                  maxLength={3}
                  onChange={(e) =>
                    set("currency")(e.target.value.toUpperCase())
                  }
                />
              </Field>
            ) : (
              ro("Currency", inv.currency)
            )}
            <Field label="IVA category">
              <Select value={f.ivaCategory} onChange={set("ivaCategory")}>
                <option value="">From the lines</option>
                {IVA_GROUPS.map(([g, it]) => (
                  <optgroup key={g} label={g}>
                    {it.map(([k, l]) => (
                      <option key={k} value={k}>
                        {l}
                      </option>
                    ))}
                  </optgroup>
                ))}
              </Select>
            </Field>
            <Field
              label="Operation type"
              hint="For intra-community operations and Modelo 349"
            >
              <Select value={f.operationType} onChange={set("operationType")}>
                <option value="">None</option>
                {Object.entries(OPERATION_TYPES).map(([k, l]) => (
                  <option key={k} value={k}>
                    {l}
                  </option>
                ))}
              </Select>
            </Field>
          </div>
        </section>
        <section className="sec">
          <h3 className="sec-title">
            Lines
            {!isNew ? (
              <span className="ml-auto muted row g1 t-xs">
                <Icon name="lock" size="xs" />
                fixed after creation
              </span>
            ) : null}
          </h3>
          {errors.lines ? (
            <span className="danger-t t-sm row g1" role="alert">
              <Icon name="alert" size="xs" />
              {errors.lines}
            </span>
          ) : null}
          {prefill?.amount ? (
            <p className="t-sm muted">
              The movement is {fmtMoney(prefill.amount)}{" "}
              {prefill.currency || "EUR"}. Enter the price before IVA and choose
              the rate printed on the invoice.
            </p>
          ) : null}
          <div
            className="scroll-x"
            tabIndex={0}
            aria-label="Invoice lines table"
          >
            <table className="tbl" aria-label="Invoice lines">
              <thead>
                <tr>
                  <th scope="col">Description</th>
                  <th
                    scope="col"
                    className="num"
                    style={{ width: "calc(var(--spacing) * 20)" }}
                  >
                    Qty
                  </th>
                  <th
                    scope="col"
                    className="num"
                    style={{ width: "calc(var(--spacing) * 28)" }}
                  >
                    Unit price
                  </th>
                  <th scope="col" className="num">
                    Subtotal
                  </th>
                  <th
                    scope="col"
                    style={{ width: "calc(var(--spacing) * 32)" }}
                  >
                    IVA rate
                  </th>
                  <th scope="col" className="num">
                    IVA
                  </th>
                  {kindIssued ? null : <th scope="col">Category</th>}
                  {isNew ? (
                    <th scope="col">
                      <span className="sr-only">Actions</span>
                    </th>
                  ) : null}
                </tr>
              </thead>
              <tbody>
                {lines.map((l, i) => {
                  const qe = parseDecimal6(l.qty, {
                      label: "Quantity",
                      positive: true,
                    }).error,
                    pe = parseDecimal6(l.price, { label: "Unit price" }).error;
                  return (
                    <tr key={i}>
                      <td>
                        {isNew ? (
                          <Input
                            size="sm"
                            value={l.description}
                            aria-label={`Line ${i + 1} description`}
                            onChange={(e) =>
                              setLine(i, { description: e.target.value })
                            }
                          />
                        ) : (
                          l.description
                        )}
                      </td>
                      <td className="num">
                        {isNew ? (
                          <Input
                            size="sm"
                            className="tnum"
                            style={{ textAlign: "right" }}
                            value={l.qty}
                            inputMode="decimal"
                            aria-label={`Line ${i + 1} quantity`}
                            aria-invalid={!!qe}
                            data-tip={qe || undefined}
                            onChange={(e) =>
                              setLine(i, { qty: e.target.value })
                            }
                          />
                        ) : (
                          l.qty
                        )}
                      </td>
                      <td className="num">
                        {isNew ? (
                          <Input
                            size="sm"
                            className="tnum"
                            style={{ textAlign: "right" }}
                            value={l.price}
                            placeholder="0.00"
                            inputMode="decimal"
                            aria-label={`Line ${i + 1} unit price`}
                            aria-invalid={!!pe}
                            data-tip={pe || undefined}
                            onChange={(e) =>
                              setLine(i, { price: e.target.value })
                            }
                          />
                        ) : (
                          l.price
                        )}
                      </td>
                      <td className="num">
                        {calc[i]?.sub != null ? (
                          fmtMoney(calc[i]!.sub)
                        ) : (
                          <span className="muted">—</span>
                        )}
                      </td>
                      <td>
                        {isNew ? (
                          <Select
                            size="sm"
                            value={l.rate}
                            aria-label={`Line ${i + 1} IVA rate`}
                            onChange={(e) =>
                              setLine(i, { rate: e.target.value })
                            }
                          >
                            <option value="" disabled>
                              Choose a rate
                            </option>
                            {LINE_RATES.map(([k, lab]) => (
                              <option key={k} value={k}>
                                {lab}
                              </option>
                            ))}
                          </Select>
                        ) : (
                          LINE_RATES.find(([k]) => k === l.rate)?.[1]
                        )}
                      </td>
                      <td className="num">
                        {calc[i]?.iva != null ? (
                          fmtMoney(calc[i]!.iva)
                        ) : (
                          <span className="muted">—</span>
                        )}
                      </td>
                      {kindIssued ? null : (
                        <td>
                          {isNew ? (
                            <Select
                              size="sm"
                              value={l.category}
                              aria-label={`Line ${i + 1} category`}
                              onChange={(e) =>
                                setLine(i, { category: e.target.value })
                              }
                            >
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
                          ) : l.category ? (
                            CATEGORY_LABEL[l.category]
                          ) : (
                            <span className="muted">None</span>
                          )}
                        </td>
                      )}
                      {isNew ? (
                        <td>
                          <IconButton
                            icon="close"
                            label={`Remove line ${i + 1}`}
                            disabled={lines.length === 1}
                            onClick={() =>
                              setLines(lines.filter((_, j) => j !== i))
                            }
                          />
                        </td>
                      ) : null}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          {isNew ? (
            <div>
              <Button
                size="xs"
                variant="ghost"
                icon="plus"
                onClick={() =>
                  setLines([
                    ...lines,
                    {
                      description: "",
                      qty: "1",
                      price: "",
                      rate: "",
                      category: "",
                    },
                  ])
                }
              >
                Add a line
              </Button>
            </div>
          ) : null}
          <p className="t-xs muted">
            Quantities and unit prices take a dot for decimals, up to six
            places, with no thousands separator. Subtotal is quantity × unit
            price, and IVA the subtotal at the line's rate, each to the cent.
          </p>
        </section>
        <section className="sec">
          <h3 className="sec-title">Totals</h3>
          <div className="split2">
            <div className="card-wash">
              <dl className="kv">
                <dt>Taxable base</dt>
                <dd className="tnum">{fmtMoney(base)}</dd>
                <dt>IVA</dt>
                <dd className="tnum">{fmtMoney(iva)}</dd>
                <dt>Recargo</dt>
                <dd>
                  {isNew ? (
                    <Input
                      size="sm"
                      className="tnum"
                      value={f.recargo}
                      placeholder="0.00"
                      aria-label="Recargo"
                      onChange={set("recargo")}
                    />
                  ) : (
                    <span className="tnum">{fmtMoney(recargo)}</span>
                  )}
                </dd>
                <dt className="fw6">Total</dt>
                <dd className="tnum fw6">
                  {fmtMoney(total)} {isNew ? f.currency : inv.currency}
                </dd>
              </dl>
              {isNew ? (
                <Field
                  label="Printed total (optional)"
                  hint="Type the total printed on the invoice to check it closes."
                  error={errors.printed}
                >
                  <Input
                    size="sm"
                    className="tnum"
                    value={f.printed}
                    onChange={set("printed")}
                  />
                </Field>
              ) : null}
            </div>
            <div className="card-wash">
              <div className="sec-title">Retención, outside the total</div>
              <div
                className="row g1 wrap"
                role="group"
                aria-label="Common retención rates"
              >
                {["15", "7", "19"].map((r) => (
                  <button
                    key={r}
                    type="button"
                    className="btn pill"
                    aria-pressed={f.retentionRate === r}
                    onClick={() => {
                      setF({ ...f, retentionRate: r });
                      setRetTouched(false);
                    }}
                  >
                    {r}%
                  </button>
                ))}
              </div>
              <div className="row g2">
                <Field
                  label="Rate"
                  className="f1"
                  hint="Write 15 for 15%"
                  error={errors.retentionRate}
                >
                  <Input
                    size="sm"
                    value={f.retentionRate}
                    placeholder="e.g. 15"
                    onChange={(e) => {
                      set("retentionRate")(e);
                      setRetTouched(false);
                    }}
                  />
                </Field>
                <Field
                  label="Amount"
                  className="f1"
                  hint={
                    retTouched && retExpected != null
                      ? `Worked out: ${fmtMoney(retExpected)}`
                      : "Worked out from the rate; you can change it"
                  }
                  error={errors.retention}
                >
                  <Input
                    size="sm"
                    className="tnum"
                    value={retText}
                    placeholder="0.00"
                    onChange={(e) => {
                      setRetTouched(true);
                      set("retention")(e);
                    }}
                  />
                </Field>
              </div>
              <span className="t-sm tnum">
                To be paid {fmtMoney(total - Number(retention.value || 0))}
                {retention.value ? (
                  <span className="muted">
                    (− {fmtMoney(Number(retention.value))} retención)
                  </span>
                ) : null}
              </span>
            </div>
          </div>
        </section>
        {!isNew ? (
          <section className="sec">
            <h3 className="sec-title">Payment</h3>
            <div className="formgrid">
              <Field label="Payment status">
                <Select value={f.payment} onChange={set("payment")}>
                  {Object.entries(PAYMENT).map(([k, l]) => (
                    <option key={k} value={k}>
                      {l}
                    </option>
                  ))}
                </Select>
              </Field>
              <Field
                label="Payment reference"
                hint="The bank or card reference, if you have it"
              >
                <Input value={f.paymentId} onChange={set("paymentId")} />
              </Field>
            </div>
          </section>
        ) : null}
        <Field label="Notes">
          <textarea
            className="input"
            value={f.notes}
            onChange={set("notes")}
          ></textarea>
        </Field>
        {!isNew ? (
          <section className="sec">
            <h3 className="sec-title">Linked movements</h3>
            {inv.linked.length ? (
              <ul className="list-rows">
                {inv.linked.map((tid) => {
                  const r = state.data.byId[tid];
                  return (
                    <li key={tid}>
                      <Icon name="link" size="xs" />
                      {r ? (
                        <>
                          <span className="f1 wrapt">{r.description}</span>
                          <span className="tnum">{fmtMoney(r.amount)}</span>
                          <Button
                            size="xs"
                            variant="ghost"
                            onClick={() => {
                              onClose();
                              page.jumpTo(tid);
                            }}
                          >
                            Show
                          </Button>
                        </>
                      ) : (
                        <span className="f1">
                          A removed movement: a one-sided link
                        </span>
                      )}
                    </li>
                  );
                })}
              </ul>
            ) : (
              <p className="muted t-sm">
                None. Link one from a movement's inspector, or from the To match
                view.
              </p>
            )}
            <p className="t-xs muted">
              <Icon name="lock" size="xs" /> A link is permanent: it cannot be
              removed here or anywhere else.
            </p>
            <p className="t-xs muted">{inv.provenance}.</p>
          </section>
        ) : null}
        {review && !isNew ? (
          <Alert title="Save these changes?">
            {fieldsChanged
              .map(
                (k) =>
                  ({
                    counterparty: "Counterparty",
                    country: "Country",
                    series: "Series",
                    rectifies: "Rectifies",
                    opDate: "Operation date",
                    ivaCategory: "IVA category",
                    operationType: "Operation type",
                    cls: "Class",
                    notes: "Notes",
                    retentionRate: "Retención rate",
                    retention: "Retención amount",
                    payment: "Payment status",
                    paymentId: "Payment reference",
                  })[k],
              )
              .join(", ")}
          </Alert>
        ) : null}
        {removing ? (
          <Alert
            tone={inv && inv.linked.length ? "danger" : "warning"}
            title={
              inv && inv.linked.length
                ? "This invoice cannot be removed"
                : "Remove this invoice?"
            }
          >
            {inv && inv.linked.length
              ? `It is linked to ${plural(inv.linked.length, "movement")}. Links cannot be removed, so a linked invoice stays in the catalogue.`
              : "It leaves the catalogue. Movements are not affected."}
          </Alert>
        ) : null}
      </div>
    </Dialog>
  );
}

/* ── Documents: evidence, drafts awaiting review, intake, consent. ───── */
export function DocumentsSection() {
  const [state] = useStore();
  const page = usePage();
  const [sub, setSub] = useState("queue");
  const docs = state.data.docs;
  const queue = docs.filter((d) => d.state === "draft" || d.state === "paused");
  const list = sub === "queue" ? queue : docs;
  const [cur, setCur] = useState(page.docFocus || queue[0]?.id);
  useEffect(() => {
    if (page.docFocus) {
      setCur(page.docFocus);
      setSub("all");
      page.docFocus = null;
    }
  }, [page, page.docFocus]);
  const doc = docs.find((d) => d.id === cur);
  const tabs = [
    { value: "queue", label: "To review", badge: queue.length },
    { value: "all", label: "All evidence", badge: docs.length },
    { value: "attach", label: "Mail attachments" },
    { value: "batch", label: "Folder intake" },
    { value: "consent", label: "Sent off this computer" },
    { value: "reader", label: "Readers" },
  ];
  return (
    <div className="section">
      <div className="section-bar">
        <div className="scroll-x" style={{ minWidth: 0 }}>
          <Tabs
            size="sm"
            value={sub}
            onChange={setSub}
            tabs={tabs}
            label="Documents"
          />
        </div>
        <span className="ml-auto"></span>
        <Button
          size="sm"
          variant="outline"
          icon="upload"
          onClick={() => page.openDialog("import", { kind: "documents" })}
        >
          Add documents
        </Button>
      </div>
      {sub === "queue" || sub === "all" ? (
        <div className="split-list">
          <div className="left" role="listbox" aria-label="Documents">
            {list.length ? (
              list.map((d) => (
                <button
                  key={d.id}
                  type="button"
                  className="doc-item"
                  role="option"
                  aria-selected={d.id === cur}
                  onClick={() => setCur(d.id)}
                >
                  <span className="row g2">
                    <Icon
                      name={
                        d.media === "image"
                          ? "image"
                          : d.media === "xml"
                            ? "sheet"
                            : "page"
                      }
                      size="xs"
                    />
                    <span className="fw5 truncate f1">{d.file}</span>
                  </span>
                  <span className="row g2 t-sm muted">
                    <DocState d={d} />
                    <span className="f1"></span>
                    <span className="tnum">{fmtDate(d.added)}</span>
                  </span>
                </button>
              ))
            ) : (
              <Empty
                icon="check"
                title="Nothing to review"
                desc="Every document is confirmed or kept as evidence."
              />
            )}
          </div>
          <div className="right">
            {doc ? (
              <DocDetail key={doc.id} d={doc} />
            ) : (
              <Empty icon="page" title="Choose a document" />
            )}
          </div>
        </div>
      ) : sub === "attach" ? (
        <div className="section-body">
          <div className="panel">
            <div className="panel-head">
              <h3>Mail attachments waiting for review</h3>
              <span className="sub">From your connected mailbox export</span>
            </div>
            <DataTable
              label="Mail attachments"
              rowKey={(r) => r.f}
              rows={[
                {
                  f: "Factura_Octubre_ArroyoAsesores.pdf",
                  from: "facturacion@ (synthetic)",
                  at: "2026-10-03",
                  size: "84 KB",
                },
                {
                  f: "LinkedIn_Invoice_IE447188.pdf",
                  from: "billing@ (synthetic)",
                  at: "2026-10-19",
                  size: "51 KB",
                },
              ]}
              columns={[
                { key: "f", label: "Attachment" },
                { key: "from", label: "From" },
                {
                  key: "at",
                  label: "Received",
                  render: (r) => fmtDateLong(r.at),
                },
                { key: "size", label: "Size", num: true },
                {
                  key: "x",
                  label: "",
                  render: () => (
                    <Button
                      size="xs"
                      variant="outline"
                      onClick={() =>
                        page.toast("Attachment details and origin (simulated)")
                      }
                    >
                      View
                    </Button>
                  ),
                },
              ]}
            />
          </div>
        </div>
      ) : sub === "batch" ? (
        <BatchIntake />
      ) : sub === "consent" ? (
        <div className="section-body">
          <div className="panel">
            <div className="panel-head">
              <h3>Sent off this computer</h3>
              <span className="sub">
                Every time a document left this computer to be read, and what
                was derived from it
              </span>
            </div>
            <DataTable
              label="Sent off this computer"
              rowKey={(r) => r.at}
              rows={state.data.consent}
              columns={[
                { key: "at", label: "When", render: (r) => fmtStamp(r.at) },
                { key: "file", label: "Document" },
                { key: "provider", label: "Read by" },
                {
                  key: "ack",
                  label: "Your acknowledgement",
                  render: () => (
                    <span className="row g1">
                      <Icon name="check" size="xs" className="ok-t" />
                      Given for this read
                    </span>
                  ),
                },
                {
                  key: "derived",
                  label: "Derived",
                  wrap: true,
                  render: (r) => r.derived.join(" · "),
                },
                { key: "effect", label: "Recorded", render: (r) => r.effect },
              ]}
            />
          </div>
          <p className="t-sm muted">
            Reading on this computer records nothing here. A read by another
            provider needs your acknowledgement each time, and is recorded
            before the document leaves.
          </p>
        </div>
      ) : (
        <ReaderReadiness />
      )}
    </div>
  );
}
export function DocState({ d }: { d: Doc }) {
  if (d.state === "confirmed")
    return (
      <span className="row g1">
        <Icon name="check" size="xs" className="ok-t" />
        Confirmed
      </span>
    );
  if (d.state === "evidence")
    return (
      <span className="row g1">
        <Icon name="attach" size="xs" />
        Evidence
      </span>
    );
  if (d.state === "paused")
    return (
      <span className="row g1">
        <Icon name="pause" size="xs" className="warn-t" />
        Not read
      </span>
    );
  return d.findings.length ? (
    <span className="row g1">
      <Icon name="alert" size="xs" className="warn-t" />
      {plural(d.findings.length, "question")} to answer
    </span>
  ) : (
    <span className="row g1">
      <Icon name="pending" size="xs" />
      Ready to confirm
    </span>
  );
}
export const DRAFT_LABEL: Record<string, string> = {
  supplier: "Supplier",
  customer: "Customer",
  supplier_tax_id: "Supplier tax id",
  customer_tax_id: "Customer tax id",
  invoice_number: "Invoice number",
  invoice_date: "Invoice date",
  taxable_base: "Taxable base",
  iva_rate: "IVA rate",
  iva_amount: "IVA amount",
  retencion_amount: "Retención",
  grand_total: "Total",
  currency: "Currency",
};
export function DocDetail({ d }: { d: Doc }) {
  const [state, dispatch] = useStore();
  const page = usePage();
  const [vals, setVals] = useState<Record<string, string>>(
    () =>
      Object.fromEntries(
        Object.entries(d.draft).map(([k, v]) => [k, v[0]]),
      ) as Record<string, string>,
  );
  const [res, setRes] = useState<DraftRes>({});
  const [kind, setKind] = useState(d.kind || "");
  const [country, setCountry] = useState("");
  const [currency, setCurrency] = useState(d.draft.currency?.[0] || "");
  const [busy, setBusy] = useState(false);
  const [rereading, setRereading] = useState(false);
  const [anyway, setAnyway] = useState(false);
  const [confirmed, setConfirmed] = useState<Invoice | null>(null);
  const [removing, setRemoving] = useState(false);
  const edited = (k: string) => vals[k] !== d.draft[k]?.[0];
  const resolved = (b: Finding) => {
    const r = res[b.id];
    return (
      r &&
      ((r.action === "choose_candidate" && r.value) ||
        (r.action === "supply_value" && r.value?.trim()) ||
        (r.action === "attest" && r.note?.trim()))
    );
  };
  const open = d.findings.filter((b) => !resolved(b));
  const linkedInv = d.invoice
    ? state.data.invoices.find((i) => i.id === d.invoice)
    : null;
  const row = d.rowId ? state.data.byId[d.rowId] : null;
  const total = Number(parseAmount(vals.grand_total || "").value ?? NaN);
  const taxId = (
    vals.supplier_tax_id ||
    vals.customer_tax_id ||
    ""
  ).toUpperCase();
  const dup =
    d.state === "draft"
      ? state.data.invoices.find(
          (i) =>
            i.number === vals.invoice_number ||
            (taxId &&
              i.nif === taxId &&
              i.total === total &&
              i.date === vals.invoice_date),
        )
      : null;
  const canConfirm =
    d.state === "draft" &&
    !open.length &&
    /^[A-Za-z]{2}$/.test(country) &&
    kind &&
    /^[A-Za-z]{3}$/.test(currency) &&
    (!dup || anyway);
  const matchRow = (inv: Invoice) =>
    Object.values(state.data.byId).find(
      (r) =>
        !r.invoiceId &&
        r.lifecycle === "active" &&
        Math.abs(r.amount - (inv.total - (inv.retention || 0))) <= 1 &&
        (inv.kind === "issued") === (r.direction === "in"),
    );
  async function confirmDraft() {
    setBusy(true);
    await sleep(1200);
    setBusy(false);
    const n = vals.invoice_number ?? "",
      base = Number(parseAmount(vals.taxable_base || "0").value || 0);
    const rateKey =
      LINE_RATES.find(
        ([, , r]) =>
          Math.abs(r * 100 - parseFloat(vals.iva_rate || "NaN")) < 1e-6,
      )?.[0] || null;
    const inv: Invoice = {
      id: hashHex("conf" + d.id),
      kind,
      cls: "ordinaria",
      series: null,
      number: n,
      date: vals.invoice_date ?? "",
      opDate: null,
      counterparty: vals.supplier || vals.customer || "",
      nif: taxId || null,
      country: country.toUpperCase(),
      idState: null,
      base,
      iva: (total || 0) - base,
      recargo: null,
      retentionRate: null,
      retention: vals.retencion_amount
        ? Number(parseAmount(vals.retencion_amount).value)
        : null,
      total: total || 0,
      currency: currency.toUpperCase(),
      lines: [
        {
          description: "As read from " + d.file,
          qty: 1,
          price: base,
          subtotal: base,
          qtyText: "1",
          priceText: canon(base),
          rate: rateKey ?? "",
          iva: (total || 0) - base,
          category: null,
        },
      ],
      payment: "pending",
      paymentId: null,
      linked: [],
      notes: "",
      ivaCategory: null,
      operationType: null,
      rectifies: null,
      created: NOW(),
      provenance: `Confirmed from ${d.file}`,
    };
    dispatch({
      type: "DATA",
      fn: (data) => ({
        ...data,
        invoices: [...data.invoices, inv],
        docs: data.docs.map((x) =>
          x.id === d.id ? { ...x, state: "confirmed", invoice: inv.id } : x,
        ),
      }),
    });
    setConfirmed(inv);
    page.toast(`Confirmed as invoice ${n}`);
  }
  const attachToExisting = () => {
    dispatch({
      type: "DATA",
      fn: (data) => ({
        ...data,
        docs: data.docs.map((x) =>
          x.id === d.id ? { ...x, state: "evidence", invoice: dup?.id } : x,
        ),
      }),
    });
    page.toast(`Kept as evidence of invoice ${dup?.number}`);
  };
  const offer =
    confirmed ||
    (d.state === "confirmed" && linkedInv && !linkedInv.linked.length
      ? linkedInv
      : null);
  const offerRow = offer ? matchRow(offer) : null;
  const stagedLink =
    offerRow &&
    state.staged.actions.some(
      (a) => a.type === "link" && a.rowIds[0] === offerRow.id,
    );
  return (
    <div className="section-body">
      <div className="row g3 wrap">
        <div className="f1 col g1">
          <h2 className="t-md fw6 wrapt">{d.file}</h2>
          <span className="muted t-sm">
            {d.media.toUpperCase()} · added {fmtDateLong(d.added)}
          </span>
        </div>
        <DocState d={d} />
      </div>
      {d.note ? <Alert icon="info">{d.note}</Alert> : null}
      {d.state === "paused" ? (
        <Alert
          tone="warning"
          icon="pause"
          title="Nothing was read"
          action={
            <Button
              size="sm"
              variant="outline"
              pending={rereading}
              onClick={async () => {
                setRereading(true);
                await sleep(1400);
                setRereading(false);
                dispatch({
                  type: "DATA",
                  fn: (data) => ({
                    ...data,
                    docs: data.docs.map((x) =>
                      x.id === d.id
                        ? {
                            ...x,
                            state: "draft",
                            draft: {
                              supplier: [
                                "Iberdrola Clientes SAU",
                                "text_layer",
                                "reconciled",
                              ],
                              invoice_number: [
                                "21260801004417",
                                "text_layer",
                                "reconciled",
                              ],
                              invoice_date: [
                                "2026-08-31",
                                "text_layer",
                                "reconciled",
                              ],
                              taxable_base: [
                                "62.40",
                                "text_layer",
                                "reconciled",
                              ],
                              iva_rate: ["21", "text_layer", "reconciled"],
                              iva_amount: ["13.10", "text_layer", "reconciled"],
                              grand_total: [
                                "75.50",
                                "text_layer",
                                "reconciled",
                              ],
                              currency: ["EUR", "text_layer", "anchored"],
                            },
                          }
                        : x,
                    ),
                  }),
                });
              }}
            >
              Read again
            </Button>
          }
        >
          {d.fallback}
        </Alert>
      ) : null}
      {d.state === "confirmed" ? (
        <Alert tone="success" title="Confirmed as an invoice">
          {linkedInv ? (
            <>
              Invoice {linkedInv.number}, {fmtMoney(linkedInv.total)}.{" "}
              <Button
                variant="link"
                size="xs"
                onClick={() => page.openInvoice(linkedInv.id)}
              >
                Open invoice
              </Button>
            </>
          ) : (
            "In the catalogue."
          )}
          {row ? (
            <>
              {" "}
              Evidence for{" "}
              <Button
                variant="link"
                size="xs"
                onClick={() => page.jumpTo(row.id)}
              >
                {row.description}
              </Button>
              .
            </>
          ) : null}
        </Alert>
      ) : null}
      {offerRow ? (
        <Alert
          icon="link"
          title="Link it to its movement?"
          action={
            stagedLink ? (
              <span className="t-sm">Link staged</span>
            ) : (
              <Button
                size="sm"
                variant="outline"
                aria-label={`Link to ${offerRow.description} · permanent`}
                onClick={() =>
                  offer &&
                  stageLinkAction(dispatch, offerRow, offer, page.toast)
                }
              >
                Link · permanent
              </Button>
            )
          }
        >
          {offerRow.description} settles invoice {offer?.number}. A link is
          permanent once saved.
        </Alert>
      ) : null}
      {d.state === "evidence" ? (
        <>
          <Alert icon="attach" title="Kept as evidence">
            {row ? (
              <>
                Attached to{" "}
                <Button
                  variant="link"
                  size="xs"
                  onClick={() => page.jumpTo(row.id)}
                >
                  {row.description}
                </Button>
                .
              </>
            ) : (
              "Not attached to a movement yet."
            )}
          </Alert>
          <div className="row g2 wrap">
            <Button
              size="sm"
              variant="outline"
              onClick={() =>
                page.toast(
                  "The evidence record's description and date are editable here (simulated)",
                )
              }
            >
              Update the record…
            </Button>
            <Button
              size="sm"
              variant="ghost"
              icon="trash"
              disabled={!!row}
              data-tip={row ? "Detach it from its movement first." : undefined}
              onClick={() => setRemoving(true)}
            >
              Remove the record…
            </Button>
          </div>
          {removing ? (
            <Alert tone="warning" title="Remove this evidence record?">
              The record and its stored copy leave the ledger.{" "}
              <div className="row g2" style={{ marginTop: "var(--spacing)" }}>
                <Button
                  size="xs"
                  variant="destructive"
                  onClick={() => {
                    dispatch({
                      type: "DATA",
                      fn: (data) => ({
                        ...data,
                        docs: data.docs.filter((x) => x.id !== d.id),
                      }),
                    });
                    page.toast("Evidence record removed");
                  }}
                >
                  Remove
                </Button>
                <Button
                  size="xs"
                  variant="ghost"
                  onClick={() => setRemoving(false)}
                >
                  Keep it
                </Button>
              </div>
            </Alert>
          ) : null}
        </>
      ) : null}
      {d.state === "draft" ? (
        <>
          <div className="split2">
            <div className="paper" aria-label="Page preview (placeholder)">
              <b>{vals.supplier || vals.customer || "Document"}</b>
              <span className="mono t-xs">{vals.invoice_number || ""}</span>
              {[90, 70, 80, 40, 85, 60, 75, 30].map((w, i) => (
                <span
                  key={i}
                  className="line"
                  style={{ width: w + "%" }}
                ></span>
              ))}
              <span className="row" style={{ justifyContent: "flex-end" }}>
                <b className="tnum">{vals.grand_total || ""}</b>
              </span>
            </div>
            <div className="col g3">
              <section className="sec">
                <h3 className="sec-title">
                  What was read
                  <span className="ml-auto muted t-xs">
                    change any; your value is marked as yours
                  </span>
                </h3>
                <table
                  className="tbl"
                  aria-label="Fields read from the document"
                >
                  <thead>
                    <tr>
                      <th scope="col">Field</th>
                      <th scope="col">Value</th>
                      <th scope="col">Where it came from</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(d.draft).map(
                      ([k, [, origin, grounding]]) => (
                        <tr key={k}>
                          <td className="muted t-sm" style={{ width: "30%" }}>
                            {DRAFT_LABEL[k] || k}
                          </td>
                          <td>
                            <Input
                              size="sm"
                              value={vals[k]}
                              className={
                                /amount|base|total|rate/.test(k) ? "tnum" : ""
                              }
                              aria-label={DRAFT_LABEL[k] || k}
                              onChange={(e) =>
                                setVals({ ...vals, [k]: e.target.value })
                              }
                            />
                          </td>
                          <td style={{ width: "36%" }}>
                            {edited(k) ? (
                              <span className="prov reconciled">
                                <i></i>Entered by you
                              </span>
                            ) : (
                              <span className={cx("prov", grounding)}>
                                <i></i>
                                {FIELD_ORIGIN[origin]}, {GROUNDING[grounding]}
                              </span>
                            )}
                          </td>
                        </tr>
                      ),
                    )}
                  </tbody>
                </table>
              </section>
            </div>
          </div>
          {d.findings.length ? (
            <section className="sec">
              <h3 className="sec-title">
                Questions to answer
                <span className="ml-auto muted t-xs">
                  {open.length ? `${open.length} open` : "all answered"}
                </span>
              </h3>
              {d.findings.map((b) => {
                const r = res[b.id] ?? {};
                return (
                  <div key={b.id} className="card-raised">
                    <div className="row g2">
                      {resolved(b) ? (
                        <Icon name="check" className="ok-t" />
                      ) : (
                        <Icon name="alert" className="warn-t" />
                      )}
                      <b className="fw6 f1">{BLOCK_REASON[b.reason]}</b>
                      <span className="t-xs muted">
                        {DRAFT_LABEL[b.field] || b.field}
                      </span>
                    </div>
                    <p className="t-sm">{b.detail}</p>
                    <Seg
                      size="sm"
                      label="Answer"
                      value={r.action || ""}
                      onChange={(a) =>
                        setRes({ ...res, [b.id]: { action: a } })
                      }
                      options={[
                        {
                          value: "choose_candidate",
                          label: "Choose a reading",
                          disabled: !b.candidates.length,
                        },
                        { value: "supply_value", label: "Type the value" },
                        { value: "attest", label: "It is right as read" },
                      ]}
                    />
                    {r.action === "choose_candidate" ? (
                      <div
                        className="col g1"
                        role="radiogroup"
                        aria-label="Readings"
                      >
                        {b.candidates.map((c) => (
                          <label key={c.value} className="row g2 t-sm">
                            <input
                              type="radio"
                              name={b.id}
                              checked={r.value === c.value}
                              onChange={() =>
                                setRes({
                                  ...res,
                                  [b.id]: { ...r, value: c.value },
                                })
                              }
                            />
                            <span className="mono">{c.value}</span>
                            <span className="muted">{c.note}</span>
                          </label>
                        ))}
                      </div>
                    ) : r.action === "supply_value" ? (
                      <Input
                        size="sm"
                        aria-label="The correct value"
                        placeholder="The correct value"
                        value={r.value || ""}
                        onChange={(e) =>
                          setRes({
                            ...res,
                            [b.id]: { ...r, value: e.target.value },
                          })
                        }
                      />
                    ) : r.action === "attest" ? (
                      <Input
                        size="sm"
                        aria-label="Why the value as read is right"
                        placeholder="Why the value as read is right (required)"
                        value={r.note || ""}
                        onChange={(e) =>
                          setRes({
                            ...res,
                            [b.id]: { ...r, note: e.target.value },
                          })
                        }
                      />
                    ) : null}
                  </div>
                );
              })}
            </section>
          ) : null}
          <section className="sec">
            <h3 className="sec-title">Confirm as an invoice</h3>
            <div className="formgrid">
              <Field
                label="This is"
                req
                hint={
                  d.kind
                    ? "From where the document came in"
                    : "There is no default"
                }
              >
                <Select value={kind} onChange={(e) => setKind(e.target.value)}>
                  <option value="" disabled>
                    Choose…
                  </option>
                  <option value="received">An invoice I received</option>
                  <option value="issued">An invoice I issued</option>
                </Select>
              </Field>
              <Field
                label="Counterparty country"
                req
                hint="Two letters, e.g. ES"
              >
                <Input
                  value={country}
                  maxLength={2}
                  placeholder="e.g. ES"
                  onChange={(e) => setCountry(e.target.value.toUpperCase())}
                />
              </Field>
              <Field
                label="Currency"
                req
                hint={
                  d.draft.currency
                    ? "As read from the document"
                    : "Not on the document: say which"
                }
              >
                <Input
                  value={currency}
                  maxLength={3}
                  placeholder="e.g. EUR"
                  onChange={(e) => setCurrency(e.target.value.toUpperCase())}
                />
              </Field>
            </div>
            {dup ? (
              <Alert
                tone="warning"
                title={`Already in the catalogue: invoice ${dup.number}`}
              >
                {dup.counterparty} · {fmtDateLong(dup.date)} ·{" "}
                {fmtMoney(dup.total)}. Attach this PDF to it as evidence, or
                confirm a second invoice anyway.
                <div className="row g2" style={{ marginTop: "var(--spacing)" }}>
                  <Button size="xs" onClick={attachToExisting}>
                    Attach to {dup.number}
                  </Button>
                  <Button
                    size="xs"
                    variant="outline"
                    aria-pressed={anyway}
                    onClick={() => setAnyway(!anyway)}
                  >
                    Confirm anyway
                  </Button>
                </div>
              </Alert>
            ) : null}
            <p className="t-xs muted">
              Confirms exactly this reading. If the file or the reading changes,
              it has to be reviewed again. The document is read again on this
              computer before the invoice is written.
            </p>
            <div className="row g2">
              <Button
                disabled={!canConfirm}
                pending={busy}
                onClick={confirmDraft}
                data-tip={
                  open.length
                    ? "Answer every question first"
                    : !kind || !country || !currency
                      ? "Choose the kind, the country and the currency"
                      : dup && !anyway
                        ? "It may already be in the catalogue"
                        : undefined
                }
              >
                Confirm as invoice
              </Button>
              <Button
                variant="outline"
                icon="sync"
                onClick={() =>
                  page.toast("Read again on this computer: no changes")
                }
              >
                Read again
              </Button>
            </div>
            <details className="tech">
              <summary>Technical details</summary>
              <dl className="kv mono t-xs">
                <dt>Source digest</dt>
                <dd>sha256 {d.sha.slice(0, 16)}…</dd>
                <dt>Reading digest</dt>
                <dd>{d.reviewSha.slice(0, 16)}…</dd>
              </dl>
            </details>
          </section>
        </>
      ) : null}
    </div>
  );
}
type BatchItem = { f: string; s: string; why?: string };
export function BatchIntake() {
  const [items, setItems] = useState<BatchItem[] | null>(null);
  const [chooser, setChooser] = useState<HTMLElement | null>(null);
  const [dir, setDir] = useState("");
  const STATUS: Record<string, [IconName, string, string]> = {
    ingested: ["check", "ok-t", "Read, ready to review"],
    no_op: ["minus", "muted", "Already in the ledger"],
    refused: ["refused", "danger-t", "Refused"],
    pending_review: ["pending", "muted", "Waiting for your review"],
    paused: ["pause", "warn-t", "Paused: the reader is busy"],
  };
  return (
    <div className="section-body">
      <div className="panel">
        <div className="panel-head">
          <h3>Folder intake</h3>
          <span className="sub">
            Every document in one folder becomes evidence and a reading to
            review
          </span>
        </div>
        <div className="panel-body">
          <div className="row g2 wrap">
            <Seg
              size="sm"
              label="These documents are"
              value={dir}
              onChange={setDir}
              options={[
                { value: "received", label: "Invoices I received" },
                { value: "issued", label: "Invoices I issued" },
              ]}
            />
            <Button
              size="sm"
              variant="outline"
              icon="folder"
              disabled={!dir}
              data-tip={
                dir ? undefined : "Say whether you issued or received them"
              }
              onClick={(e) => setChooser(e.currentTarget)}
            >
              Choose a folder…
            </Button>
          </div>
          {items ? (
            <DataTable
              label="Folder results"
              rowKey={(r) => r.f}
              rows={items}
              columns={[
                { key: "f", label: "Document" },
                {
                  key: "s",
                  label: "Result",
                  render: (r) => {
                    const [i, c, l] = STATUS[r.s]!;
                    return (
                      <span className="row g1">
                        <Icon name={i} size="xs" className={c} />
                        {l}
                        {r.why ? (
                          <span className="muted"> · {r.why}</span>
                        ) : null}
                      </span>
                    );
                  },
                },
              ]}
            />
          ) : (
            <p className="muted t-sm">
              Folders inside the chosen folder are not read.
            </p>
          )}
        </div>
      </div>
      {chooser ? (
        <HostFileDialog
          anchor={chooser}
          folder
          kind="document"
          onClose={() => setChooser(null)}
          onPick={() => {
            setChooser(null);
            setItems([
              { f: "ticket-plenoil-1015.jpg", s: "pending_review" },
              { f: "factura-correos-oct.pdf", s: "ingested" },
              { f: "factura-domestika-lettering.pdf", s: "ingested" },
              { f: "factura-arroyo-2026-10.pdf", s: "no_op" },
              {
                f: "presupuesto.docx",
                s: "refused",
                why: "Not a PDF, image or e-invoice",
              },
            ]);
          }}
        />
      ) : null}
    </div>
  );
}
export function ReaderReadiness() {
  const [state] = useStore();
  const down = state.proto.state === "modelUnavailable";
  return (
    <div className="section-body">
      <div className="panel">
        <div className="panel-head">
          <h3>Readers</h3>
          <span className="sub">
            What can read documents and suggest classifications on this computer
          </span>
        </div>
        <div className="panel-body">
          <ul className="list-rows">
            <li>
              <Icon
                name={down ? "unplug" : "check"}
                className={down ? "warn-t" : "ok-t"}
              />
              <span className="f1">Local model (medium tier)</span>
              <span className="muted t-sm">
                {down
                  ? "Not loaded: not enough memory free (needs 9.1 GB, 6.4 GB free)"
                  : "Loaded, 9.1 GB"}
              </span>
            </li>
            <li>
              <Icon name="check" className="ok-t" />
              <span className="f1">PDF text and e-invoice XML</span>
              <span className="muted t-sm">Always available, no model</span>
            </li>
            <li>
              <Icon
                name={down ? "unplug" : "check"}
                className={down ? "warn-t" : "ok-t"}
              />
              <span className="f1">Reading images</span>
              <span className="muted t-sm">
                {down ? "Needs the local model" : "Available"}
              </span>
            </li>
            <li>
              <Icon name="minus" className="muted" />
              <span className="f1">Reading off this computer</span>
              <span className="muted t-sm">
                Only with your acknowledgement, each time
              </span>
            </li>
          </ul>
        </div>
      </div>
    </div>
  );
}

/* ── Setup › Rules: rules, ratios, counterparties, model diagnostics. ── */
export function RulesSection() {
  const [state] = useStore();
  const [sub, setSub] = useState("rules");
  return (
    <div className="section">
      <div className="section-bar">
        <div className="scroll-x" style={{ minWidth: 0 }}>
          <Tabs
            size="sm"
            value={sub}
            onChange={setSub}
            label="Rules"
            tabs={[
              {
                value: "rules",
                label: "Classification rules",
                badge: state.data.rules.length,
              },
              { value: "ratios", label: "Business-use ratios" },
              { value: "cps", label: "Counterparties" },
              { value: "diag", label: "Model diagnostics" },
            ]}
          />
        </div>
      </div>
      {sub === "rules" ? (
        <RulesPane />
      ) : sub === "ratios" ? (
        <RatiosPane />
      ) : sub === "cps" ? (
        <CounterpartiesPane />
      ) : (
        <DiagnosticsPane />
      )}
    </div>
  );
}
export function RulesPane() {
  const [state, dispatch] = useStore();
  const page = usePage();
  const [preview, setPreview] = useState<RulePreview | null>(null);
  const [busy, setBusy] = useState(false);
  const sorted = [...state.data.rules].sort(
    (a, b) => (a.priority ?? 0) - (b.priority ?? 0),
  );
  const move = (r: Rule, d: number) => {
    const i = sorted.indexOf(r);
    const j = i + d;
    if (j < 0 || j >= sorted.length) return;
    const o = [...sorted];
    [o[i], o[j]] = [o[j]!, o[i]!];
    dispatch({
      type: "DATA",
      fn: (data) => ({
        ...data,
        rules: o.map((x, k) => ({ ...x, priority: (k + 1) * 10 })),
      }),
    });
    announce(`${ruleText(r)} moved ${d < 0 ? "up" : "down"}`);
  };
  const dry = async () => {
    setBusy(true);
    await sleep(700);
    setBusy(false);
    const used = new Set();
    let skippedStaged = 0;
    const out = sorted.map((rule) => {
      const c = ruleCandidates(rule, state);
      skippedStaged += c.skippedStaged;
      const rows = c.rows.filter((r) => !used.has(r.id));
      rows.forEach((r) => used.add(r.id));
      return { rule, rows };
    });
    setPreview({ out, skippedStaged });
  };
  const total = preview
    ? preview.out.reduce((s, p) => s + p.rows.length, 0)
    : 0;
  return (
    <div className="section-body">
      <div className="panel">
        <div className="panel-head">
          <h3>Rules</h3>
          <span className="sub">
            They run in order on unclassified active movements; the first that
            matches decides
          </span>
          <span className="f1"></span>
          <Button
            size="sm"
            variant="outline"
            icon="plus"
            onClick={() => page.openDialog("rule", { rows: [] })}
          >
            Make a rule…
          </Button>
          <Button size="sm" variant="outline" pending={busy} onClick={dry}>
            Preview what they would classify
          </Button>
        </div>
        <DataTable
          label="Rules"
          rowKey={(r) => r.id}
          rows={sorted}
          columns={[
            {
              key: "order",
              label: "Order",
              num: true,
              width: 64,
              render: (r) => sorted.indexOf(r) + 1,
            },
            {
              key: "match",
              label: "Rule",
              wrap: true,
              render: (r) => (
                <span className="col">
                  <span>{ruleText(r)}</span>
                  {r.pattern ? (
                    <details className="tech">
                      <summary>Advanced</summary>
                      <span className="mono t-xs">{r.pattern}</span>
                    </details>
                  ) : null}
                </span>
              ),
            },
            {
              key: "cls",
              label: "Classifies as",
              render: (r) => CLS[r.cls].label,
            },
            {
              key: "category",
              label: "Category",
              render: (r) =>
                r.category ? (
                  CATEGORY_LABEL[r.category]
                ) : (
                  <span className="muted">None</span>
                ),
            },
            {
              key: "created",
              label: "Added",
              render: (r) => fmtDateLong(r.created),
            },
            {
              key: "x",
              label: "",
              render: (r) => (
                <span className="row g1">
                  <IconButton
                    icon="chevronUp"
                    label={"Move up: " + ruleText(r)}
                    disabled={sorted.indexOf(r) === 0}
                    onClick={() => move(r, -1)}
                  />
                  <IconButton
                    icon="chevronDown"
                    label={"Move down: " + ruleText(r)}
                    disabled={sorted.indexOf(r) === sorted.length - 1}
                    onClick={() => move(r, 1)}
                  />
                </span>
              ),
            },
          ]}
        />
        {preview ? (
          <div
            className="panel-body"
            style={{ borderTop: "var(--hairline) solid var(--border)" }}
          >
            <div className="row g2 wrap">
              <b className="fw6 f1">
                {plural(total, "movement")} would be classified
              </b>
              <Button
                size="sm"
                disabled={!total}
                onClick={() => {
                  const n = stageRulesAction(
                    dispatch,
                    preview.out.filter((p) => p.rows.length),
                  );
                  setPreview(null);
                  page.toast(
                    `Rules staged for ${plural(n, "movement")} · not saved`,
                  );
                }}
              >
                Stage them
              </Button>
            </div>
            {preview.out.map((p) =>
              p.rows.length ? (
                <div key={p.rule.id} className="col g1">
                  <span className="t-sm">
                    {ruleText(p.rule)} → {CLS[p.rule.cls].label}:{" "}
                    {plural(p.rows.length, "movement")}
                  </span>
                  <span className="t-xs muted wrapt">
                    {p.rows
                      .slice(0, 4)
                      .map((r) => r.description)
                      .join(" · ")}
                    {p.rows.length > 4 ? " …" : ""}
                  </span>
                </div>
              ) : null,
            )}
            <p className="t-xs muted">
              Movements you classified are never touched; sealed ones are
              skipped.
              {preview.skippedStaged
                ? ` ${plural(preview.skippedStaged, "movement")} with unsaved changes left out.`
                : ""}{" "}
              The rules are applied when you save, like any other change.
            </p>
          </div>
        ) : null}
      </div>
    </div>
  );
}
export function RatiosPane() {
  const [state, dispatch] = useStore();
  const page = usePage();
  const [year, setYear] = useState(+TODAY.slice(0, 4));
  const [edit, setEdit] = useState<Record<string, string>>({});
  const [offer, setOffer] = useState<{
    c: string;
    value: number;
    rows: Movement[];
  } | null>(null);
  const [validation, setValidation] = useState<"ok" | "bad" | null>(null);
  const ratios = state.data.ratios[year] || {};
  const usingRows = (c: string) =>
    Object.values(state.data.byId).filter(
      (r) =>
        r.cls === "mixed" &&
        r.usageRatio === c &&
        effDate(r).startsWith(String(year)) &&
        r.lifecycle === "active",
    );
  const save = (c: string) => {
    const r = parsePercent(edit[c], { label: "Ratio" });
    if (r.error || r.empty) {
      page.toast(r.error || "Enter a ratio");
      return;
    }
    dispatch({
      type: "DATA",
      fn: (d) => ({
        ...d,
        ratios: {
          ...d.ratios,
          [year]: { ...(d.ratios[year] || {}), [c]: r.value },
        },
      }),
    });
    const n = { ...edit };
    delete n[c];
    setEdit(n);
    const rows = usingRows(c).filter(
      (x) => x.share !== r.value && !x.sealed?.length,
    );
    const value = Number(r.value);
    if (rows.length) setOffer({ c, value, rows });
    else page.toast(`${CATEGORY_LABEL[c]} ${year}: ${pct(value)}`);
  };
  return (
    <div className="section-body">
      <div className="panel">
        <div className="panel-head">
          <h3>Business-use ratios</h3>
          <span className="sub">
            The share of a category used for the activity, per year. Mixed
            movements reference them.
          </span>
          <span className="f1"></span>
          <PeriodControl
            label="Ratio year"
            yearOnly
            value={{ year, code: "0A" }}
            onChange={(p) => {
              setYear(p.year);
              setOffer(null);
            }}
          />
          <Button
            size="sm"
            variant="outline"
            onClick={() =>
              setValidation(
                Object.entries(ratios).every(
                  ([c, v]) => RATIO_ELIGIBLE.includes(c) && v >= 0 && v <= 1,
                )
                  ? "ok"
                  : "bad",
              )
            }
          >
            Check them
          </Button>
        </div>
        {validation ? (
          <div className="panel-body">
            <Alert tone={validation === "ok" ? "success" : "danger"}>
              {validation === "ok"
                ? `Every ${year} ratio is on an eligible category and between 0% and 100%.`
                : "Some ratios are out of bounds."}
            </Alert>
          </div>
        ) : null}
        {offer ? (
          <div className="panel-body">
            <Alert
              icon="scale"
              title={`${plural(offer.rows.length, "Mixed movement")} use this ratio`}
            >
              Their share still says the old value. Stage {pct(offer.value)} on
              each? Saving is separate.
              <div className="row g2" style={{ marginTop: "var(--spacing)" }}>
                <Button
                  size="xs"
                  onClick={() => {
                    dispatch({
                      type: "STAGE",
                      changes: offer.rows.map((r) => ({
                        id: r.id,
                        field: "share",
                        value: offer.value,
                      })),
                      label: "Share from the new ratio",
                    });
                    page.toast(
                      `${plural(offer.rows.length, "share")} staged · not saved`,
                    );
                    setOffer(null);
                  }}
                >
                  Stage the new share
                </Button>
                <Button
                  size="xs"
                  variant="ghost"
                  onClick={() => setOffer(null)}
                >
                  Leave them
                </Button>
              </div>
            </Alert>
          </div>
        ) : null}
        <DataTable
          label={`Ratios ${year}`}
          rowKey={(c) => c}
          rows={RATIO_ELIGIBLE}
          columns={[
            {
              key: "cat",
              label: "Category",
              render: (c) => (
                <span className="col">
                  <span>{CATEGORY_LABEL[c]}</span>
                  <span className="muted t-xs">
                    {FAMILY_LABEL[CATEGORY_FAMILY[c] ?? ""]}
                  </span>
                </span>
              ),
            },
            {
              key: "ratio",
              label: "Ratio",
              render: (c) =>
                edit[c] != null ? (
                  <span className="row g1">
                    <Input
                      size="sm"
                      style={{ width: "calc(var(--spacing) * 20)" }}
                      value={edit[c]}
                      autoFocus
                      aria-label={`Ratio for ${CATEGORY_LABEL[c]}, write 50 for 50%`}
                      onChange={(e) =>
                        setEdit({ ...edit, [c]: e.target.value })
                      }
                      onKeyDown={(e) => {
                        if (e.key === "Enter") save(c);
                        if (e.key === "Escape") {
                          const n = { ...edit };
                          delete n[c];
                          setEdit(n);
                        }
                      }}
                    />
                    <span className="muted">%</span>
                  </span>
                ) : ratios[c] != null ? (
                  <span className="tnum fw5">{pct(ratios[c])}</span>
                ) : (
                  <span className="muted">Not set</span>
                ),
            },
            {
              key: "used",
              label: "Mixed movements using it",
              num: true,
              render: (c) => usingRows(c).length,
            },
            {
              key: "x",
              label: "",
              render: (c) => (
                <span className="row g1">
                  <Button
                    size="xs"
                    variant="ghost"
                    onClick={() =>
                      setEdit({
                        ...edit,
                        [c]:
                          ratios[c] != null ? String(+(ratios[c] * 100)) : "",
                      })
                    }
                  >
                    {ratios[c] != null ? "Change" : "Set"}
                  </Button>
                  {ratios[c] != null ? (
                    <Button
                      size="xs"
                      variant="ghost"
                      onClick={() =>
                        dispatch({
                          type: "DATA",
                          fn: (d) => {
                            const y = { ...(d.ratios[year] || {}) };
                            delete y[c];
                            return { ...d, ratios: { ...d.ratios, [year]: y } };
                          },
                        })
                      }
                    >
                      Unset
                    </Button>
                  ) : null}
                </span>
              ),
            },
          ]}
        />
        <div className="panel-body">
          <p className="t-xs muted">
            Only these categories take a ratio. Others are wholly business or
            wholly personal.
          </p>
        </div>
      </div>
    </div>
  );
}
export function CounterpartiesPane() {
  const [state, dispatch] = useStore();
  const page = usePage();
  const [cur, setCur] = useState<string | null>(null);
  const [form, setForm] = useState<CpForm>(NO_CP_FORM);
  const [withdraw, setWithdraw] = useState<string | null>(null);
  const c = state.data.counterparties.find((x) => x.name === cur);
  return (
    <div className="section-body">
      <div className="panel">
        <div className="panel-head">
          <h3>Counterparties</h3>
          <span className="sub">
            Where a counterparty is established and which State IVA-identifies
            it. This decides intra-community treatment.
          </span>
        </div>
        <DataTable
          label="Counterparties"
          rowKey={(x) => x.name}
          rows={state.data.counterparties}
          onRowClick={(x) => {
            setCur(x.name);
            setWithdraw(null);
            setForm({
              taxId: x.taxId,
              country: x.country,
              idState: x.idState || "",
              scope: x.scope,
              note: x.note,
            });
          }}
          rowLabel={(x) => x.name}
          selectedKey={cur}
          columns={[
            { key: "name", label: "Counterparty", wrap: true },
            {
              key: "taxId",
              label: "Tax id",
              render: (x) => <span className="mono t-sm">{x.taxId}</span>,
            },
            { key: "country", label: "Country" },
            {
              key: "idState",
              label: "VAT-identified in",
              render: (x) =>
                x.idState ? (
                  x.idState.toUpperCase()
                ) : (
                  <span className="muted">Not established</span>
                ),
            },
            {
              key: "confirmed",
              label: "Confirmed",
              render: (x) =>
                x.confirmed ? (
                  fmtDateLong(x.confirmed)
                ) : (
                  <span className="row g1">
                    <Icon name="unknown" size="xs" className="warn-t" />
                    Not yet
                  </span>
                ),
            },
          ]}
        />
        {c ? (
          <div
            className="panel-body"
            style={{ borderTop: "var(--hairline) solid var(--border)" }}
          >
            <div className="row g2">
              <b className="fw6 f1">{c.name}</b>
              <IconButton
                icon="close"
                label="Close"
                onClick={() => setCur(null)}
              />
            </div>
            <Alert icon="info" title="What the ledger would answer now">
              {c.idState
                ? `IVA-identified in ${c.idState.toUpperCase()}, established ${c.scope.toLowerCase()}: purchases are EU acquisitions under reverse charge.`
                : "Not enough is confirmed: intra-community treatment stays undetermined and its movements show a readiness issue."}
            </Alert>
            <div className="formgrid">
              <Field label="Tax id" req>
                <Input
                  className="mono"
                  value={form.taxId}
                  onChange={(e) => setForm({ ...form, taxId: e.target.value })}
                />
              </Field>
              <Field label="Country" req>
                <Input
                  value={form.country}
                  maxLength={2}
                  onChange={(e) =>
                    setForm({ ...form, country: e.target.value.toUpperCase() })
                  }
                />
              </Field>
              <Field
                label="VAT-identification state"
                hint="Two letters, e.g. LU"
              >
                <Input
                  value={form.idState}
                  maxLength={2}
                  onChange={(e) =>
                    setForm({ ...form, idState: e.target.value.toLowerCase() })
                  }
                />
              </Field>
              <Field label="Note">
                <Input
                  value={form.note}
                  onChange={(e) => setForm({ ...form, note: e.target.value })}
                />
              </Field>
            </div>
            <div className="row g2">
              <Button
                size="sm"
                onClick={() => {
                  dispatch({
                    type: "DATA",
                    fn: (d) => ({
                      ...d,
                      counterparties: d.counterparties.map((x) =>
                        x.name === c.name
                          ? {
                              ...x,
                              ...form,
                              idState: form.idState || null,
                              confirmed: TODAY,
                            }
                          : x,
                      ),
                    }),
                  });
                  page.toast("Counterparty confirmed");
                }}
              >
                Confirm
              </Button>
              {c.confirmed ? (
                <Button
                  size="sm"
                  variant="outline"
                  aria-expanded={withdraw != null}
                  onClick={() => setWithdraw("")}
                >
                  Withdraw…
                </Button>
              ) : null}
            </div>
            {withdraw != null ? (
              <div className="card-wash">
                <Field label="Why the earlier answer was wrong" req>
                  <Input
                    data-autofocus
                    value={withdraw}
                    onChange={(e) => setWithdraw(e.target.value)}
                  />
                </Field>
                <div className="row g2">
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => setWithdraw(null)}
                  >
                    Cancel
                  </Button>
                  <Button
                    size="sm"
                    variant="destructive"
                    disabled={!withdraw.trim()}
                    onClick={() => {
                      dispatch({
                        type: "DATA",
                        fn: (d) => ({
                          ...d,
                          counterparties: d.counterparties.map((x) =>
                            x.name === c.name
                              ? {
                                  ...x,
                                  confirmed: null,
                                  idState: null,
                                  scope: "Not confirmed",
                                }
                              : x,
                          ),
                        }),
                      });
                      setWithdraw(null);
                      page.toast(
                        "Withdrawn: the earlier answer is recorded as wrong",
                      );
                    }}
                  >
                    Withdraw the confirmation
                  </Button>
                </div>
              </div>
            ) : null}
          </div>
        ) : null}
      </div>
    </div>
  );
}
export function DiagnosticsPane() {
  const [state] = useStore();
  const rows = Object.values(state.data.byId);
  const llm = rows.filter((r) => r.suggestion).length;
  return (
    <div className="section-body">
      <div className="panel">
        <div className="panel-head">
          <h3>Model diagnostics</h3>
          <span className="sub">
            1 Jan 2026 to {fmtDateLong(TODAY)} · low confidence is below 70%
          </span>
        </div>
        <div className="panel-body">
          <dl className="kv" style={{ maxWidth: "calc(var(--spacing) * 128)" }}>
            <dt>Suggestions made</dt>
            <dd className="tnum">{llm + 41}</dd>
            <dt>Approved by you</dt>
            <dd className="tnum">29</dd>
            <dt>Rejected</dt>
            <dd className="tnum">
              {rows.filter((r) => r.modelRejected).length + 3}
            </dd>
            <dt>Low confidence</dt>
            <dd className="tnum">
              {rows.filter((r) => r.suggestion && r.suggestion.confidence < 0.7)
                .length + 6}
            </dd>
            <dt>Cost</dt>
            <dd>0.00 EUR · all read on this computer</dd>
          </dl>
        </div>
      </div>
    </div>
  );
}

/* ── Setup › Registers. ─────────────────────────────────────────────── */
export function RegistersSection() {
  const [sub, setSub] = useState("accounts");
  return (
    <div className="section">
      <div className="section-bar">
        <div className="scroll-x" style={{ minWidth: 0 }}>
          <Tabs
            size="sm"
            value={sub}
            onChange={setSub}
            label="Registers"
            tabs={[
              { value: "accounts", label: "Own accounts" },
              { value: "prorrata", label: "Prorrata" },
              { value: "capital", label: "Bienes de inversión" },
              { value: "inventory", label: "Inventory" },
              { value: "assets", label: "Activity assets" },
            ]}
          />
        </div>
      </div>
      {sub === "accounts" ? (
        <AccountsPane />
      ) : sub === "prorrata" ? (
        <ProrrataPane />
      ) : sub === "capital" ? (
        <CapitalPane />
      ) : sub === "inventory" ? (
        <InventoryPane />
      ) : (
        <AssetsPane />
      )}
    </div>
  );
}
export function AccountsPane() {
  const [state, dispatch] = useStore();
  const page = usePage();
  const [adding, setAdding] = useState(false);
  const blank = {
    label: "",
    bank: "",
    iban: "",
    currency: "EUR",
    opened: "",
    holding: "titular",
  };
  const [f, setF] = useState(blank);
  const [menu, setMenu] = useState<{ anchor: HTMLElement; a: Account } | null>(
    null,
  );
  const [act, setAct] = useState<AcctAction | null>(null);
  const ibanOk = /^[A-Z]{2}\d{2}[A-Z0-9]{10,30}$/.test(
    f.iban.replace(/\s/g, "").toUpperCase(),
  );
  const opened = parseDateIso(f.opened);
  const used = (id: string) =>
    Object.values(state.data.byId).filter((r) => r.account === id).length;
  const actDate = act ? parseDateIso(act.date || "") : null;
  return (
    <div className="section-body">
      <div className="panel">
        <div className="panel-head">
          <h3>Your own accounts</h3>
          <span className="sub">
            Bank statements bind to these. IBANs are entered through a protected
            field and shown masked afterwards.
          </span>
          <span className="f1"></span>
          <Button size="sm" icon="plus" onClick={() => setAdding(true)}>
            Add account
          </Button>
        </div>
        <DataTable
          label="Own accounts"
          rowKey={(a) => a.id}
          rows={state.data.accounts}
          columns={[
            {
              key: "label",
              label: "Account",
              render: (a) => <span className="fw5">{a.label}</span>,
            },
            { key: "bank", label: "Bank", wrap: true },
            {
              key: "iban",
              label: "IBAN",
              render: (a) => <span className="mono t-sm nowrap">{a.iban}</span>,
            },
            { key: "currency", label: "Currency" },
            {
              key: "opened",
              label: "Opened",
              render: (a) => fmtDateLong(a.opened),
            },
            {
              key: "closed",
              label: "Closed",
              render: (a) =>
                a.closed ? (
                  fmtDateLong(a.closed)
                ) : (
                  <span className="muted">Not closed</span>
                ),
            },
            {
              key: "holding",
              label: "You are",
              render: (a) => (a.holding === "titular" ? "Holder" : "Co-holder"),
            },
            {
              key: "roles",
              label: "Designated for",
              wrap: true,
              render: (a) =>
                a.roles.length ? (
                  a.roles.join(" · ")
                ) : (
                  <span className="muted">None</span>
                ),
            },
            {
              key: "used",
              label: "Movements",
              num: true,
              render: (a) => used(a.id),
            },
            {
              key: "x",
              label: "",
              render: (a) => (
                <IconButton
                  icon="more"
                  label={"Actions for " + a.label}
                  onClick={(e) => setMenu({ anchor: e.currentTarget, a })}
                />
              ),
            },
          ]}
        />
        {act ? (
          <div
            className="panel-body"
            style={{ borderTop: "var(--hairline) solid var(--border)" }}
          >
            <div className="card-wash">
              <b className="fw6">
                {act.type === "close"
                  ? `Close ${act.a.label}`
                  : `Designate ${act.a.label}`}
              </b>
              {act.type === "close" ? (
                <Field
                  label="Closed on"
                  req
                  hint="Year-month-day. Its movements keep the account."
                  error={act.date && actDate?.error ? actDate.error : null}
                >
                  <Input
                    data-autofocus
                    value={act.date || ""}
                    placeholder="e.g. 2026-10-31"
                    onChange={(e) => setAct({ ...act, date: e.target.value })}
                  />
                </Field>
              ) : (
                <div className="formgrid">
                  <Field label="For" req>
                    <Select
                      value={act.role || ""}
                      onChange={(e) => setAct({ ...act, role: e.target.value })}
                    >
                      <option value="" disabled>
                        Choose…
                      </option>
                      <option value="Charge">Charges (you pay)</option>
                      <option value="Refund">Refunds (you receive)</option>
                    </Select>
                  </Field>
                  <Field label="Modelo" req>
                    <Select
                      value={act.modelo || ""}
                      onChange={(e) =>
                        setAct({ ...act, modelo: e.target.value })
                      }
                    >
                      <option value="" disabled>
                        Choose…
                      </option>
                      {[
                        "all modelos",
                        "Modelo 303",
                        "Modelo 130",
                        "Modelo 100",
                      ].map((m) => (
                        <option key={m} value={m}>
                          {m}
                        </option>
                      ))}
                    </Select>
                  </Field>
                </div>
              )}
              <div className="row g2">
                <Button size="sm" variant="ghost" onClick={() => setAct(null)}>
                  Cancel
                </Button>
                <Button
                  size="sm"
                  disabled={
                    act.type === "close"
                      ? !(actDate && actDate.value)
                      : !(act.role && act.modelo)
                  }
                  onClick={() => {
                    if (act.type === "close") {
                      dispatch({
                        type: "DATA",
                        fn: (d) => ({
                          ...d,
                          accounts: d.accounts.map((x) =>
                            x.id === act.a.id
                              ? { ...x, closed: String(actDate?.value ?? "") }
                              : x,
                          ),
                        }),
                      });
                      page.toast(
                        `${act.a.label} closed on ${fmtDateLong(String(actDate?.value ?? ""))}`,
                      );
                    } else {
                      dispatch({
                        type: "DATA",
                        fn: (d) => ({
                          ...d,
                          accounts: d.accounts.map((x) =>
                            x.id === act.a.id
                              ? {
                                  ...x,
                                  roles: [
                                    ...new Set([
                                      ...x.roles,
                                      `${act.role} · ${act.modelo}`,
                                    ]),
                                  ],
                                }
                              : x,
                          ),
                        }),
                      });
                      page.toast(
                        `Designated for ${(act.role ?? "").toLowerCase()}s · ${act.modelo}`,
                      );
                    }
                    setAct(null);
                  }}
                >
                  {act.type === "close" ? "Close the account" : "Designate"}
                </Button>
              </div>
            </div>
          </div>
        ) : null}
        {adding ? (
          <div
            className="panel-body"
            style={{ borderTop: "var(--hairline) solid var(--border)" }}
          >
            <div className="formgrid">
              <Field label="Name" req>
                <Input
                  value={f.label}
                  onChange={(e) => setF({ ...f, label: e.target.value })}
                  placeholder="e.g. CaixaBank nómina"
                />
              </Field>
              <Field label="Bank">
                <Input
                  value={f.bank}
                  onChange={(e) => setF({ ...f, bank: e.target.value })}
                />
              </Field>
              <Field
                label="IBAN"
                req
                hint="Sent through the protected channel, checked with its control digits, stored encrypted and shown masked afterwards."
                error={f.iban && !ibanOk ? "Not an IBAN shape." : null}
              >
                <Input
                  type="password"
                  autoComplete="off"
                  className="mono"
                  value={f.iban}
                  onChange={(e) => setF({ ...f, iban: e.target.value })}
                />
              </Field>
              <Field label="Currency" req>
                <Input
                  value={f.currency}
                  maxLength={3}
                  onChange={(e) =>
                    setF({ ...f, currency: e.target.value.toUpperCase() })
                  }
                />
              </Field>
              <Field
                label="Opened on"
                req
                hint="Year-month-day"
                error={f.opened && opened.error ? opened.error : null}
              >
                <Input
                  value={f.opened}
                  placeholder="e.g. 2019-03-01"
                  onChange={(e) => setF({ ...f, opened: e.target.value })}
                />
              </Field>
              <Field label="You are">
                <Select
                  value={f.holding}
                  onChange={(e) => setF({ ...f, holding: e.target.value })}
                >
                  <option value="titular">The holder</option>
                  <option value="cotitular">A co-holder</option>
                </Select>
              </Field>
            </div>
            <div className="row g2">
              <Button
                size="sm"
                variant="ghost"
                onClick={() => setAdding(false)}
              >
                Cancel
              </Button>
              <Button
                size="sm"
                disabled={!f.label.trim() || !ibanOk || !opened.value}
                onClick={() => {
                  const id =
                    "acc-" +
                    String(state.data.accounts.length + 1).padStart(2, "0");
                  const ib = f.iban.replace(/\s/g, "").toUpperCase();
                  const acct: Account = {
                    id,
                    label: f.label.trim(),
                    bank: f.bank,
                    iban: `${ib.slice(0, 4)} •••• •••• •••• ${ib.slice(-4)}`,
                    currency: f.currency,
                    opened: String(opened.value),
                    closed: null,
                    holding: f.holding,
                    roles: [],
                  };
                  dispatch({
                    type: "DATA",
                    fn: (d) => ({ ...d, accounts: [...d.accounts, acct] }),
                  });
                  setAdding(false);
                  setF(blank);
                  page.toast(`${acct.label} added; the IBAN field was cleared`);
                }}
              >
                Add account
              </Button>
            </div>
          </div>
        ) : null}
        {menu ? (
          <Menu
            anchor={menu.anchor}
            label="Account actions"
            onClose={() => setMenu(null)}
            items={[
              {
                label: "Update details…",
                icon: "edit",
                onSelect: () =>
                  page.toast(
                    "Details editor: name, bank and a new IBAN through the protected field (simulated)",
                  ),
              },
              {
                label: "Designate for charges or refunds…",
                icon: "tick",
                onSelect: () => setAct({ type: "designate", a: menu.a }),
              },
              {
                label: "Remove a designation",
                icon: "minus",
                disabled: !menu.a.roles.length,
                reason: "It has no designation.",
                onSelect: () =>
                  dispatch({
                    type: "DATA",
                    fn: (d) => ({
                      ...d,
                      accounts: d.accounts.map((x) =>
                        x.id === menu.a.id
                          ? { ...x, roles: x.roles.slice(1) }
                          : x,
                      ),
                    }),
                  }),
              },
              {
                label: "Close on a date…",
                icon: "clock",
                disabled: !!menu.a.closed,
                reason: "Already closed.",
                onSelect: () => setAct({ type: "close", a: menu.a, date: "" }),
              },
              { sep: true },
              {
                label: "Remove…",
                icon: "trash",
                disabled: used(menu.a.id) > 0 || menu.a.roles.length > 0,
                reason: used(menu.a.id)
                  ? `${plural(used(menu.a.id), "movement")} use it. Close it instead.`
                  : "A designation uses it.",
                onSelect: () =>
                  dispatch({
                    type: "DATA",
                    fn: (d) => ({
                      ...d,
                      accounts: d.accounts.filter((x) => x.id !== menu.a.id),
                    }),
                  }),
              },
            ]}
          />
        ) : null}
      </div>
    </div>
  );
}
type FieldSpec = {
  k: string;
  l: string;
  req?: boolean;
  h?: string;
  d?: string;
  opts?: [string, string][];
};
export function MiniForm({
  title,
  fields,
  onSubmit,
  submit,
  note,
}: {
  title: string;
  fields: FieldSpec[];
  onSubmit: (values: Record<string, string>) => void;
  submit: string;
  note?: string;
}) {
  const [v, setV] = useState<Record<string, string>>(() =>
    Object.fromEntries(fields.map((f) => [f.k, f.d || ""])),
  );
  return (
    <div className="card-wash">
      <b className="fw6">{title}</b>
      {note ? <p className="t-xs muted">{note}</p> : null}
      <div className="formgrid">
        {fields.map((f) => (
          <Field key={f.k} label={f.l} req={f.req} hint={f.h}>
            {f.opts ? (
              <Select
                size="sm"
                value={v[f.k]}
                onChange={(e) => setV({ ...v, [f.k]: e.target.value })}
              >
                {f.opts.map(([o, l]) => (
                  <option key={o} value={o}>
                    {l}
                  </option>
                ))}
              </Select>
            ) : (
              <Input
                size="sm"
                value={v[f.k]}
                onChange={(e) => setV({ ...v, [f.k]: e.target.value })}
              />
            )}
          </Field>
        ))}
      </div>
      <div>
        <Button
          size="sm"
          variant="outline"
          disabled={fields.some((f) => f.req && !String(v[f.k]).trim())}
          onClick={() => onSubmit(v)}
        >
          {submit}
        </Button>
      </div>
    </div>
  );
}
export function ProrrataPane() {
  const [state, dispatch] = useStore();
  const page = usePage();
  const [action, setAction] = useState<string | null>(null);
  const [year, setYear] = useState(+TODAY.slice(0, 4));
  const acts = [
    ["seed", "Seed from the prior year"],
    ["declare", "Declare a sector"],
    ["general", "Elect general"],
    ["especial", "Elect especial"],
    ["revoke", "Revoke especial"],
    ["seedSector", "Seed a sector"],
    ["settleSector", "Settle a sector"],
  ];
  const done = (msg: string) => {
    page.toast(msg);
    setAction(null);
  };
  const ensure = (d: DataState) =>
    d.prorrata.some((p) => p.year === year)
      ? d.prorrata
      : [
          ...d.prorrata,
          {
            year,
            regime: "General",
            provisional: "Not set",
            source: "Declared here",
            definitive: "Not settled",
            sectors: [],
          },
        ].sort((a, b) => b.year - a.year);
  return (
    <div className="section-body">
      <div className="panel">
        <div className="panel-head">
          <h3>Prorrata register</h3>
          <span className="sub">
            Your IVA deduction percentage when part of the activity is exempt
          </span>
          <span className="f1"></span>
          <span className="t-sm muted">Ejercicio</span>
          <PeriodControl
            label="Ejercicio"
            yearOnly
            value={{ year, code: "0A" }}
            onChange={(p) => setYear(p.year)}
          />
        </div>
        <DataTable
          label="Prorrata"
          rowKey={(p) => String(p.year)}
          rows={state.data.prorrata}
          selectedKey={String(year)}
          columns={[
            { key: "year", label: "Ejercicio", num: true },
            { key: "regime", label: "Regime" },
            { key: "provisional", label: "Provisional", num: true },
            { key: "source", label: "Source", wrap: true },
            { key: "definitive", label: "Definitive" },
            {
              key: "sectors",
              label: "Sectors",
              render: (p) =>
                p.sectors.length ? (
                  p.sectors.join(", ")
                ) : (
                  <span className="muted">None declared</span>
                ),
            },
          ]}
        />
        <div className="panel-body">
          <div className="row g1 wrap">
            {acts.map(([k, l]) => (
              <Button
                key={k}
                size="sm"
                variant={action === k ? "secondary" : "outline"}
                aria-pressed={action === k}
                onClick={() => setAction(action === k ? null : (k ?? null))}
              >
                {l}
              </Button>
            ))}
          </div>
          {action === "seed" ? (
            <MiniForm
              key={"s" + year}
              title={`Seed ${year} from ${year - 1}`}
              note={`Reads the definitive percentage of the stamped ${year - 1} Modelo 390 (LIVA art. 105.Uno).`}
              fields={[]}
              submit="Seed"
              onSubmit={() =>
                done(
                  state.data.prorrata.find(
                    (p) =>
                      p.year === year - 1 && p.definitive !== "Not settled",
                  )
                    ? `${year} seeded from the ${year - 1} definitive`
                    : `Refused: the ${year - 1} Modelo 390 has no definitive percentage to seed from.`,
                )
              }
            />
          ) : action === "declare" ? (
            <MiniForm
              key={"d" + year}
              title={`Declare a differentiated sector for ${year}`}
              note="Your art. 9.1.c partition; never inferred from your records."
              fields={[
                { k: "id", l: "Sector id", req: true },
                {
                  k: "letter",
                  l: "Activity group",
                  opts: [
                    ["a", "a · Different CNAE group"],
                    ["b", "b · Different deduction %"],
                  ],
                },
              ]}
              submit="Declare sector"
              onSubmit={(v) => {
                dispatch({
                  type: "DATA",
                  fn: (d) => ({
                    ...d,
                    prorrata: ensure(d).map((p) =>
                      p.year === year
                        ? { ...p, sectors: [...p.sectors, v.id ?? ""] }
                        : p,
                    ),
                  }),
                });
                done(`Sector ${v.id} declared for ${year}`);
              }}
            />
          ) : action === "general" || action === "especial" ? (
            <MiniForm
              key={action + year}
              title={`${action === "general" ? "Elect prorrata general" : "Elect prorrata especial"} for ${year}`}
              note={
                action === "general"
                  ? "One deduction percentage applies to every deducible cuota (LIVA art. 104)."
                  : "Each input routes by its classification: exclusively deductible, not, or common (LIVA art. 103.Dos.1)."
              }
              fields={[]}
              submit="Elect"
              onSubmit={() => {
                dispatch({
                  type: "DATA",
                  fn: (d) => ({
                    ...d,
                    prorrata: ensure(d).map((p) =>
                      p.year === year
                        ? {
                            ...p,
                            regime:
                              action === "general" ? "General" : "Especial",
                          }
                        : p,
                    ),
                  }),
                });
                done(`Prorrata ${action} elected for ${year}`);
              }}
            />
          ) : action === "revoke" ? (
            <MiniForm
              key={"r" + year}
              title={`Revoke prorrata especial for ${year}`}
              fields={[]}
              submit="Revoke"
              onSubmit={() =>
                done(
                  `Refused: ${year - 1} was not in prorrata especial, so there is nothing to revoke.`,
                )
              }
            />
          ) : action === "seedSector" ? (
            <MiniForm
              key={"ss" + year}
              title={`Seed a sector's provisional prorrata for ${year}`}
              fields={[{ k: "s", l: "Sector id", req: true }]}
              submit="Seed sector"
              onSubmit={(v) =>
                done(
                  `Refused: sector ${v.s} has no ${year - 1} definitive in the register.`,
                )
              }
            />
          ) : action === "settleSector" ? (
            <MiniForm
              key={"st" + year}
              title={`Settle a sector's definitive prorrata for ${year}`}
              fields={[
                { k: "s", l: "Sector id", req: true },
                {
                  k: "vol",
                  l: "Volume with right to deduct",
                  h: "e.g. 48200.00",
                  req: true,
                },
                { k: "tot", l: "Total volume", req: true },
              ]}
              submit="Settle"
              onSubmit={(v) => {
                const a = parseAmount(v.vol),
                  b = parseAmount(v.tot);
                if (a.error || b.error)
                  return page.toast(a.error || b.error || "");
                done(
                  `Sector ${v.s} definitive for ${year}: ${Math.ceil((Number(a.value) / Number(b.value)) * 100)}% (rounded up, art. 104.Dos)`,
                );
              }}
            />
          ) : null}
        </div>
      </div>
    </div>
  );
}
export function CapitalPane() {
  const [state, dispatch] = useStore();
  const page = usePage();
  return (
    <div className="section-body">
      <div className="panel">
        <div className="panel-head">
          <h3>Bienes de inversión</h3>
          <span className="sub">
            Capital goods tracked for IVA regularización over their period
          </span>
        </div>
        <DataTable
          label="Capital goods"
          rowKey={(c) => c.id}
          rows={state.data.capital}
          columns={[
            { key: "description", label: "Good", wrap: true },
            { key: "kind", label: "Kind" },
            { key: "acquired", label: "Acquired", num: true },
            { key: "ledgerRow", label: "Ledger movement", wrap: true },
            {
              key: "cuota",
              label: "Cuota soportada",
              num: true,
              render: (c) => fmtMoney(c.cuota),
            },
            { key: "prorrata", label: "Initial prorrata", num: true },
            { key: "regularization", label: "Regularización" },
            {
              key: "disposal",
              label: "Disposal",
              render: (c) =>
                c.disposal || <span className="muted">Not disposed</span>,
            },
          ]}
        />
        <div className="panel-body">
          <MiniForm
            title="Declare a capital good"
            note="Over 3,005.06 EUR and used for more than a year."
            fields={[
              { k: "id", l: "Your reference", req: true },
              { k: "desc", l: "Description", req: true },
              {
                k: "kind",
                l: "Kind",
                opts: [
                  ["Mobiliario", "Furniture"],
                  ["Equipos", "Equipment"],
                  ["Inmueble", "Real estate"],
                  ["Vehículo", "Vehicle"],
                ],
              },
              { k: "y", l: "Acquisition year", req: true, h: "Four digits" },
              { k: "cuota", l: "Cuota soportada", h: "e.g. 714.00", req: true },
              {
                k: "pr",
                l: "Initial prorrata",
                h: "Write 92 for 92%",
                req: true,
              },
            ]}
            submit="Declare"
            onSubmit={(v) => {
              const c = parseAmount(v.cuota);
              if (c.error) return page.toast(c.error);
              const y = v.y ?? "";
              if (!/^\d{4}$/.test(y) || !yearOk(+y))
                return page.toast(
                  `“${y}” is not a year from ${YEAR_MIN} to ${YEAR_MAX}.`,
                );
              const p = parsePercent(v.pr, { label: "Prorrata" });
              if (p.error) return page.toast(p.error);
              dispatch({
                type: "DATA",
                fn: (d) => ({
                  ...d,
                  capital: [
                    ...d.capital,
                    {
                      id: v.id ?? "",
                      description: v.desc ?? "",
                      kind: v.kind || "Mobiliario",
                      acquired: +y,
                      ledgerRow: "Not linked",
                      cuota: Number(c.value),
                      prorrata: pct(Number(p.value)),
                      regularization: `${y}–${+y + 4} (5 years)`,
                      disposal: null,
                    },
                  ],
                }),
              });
              page.toast(`Capital good ${v.id} declared`);
            }}
          />
        </div>
      </div>
    </div>
  );
}
export function InventoryPane() {
  const [state, dispatch] = useStore();
  const page = usePage();
  const [year, setYear] = useState(state.data.inventory.year);
  const inv = state.data.inventory;
  const has = inv.year === year;
  const [val, setVal] = useState<{
    qty: number;
    value: number;
    cogs: number;
  } | null>(null);
  const [chooser, setChooser] = useState<HTMLElement | null>(null);
  const valuation = () => {
    const lots: { q: number; u: number }[] = [];
    let cogs = 0;
    inv.movements
      .map((m) => ({ ...m }))
      .forEach((m) => {
        if (m.kind === "opening" || m.kind === "purchase")
          lots.push({ q: m.qty, u: m.unit ?? 0 });
        else if (m.kind === "cogs") {
          let need = m.qty;
          while (need > 0 && lots.length) {
            const l = lots[0]!;
            const t = Math.min(need, l.q);
            cogs += t * l.u;
            l.q -= t;
            need -= t;
            if (!l.q) lots.shift();
          }
        }
      });
    return {
      qty: lots.reduce((s, l) => s + l.q, 0),
      value: lots.reduce((s, l) => s + l.q * l.u, 0),
      cogs,
    };
  };
  return (
    <div className="section-body">
      <div className="panel">
        <div className="panel-head">
          <h3>Inventory book</h3>
          <span className="sub">
            {has ? `${inv.activity} · ${inv.method}` : "One book per year"}
          </span>
          <span className="f1"></span>
          <PeriodControl
            label="Inventory year"
            yearOnly
            value={{ year, code: "0A" }}
            onChange={(p) => {
              setYear(p.year);
              setVal(null);
            }}
          />
          {has ? (
            <>
              <Button
                size="sm"
                variant="outline"
                onClick={() => setVal(valuation())}
              >
                Preview valuation
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={(e) => setChooser(e.currentTarget)}
              >
                Record the closing count…
              </Button>
            </>
          ) : null}
        </div>
        {has ? (
          <>
            <DataTable
              label={`Inventory movements ${year}`}
              rowKey={(m) => m.id}
              rows={inv.movements}
              columns={[
                {
                  key: "date",
                  label: "Date",
                  render: (m) => fmtDateLong(m.date),
                },
                {
                  key: "kind",
                  label: "Kind",
                  render: (m) =>
                    ({
                      opening: "Opening stock",
                      purchase: "Purchase",
                      cogs: "Cost of sales",
                      count: "Count",
                    })[m.kind],
                },
                { key: "qty", label: "Units", num: true },
                {
                  key: "unit",
                  label: "Unit cost",
                  num: true,
                  render: (m) =>
                    m.unit != null ? (
                      fmtMoney(m.unit)
                    ) : (
                      <span className="muted">by {inv.method}</span>
                    ),
                },
                {
                  key: "base",
                  label: "Taxable base",
                  num: true,
                  render: (m) => (m.base != null ? fmtMoney(m.base) : ""),
                },
                { key: "note", label: "Note", wrap: true },
              ]}
            />
            {val ? (
              <div className="panel-body">
                <Alert
                  title={`Closing stock: ${val.qty} units, ${fmtMoney(val.value)} EUR`}
                >
                  Cost of sales so far {fmtMoney(val.cogs)} EUR by {inv.method}.
                  A preview: nothing is recorded.
                </Alert>
              </div>
            ) : null}
            <div className="panel-body">
              <MiniForm
                title="Add a movement"
                fields={[
                  { k: "date", l: "Date", req: true, h: "Year-month-day" },
                  {
                    k: "kind",
                    l: "Kind",
                    opts: [
                      ["purchase", "Purchase"],
                      ["cogs", "Cost of sales"],
                      ["count", "Count"],
                      ["opening", "Opening stock"],
                    ],
                  },
                  { k: "qty", l: "Units", req: true },
                  { k: "unit", l: "Unit cost", h: "e.g. 4.10" },
                ]}
                submit="Add movement"
                onSubmit={(v) => {
                  const d = parseDateIso(v.date);
                  if (d.error) return page.toast(d.error);
                  const qty = v.qty ?? "";
                  if (!/^\d+$/.test(qty))
                    return page.toast("Units are a whole number.");
                  const u: Parsed = v.unit
                    ? parseAmount(v.unit)
                    : { value: null };
                  if (u.error) return page.toast(u.error);
                  dispatch({
                    type: "DATA",
                    fn: (data) => ({
                      ...data,
                      inventory: {
                        ...data.inventory,
                        movements: [
                          ...data.inventory.movements,
                          {
                            id: "m-" + hashHex((v.date ?? "") + qty, 4),
                            date: String(d.value),
                            kind: v.kind || "purchase",
                            qty: +qty,
                            unit: typeof u.value === "number" ? u.value : null,
                            base:
                              typeof u.value === "number"
                                ? u.value * +qty
                                : null,
                            note: "",
                          },
                        ],
                      },
                    }),
                  });
                  page.toast("Inventory movement added");
                }}
              />
            </div>
          </>
        ) : (
          <div className="panel-body">
            <Empty
              icon="archive"
              title={`No inventory book for ${year}`}
              desc="An inventory book is kept only for years with stock. Nothing here does not mean nothing was held."
            />
          </div>
        )}
        {chooser ? (
          <HostFileDialog
            anchor={chooser}
            kind="book"
            onClose={() => setChooser(null)}
            onPick={(f) => {
              setChooser(null);
              page.toast(`Refused: ${f[0]} is not a closing-count record.`);
            }}
          />
        ) : null}
      </div>
    </div>
  );
}
export function AssetsPane() {
  const [state] = useStore();
  const page = usePage();
  const [cur, setCur] = useState("aa-01");
  const [out, setOut] = useState<{ t: string; b: string } | null>(null);
  const a = state.data.assets.find((x) => x.id === cur);
  return (
    <div className="section-body">
      <div className="panel">
        <div className="panel-head">
          <h3>Activity assets</h3>
          <span className="sub">
            Depreciable assets of the activity (amortización), each a chain of
            revisions that are never edited
          </span>
          <span className="f1"></span>
          <Button
            size="sm"
            variant="outline"
            icon="plus"
            onClick={() =>
              page.toast(
                "Create from a first revision: opens the revision editor (simulated)",
              )
            }
          >
            Create…
          </Button>
        </div>
        <DataTable
          label="Activity assets"
          rowKey={(x) => x.id}
          rows={state.data.assets}
          onRowClick={(x) => {
            setCur(x.id);
            setOut(null);
          }}
          rowLabel={(x) => x.name}
          selectedKey={cur}
          columns={[
            { key: "name", label: "Asset", wrap: true },
            {
              key: "acquired",
              label: "In use from",
              render: (x) => fmtDateLong(x.acquired),
            },
            {
              key: "base",
              label: "Base",
              num: true,
              render: (x) => fmtMoney(x.base),
            },
            { key: "method", label: "Method" },
            { key: "claimed", label: "Claimed" },
            { key: "revisions", label: "Revisions", num: true },
          ]}
        />
        {a ? (
          <div
            className="panel-body"
            style={{ borderTop: "var(--hairline) solid var(--border)" }}
          >
            <div className="row g1 wrap">
              <b className="fw6 f1">{a.name}</b>
              <Button
                size="sm"
                variant="outline"
                onClick={() =>
                  setOut({
                    t: "Revisions",
                    b: `1 · ${fmtDateLong(a.acquired)} · created from the purchase${a.revisions > 1 ? " · 2 · 30 Jun 2026 · corrected useful life" : ""}`,
                  })
                }
              >
                Revisions
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={() =>
                  setOut({
                    t: "Forecast for 2026 4T (not recorded)",
                    b: `Amortización ${fmtMoney(Math.round((a.base * (a.id === "aa-01" ? 0.25 : 0.1)) / 4))} EUR for the quarter.`,
                  })
                }
              >
                Forecast
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={() =>
                  setOut({
                    t: "Claim recorded",
                    b: "Recording the same claim again returns this one; nothing is recorded twice.",
                  })
                }
              >
                Record claim
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={() =>
                  setOut({
                    t: "For your declarations",
                    b: "Modelo 130 2026 3T: cumulative amortización in box 02. Modelo 100 2026: activity expenses, amortizaciones.",
                  })
                }
              >
                For declarations
              </Button>
              <Button
                size="sm"
                variant="ghost"
                onClick={() =>
                  page.toast(
                    "Add a correcting revision: opens the revision editor (simulated)",
                  )
                }
              >
                Correct…
              </Button>
            </div>
            {out ? <Alert title={out.t}>{out.b}</Alert> : null}
          </div>
        ) : null}
      </div>
    </div>
  );
}

/* ── Setup › Health. ────────────────────────────────────────────────── */
export function HealthSection() {
  const [state, dispatch] = useStore();
  const page = usePage();
  const [period, setPeriod] = useState(
    state.view.period.code === "ALL"
      ? { year: +TODAY.slice(0, 4), code: "0A" }
      : state.view.period,
  );
  const rows = Object.values(state.data.byId);
  const range = periodRange(period);
  const inP = range
    ? rows.filter((r) => effDate(r) >= range[0] && effDate(r) <= range[1])
    : rows;
  const byLife: Record<string, number> = {};
  inP.forEach((r) => (byLife[r.lifecycle] = (byLife[r.lifecycle] || 0) + 1));
  const bySt: Record<string, number> = {};
  inP
    .filter((r) => r.lifecycle === "active")
    .forEach((r) => {
      const s = statusOf(r, state.check).key;
      bySt[s] = (bySt[s] || 0) + 1;
    });
  const eur: Record<string, number> = { in: 0, out: 0 };
  let unconverted = 0;
  inP
    .filter(
      (r) =>
        r.lifecycle === "active" &&
        CLASSIFIED.has(r.cls) &&
        r.cls !== "personal",
    )
    .forEach((r) => {
      if (r.direction === "transfer") return;
      const v = r.currency === "EUR" ? r.amount : r.fx?.eur;
      if (v == null) {
        unconverted++;
        return;
      }
      eur[r.direction] = (eur[r.direction] ?? 0) + v;
    });
  const reasons: Record<string, number> = {};
  inP.forEach((r) =>
    checkIssues(r, state.check).forEach(
      (x) => (reasons[x] = (reasons[x] || 0) + 1),
    ),
  );
  const [checked, setChecked] = useState<boolean | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [resetReason, setResetReason] = useState("");
  const [resetPreview, setResetPreview] = useState<{
    rows: number;
    docs: number;
    sealed: number;
  } | null>(null);
  const run = async (k: string, fn: () => void) => {
    setBusy(k);
    await sleep(900);
    setBusy(null);
    fn();
  };
  const sided = oneSidedLinks(state.data).length;
  const showReason = (k: string) => {
    dispatch({
      type: "VIEW",
      patch: {
        period,
        filters: { ...EMPTY_FILTERS, reason: k },
        savedView: "custom",
        missingMark: k,
      },
    });
    page.setSection("movements");
  };
  return (
    <div className="section">
      <div className="section-body">
        <div className="row g2 wrap">
          <h3 className="t-md fw6 f1">Health</h3>
          <PeriodControl
            label="Health period"
            value={period}
            allowAll={false}
            onChange={(p) => {
              setPeriod(p);
              setChecked(null);
            }}
          />
        </div>
        <div className="split2">
          <div className="panel">
            <div className="panel-head">
              <h3>Status · {periodShort(period)}</h3>
            </div>
            <div className="panel-body">
              {inP.length ? (
                <dl className="kv">
                  {Object.entries(byLife).map(([k, n]) => (
                    <Fragment key={k}>
                      <dt>{LIFECYCLE[k as Lifecycle].label}</dt>
                      <dd className="tnum">{n}</dd>
                    </Fragment>
                  ))}
                  {Object.entries(bySt).map(([k, n]) => (
                    <Fragment key={k}>
                      <dt>{STATUS_FILTERS[k]}</dt>
                      <dd className="tnum">{n}</dd>
                    </Fragment>
                  ))}
                  <dt>Business in, EUR</dt>
                  <dd className="tnum">{fmtMoney(eur.in)}</dd>
                  <dt>Business out, EUR</dt>
                  <dd className="tnum">{fmtMoney(eur.out)}</dd>
                  <dt>Left out of EUR totals</dt>
                  <dd>
                    {unconverted ? (
                      <span className="row g1">
                        <Icon name="noRate" size="xs" className="warn-t" />
                        {plural(unconverted, "foreign movement")} without a rate
                      </span>
                    ) : (
                      "None"
                    )}
                  </dd>
                </dl>
              ) : (
                <p className="muted t-sm">
                  No movements in {periodShort(period)}. That is not the same as
                  nothing owed.
                </p>
              )}
            </div>
          </div>
          <div className="panel">
            <div className="panel-head">
              <h3>What's still missing · {periodShort(period)}</h3>
              <span className="f1"></span>
              <Button
                size="sm"
                variant="outline"
                icon="sync"
                pending={busy === "pre"}
                onClick={() =>
                  run("pre", () => {
                    dispatch({ type: "CHECK" });
                    page.toast("Checked again: " + periodShort(period));
                  })
                }
              >
                Check again
              </Button>
            </div>
            <div className="panel-body">
              <p className="t-xs muted">
                As of the last check, {fmtTime(state.check.at)}.
              </p>
              {Object.keys(reasons).length ? (
                <ul className="list-rows">
                  {Object.entries(reasons).map(([k, n]) => (
                    <li key={k}>
                      <Icon name="alert" className="warn-t" />
                      <span className="f1">{REASONS[k]}</span>
                      <span className="tnum fw5">{n}</span>
                      <Button
                        size="xs"
                        variant="ghost"
                        onClick={() => showReason(k)}
                      >
                        Show
                      </Button>
                    </li>
                  ))}
                </ul>
              ) : inP.length ? (
                <Alert tone="success">Ready for calculation.</Alert>
              ) : null}
            </div>
          </div>
        </div>
        <div className="panel">
          <div className="panel-head">
            <h3>Check the whole ledger</h3>
            <span className="sub">
              Anomalies in every year it spans, and links the invoice and
              movement sides disagree about
            </span>
            <span className="f1"></span>
            <Button
              size="sm"
              variant="outline"
              pending={busy === "check"}
              onClick={() => run("check", () => setChecked(true))}
            >
              Run the check
            </Button>
          </div>
          <div className="panel-body">
            {checked ? (
              <ul className="list-rows">
                {[...new Set(rows.map((r) => +effDate(r).slice(0, 4)))]
                  .sort((a, b) => b - a)
                  .map((y) => {
                    const n = rows.filter(
                      (r) =>
                        effDate(r).startsWith(String(y)) && issuesOf(r).length,
                    ).length;
                    return (
                      <li key={y}>
                        <span className="f1 tnum">{y}</span>
                        <span>
                          {n
                            ? plural(n, "movement") + " with issues"
                            : "No issues"}
                        </span>
                        {n ? (
                          <Button
                            size="xs"
                            variant="ghost"
                            onClick={() => setPeriod({ year: y, code: "0A" })}
                          >
                            Look at {y}
                          </Button>
                        ) : null}
                      </li>
                    );
                  })}
                <li>
                  <span className="f1">One-sided invoice links</span>
                  <span className="tnum">{sided}</span>
                  {sided ? (
                    <Button
                      size="xs"
                      variant="ghost"
                      onClick={() => page.setSection("invoices")}
                    >
                      Invoices
                    </Button>
                  ) : null}
                </li>
              </ul>
            ) : (
              <p className="muted t-sm">
                Not run in this window yet: nothing is shown as zero until it is
                measured.
              </p>
            )}
          </div>
        </div>
        <div className="split2">
          <div className="panel">
            <div className="panel-head">
              <h3>Declarations to recalculate</h3>
            </div>
            <div className="panel-body">
              <ul className="list-rows">
                <li>
                  <Icon name="clock" className="warn-t" />
                  <span className="f1">
                    Modelo 303 · 2026 3T, draft: 6 movements changed since it
                    was calculated on 14 Oct
                  </span>
                  <Button
                    size="xs"
                    variant="link"
                    onClick={() =>
                      page.toast(
                        "Opens Modelo 303 · 2026 3T in Declarations (another page of the window)",
                      )
                    }
                  >
                    Open in Declarations ›
                  </Button>
                </li>
                <li>
                  <Icon name="lock" />
                  <span className="f1">
                    Modelo 303 · 2026 1T, filed · receipt confirmed: unchanged
                  </span>
                </li>
              </ul>
            </div>
          </div>
          <div className="panel">
            <div className="panel-head">
              <h3>Declaration links</h3>
              <span className="sub">
                Which declarations use which movements
              </span>
            </div>
            <div className="panel-body">
              <p className="t-sm muted">
                Rebuild them if a movement's “Used in” looks wrong. It reads
                every declaration; nothing else changes.
              </p>
              <div>
                <Button
                  size="sm"
                  variant="outline"
                  pending={busy === "part"}
                  onClick={() =>
                    run("part", () =>
                      page.toast("Declaration links rebuilt: 412 references"),
                    )
                  }
                >
                  Rebuild the links
                </Button>
              </div>
            </div>
          </div>
        </div>
        <section className="panel danger" aria-labelledby="h-danger">
          <div className="panel-head">
            <h3 id="h-danger">Danger zone · reset the ledger</h3>
            <span className="sub">
              Deletes every movement, rule and register entry of this profile. A
              dry run comes first.
            </span>
          </div>
          <div className="panel-body">
            <Field
              label="Reason"
              req
              hint="Kept in the audit trail. Up to 500 characters."
            >
              <Input
                value={resetReason}
                maxLength={500}
                onChange={(e) => setResetReason(e.target.value)}
              />
            </Field>
            <div>
              <Button
                size="sm"
                variant="outline"
                disabled={!resetReason.trim()}
                pending={busy === "reset"}
                onClick={() =>
                  run("reset", () =>
                    setResetPreview({
                      rows: rows.length,
                      docs: state.data.docs.length,
                      sealed: rows.filter((r) => r.sealed?.length).length,
                    }),
                  )
                }
              >
                Run the dry run
              </Button>
            </div>
            {resetPreview ? (
              <Alert tone="danger" icon="lock" title="Reset is blocked">
                It would remove {resetPreview.rows} movements and{" "}
                {resetPreview.docs} documents, but {resetPreview.sealed}{" "}
                movements are used by filed or verified declarations. A ledger
                with sealed movements cannot be reset.
              </Alert>
            ) : null}
          </div>
        </section>
      </div>
    </div>
  );
}
