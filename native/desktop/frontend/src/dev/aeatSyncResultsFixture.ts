import { DEMO_BORRADOR_YEARS } from "./aeatSyncFixture";
import type {
  AeatSyncResult,
  AeatSyncResults,
  AeatSyncResultsPort,
  FiledRow,
  NotificationRow,
} from "../shell/aeatSyncResults";

/** What the scenario's AEAT results are served. */
export type AeatSyncResultsMode =
  /** Every kind of result: news, changes, failures, an unread notification. */
  | "mixed"
  /** Everything read and nothing new anywhere. */
  | "quiet"
  /** Nothing was found at AEAT. */
  | "empty"
  /** The reads failed, each for a different reason. */
  | "failed"
  /** The last read of some data ended without a known answer. */
  | "unknown"
  /** The results cannot be read. */
  | "unavailable";

const DAY = 24 * 60 * 60 * 1000;
const ago = (days: number) => new Date(Date.now() - days * DAY).toISOString();

function summary(
  area: AeatSyncResult["area"],
  patch: Partial<AeatSyncResult>,
): AeatSyncResult {
  return {
    area,
    outcome: "brought",
    at: ago(0),
    new_count: 0,
    changed_count: 0,
    failed: [],
    review_pending: false,
    ...patch,
  };
}

const filed: FiledRow[] = [
  {
    form: "303",
    year: 2025,
    period: "3T",
    match: "matched",
    record: { status: "marked_filed", on: ago(40) },
    aeat: { seen_on: ago(0) },
    receipt: "confirmed",
    differences: [],
  },
  {
    form: "303",
    year: 2025,
    period: "2T",
    match: "matched",
    record: { status: "marked_filed", on: ago(130) },
    aeat: { seen_on: ago(0) },
    receipt: "not_confirmed",
    differences: [],
  },
  {
    form: "130",
    year: 2025,
    period: "3T",
    match: "differing",
    record: { status: "marked_filed", on: ago(38) },
    aeat: { seen_on: ago(0) },
    receipt: "not_confirmed",
    differences: ["status"],
  },
  {
    form: "390",
    year: 2024,
    period: null,
    match: "aeat_only",
    record: null,
    aeat: { seen_on: ago(0) },
    receipt: "not_confirmed",
    differences: [],
  },
  {
    form: "111",
    year: 2024,
    period: "4T",
    match: "aeat_only",
    record: null,
    aeat: { seen_on: ago(0) },
    receipt: "not_confirmed",
    differences: [],
  },
  {
    form: "115",
    year: 2025,
    period: "3T",
    match: "local_only",
    record: { status: "marked_filed", on: ago(35) },
    aeat: null,
    receipt: "not_confirmed",
    differences: [],
  },
  {
    form: "130",
    year: 2025,
    period: "4T",
    match: "aeat_only",
    record: { status: "draft", on: ago(5) },
    aeat: { seen_on: ago(0) },
    receipt: "not_confirmed",
    differences: [],
  },
];

const notifications: NotificationRow[] = [
  {
    subject: "Requerimiento de información sobre el modelo 303",
    received_on: ago(2),
    read: false,
    read_on: null,
  },
  {
    subject: "Aviso de vencimiento de plazo",
    received_on: ago(6),
    read: false,
    read_on: null,
  },
  {
    subject: "Comunicación sobre el modelo 130",
    received_on: ago(25),
    read: true,
    read_on: ago(24),
  },
  {
    subject: "Acuse de recibo de la declaración anual",
    received_on: ago(80),
    read: true,
    read_on: ago(79),
  },
];

