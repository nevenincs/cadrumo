import type { IconName } from "@/components/ui/icon";
import type {
  Editability,
  FormField,
  Origin,
  ResultDirection,
  SourceFamily,
} from "./types";
import { w } from "./words";

// How the workspace says things. Every sentence about a box, a source, a
// period, a result or a next step is the product's own catalogue wording
// (`words.ts`); this module only chooses which, and pairs each with a tone and
// an icon. Colour always reinforces a word, never replaces it.

export type Tone = "attention" | "danger" | "mine" | "source" | "quiet";

export const TONE_TEXT: Record<Tone, string> = {
  attention: "text-warning",
  danger: "text-destructive",
  mine: "text-foreground",
  source: "text-muted-foreground",
  quiet: "text-faint",
};

const ORIGIN_LOOK: Record<Origin, { tone: Tone; icon: IconName }> = {
  needs_input: { tone: "attention", icon: "edit" },
  default_to_confirm: { tone: "attention", icon: "tick" },
  calculation_failed: { tone: "danger", icon: "alert" },
  entered: { tone: "mine", icon: "person" },
  cleared: { tone: "mine", icon: "erase" },
  overrides_source: { tone: "attention", icon: "swap" },
  imported: { tone: "source", icon: "download" },
  not_imported_yet: { tone: "quiet", icon: "clock" },
  calculated: { tone: "source", icon: "sync" },
  not_calculated_yet: { tone: "quiet", icon: "clock" },
  informational: { tone: "quiet", icon: "info" },
  optional_empty: { tone: "quiet", icon: "page" },
  not_applicable: { tone: "quiet", icon: "close" },
};

/** Whether an optional box nobody filled holds a value anyway: the product
 * then says it was left at that value, never that it is empty. */
export const holdsValue = (f: FormField) =>
  !!f.value && f.value.kind !== "null" && f.value.text !== "";

/** The origin of a box in words, naming its source when it has one. */
export function originWords(f: FormField, locale: string) {
  const look = ORIGIN_LOOK[f.origin];
  const family = f.source?.family;
  const filings = f.source?.earlier_filings ?? [];
  let word = w(`tui.modelo.workbench.origin.${f.origin}`, locale);
  if (
    family &&
    (f.origin === "imported" ||
      f.origin === "not_imported_yet" ||
      f.origin === "overrides_source")
  )
    word =
      filings.length === 1 && family === "earlier_filings"
        ? w(
            `tui.modelo.workbench.origin_source.${f.origin}.named_filing`,
            locale,
            {
              modelo: filings[0]!.modelo,
              period: periodWords(
                filings[0]!.period.code,
                filings[0]!.period.filing_year,
                locale,
              ),
            },
          )
        : w(`tui.modelo.workbench.origin_source.${f.origin}.${family}`, locale);
  if (
    f.origin === "imported" &&
    family === "earlier_filings" &&
    filings.length === 0
  )
    word = w(
      "tui.modelo.workbench.origin_source.imported.earlier_filings_none",
      locale,
    );
  if (f.origin === "optional_empty" && holdsValue(f))
    word = w("tui.modelo.workbench.origin_held_zero.optional_empty", locale);
  return {
    word,
    sentence: w(
      `tui.modelo.workbench.legend.meaning.origin.${f.origin}`,
      locale,
    ),
    ...look,
  };
}

export const FAMILY_ICON: Record<SourceFamily, IconName> = {
  records: "sheet",
  registers: "archive",
  profile: "idCard",
  earlier_filings: "page",
  aeat_draft: "office",
  your_entries: "person",
  fixed_by_design: "lock",
};

export const familyWords = (family: SourceFamily, locale: string) =>
  w(`tui.modelo.workbench.origin_source.imported.${family}`, locale);

export const SURFACE_WORD: Record<string, string> = {
  ledger: "Open your records",
  withholding: "Open withholdings",
  profile: "Open your profile",
  declarations: "Open that declaration",
};

const EDITABLE: ReadonlySet<Editability> = new Set([
  "editable_value",
  "editable_override",
  "overridable_source",
]);

/** Whether the value of a box can be typed in here, and the product's own
 * sentence for why or why not. */
export function editing(field: FormField, locale: string) {
  const editable = EDITABLE.has(field.editability);
  const why = field.not_writable_reason
    ? w(
        `tui.modelo.workbench.not_writable.${field.not_writable_reason}`,
        locale,
      )
    : w(`tui.modelo.workbench.editability.${field.editability}`, locale);
  return { editable, why };
}

/** The application's rule for a value the filer may confirm as their own:
 * an assumed value they type into, edited at the box itself. */
export const confirmable = (f: FormField) =>
  f.origin === "default_to_confirm" &&
  holdsValue(f) &&
  (f.editability === "editable_value" ||
    f.editability === "editable_override") &&
  !(f.editability === "editable_override" && f.bindings.length > 0) &&
  f.bindings.every((b) => b.policy.override_policy === "enter");

