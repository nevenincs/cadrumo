import e130en from "@/dev/fixtures/modelo/modelo-130-1T-en.json";
import e130es from "@/dev/fixtures/modelo/modelo-130-1T-es.json";
import e303en from "@/dev/fixtures/modelo/modelo-303-1T-en.json";
import e303es from "@/dev/fixtures/modelo/modelo-303-1T-es.json";
import e347en from "@/dev/fixtures/modelo/modelo-347-0A-en.json";
import e347es from "@/dev/fixtures/modelo/modelo-347-0A-es.json";
import e390en from "@/dev/fixtures/modelo/modelo-390-0A-en.json";
import e390es from "@/dev/fixtures/modelo/modelo-390-0A-es.json";
import { ISSUES_130 } from "./scenarios";
import type {
  FormEnvelope,
  FormField,
  ModeloForm,
  Origin,
  ResultDirection,
} from "./types";

// Envelopes of the registered read `modelo.work.form`, produced by the
// application's own builder and public projection over the published
// registry, for a synthetic taxpayer in a throwaway profile: 130 and 347 were
// calculated, the others were read before any calculation. The scenarios
// below change a copy so a story can show what an untouched profile never
// reaches; each says what it changed.

const ENVELOPES: Record<string, Record<"en" | "es", unknown>> = {
  "130": { en: e130en, es: e130es },
  "303": { en: e303en, es: e303es },
  "347": { en: e347en, es: e347es },
  "390": { en: e390en, es: e390es },
};

/** The day every story is read on, so deadlines read the same everywhere. */
export const FIXTURE_TODAY = "2026-10-14";

const ANNUAL_CLOSES: Record<string, string> = {
  "347": "2027-02-28",
  "390": "2027-01-30",
};

const daysFrom = (today: string, day: string) =>
  Math.round(
    (Date.parse(`${day}T12:00:00Z`) - Date.parse(`${today}T12:00:00Z`)) /
      86_400_000,
  );

/** An envelope as the builder produced it, moved to the third quarter of
 * 2026 (or the 2026 year) and read on `FIXTURE_TODAY`: the builder stamps the
 * period it was asked for and the day it ran, which made every story late. */
export function envelope(modelo: string, locale: string): FormEnvelope {
  const byLocale = ENVELOPES[modelo];
  if (!byLocale) throw new Error(`No fixture for modelo ${modelo}`);
  const lang = locale === "es" || locale === "ca" ? "es" : "en";
  const e = structuredClone(byLocale[lang]) as FormEnvelope;
  const f = e.form.form;
  const annual = f.period.code === "0A";
  const closes = annual
    ? (ANNUAL_CLOSES[modelo] ?? "2027-01-30")
    : "2026-10-20";
  f.period = { filing_year: 2026, code: annual ? "0A" : "3T" };
  f.filing_year = 2026;
  for (const page of f.pages)
    for (const s of page.sections)
      for (const b of s.blocks)
        if (b.kind === "context_field" && b.value?.kind === "string") {
          if (b.id.includes("periodo") && /^[1-4]T$/.test(b.value.text))
            b.value = { ...b.value, text: "3T" };
          if (b.id.includes("ejercicio"))
            b.value = { ...b.value, text: "2026" };
        }
  if (f.deadline)
    f.deadline = {
      ...f.deadline,
      closes_on: closes,
      nominal_closes_on: closes,
      days_remaining: daysFrom(FIXTURE_TODAY, closes),
      days_overdue: null,
    };
  return e;
}

/** Every field of a form, in reading order. */
export function fieldsOf(f: ModeloForm): FormField[] {
  const out: FormField[] = [];
  for (const page of f.pages)
    for (const section of page.sections)
      for (const block of section.blocks) {
        if (block.kind === "field") out.push(block.field);
        if (block.kind === "binding_inputs") out.push(...block.fields);
        if (block.kind === "grid")
          for (const row of block.rows)
            for (const cell of row.cells)
              if (cell.field && cell.kind !== "design_constant")
                out.push(cell.field);
      }
  out.push(...f.working_figures, ...f.unplaced.map((u) => u.field));
  return out;
}

function setBox(
  f: ModeloForm,
  id: string,
  value: string | null,
  origin: Origin,
) {
  const field = fieldsOf(f).find(
    (x) => x.address.kind === "casilla" && x.address.casilla_id === id,
  );
  if (!field) return;
  field.value = value === null ? null : { kind: "decimal", text: value };
  field.origin = origin;
}

/** Modelo 130 with income and expenses imported from the ledger, earlier
 * instalments carried into box 05, box 06 entered by the filer and box 18
 * waiting for them. Counts and result are set to agree with those boxes. */