function served(mode: AeatSyncResultsMode): AeatSyncResults {
  const years = { borrador_years: [...DEMO_BORRADOR_YEARS] };
  switch (mode) {
    case "mixed":
      return {
        areas: [
          summary("census", { changed_count: 3, review_pending: true }),
          summary("filed", {
            new_count: 2,
            changed_count: 1,
            failed: [{ part: 2, year: 2023, reason: "unavailable" }],
          }),
          summary("notifications", { new_count: 2 }),
          summary("vat", { outcome: "nothing_found" }),
          summary("borrador", { outcome: "nothing_found", at: null }),
          summary("identity", { new_count: 1 }),
        ],
        filed,
        notifications,
        ...years,
      };
    case "quiet":
      return {
        areas: [
          summary("census", {}),
          summary("filed", {}),
          summary("notifications", {}),
          summary("vat", {}),
          summary("borrador", { outcome: "nothing_found", at: null }),
          summary("identity", {}),
        ],
        filed: filed.filter((row) => row.match === "matched"),
        notifications: notifications.filter((row) => row.read),
        ...years,
      };
    case "empty":
      return {
        areas: [
          summary("census", { outcome: "nothing_found" }),
          summary("filed", { outcome: "nothing_found" }),
          summary("notifications", { outcome: "nothing_found" }),
          summary("vat", { outcome: "nothing_found" }),
          summary("borrador", { outcome: "nothing_found", at: null }),
          summary("identity", { outcome: "nothing_found" }),
        ],
        filed: [],
        notifications: [],
        ...years,
      };
    case "failed":
      return {
        areas: [
          summary("census", {
            outcome: "failed",
            failed: [{ part: 0, year: null, reason: "no_access" }],
          }),
          summary("filed", {
            outcome: "failed",
            new_count: 1,
            failed: [
              { part: 1, year: 2025, reason: "session_ended" },
              { part: 2, year: 2024, reason: "refused" },
              { part: 3, year: 2023, reason: "other" },
            ],
          }),
          summary("notifications", {
            outcome: "failed",
            failed: [{ part: 0, year: null, reason: "unavailable" }],
          }),
          summary("vat", {
            outcome: "failed",
            failed: [{ part: 0, year: 2025, reason: "other" }],
          }),
          summary("borrador", { outcome: "nothing_found", at: null }),
          summary("identity", {
            outcome: "failed",
            failed: [{ part: 0, year: null, reason: "session_ended" }],
          }),
        ],
        filed: filed.filter((row) => row.match === "matched"),
        notifications: [],
        ...years,
      };
    case "unknown":
      return {
        areas: [
          summary("census", { outcome: "unknown", at: ago(1) }),
          summary("filed", { outcome: "unknown", at: ago(1), new_count: 2 }),
          summary("notifications", { outcome: "brought" }),
          summary("vat", { outcome: "brought" }),
          summary("borrador", { outcome: "nothing_found", at: null }),
          summary("identity", { outcome: "brought" }),
        ],
        filed,
        notifications,
        ...years,
      };
    case "unavailable":
      throw new Error("unavailable");
  }
}

/** The results' host port over demo data. A retry or an import is recorded
 * and changes nothing, as no read is behind it here. */
export function aeatSyncResultsFixture(
  mode: AeatSyncResultsMode,
  say: (line: string) => void,
  picked: "file" | "cancelled" = "file",
  importResult: "imported" | "nothing_found" | "failed" = "imported",
): AeatSyncResultsPort {
  return {
    results() {
      try {
        return Promise.resolve(served(mode));
      } catch {
        return Promise.reject({ code: "unavailable" });
      }
    },
    retry(_profile, area, part, acknowledgedUnknown) {
      say(
        `aeatSyncResults.retry ${area} ${part ?? "all"} acknowledged=${acknowledgedUnknown}`,
      );
      return Promise.resolve();
    },
    pickBorrador() {
      return Promise.resolve(
        picked === "file"
          ? { token: "synthetic", name: "borrador-2025.pdf" }
          : null,
      );
    },
    importBorrador(_profile, _file, year) {
      say(`aeatSyncResults.importBorrador ${year ?? ""}`.trim());
      return importResult === "failed"
        ? Promise.reject({ code: "unavailable" })
        : Promise.resolve(importResult);
    },
  };
}
