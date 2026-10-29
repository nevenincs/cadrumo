import type {
  AeatSyncArea,
  AeatSyncPort,
  AeatSyncStart,
  AeatSyncStatus,
} from "../shell/aeatSync";

/** What the scenario's AEAT data page is served. */
export type AeatSyncMode =
  /** Nothing was ever brought. */
  | "never"
  /** Every state the page words, with counts. */
  | "mixed"
  /** The status read fails. */
  | "unavailable";

const DAY = 24 * 60 * 60 * 1000;

function mixed(now: number): AeatSyncArea[] {
  const ago = (days: number) => new Date(now - days * DAY).toISOString();
  return [
    {
      area: "census",
      state: "current",
      captured_at: ago(12),
      last_attempt: { at: ago(12), outcome: "brought" },
      counts: [],
      update: "bring",
    },
    {
      area: "filed",
      state: "possibly_stale",
      captured_at: ago(130),
      last_attempt: { at: ago(3), outcome: "failed" },
      counts: [
        { kind: "filed_matched", value: 9 },
        { kind: "filed_aeat_only", value: 2 },
        { kind: "filed_local_only", value: 1 },
        { kind: "filed_differing", value: 1 },
      ],
      update: "bring",
    },
    {
      area: "notifications",
      state: "possibly_stale",
      captured_at: ago(20),
      last_attempt: { at: ago(1), outcome: "unknown" },
      counts: [{ kind: "unread_notifications", value: 3 }],
      update: "bring",
    },
    {
      area: "vat",
      state: "never_brought",
      captured_at: null,
      last_attempt: null,
      counts: [],
      update: "bring",
    },
    {
      area: "borrador",
      state: "unavailable",
      captured_at: null,
      last_attempt: null,
      counts: [],
      update: "import",
    },
    {
      area: "identity",
      state: "current",
      captured_at: ago(40),
      last_attempt: { at: ago(2), outcome: "nothing_found" },
      counts: [],
      update: "bring",
    },
  ];
}

function never(): AeatSyncArea[] {
  return (
    ["census", "filed", "notifications", "vat", "borrador", "identity"] as const
  ).map((area) => ({
    area,
    state: "never_brought",
    captured_at: null,
    last_attempt: null,
    counts: [],
    update: area === "borrador" ? "import" : "bring",
  }));
}

/** The AEAT data page's host port over demo data. A start is recorded and
 * changes nothing, as no flow is behind it here. */
export function aeatSyncFixture(
  mode: AeatSyncMode,
  say: (line: string) => void,
): AeatSyncPort {
  const listeners = new Set<() => void>();
  return {
    status() {
      if (mode === "unavailable")
        return Promise.reject({ code: "unavailable" });
      const status: AeatSyncStatus = {
        profile_id: "demo",
        areas: mode === "never" ? never() : mixed(Date.now()),
      };
      return Promise.resolve(status);
    },
    observe(changed) {
      listeners.add(changed);
      return Promise.resolve(() => listeners.delete(changed));
    },
    start(_profile: string, request: AeatSyncStart) {
      say(`aeatSync.start ${request.areas.join(",")}`);
      listeners.forEach((listener) => listener());
      return Promise.resolve();
    },
  };
}