export const resultWords = (direction: ResultDirection, locale: string) =>
  ({
    to_pay: w("tui.modelo.workbench.header.result.to_pay", locale),
    to_refund: w("tui.modelo.workbench.header.result.to_refund", locale),
    to_carry_forward: w(
      "tui.modelo.workbench.header.result.to_carry_forward",
      locale,
    ),
    to_deduct_later: "To deduct in later periods",
    negative: w("tui.modelo.workbench.header.result.negative", locale),
    nil: w("tui.modelo.workbench.header.result.zero", locale),
    unknown: w("tui.modelo.workbench.header.result.unknown", locale),
  })[direction];

/** A period in words: "3rd quarter 2026", "March 2026", "Annual 2026". */
export function periodWords(
  code: string,
  year: number,
  locale: string,
): string {
  const q = /^([1-4])T$/.exec(code);
  if (q)
    return w(`tui.modelo.workbench.period.quarter_${q[1]}`, locale, { year });
  if (/^(0[1-9]|1[0-2])$/.test(code))
    return w(`tui.modelo.workbench.period.month_${code}`, locale, { year });
  if (code === "0A")
    return w("tui.modelo.workbench.period.annual", locale, { year });
  return `${code} ${year}`;
}

export function money(value: string | number | null, locale: string): string {
  if (value === null || value === "") return "";
  const n = typeof value === "number" ? value : Number(value);
  if (Number.isNaN(n)) return String(value);
  // Spanish leaves four-digit amounts ungrouped; a column of amounts reads
  // only if every one of them is grouped the same way.
  const parts = new Intl.NumberFormat(locale, {
    style: "currency",
    currency: "EUR",
    minimumFractionDigits: 2,
  }).formatToParts(n);
  const group =
    new Intl.NumberFormat(locale)
      .formatToParts(1_000_000)
      .find((p) => p.type === "group")?.value ?? ".";
  return parts
    .map((p) =>
      p.type === "integer" && p.value.length > 3
        ? p.value.replace(/\B(?=(\d{3})+(?!\d))/g, group)
        : p.value,
    )
    .join("");
}

function percent(n: number, locale: string): string {
  return Number.isNaN(n)
    ? ""
    : new Intl.NumberFormat(locale, { maximumFractionDigits: 4 }).format(n) +
        " %";
}

/** A box's value in the reader's language, or "" when it holds none. The
 * product formats values in the application; this stands in for it. */
export function display(field: FormField, locale: string): string {
  const v = field.value;
  if (!v || v.kind === "null" || v.text === "") {
    const rate = field.printed_rate ?? field.grounded_rate;
    return rate ? percent(Number(rate.ratio) * 100, locale) : "";
  }
  if (v.kind === "boolean")
    return w(
      `tui.declarations.value.${v.text === "true" ? "yes" : "no"}`,
      locale,
    );
  if (v.kind === "date") return dateWords(v.text, locale);
  if (field.data_type === "money") return money(v.text, locale);
  if (field.data_type === "ratio" || field.data_type === "percentage")
    return percent(Number(v.text), locale);
  return v.text;
}

/** An official label written all in capitals, put in sentence case. */
export const calm = (text: string) =>
  text.length > 3 && text === text.toUpperCase() && /[A-ZÁÉÍÓÚÑ]/.test(text)
    ? text.charAt(0) + text.slice(1).toLowerCase()
    : text;

export function dateWords(iso: string, locale: string): string {
  return new Intl.DateTimeFormat(locale, {
    day: "numeric",
    month: "short",
    year: "numeric",
  }).format(new Date(`${iso.slice(0, 10)}T12:00:00`));
}

export function timeWords(iso: string, locale: string): string {
  return new Intl.DateTimeFormat(locale, {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(iso));
}

export function dueWords(
  daysLeft: number | null,
  daysOverdue: number | null,
): { text: string; tone: Tone } {
  if (daysOverdue !== null && daysOverdue > 0)
    return { text: `${daysOverdue} days late`, tone: "danger" };
  if (daysLeft === null) return { text: "", tone: "quiet" };
  if (daysLeft === 0) return { text: "Due today", tone: "danger" };
  if (daysLeft <= 7)
    return {
      text: `Due in ${daysLeft} day${daysLeft === 1 ? "" : "s"}`,
      tone: "attention",
    };
  return { text: `Due in ${daysLeft} days`, tone: "source" };
}

/** What a deadline's holiday check covered, when it did not cover all. */
export const COVERAGE_WORDS: Record<string, string> = {
  national_only: "Regional holidays not checked",
  calendar_unavailable: "Holidays not checked",
  territory_unverified: "Regional holidays not confirmed",
};

const LAW_KINDS: Record<string, string> = {
  ley: "Ley",
  rd: "RD",
  rdl: "RDL",
};

/** A legal reference shaped for reading. The product takes the citation
 * text from the box's help card (`modelo.work.casilla_help`). */
export function citation(ref: string): string {
  const [law = ref, part] = ref.split(":");
  const m = /^(ley|rdl|rd|orden-[a-z]+)-(\d+)-(\d{4})$/.exec(law);
  if (!m) return ref;
  const kind = LAW_KINDS[m[1]!] ?? `Orden ${m[1]!.slice(6).toUpperCase()}/`;
  const name = kind.endsWith("/")
    ? `${kind}${m[2]}/${m[3]}`
    : `${kind} ${m[2]}/${m[3]}`;
  const where = part?.replace(/^art-/, "art. ").replace(/-/g, " ") ?? "";
  return where ? `${name}, ${where}` : name;
}