export function filled130(locale: string): FormEnvelope {
  const e = envelope("130", locale);
  const f = e.form.form;
  const boxes: [string, string | null, Origin][] = [
    ["01", "18450.00", "imported"],
    ["02", "6230.40", "imported"],
    ["03", "12219.60", "calculated"],
    ["04", "2443.92", "calculated"],
    ["05", "1120.40", "imported"],
    ["06", "1100.00", "entered"],
    ["07", "1343.92", "calculated"],
    ["12", "1343.92", "calculated"],
    ["13", "0.00", "calculated"],
    ["14", "1343.92", "calculated"],
    ["15", "0.00", "calculated"],
    ["17", "1343.92", "calculated"],
    ["18", null, "needs_input"],
    ["19", "1343.92", "calculated"],
  ];
  for (const [id, value, origin] of boxes) setBox(f, id, value, origin);
  for (const w of f.working_figures) w.origin = "calculated";
  const carried = fieldsOf(f).find((x) => x.box === "05");
  if (carried?.source)
    carried.source.earlier_filings = [
      { modelo: "130", period: { filing_year: 2026, code: "2T" } },
    ];
  f.counts = { ...f.counts, needs_input: 1, entered: 1, blocked: 0 };
  for (const page of f.pages)
    for (const s of page.sections)
      s.counts = {
        ...s.counts,
        blocked: 0,
        needs_input: s.blocks.some(
          (b) => b.kind === "field" && b.field.box === "18",
        )
          ? 1
          : 0,
      };
  f.result = {
    casilla_id: "19",
    box: "19",
    value: "1343.92",
    direction: "to_pay",
    election_may_change: false,
  };
  f.calculation_notes = [];
  return e;
}

/** The same 130 with box 18 entered and the check passed. */
export function checked130(locale: string): FormEnvelope {
  const e = filled130(locale);
  const f = e.form.form;
  setBox(f, "18", "0.00", "entered");
  f.counts.needs_input = 0;
  for (const page of f.pages)
    for (const s of page.sections) s.counts.needs_input = 0;
  f.verification = "complete";
  e.form.verified = true;
  return e;
}

/** The checked 130 after it was exported and recorded as filed: the form
 * closes for editing; the AEAT receipt is still to be added. */
export function recorded130(locale: string): FormEnvelope {
  const e = checked130(locale);
  const f = e.form.form;
  f.filing = { recorded_at: "2026-10-14T18:02:00" };
  f.last_export = {
    exported_at: "2026-10-14T17:55:00",
    calculation_revision_id: f.calculation_revision_id ?? "",
    current: true,
  };
  f.edit_closure = "recorded_as_filed";
  e.admitted_baseline = null;
  e.form.filed = true;
  return e;
}

/** Plain-language names for the modelos the prototype shows. The product
 * reads each from the catalogue key `modelo.schema.{modelo}.field.title`. */
const MODELO_TITLES: Record<"en" | "es", Record<string, string>> = {
  en: {
    "111": "Withholding on wages and professional fees",
    "115": "Withholding on property rentals",
    "130": "Income tax instalment",
    "303": "VAT self-assessment",
    "347": "Annual return of transactions with third parties",
    "349": "Intra-community transactions",
    "390": "Annual VAT summary",
    "100": "Personal income tax return",
  },
  es: {
    "111": "Retenciones de trabajo y actividades profesionales",
    "115": "Retenciones de arrendamientos de inmuebles",
    "130": "Pago fraccionado del IRPF",
    "303": "Autoliquidación del IVA",
    "347": "Declaración anual de operaciones con terceros",
    "349": "Operaciones intracomunitarias",
    "390": "Resumen anual del IVA",
    "100": "Declaración de la renta",
  },
};

export const modeloTitle = (modelo: string, locale: string) =>
  MODELO_TITLES[locale === "es" || locale === "ca" ? "es" : "en"][modelo] ?? "";

type SummaryState =
  | "draft"
  | "calculated"
  | "blocked"
  | "checked"
  | "recorded"
  | "superseded"
  | "discarded"
  | "unreadable";

export type AeatState =
  "not_observed" | "submitted_observed" | "accepted" | "justificante_verified";

/** One line of the declarations list, in the shape of the application's
 * `DeclarationListRow`: its own group and state, the local declaration and
 * the calendar entry, kept apart. */
export type ListRow = {
  key: string;
  modelo: string;
  period: { filing_year: number; code: string } | null;
  state: string;
  group:
    | "attention"
    | "in_progress"
    | "ready"
    | "not_started"
    | "recorded"
    | "aeat_unlinked"
    | "maybe";
  declaration: {
    work_unit_id: string;
    summary: {
      state: SummaryState;
      blocking_count: number | null;
      checked: boolean;
      result: { value: string | null; direction: ResultDirection } | null;
      is_correction: boolean;
    } | null;
  } | null;
  calendar: {
    adjusted_closes_on: string;
    holiday_coverage: string;
    days_overdue: number | null;
    local_filing_state: string | null;
    aeat_submission_state: AeatState | null;
    justificante_verified: boolean | null;
    evidence_conflicted: boolean;
    aeat_needs_check: boolean;
  } | null;
  advice:
    | "applicable_window_missing"
    | "applicability_undetermined"
    | "registry_unmodeled"
    | null;
};

