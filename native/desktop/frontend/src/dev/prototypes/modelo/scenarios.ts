import type { FormIssue } from "./types";

// What the read models report after steps a fresh synthetic profile never
// reaches. Findings are in the form's own wire shape, with the catalogue keys
// and facts the verification really emits; the AEAT side comes from the
// calendar read, never from the form; history and sources are scenario data
// in the shape their reads will take.

export const ISSUES_130: FormIssue[] = [
  {
    finding: {
      kind: "missing_required_casilla",
      severity: "blocking",
      casilla_id: "18",
      message_locale_key:
        "application.modelo.findings.missing_required_casilla",
      message_facts: { casilla_id: "18" },
      legal_refs: ["orden-eha-672-2007:art-1"],
    },
    box: "18",
    attention: "missing",
    action_locale_key:
      "application.modelo.work_form.finding_action.enter_box_value",
  },
  {
    finding: {
      kind: "advisory",
      severity: "advisory",
      casilla_id: "05",
      message_locale_key:
        "application.modelo.findings.cross_period_zero_value_previous_filing",
      message_facts: {
        source_modelo: "130",
        source_filing_year: 2026,
        source_period: "2T",
        target_modelo: "130",
        target_filing_year: 2026,
        target_period: "3T",
      },
      legal_refs: ["rd-439-2007:art-110"],
    },
    box: "05",
    attention: "check",
    action_locale_key:
      "application.modelo.work_form.finding_action.compare_figures",
  },
  {
    finding: {
      kind: "advisory",
      severity: "info",
      casilla_id: null,
      message_locale_key:
        "application.modelo.findings.registry_advisory_predicate_fired",
      message_facts: {},
      legal_refs: ["ley-35-2006:art-99"],
    },
    box: null,
    attention: "info",
    action_locale_key:
      "application.modelo.work_form.finding_action.compare_figures",
  },
];

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
