import checked130En from "@/dev/fixtures/modelo/modelo-130-1T-checked-en.json";
import checked130Es from "@/dev/fixtures/modelo/modelo-130-1T-checked-es.json";
import type { Attention, FormIssue } from "./types";

// What the read models report after steps a fresh synthetic profile never
// reaches. Findings carry the words of a real checked envelope's issue lines;
// the AEAT side comes from the
// calendar read, never from the form; history and sources are scenario data
// in the shape their reads will take.

type IssueLine = {
  level: Attention;
  box: string | null;
  message: string;
  action: string;
  technical: string;
};

const CHECKED_130_LINES: Record<string, IssueLine[]> = {
  en: checked130En.issue_lines as IssueLine[],
  es: checked130Es.issue_lines as IssueLine[],
};

const SEVERITY: Record<Attention, string> = {
  blocks: "blocking",
  missing: "blocking",
  confirm: "advisory",
  check: "advisory",
  info: "info",
};

/** The checked 130's issue lines as the read model words them in English and
 * Spanish; a language the envelope was not read in shows the English. */
export const ISSUES_130: FormIssue[] = CHECKED_130_LINES.en!.map((line, i) => ({
  finding: {
    kind: /: (\w+)/.exec(line.technical)?.[1] ?? "advisory",
    severity: SEVERITY[line.level],
    casilla_id: line.box,
    legal_refs: [],
  },
  box: line.box,
  attention: line.level,
  words: Object.fromEntries(
    ["en", "es", "ca", "hu"].map((locale) => {
      const said = (CHECKED_130_LINES[locale] ?? CHECKED_130_LINES.en!)[i]!;
      return [locale, { message: said.message, action: said.action }];
    }),
  ),
}));

/** What has been seen of the AEAT for this declaration: the calendar read's
 * submission axis, separate from anything recorded here. */
export type AeatSide = {
  state:
    | "not_observed"
    | "submitted_observed"
    | "accepted"
    | "justificante_verified";
  on: string | null;
};

export type Artefact = {
  id: "workbook" | "google" | "report" | "package";
  title: string;
  detail: string;
  icon: "sheet" | "page" | "fileArchive";
  action: string;
  needs: string | null;
  leaves: string | null;
};

export const ARTEFACTS: Artefact[] = [
  {
    id: "workbook",
    title: "Calculation workbook",
    detail: "Every box with its formula, as a spreadsheet file.",
    icon: "sheet",
    action: "Save workbook",
    needs: null,
    leaves: null,
  },
  {
    id: "google",
    title: "Copy in Google Sheets",
    detail:
      "A new copy in your Google Drive; earlier copies are never changed.",
    icon: "sheet",
    action: "Make a copy",
    needs: "Sign in to Google first",
    leaves: "Leaves this computer for your Google Drive",
  },
  {
    id: "report",
    title: "Calculation report",
    detail: "A signed PDF explaining every figure. It is not proof of filing.",
    icon: "page",
    action: "Save report",
    needs: null,
    leaves: null,
  },
  {
    id: "package",
    title: "Package for your accountant",
    detail: "Encrypted for one person, who can send comments back.",
    icon: "fileArchive",
    action: "Prepare package",
    needs: null,
    leaves: null,
  },
];

export type HistoryEvent = {
  at: string;
  kind:
    | "created"
    | "calculated"
    | "changed"
    | "verified"
    | "exported"
    | "filed"
    | "amended";
  detail: string;
  amount?: string;
};

/** The 130 for the third quarter, newest first, matching the recorded story. */
export const HISTORY_130: HistoryEvent[] = [
  { at: "2026-10-14T18:02:00", kind: "filed", detail: "Original declaration" },
  {
    at: "2026-10-14T17:55:00",
    kind: "exported",
    detail: "From the calculation of 17:51",
  },
  {
    at: "2026-10-14T17:52:00",
    kind: "verified",
    detail: "Nothing blocks filing",
  },
  {
    at: "2026-10-14T17:51:00",
    kind: "calculated",
    detail: "",
    amount: "1343.92",
  },
  { at: "2026-10-14T17:49:00", kind: "changed", detail: "Box 18" },
  {
    at: "2026-10-09T11:20:00",
    kind: "calculated",
    detail: "From your records",
  },
  { at: "2026-10-09T11:19:00", kind: "created", detail: "3rd quarter 2026" },
];

export type SourceGroup = {
  family:
    | "records"
    | "registers"
    | "profile"
    | "earlier_filings"
    | "aeat_draft"
    | "your_entries";
  state: "ready" | "partial" | "missing";
  stateWords: string;
  lines: {
    name: string;
    detail: string;
    boxes: string[];
    state: "ready" | "missing";
  }[];
  open: string | null;
  bring: string | null;
};

export const SOURCES_130: SourceGroup[] = [
  {
    family: "records",
    state: "ready",
    stateWords: "As of the last calculation",
    lines: [
      {
        name: "Business income, year to date",
        detail: "143 entries, January to September 2026",
        boxes: ["01"],
        state: "ready",
      },
      {
        name: "Deductible expenses, year to date",
        detail: "88 entries, January to September 2026",
        boxes: ["02"],
        state: "ready",
      },
    ],
    open: "Open your records",
    bring: "Import a bank statement or invoices",
  },
  {
    family: "earlier_filings",
    state: "partial",
    stateWords: "One earlier quarter is not recorded here",
    lines: [
      {
        name: "Instalments paid earlier this year",
        detail: "2nd quarter recorded; 1st quarter not found",
        boxes: ["05"],
        state: "missing",
      },
      {
        name: "Negative results of earlier quarters",
        detail: "None",
        boxes: ["15"],
        state: "ready",
      },
    ],
    open: "Open declarations",
    bring: "Import a filed declaration (PDF)",
  },
  {
    family: "profile",
    state: "partial",
    stateWords: "Last year's income is missing",
    lines: [
      {
        name: "Last year's net business income",
        detail: "Not in your profile",
        boxes: ["13"],
        state: "missing",
      },
    ],
    open: "Open your profile",
    bring: null,
  },
  {
    family: "your_entries",
    state: "ready",
    stateWords: "1 value entered by you",
    lines: [
      {
        name: "Withholdings and payments on account",
        detail: "1.100,00 €",
        boxes: ["06"],
        state: "ready",
      },
    ],
    open: null,
    bring: null,
  },
];