const q = (code: string, year = 2026) => ({ filing_year: year, code });

function cal(
  closes: string,
  aeat: AeatState = "not_observed",
  more: Partial<NonNullable<ListRow["calendar"]>> = {},
): NonNullable<ListRow["calendar"]> {
  return {
    adjusted_closes_on: closes,
    holiday_coverage: "national_only",
    days_overdue: null,
    local_filing_state: "not_ready_to_file",
    aeat_submission_state: aeat,
    justificante_verified: aeat === "justificante_verified",
    evidence_conflicted: false,
    aeat_needs_check: false,
    ...more,
  };
}

function work(
  id: string,
  state: SummaryState,
  blocking: number | null,
  result: [string, ResultDirection] | null,
  checked = false,
): NonNullable<ListRow["declaration"]> {
  return {
    work_unit_id: id,
    summary: {
      state,
      blocking_count: blocking,
      checked,
      result: result ? { value: result[0], direction: result[1] } : null,
      is_correction: false,
    },
  };
}

const recorded = { local_filing_state: null };

export const DECLARATIONS: ListRow[] = [
  {
    key: "w-303-3t",
    modelo: "303",
    period: q("3T"),
    state: "calculated",
    group: "attention",
    declaration: work("w-303-3t", "calculated", 3, ["1234.56", "to_pay"]),
    calendar: cal("2026-10-20"),
    advice: null,
  },
  {
    key: "w-130-3t",
    modelo: "130",
    period: q("3T"),
    state: "blocked",
    group: "attention",
    declaration: work("w-130-3t", "blocked", 1, null),
    calendar: cal("2026-10-20"),
    advice: null,
  },
  {
    key: "c-115-3t",
    modelo: "115",
    period: q("3T"),
    state: "not_started",
    group: "attention",
    declaration: null,
    calendar: cal("2026-10-20"),
    advice: null,
  },
  {
    key: "w-111-3t",
    modelo: "111",
    period: q("3T"),
    state: "checked",
    group: "ready",
    declaration: work("w-111-3t", "checked", 0, ["412.00", "to_pay"], true),
    calendar: cal("2026-10-20"),
    advice: null,
  },
  {
    key: "w-347-0a",
    modelo: "347",
    period: q("0A"),
    state: "draft",
    group: "in_progress",
    declaration: work("w-347-0a", "draft", null, null),
    calendar: cal("2027-02-28"),
    advice: null,
  },
  {
    key: "w-390-0a",
    modelo: "390",
    period: q("0A"),
    state: "draft",
    group: "in_progress",
    declaration: work("w-390-0a", "draft", null, null),
    calendar: cal("2027-01-30"),
    advice: null,
  },
  {
    key: "w-303-2t",
    modelo: "303",
    period: q("2T"),
    state: "recorded",
    group: "recorded",
    declaration: work("w-303-2t", "recorded", 0, ["980.10", "to_pay"], true),
    calendar: cal("2026-07-20", "justificante_verified", recorded),
    advice: null,
  },
  {
    key: "w-130-2t",
    modelo: "130",
    period: q("2T"),
    state: "recorded",
    group: "recorded",
    declaration: work("w-130-2t", "recorded", 0, ["1120.40", "to_pay"], true),
    calendar: cal("2026-07-20", "not_observed", recorded),
    advice: null,
  },
  {
    key: "w-303-1t",
    modelo: "303",
    period: q("1T"),
    state: "recorded",
    group: "recorded",
    declaration: work("w-303-1t", "recorded", 0, ["310.00", "to_refund"], true),
    calendar: cal("2026-04-20", "accepted", {
      ...recorded,
      aeat_needs_check: true,
    }),
    advice: null,
  },
  {
    key: "advice-349",
    modelo: "349",
    period: null,
    state: "maybe",
    group: "maybe",
    declaration: null,
    calendar: null,
    advice: "applicability_undetermined",
  },
];

/** The filled 130 after a check that found things to sort out. */
export function issues130(locale: string): FormEnvelope {
  const e = filled130(locale);
  e.form.form.verification = "incomplete";
  e.form.form.issues = ISSUES_130;
  return e;
}

/** The checked 130 with a file exported, from the current calculation or
 * from an earlier one. */
export function exported130(locale: string, current: boolean): FormEnvelope {
  const e = checked130(locale);
  e.form.form.last_export = {
    exported_at: "2026-10-14T17:55:00",
    calculation_revision_id: current
      ? (e.form.form.calculation_revision_id ?? "")
      : "earlier",
    current,
  };
  return e;
}
